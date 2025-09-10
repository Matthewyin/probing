"""
配置管理模块 - 遵循十二要素应用原则
使用Pydantic Settings进行类型安全的配置管理
"""
import os
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
    
    # 系统配置
    SUDO_PASSWORD: Optional[str] = None  # sudo密码，用于mtr命令
    OUTPUT_DIR: str = "./output"         # 输出目录
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
