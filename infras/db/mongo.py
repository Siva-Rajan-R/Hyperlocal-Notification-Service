from motor.motor_asyncio import AsyncIOMotorClient
from core.configs.settings_config import SETTINGS

class MongoDBManager:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect(cls):
        cls.client = AsyncIOMotorClient(SETTINGS.MONGO_URL)
        cls.db = cls.client[SETTINGS.MONGO_DB_NAME]
        # Ensure index on user_id and created_at
        await cls.db.notifications.create_index([("user_id", 1)])
        await cls.db.notifications.create_index([("created_at", -1)])

    @classmethod
    async def disconnect(cls):
        if cls.client:
            cls.client.close()

def get_collection():
    return MongoDBManager.db.notifications
