# app/utils/redis_client.py
from redis import asyncio as aioredis
from app.config import settings

redis = aioredis.from_url(settings.REDIS_URL)