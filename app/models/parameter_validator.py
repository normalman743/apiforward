# app/core/request_handler.py 中的相关方法更新
from fastapi import HTTPException
from typing import Dict
from app.models.logger import logger
from app.models.schemas import EnhancedModelConfig


async def _validate_request(self, request: Dict, model_config: EnhancedModelConfig) -> Dict:
    """验证并转换请求参数"""
    try:
        # 验证模型能力
        if "messages" in request:
            for message in request["messages"]:
                content = message.get("content")
                # 检查是否支持图片输入
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") in ["image", "image_url"]:
                            if "image" not in model_config.capabilities.input_types:
                                raise HTTPException(
                                    status_code=400,
                                    detail=f"Model {model_config.model_id} does not support image input"
                                )

        # 验证参数
        from app.models.parameter_validator import ModelParameterValidator
        validated_params = await ModelParameterValidator.validate_request(
            request,
            model_config
        )

        # 合并验证后的参数
        validated_request = request.copy()
        validated_request.update(validated_params)

        return validated_request

    except Exception as e:
        logger.error(f"Request validation failed", extra={
            "error": str(e),
            "model": model_config.model_id
        })
        raise