from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config

# ── Keyboards ──────────────────────────────────────────────────────────────────

def start_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Help",    callback_data="help"),
            InlineKeyboardButton("👤 Profile", callback_data="profile"),
        ],
        [
            InlineKeyboardButton("👑 Get Premium", callback_data="premium"),
            InlineKeyboardButton("📢 Channel", url=Config.CHANNEL_URL),
        ],
    ])

def help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Back", callback_data="start")],
    ])

def premium_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Back", callback_data="start")],
    ])

def profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Back", callback_data="start")],
    ])

# ── Message texts ──────────────────────────────────────────────────────────────

START_TEXT = """👋 **Welcome to Xylon Mediafire Bot!**

I can download files & folders from **MediaFire** and send them directly to you on Telegram.

🔗 Just send me any MediaFire link and I'll handle the rest!

**What I support:**
• 📄 Single file downloads
• 📁 Folder downloads (all files)
• 📦 Large file auto-splitting & reassembly guide
• 📊 Live progress bar — speed, ETA, percentage

**Your Status:**
• 🆓 Plan: Free
• 📥 Downloads today: {today} / {limit}

Use /help for all commands."""


HELP_TEXT = """📖 **Xylon Mediafire Bot — Help**

🔗 **How to Download:**
Send any `mediafire.com/file/` or `mediafire.com/folder/` link.

📋 **Commands:**
• /start — Show welcome message
• /help — This help page
• /profile — Your account info & stats
• /history — Your last 10 downloads
• /cancel — Cancel active download
• /ping — Check bot latency

👑 **Premium Commands:**
• /premium — View premium plans & benefits
• /redeem `<key>` — Activate a premium key

⚡ **Premium Benefits:**
• Unlimited daily downloads (free: {free_limit}/day)
• Files up to 4 GB (free: {free_size} MB)
• Priority in download queue
• Detailed file metadata

💬 **Support:** {support}"""


PREMIUM_TEXT = """👑 **Xylon Mediafire Bot Premium**

Go unlimited and supercharge your downloads.

**Free Plan:**
• {free_limit} downloads / day
• Max file size: {free_size} MB
• Shared queue

**👑 Premium Plan:**
• ♾ Unlimited downloads
• Max file size: 4 GB
• Priority queue
• Detailed metadata
• Early access to new features

🔑 **Have a key?**
Use: `/redeem YOUR_KEY`

📩 To purchase, contact: {support}"""


def profile_text(user_id, name, username, today, total, joined, premium):
    plan = "👑 Premium" if premium else "🆓 Free"
    uname = f"@{username}" if username else "N/A"
    return f"""👤 **Your Profile**

🆔 User ID: `{user_id}`
👤 Name: {name}
🏷 Username: {uname}

📊 **Stats:**
• 📥 Downloads today: {today}
• 📦 Total downloads: {total}
• 🗓 Member since: {joined}

⚡ Plan: {plan}"""


def file_info_text(info: dict) -> str:
    return (
        f"📄 **{info['filename']}**\n\n"
        f"📦 Size: `{info['size_mb']} MB`\n"
        f"🗂 Type: `{info['type'] or 'Unknown'}`\n"
        f"🔒 Privacy: `{info['privacy']}`\n"
        f"👤 Owner: `{info['owner']}`\n\n"
        f"⬇️ Starting download..."
    )


def downloading_text(filename: str, size_mb: float, downloaded: int,
                     total: int, speed_mb: float, eta: int) -> str:
    if total > 0:
        pct = downloaded / total * 100
        bar_filled = int(pct / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        eta_str = f"{eta}s" if eta < 60 else f"{eta//60}m {eta%60}s"
        dl_mb = downloaded / 1024 / 1024
        tot_mb = total / 1024 / 1024
        return (
            f"⬇️ **Downloading...**\n\n"
            f"📄 `{filename}`\n"
            f"📦 Size: `{size_mb} MB`\n"
            f"⚡ Speed: `{speed_mb:.1f} MB/s`\n"
            f"⏱ ETA: `{eta_str}`\n\n"
            f"`{bar}` {pct:.1f}%\n"
            f"`{dl_mb:.1f} / {tot_mb:.1f} MB`"
        )
    else:
        dl_mb = downloaded / 1024 / 1024
        return (
            f"⬇️ **Downloading...**\n\n"
            f"📄 `{filename}`\n"
            f"⚡ Speed: `{speed_mb:.1f} MB/s`\n"
            f"`{dl_mb:.1f} MB downloaded`"
        )


def uploading_text(filename: str, uploaded: int, total: int) -> str:
    if total > 0:
        pct = uploaded / total * 100
        bar_filled = int(pct / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        return (
            f"📤 **Uploading to Telegram...**\n\n"
            f"📄 `{filename}`\n"
            f"`{bar}` {pct:.1f}%"
        )
    return f"📤 **Uploading to Telegram...**\n\n📄 `{filename}`"


def done_text(filename: str, size_mb: float) -> str:
    return (
        f"✅ **Done!** `{filename}` delivered.\n\n"
        f"📦 Size: `{size_mb} MB`\n\n"
        f"_Powered by_ **Xylon Mediafire Bot** | {Config.CHANNEL_URL}"
    )


def folder_start_text(folder_name: str, total_files: int, total_mb: float) -> str:
    return (
        f"📁 **Folder:** `{folder_name}`\n"
        f"📄 Files: `{total_files}`\n"
        f"📦 Total Size: `{total_mb:.1f} MB`\n\n"
        f"⬇️ Starting downloads..."
    )


def folder_progress_text(folder_name: str, done: int, total: int,
                         current_file: str) -> str:
    bar_filled = int(done / max(total, 1) * 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)
    return (
        f"📁 **{folder_name}**\n\n"
        f"📄 Current: `{current_file}`\n"
        f"`{bar}` {done}/{total} files"
    )
