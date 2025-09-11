"""
配置文件监控器 - 监控配置文件变化并支持热重载
"""
import asyncio
import time
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from .logger import get_logger

logger = get_logger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变化处理器"""
    
    def __init__(self, config_file: Path, callback: Callable, debounce_seconds: float = 0.5):
        """
        初始化配置文件处理器
        
        Args:
            config_file: 要监控的配置文件路径
            callback: 文件变化时的回调函数
            debounce_seconds: 防抖延迟时间（秒）
        """
        self.config_file = config_file.resolve()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.last_modified = 0
        
    def on_modified(self, event):
        """文件修改事件处理"""
        if event.is_directory:
            return
            
        # 检查是否是我们要监控的文件
        if hasattr(event, 'src_path'):
            event_path = Path(event.src_path).resolve()
            if event_path != self.config_file:
                return
        
        # 防抖处理
        current_time = time.time()
        if current_time - self.last_modified < self.debounce_seconds:
            return
            
        self.last_modified = current_time
        
        logger.info(f"Configuration file changed: {self.config_file}")
        
        # 延迟执行回调，确保文件写入完成
        asyncio.create_task(self._delayed_callback())
    
    async def _delayed_callback(self):
        """延迟执行回调函数"""
        await asyncio.sleep(self.debounce_seconds)
        try:
            await self.callback()
        except Exception as e:
            logger.error(f"Error in config reload callback: {str(e)}")


class ConfigWatcher:
    """配置文件监控器"""
    
    def __init__(self, config_file: str, reload_callback: Callable):
        """
        初始化配置监控器
        
        Args:
            config_file: 配置文件路径
            reload_callback: 配置重载回调函数（异步）
        """
        self.config_file = Path(config_file)
        self.reload_callback = reload_callback
        self.observer: Optional[Observer] = None
        self.handler: Optional[ConfigFileHandler] = None
        self.is_watching = False
        
    def start_watching(self):
        """开始监控配置文件"""
        if self.is_watching:
            logger.warning("Config watcher is already running")
            return
            
        if not self.config_file.exists():
            logger.error(f"Configuration file does not exist: {self.config_file}")
            return
            
        try:
            # 创建文件处理器
            self.handler = ConfigFileHandler(
                self.config_file, 
                self.reload_callback,
                debounce_seconds=0.5
            )
            
            # 创建观察者
            self.observer = Observer()
            
            # 监控配置文件所在的目录
            watch_dir = self.config_file.parent
            self.observer.schedule(self.handler, str(watch_dir), recursive=False)
            
            # 启动观察者
            self.observer.start()
            self.is_watching = True
            
            logger.info(f"Started watching configuration file: {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to start config watcher: {str(e)}")
            self.stop_watching()
    
    def stop_watching(self):
        """停止监控配置文件"""
        if not self.is_watching:
            return
            
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5.0)
                self.observer = None
                
            self.handler = None
            self.is_watching = False
            
            logger.info("Stopped watching configuration file")
            
        except Exception as e:
            logger.error(f"Error stopping config watcher: {str(e)}")
    
    def is_running(self) -> bool:
        """检查监控器是否正在运行"""
        return self.is_watching and self.observer is not None and self.observer.is_alive()


async def test_config_watcher():
    """测试配置文件监控器"""
    async def reload_callback():
        print("Configuration file changed!")
    
    watcher = ConfigWatcher("test_config.yaml", reload_callback)
    watcher.start_watching()
    
    try:
        # 等待文件变化
        await asyncio.sleep(30)
    finally:
        watcher.stop_watching()


if __name__ == "__main__":
    asyncio.run(test_config_watcher())
