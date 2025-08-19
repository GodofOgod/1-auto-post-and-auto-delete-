# © 2025 FtKrishna. All rights reserved.
# Channel  : https://t.me/NxMirror
# Contact  : @FTKrshna

from bot.logger import setup_logger
from motor.motor_asyncio import AsyncIOMotorClient
from config import DB_URL
from datetime import datetime
from bson import ObjectId

logger = setup_logger(__name__)

class MongoDB:
    def __init__(self):
        self.client = AsyncIOMotorClient(DB_URL)
        self.db = self.client["krshna"]
        self.channels = self.db.channels
        self.default_buttons = self.db.default_buttons
        self.schedules = self.db.schedules   # ✅ new collection for scheduled broadcasts

    # ----------------- CHANNELS -----------------
    async def add_channel(self, channel_id: int, title: str) -> bool:
        try:
            if not await self.channels.find_one({"channel_id": channel_id}):
                await self.channels.insert_one({"channel_id": channel_id, "title": title})
                logger.info(f"Added channel {channel_id} ({title}) to database")
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding channel: {str(e)}")
            return False

    async def get_channels(self) -> list:
        try:
            cursor = self.channels.find()
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Error fetching channels: {str(e)}")
            return []

    async def remove_channel(self, channel_id: int) -> bool:
        try:
            result = await self.channels.delete_one({"channel_id": channel_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error removing channel: {str(e)}")
            return False

    async def clear_all_channels(self) -> int:
        try:
            result = await self.channels.delete_many({})
            logger.info(f"Cleared {result.deleted_count} channels from database")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error clearing all channels: {str(e)}")
            return 0

    # ----------------- DEFAULT BUTTONS -----------------
    async def set_default_buttons(self, user_id: int, button_text: str) -> bool:
        try:
            await self.default_buttons.update_one(
                {"user_id": user_id},
                {"$set": {"button_text": button_text}},
                upsert=True
            )
            logger.info(f"Saved default buttons for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving default buttons for user {user_id}: {str(e)}")
            return False

    async def get_default_buttons(self, user_id: int) -> str | None:
        try:
            doc = await self.default_buttons.find_one({"user_id": user_id})
            if doc:
                return doc.get("button_text")
            return None
        except Exception as e:
            logger.error(f"Error fetching default buttons for user {user_id}: {str(e)}")
            return None

    async def delete_default_buttons(self, user_id: int) -> bool:
        try:
            result = await self.default_buttons.delete_one({"user_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting default buttons for user {user_id}: {str(e)}")
            return False

    # ----------------- SCHEDULED BROADCASTS -----------------
    async def save_schedule(self, user_id: int, content: dict, schedule_time: datetime) -> str | None:
        """Save a new scheduled broadcast."""
        try:
            result = await self.schedules.insert_one({
                "user_id": user_id,
                "content": content,
                "schedule_time": schedule_time,
                "status": "pending",
                "created_at": datetime.utcnow()
            })
            logger.info(f"Scheduled broadcast for {schedule_time} by user {user_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error saving schedule: {str(e)}")
            return None

    async def get_due_schedules(self, now: datetime) -> list:
        """Get all broadcasts that should be sent by now."""
        try:
            cursor = self.schedules.find({
                "schedule_time": {"$lte": now},
                "status": "pending"
            })
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Error fetching due schedules: {str(e)}")
            return []

    async def mark_done(self, schedule_id: str) -> bool:
        """Mark a scheduled broadcast as done."""
        try:
            result = await self.schedules.update_one(
                {"_id": ObjectId(schedule_id)},
                {"$set": {"status": "done", "sent_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error marking schedule done: {str(e)}")
            return False

    async def list_schedules(self, user_id: int) -> list:
        """List all schedules of a user (pending + done)."""
        try:
            cursor = self.schedules.find({"user_id": user_id}).sort("schedule_time", 1)
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Error listing schedules: {str(e)}")
            return []

    async def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel (delete) a scheduled broadcast by ID."""
        try:
            result = await self.schedules.delete_one({"_id": ObjectId(schedule_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error canceling schedule: {str(e)}")
            return False


mongo_db = MongoDB()
