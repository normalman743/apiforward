# app/models/database.py
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from app.config import settings

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGODB_URL)
        self.db = self.client.ai_proxy
        
        # 初始化集合属性
        self.models = self.db.models
        self.api_keys = self.db.api_keys
        self.requests = self.db.requests
        self.transactions = self.db.transactions
    
    async def initialize_collections(self):
        """初始化数据库集合"""
        # 获取现有集合列表
        collections = await self.db.list_collection_names()
        
        # 如果集合不存在，创建它们
        required_collections = ['models', 'api_keys', 'requests']
        for collection in required_collections:
            if collection not in collections:
                await self.db.create_collection(collection)
        
        # 可以在这里添加索引创建
        await self.models.create_index("model_id", unique=True)
        await self.api_keys.create_index("api_key", unique=True)
        await self.requests.create_index("request_id")

# 创建全局数据库实例
db = Database()