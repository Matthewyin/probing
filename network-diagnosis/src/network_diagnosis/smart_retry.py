"""
智能重试机制
基于错误分析结果决定重试策略
"""
import asyncio
import time
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass

from .logger import get_logger
from .models import EnhancedTCPConnectionInfo

logger = get_logger(__name__)


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_backoff: bool = True
    jitter: bool = True


class SmartRetryManager:
    """智能重试管理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    async def execute_with_retry(
        self,
        operation: Callable[[], Awaitable[Any]],
        operation_name: str,
        should_retry_func: Optional[Callable[[Any], bool]] = None
    ) -> Any:
        """
        执行操作并根据结果智能重试
        
        Args:
            operation: 要执行的异步操作
            operation_name: 操作名称（用于日志）
            should_retry_func: 自定义重试判断函数
            
        Returns:
            操作结果
        """
        last_result = None
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(f"Executing {operation_name}, attempt {attempt + 1}/{self.config.max_retries + 1}")
                
                result = await operation()
                
                # 检查是否需要重试
                if should_retry_func and should_retry_func(result):
                    if attempt < self.config.max_retries:
                        delay = self._calculate_delay(attempt, result)
                        logger.info(f"{operation_name} needs retry (attempt {attempt + 1}), waiting {delay:.2f}s")
                        await asyncio.sleep(delay)
                        last_result = result
                        continue
                    else:
                        logger.warning(f"{operation_name} failed after {self.config.max_retries} retries")
                        return result
                else:
                    # 成功或不需要重试
                    if attempt > 0:
                        logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                    return result
                    
            except Exception as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(f"{operation_name} failed with {type(e).__name__}: {e}, retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"{operation_name} failed after {self.config.max_retries} retries: {e}")
                    raise
        
        # 如果到这里，说明所有重试都失败了
        if last_exception:
            raise last_exception
        return last_result
    
    def _calculate_delay(self, attempt: int, result: Any = None) -> float:
        """计算重试延迟时间"""
        # 基础延迟
        if self.config.exponential_backoff:
            delay = self.config.base_delay * (2 ** attempt)
        else:
            delay = self.config.base_delay
        
        # 限制最大延迟
        delay = min(delay, self.config.max_delay)
        
        # 基于错误分析调整延迟
        if result and hasattr(result, 'error_classification'):
            error_info = result.error_classification
            if error_info and isinstance(error_info, dict):
                suggested_delay = error_info.get('retry_delay_seconds', delay)
                delay = max(delay, suggested_delay)
        
        # 添加抖动避免雷群效应
        if self.config.jitter:
            import random
            jitter_factor = 0.1  # 10%的抖动
            jitter = delay * jitter_factor * (random.random() * 2 - 1)
            delay += jitter
        
        return max(0.1, delay)  # 最小延迟0.1秒
    
    @staticmethod
    def should_retry_tcp_connection(result: EnhancedTCPConnectionInfo) -> bool:
        """判断TCP连接是否应该重试"""
        if result.is_connected:
            return False
        
        # 检查错误分析
        error_info = result.error_classification
        if error_info and isinstance(error_info, dict):
            return error_info.get('is_retryable', False)
        
        # 默认不重试
        return False
    
    @staticmethod
    def should_retry_by_error_type(error_type: str) -> bool:
        """根据错误类型判断是否应该重试"""
        retryable_errors = {
            'timeout',
            'network_unreachable', 
            'connection_reset',
            'temporary_failure'
        }
        return error_type in retryable_errors


class EnhancedDiagnosisCoordinator:
    """增强的诊断协调器，支持智能重试"""
    
    def __init__(self, base_coordinator, retry_config: Optional[RetryConfig] = None):
        self.base_coordinator = base_coordinator
        self.retry_manager = SmartRetryManager(retry_config)
    
    async def diagnose_with_retry(self, request) -> Any:
        """带智能重试的诊断"""
        
        async def tcp_operation():
            """TCP连接操作"""
            if not request.target_ip:
                return None
            
            return await self.base_coordinator.tcp_service.test_connection(
                request.domain, 
                request.port, 
                request.target_ip
            )
        
        async def tls_operation():
            """TLS连接操作"""
            return await self.base_coordinator.tls_service.get_tls_info(
                request.domain, 
                request.port
            )
        
        async def http_operation():
            """HTTP请求操作"""
            # 构建URL
            protocol = "https" if request.port in [443, 8443] else "http"
            url = f"{protocol}://{request.domain}:{request.port}/"
            
            return await self.base_coordinator.http_service.get_http_info(url)
        
        # 执行DNS解析（通常不需要重试）
        dns_result = await self.base_coordinator.dns_service.resolve_domain(request.domain)
        request.target_ip = dns_result.primary_ip if dns_result.is_successful else None
        
        results = {
            'dns_resolution': dns_result,
            'tcp_connection': None,
            'tls_info': None,
            'http_response': None
        }
        
        # TCP连接（支持智能重试）
        if request.target_ip:
            try:
                tcp_result = await self.retry_manager.execute_with_retry(
                    tcp_operation,
                    f"TCP connection to {request.domain}:{request.port}",
                    self.retry_manager.should_retry_tcp_connection
                )
                results['tcp_connection'] = tcp_result
                
                # 只有TCP成功才继续后续测试
                if tcp_result and tcp_result.is_connected:
                    
                    # TLS测试（如果需要）
                    if request.include_tls and request.port in [443, 8443]:
                        try:
                            tls_result = await self.retry_manager.execute_with_retry(
                                tls_operation,
                                f"TLS handshake to {request.domain}:{request.port}",
                                lambda result: result is None or not result.is_secure
                            )
                            results['tls_info'] = tls_result
                        except Exception as e:
                            logger.warning(f"TLS test failed: {e}")
                    
                    # HTTP测试（如果需要）
                    if request.include_http:
                        try:
                            http_result = await self.retry_manager.execute_with_retry(
                                http_operation,
                                f"HTTP request to {request.domain}:{request.port}",
                                lambda result: result is None or result.status_code >= 500
                            )
                            results['http_response'] = http_result
                        except Exception as e:
                            logger.warning(f"HTTP test failed: {e}")
                            
            except Exception as e:
                logger.error(f"TCP connection failed after retries: {e}")
        
        return results


def create_retry_config_from_settings() -> RetryConfig:
    """从配置创建重试配置"""
    from .config import settings
    
    return RetryConfig(
        max_retries=getattr(settings, 'TCP_MAX_RETRIES', 3),
        base_delay=getattr(settings, 'TCP_RETRY_BASE_DELAY', 1.0),
        max_delay=getattr(settings, 'TCP_RETRY_MAX_DELAY', 30.0),
        exponential_backoff=getattr(settings, 'TCP_RETRY_EXPONENTIAL_BACKOFF', True),
        jitter=getattr(settings, 'TCP_RETRY_JITTER', True)
    )
