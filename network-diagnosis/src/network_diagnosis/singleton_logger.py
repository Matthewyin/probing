"""
单例模式日志管理器 - 阶段三长期改进
避免重复创建日志处理器，提供全局统一的日志管理
"""
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from .config import settings


class SingletonLoggerManager:
    """
    单例模式的日志管理器
    确保整个应用程序中只有一个日志管理器实例
    """
    
    _instance: Optional['SingletonLoggerManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'SingletonLoggerManager':
        """确保单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化日志管理器（只执行一次）"""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._loggers: Dict[str, logging.Logger] = {}
        self._file_handlers: Dict[str, logging.FileHandler] = {}
        self._current_config: Optional[str] = None
        self._current_log_file: Optional[str] = None
        
        # 初始化根日志器
        self._setup_root_logger()
        
        # 创建业务日志器
        self._setup_business_logger()
    
    def _setup_root_logger(self):
        """设置根日志器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        
        # 创建格式化器
        formatter = logging.Formatter(settings.LOG_FORMAT)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        root_logger.addHandler(console_handler)
        
        self._loggers['root'] = root_logger
    
    def _setup_business_logger(self):
        """设置业务日志器"""
        business_logger = logging.getLogger("business_log")
        business_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        business_logger.propagate = False  # 不传播到根记录器
        
        self._loggers['business'] = business_logger
    
    def setup_config_logging(self, config_name: str) -> str:
        """
        为特定配置设置文件日志记录

        Args:
            config_name: 配置文件名

        Returns:
            日志文件路径
        """
        with self._lock:
            # 如果已经为相同配置设置过，直接返回
            if self._current_config == config_name and self._current_log_file:
                return self._current_log_file

            # 清理旧的文件处理器
            self._cleanup_file_handlers()

            # 生成新的日志文件
            log_file_path = self._create_log_file(config_name)

            # 为根日志器添加文件处理器
            self._add_file_handler_to_logger('root', log_file_path)

            # 为业务日志器添加文件处理器
            self._add_file_handler_to_logger('business', log_file_path)

            # 更新当前配置
            self._current_config = config_name
            self._current_log_file = log_file_path

            return log_file_path
    
    def _create_log_file(self, config_name: str) -> str:
        """创建日志文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 计算日志目录路径
        network_diagnosis_dir = Path(__file__).parent.parent.parent
        log_dir = network_diagnosis_dir / "log" / config_name
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成日志文件路径
        log_filename = f"diagnosis_{timestamp}.log"
        log_filepath = log_dir / log_filename
        
        return str(log_filepath)
    
    def _add_file_handler_to_logger(self, logger_name: str, log_file_path: str):
        """为指定日志器添加文件处理器"""
        logger = self._loggers.get(logger_name)
        if not logger:
            return
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        
        # 创建格式化器
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # 添加到日志器
        logger.addHandler(file_handler)
        
        # 记录文件处理器
        handler_key = f"{logger_name}_{log_file_path}"
        self._file_handlers[handler_key] = file_handler
    
    def _cleanup_file_handlers(self):
        """清理所有文件处理器"""
        # 创建副本避免在迭代时修改字典
        handlers_copy = dict(self._file_handlers)

        for handler_key, handler in handlers_copy.items():
            try:
                handler.close()

                # 从对应的日志器中移除
                logger_name = handler_key.split('_')[0]
                logger = self._loggers.get(logger_name)
                if logger and handler in logger.handlers:
                    logger.removeHandler(handler)
            except Exception as e:
                print(f"Warning: Failed to cleanup file handler {handler_key}: {e}")

        # 清空记录
        self._file_handlers.clear()
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        with self._lock:
            if name not in self._loggers:
                self._loggers[name] = logging.getLogger(name)
            return self._loggers[name]
    
    def log_and_print(self, message: str, level: str = "INFO", log_only: bool = False):
        """
        统一的输出函数：既打印到控制台又记录到日志
        
        Args:
            message: 要输出的消息
            level: 日志级别
            log_only: 是否只记录到日志
        """
        # 控制台输出
        if not log_only:
            print(message)
        
        # 日志记录
        business_logger = self._loggers.get('business')
        if business_logger:
            getattr(business_logger, level.lower())(message)
    
    def get_status(self) -> Dict[str, Any]:
        """获取日志管理器状态"""
        return {
            'current_config': self._current_config,
            'current_log_file': self._current_log_file,
            'active_loggers': list(self._loggers.keys()),
            'active_file_handlers': len(self._file_handlers),
            'file_handlers': list(self._file_handlers.keys())
        }
    
    def cleanup(self):
        """清理所有资源"""
        with self._lock:
            self._cleanup_file_handlers()
            self._current_config = None
            self._current_log_file = None


# 全局单例实例
_logger_manager = SingletonLoggerManager()


def get_singleton_logger_manager() -> SingletonLoggerManager:
    """获取单例日志管理器"""
    return _logger_manager


def setup_config_logging(config_name: str) -> str:
    """
    兼容性函数：为特定配置设置日志记录
    使用单例日志管理器
    """
    return _logger_manager.setup_config_logging(config_name)


def log_and_print(message: str, level: str = "INFO", log_only: bool = False):
    """
    兼容性函数：统一的输出函数
    使用单例日志管理器
    """
    _logger_manager.log_and_print(message, level, log_only)


def get_logger(name: str) -> logging.Logger:
    """
    兼容性函数：获取指定名称的日志器
    使用单例日志管理器
    """
    return _logger_manager.get_logger(name)


# 初始化日志系统
logger = get_logger(__name__)
