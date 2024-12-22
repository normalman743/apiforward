# app/models/schemas.py
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Union, Literal
from datetime import datetime

# 基础模型
class ModelCategory(str, Enum):
    GENERAL = "general"  # 通用模型 
    INFERENCE = "inference"  # 推理模型
    EMBEDDING = "embedding"  # 嵌入模型
    IMAGE = "image"  # 图像模型
    AUDIO = "audio"  # 音频模型
    VIDEO = "video"  # 视频模型

# Content Type Definitions
class TextContent(BaseModel):
    type: Literal["text"]
    text: str

class ImageContent(BaseModel):
    type: Literal["image_url"]
    image_url: Dict[str, str]

# Type Aliases
MessageContentItem = Union[TextContent, ImageContent]

# 消息定义
class Message(BaseModel):
    role: Literal["system", "user", "assistant", "function"]
    content: Union[str, List[MessageContentItem]]
    name: Optional[str] = None
    function_call: Optional[dict] = None

class ResponseFormat(BaseModel):
    type: Literal["text", "json_object"]

# 请求定义
class CompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    top_p: Optional[float] = 1.0
    frequency_penalty: Optional[float] = 0
    presence_penalty: Optional[float] = 0
    response_format: Optional[ResponseFormat] = None
    stream: Optional[bool] = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "gpt-4",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "https://example.com/image.jpg",
                                    "detail": "high"
                                }
                            },
                            {
                                "type": "text",
                                "text": "What's in this image?"
                            }
                        ]
                    }
                ],
                "temperature": 1.0
            }
        }
    )

# 响应相关定义
class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: Optional[str] = None

class CompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage
    system_fingerprint: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

# 模型配置相关
class ModelCapabilities(BaseModel):
    input_types: List[Literal["text", "image", "audio"]]
    output_types: List[Literal["text", "json_object", "json_schema", "image", "audio"]]
    default_output: str
    max_input_tokens: int
    max_output_tokens: int
    supports_streaming: bool = False
    supports_functions: bool = False

class ParameterType(str, Enum):
    FLOAT = "float"
    INT = "integer"
    STRING = "string"
    BOOL = "boolean"
    ENUM = "enum"

class ParameterDefinition(BaseModel):
    type: ParameterType
    description: str
    required: bool = False
    default: Optional[Union[float, int, str, bool]] = None
    min_value: Optional[Union[float, int]] = None
    max_value: Optional[Union[float, int]] = None
    allowed_values: Optional[List[str]] = None
    provider_param_name: Optional[str] = None

class ModelParameters(BaseModel):
    temperature: Optional[ParameterDefinition] = Field(default_factory=lambda: ParameterDefinition(
        type=ParameterType.FLOAT,
        description="Controls randomness in the response",
        default=1.0,
        min_value=0.0,
        max_value=2.0
    ))
    max_tokens: Optional[ParameterDefinition] = Field(default_factory=lambda: ParameterDefinition(
        type=ParameterType.INT,
        description="Maximum number of tokens to generate",
        default=None,
        min_value=1
    ))
    top_p: Optional[ParameterDefinition] = None
    top_k: Optional[ParameterDefinition] = None
    frequency_penalty: Optional[ParameterDefinition] = None
    presence_penalty: Optional[ParameterDefinition] = None
    stop: Optional[ParameterDefinition] = None
    stream: Optional[ParameterDefinition] = None
    
    # Custom parameters specific to each model
    custom_parameters: Dict[str, ParameterDefinition] = Field(default_factory=dict)

class ModelPricing(BaseModel):
    input_price: float  # Per 1M tokens
    output_price: float  # Per 1M tokens
    reasoning_price: Optional[float] = None  # Per 1M tokens
    image_input_price: Optional[float] = None  # Per image or per resolution
    audio_input_price: Optional[float] = None  # Per second or per minute

class EnhancedModelConfig(BaseModel):
    model_id: str
    display_name: str
    provider: str
    category: ModelCategory
    capabilities: ModelCapabilities
    pricing: ModelPricing
    parameters: ModelParameters
    description: Optional[str] = None
    status: str = "active"
    version: str = "1.0"
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "model_id": "gpt-4",
                "display_name": "GPT-4",
                "provider": "openai",
                "category": "general",
                "capabilities": {
                    "input_types": ["text"],
                    "output_types": ["text", "json_object"],
                    "default_output": "text",
                    "max_input_tokens": 128000,
                    "max_output_tokens": 4096,
                    "supports_streaming": True,
                    "supports_functions": True
                },
                "pricing": {
                    "input_price": 15.0,
                    "output_price": 50.0
                }
            }
        }
    )

# API密钥和请求验证相关
class ValidatedRequest(BaseModel):
    """用于存储验证和转换后的请求参数"""
    provider_model_id: str  # 供应商原始模型ID
    validated_params: Dict  # 验证并转换后的参数
    original_request: Dict  # 原始请求，用于日志和调试

class RateLimits(BaseModel):
    requests_per_minute: int
    requests_per_day: int
    requests_per_month: int
    concurrent_requests: int

class RetryConfig(BaseModel):
    auto_retry: bool = True
    max_retries: int = 3
    retry_delay: int = 1000  # milliseconds
    fallback_to_lower_tier: bool = True

class ApiKeyConfig(BaseModel):
    api_key: str
    tier: Literal["limit", "normal", "admin"]
    balance: float
    rate_limits: RateLimits
    retry_config: RetryConfig
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(arbitrary_types_allowed=True)

# 日志相关
class RetryAttempt(BaseModel):
    timestamp: datetime
    model_id: str
    reason: str
    status: str

class RequestLog(BaseModel):
    request_id: str
    api_key: str
    model_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tokens: Dict[str, int]
    cost: float
    status: str
    retry_attempts: Optional[List[RetryAttempt]] = []
    error: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

# 函数调用相关
class FunctionDefinition(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: dict