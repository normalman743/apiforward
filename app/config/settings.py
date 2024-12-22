# app/config/settings.py
from pydantic_settings import BaseSettings
from typing import Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件

class Settings(BaseSettings):
    # 服务基础配置
    SERVICE_NAME: str = "ai-proxy"
    ENV: str = "development"  # development/production
    DEBUG: bool = True
    
    # 数据库配置
    MONGODB_URL: str = "mongodb://localhost:27017"
    REDIS_URL: str = "redis://localhost:6379"
    
    # AI供应商API密钥
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str
    XAI_API_KEY: str 
    # 后续添加
    # GOOGLE_API_KEY: str
    # GROK_API_KEY: str
    # 2FLASH_API_KEY: str
    
    # 我们的API密钥配置
    API_KEY_PREFIX: str = "sk-"  # API密钥前缀
    API_KEY_LENGTH: int = 32     # API密钥长度
    ADMIN_API_KEY: str          # 管理员API密钥
    
    # 速率限制默认配置
    DEFAULT_RATE_LIMITS: Dict = {
        "limit": {
            "requests_per_minute": 10,
            "requests_per_day": 1000,
            "requests_per_month": 10000,
            "concurrent_requests": 2
        },
        "normal": {
            "requests_per_minute": 60,
            "requests_per_day": 10000,
            "requests_per_month": 100000,
            "concurrent_requests": 10
        },
        "admin": {
            "requests_per_minute": 100,
            "requests_per_day": 100000,
            "requests_per_month": 1000000,
            "concurrent_requests": 20
        }
    }
    
    # 重试配置
    DEFAULT_RETRY_CONFIG: Dict = {
        "max_retries": 3,
        "retry_delay": 1000,  # ms
        "fallback_to_lower_tier": True
    }
    
    class Config:
        env_file = ".env"