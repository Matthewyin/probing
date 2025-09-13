"""
服务适配器模块
提供统一接口，支持在aiohttp和传统实现之间切换
"""
import asyncio
from typing import Optional, Dict, Any

from .logger import get_logger
from .config import settings
from .models import TCPConnectionInfo, HTTPResponseInfo, TLSInfo
from .models import EnhancedTCPConnectionInfo, EnhancedHTTPResponseInfo, EnhancedTLSInfo
from .services import TCPConnectionService, HTTPService, TLSService
from .aiohttp_services import AiohttpHTTPService, AiohttpTLSService
from .async_tcp_service import AsyncTCPService

logger = get_logger(__name__)


class TCPServiceAdapter:
    """TCP服务适配器 - 支持AsyncTCPService和传统实现"""

    def __init__(self):
        self.legacy_service = TCPConnectionService()  # 传统实现
        self.async_service = AsyncTCPService()        # 新的AsyncTCP实现

    async def test_connection(self, host: str, port: int, target_ip: str) -> TCPConnectionInfo:
        """统一的TCP连接测试接口"""

        if settings.USE_ASYNC_TCP_SERVICE:
            try:
                # 尝试使用新的AsyncTCPService
                result = await self.async_service.test_connection(host, port, target_ip)

                # 如果需要详细信息，直接返回增强结果
                if settings.ENABLE_DETAILED_TIMING:
                    return result
                else:
                    # 转换为标准格式（向后兼容）
                    return self._convert_to_standard_format(result)

            except Exception as e:
                logger.warning(f"AsyncTCP test failed, falling back to legacy: {e}")

                if settings.TCP_FALLBACK_ENABLED:
                    # 降级到传统实现
                    return await self.legacy_service.test_connection(host, port, target_ip)
                else:
                    raise
        else:
            # 直接使用传统实现
            return await self.legacy_service.test_connection(host, port, target_ip)

    def _convert_to_standard_format(self, enhanced_result: EnhancedTCPConnectionInfo) -> TCPConnectionInfo:
        """将增强结果转换为标准格式（向后兼容）"""
        return TCPConnectionInfo(
            host=enhanced_result.host,
            port=enhanced_result.port,
            target_ip=enhanced_result.target_ip,
            connect_time_ms=enhanced_result.connect_time_ms,
            is_connected=enhanced_result.is_connected,
            socket_family=enhanced_result.socket_family,
            local_address=enhanced_result.local_address,
            local_port=enhanced_result.local_port,
            error_message=enhanced_result.error_message
        )

    async def compare_implementations(self, host: str, port: int, target_ip: str) -> Dict[str, Any]:
        """并行测试新旧实现，进行性能对比"""
        import time

        # 并行执行新旧实现
        async_start = time.time()
        try:
            async_result = await self.async_service.test_connection(host, port, target_ip)
            async_success = True
            async_error = None
        except Exception as e:
            async_result = None
            async_success = False
            async_error = str(e)
        async_duration = (time.time() - async_start) * 1000

        legacy_start = time.time()
        try:
            legacy_result = await self.legacy_service.test_connection(host, port, target_ip)
            legacy_success = True
            legacy_error = None
        except Exception as e:
            legacy_result = None
            legacy_success = False
            legacy_error = str(e)
        legacy_duration = (time.time() - legacy_start) * 1000

        # 生成对比报告
        comparison = {
            "test_target": f"{host}:{port} ({target_ip})",
            "async_tcp": {
                "success": async_success,
                "duration_ms": async_duration,
                "result": async_result.dict() if async_result else None,
                "error": async_error
            },
            "legacy_tcp": {
                "success": legacy_success,
                "duration_ms": legacy_duration,
                "result": legacy_result.dict() if legacy_result else None,
                "error": legacy_error
            },
            "performance_analysis": {
                "async_faster": async_duration < legacy_duration,
                "speed_improvement": ((legacy_duration - async_duration) / legacy_duration * 100) if legacy_duration > 0 else 0,
                "consistency_check": self._check_result_consistency(async_result, legacy_result)
            }
        }

        logger.info(f"TCP Implementation Comparison for {host}:{port}")
        logger.info(f"  AsyncTCP: {async_duration:.2f}ms ({'✓' if async_success else '✗'})")
        logger.info(f"  Legacy:   {legacy_duration:.2f}ms ({'✓' if legacy_success else '✗'})")
        if async_success and legacy_success:
            improvement = comparison["performance_analysis"]["speed_improvement"]
            logger.info(f"  Performance: {improvement:+.1f}% ({'faster' if improvement > 0 else 'slower'})")

        return comparison

    def _check_result_consistency(self, async_result: Optional[EnhancedTCPConnectionInfo],
                                 legacy_result: Optional[TCPConnectionInfo]) -> Dict[str, Any]:
        """检查新旧实现结果的一致性"""
        if not async_result or not legacy_result:
            return {"consistent": False, "reason": "One or both implementations failed"}

        # 检查关键字段的一致性
        checks = {
            "is_connected": async_result.is_connected == legacy_result.is_connected,
            "socket_family": async_result.socket_family == legacy_result.socket_family,
            "target_ip": async_result.target_ip == legacy_result.target_ip,
            "port": async_result.port == legacy_result.port
        }

        all_consistent = all(checks.values())

        return {
            "consistent": all_consistent,
            "field_checks": checks,
            "differences": [field for field, consistent in checks.items() if not consistent]
        }



