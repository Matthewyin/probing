"""
日志配置模块 - 遵循十二要素应用原则
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from .config import settings


def _cleanup_file_handlers(logger_obj: logging.Logger):
    """
    清理指定logger的所有文件处理器，防止处理器泄漏

    Args:
        logger_obj: 要清理的logger对象
    """
    # 使用切片复制列表，避免在迭代时修改列表
    for handler in logger_obj.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            try:
                handler.close()  # 关闭文件句柄
                logger_obj.removeHandler(handler)
            except Exception as e:
                # 记录清理失败，但不影响程序继续运行
                print(f"Warning: Failed to cleanup file handler: {e}")


def setup_logging():
    """设置应用日志配置"""
    # 创建根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # 清除默认处理器
    root_logger.handlers.clear()
    
    # 创建控制台处理器（输出到stdout）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # 创建格式化器
    formatter = logging.Formatter(settings.LOG_FORMAT)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到根日志器
    root_logger.addHandler(console_handler)
    
    return root_logger


def setup_config_logging(config_name: str) -> str:
    """
    为特定配置文件设置日志记录

    Args:
        config_name: 配置文件名（不含扩展名）

    Returns:
        日志文件路径
    """
    # 生成时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 创建日志目录 - 从当前文件位置计算
    # __file__ 是 .../network-diagnosis/src/network_diagnosis/logger.py
    # parent.parent 是 .../network-diagnosis/src
    # parent.parent.parent 是 .../network-diagnosis
    # 然后进入 log 目录
    network_diagnosis_dir = Path(__file__).parent.parent.parent
    log_dir = network_diagnosis_dir / "log" / config_name
    log_dir.mkdir(parents=True, exist_ok=True)

    # 生成日志文件名
    log_filename = f"diagnosis_{timestamp}.log"
    log_filepath = log_dir / log_filename

    # 获取根日志器
    root_logger = logging.getLogger()

    # 🔧 修复：清理已存在的文件处理器，防止泄漏
    _cleanup_file_handlers(root_logger)

    # 创建文件处理器
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # 创建详细的文件日志格式
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # 添加文件处理器到根日志器
    root_logger.addHandler(file_handler)

    # 为business_log创建专门的文件处理器
    business_logger = logging.getLogger("business_log")
    business_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    business_logger.propagate = False  # 不传播到根记录器，避免重复输出

    # 🔧 修复：清理business_logger的文件处理器
    _cleanup_file_handlers(business_logger)

    # 创建business_log专用的文件处理器
    business_file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    business_file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    business_file_handler.setFormatter(file_formatter)
    business_logger.addHandler(business_file_handler)

    return str(log_filepath)


def log_and_print(message: str, level: str = "INFO", log_only: bool = False):
    """
    统一的输出函数：既打印到控制台又记录到日志

    Args:
        message: 要输出的消息
        level: 日志级别 (INFO, WARNING, ERROR, DEBUG)
        log_only: 如果为True，只记录到日志文件，不打印到控制台
    """
    # 控制台输出（保持原有美观格式）
    if not log_only:
        print(message)

    # 日志记录（带时间戳和模块信息）
    # 使用专门的business_log记录器，它只输出到文件
    business_logger = logging.getLogger("business_log")

    # 确保business_log记录器不传播到根记录器（避免重复输出到控制台）
    business_logger.propagate = False

    # 如果还没有文件处理器，添加一个（这种情况不应该发生，但作为保险）
    if not business_logger.handlers:
        # 这里应该已经通过setup_config_logging设置了文件处理器
        pass

    getattr(business_logger, level.lower())(message)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器"""
    return logging.getLogger(name)


# 初始化日志系统
setup_logging()
logger = get_logger(__name__)
