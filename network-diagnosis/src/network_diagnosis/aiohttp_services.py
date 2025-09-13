"""
基于aiohttp的网络诊断服务模块
提供TCP、HTTP、TLS拨测的增强实现
"""
import asyncio
import aiohttp
import ssl
import time
import socket
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from .logger import get_logger
from .config import settings
from .models import (
    EnhancedTCPConnectionInfo, EnhancedHTTPResponseInfo, EnhancedTLSInfo,
    TCPConnectionInfo, HTTPResponseInfo, TLSInfo, SSLCertificateInfo
)

logger = get_logger(__name__)


class AiohttpTCPService:
    """基于aiohttp的TCP连接测试服务"""
    
    def __init__(self):
        self.connector = None
        self.session = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.connector = aiohttp.TCPConnector(
            limit=settings.AIOHTTP_CONNECTOR_LIMIT,
            limit_per_host=settings.AIOHTTP_CONNECTOR_LIMIT_PER_HOST,
            ttl_dns_cache=settings.AIOHTTP_CONNECTOR_TTL_DNS_CACHE,
            use_dns_cache=settings.AIOHTTP_CONNECTOR_USE_DNS_CACHE,
            enable_cleanup_closed=True
        )
        self.session = aiohttp.ClientSession(connector=self.connector)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()
    
    async def test_connection(self, host: str, port: int, target_ip: str) -> EnhancedTCPConnectionInfo:
        """测试TCP连接（aiohttp版本）"""
        start_time = time.time()
        timing_breakdown = {}
        
        try:
            # 构造测试URL（用于触发TCP连接）
            test_url = f"http://{target_ip}:{port}/"
            
            # 创建自定义连接器以获取详细信息
            connector = aiohttp.TCPConnector(
                limit=1,
                limit_per_host=1,
                enable_cleanup_closed=True,
                # 禁用SSL以进行纯TCP测试
                ssl=False
            )
            
            async with aiohttp.ClientSession(connector=connector) as session:
                # 记录DNS解析开始时间（虽然这里使用IP，但保持结构一致）
                dns_start = time.time()
                tcp_start = time.time()
                
                try:
                    # 尝试建立连接（使用HEAD请求减少数据传输）
                    async with session.head(
                        test_url,
                        timeout=aiohttp.ClientTimeout(
                            connect=settings.CONNECT_TIMEOUT,
                            total=settings.CONNECT_TIMEOUT
                        ),
                        allow_redirects=False
                    ) as response:
                        connect_time = (time.time() - start_time) * 1000
                        
                        # 提取连接信息
                        connection_info = self._extract_connection_info(response)
                        timing_breakdown = self._extract_timing_info(start_time, dns_start, tcp_start)
                        pool_info = self._get_pool_info(connector)
                        
                        logger.info(f"aiohttp TCP connection to {host}:{port} ({target_ip}) successful in {connect_time:.2f}ms")
                        
                        return EnhancedTCPConnectionInfo(
                            host=host,
                            port=port,
                            target_ip=target_ip,
                            connect_time_ms=connect_time,
                            is_connected=True,
                            socket_family="IPv4",  # 从连接信息中提取
                            local_address=connection_info.get("local_address"),
                            local_port=connection_info.get("local_port"),
                            timing_breakdown=timing_breakdown,
                            connection_pool_info=pool_info,
                            transport_info=connection_info
                        )
                        
                except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as e:
                    # 连接失败
                    connect_time = (time.time() - start_time) * 1000
                    timing_breakdown = self._extract_timing_info(start_time, dns_start, tcp_start)
                    
                    logger.warning(f"aiohttp TCP connection to {host}:{port} ({target_ip}) failed: {str(e)}")
                    
                    return EnhancedTCPConnectionInfo(
                        host=host,
                        port=port,
                        target_ip=target_ip,
                        connect_time_ms=connect_time,
                        is_connected=False,
                        socket_family="IPv4",
                        error_message=str(e),
                        timing_breakdown=timing_breakdown
                    )
                    
        except Exception as e:
            connect_time = (time.time() - start_time) * 1000
            logger.error(f"aiohttp TCP connection to {host}:{port} ({target_ip}) failed with unexpected error: {str(e)}")
            
            return EnhancedTCPConnectionInfo(
                host=host,
                port=port,
                target_ip=target_ip,
                connect_time_ms=connect_time,
                is_connected=False,
                socket_family="IPv4",
                error_message=str(e),
                timing_breakdown={"total_time_ms": connect_time}
            )
    
    def _extract_connection_info(self, response) -> Dict[str, Any]:
        """从响应中提取连接信息"""
        connection_info = {}
        
        try:
            # 尝试从响应中获取连接信息
            if hasattr(response, 'connection') and response.connection:
                transport = response.connection.transport
                if transport:
                    # 获取本地和远程地址
                    if hasattr(transport, 'get_extra_info'):
                        sockname = transport.get_extra_info('sockname')
                        peername = transport.get_extra_info('peername')
                        
                        if sockname:
                            connection_info['local_address'] = sockname[0]
                            connection_info['local_port'] = sockname[1]
                        
                        if peername:
                            connection_info['remote_address'] = peername[0]
                            connection_info['remote_port'] = peername[1]
                        
                        # 获取socket信息
                        sock = transport.get_extra_info('socket')
                        if sock:
                            connection_info['socket_family'] = sock.family.name
                            connection_info['socket_type'] = sock.type.name
                            
        except Exception as e:
            logger.debug(f"Failed to extract connection info: {e}")
        
        return connection_info
    
    def _extract_timing_info(self, start_time: float, dns_start: float, tcp_start: float) -> Dict[str, float]:
        """提取详细的timing信息"""
        current_time = time.time()
        
        return {
            "dns_lookup_ms": (tcp_start - dns_start) * 1000,  # DNS查找时间（这里为0，因为使用IP）
            "tcp_connect_ms": (current_time - tcp_start) * 1000,  # TCP连接时间
            "total_time_ms": (current_time - start_time) * 1000  # 总时间
        }
    
    def _get_pool_info(self, connector) -> Dict[str, Any]:
        """获取连接池信息"""
        pool_info = {}
        
        try:
            if hasattr(connector, '_conns'):
                # 获取连接池统计信息
                pool_info['pool_size'] = len(connector._conns)
                pool_info['active_connections'] = sum(len(conns) for conns in connector._conns.values())
                pool_info['connection_reused'] = False  # 新连接默认为False
                
        except Exception as e:
            logger.debug(f"Failed to get pool info: {e}")
        
        return pool_info


