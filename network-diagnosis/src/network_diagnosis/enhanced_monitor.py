"""
增强监控和告警系统 - 阶段三长期改进
提供完善的监控、告警阈值、通知机制和持久化监控数据
"""
import os
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from .resource_monitor import ResourceMonitor
from .singleton_logger import get_logger

logger = get_logger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertThreshold:
    """告警阈值配置"""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison: str = "greater"  # greater, less, equal
    enabled: bool = True


@dataclass
class AlertEvent:
    """告警事件"""
    timestamp: datetime
    level: AlertLevel
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class NotificationHandler:
    """通知处理器基类"""
    
    def send_notification(self, alert: AlertEvent) -> bool:
        """发送通知"""
        raise NotImplementedError


class LogNotificationHandler(NotificationHandler):
    """日志通知处理器"""
    
    def send_notification(self, alert: AlertEvent) -> bool:
        """通过日志发送通知"""
        try:
            level_map = {
                AlertLevel.INFO: logger.info,
                AlertLevel.WARNING: logger.warning,
                AlertLevel.CRITICAL: logger.error
            }
            
            log_func = level_map.get(alert.level, logger.info)
            log_func(f"🚨 Alert: {alert.message} (Current: {alert.current_value}, Threshold: {alert.threshold_value})")
            return True
        except Exception as e:
            logger.error(f"Failed to send log notification: {e}")
            return False


class FileNotificationHandler(NotificationHandler):
    """文件通知处理器"""
    
    def __init__(self, alert_file_path: str):
        self.alert_file_path = Path(alert_file_path)
        self.alert_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def send_notification(self, alert: AlertEvent) -> bool:
        """写入告警文件"""
        try:
            alert_data = {
                'timestamp': alert.timestamp.isoformat(),
                'level': alert.level.value,
                'metric_name': alert.metric_name,
                'current_value': alert.current_value,
                'threshold_value': alert.threshold_value,
                'message': alert.message,
                'resolved': alert.resolved
            }
            
            # 追加到文件
            with open(self.alert_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(alert_data) + '\n')
            
            return True
        except Exception as e:
            logger.error(f"Failed to write alert to file: {e}")
            return False


