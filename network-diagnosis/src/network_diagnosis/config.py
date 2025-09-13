"""
配置管理模块 - 遵循十二要素应用原则
使用Pydantic Settings进行类型安全的配置管理
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """应用配置类 - 从环境变量加载配置"""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )
    
    # 应用基础配置
    APP_NAME: str = "Network Diagnosis Tool"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # 网络诊断配置
    CONNECT_TIMEOUT: int = 10  # TCP连接超时时间（秒）
    READ_TIMEOUT: int = 30     # 读取超时时间（秒）
    MAX_REDIRECTS: int = 5     # 最大重定向次数

    # TCP服务配置
    USE_ASYNC_TCP_SERVICE: bool = True      # 使用新的AsyncTCPService
    TCP_FALLBACK_ENABLED: bool = True       # 启用TCP fallback机制
    TCP_DETAILED_ERROR_ANALYSIS: bool = True  # 详细错误分析

    # 智能重试配置
    ENABLE_SMART_RETRY: bool = True         # 启用智能重试
    TCP_MAX_RETRIES: int = 3                # TCP最大重试次数
    TCP_RETRY_BASE_DELAY: float = 1.0       # 基础重试延迟（秒）
    TCP_RETRY_MAX_DELAY: float = 30.0       # 最大重试延迟（秒）
    TCP_RETRY_EXPONENTIAL_BACKOFF: bool = True  # 指数退避
    TCP_RETRY_JITTER: bool = True           # 添加抖动

    # aiohttp客户端配置
    USE_AIOHTTP_CLIENT: bool = True  # 是否使用aiohttp客户端（HTTP/TLS）
    AIOHTTP_FALLBACK_ENABLED: bool = True  # 是否启用fallback到原实现

    # aiohttp连接器配置
    AIOHTTP_CONNECTOR_LIMIT: int = 100  # 连接池总大小
    AIOHTTP_CONNECTOR_LIMIT_PER_HOST: int = 30  # 每主机最大连接数
    AIOHTTP_CONNECTOR_TTL_DNS_CACHE: int = 300  # DNS缓存TTL（秒）
    AIOHTTP_CONNECTOR_USE_DNS_CACHE: bool = True  # 启用DNS缓存

    # 详细信息配置
    ENABLE_DETAILED_TIMING: bool = True  # 启用详细时间分解
    ENABLE_CONNECTION_REUSE_INFO: bool = True  # 启用连接复用信息
    
    # 系统配置
    SUDO_PASSWORD: Optional[str] = None  # sudo密码，用于mtr命令
    OUTPUT_DIR: str = "./output"  # 输出目录（将在__init__中重新计算）
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 重新计算输出目录路径
        self.OUTPUT_DIR = str(Path(__file__).parent.parent.parent / "output")
        self._validate_config()
        self._ensure_output_dir()
    
    def _validate_config(self):
        """验证配置的有效性"""
        if self.CONNECT_TIMEOUT <= 0:
            raise ValueError("CONNECT_TIMEOUT must be positive")
        if self.READ_TIMEOUT <= 0:
            raise ValueError("READ_TIMEOUT must be positive")
        if self.MAX_REDIRECTS < 0:
            raise ValueError("MAX_REDIRECTS must be non-negative")
    
    def _ensure_output_dir(self):
        """确保输出目录存在"""
        if not os.path.exists(self.OUTPUT_DIR):
            os.makedirs(self.OUTPUT_DIR, exist_ok=True)


# 全局配置实例
settings = AppSettings()
