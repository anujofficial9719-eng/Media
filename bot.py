#!/usr/bin/env python3
"""
Xylon MediaFire Downloader Bot — main entry point
"""
import logging
import os
from pyrogram import Client
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("xylon")

os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)

app = Client(
    name      = "xylon_mediafire_bot",
    api_id    = Config.API_ID,
    api_hash  = Config.API_HASH,
    bot_token = Config.BOT_TOKEN,
)

# registers all handlers via decorators
import handlers  # noqa: F401, E402

if __name__ == "__main__":
    logger.info("🚀 Starting Xylon MediaFire Bot…")
    app.run()
