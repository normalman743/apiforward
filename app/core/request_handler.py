# app/core/request_handler.py
from typing import Dict, Optional, List
from datetime import datetime
from fastapi import HTTPException
import asyncio
import json
import traceback

from app.core.rate_limiter import RateLimiter
from app.core.billing import BillingSystem
from app.config import settings
from app.models.model_manager import ModelManager
from app.providers.base import BaseProvider
from app.providers.openai import OpenAIProvider
from app.providers.anthropic import AnthropicProvider
from app.providers.xai import XAIProvider
from app.models.logger import logger

class RequestHandler:
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.billing = BillingSystem()
        self.model_manager = ModelManager()
        
        # Initialize providers with API keys from settings
        self.providers = {
            "openai": OpenAIProvider(api_key=settings.OPENAI_API_KEY),
            "anthropic": AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY),
            "xai": XAIProvider(api_key=settings.XAI_API_KEY)
        }
    
    async def handle_request(self, request: Dict, api_key: str):
        """处理API请求的主函数"""
        request_id = str(datetime.now().timestamp())
        start_time = datetime.now()
        retry_attempts = []
        
        logger.info(f"Starting request processing", extra={
            "request_id": request_id,
            "api_key": api_key,
            "model": request.get("model"),
            "timestamp": start_time
        })

        try:
            # 1. 验证API密钥和获取配置
            logger.debug(f"Validating API key and getting config", extra={
                "request_id": request_id,
                "api_key": api_key
            })
            api_config = await self._get_api_config(api_key)
            
            if not api_config:
                logger.error(f"Invalid API key", extra={
                    "request_id": request_id,
                    "api_key": api_key
                })
                raise HTTPException(401, "Invalid API key")
            
            # 2. 获取模型配置
            logger.debug(f"Getting model config", extra={
                "request_id": request_id,
                "model": request.get("model")
            })
            model_config = await self.model_manager.get_model_config(request["model"])
            
            if not model_config:
                logger.error(f"Model not found", extra={
                    "request_id": request_id,
                    "model": request.get("model")
                })
                raise HTTPException(400, "Model not found")
            
            # 3. 检查速率限制
            logger.debug(f"Checking rate limits", extra={
                "request_id": request_id,
                "api_key": api_key,
                "rate_limits": api_config["rate_limits"]
            })
            await self.rate_limiter.check_rate_limits(api_key, api_config["rate_limits"])
            
            # 4. 验证请求参数
            logger.debug(f"Validating request parameters", extra={
                "request_id": request_id,
                "parameters": {k: v for k, v in request.items() if k != "messages"}
            })
            await self._validate_request(request, model_config)
            
            # 5. 检查余额
            estimated_cost = await self._estimate_cost(request, model_config)
            logger.debug(f"Checking balance", extra={
                "request_id": request_id,
                "api_key": api_key,
                "estimated_cost": estimated_cost
            })
            
            if not await self.billing.check_balance(api_key, estimated_cost):
                logger.warning(f"Insufficient balance", extra={
                    "request_id": request_id,
                    "api_key": api_key,
                    "balance": api_config.get("balance"),
                    "estimated_cost": estimated_cost
                })
                return await self._handle_insufficient_balance(request, api_key, api_config)
            
            # 6. 处理请求（包含重试逻辑）
            logger.info(f"Processing request", extra={
                "request_id": request_id,
                "model": request.get("model"),
                "provider": model_config.get("provider")
            })
            response = await self._process_request_with_retry(
                request, model_config, api_config, retry_attempts
            )
            
            # 7. 处理计费
            actual_cost = await self._calculate_actual_cost(response, model_config)
            logger.info(f"Processing billing", extra={
                "request_id": request_id,
                "api_key": api_key,
                "cost": actual_cost,
                "tokens": response.get("usage", {})
            })
            await self.billing.deduct_balance(api_key, actual_cost)
            
            # 8. 记录请求完成
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            logger.info(f"Request completed", extra={
                "request_id": request_id,
                "api_key": api_key,
                "model": request.get("model"),
                "status": "success",
                "processing_time": processing_time,
                "tokens": response.get("usage", {}),
                "cost": actual_cost,
                "retry_attempts": len(retry_attempts)
            })
            
            await self._log_request(request, response, api_key, actual_cost, retry_attempts)
            return response
            
        except Exception as e:
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            
            logger.error(f"Request failed", extra={
                "request_id": request_id,
                "api_key": api_key,
                "model": request.get("model"),
                "status": "error",
                "processing_time": processing_time,
                "error_details": error_details,
                "retry_attempts": len(retry_attempts)
            })
            
            await self._log_error(request, api_key, error_details)
            raise

    async def _process_request_with_retry(
        self, 
        request: Dict, 
        model_config: Dict,
        api_config: Dict,
        retry_attempts: List
    ) -> Dict:
        """处理请求，包含重试逻辑"""
        retry_config = api_config["retry_config"]
        provider = self.providers[model_config["provider"]]
        
        for attempt in range(retry_config["max_retries"]):
            try:
                logger.debug(f"Processing request attempt {attempt + 1}", extra={
                    "attempt": attempt + 1,
                    "max_retries": retry_config["max_retries"],
                    "model": request.get("model")
                })
                
                response = await provider.completion(request)
                
                if attempt > 0:
                    retry_attempts.append({
                        "attempt": attempt + 1,
                        "timestamp": datetime.now(),
                        "status": "success"
                    })
                
                return response
                
            except Exception as e:
                logger.warning(f"Request attempt failed", extra={
                    "attempt": attempt + 1,
                    "error": str(e),
                    "model": request.get("model")
                })
                
                retry_attempts.append({
                    "attempt": attempt + 1,
                    "timestamp": datetime.now(),
                    "status": "failed",
                    "error": str(e)
                })
                
                if attempt == retry_config["max_retries"] - 1:
                    raise
                    
                await asyncio.sleep(retry_config["retry_delay"] / 1000)

    async def _log_request(
        self, 
        request: Dict, 
        response: Dict, 
        api_key: str, 
        cost: float,
        retry_attempts: List
    ):
        """记录请求信息"""
        log_data = {
            "request_id": str(datetime.now().timestamp()),
            "api_key": api_key,
            "model_id": request["model"],
            "timestamp": datetime.now(),
            "request_type": "completion",
            "parameters": {k: v for k, v in request.items() if k != "messages"},
            "message_count": len(request.get("messages", [])),
            "tokens": response.get("usage", {}),
            "cost": cost,
            "status": "completed",
            "retry_attempts": retry_attempts
        }
        
        # Log message types and counts
        message_types = {}
        for msg in request.get("messages", []):
            role = msg.get("role", "unknown")
            message_types[role] = message_types.get(role, 0) + 1
        log_data["message_types"] = message_types
        
        await self.model_manager.log_request(log_data)
    async def _log_error(
        self, 
        request: Dict, 
        api_key: str, 
        error_details: Dict
    ):
        """记录错误信息"""
        log_data = {
            "request_id": str(datetime.now().timestamp()),
            "api_key": api_key,
            "model_id": request.get("model"),
            "timestamp": datetime.now(),
            "request_type": "completion",
            "parameters": {k: v for k, v in request.items() if k != "messages"},
            "message_count": len(request.get("messages", [])),
            "status": "failed",
            "error_type": error_details["error_type"],
            "error_message": error_details["error_message"],
            "error_traceback": error_details["traceback"]
        }
        
        await self.model_manager.log_request(log_data)

    async def _get_api_config(self, api_key: str) -> Optional[Dict]:
        """获取API密钥配置信息"""
        logger.debug(f"Getting API config for key: {api_key}")
        
        api_config = await self.model_manager.get_api_config(api_key)
        
        if not api_config:
            logger.error(f"API config not found for key: {api_key}")
            return None
            
        # 验证API密钥状态
        if api_config.get("status") != "active":
            logger.warning(f"API key is not active: {api_key}")
            raise HTTPException(403, "API key is not active")
            
        return api_config
        
    async def _validate_request(self, request: Dict, model_config: Dict):
        """验证请求参数"""
        # 验证基本请求结构
        if not request.get("messages"):
            raise HTTPException(400, "Request must contain 'messages' field")
            
        # 验证消息格式
        for message in request["messages"]:
            if not isinstance(message, dict) or "role" not in message or "content" not in message:
                raise HTTPException(400, "Invalid message format")
                
        # 验证模型参数
        allowed_params = model_config["parameters"]
        for param, value in request.items():
            # if NULL, use default value
            if value is None:
                try:
                    request[param] = allowed_params[param]["default"]
                except KeyError:
                    continue
            continue

        for param, value in request.items():
            if param in allowed_params:
                param_config = allowed_params[param]
                
                # 验证并转换参数类型
                try:
                    if param_config["type"] == "float":
                        # 转换为float并验证
                        value = float(value)
                        request[param] = value  # 更新请求中的值
                        if "min" in param_config and value < param_config["min"]:
                            raise HTTPException(400, f"Parameter '{param}' must be >= {param_config['min']}")
                        if "max" in param_config and value > param_config["max"]:
                            raise HTTPException(400, f"Parameter '{param}' must be <= {param_config['max']}")
                            
                    elif param_config["type"] == "int":
                        # 转换为int并验证
                        value = int(float(value))  # 允许从浮点数转换为整数
                        request[param] = value  # 更新请求中的值
                        if "min" in param_config and value < param_config["min"]:
                            raise HTTPException(400, f"Parameter '{param}' must be >= {param_config['min']}")
                        if "max" in param_config and value > param_config["max"]:
                            raise HTTPException(400, f"Parameter '{param}' must be <= {param_config['max']}")
                            
                    elif param_config["type"] == "enum":
                        if value not in param_config["values"]:
                            raise HTTPException(400, f"Parameter '{param}' must be one of: {param_config['values']}")
                            
                except (ValueError, TypeError):
                    raise HTTPException(400, f"Parameter '{param}' has invalid type. Expected {param_config['type']}")
                        
    async def _estimate_cost(self, request: Dict, model_config: Dict) -> float:
        """估算请求成本"""
        # 基于输入消息长度估算token数量
        estimated_input_tokens = sum(len(str(msg.get("content", ""))) // 4 for msg in request["messages"])
        estimated_output_tokens = model_config.get("max_tokens", 2048)  # 使用请求中指定的max_tokens或默认值
        
        # 计算预估成本
        input_cost = (estimated_input_tokens / 1_000_000) * model_config["pricing"]["input_price"]
        output_cost = (estimated_output_tokens / 1_000_000) * model_config["pricing"]["output_price"]
        
        # 添加图片处理成本（如果有）
        image_cost = 0
        for message in request["messages"]:
            content = message.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") in ["image", "image_url"]:
                        image_cost += model_config["pricing"].get("image_input_price", 0)
        
        total_cost = input_cost + output_cost + image_cost
        # 添加一个安全边际
        return total_cost * 1.2  # 增加20%的安全边际
        
    async def _calculate_actual_cost(self, response: Dict, model_config: Dict) -> float:
        """计算实际成本"""
        usage = response.get("usage", {})
        
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        
        input_cost = (input_tokens / 1_000_000) * model_config["pricing"]["input_price"]
        output_cost = (output_tokens / 1_000_000) * model_config["pricing"]["output_price"]
        
        return input_cost + output_cost
        
    async def _handle_insufficient_balance(
        self,
        request: Dict,
        api_key: str,
        api_config: Dict
    ) -> Dict:
        """处理余额不足的情况"""
        logger.warning(f"Insufficient balance for API key: {api_key}")
        
        if not api_config["retry_config"].get("fallback_to_lower_tier", False):
            raise HTTPException(402, "Insufficient balance")
            
        # 尝试查找更低级别的模型
        current_model = await self.model_manager.get_model_config(request["model"])
        if not current_model:
            raise HTTPException(400, "Model not found")
            
        lower_tier_model = await self.model_manager.find_lower_tier_model(
            current_model["capability_level"],
            current_model["capabilities"]
        )
        
        if not lower_tier_model:
            raise HTTPException(402, "Insufficient balance and no lower tier model available")
            
        # 使用更低级别的模型重试请求
        request["model"] = lower_tier_model["model_id"]
        logger.info(f"Falling back to lower tier model: {lower_tier_model['model_id']}")
        
        return await self.handle_request(request, api_key)