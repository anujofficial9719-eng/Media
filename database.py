from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config


class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URI)
        self.db     = self.client[Config.DB_NAME]
        self.users  = self.db["users"]

    async def get_user(self, user_id: int) -> dict:
        user = await self.users.find_one({"_id": user_id})
        if not user:
            user = await self._create_user(user_id)
        return user

    async def _create_user(self, user_id: int) -> dict:
        doc = {
            "_id":             user_id,
            "premium":         False,
            "downloads_today": 0,
            "total_downloads": 0,
            "last_reset":      datetime.now(timezone.utc).date().isoformat(),
            "joined":          datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "history":         [],
        }
        await self.users.insert_one(doc)
        return doc

    async def _reset_if_needed(self, user_id: int):
        user  = await self.get_user(user_id)
        today = datetime.now(timezone.utc).date().isoformat()
        if user.get("last_reset") != today:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {"downloads_today": 0, "last_reset": today}}
            )

    async def get_downloads_today(self, user_id: int) -> int:
        await self._reset_if_needed(user_id)
        user = await self.get_user(user_id)
        return user.get("downloads_today", 0)

    async def increment_downloads(self, user_id: int):
        await self._reset_if_needed(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$inc": {"downloads_today": 1, "total_downloads": 1}}
        )

    async def add_history(self, user_id: int, filename: str, size_mb: float):
        entry = {
            "filename": filename,
            "size_mb":  round(size_mb, 2),
            "time":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }
        await self.users.update_one(
            {"_id": user_id},
            {"$push": {"history": {"$each": [entry], "$slice": -10}}}
        )

    async def get_history(self, user_id: int) -> list:
        user = await self.get_user(user_id)
        return user.get("history", [])

    async def is_premium(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return user.get("premium", False)

    async def set_premium(self, user_id: int, status: bool = True):
        await self.users.update_one(
            {"_id": user_id},
            {"$set": {"premium": status}}
        )

    async def get_stats(self) -> dict:
        total   = await self.users.count_documents({})
        premium = await self.users.count_documents({"premium": True})
        return {"total": total, "premium": premium}


db = Database()
