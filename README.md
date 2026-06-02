# Xylon MediaFire Downloader Bot

Telegram bot that downloads files & folders from MediaFire and delivers them directly to your chat.

## Features
- ✅ Single file downloads
- ✅ Full folder downloads (recursive, all sub-folders)
- ✅ Live progress bar (speed, ETA, %)
- ✅ Free / Premium user system (MongoDB)
- ✅ Daily download limits
- ✅ Download history (/history)
- ✅ /cancel support

## Setup

### 1. Get credentials
- `API_ID` & `API_HASH` → https://my.telegram.org
- `BOT_TOKEN` → @BotFather
- `MONGO_URI` → local MongoDB or Atlas

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your values
```

### 3a. Run with Docker (recommended)
```bash
docker-compose up -d
```

### 3b. Run manually
```bash
pip install -r requirements.txt
python bot.py
```

## Commands
| Command | Description |
|---------|-------------|
| /start  | Welcome message |
| /help   | Help page |
| /profile | Your stats |
| /history | Last 10 downloads |
| /cancel | Cancel active download |
| /ping   | Bot latency |
| /premium | Premium info |
| /redeem `<key>` | Activate premium key |
| /stats  | Bot stats (owner only) |

## Project Structure
```
xylon_mediafire_bot/
├── bot.py           # Entry point
├── config.py        # Configuration
├── database.py      # MongoDB helpers
├── mediafire.py     # Download engine (merged from both scripts)
├── texts.py         # All messages & keyboards
├── handlers/
│   ├── start.py     # /start, /help, /profile, callbacks
│   └── downloader.py # URL handler, file & folder download
├── assets/
│   └── logo.jpg     # Bot logo (add your own)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Add logo
Place your logo image at `assets/logo.jpg`.
