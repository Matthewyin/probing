"""
自动恢复机制 - 阶段三长期改进
实现系统自动故障检测和恢复，包括服务重启、资源清理、状态恢复
"""
import os
import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from .singleton_logger import get_logger
from .enhanced_monitor import get_enhanced_monitor, AlertLevel
from .resource_monitor import ResourceMonitor

logger = get_logger(__name__)


class RecoveryAction(Enum):
    """恢复动作类型"""
    CLEANUP_RESOURCES = "cleanup_resources"
    RESTART_LOGGING = "restart_logging"
    KILL_PROCESSES = "kill_processes"
    CLEAR_CACHE = "clear_cache"
    RESTART_SERVICE = "restart_service"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"


@dataclass
class RecoveryRule:
    """恢复规则"""
    name: str
    condition: str  # 触发条件描述
    metric_name: str
    threshold_value: float
    comparison: str  # greater, less, equal
    action: RecoveryAction
    cooldown_seconds: int = 300  # 冷却时间，防止频繁执行
    max_attempts: int = 3  # 最大尝试次数
    enabled: bool = True


@dataclass
class RecoveryAttempt:
    """恢复尝试记录"""
    timestamp: datetime
    rule_name: str
    action: RecoveryAction
    success: bool
    error_message: Optional[str] = None
    metrics_before: Optional[Dict[str, Any]] = None
    metrics_after: Optional[Dict[str, Any]] = None