class EnhancedMonitor:
    """增强监控系统"""
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化增强监控系统
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent.parent / "monitoring_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 监控数据存储
        self.metrics_file = self.data_dir / "metrics.jsonl"
        self.alerts_file = self.data_dir / "alerts.jsonl"
        
        # 告警配置
        self.thresholds: Dict[str, AlertThreshold] = {}
        self.notification_handlers: List[NotificationHandler] = []
        self.active_alerts: Dict[str, AlertEvent] = {}
        
        # 监控状态
        self.monitoring_enabled = True
        self.last_check_time = datetime.now()
        self.check_interval = 60  # 秒
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 初始化默认配置
        self._setup_default_thresholds()
        self._setup_default_notifications()
    
    def _setup_default_thresholds(self):
        """设置默认告警阈值"""
        default_thresholds = [
            AlertThreshold("open_files", 800, 950, "greater"),
            AlertThreshold("file_handlers", 10, 20, "greater"),
            AlertThreshold("active_processes", 5, 10, "greater"),
            AlertThreshold("memory_usage_mb", 500, 1000, "greater"),
            AlertThreshold("cpu_usage_percent", 80, 95, "greater"),
        ]
        
        for threshold in default_thresholds:
            self.thresholds[threshold.metric_name] = threshold
    
    def _setup_default_notifications(self):
        """设置默认通知处理器"""
        # 日志通知
        self.notification_handlers.append(LogNotificationHandler())
        
        # 文件通知
        self.notification_handlers.append(
            FileNotificationHandler(str(self.alerts_file))
        )
    
    def add_threshold(self, threshold: AlertThreshold):
        """添加告警阈值"""
        with self._lock:
            self.thresholds[threshold.metric_name] = threshold
    
    def add_notification_handler(self, handler: NotificationHandler):
        """添加通知处理器"""
        with self._lock:
            self.notification_handlers.append(handler)
    
    def collect_metrics(self) -> Dict[str, Any]:
        """收集系统指标"""
        try:
            # 基础资源监控
            resource_status = ResourceMonitor.check_resource_limits()
            handler_status = ResourceMonitor.monitor_log_handlers()
            process_status = ResourceMonitor.monitor_process_status()
            
            # 扩展指标
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'open_files': resource_status.get('open_files', 0),
                'file_handlers': handler_status.get('total_file_handlers', 0),
                'active_processes': process_status.get('active_processes', 0),
                'memory_usage_mb': 0,
                'cpu_usage_percent': 0,
            }
            
            # 如果psutil可用，收集更多指标
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process(os.getpid())
                    memory_info = process.memory_info()
                    metrics['memory_usage_mb'] = memory_info.rss / 1024 / 1024
                    metrics['cpu_usage_percent'] = process.cpu_percent()
                except Exception as e:
                    logger.debug(f"Failed to collect psutil metrics: {e}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            return {}
    
    def check_thresholds(self, metrics: Dict[str, Any]) -> List[AlertEvent]:
        """检查告警阈值"""
        alerts = []
        
        for metric_name, threshold in self.thresholds.items():
            if not threshold.enabled:
                continue
            
            current_value = metrics.get(metric_name)
            if current_value is None:
                continue
            
            # 检查是否触发告警
            alert_level = None
            threshold_value = None
            
            if threshold.comparison == "greater":
                if current_value >= threshold.critical_threshold:
                    alert_level = AlertLevel.CRITICAL
                    threshold_value = threshold.critical_threshold
                elif current_value >= threshold.warning_threshold:
                    alert_level = AlertLevel.WARNING
                    threshold_value = threshold.warning_threshold
            elif threshold.comparison == "less":
                if current_value <= threshold.critical_threshold:
                    alert_level = AlertLevel.CRITICAL
                    threshold_value = threshold.critical_threshold
                elif current_value <= threshold.warning_threshold:
                    alert_level = AlertLevel.WARNING
                    threshold_value = threshold.warning_threshold
            
            if alert_level:
                # 创建告警事件
                alert = AlertEvent(
                    timestamp=datetime.now(),
                    level=alert_level,
                    metric_name=metric_name,
                    current_value=current_value,
                    threshold_value=threshold_value,
                    message=f"{metric_name} {threshold.comparison} threshold: {current_value} vs {threshold_value}"
                )
                alerts.append(alert)
        
        return alerts
    
    def process_alerts(self, alerts: List[AlertEvent]):
        """处理告警事件"""
        with self._lock:
            for alert in alerts:
                alert_key = f"{alert.metric_name}_{alert.level.value}"
                
                # 检查是否是新告警或级别升级
                existing_alert = self.active_alerts.get(alert_key)
                if not existing_alert or existing_alert.level != alert.level:
                    # 发送通知
                    for handler in self.notification_handlers:
                        try:
                            handler.send_notification(alert)
                        except Exception as e:
                            logger.error(f"Notification handler failed: {e}")
                    
                    # 记录活跃告警
                    self.active_alerts[alert_key] = alert
    
    def resolve_alerts(self, metrics: Dict[str, Any]):
        """解决已恢复的告警"""
        with self._lock:
            resolved_keys = []
            
            for alert_key, alert in self.active_alerts.items():
                threshold = self.thresholds.get(alert.metric_name)
                if not threshold:
                    continue
                
                current_value = metrics.get(alert.metric_name)
                if current_value is None:
                    continue
                
                # 检查是否已恢复
                recovered = False
                if threshold.comparison == "greater":
                    if current_value < threshold.warning_threshold:
                        recovered = True
                elif threshold.comparison == "less":
                    if current_value > threshold.warning_threshold:
                        recovered = True
                
                if recovered:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    
                    # 发送恢复通知
                    recovery_alert = AlertEvent(
                        timestamp=datetime.now(),
                        level=AlertLevel.INFO,
                        metric_name=alert.metric_name,
                        current_value=current_value,
                        threshold_value=alert.threshold_value,
                        message=f"{alert.metric_name} recovered: {current_value}",
                        resolved=True
                    )
                    
                    for handler in self.notification_handlers:
                        try:
                            handler.send_notification(recovery_alert)
                        except Exception as e:
                            logger.error(f"Recovery notification failed: {e}")
                    
                    resolved_keys.append(alert_key)
            
            # 移除已解决的告警
            for key in resolved_keys:
                del self.active_alerts[key]
    
    def save_metrics(self, metrics: Dict[str, Any]):
        """保存监控数据"""
        try:
            with open(self.metrics_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(metrics) + '\n')
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def run_monitoring_cycle(self):
        """运行一次监控周期"""
        if not self.monitoring_enabled:
            return
        
        try:
            # 收集指标
            metrics = self.collect_metrics()
            if not metrics:
                return
            
            # 保存指标
            self.save_metrics(metrics)
            
            # 检查告警
            alerts = self.check_thresholds(metrics)
            
            # 处理告警
            if alerts:
                self.process_alerts(alerts)
            
            # 解决已恢复的告警
            self.resolve_alerts(metrics)
            
            self.last_check_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控系统状态"""
        with self._lock:
            return {
                'monitoring_enabled': self.monitoring_enabled,
                'last_check_time': self.last_check_time.isoformat(),
                'active_alerts_count': len(self.active_alerts),
                'active_alerts': [asdict(alert) for alert in self.active_alerts.values()],
                'thresholds_count': len(self.thresholds),
                'notification_handlers_count': len(self.notification_handlers),
                'data_dir': str(self.data_dir),
                'psutil_available': PSUTIL_AVAILABLE
            }


# 全局增强监控实例
_enhanced_monitor = None


def get_enhanced_monitor() -> EnhancedMonitor:
    """获取全局增强监控实例"""
    global _enhanced_monitor
    if _enhanced_monitor is None:
        _enhanced_monitor = EnhancedMonitor()
    return _enhanced_monitor