class AiohttpHTTPService:
    """基于aiohttp的HTTP响应信息收集服务"""

    def __init__(self):
        self.trace_config = None
        self.timing_data = {}

    async def get_http_info(self, url: str) -> Optional[EnhancedHTTPResponseInfo]:
        """获取HTTP响应信息（aiohttp版本）"""
        start_time = time.time()

        try:
            # 解析URL以确定是否需要SSL
            parsed_url = urlparse(url)
            use_ssl = parsed_url.scheme == 'https'

            # 创建trace配置以获取详细timing
            self.timing_data = {}
            trace_config = self._create_trace_config()

            # 创建自定义连接器
            connector = aiohttp.TCPConnector(
                limit=settings.AIOHTTP_CONNECTOR_LIMIT,
                limit_per_host=settings.AIOHTTP_CONNECTOR_LIMIT_PER_HOST,
                ssl=False,  # 禁用SSL验证以匹配现有行为
                enable_cleanup_closed=True,
                ttl_dns_cache=settings.AIOHTTP_CONNECTOR_TTL_DNS_CACHE,
                use_dns_cache=settings.AIOHTTP_CONNECTOR_USE_DNS_CACHE
            )

            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    connect=settings.CONNECT_TIMEOUT,
                    total=settings.READ_TIMEOUT
                ),
                trace_configs=[trace_config]
            ) as session:

                async with session.get(
                    url,
                    allow_redirects=True,
                    max_redirects=settings.MAX_REDIRECTS
                ) as response:

                    response_time = (time.time() - start_time) * 1000

                    # 提取详细timing信息
                    timing_breakdown = self._extract_http_timing(start_time)

                    # 提取连接信息
                    connection_info = self._extract_http_connection_info(response)

                    # 读取响应内容
                    content = await response.read()

                    logger.info(f"aiohttp HTTP request to {url} completed in {response_time:.2f}ms with status {response.status}")

                    return EnhancedHTTPResponseInfo(
                        status_code=response.status,
                        reason_phrase=response.reason or "",
                        headers=dict(response.headers),
                        response_time_ms=response_time,
                        content_length=len(content) if content else None,
                        content_type=response.headers.get('content-type'),
                        server=response.headers.get('server'),
                        redirect_count=len(response.history),
                        final_url=str(response.url),
                        timing_breakdown=timing_breakdown,
                        connection_info=connection_info,
                        request_info=self._get_request_info(response),
                        response_details=self._get_response_details(response, content)
                    )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"aiohttp HTTP request to {url} failed: {str(e)}")
            return None
    
    def _create_trace_config(self) -> aiohttp.TraceConfig:
        """创建trace配置以获取详细timing信息"""
        trace_config = aiohttp.TraceConfig()

        # DNS解析开始
        async def on_dns_resolvehost_start(session, trace_config_ctx, params):
            trace_config_ctx.dns_start = time.time()

        # DNS解析结束
        async def on_dns_resolvehost_end(session, trace_config_ctx, params):
            if hasattr(trace_config_ctx, 'dns_start'):
                self.timing_data['dns_lookup_ms'] = (time.time() - trace_config_ctx.dns_start) * 1000

        # 连接开始
        async def on_connection_create_start(session, trace_config_ctx, params):
            trace_config_ctx.connection_start = time.time()

        # 连接结束
        async def on_connection_create_end(session, trace_config_ctx, params):
            if hasattr(trace_config_ctx, 'connection_start'):
                self.timing_data['tcp_connect_ms'] = (time.time() - trace_config_ctx.connection_start) * 1000

        # 请求开始
        async def on_request_start(session, trace_config_ctx, params):
            trace_config_ctx.request_start = time.time()

        # 请求结束
        async def on_request_end(session, trace_config_ctx, params):
            if hasattr(trace_config_ctx, 'request_start'):
                self.timing_data['request_sent_ms'] = (time.time() - trace_config_ctx.request_start) * 1000

        # 响应开始
        async def on_response_chunk_received(session, trace_config_ctx, params):
            if not hasattr(trace_config_ctx, 'first_byte_time'):
                trace_config_ctx.first_byte_time = time.time()
                if hasattr(trace_config_ctx, 'request_start'):
                    self.timing_data['waiting_time_ms'] = (trace_config_ctx.first_byte_time - trace_config_ctx.request_start) * 1000

        # 绑定事件
        trace_config.on_dns_resolvehost_start.append(on_dns_resolvehost_start)
        trace_config.on_dns_resolvehost_end.append(on_dns_resolvehost_end)
        trace_config.on_connection_create_start.append(on_connection_create_start)
        trace_config.on_connection_create_end.append(on_connection_create_end)
        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)
        trace_config.on_response_chunk_received.append(on_response_chunk_received)

        return trace_config

    def _extract_http_timing(self, start_time: float) -> Dict[str, float]:
        """提取HTTP请求的详细timing信息"""
        current_time = time.time()
        total_time = (current_time - start_time) * 1000

        # 使用trace收集的真实timing数据
        timing = {
            "dns_lookup_ms": self.timing_data.get('dns_lookup_ms', 0.0),
            "tcp_connect_ms": self.timing_data.get('tcp_connect_ms', 0.0),
            "request_sent_ms": self.timing_data.get('request_sent_ms', 0.0),
            "waiting_time_ms": self.timing_data.get('waiting_time_ms', 0.0),
            "total_time_ms": total_time
        }

        # 计算内容传输时间（总时间减去其他阶段）
        other_time = sum([timing['dns_lookup_ms'], timing['tcp_connect_ms'],
                         timing['request_sent_ms'], timing['waiting_time_ms']])
        timing['content_transfer_ms'] = max(0.0, total_time - other_time)

        return timing
    
    def _extract_http_connection_info(self, response) -> Dict[str, Any]:
        """提取HTTP连接信息"""
        connection_info = {}
        
        try:
            # 获取HTTP版本
            if hasattr(response, 'version'):
                connection_info['http_version'] = f"HTTP/{response.version.major}.{response.version.minor}"
            
            # 检查是否启用了keep-alive
            connection_header = response.headers.get('connection', '').lower()
            connection_info['keep_alive'] = 'keep-alive' in connection_header
            
            # 检查压缩
            encoding = response.headers.get('content-encoding')
            if encoding:
                connection_info['compression'] = encoding
            
            # 连接复用信息（需要从连接器获取）
            connection_info['connection_reused'] = False  # 默认值，实际需要从连接器获取
            
        except Exception as e:
            logger.debug(f"Failed to extract HTTP connection info: {e}")
        
        return connection_info
    
    def _get_request_info(self, response) -> Dict[str, Any]:
        """获取请求详细信息"""
        return {
            "method": "GET",  # 当前只支持GET
            "url": str(response.url),
            "headers_sent": {},  # 实际需要记录发送的头
        }
    
    def _get_response_details(self, response, content: bytes) -> Dict[str, Any]:
        """获取响应详细信息"""
        return {
            "content_size": len(content) if content else 0,
            "headers_received": dict(response.headers),
            "cookies_received": len(response.cookies) if hasattr(response, 'cookies') else 0,
        }


