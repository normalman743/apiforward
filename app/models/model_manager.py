# app/models/model_manager.py
from datetime import datetime
from typing import Optional, List, Dict
from fastapi import HTTPException
from app.models.database import db
from app.config import settings
from app.models.logger import logger

class RequestHandler:
    async def handle_request(self, request: Dict, api_key: str):
        """处理API请求的主函数"""
        try:
            # 1. 验证API密钥和获取配置
            logger.info(f"Getting API config for key: {api_key}")
            api_config = await self._get_api_config(api_key)
            
            if not api_config:
                logger.error(f"API config not found for key: {api_key}")
                raise HTTPException(401, "Invalid API key")
            
            # 2. 获取模型配置
            model_id = request.get("model")
            logger.info(f"Getting model config for model: {model_id}")
            model_config = await self.model_manager.get_model_config(model_id)
            
            if not model_config:
                logger.error(f"Model config not found for model: {model_id}")
                raise HTTPException(400, "Model not found")
            
            # 3. 检查速率限制
            await self.rate_limiter.check_rate_limits(api_key, api_config["rate_limits"])
            
            # 4. 验证请求参数
            await self._validate_request(request, model_config)
            
            # 5. 处理请求
            response = await self._process_request_with_retry(request, model_config, api_config)
            
            # 6. 记录成功请求
            logger.info("Request completed successfully", extra={
                "api_key": api_key,
                "model": model_id,
                "status": "success",
                "tokens": response.get("usage", {}),
                "cost": await self._calculate_actual_cost(response, model_config)
            })
            
            return response
            
        except Exception as e:
            logger.error("Request failed", extra={
                "api_key": api_key,
                "model": request.get("model"),
                "status": "error",
                "error": str(e)
            })
            raise
        
