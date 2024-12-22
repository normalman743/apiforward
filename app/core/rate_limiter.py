# app/core/rate_limiter.py
from datetime import datetime
from fastapi import HTTPException
from app.utils.redis_client import redis
from typing import Dict
from app.models.logger import logger

class RateLimiter:
    def __init__(self):
        self.redis = redis
        
    async def check_rate_limits(self, api_key: str, rate_limits: Dict):
        now = datetime.now()
        request_id = str(now.timestamp())
        
        logger.info("Starting rate limit check", extra={
            "request_id": request_id,
            "api_key": api_key,
            "timestamp": now
        })
        
        pipe = self.redis.pipeline()
        
        # Check concurrent requests
        concurrent_key = f"concurrent:{api_key}"
        current_concurrent = await self.redis.get(concurrent_key) or 0
        
        logger.debug("Checking concurrent requests", extra={
            "request_id": request_id,
            "api_key": api_key,
            "current_concurrent": int(current_concurrent),
            "limit": rate_limits["concurrent_requests"]
        })
        
        if int(current_concurrent) >= rate_limits["concurrent_requests"]:
            logger.warning("Concurrent request limit exceeded", extra={
                "request_id": request_id,
                "api_key": api_key,
                "current_concurrent": int(current_concurrent),
                "limit": rate_limits["concurrent_requests"]
            })
            raise HTTPException(429, "Too many concurrent requests")
            
        # Generate rate limit keys
        minute_key = f"minute:{api_key}:{now.minute}"
        day_key = f"day:{api_key}:{now.date()}"
        month_key = f"month:{api_key}:{now.year}-{now.month}"
        
        # Get current counts before incrementing
        current_minute = await self.redis.get(minute_key) or 0
        current_day = await self.redis.get(day_key) or 0
        current_month = await self.redis.get(month_key) or 0
        
        logger.debug("Current rate limit counters", extra={
            "request_id": request_id,
            "api_key": api_key,
            "minute_count": int(current_minute),
            "day_count": int(current_day),
            "month_count": int(current_month),
            "minute_limit": rate_limits["requests_per_minute"],
            "day_limit": rate_limits["requests_per_day"],
            "month_limit": rate_limits["requests_per_month"]
        })
        
        # Increment counters
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)
        pipe.incr(day_key)
        pipe.expire(day_key, 86400)
        pipe.incr(month_key)
        pipe.expire(month_key, 2592000)
        
        results = await pipe.execute()
        
        # Check if any limits are exceeded
        if results[0] > rate_limits["requests_per_minute"]:
            logger.warning("Per-minute rate limit exceeded", extra={
                "request_id": request_id,
                "api_key": api_key,
                "current_count": results[0],
                "limit": rate_limits["requests_per_minute"]
            })
            raise HTTPException(429, "Rate limit exceeded (per minute)")
            
        if results[2] > rate_limits["requests_per_day"]:
            logger.warning("Per-day rate limit exceeded", extra={
                "request_id": request_id,
                "api_key": api_key,
                "current_count": results[2],
                "limit": rate_limits["requests_per_day"]
            })
            raise HTTPException(429, "Rate limit exceeded (per day)")
            
        if results[4] > rate_limits["requests_per_month"]:
            logger.warning("Per-month rate limit exceeded", extra={
                "request_id": request_id,
                "api_key": api_key,
                "current_count": results[4],
                "limit": rate_limits["requests_per_month"]
            })
            raise HTTPException(429, "Rate limit exceeded (per month)")
            
        logger.info("Rate limit check passed", extra={
            "request_id": request_id,
            "api_key": api_key,
            "minute_count": results[0],
            "day_count": results[2],
            "month_count": results[4]
        })