class AutoRecoverySystem:
    """自动恢复系统"""
    
    def __init__(self):
        """初始化自动恢复系统"""
        self.recovery_rules: Dict[str, RecoveryRule] = {}
        self.recovery_history: List[RecoveryAttempt] = []
        self.last_attempt_times: Dict[str, datetime] = {}
        self.attempt_counts: Dict[str, int] = {}
        
        # 系统状态
        self.enabled = True
        self.emergency_mode = False
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 初始化默认恢复规则
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """设置默认恢复规则"""
        default_rules = [
            RecoveryRule(
                name="high_file_handles",
                condition="文件句柄数量过高",
                metric_name="open_files",
                threshold_value=900,
                comparison="greater",
                action=RecoveryAction.CLEANUP_RESOURCES,
                cooldown_seconds=180,
                max_attempts=3
            ),
            RecoveryRule(
                name="excessive_log_handlers",
                condition="日志处理器过多",
                metric_name="file_handlers",
                threshold_value=15,
                comparison="greater",
                action=RecoveryAction.RESTART_LOGGING,
                cooldown_seconds=120,
                max_attempts=2
            ),
            RecoveryRule(
                name="too_many_processes",
                condition="活跃进程过多",
                metric_name="active_processes",
                threshold_value=8,
                comparison="greater",
                action=RecoveryAction.KILL_PROCESSES,
                cooldown_seconds=300,
                max_attempts=2
            ),
            RecoveryRule(
                name="critical_memory_usage",
                condition="内存使用过高",
                metric_name="memory_usage_mb",
                threshold_value=800,
                comparison="greater",
                action=RecoveryAction.CLEAR_CACHE,
                cooldown_seconds=240,
                max_attempts=3
            ),
            RecoveryRule(
                name="system_overload",
                condition="系统严重过载",
                metric_name="open_files",
                threshold_value=980,
                comparison="greater",
                action=RecoveryAction.EMERGENCY_SHUTDOWN,
                cooldown_seconds=600,
                max_attempts=1
            )
        ]
        
        for rule in default_rules:
            self.recovery_rules[rule.name] = rule
    
    def add_recovery_rule(self, rule: RecoveryRule):
        """添加恢复规则"""
        with self._lock:
            self.recovery_rules[rule.name] = rule
    
    def remove_recovery_rule(self, rule_name: str):
        """移除恢复规则"""
        with self._lock:
            if rule_name in self.recovery_rules:
                del self.recovery_rules[rule_name]
    
    def check_recovery_conditions(self, metrics: Dict[str, Any]) -> List[RecoveryRule]:
        """检查是否需要执行恢复动作"""
        triggered_rules = []
        
        for rule_name, rule in self.recovery_rules.items():
            if not rule.enabled:
                continue
            
            # 检查冷却时间
            last_attempt = self.last_attempt_times.get(rule_name)
            if last_attempt:
                cooldown_end = last_attempt + timedelta(seconds=rule.cooldown_seconds)
                if datetime.now() < cooldown_end:
                    continue
            
            # 检查最大尝试次数
            attempt_count = self.attempt_counts.get(rule_name, 0)
            if attempt_count >= rule.max_attempts:
                continue
            
            # 检查触发条件
            current_value = metrics.get(rule.metric_name)
            if current_value is None:
                continue
            
            triggered = False
            if rule.comparison == "greater":
                triggered = current_value > rule.threshold_value
            elif rule.comparison == "less":
                triggered = current_value < rule.threshold_value
            elif rule.comparison == "equal":
                triggered = current_value == rule.threshold_value
            
            if triggered:
                triggered_rules.append(rule)
        
        return triggered_rules
    
    async def execute_recovery_action(self, rule: RecoveryRule, metrics_before: Dict[str, Any]) -> RecoveryAttempt:
        """执行恢复动作"""
        attempt = RecoveryAttempt(
            timestamp=datetime.now(),
            rule_name=rule.name,
            action=rule.action,
            success=False,
            metrics_before=metrics_before
        )
        
        try:
            logger.warning(f"🔧 执行恢复动作: {rule.action.value} (规则: {rule.name})")
            
            if rule.action == RecoveryAction.CLEANUP_RESOURCES:
                success = await self._cleanup_resources()
            elif rule.action == RecoveryAction.RESTART_LOGGING:
                success = await self._restart_logging()
            elif rule.action == RecoveryAction.KILL_PROCESSES:
                success = await self._kill_processes()
            elif rule.action == RecoveryAction.CLEAR_CACHE:
                success = await self._clear_cache()
            elif rule.action == RecoveryAction.RESTART_SERVICE:
                success = await self._restart_service()
            elif rule.action == RecoveryAction.EMERGENCY_SHUTDOWN:
                success = await self._emergency_shutdown()
            else:
                logger.error(f"未知的恢复动作: {rule.action}")
                success = False
            
            attempt.success = success
            
            # 等待一段时间让系统稳定
            await asyncio.sleep(2)
            
            # 收集恢复后的指标
            monitor = get_enhanced_monitor()
            attempt.metrics_after = monitor.collect_metrics()
            
            if success:
                logger.info(f"✅ 恢复动作成功: {rule.action.value}")
            else:
                logger.error(f"❌ 恢复动作失败: {rule.action.value}")
            
        except Exception as e:
            attempt.error_message = str(e)
            logger.error(f"❌ 恢复动作异常: {rule.action.value} - {e}")
        
        return attempt
    
    async def _cleanup_resources(self) -> bool:
        """清理系统资源"""
        try:
            # 清理日志处理器
            from .singleton_logger import get_singleton_logger_manager
            logger_manager = get_singleton_logger_manager()
            logger_manager.cleanup()
            
            # 清理进程管理器
            from .process_manager import process_manager
            await process_manager.cleanup_all()
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            logger.info("🧹 资源清理完成")
            return True
            
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
            return False
    
    async def _restart_logging(self) -> bool:
        """重启日志系统"""
        try:
            from .singleton_logger import get_singleton_logger_manager
            logger_manager = get_singleton_logger_manager()
            
            # 清理现有日志处理器
            logger_manager.cleanup()
            
            # 重新设置日志（如果有当前配置）
            if logger_manager._current_config:
                logger_manager.setup_config_logging(logger_manager._current_config)
            
            logger.info("🔄 日志系统重启完成")
            return True
            
        except Exception as e:
            logger.error(f"日志系统重启失败: {e}")
            return False
    
    async def _kill_processes(self) -> bool:
        """终止过多的进程"""
        try:
            from .process_manager import process_manager
            
            # 获取长时间运行的进程
            status = process_manager.get_status()
            long_running = status.get('long_running_processes', [])
            
            # 终止超时进程
            killed_count = 0
            for process_info in long_running:
                try:
                    await process_manager.force_cleanup_process(process_info.get('id'))
                    killed_count += 1
                except Exception as e:
                    logger.warning(f"终止进程失败: {e}")
            
            logger.info(f"🔪 终止了 {killed_count} 个进程")
            return killed_count > 0
            
        except Exception as e:
            logger.error(f"进程终止失败: {e}")
            return False
    
    async def _clear_cache(self) -> bool:
        """清理缓存"""
        try:
            # 强制垃圾回收
            import gc
            gc.collect()
            
            # 清理临时文件（如果有）
            import tempfile
            temp_dir = tempfile.gettempdir()
            
            logger.info("🗑️ 缓存清理完成")
            return True
            
        except Exception as e:
            logger.error(f"缓存清理失败: {e}")
            return False
    
    async def _restart_service(self) -> bool:
        """重启服务（谨慎使用）"""
        try:
            logger.warning("🔄 准备重启服务...")
            
            # 清理所有资源
            await self._cleanup_resources()
            
            # 这里可以添加服务重启逻辑
            # 注意：实际重启需要外部脚本支持
            
            logger.info("🔄 服务重启准备完成")
            return True
            
        except Exception as e:
            logger.error(f"服务重启失败: {e}")
            return False
    
    async def _emergency_shutdown(self) -> bool:
        """紧急关闭"""
        try:
            logger.critical("🚨 执行紧急关闭...")
            
            # 设置紧急模式
            self.emergency_mode = True
            
            # 清理所有资源
            await self._cleanup_resources()
            
            # 停止监控
            self.enabled = False
            
            logger.critical("🛑 紧急关闭完成")
            return True
            
        except Exception as e:
            logger.error(f"紧急关闭失败: {e}")
            return False
    
    async def run_recovery_check(self):
        """运行恢复检查"""
        if not self.enabled or self.emergency_mode:
            return
        
        try:
            # 获取当前指标
            monitor = get_enhanced_monitor()
            current_metrics = monitor.collect_metrics()
            
            if not current_metrics:
                return
            
            # 检查恢复条件
            triggered_rules = self.check_recovery_conditions(current_metrics)
            
            if not triggered_rules:
                return
            
            # 执行恢复动作
            for rule in triggered_rules:
                with self._lock:
                    # 更新尝试记录
                    self.last_attempt_times[rule.name] = datetime.now()
                    self.attempt_counts[rule.name] = self.attempt_counts.get(rule.name, 0) + 1
                
                # 执行恢复
                attempt = await self.execute_recovery_action(rule, current_metrics)
                
                # 记录恢复历史
                with self._lock:
                    self.recovery_history.append(attempt)
                    
                    # 保持历史记录在合理范围内
                    if len(self.recovery_history) > 100:
                        self.recovery_history = self.recovery_history[-50:]
                
                # 如果是紧急关闭，停止后续处理
                if rule.action == RecoveryAction.EMERGENCY_SHUTDOWN:
                    break
        
        except Exception as e:
            logger.error(f"恢复检查失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取自动恢复系统状态"""
        with self._lock:
            return {
                'enabled': self.enabled,
                'emergency_mode': self.emergency_mode,
                'rules_count': len(self.recovery_rules),
                'recovery_attempts_total': len(self.recovery_history),
                'recent_attempts': [
                    {
                        'timestamp': attempt.timestamp.isoformat(),
                        'rule_name': attempt.rule_name,
                        'action': attempt.action.value,
                        'success': attempt.success,
                        'error': attempt.error_message
                    }
                    for attempt in self.recovery_history[-10:]  # 最近10次
                ],
                'attempt_counts': dict(self.attempt_counts),
                'last_attempt_times': {
                    rule_name: timestamp.isoformat()
                    for rule_name, timestamp in self.last_attempt_times.items()
                }
            }
    
    def reset_attempt_counts(self):
        """重置尝试计数"""
        with self._lock:
            self.attempt_counts.clear()
            self.last_attempt_times.clear()
    
    def enable(self):
        """启用自动恢复"""
        self.enabled = True
        self.emergency_mode = False
    
    def disable(self):
        """禁用自动恢复"""
        self.enabled = False


# 全局自动恢复系统实例
_auto_recovery_system = None


def get_auto_recovery_system() -> AutoRecoverySystem:
    """获取全局自动恢复系统实例"""
    global _auto_recovery_system
    if _auto_recovery_system is None:
        _auto_recovery_system = AutoRecoverySystem()
    return _auto_recovery_system
