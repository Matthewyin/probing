"""
资源监控模块 - 监控系统资源使用情况，防止资源泄漏
"""
import os
import logging
import resource
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from .logger import get_logger

logger = get_logger(__name__)

# 延迟导入避免循环依赖
def get_process_manager():
    """延迟导入进程管理器"""
    try:
        from .process_manager import process_manager
        return process_manager
    except ImportError:
        return None


class ResourceMonitor:
    """系统资源监控器"""
    
    @staticmethod
    def get_open_files_count() -> int:
        """
        获取当前进程打开的文件数量
        
        Returns:
            打开的文件数量，如果获取失败返回-1
        """
        try:
            if PSUTIL_AVAILABLE:
                process = psutil.Process(os.getpid())
                return len(process.open_files())
            else:
                # 备用方法：通过/proc/self/fd目录计算（仅Linux）
                try:
                    fd_dir = "/proc/self/fd"
                    if os.path.exists(fd_dir):
                        return len(os.listdir(fd_dir))
                except:
                    pass
                return -1
        except Exception as e:
            logger.warning(f"Failed to get open files count: {e}")
            return -1
    
    @staticmethod
    def get_file_descriptor_limits() -> Dict[str, int]:
        """
        获取文件描述符限制
        
        Returns:
            包含软限制和硬限制的字典
        """
        try:
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            return {
                'soft_limit': soft_limit,
                'hard_limit': hard_limit
            }
        except Exception as e:
            logger.warning(f"Failed to get file descriptor limits: {e}")
            return {
                'soft_limit': -1,
                'hard_limit': -1
            }
    
    @staticmethod
    def check_resource_limits() -> Dict[str, Any]:
        """
        检查资源使用情况
        
        Returns:
            资源使用状态字典
        """
        open_files = ResourceMonitor.get_open_files_count()
        limits = ResourceMonitor.get_file_descriptor_limits()
        
        soft_limit = limits['soft_limit']
        hard_limit = limits['hard_limit']
        
        # 计算使用率
        usage_ratio = 0.0
        if soft_limit > 0 and open_files >= 0:
            usage_ratio = open_files / soft_limit
        
        # 判断警告和危险状态
        warning = usage_ratio > 0.7  # 超过70%发出警告
        critical = usage_ratio > 0.9  # 超过90%为危险状态
        
        return {
            'timestamp': datetime.now().isoformat(),
            'open_files': open_files,
            'soft_limit': soft_limit,
            'hard_limit': hard_limit,
            'usage_ratio': usage_ratio,
            'usage_percentage': f"{usage_ratio * 100:.1f}%",
            'warning': warning,
            'critical': critical,
            'status': 'critical' if critical else ('warning' if warning else 'healthy')
        }
    
    @staticmethod
    def monitor_log_handlers() -> Dict[str, Any]:
        """
        监控日志处理器数量
        
        Returns:
            日志处理器状态字典
        """
        try:
            root_logger = logging.getLogger()
            business_logger = logging.getLogger("business_log")
            
            # 统计文件处理器数量
            root_file_handlers = len([h for h in root_logger.handlers 
                                    if isinstance(h, logging.FileHandler)])
            business_file_handlers = len([h for h in business_logger.handlers 
                                        if isinstance(h, logging.FileHandler)])
            
            total_file_handlers = root_file_handlers + business_file_handlers
            
            # 统计所有处理器数量
            total_root_handlers = len(root_logger.handlers)
            total_business_handlers = len(business_logger.handlers)
            
            # 判断是否异常
            warning = total_file_handlers > 2  # 正常情况下应该只有2个文件处理器
            critical = total_file_handlers > 10  # 超过10个就很危险了
            
            return {
                'timestamp': datetime.now().isoformat(),
                'root_file_handlers': root_file_handlers,
                'business_file_handlers': business_file_handlers,
                'total_file_handlers': total_file_handlers,
                'total_root_handlers': total_root_handlers,
                'total_business_handlers': total_business_handlers,
                'warning': warning,
                'critical': critical,
                'status': 'critical' if critical else ('warning' if warning else 'healthy')
            }
        except Exception as e:
            logger.error(f"Failed to monitor log handlers: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'status': 'error'
            }

    @staticmethod
    def monitor_process_status() -> Dict[str, Any]:
        """
        监控进程状态

        Returns:
            进程状态字典
        """
        process_manager = get_process_manager()
        if not process_manager:
            return {
                'active_processes': 0,
                'process_info': [],
                'warning': False,
                'critical': False,
                'manager_available': False
            }

        try:
            active_count = process_manager.get_process_count()
            process_info = process_manager.get_process_info()

            # 检查是否有长时间运行的进程
            long_running_processes = [
                p for p in process_info
                if p.get('running_time', 0) > 600  # 超过10分钟
            ]

            # 检查是否有超时的进程
            timeout_processes = [
                p for p in process_info
                if p.get('timeout') and p.get('running_time', 0) > p.get('timeout', 0)
            ]

            warning = active_count > 10 or len(long_running_processes) > 0
            critical = active_count > 50 or len(timeout_processes) > 0

            return {
                'active_processes': active_count,
                'process_info': process_info,
                'long_running_processes': len(long_running_processes),
                'timeout_processes': len(timeout_processes),
                'warning': warning,
                'critical': critical,
                'manager_available': True
            }

        except Exception as e:
            logger.warning(f"Failed to get process status: {e}")
            return {
                'active_processes': -1,
                'process_info': [],
                'warning': False,
                'critical': False,
                'manager_available': True,
                'error': str(e)
            }

    @staticmethod
    def get_comprehensive_status() -> Dict[str, Any]:
        """
        获取综合资源状态
        
        Returns:
            综合状态字典
        """
        resource_status = ResourceMonitor.check_resource_limits()
        handler_status = ResourceMonitor.monitor_log_handlers()
        process_status = ResourceMonitor.monitor_process_status()

        # 确定整体状态
        overall_status = 'healthy'
        warnings = []
        errors = []

        # 检查资源状态
        if resource_status.get('critical', False):
            overall_status = 'critical'
            errors.append(f"Critical file descriptor usage: {resource_status.get('usage_percentage', 'unknown')}")
        elif resource_status.get('warning', False):
            if overall_status != 'critical':
                overall_status = 'warning'
            warnings.append(f"High file descriptor usage: {resource_status.get('usage_percentage', 'unknown')}")

        # 检查处理器状态
        if handler_status.get('critical', False):
            overall_status = 'critical'
            errors.append(f"Too many log handlers: {handler_status.get('total_file_handlers', 'unknown')}")
        elif handler_status.get('warning', False):
            if overall_status != 'critical':
                overall_status = 'warning'
            warnings.append(f"Unusual log handler count: {handler_status.get('total_file_handlers', 'unknown')}")

        # 🔧 新增：检查进程状态
        if process_status.get('critical', False):
            overall_status = 'critical'
            errors.append(f"Critical process issues: {process_status.get('active_processes', 'unknown')} active, {process_status.get('timeout_processes', 0)} timeout")
        elif process_status.get('warning', False):
            if overall_status != 'critical':
                overall_status = 'warning'
            warnings.append(f"Process concerns: {process_status.get('active_processes', 'unknown')} active, {process_status.get('long_running_processes', 0)} long-running")

        return {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status,
            'resource_status': resource_status,
            'handler_status': handler_status,
            'process_status': process_status,
            'warnings': warnings,
            'errors': errors,
            'psutil_available': PSUTIL_AVAILABLE
        }
    
    @staticmethod
    def log_status_summary():
        """记录资源状态摘要到日志"""
        try:
            status = ResourceMonitor.get_comprehensive_status()
            
            if status['overall_status'] == 'critical':
                logger.error(f"🚨 Critical resource status: {', '.join(status['errors'])}")
            elif status['overall_status'] == 'warning':
                logger.warning(f"⚠️ Resource warning: {', '.join(status['warnings'])}")
            else:
                logger.debug(f"✅ Resource status healthy - Files: {status['resource_status']['open_files']}, Handlers: {status['handler_status']['total_file_handlers']}")
                
        except Exception as e:
            logger.error(f"Failed to log status summary: {e}")


def install_psutil_if_missing():
    """如果psutil不可用，提供安装提示"""
    if not PSUTIL_AVAILABLE:
        logger.warning(
            "psutil is not available. For better resource monitoring, install it with: "
            "pip install psutil"
        )
        return False
    return True


# 在模块加载时检查psutil可用性
install_psutil_if_missing()
