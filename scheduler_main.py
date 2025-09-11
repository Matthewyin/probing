#!/usr/bin/env python3
"""
定时任务主程序 - 支持定时执行批量网络诊断和配置热重载
"""
import asyncio
import argparse
import signal
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "network-diagnosis" / "src"))

from network_diagnosis.scheduler_runner import SchedulerRunner
from network_diagnosis.config_watcher import ConfigWatcher
from network_diagnosis.config_loader import ConfigLoader
from network_diagnosis.logger import get_logger, log_and_print

logger = get_logger(__name__)


class SchedulerApp:
    """定时任务应用程序"""
    
    def __init__(self, config_file: str):
        """
        初始化定时任务应用
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.scheduler_runner: SchedulerRunner = None
        self.config_watcher: ConfigWatcher = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """初始化应用组件"""
        try:
            # 验证配置文件
            config_path = Path(self.config_file)
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
            
            # 检查配置文件中是否启用了调度器
            config_loader = ConfigLoader(self.config_file)
            config = config_loader.load_config()
            
            if not config_loader.has_scheduler_config():
                raise ValueError(
                    "Scheduler is not enabled in configuration. "
                    "Please add 'scheduler' section with 'enabled: true' to your config file."
                )
            
            # 初始化调度器运行器
            self.scheduler_runner = SchedulerRunner(self.config_file)
            await self.scheduler_runner.initialize()
            
            # 初始化配置文件监控器
            self.config_watcher = ConfigWatcher(
                self.config_file, 
                self._on_config_changed
            )
            
            logger.info(f"Scheduler app initialized with config: {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to initialize scheduler app: {str(e)}")
            raise
    
    async def _on_config_changed(self):
        """配置文件变化回调"""
        logger.info("Configuration file changed, reloading...")
        
        try:
            # 验证新配置
            config_loader = ConfigLoader(self.config_file)
            config = config_loader.load_config()
            
            # 重新加载调度器配置
            if self.scheduler_runner:
                await self.scheduler_runner.reload_config()
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {str(e)}")
    
    async def start(self):
        """启动应用"""
        try:
            # 启动调度器
            await self.scheduler_runner.start()
            
            # 启动配置文件监控
            self.config_watcher.start_watching()
            
            log_and_print("🚀 Scheduler started successfully")
            log_and_print(f"📁 Configuration file: {self.config_file}")
            log_and_print("📝 Monitoring configuration file for changes...")
            
            # 显示调度器状态
            status = self.scheduler_runner.get_status()
            if status["next_run_time"]:
                log_and_print(f"⏰ Next diagnosis scheduled at: {status['next_run_time']}")
            
            log_and_print("Press Ctrl+C to stop the scheduler")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler app: {str(e)}")
            raise
    
    async def stop(self):
        """停止应用"""
        log_and_print("\n🛑 Stopping scheduler...")
        
        try:
            # 停止配置文件监控
            if self.config_watcher:
                self.config_watcher.stop_watching()
            
            # 停止调度器
            if self.scheduler_runner:
                await self.scheduler_runner.stop()
            
            log_and_print("✅ Scheduler stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler app: {str(e)}")
    
    async def run(self):
        """运行应用主循环"""
        try:
            await self.start()
            
            # 等待关闭信号
            await self.shutdown_event.wait()
            
        finally:
            await self.stop()
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()


async def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description="定时任务网络诊断工具 - 支持定时执行和配置热重载",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
配置文件格式 (YAML):
  scheduler:
    enabled: true
    timezone: "Asia/Shanghai"
    trigger_type: "cron"  # 或 "interval"
    cron: "0 */2 * * *"   # 每2小时执行一次
    # interval_hours: 2   # 或使用间隔触发
    max_instances: 1
    coalesce: true
    misfire_grace_time: 300

  targets:
    - domain: "google.com"
      port: 443
      # ...

示例用法:
  python scheduler_main.py -c network-diagnosis/input/config.yaml
  python scheduler_main.py -c config.yaml --daemon
        """
    )
    
    parser.add_argument(
        "-c", "--config",
        default="network-diagnosis/input/targets.yaml",
        help="配置文件路径 (默认: network-diagnosis/input/targets.yaml)"
    )
    
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="后台运行模式（当前版本暂不支持真正的daemon模式）"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="显示调度器状态并退出"
    )
    
    args = parser.parse_args()
    
    try:
        # 解析配置文件路径
        config_file = args.config
        
        # 如果只是查看状态
        if args.status:
            try:
                config_loader = ConfigLoader(config_file)
                config = config_loader.load_config()
                scheduler_config = config_loader.get_scheduler_config()
                
                log_and_print(f"Configuration file: {config_file}")
                if scheduler_config and scheduler_config.enabled:
                    log_and_print(f"Scheduler: Enabled")
                    log_and_print(f"Trigger type: {scheduler_config.trigger_type}")
                    if scheduler_config.trigger_type == "cron":
                        log_and_print(f"Cron expression: {scheduler_config.cron}")
                    else:
                        if scheduler_config.interval_minutes:
                            log_and_print(f"Interval: {scheduler_config.interval_minutes} minutes")
                        elif scheduler_config.interval_hours:
                            log_and_print(f"Interval: {scheduler_config.interval_hours} hours")
                    log_and_print(f"Timezone: {scheduler_config.timezone}")
                else:
                    log_and_print("Scheduler: Disabled")
                
                return 0
                
            except Exception as e:
                log_and_print(f"Error reading configuration: {str(e)}", "ERROR")
                return 1
        
        # 创建并运行调度器应用
        app = SchedulerApp(config_file)
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, app.signal_handler)
        signal.signal(signal.SIGTERM, app.signal_handler)
        
        # 初始化应用
        await app.initialize()
        
        # 运行应用
        await app.run()
        
        return 0
        
    except KeyboardInterrupt:
        log_and_print("\nReceived interrupt signal")
        return 0
    except Exception as e:
        log_and_print(f"Error: {str(e)}", "ERROR")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
