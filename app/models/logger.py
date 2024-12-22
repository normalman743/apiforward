# app/models/logger.py
import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

class Logger:
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._logger is None:
            self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """设置日志配置"""
        # 创建logger实例
        logger = logging.getLogger('ai_proxy')
        logger.setLevel(logging.INFO)

        # 创建日志格式
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 创建文件处理器
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 按日期创建日志文件
        current_date = datetime.now().strftime('%Y-%m-%d')
        file_handler = RotatingFileHandler(
            filename=log_dir / f"ai_proxy_{current_date}.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """获取日志实例"""
        if cls._instance is None:
            cls._instance = Logger()
        return cls._instance._logger

    def log_request(self, **kwargs):
        """记录请求日志"""
        self._logger.info(
            "Request: model=%(model)s, api_key=%(api_key)s, status=%(status)s",
            kwargs
        )

    def log_error(self, error: str, **kwargs):
        """记录错误日志"""
        self._logger.error(
            "Error: %s, context: %s",
            error,
            kwargs
        )

    def log_billing(self, **kwargs):
        """记录计费日志"""
        self._logger.info(
            "Billing: api_key=%(api_key)s, cost=%(cost)s, tokens=%(tokens)s",
            kwargs
        )

# 创建全局日志实例
logger = Logger.get_logger()