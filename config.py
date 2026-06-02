import os

class Config:
    API_ID       = int(os.environ.get("API_ID", 0))
    API_HASH     = os.environ.get("API_HASH", "")
    BOT_TOKEN    = os.environ.get("BOT_TOKEN", "8741784728:AAFLpwz7UZvEUumoxgO2I7ii8Lo-9ZSpa1o")
    MONGO_URI    = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME      = "xylon_mediafire"
    CHANNEL_URL  = os.environ.get("CHANNEL_URL", "https://t.me/XylonBots")
    OWNER_ID     = int(os.environ.get("OWNER_ID", 0))

    FREE_DAILY_LIMIT    = 7
    FREE_MAX_SIZE_MB    = 500
    PREMIUM_MAX_SIZE_MB = 4096

    DOWNLOAD_DIR = "./downloads"
    CHUNK_SIZE   = 512 * 1024   # 512 KB
    TG_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