class ModelManager:
    @staticmethod
    async def init_default_configs():
        """初始化默认模型配置和API密钥到数据库"""
        # 确保集合已经初始化
        await db.initialize_collections()
        
        # 初始化默认模型配置
        await ModelManager._init_default_models()
        
        # 初始化默认API密钥
        await ModelManager._init_default_api_keys()
    
    @staticmethod
    async def _init_default_api_keys():
        """初始化默认API密钥配置"""
        # 检查是否已经初始化
        existing = await db.api_keys.count_documents({})
        if existing > 0:
            return
            
        # 默认API密钥配置
        default_api_keys = [
            {
                "api_key": settings.ADMIN_API_KEY,
                "tier": "admin",
                "balance": 1000.0,  # 初始余额
                "rate_limits": settings.DEFAULT_RATE_LIMITS["admin"],
                "retry_config": settings.DEFAULT_RETRY_CONFIG,
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "api_key": f"{settings.API_KEY_PREFIX}default",  # 默认普通用户API密钥
                "tier": "normal",
                "balance": 100.0,  # 初始余额
                "rate_limits": settings.DEFAULT_RATE_LIMITS["normal"],
                "retry_config": settings.DEFAULT_RETRY_CONFIG,
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        # 批量插入
        await db.api_keys.insert_many(default_api_keys)
    
    @staticmethod
    async def _init_default_models():
        """初始化默认模型配置"""
        # 检查是否已经初始化
        existing = await db.models.count_documents({})
        if existing > 0:
            return
            
        # 默认模型配置
        default_configs = [
            {
                "model_id": "gpt-4o",
                "provider": "openai",
                "capabilities": {
                    "text": True,
                    "image": True,
                    "reply_mode": True
                },
                "pricing": {
                    "input_price": 15.0,
                    "output_price": 50.0,
                    "image_input_price": 0.00765,
                },
                "capability_level": 3,
                "max_tokens": 128000,
                "parameters": {
                    "temperature": {"type": "float", "min": 0, "max": 2, "default": 1.0},
                    "max_tokens": {"type": "int", "min": 1, "max": 4096, "default": 2048},
                    "top_p": {"type": "float", "min": 0, "max": 1, "default": 1.0},
                    "frequency_penalty": {"type": "float", "min": -2, "max": 2, "default": 0.0},
                    "presence_penalty": {"type": "float", "min": -2, "max": 2, "default": 0.0},
                    "response_format": {
                        "type": "enum",
                        "values": ["text", "json_object"],
                        "default": "text"
                    }
                },
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "model_id": "claude-3.5-sonnet",
                "provider": "anthropic",
                "capabilities": {
                    "text": True,
                    "image": True,
                    "reply_mode": True
                },
                "pricing": {
                    "input_price": 15.0,
                    "output_price": 50.0,
                    "image_input_price": 0.00765,
                },
                "capability_level": 3,
                "max_tokens": 128000,
                "parameters": {
                    "temperature": {"type": "float", "min": 0, "max": 2, "default": 1.0},
                    "max_tokens": {"type": "int", "min": 1, "max": 4096, "default": 2048},
                    "top_p": {"type": "float", "min": 0, "max": 1, "default": 1.0}
                },
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "model_id": "grok-vision-beta",
                "provider": "xai",
                "capabilities": {
                    "text": True,
                    "image": True,
                    "reply_mode": True
                },
                "pricing": {
                    "input_price": 5.0,
                    "output_price": 5.0,
                    "image_input_price": 15.0,
                },
                "capability_level": 1,
                "max_tokens": 8192,
                "parameters": {
                    "temperature": {"type": "float", "min": 0, "max": 2, "default": 1.0},
                    "max_tokens": {"type": "int", "min": 1, "max": 8192, "default": 2048},
                    "top_p": {"type": "float", "min": 0, "max": 1, "default": 1.0},
                    "frequency_penalty": {"type": "float", "min": -2, "max": 2, "default": 0.0},
                    "presence_penalty": {"type": "float", "min": -2, "max": 2, "default": 0.0}
                },
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "model_id": "grok-2-vision-1212",
                "provider": "xai",
                "capabilities": {
                    "text": True,
                    "image": True,
                    "reply_mode": True
                },
                "pricing": {
                    "input_price": 2.0,
                    "output_price": 2.0,
                    "image_input_price": 10.0,
                },
                "capability_level": 1,
                "max_tokens": 32768,
                "parameters": {
                    "temperature": {"type": "float", "min": 0, "max": 2, "default": 1.0},
                    "max_tokens": {"type": "int", "min": 1, "max": 32768, "default": 2048},
                    "top_p": {"type": "float", "min": 0, "max": 1, "default": 1.0},
                    "frequency_penalty": {"type": "float", "min": -2, "max": 2, "default": 0.0},
                    "presence_penalty": {"type": "float", "min": -2, "max": 2, "default": 0.0}
                },
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        # 批量插入
        await db.models.insert_many(default_configs)
    
    @staticmethod
    async def get_model_config(model_id: str) -> Optional[Dict]:
        """获取模型配置"""
        return await db.models.find_one({"model_id": model_id})
    
    @staticmethod
    async def update_model_config(self, model_id: str, updates: dict):
        logger.info("Updating model configuration", extra={
            "model_id": model_id,
            "updates": updates
        })
        
        try:
            await db.models.update_one(
                {"model_id": model_id},
                {"$set": updates}
            )
            logger.info("Model configuration updated successfully", extra={
                "model_id": model_id
            })
        except Exception as e:
            logger.error("Model configuration update failed", extra={
                "model_id": model_id,
                "error": str(e)
            })
            raise

    
    @staticmethod
    async def get_active_models() -> List[Dict]:
        """获取所有激活的模型"""
        cursor = db.models.find({"status": "active"})
        return await cursor.to_list(None)
    
    @staticmethod
    async def find_lower_tier_model(current_level: int, capabilities: Dict) -> Optional[Dict]:
        """查找更低级别的模型"""
        query = {
            "capability_level": {"$lt": current_level},
            "capabilities": {"$all": [k for k, v in capabilities.items() if v]},
            "status": "active"
        }
        return await db.models.find_one(query, sort=[("capability_level", -1)])
    
    @staticmethod
    async def get_api_config(api_key: str) -> Optional[Dict]:
        """获取API密钥配置"""
        return await db.api_keys.find_one({"api_key": api_key})
    
    @staticmethod
    async def log_request(log_data: Dict):
        """记录请求日志"""
        await db.requests.insert_one(log_data)