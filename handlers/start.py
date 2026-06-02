import time
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

from config import Config
from database import db
from texts import (
    START_TEXT, HELP_TEXT, PREMIUM_TEXT,
    profile_text,
    start_keyboard, help_keyboard, premium_keyboard, profile_keyboard,
)


# ── /start ─────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message):
    user   = message.from_user
    today  = await db.get_downloads_today(user.id)
    prem   = await db.is_premium(user.id)
    limit  = "∞" if prem else Config.FREE_DAILY_LIMIT

    text = START_TEXT.format(today=today, limit=limit)

    await message.reply_photo(
        photo="assets/logo.jpg",
        caption=text,
        reply_markup=start_keyboard(),
    )


# ── /help ──────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("help") & filters.private)
async def cmd_help(client: Client, message: Message):
    text = HELP_TEXT.format(
        free_limit=Config.FREE_DAILY_LIMIT,
        free_size=Config.FREE_MAX_SIZE_MB,
        support=Config.CHANNEL_URL,
    )
    await message.reply(text, reply_markup=help_keyboard())


# ── /premium ───────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("premium") & filters.private)
async def cmd_premium(client: Client, message: Message):
    text = PREMIUM_TEXT.format(
        free_limit=Config.FREE_DAILY_LIMIT,
        free_size=Config.FREE_MAX_SIZE_MB,
        support=Config.CHANNEL_URL,
    )
    await message.reply(text, reply_markup=premium_keyboard())


# ── /profile ───────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("profile") & filters.private)
async def cmd_profile(client: Client, message: Message):
    user   = message.from_user
    dbuser = await db.get_user(user.id)
    today  = await db.get_downloads_today(user.id)
    text   = profile_text(
        user_id  = user.id,
        name     = user.first_name,
        username = user.username,
        today    = today,
        total    = dbuser.get("total_downloads", 0),
        joined   = dbuser.get("joined", "N/A"),
        premium  = dbuser.get("premium", False),
    )
    await message.reply(text, reply_markup=profile_keyboard())


# ── /history ───────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("history") & filters.private)
async def cmd_history(client: Client, message: Message):
    history = await db.get_history(message.from_user.id)
    if not history:
        await message.reply("📭 No download history yet.")
        return

    lines = ["📋 **Your last downloads:**\n"]
    for i, h in enumerate(reversed(history), 1):
        lines.append(f"{i}. `{h['filename']}` — {h['size_mb']} MB  _{h['time']}_")
    await message.reply("\n".join(lines))


# ── /ping ──────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("ping") & filters.private)
async def cmd_ping(client: Client, message: Message):
    t = time.monotonic()
    m = await message.reply("🏓 Pong!")
    ms = int((time.monotonic() - t) * 1000)
    await m.edit(f"🏓 Pong! `{ms} ms`")


# ── /redeem ────────────────────────────────────────────────────────────────────

VALID_KEYS = {}   # key -> True  (populate from DB / env as needed)

@Client.on_message(filters.command("redeem") & filters.private)
async def cmd_redeem(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Usage: `/redeem YOUR_KEY`")
        return
    key = parts[1].strip()
    if key in VALID_KEYS:
        await db.set_premium(message.from_user.id, True)
        VALID_KEYS.pop(key)
        await message.reply("✅ Premium activated! Enjoy unlimited downloads.")
    else:
        await message.reply("❌ Invalid or already used key.")


# ── /stats (owner only) ────────────────────────────────────────────────────────

@Client.on_message(filters.command("stats") & filters.private)
async def cmd_stats(client: Client, message: Message):
    if message.from_user.id != Config.OWNER_ID:
        return
    s = await db.get_stats()
    await message.reply(
        f"📊 **Bot Stats**\n\n"
        f"👥 Total users: `{s['total']}`\n"
        f"👑 Premium users: `{s['premium']}`"
    )


# ── Callback query handler ─────────────────────────────────────────────────────

@Client.on_callback_query()
async def on_callback(client: Client, cb: CallbackQuery):
    user = cb.from_user
    data = cb.data

    if data == "start":
        today = await db.get_downloads_today(user.id)
        prem  = await db.is_premium(user.id)
        limit = "∞" if prem else Config.FREE_DAILY_LIMIT
        text  = START_TEXT.format(today=today, limit=limit)
        await cb.message.edit_caption(caption=text, reply_markup=start_keyboard())

    elif data == "help":
        text = HELP_TEXT.format(
            free_limit=Config.FREE_DAILY_LIMIT,
            free_size=Config.FREE_MAX_SIZE_MB,
            support=Config.CHANNEL_URL,
        )
        await cb.message.edit_caption(caption=text, reply_markup=help_keyboard())

    elif data == "premium":
        text = PREMIUM_TEXT.format(
            free_limit=Config.FREE_DAILY_LIMIT,
            free_size=Config.FREE_MAX_SIZE_MB,
            support=Config.CHANNEL_URL,
        )
        await cb.message.edit_caption(caption=text, reply_markup=premium_keyboard())

    elif data == "profile":
        dbuser = await db.get_user(user.id)
        today  = await db.get_downloads_today(user.id)
        text   = profile_text(
            user_id  = user.id,
            name     = user.first_name,
            username = user.username,
            today    = today,
            total    = dbuser.get("total_downloads", 0),
            joined   = dbuser.get("joined", "N/A"),
            premium  = dbuser.get("premium", False),
        )
        await cb.message.edit_caption(caption=text, reply_markup=profile_keyboard())

    await cb.answer()