class HTTPServiceAdapter:
    """HTTP服务适配器"""
    
    def __init__(self):
        self.legacy_service = HTTPService()  # 现有httpx实现
    
    async def get_http_info(self, url: str) -> Optional[HTTPResponseInfo]:
        """统一的HTTP信息获取接口"""
        
        if settings.USE_AIOHTTP_CLIENT:
            try:
                # 尝试使用aiohttp实现
                aiohttp_service = AiohttpHTTPService()
                result = await aiohttp_service.get_http_info(url)
                
                if result:
                    # 如果需要详细信息，直接返回增强结果
                    if settings.ENABLE_DETAILED_TIMING:
                        return result
                    else:
                        # 转换为标准格式（向后兼容）
                        return self._convert_to_standard_format(result)
                else:
                    return None
                    
            except Exception as e:
                logger.warning(f"aiohttp HTTP test failed, falling back to httpx: {e}")
                
                if settings.AIOHTTP_FALLBACK_ENABLED:
                    return await self.legacy_service.get_http_info(url)
                else:
                    raise
        else:
            return await self.legacy_service.get_http_info(url)
    
    def _convert_to_standard_format(self, enhanced_result: EnhancedHTTPResponseInfo) -> HTTPResponseInfo:
        """将增强结果转换为标准格式（向后兼容）"""
        return HTTPResponseInfo(
            status_code=enhanced_result.status_code,
            reason_phrase=enhanced_result.reason_phrase,
            headers=enhanced_result.headers,
            response_time_ms=enhanced_result.response_time_ms,
            content_length=enhanced_result.content_length,
            content_type=enhanced_result.content_type,
            server=enhanced_result.server,
            redirect_count=enhanced_result.redirect_count,
            final_url=enhanced_result.final_url
        )


class TLSServiceAdapter:
    """TLS服务适配器"""
    
    def __init__(self):
        self.legacy_service = TLSService()  # 现有实现
    
    async def get_tls_info(self, host: str, port: int) -> Optional[TLSInfo]:
        """统一的TLS信息获取接口"""

        if settings.USE_AIOHTTP_CLIENT:
            try:
                # 使用aiohttp TLS实现
                aiohttp_service = AiohttpTLSService()
                result = await aiohttp_service.get_tls_info(host, port)

                if result:
                    # 如果需要详细信息，直接返回增强结果
                    if settings.ENABLE_DETAILED_TIMING:
                        return result
                    else:
                        # 转换为标准格式（向后兼容）
                        return self._convert_to_standard_format(result)
                else:
                    return None

            except Exception as e:
                logger.warning(f"aiohttp TLS test failed, falling back to legacy: {e}")

                if settings.AIOHTTP_FALLBACK_ENABLED:
                    return await self.legacy_service.get_tls_info(host, port)
                else:
                    raise
        else:
            return await self.legacy_service.get_tls_info(host, port)

    def _convert_to_standard_format(self, enhanced_result: EnhancedTLSInfo) -> TLSInfo:
        """将增强结果转换为标准格式（向后兼容）"""
        return TLSInfo(
            protocol_version=enhanced_result.protocol_version,
            cipher_suite=enhanced_result.cipher_suite,
            certificate=enhanced_result.certificate,
            certificate_chain_length=enhanced_result.certificate_chain_length,
            is_secure=enhanced_result.is_secure,
            handshake_time_ms=enhanced_result.handshake_time_ms
        )


class NetworkServiceFactory:
    """网络服务工厂 - 根据配置创建相应的服务实例"""
    
    @staticmethod
    def create_tcp_service():
        """创建TCP服务实例"""
        return TCPServiceAdapter()
    
    @staticmethod
    def create_http_service():
        """创建HTTP服务实例"""
        return HTTPServiceAdapter()
    
    @staticmethod
    def create_tls_service():
        """创建TLS服务实例"""
        return TLSServiceAdapter()
    
    @staticmethod
    def create_all_services():
        """创建所有网络服务实例"""
        return {
            'tcp': NetworkServiceFactory.create_tcp_service(),
            'http': NetworkServiceFactory.create_http_service(),
            'tls': NetworkServiceFactory.create_tls_service()
        }


# 便捷函数，用于快速测试
async def test_tcp_connection_with_fallback(host: str, port: int, target_ip: str) -> TCPConnectionInfo:
    """便捷函数：测试TCP连接（带fallback）"""
    adapter = TCPServiceAdapter()
    return await adapter.test_connection(host, port, target_ip)


async def test_http_response_with_fallback(url: str) -> Optional[HTTPResponseInfo]:
    """便捷函数：测试HTTP响应（带fallback）"""
    adapter = HTTPServiceAdapter()
    return await adapter.get_http_info(url)


async def test_tls_info_with_fallback(host: str, port: int) -> Optional[TLSInfo]:
    """便捷函数：测试TLS信息（带fallback）"""
    adapter = TLSServiceAdapter()
    return await adapter.get_tls_info(host, port)
