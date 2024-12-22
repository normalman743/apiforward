
# app/utils/logger.py
import logging
from datetime import datetime
from typing import Dict
from app.utils import db
from typing import List
logger = logging.getLogger("ai_proxy")

async def log_request(request: Dict, response: Dict, api_key: str, cost: float, retry_attempts: List):
    await db.requests.insert_one({
        "request_id": str(datetime.now().timestamp()),
        "api_key": api_key,
        "model_id": request["model"],
        "timestamp": datetime.now(),
        "request_type": "completion",
        "tokens": response["usage"],
        "cost": cost,
        "status": "completed",
        "retry_attempts": retry_attempts
    })