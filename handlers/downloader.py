"""
Handles MediaFire file and folder download requests.

Flow (file):
  URL received → fetch info → check limits → download with progress →
  upload to Telegram with progress → cleanup → log history

Flow (folder):
  URL received → fetch folder info → enumerate all files → for each file:
    download → upload → delete temp → next
"""

import asyncio
import os
import re
import time

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from database import db
import mediafire as mf
from texts import (
    file_info_text, downloading_text, uploading_text,
    done_text, folder_start_text, folder_progress_text,
)

# active download per user  {user_id: asyncio.Task}
_active: dict[int, asyncio.Task] = {}

MF_URL_RE = re.compile(
    r"https?://(?:www\.)?mediafire\.com/(file|file_premium|folder)/([a-zA-Z0-9]+)[^\s]*"
)


# ── URL detector ──────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.text)
async def handle_url(client: Client, message: Message):
    text = message.text or ""
    m    = MF_URL_RE.search(text)
    if not m:
        return   # not a MediaFire link — ignore silently

    url  = m.group(0)
    kind = m.group(1)   # file | file_premium | folder
    uid  = message.from_user.id

    # One download at a time
    if uid in _active and not _active[uid].done():
        await message.reply(
            "⏳ You already have an active download. Use /cancel to stop it first."
        )
        return

    if kind in ("file", "file_premium"):
        task = asyncio.create_task(_handle_file(client, message, url))
    else:
        task = asyncio.create_task(_handle_folder(client, message, url))

    _active[uid] = task
    try:
        await task
    except asyncio.CancelledError:
        await message.reply("🚫 Download cancelled.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        _active.pop(uid, None)


# ── /cancel ───────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("cancel") & filters.private)
async def cmd_cancel(client: Client, message: Message):
    uid  = message.from_user.id
    task = _active.get(uid)
    if task and not task.done():
        task.cancel()
        # reply is sent by the CancelledError handler above
    else:
        await message.reply("ℹ️ No active download to cancel.")


# ── Single file handler ───────────────────────────────────────────────────────

async def _handle_file(client: Client, message: Message, url: str):
    uid = message.from_user.id

    # ── fetch info ──
    status = await message.reply("🔍 Fetching file info...")
    try:
        info = await mf.get_file_info(url)
    except Exception as e:
        await status.edit(f"❌ Could not fetch file info:\n`{e}`")
        return

    # ── size / limit checks ──
    prem     = await db.is_premium(uid)
    max_mb   = Config.PREMIUM_MAX_SIZE_MB if prem else Config.FREE_MAX_SIZE_MB
    today    = await db.get_downloads_today(uid)
    day_lim  = 999999 if prem else Config.FREE_DAILY_LIMIT

    if today >= day_lim:
        await status.edit(
            f"⚠️ Daily limit reached ({Config.FREE_DAILY_LIMIT}/day on Free plan).\n"
            f"Upgrade with /premium for unlimited downloads."
        )
        return

    if info["size_mb"] > max_mb:
        await status.edit(
            f"⚠️ File is `{info['size_mb']} MB`, your limit is `{max_mb} MB`.\n"
            f"Upgrade with /premium for up to 4 GB."
        )
        return

    await status.edit(file_info_text(info))

    # ── download ──
    dest_dir  = os.path.join(Config.DOWNLOAD_DIR, str(uid))
    filename  = info["filename"]
    size_mb   = info["size_mb"]
    dl_start  = time.monotonic()
    last_edit = [0.0]

    async def dl_progress(downloaded: int, total: int):
        now = time.monotonic()
        if now - last_edit[0] < 2:
            return
        last_edit[0] = now
        elapsed  = max(now - dl_start, 0.001)
        speed_mb = (downloaded / 1024 / 1024) / elapsed
        eta      = int((total - downloaded) / max(downloaded / elapsed, 1)) if total else 0
        try:
            await status.edit(
                downloading_text(filename, size_mb, downloaded, total, speed_mb, eta)
            )
        except Exception:
            pass

    try:
        local_path = await mf.download_file(
            download_url  = info["link"],
            dest_dir      = dest_dir,
            filename      = filename,
            expected_hash = info["hash"],
            progress_cb   = dl_progress,
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await status.edit(f"❌ Download failed:\n`{e}`")
        return

    # ── upload ──
    up_start  = time.monotonic()
    last_edit[0] = 0.0
    file_size = os.path.getsize(local_path)

    async def up_progress(current: int, total: int):
        now = time.monotonic()
        if now - last_edit[0] < 2:
            return
        last_edit[0] = now
        try:
            await status.edit(uploading_text(filename, current, total))
        except Exception:
            pass

    try:
        await status.edit(uploading_text(filename, 0, file_size))
        await client.send_document(
            chat_id   = message.chat.id,
            document  = local_path,
            caption   = done_text(filename, size_mb),
            progress  = up_progress,
        )
        await status.delete()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await status.edit(f"❌ Upload failed:\n`{e}`")
        return
    finally:
        _safe_delete(local_path)

    # ── log ──
    await db.increment_downloads(uid)
    await db.add_history(uid, filename, size_mb)


# ── Folder handler ────────────────────────────────────────────────────────────

async def _handle_folder(client: Client, message: Message, url: str):
    uid = message.from_user.id

    m = re.search(r"mediafire\.com/folder/([a-zA-Z0-9]+)", url)
    if not m:
        await message.reply("❌ Invalid folder URL.")
        return
    folder_key = m.group(1)

    status = await message.reply("🔍 Fetching folder info...")

    try:
        folder_info = await mf.get_folder_info(folder_key)
        folder_name = folder_info.get("name", "Folder")
    except Exception as e:
        await status.edit(f"❌ Could not fetch folder info:\n`{e}`")
        return

    try:
        files = await mf.get_folder_files(folder_key)
    except Exception as e:
        await status.edit(f"❌ Could not enumerate folder files:\n`{e}`")
        return

    if not files:
        await status.edit("📭 Folder is empty.")
        return

    total_mb = sum(f["size_mb"] for f in files)
    await status.edit(folder_start_text(folder_name, len(files), total_mb))
    await asyncio.sleep(1)

    prem   = await db.is_premium(uid)
    max_mb = Config.PREMIUM_MAX_SIZE_MB if prem else Config.FREE_MAX_SIZE_MB

    dest_dir = os.path.join(Config.DOWNLOAD_DIR, str(uid), folder_name)

    for idx, finfo in enumerate(files, 1):
        # Check cancellation
        await asyncio.sleep(0)

        fname   = finfo["filename"]
        fsize   = finfo["size_mb"]
        dl_start = time.monotonic()
        last_edit = [0.0]

        if fsize > max_mb:
            await message.reply(
                f"⚠️ Skipping `{fname}` ({fsize} MB) — exceeds your {max_mb} MB limit."
            )
            continue

        await status.edit(
            folder_progress_text(folder_name, idx - 1, len(files), fname)
        )

        async def dl_progress(downloaded: int, total: int,
                               _fname=fname, _fsize=fsize):
            now = time.monotonic()
            if now - last_edit[0] < 2:
                return
            last_edit[0] = now
            elapsed  = max(now - dl_start, 0.001)
            speed_mb = (downloaded / 1024 / 1024) / elapsed
            eta      = int((total - downloaded) / max(downloaded / elapsed, 1)) if total else 0
            try:
                await status.edit(
                    downloading_text(_fname, _fsize, downloaded, total, speed_mb, eta)
                )
            except Exception:
                pass

        try:
            local_path = await mf.download_file(
                download_url  = finfo["link"],
                dest_dir      = dest_dir,
                filename      = fname,
                expected_hash = finfo.get("hash", ""),
                progress_cb   = dl_progress,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await message.reply(f"❌ Failed to download `{fname}`:\n`{e}`")
            continue

        # upload
        file_size = os.path.getsize(local_path)
        up_last   = [0.0]

        async def up_progress(current: int, total: int,
                               _fname=fname):
            now = time.monotonic()
            if now - up_last[0] < 2:
                return
            up_last[0] = now
            try:
                await status.edit(uploading_text(_fname, current, total))
            except Exception:
                pass

        try:
            await client.send_document(
                chat_id  = message.chat.id,
                document = local_path,
                caption  = done_text(fname, fsize),
                progress = up_progress,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await message.reply(f"❌ Failed to upload `{fname}`:\n`{e}`")
        finally:
            _safe_delete(local_path)

        await db.increment_downloads(uid)
        await db.add_history(uid, fname, fsize)

    await status.edit(
        f"✅ **Done!** All {len(files)} files from `{folder_name}` delivered.\n\n"
        f"_Powered by_ **Xylon Mediafire Bot** | {Config.CHANNEL_URL}"
    )


# ── Util ──────────────────────────────────────────────────────────────────────

def _safe_delete(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