class AiohttpTLSService:
    """基于aiohttp的TLS/SSL信息收集服务"""

    def __init__(self):
        self.timing_data = {}

    async def get_tls_info(self, host: str, port: int) -> Optional[EnhancedTLSInfo]:
        """获取TLS/SSL连接信息（aiohttp增强版本）"""
        start_time = time.time()

        try:
            # 1. 基础TLS连接测试
            basic_info = await self._test_basic_tls(host, port, start_time)

            if basic_info:
                # 2. 双向SSL检测
                mutual_tls_info = await self._test_client_cert_requirement(host, port)

                # 3. 获取详细timing信息
                timing_breakdown = self._extract_tls_timing(start_time)

                # 4. TLS协商详情检测
                negotiation_details = await self._get_tls_negotiation_details(host, port)

                # 5. 安全特性检测
                security_features = await self._detect_security_features(host, port)

                logger.info(f"aiohttp TLS handshake to {host}:{port} completed in {basic_info.handshake_time_ms:.2f}ms")

                return EnhancedTLSInfo(
                    protocol_version=basic_info.protocol_version,
                    cipher_suite=basic_info.cipher_suite,
                    certificate=basic_info.certificate,
                    certificate_chain_length=basic_info.certificate_chain_length,
                    is_secure=basic_info.is_secure,
                    handshake_time_ms=basic_info.handshake_time_ms,
                    tls_timing_breakdown=timing_breakdown,
                    tls_negotiation_details=negotiation_details,
                    mutual_tls_info=mutual_tls_info,
                    security_features=security_features
                )
            else:
                # 连接失败，但尝试获取部分信息
                return await self._handle_failed_connection(host, port, start_time)

        except Exception as e:
            handshake_time = (time.time() - start_time) * 1000
            logger.error(f"aiohttp TLS connection to {host}:{port} failed: {str(e)}")

            # 尝试从失败中获取信息
            return await self._extract_info_from_failure(host, port, str(e), handshake_time)

    async def _test_basic_tls(self, host: str, port: int, start_time: float) -> Optional[TLSInfo]:
        """基础TLS连接测试"""
        try:
            # 创建SSL上下文
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE  # 禁用证书验证以获取更多信息

            # 记录TCP连接开始时间
            tcp_start = time.time()

            # 建立TCP连接
            sock = socket.create_connection((host, port), timeout=settings.CONNECT_TIMEOUT)
            tcp_time = (time.time() - tcp_start) * 1000
            self.timing_data['tcp_connect_ms'] = tcp_time

            # 记录TLS握手开始时间
            tls_start = time.time()

            # 进行TLS握手
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                handshake_time = (time.time() - start_time) * 1000
                tls_handshake_time = (time.time() - tls_start) * 1000
                self.timing_data['tls_handshake_ms'] = tls_handshake_time

                # 获取SSL信息
                cipher = ssock.cipher()
                protocol_version = ssock.version()
                peer_cert = ssock.getpeercert(binary_form=True)

                # 解析证书
                cert_info = None
                if peer_cert:
                    cert_info = await self._parse_certificate_async(peer_cert)

                return TLSInfo(
                    protocol_version=protocol_version or "Unknown",
                    cipher_suite=cipher[0] if cipher else "Unknown",
                    certificate=cert_info,
                    certificate_chain_length=1 if peer_cert else 0,
                    is_secure=True,
                    handshake_time_ms=handshake_time
                )

        except Exception as e:
            logger.debug(f"Basic TLS test failed for {host}:{port}: {str(e)}")
            return None

    async def _test_client_cert_requirement(self, host: str, port: int) -> Dict[str, Any]:
        """检测是否需要客户端证书（双向SSL检测）"""
        try:
            # 尝试不带客户端证书的连接
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with socket.create_connection((host, port), timeout=settings.CONNECT_TIMEOUT) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    # 连接成功，说明是单向SSL
                    return {
                        "requires_client_cert": False,
                        "connection_successful": True,
                        "ssl_type": "单向SSL",
                        "detection_method": "successful_connection"
                    }

        except ssl.SSLError as e:
            # 分析SSL错误
            error_msg = str(e).lower()
            client_cert_keywords = [
                "certificate required", "client certificate",
                "peer did not return a certificate", "certificate_required",
                "handshake failure", "certificate unknown"
            ]

            if any(keyword in error_msg for keyword in client_cert_keywords):
                # 可能是双向SSL
                server_cert_available = await self._can_get_server_cert(host, port)
                return {
                    "requires_client_cert": True,
                    "connection_successful": False,
                    "ssl_type": "双向SSL",
                    "error_details": str(e),
                    "server_cert_available": server_cert_available,
                    "detection_method": "ssl_error_analysis"
                }
            else:
                # 其他SSL错误
                return {
                    "requires_client_cert": False,
                    "connection_successful": False,
                    "ssl_type": "SSL错误",
                    "error_details": str(e),
                    "detection_method": "other_ssl_error"
                }

        except Exception as e:
            # 非SSL错误
            return {
                "requires_client_cert": False,
                "connection_successful": False,
                "ssl_type": "连接错误",
                "error_details": str(e),
                "detection_method": "connection_error"
            }

    async def _can_get_server_cert(self, host: str, port: int) -> bool:
        """检测是否能获取服务器证书（即使在双向SSL场景下）"""
        try:
            # 尝试进行部分握手以获取服务器证书
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with socket.create_connection((host, port), timeout=5) as sock:
                # 尝试获取服务器证书，即使握手可能失败
                try:
                    with context.wrap_socket(sock, server_hostname=host) as ssock:
                        cert = ssock.getpeercert(binary_form=True)
                        return cert is not None
                except ssl.SSLError:
                    # 即使握手失败，有时也能获取证书
                    return False

        except Exception:
            return False

    async def _parse_certificate_async(self, cert_data: bytes) -> Optional[SSLCertificateInfo]:
        """异步解析SSL证书信息"""
        try:
            # 使用现有的证书解析逻辑
            from .services import TLSService
            tls_service = TLSService()
            return tls_service._parse_certificate(cert_data)
        except Exception as e:
            logger.error(f"Certificate parsing failed: {str(e)}")
            return None

    def _extract_tls_timing(self, start_time: float) -> Dict[str, float]:
        """提取TLS握手的详细timing信息"""
        current_time = time.time()
        total_time = (current_time - start_time) * 1000

        timing = {
            "tcp_connect_ms": self.timing_data.get('tcp_connect_ms', 0.0),
            "tls_handshake_ms": self.timing_data.get('tls_handshake_ms', 0.0),
            "total_time_ms": total_time
        }

        # 计算证书验证时间（估算）
        if timing['tls_handshake_ms'] > 0:
            timing['certificate_verification_ms'] = max(0.0, timing['tls_handshake_ms'] * 0.1)
        else:
            timing['certificate_verification_ms'] = 0.0

        return timing

    async def _get_tls_negotiation_details(self, host: str, port: int) -> Dict[str, Any]:
        """获取TLS协商详情"""
        # 这里可以实现更复杂的TLS版本和密码套件检测
        # 目前返回基础信息
        return {
            "detection_method": "basic",
            "supported_protocols": ["检测中..."],
            "supported_cipher_suites": ["检测中..."],
            "note": "详细协商信息检测功能开发中"
        }

    async def _detect_security_features(self, host: str, port: int) -> Dict[str, Any]:
        """检测安全特性"""
        features = {
            "sni_support": True,  # 默认假设支持SNI
            "ocsp_stapling": False,  # 需要进一步检测
            "certificate_transparency": False,  # 需要进一步检测
            "hsts_preload": False,  # 需要HTTP头检测
            "detection_method": "basic"
        }

        # 可以在这里添加更详细的检测逻辑
        return features

    async def _handle_failed_connection(self, host: str, port: int, start_time: float) -> Optional[EnhancedTLSInfo]:
        """处理连接失败的情况，尝试获取部分信息"""
        handshake_time = (time.time() - start_time) * 1000

        # 尝试双向SSL检测
        mutual_tls_info = await self._test_client_cert_requirement(host, port)

        return EnhancedTLSInfo(
            protocol_version="Unknown",
            cipher_suite="Unknown",
            certificate=None,
            certificate_chain_length=0,
            is_secure=False,
            handshake_time_ms=handshake_time,
            tls_timing_breakdown={"total_time_ms": handshake_time},
            mutual_tls_info=mutual_tls_info,
            tls_negotiation_details={"status": "connection_failed"},
            security_features={"detection_failed": True}
        )

    async def _extract_info_from_failure(self, host: str, port: int, error_msg: str, handshake_time: float) -> Optional[EnhancedTLSInfo]:
        """从失败的连接中提取信息"""

        # 分析错误信息
        error_analysis = {
            "error_message": error_msg,
            "error_type": "unknown"
        }

        if "certificate" in error_msg.lower():
            error_analysis["error_type"] = "certificate_related"
        elif "timeout" in error_msg.lower():
            error_analysis["error_type"] = "timeout"
        elif "connection" in error_msg.lower():
            error_analysis["error_type"] = "connection_failed"

        return EnhancedTLSInfo(
            protocol_version="Unknown",
            cipher_suite="Unknown",
            certificate=None,
            certificate_chain_length=0,
            is_secure=False,
            handshake_time_ms=handshake_time,
            tls_timing_breakdown={"total_time_ms": handshake_time},
            mutual_tls_info=error_analysis,
            tls_negotiation_details={"status": "failed", "error": error_msg},
            security_features={"detection_failed": True}
        )
