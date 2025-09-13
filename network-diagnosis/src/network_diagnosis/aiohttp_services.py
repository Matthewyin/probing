"""
基于aiohttp的网络诊断服务模块
提供HTTP、TLS拨测的增强实现
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
    EnhancedHTTPResponseInfo, EnhancedTLSInfo,
    HTTPResponseInfo, TLSInfo, SSLCertificateInfo
)

logger = get_logger(__name__)


# AiohttpTCPService 已删除 - 使用 AsyncTCPService 替代


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

                # 4. TLS协商详情检测（根据配置启用）
                if settings.TLS_PROTOCOL_ENUMERATION or settings.TLS_CIPHER_DETECTION:
                    negotiation_details = await self._get_tls_negotiation_details(host, port)
                else:
                    negotiation_details = {
                        "detection_method": "disabled",
                        "supported_protocols": ["检测已禁用"],
                        "supported_cipher_suites": ["检测已禁用"],
                        "note": "TLS协商详情检测已在配置中禁用"
                    }

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
                        "confidence_level": 1.0,  # 新增：成功连接的高置信度
                        "detection_method": "successful_connection"
                    }

        except ssl.SSLError as e:
            # 分析SSL错误
            error_msg = str(e).lower()

            # 双向SSL指示器（扩展版）
            mutual_ssl_indicators = [
                "certificate required", "client certificate",
                "peer did not return a certificate", "certificate_required",
                "handshake failure", "certificate unknown",
                "unsafe_legacy_renegotiation_disabled",  # 新增：常见双向SSL错误
                "legacy renegotiation", "renegotiation",
                "certificate verify failed", "verify failed"
            ]

            # 检查是否为双向SSL指示器
            is_mutual_ssl_indicator = any(keyword in error_msg for keyword in mutual_ssl_indicators)

            if is_mutual_ssl_indicator:
                # 分析具体的双向SSL类型
                ssl_type, confidence = self._analyze_mutual_ssl_error(str(e))
                server_cert_available = await self._can_get_server_cert(host, port)

                return {
                    "requires_client_cert": True,
                    "connection_successful": False,
                    "ssl_type": ssl_type,
                    "confidence_level": confidence,  # 新增：置信度
                    "error_details": str(e),
                    "server_cert_available": server_cert_available,
                    "detection_method": "ssl_error_analysis",
                    "evidence": [  # 新增：证据链
                        f"SSL错误: {str(e)}",
                        f"错误模式匹配: {[kw for kw in mutual_ssl_indicators if kw in error_msg]}"
                    ]
                }
            else:
                # 其他SSL错误
                return {
                    "requires_client_cert": False,
                    "connection_successful": False,
                    "ssl_type": "SSL错误",
                    "confidence_level": 0.1,  # 新增：低置信度
                    "error_details": str(e),
                    "detection_method": "other_ssl_error"
                }

        except Exception as e:
            # 非SSL错误
            return {
                "requires_client_cert": False,
                "connection_successful": False,
                "ssl_type": "连接错误",
                "confidence_level": 0.0,
                "error_details": str(e),
                "detection_method": "connection_error"
            }

    def _analyze_mutual_ssl_error(self, error_msg: str) -> tuple[str, float]:
        """分析双向SSL错误类型和置信度"""
        error_lower = error_msg.lower()

        # 高置信度双向SSL指示器
        high_confidence_patterns = {
            "unsafe_legacy_renegotiation_disabled": ("双向SSL", 0.85),
            "certificate required": ("双向SSL", 0.95),
            "client certificate": ("双向SSL", 0.90),
            "certificate verify failed": ("双向SSL", 0.80)
        }

        # 中等置信度指示器
        medium_confidence_patterns = {
            "handshake failure": ("双向SSL", 0.70),
            "renegotiation": ("双向SSL", 0.65),
            "certificate unknown": ("双向SSL", 0.60)
        }

        # 检查高置信度模式
        for pattern, (ssl_type, confidence) in high_confidence_patterns.items():
            if pattern in error_lower:
                return ssl_type, confidence

        # 检查中等置信度模式
        for pattern, (ssl_type, confidence) in medium_confidence_patterns.items():
            if pattern in error_lower:
                return ssl_type, confidence

        # 默认：低置信度双向SSL
        return "可能的双向SSL", 0.50

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
        """获取TLS协商详情（真实检测）"""
        detection_start = time.time()

        try:
            # 根据配置选择性启用检测
            tasks = []

            if settings.TLS_PROTOCOL_ENUMERATION:
                protocols_task = self._detect_supported_protocols(host, port)
                tasks.append(protocols_task)
            else:
                protocols_task = None

            if settings.TLS_CIPHER_DETECTION:
                ciphers_task = self._detect_cipher_suites(host, port)
                tasks.append(ciphers_task)
            else:
                ciphers_task = None

            # 如果没有启用任何检测，返回基础信息
            if not tasks:
                return {
                    "detection_method": "disabled",
                    "supported_protocols": ["检测已禁用"],
                    "supported_cipher_suites": ["检测已禁用"],
                    "note": "所有TLS协商详情检测已在配置中禁用"
                }

            # 等待检测完成（使用配置的超时时间）
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=settings.TLS_DETECTION_TIMEOUT
            )

            # 解析结果
            protocols = results[0] if protocols_task else ["协议检测已禁用"]
            ciphers = results[1] if ciphers_task and len(results) > 1 else results[0] if ciphers_task and len(results) == 1 else ["加密套件检测已禁用"]

            # 处理检测结果
            supported_protocols = protocols if not isinstance(protocols, Exception) else []
            supported_ciphers = ciphers if not isinstance(ciphers, Exception) else []

            detection_time = (time.time() - detection_start) * 1000

            return {
                "detection_method": "active_probing",
                "supported_protocols": supported_protocols,
                "supported_cipher_suites": supported_ciphers,
                "detection_summary": {
                    "total_protocols_tested": 4,  # TLS 1.0, 1.1, 1.2, 1.3
                    "supported_protocols_count": len(supported_protocols),
                    "cipher_suites_detected": len(supported_ciphers),
                    "detection_time_ms": round(detection_time, 2)
                }
            }

        except asyncio.TimeoutError:
            return {
                "detection_method": "timeout",
                "supported_protocols": ["检测超时"],
                "supported_cipher_suites": ["检测超时"],
                "note": "协商详情检测超时，使用基础信息"
            }
        except Exception as e:
            logger.warning(f"TLS negotiation details detection failed: {e}")
            return {
                "detection_method": "failed",
                "supported_protocols": ["检测失败"],
                "supported_cipher_suites": ["检测失败"],
                "error": str(e)
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

    async def _detect_supported_protocols(self, host: str, port: int) -> List[str]:
        """检测服务器支持的TLS协议版本"""
        supported_protocols = []

        # 定义要测试的TLS版本
        tls_versions = [
            ("TLS 1.3", ssl.PROTOCOL_TLS_CLIENT, {"minimum_version": ssl.TLSVersion.TLSv1_3}),
            ("TLS 1.2", ssl.PROTOCOL_TLS_CLIENT, {"minimum_version": ssl.TLSVersion.TLSv1_2, "maximum_version": ssl.TLSVersion.TLSv1_2}),
            ("TLS 1.1", ssl.PROTOCOL_TLS_CLIENT, {"minimum_version": ssl.TLSVersion.TLSv1_1, "maximum_version": ssl.TLSVersion.TLSv1_1}),
            ("TLS 1.0", ssl.PROTOCOL_TLS_CLIENT, {"minimum_version": ssl.TLSVersion.TLSv1, "maximum_version": ssl.TLSVersion.TLSv1})
        ]

        for version_name, protocol, context_options in tls_versions:
            try:
                if await self._test_tls_version(host, port, context_options):
                    supported_protocols.append(version_name)
            except Exception as e:
                logger.debug(f"TLS version {version_name} test failed for {host}:{port}: {e}")
                continue

        return supported_protocols

    async def _test_tls_version(self, host: str, port: int, context_options: dict) -> bool:
        """测试特定TLS版本是否支持"""
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            # 设置TLS版本限制
            if "minimum_version" in context_options:
                context.minimum_version = context_options["minimum_version"]
            if "maximum_version" in context_options:
                context.maximum_version = context_options["maximum_version"]

            # 尝试连接
            with socket.create_connection((host, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    # 连接成功，该版本被支持
                    return True

        except Exception:
            return False

    async def _detect_cipher_suites(self, host: str, port: int) -> List[str]:
        """检测服务器支持的加密套件"""
        supported_ciphers = []

        # 常见的加密套件列表（按安全性排序）
        common_ciphers = [
            # TLS 1.3 套件
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_128_GCM_SHA256",

            # TLS 1.2 ECDHE 套件
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-RSA-CHACHA20-POLY1305",
            "ECDHE-RSA-AES256-SHA384",
            "ECDHE-RSA-AES128-SHA256",

            # TLS 1.2 其他套件
            "AES256-GCM-SHA384",
            "AES128-GCM-SHA256",
            "AES256-SHA256",
            "AES128-SHA256"
        ]

        # 测试每个加密套件
        for cipher in common_ciphers:
            try:
                if await self._test_cipher_suite(host, port, cipher):
                    supported_ciphers.append(cipher)

                # 限制检测数量，避免过长时间
                if len(supported_ciphers) >= 10:
                    break

            except Exception as e:
                logger.debug(f"Cipher {cipher} test failed for {host}:{port}: {e}")
                continue

        return supported_ciphers

    async def _test_cipher_suite(self, host: str, port: int, cipher: str) -> bool:
        """测试特定加密套件是否支持"""
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            # 设置特定的加密套件
            context.set_ciphers(cipher)

            # 尝试连接
            with socket.create_connection((host, port), timeout=3) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    # 检查实际使用的加密套件
                    actual_cipher = ssock.cipher()
                    if actual_cipher and actual_cipher[0] == cipher:
                        return True
                    return False

        except Exception:
            return False

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
