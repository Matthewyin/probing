"""
调度器运行器 - 封装APScheduler功能，支持定时执行批量网络诊断
"""
import asyncio
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from .config_loader import ConfigLoader, SchedulerConfig
from .batch_runner import BatchDiagnosisRunner
from .logger import get_logger

logger = get_logger(__name__)


class SchedulerRunner:
    """调度器运行器"""
    
    def __init__(self, config_file: str):
        """
        初始化调度器运行器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config_loader = ConfigLoader(config_file)
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        self.job_id = "batch_diagnosis_job"
        
    async def initialize(self):
        """初始化调度器"""
        try:
            # 加载配置
            config = self.config_loader.load_config()
            scheduler_config = self.config_loader.get_scheduler_config()
            
            if not scheduler_config or not scheduler_config.enabled:
                raise ValueError("Scheduler is not enabled in configuration")
            
            # 创建调度器
            self.scheduler = AsyncIOScheduler(timezone=scheduler_config.timezone)
            
            # 添加事件监听器
            self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
            self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
            
            # 添加诊断任务
            await self._add_diagnosis_job(scheduler_config)
            
            logger.info(f"Scheduler initialized with timezone: {scheduler_config.timezone}")
            
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {str(e)}")
            raise
    
    async def _add_diagnosis_job(self, scheduler_config: SchedulerConfig):
        """添加诊断任务到调度器"""
        try:
            # 创建触发器
            trigger = self._create_trigger(scheduler_config)
            
            # 添加任务
            self.scheduler.add_job(
                func=self._execute_batch_diagnosis,
                trigger=trigger,
                id=self.job_id,
                name="Batch Network Diagnosis",
                max_instances=scheduler_config.max_instances,
                coalesce=scheduler_config.coalesce,
                misfire_grace_time=scheduler_config.misfire_grace_time,
                replace_existing=True
            )
            
            logger.info(f"Added diagnosis job with trigger: {scheduler_config.trigger_type}")
            
        except Exception as e:
            logger.error(f"Failed to add diagnosis job: {str(e)}")
            raise
    
    def _create_trigger(self, scheduler_config: SchedulerConfig):
        """创建触发器"""
        if scheduler_config.trigger_type == "cron":
            # 解析cron表达式
            cron_parts = scheduler_config.cron.split()
            if len(cron_parts) != 5:
                raise ValueError(f"Invalid cron expression: {scheduler_config.cron}")
            
            minute, hour, day, month, day_of_week = cron_parts
            return CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=scheduler_config.timezone
            )
            
        elif scheduler_config.trigger_type == "interval":
            kwargs = {}
            if scheduler_config.interval_minutes:
                kwargs['minutes'] = scheduler_config.interval_minutes
            elif scheduler_config.interval_hours:
                kwargs['hours'] = scheduler_config.interval_hours
            
            return IntervalTrigger(**kwargs, timezone=scheduler_config.timezone)
        
        else:
            raise ValueError(f"Unsupported trigger type: {scheduler_config.trigger_type}")
    
    async def _execute_batch_diagnosis(self):
        """执行批量诊断任务"""
        start_time = datetime.now()
        logger.info(f"Starting scheduled batch diagnosis at {start_time}")
        
        try:
            # 创建批量诊断运行器
            runner = BatchDiagnosisRunner(self.config_file)
            
            # 执行批量诊断
            result = await runner.run_batch_diagnosis()
            
            # 记录执行结果
            summary = result.get_summary()
            exec_summary = summary["execution_summary"]
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(
                f"Scheduled batch diagnosis completed in {duration:.2f}s: "
                f"{exec_summary['successful']}/{exec_summary['total_targets']} successful"
            )
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.error(f"Scheduled batch diagnosis failed after {duration:.2f}s: {str(e)}")
            raise
    
    def _job_executed(self, event):
        """任务执行完成事件处理"""
        logger.info(f"Job {event.job_id} executed successfully")
    
    def _job_error(self, event):
        """任务执行错误事件处理"""
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    
    async def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        if not self.scheduler:
            await self.initialize()
        
        try:
            self.scheduler.start()
            self.is_running = True
            logger.info("Scheduler started successfully")
            
            # 显示下次执行时间
            next_run = self.scheduler.get_job(self.job_id).next_run_time
            if next_run:
                logger.info(f"Next diagnosis scheduled at: {next_run}")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}")
            raise
    
    async def stop(self):
        """停止调度器"""
        if not self.is_running:
            return
        
        try:
            if self.scheduler:
                self.scheduler.shutdown(wait=True)
                self.scheduler = None
            
            self.is_running = False
            logger.info("Scheduler stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
    
    async def reload_config(self):
        """重新加载配置"""
        logger.info("Reloading scheduler configuration...")
        
        try:
            # 重新加载配置
            config = self.config_loader.load_config()
            scheduler_config = self.config_loader.get_scheduler_config()
            
            if not scheduler_config or not scheduler_config.enabled:
                logger.info("Scheduler disabled in new configuration, stopping...")
                await self.stop()
                return
            
            # 如果调度器正在运行，重新配置任务
            if self.is_running and self.scheduler:
                # 移除现有任务
                if self.scheduler.get_job(self.job_id):
                    self.scheduler.remove_job(self.job_id)
                
                # 添加新任务
                await self._add_diagnosis_job(scheduler_config)
                
                # 显示下次执行时间
                next_run = self.scheduler.get_job(self.job_id).next_run_time
                if next_run:
                    logger.info(f"Configuration reloaded. Next diagnosis scheduled at: {next_run}")
            
            logger.info("Scheduler configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload scheduler configuration: {str(e)}")
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        status = {
            "is_running": self.is_running,
            "config_file": self.config_file,
            "next_run_time": None,
            "job_count": 0
        }
        
        if self.scheduler and self.is_running:
            job = self.scheduler.get_job(self.job_id)
            if job:
                status["next_run_time"] = job.next_run_time
                status["job_count"] = len(self.scheduler.get_jobs())
        
        return status
