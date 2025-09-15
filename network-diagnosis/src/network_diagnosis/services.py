"""
网络诊断服务模块 - 核心功能实现
"""
import asyncio
import json
import platform
import re
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

import httpx
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

from .logger import get_logger
from .config import settings

logger = get_logger(__name__)

try:
    import dns.resolver
    import dns.exception
    import dns.rdatatype
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    logger.warning("dnspython not available, falling back to socket-based DNS resolution")

from .models import (
    DNSResolutionInfo, DNSResolutionStep, AuthoritativeQueryResult,
    TCPConnectionInfo, TLSInfo, SSLCertificateInfo,
    HTTPResponseInfo, NetworkPathInfo, TraceRouteHop,
    NetworkDiagnosisResult, DiagnosisRequest, PublicIPInfo, ICMPInfo
)


class DNSResolutionService:
    """DNS解析服务"""

    async def resolve_domain(self, domain: str) -> DNSResolutionInfo:
        """解析域名并收集详细信息"""
        start_time = time.time()

        try:
            # 检查是否已经是IP地址
            try:
                socket.inet_aton(domain)
                # 如果是IP地址，直接返回
                resolution_time = (time.time() - start_time) * 1000
                return DNSResolutionInfo(
                    domain=domain,
                    resolved_ips=[domain],
                    primary_ip=domain,
                    resolution_time_ms=resolution_time,
                    record_type="IP",
                    is_successful=True
                )
            except socket.error:
                pass  # 不是IP地址，继续DNS解析

            # 执行DNS解析
            loop = asyncio.get_event_loop()

            # 解析A记录（IPv4）
            try:
                ip_address = await loop.run_in_executor(None, socket.gethostbyname, domain)
                resolution_time = (time.time() - start_time) * 1000

                # 尝试获取所有IP地址
                try:
                    addr_info = await loop.run_in_executor(
                        None, socket.getaddrinfo, domain, None, socket.AF_INET
                    )
                    all_ips = list(set([addr[4][0] for addr in addr_info]))
                except Exception:
                    all_ips = [ip_address]

                # 尝试获取DNS服务器信息（从系统配置）
                dns_server = self._get_system_dns_server()

                logger.info(f"Resolved {domain} to {ip_address} in {resolution_time:.2f}ms")

                return DNSResolutionInfo(
                    domain=domain,
                    resolved_ips=all_ips,
                    primary_ip=ip_address,
                    resolution_time_ms=resolution_time,
                    dns_server=dns_server,
                    record_type="A",
                    is_successful=True
                )

            except socket.gaierror as e:
                resolution_time = (time.time() - start_time) * 1000
                error_msg = f"DNS resolution failed: {str(e)}"
                logger.warning(f"Failed to resolve domain {domain}: {error_msg}")

                return DNSResolutionInfo(
                    domain=domain,
                    resolution_time_ms=resolution_time,
                    is_successful=False,
                    error_message=error_msg
                )

        except Exception as e:
            resolution_time = (time.time() - start_time) * 1000
            error_msg = f"DNS resolution error: {str(e)}"
            logger.error(f"DNS resolution failed for {domain}: {error_msg}")

            return DNSResolutionInfo(
                domain=domain,
                resolution_time_ms=resolution_time,
                is_successful=False,
                error_message=error_msg
            )

    def _get_system_dns_server(self) -> Optional[str]:
        """获取系统DNS服务器地址"""
        try:
            # 在Linux/macOS上读取/etc/resolv.conf
            import platform
            if platform.system() in ['Linux', 'Darwin']:
                try:
                    with open('/etc/resolv.conf', 'r') as f:
                        for line in f:
                            if line.startswith('nameserver'):
                                return line.split()[1]
                except Exception:
                    pass

            # Windows或其他系统的默认DNS
            return None

        except Exception:
            return None


class EnhancedDNSResolutionService:
    """增强的DNS解析服务 - 支持CNAME解析、循环检测和权威DNS查询"""

    def __init__(self, max_cname_depth: int = 10):
        """
        初始化增强DNS解析服务

        Args:
            max_cname_depth: 最大CNAME解析深度，防止无限递归
        """
        self.max_cname_depth = max_cname_depth
        self.fallback_service = DNSResolutionService()  # 降级服务

    async def resolve_domain(self, domain: str) -> DNSResolutionInfo:
        """
        增强的域名解析，支持CNAME链路追踪和权威DNS查询

        Args:
            domain: 要解析的域名

        Returns:
            DNSResolutionInfo: 包含完整解析信息的结果
        """
        if not DNS_AVAILABLE:
            logger.warning("dnspython not available, using fallback DNS resolution")
            return await self.fallback_service.resolve_domain(domain)

        start_time = time.time()

        try:
            # 检查是否已经是IP地址
            try:
                socket.inet_aton(domain)
                # 如果是IP地址，直接返回
                resolution_time = (time.time() - start_time) * 1000
                return DNSResolutionInfo(
                    domain=domain,
                    resolved_ips=[domain],
                    primary_ip=domain,
                    resolution_time_ms=resolution_time,
                    is_successful=True,
                    record_type="IP",
                    resolution_steps=[
                        DNSResolutionStep(
                            record_name=domain,
                            record_type="IP",
                            record_value=domain,
                            ttl=None,
                            dns_server="N/A",
                            server_type="local"
                        )
                    ]
                )
            except socket.error:
                pass  # 不是IP地址，继续DNS解析

            # 1. 执行本地DNS解析（包含CNAME支持）
            local_result = await self._resolve_with_cname_support(domain)

            # 2. 发现并查询权威DNS服务器
            if local_result.is_successful:
                try:
                    auth_result = await self._query_authoritative_dns(domain)
                    if auth_result:
                        local_result.authoritative_result = auth_result
                except Exception as e:
                    logger.warning(f"Authoritative DNS query failed for {domain}: {e}")

            # 计算总解析时间
            total_time = (time.time() - start_time) * 1000
            local_result.resolution_time_ms = total_time

            return local_result

        except Exception as e:
            logger.error(f"Enhanced DNS resolution failed for {domain}: {str(e)}")
            # 降级到基础DNS解析
            return await self.fallback_service.resolve_domain(domain)

    async def _resolve_with_cname_support(self, domain: str) -> DNSResolutionInfo:
        """
        支持CNAME的DNS解析，包含循环检测

        Args:
            domain: 要解析的域名

        Returns:
            DNSResolutionInfo: 解析结果
        """
        resolution_steps = []
        visited_domains = set()  # 循环检测
        current_domain = domain
        depth = 0

        # 获取本地DNS服务器
        local_dns_server = self._get_local_dns_server()

        try:
            # CNAME解析循环
            while depth < self.max_cname_depth:
                depth += 1

                # 循环检测
                if current_domain in visited_domains:
                    logger.warning(f"CNAME loop detected for {domain} at {current_domain}")
                    break
                visited_domains.add(current_domain)

                # 查询CNAME记录
                cname_result = await self._query_cname_record(current_domain, local_dns_server)
                if cname_result:
                    # 记录CNAME步骤
                    resolution_steps.append(DNSResolutionStep(
                        record_name=current_domain,
                        record_type="CNAME",
                        record_value=cname_result['target'],
                        ttl=cname_result['ttl'],
                        dns_server=local_dns_server,
                        server_type="local"
                    ))
                    current_domain = cname_result['target']
                    continue

                # 没有CNAME，查询A记录
                a_results = await self._query_a_records(current_domain, local_dns_server)
                if a_results:
                    # 记录A记录步骤
                    for a_result in a_results:
                        resolution_steps.append(DNSResolutionStep(
                            record_name=current_domain,
                            record_type="A",
                            record_value=a_result['address'],
                            ttl=a_result['ttl'],
                            dns_server=local_dns_server,
                            server_type="local"
                        ))

                    # 收集所有IP地址
                    resolved_ips = [result['address'] for result in a_results]

                    return DNSResolutionInfo(
                        domain=domain,
                        resolved_ips=resolved_ips,
                        primary_ip=resolved_ips[0] if resolved_ips else None,
                        resolution_time_ms=0.0,  # 将在上层计算
                        is_successful=True,
                        local_dns_server=local_dns_server,
                        resolution_steps=resolution_steps,
                        # 兼容性字段
                        dns_server=local_dns_server,
                        record_type="A" if not any(step.record_type == "CNAME" for step in resolution_steps) else "CNAME",
                        ttl=a_results[0]['ttl'] if a_results else None
                    )

                # 没有A记录，结束循环
                break

            # 如果到这里，说明解析失败
            return DNSResolutionInfo(
                domain=domain,
                resolved_ips=[],
                primary_ip=None,
                resolution_time_ms=0.0,
                is_successful=False,
                error_message=f"Failed to resolve domain {domain}",
                local_dns_server=local_dns_server,
                resolution_steps=resolution_steps
            )

        except Exception as e:
            logger.error(f"CNAME resolution failed for {domain}: {str(e)}")
            return DNSResolutionInfo(
                domain=domain,
                resolved_ips=[],
                primary_ip=None,
                resolution_time_ms=0.0,
                is_successful=False,
                error_message=str(e),
                local_dns_server=local_dns_server,
                resolution_steps=resolution_steps
            )

    async def _query_cname_record(self, domain: str, dns_server: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        查询CNAME记录

        Args:
            domain: 要查询的域名
            dns_server: DNS服务器IP（可选）

        Returns:
            Dict包含target和ttl，如果没有CNAME记录则返回None
        """
        try:
            resolver = dns.resolver.Resolver()
            if dns_server:
                resolver.nameservers = [dns_server]

            # 查询CNAME记录
            response = resolver.resolve(domain, 'CNAME')
            if response:
                cname_record = response[0]
                return {
                    'target': str(cname_record.target).rstrip('.'),
                    'ttl': response.rrset.ttl
                }
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
            # 没有CNAME记录或查询失败
            pass
        except Exception as e:
            logger.debug(f"CNAME query failed for {domain}: {e}")

        return None

    async def _query_a_records(self, domain: str, dns_server: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        查询A记录

        Args:
            domain: 要查询的域名
            dns_server: DNS服务器IP（可选）

        Returns:
            List[Dict]: 包含address和ttl的字典列表
        """
        try:
            resolver = dns.resolver.Resolver()
            if dns_server:
                resolver.nameservers = [dns_server]

            # 查询A记录
            response = resolver.resolve(domain, 'A')
            results = []
            for record in response:
                results.append({
                    'address': str(record),
                    'ttl': response.rrset.ttl
                })
            return results
        except Exception as e:
            logger.debug(f"A record query failed for {domain}: {e}")
            return []

    def _get_local_dns_server(self) -> Optional[str]:
        """
        获取本地DNS服务器地址

        Returns:
            str: DNS服务器IP地址，如果无法获取则返回None
        """
        try:
            # 尝试从dnspython获取默认DNS服务器
            resolver = dns.resolver.Resolver()
            if resolver.nameservers:
                return resolver.nameservers[0]
        except Exception:
            pass

        # 降级到系统方法
        return self.fallback_service._get_system_dns_server()

    async def _query_authoritative_dns(self, domain: str) -> Optional[AuthoritativeQueryResult]:
        """
        查询权威DNS服务器

        Args:
            domain: 要查询的域名

        Returns:
            AuthoritativeQueryResult: 权威查询结果，如果失败则返回None
        """
        try:
            # 1. 发现权威DNS服务器
            auth_servers = await self._discover_authoritative_servers(domain)
            if not auth_servers:
                logger.debug(f"No authoritative servers found for {domain}")
                return None

            # 2. 向权威服务器查询
            for server_ip in auth_servers:
                try:
                    start_time = time.time()
                    auth_result = await self._resolve_with_cname_support_on_server(domain, server_ip)
                    query_time = (time.time() - start_time) * 1000

                    if auth_result.is_successful:
                        # 更新解析步骤的服务器类型
                        auth_steps = []
                        for step in auth_result.resolution_steps:
                            auth_step = DNSResolutionStep(
                                record_name=step.record_name,
                                record_type=step.record_type,
                                record_value=step.record_value,
                                ttl=step.ttl,
                                dns_server=server_ip,
                                server_type="authoritative"
                            )
                            auth_steps.append(auth_step)

                        return AuthoritativeQueryResult(
                            queried_server=server_ip,
                            query_time_ms=query_time,
                            resolution_steps=auth_steps
                        )
                except Exception as e:
                    logger.debug(f"Authoritative query failed on {server_ip}: {e}")
                    continue

            logger.debug(f"All authoritative servers failed for {domain}")
            return None

        except Exception as e:
            logger.debug(f"Authoritative DNS discovery failed for {domain}: {e}")
            return None

    async def _discover_authoritative_servers(self, domain: str) -> List[str]:
        """
        发现域名的权威DNS服务器

        Args:
            domain: 要查询的域名

        Returns:
            List[str]: 权威DNS服务器IP地址列表
        """
        try:
            # 域名层级分解
            domain_hierarchy = self._decompose_domain(domain)

            for zone_domain in domain_hierarchy:
                try:
                    # 查询NS记录
                    resolver = dns.resolver.Resolver()
                    response = resolver.resolve(zone_domain, 'NS')

                    auth_servers = []
                    for ns_record in response:
                        ns_hostname = str(ns_record.target).rstrip('.')
                        # 解析NS服务器的IP地址
                        try:
                            ns_ips = await self._query_a_records(ns_hostname)
                            for ip_info in ns_ips:
                                auth_servers.append(ip_info['address'])
                        except Exception:
                            continue

                    if auth_servers:
                        return auth_servers[:3]  # 最多返回3个权威服务器

                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
                    continue
                except Exception as e:
                    logger.debug(f"NS query failed for {zone_domain}: {e}")
                    continue

            return []

        except Exception as e:
            logger.debug(f"Authoritative server discovery failed: {e}")
            return []

    def _decompose_domain(self, domain: str) -> List[str]:
        """
        将域名分解为层级列表

        Args:
            domain: 输入域名

        Returns:
            List[str]: 域名层级列表，从具体到抽象
        """
        parts = domain.rstrip('.').split('.')
        domains = []

        # 从完整域名开始，逐级向上
        for i in range(len(parts)):
            subdomain = '.'.join(parts[i:])
            domains.append(subdomain)

        return domains

    async def _resolve_with_cname_support_on_server(self, domain: str, dns_server: str) -> DNSResolutionInfo:
        """
        在指定DNS服务器上进行CNAME解析

        Args:
            domain: 要解析的域名
            dns_server: DNS服务器IP

        Returns:
            DNSResolutionInfo: 解析结果
        """
        resolution_steps = []
        visited_domains = set()
        current_domain = domain
        depth = 0

        try:
            # CNAME解析循环
            while depth < self.max_cname_depth:
                depth += 1

                # 循环检测
                if current_domain in visited_domains:
                    break
                visited_domains.add(current_domain)

                # 查询CNAME记录
                cname_result = await self._query_cname_record(current_domain, dns_server)
                if cname_result:
                    resolution_steps.append(DNSResolutionStep(
                        record_name=current_domain,
                        record_type="CNAME",
                        record_value=cname_result['target'],
                        ttl=cname_result['ttl'],
                        dns_server=dns_server,
                        server_type="authoritative"
                    ))
                    current_domain = cname_result['target']
                    continue

                # 查询A记录
                a_results = await self._query_a_records(current_domain, dns_server)
                if a_results:
                    for a_result in a_results:
                        resolution_steps.append(DNSResolutionStep(
                            record_name=current_domain,
                            record_type="A",
                            record_value=a_result['address'],
                            ttl=a_result['ttl'],
                            dns_server=dns_server,
                            server_type="authoritative"
                        ))

                    resolved_ips = [result['address'] for result in a_results]

                    return DNSResolutionInfo(
                        domain=domain,
                        resolved_ips=resolved_ips,
                        primary_ip=resolved_ips[0] if resolved_ips else None,
                        resolution_time_ms=0.0,
                        is_successful=True,
                        local_dns_server=dns_server,
                        resolution_steps=resolution_steps
                    )

                break

            # 解析失败
            return DNSResolutionInfo(
                domain=domain,
                resolved_ips=[],
                primary_ip=None,
                resolution_time_ms=0.0,
                is_successful=False,
                error_message=f"Failed to resolve {domain} on {dns_server}",
                local_dns_server=dns_server,
                resolution_steps=resolution_steps
            )

        except Exception as e:
            return DNSResolutionInfo(
                domain=domain,
                resolved_ips=[],
                primary_ip=None,
                resolution_time_ms=0.0,
                is_successful=False,
                error_message=str(e),
                local_dns_server=dns_server,
                resolution_steps=resolution_steps
            )


class TCPConnectionService:
    """TCP连接测试服务"""
    
    async def test_connection(self, host: str, port: int, target_ip: str) -> TCPConnectionInfo:
        """测试TCP连接"""
        start_time = time.time()

        try:
            # 创建socket连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(settings.CONNECT_TIMEOUT)

            # 连接到目标IP
            result = sock.connect_ex((target_ip, port))
            connect_time = (time.time() - start_time) * 1000  # 转换为毫秒

            local_address = None
            local_port = None
            socket_family = "IPv4"

            if result == 0:
                # 获取本地连接信息
                try:
                    local_addr = sock.getsockname()
                    local_address = local_addr[0]
                    local_port = local_addr[1]

                    # 确定socket家族
                    if sock.family == socket.AF_INET6:
                        socket_family = "IPv6"
                    else:
                        socket_family = "IPv4"

                except Exception:
                    pass

                sock.close()

                logger.info(f"TCP connection to {host}:{port} ({target_ip}) successful in {connect_time:.2f}ms")
                return TCPConnectionInfo(
                    host=host,
                    port=port,
                    target_ip=target_ip,
                    connect_time_ms=connect_time,
                    is_connected=True,
                    socket_family=socket_family,
                    local_address=local_address,
                    local_port=local_port
                )
            else:
                sock.close()
                error_msg = f"Connection failed with error code: {result}"
                logger.warning(f"TCP connection to {host}:{port} ({target_ip}) failed: {error_msg}")
                return TCPConnectionInfo(
                    host=host,
                    port=port,
                    target_ip=target_ip,
                    connect_time_ms=connect_time,
                    is_connected=False,
                    socket_family=socket_family,
                    error_message=error_msg
                )

        except Exception as e:
            connect_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"TCP connection to {host}:{port} ({target_ip}) failed: {error_msg}")

            return TCPConnectionInfo(
                host=host,
                port=port,
                target_ip=target_ip,
                connect_time_ms=connect_time,
                is_connected=False,
                socket_family="IPv4",
                error_message=error_msg
            )


class TLSService:
    """TLS/SSL信息收集服务"""
    
    async def get_tls_info(self, host: str, port: int) -> Optional[TLSInfo]:
        """获取TLS/SSL连接信息"""
        start_time = time.time()
        
        try:
            # 创建SSL上下文
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE  # 暂时禁用证书验证

            # 建立SSL连接
            with socket.create_connection((host, port), timeout=settings.CONNECT_TIMEOUT) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    handshake_time = (time.time() - start_time) * 1000
                    
                    # 获取SSL信息
                    cipher = ssock.cipher()
                    protocol_version = ssock.version()
                    peer_cert = ssock.getpeercert(binary_form=True)
                    
                    # 解析证书
                    cert_info = None
                    if peer_cert:
                        cert_info = self._parse_certificate(peer_cert)
                    
                    logger.info(f"TLS handshake completed in {handshake_time:.2f}ms")
                    
                    return TLSInfo(
                        protocol_version=protocol_version or "Unknown",
                        cipher_suite=cipher[0] if cipher else "Unknown",
                        certificate=cert_info,
                        certificate_chain_length=1 if peer_cert else 0,
                        is_secure=True,
                        handshake_time_ms=handshake_time
                    )
                    
        except Exception as e:
            handshake_time = (time.time() - start_time) * 1000
            logger.error(f"TLS connection failed: {str(e)}")
            return TLSInfo(
                protocol_version="Unknown",
                cipher_suite="Unknown",
                certificate=None,
                certificate_chain_length=0,
                is_secure=False,
                handshake_time_ms=handshake_time
            )
    
    def _parse_certificate(self, cert_data: bytes) -> Optional[SSLCertificateInfo]:
        """解析SSL证书信息"""
        try:
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
            
            # 提取证书信息
            subject = {attr.oid._name: attr.value for attr in cert.subject}
            issuer = {attr.oid._name: attr.value for attr in cert.issuer}
            
            # 计算到期时间
            now = datetime.now(timezone.utc)
            not_after = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after.replace(tzinfo=timezone.utc)
            days_until_expiry = (not_after - now).days
            
            # 获取公钥信息
            public_key = cert.public_key()
            public_key_size = None
            public_key_algorithm = "Unknown"
            
            if hasattr(public_key, 'key_size'):
                public_key_size = public_key.key_size
                public_key_algorithm = type(public_key).__name__
            
            return SSLCertificateInfo(
                subject=subject,
                issuer=issuer,
                version=cert.version.value,
                serial_number=str(cert.serial_number),
                not_before=cert.not_valid_before_utc if hasattr(cert, 'not_valid_before_utc') else cert.not_valid_before.replace(tzinfo=timezone.utc),
                not_after=not_after,
                signature_algorithm=cert.signature_algorithm_oid._name,
                public_key_algorithm=public_key_algorithm,
                public_key_size=public_key_size,
                fingerprint_sha256=cert.fingerprint(hashes.SHA256()).hex(),
                is_expired=now > not_after,
                days_until_expiry=days_until_expiry
            )
            
        except Exception as e:
            logger.error(f"Certificate parsing failed: {str(e)}")
            return None


class HTTPService:
    """HTTP响应信息收集服务"""

    async def get_http_info(self, url: str) -> Optional[HTTPResponseInfo]:
        """获取HTTP响应信息"""
        start_time = time.time()

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=settings.CONNECT_TIMEOUT,
                    read=settings.READ_TIMEOUT,
                    write=settings.CONNECT_TIMEOUT,
                    pool=settings.READ_TIMEOUT
                ),
                follow_redirects=True,
                max_redirects=settings.MAX_REDIRECTS,
                verify=False  # 暂时禁用SSL验证以避免证书问题
            ) as client:
                response = await client.get(url)
                response_time = (time.time() - start_time) * 1000

                # 计算重定向次数
                redirect_count = len(response.history)

                logger.info(f"HTTP request completed in {response_time:.2f}ms with status {response.status_code}")

                return HTTPResponseInfo(
                    status_code=response.status_code,
                    reason_phrase=response.reason_phrase,
                    headers=dict(response.headers),
                    response_time_ms=response_time,
                    content_length=len(response.content) if response.content else None,
                    content_type=response.headers.get('content-type'),
                    server=response.headers.get('server'),
                    redirect_count=redirect_count,
                    final_url=str(response.url)
                )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"HTTP request failed: {str(e)}")
            return None


class NetworkPathService:
    """网络路径追踪服务"""

    async def trace_path(self, host: str) -> Optional[NetworkPathInfo]:
        """执行网络路径追踪"""
        logger.info(f"Starting network path trace to {host}")

        # 首先尝试使用mtr（无需密码，通过sudoers配置）
        result = await self._trace_with_mtr(host)
        if result:
            return result

        # 如果mtr失败或不可用，使用traceroute
        return await self._trace_with_traceroute(host)

    async def _trace_with_mtr(self, host: str) -> Optional[NetworkPathInfo]:
        """使用mtr进行路径追踪"""
        try:
            # 构建mtr命令 - 使用完整路径
            cmd = ['sudo', 'mtr', '-rwc', '5', '-f', '1', '-n', '-i', '1', '-4', '-z', '--json', host]
            logger.info(f"Executing mtr command: {' '.join(cmd)}")

            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # 等待命令完成（无需密码输入），设置超时
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=300.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"mtr command timed out for {host}")
                process.kill()
                return None

            logger.info(f"mtr command completed with return code: {process.returncode}")

            if process.returncode == 0:
                # 解析mtr JSON输出
                stdout_str = stdout.decode()
                logger.debug(f"mtr output length: {len(stdout_str)} characters")
                mtr_data = json.loads(stdout_str)
                return self._parse_mtr_output(mtr_data, host)
            else:
                stderr_str = stderr.decode()
                logger.warning(f"mtr failed with return code {process.returncode}: {stderr_str}")
                return None

        except Exception as e:
            logger.error(f"mtr execution failed: {str(e)}")
            return None

    async def _trace_with_traceroute(self, host: str) -> Optional[NetworkPathInfo]:
        """使用traceroute进行路径追踪"""
        try:
            # 构建traceroute命令
            cmd = ['traceroute', '-n', '-m', '30', '-w', '2', host]

            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # 解析traceroute输出
                return self._parse_traceroute_output(stdout.decode(), host)
            else:
                logger.warning(f"traceroute failed: {stderr.decode()}")
                return None

        except Exception as e:
            logger.error(f"traceroute execution failed: {str(e)}")
            return None

    def _parse_mtr_output(self, mtr_data: Dict[str, Any], host: str) -> NetworkPathInfo:
        """解析mtr JSON输出"""
        hops = []
        target_ip = None

        for hop_data in mtr_data.get('report', {}).get('hubs', []):
            # 跳过无响应的跳点（host为"???"）
            if hop_data.get('host') == '???':
                continue

            # 收集响应时间数据（包含更详细的统计）
            response_times = []
            if hop_data.get('Best', 0) > 0:
                response_times.append(hop_data.get('Best', 0.0))
            if hop_data.get('Avg', 0) > 0:
                response_times.append(hop_data.get('Avg', 0.0))
            if hop_data.get('Wrst', 0) > 0:
                response_times.append(hop_data.get('Wrst', 0.0))

            # 如果没有有效的响应时间，使用平均值
            if not response_times:
                response_times = [hop_data.get('Avg', 0.0)]

            hop = TraceRouteHop(
                hop_number=hop_data.get('count', 0),
                ip_address=hop_data.get('host'),
                response_times_ms=response_times,
                avg_response_time_ms=hop_data.get('Avg', 0.0),
                packet_loss_percent=hop_data.get('Loss%', 0.0),
                # 新增字段
                asn=hop_data.get('ASN'),
                packets_sent=hop_data.get('Snt', 0),
                best_time_ms=hop_data.get('Best', 0.0),
                worst_time_ms=hop_data.get('Wrst', 0.0),
                std_dev_ms=hop_data.get('StDev', 0.0)
            )
            hops.append(hop)

            # 最后一跳通常是目标IP
            if hop_data.get('Loss%', 100) < 100:  # 有响应的跳点
                target_ip = hop_data.get('host')

        # 计算总体统计（只计算有响应的跳点）
        valid_hops = [hop for hop in hops if hop.avg_response_time_ms > 0]
        avg_latency = sum(hop.avg_response_time_ms for hop in valid_hops) / len(valid_hops) if valid_hops else None
        total_loss = sum(hop.packet_loss_percent for hop in hops) / len(hops) if hops else 0

        return NetworkPathInfo(
            target_host=host,
            target_ip=target_ip,  # 使用最后一个有响应的跳点作为目标IP
            trace_method="mtr",
            hops=hops,
            total_hops=len(hops),
            avg_latency_ms=avg_latency,
            packet_loss_percent=total_loss
        )

    def _parse_traceroute_output(self, output: str, host: str) -> NetworkPathInfo:
        """解析traceroute文本输出"""
        lines = output.strip().split('\n')
        hops = []

        for line in lines[1:]:  # 跳过第一行标题
            if not line.strip():
                continue

            parts = line.strip().split()
            if len(parts) < 2:
                continue

            try:
                hop_number = int(parts[0])
                ip_address = parts[1] if parts[1] != '*' else None

                # 提取响应时间
                response_times = []
                for part in parts[2:]:
                    if part.endswith('ms'):
                        try:
                            response_times.append(float(part[:-2]))
                        except ValueError:
                            continue

                avg_time = sum(response_times) / len(response_times) if response_times else None

                hop = TraceRouteHop(
                    hop_number=hop_number,
                    ip_address=ip_address,
                    response_times_ms=response_times,
                    avg_response_time_ms=avg_time,
                    packet_loss_percent=0.0  # traceroute不提供丢包率
                )
                hops.append(hop)

            except (ValueError, IndexError):
                continue

        # 计算总体统计
        avg_latency = sum(hop.avg_response_time_ms or 0 for hop in hops) / len(hops) if hops else None

        return NetworkPathInfo(
            target_host=host,
            trace_method="traceroute",
            hops=hops,
            total_hops=len(hops),
            avg_latency_ms=avg_latency,
            packet_loss_percent=0.0
        )


class PublicIPService:
    """公网IP获取服务"""

    def __init__(self):
        self.timeout = 3.0  # 3秒超时

    async def get_public_ip_info(self) -> Optional[PublicIPInfo]:
        """获取公网IP信息，多服务容错"""
        services = [
            ("百度智能云", self._get_from_baidu),
            ("IPIP.NET", self._get_from_ipip),
            ("VORE API", self._get_from_vore)
        ]

        for service_name, service_func in services:
            try:
                start_time = time.time()
                result = await service_func()
                query_time = (time.time() - start_time) * 1000

                if result:
                    result.service_provider = service_name
                    result.query_time_ms = query_time
                    logger.info(f"Successfully got public IP info from {service_name}: {result.ip}")
                    return result

            except Exception as e:
                logger.warning(f"Failed to get IP info from {service_name}: {e}")
                continue

        logger.warning("All public IP services failed")
        return None

    async def _get_from_baidu(self) -> Optional[PublicIPInfo]:
        """从百度智能云获取公网IP信息"""
        url = "https://qifu-api.baidubce.com/ip/local/geo/v1/district"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == "Success" and "data" in data:
                ip_data = data["data"]
                return PublicIPInfo(
                    ip=data.get("ip", ""),
                    country=ip_data.get("country"),
                    province=ip_data.get("prov"),
                    city=ip_data.get("city"),
                    district=ip_data.get("district"),
                    isp=ip_data.get("isp"),
                    continent=ip_data.get("continent"),
                    zipcode=ip_data.get("zipcode"),
                    adcode=ip_data.get("adcode")
                )
        return None

    async def _get_from_ipip(self) -> Optional[PublicIPInfo]:
        """从IPIP.NET获取公网IP信息"""
        url = "https://myip.ipip.net/json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("ret") == "ok" and "data" in data:
                ip_data = data["data"]
                location = ip_data.get("location", [])

                return PublicIPInfo(
                    ip=ip_data.get("ip", ""),
                    country=location[0] if len(location) > 0 else None,
                    province=location[1] if len(location) > 1 else None,
                    city=location[2] if len(location) > 2 else None,
                    isp=location[4] if len(location) > 4 else None
                )
        return None

    async def _get_from_vore(self) -> Optional[PublicIPInfo]:
        """从VORE API获取公网IP信息"""
        url = "https://api.vore.top/api/IPdata?ip="

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200 and "ipdata" in data:
                ip_info = data.get("ipinfo", {})
                ip_data = data.get("ipdata", {})

                return PublicIPInfo(
                    ip=ip_info.get("text", ""),
                    country=ip_data.get("info1"),
                    province=ip_data.get("info2"),
                    city=ip_data.get("info3"),
                    isp=ip_data.get("isp")
                )
        return None


class ICMPService:
    """ICMP探测服务"""

    def __init__(self, packet_count: int = 5, packet_size: int = 64, timeout: int = 3000):
        """
        初始化ICMP服务

        Args:
            packet_count: 发送的数据包数量
            packet_size: 数据包大小（字节）
            timeout: 超时时间（毫秒）
        """
        self.packet_count = packet_count
        self.packet_size = packet_size
        self.timeout_ms = timeout

    async def ping(self, host: str) -> Optional[ICMPInfo]:
        """执行ICMP探测"""
        logger.info(f"Starting ICMP ping to {host}")
        start_time = time.time()

        try:
            # 构建ping命令（跨平台兼容）
            ping_cmd = self._build_ping_command(host)
            logger.info(f"Executing ping command: {' '.join(ping_cmd)}")

            # 执行ping命令
            process = await asyncio.create_subprocess_exec(
                *ping_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # 等待命令完成，设置超时
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_ms / 1000 + 15  # 额外5秒缓冲
                )
            except asyncio.TimeoutError:
                logger.warning(f"Ping command timed out for {host}")
                process.kill()
                return self._create_timeout_result(host, ping_cmd)

            execution_time = (time.time() - start_time) * 1000

            if process.returncode == 0:
                # 解析ping输出
                stdout_str = stdout.decode('utf-8', errors='ignore')
                return self._parse_ping_output(stdout_str, host, ping_cmd, execution_time)
            else:
                # ping失败
                stderr_str = stderr.decode('utf-8', errors='ignore')
                logger.warning(f"Ping failed for {host}: {stderr_str}")
                return self._create_error_result(host, ping_cmd, execution_time, stderr_str)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"ICMP ping execution failed for {host}: {str(e)}")
            return self._create_error_result(host, [], execution_time, str(e))

    def _build_ping_command(self, host: str) -> List[str]:
        """构建跨平台的ping命令"""
        import platform

        system = platform.system().lower()

        if system == "windows":
            # Windows ping命令
            cmd = [
                "ping",
                "-n", str(self.packet_count),  # 发送包数量
                "-l", str(self.packet_size),   # 数据包大小
                "-w", str(self.timeout_ms),    # 超时时间（毫秒）
                host
            ]
        else:
            # Linux/macOS ping命令
            timeout_sec = max(1, self.timeout_ms // 1000)  # 转换为秒，最少1秒
            cmd = [
                "ping",
                "-c", str(self.packet_count),  # 发送包数量
                "-s", str(self.packet_size),   # 数据包大小
                "-W", str(timeout_sec),        # 超时时间（秒）
                "-i", "1",                   # 包间隔1秒
                host
            ]

        return cmd

    def _parse_ping_output(self, output: str, host: str, ping_cmd: List[str], execution_time: float) -> ICMPInfo:
        """解析ping命令输出"""
        import platform
        import re

        system = platform.system().lower()

        try:
            if system == "windows":
                return self._parse_windows_ping(output, host, ping_cmd, execution_time)
            else:
                return self._parse_unix_ping(output, host, ping_cmd, execution_time)
        except Exception as e:
            logger.error(f"Failed to parse ping output: {str(e)}")
            return self._create_error_result(host, ping_cmd, execution_time, f"Parse error: {str(e)}")

    def _parse_windows_ping(self, output: str, host: str, ping_cmd: List[str], execution_time: float) -> ICMPInfo:
        """解析Windows ping输出"""
        lines = output.strip().split('\n')

        # 提取目标IP
        target_ip = host
        ip_match = re.search(r'Pinging .+ \[([^\]]+)\]', output)
        if ip_match:
            target_ip = ip_match.group(1)

        # 提取统计信息
        packets_sent = 0
        packets_received = 0
        packet_loss = 100.0

        # 查找统计行，例如: "Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)"
        stats_match = re.search(r'Packets: Sent = (\d+), Received = (\d+), Lost = \d+ \((\d+)% loss\)', output)
        if stats_match:
            packets_sent = int(stats_match.group(1))
            packets_received = int(stats_match.group(2))
            packet_loss = float(stats_match.group(3))

        # 提取RTT统计，例如: "Minimum = 1ms, Maximum = 4ms, Average = 2ms"
        min_rtt = max_rtt = avg_rtt = None
        rtt_match = re.search(r'Minimum = (\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms', output)
        if rtt_match:
            min_rtt = float(rtt_match.group(1))
            max_rtt = float(rtt_match.group(2))
            avg_rtt = float(rtt_match.group(3))

        return ICMPInfo(
            target_host=host,
            target_ip=target_ip,
            packets_sent=packets_sent,
            packets_received=packets_received,
            packet_loss_percent=packet_loss,
            min_rtt_ms=min_rtt,
            max_rtt_ms=max_rtt,
            avg_rtt_ms=avg_rtt,
            std_dev_rtt_ms=None,  # Windows ping不提供标准差
            packet_size=self.packet_size,
            timeout_ms=self.timeout_ms,
            ping_command=' '.join(ping_cmd),
            execution_time_ms=execution_time,
            is_successful=packets_received > 0,
            error_message=None if packets_received > 0 else "No packets received"
        )

    def _parse_unix_ping(self, output: str, host: str, ping_cmd: List[str], execution_time: float) -> ICMPInfo:
        """解析Unix/Linux/macOS ping输出"""
        lines = output.strip().split('\n')

        # 提取目标IP
        target_ip = host
        ip_match = re.search(r'PING .+ \(([^)]+)\)', output)
        if ip_match:
            target_ip = ip_match.group(1)

        # 提取统计信息，支持多种格式
        # Linux: "4 packets transmitted, 4 received, 0% packet loss"
        # macOS: "4 packets transmitted, 4 packets received, 0.0% packet loss"
        packets_sent = 0
        packets_received = 0
        packet_loss = 100.0

        # 尝试匹配不同的统计格式
        stats_patterns = [
            r'(\d+) packets transmitted, (\d+) packets received, (\d+(?:\.\d+)?)% packet loss',  # macOS
            r'(\d+) packets transmitted, (\d+) received, (\d+(?:\.\d+)?)% packet loss',         # Linux
        ]

        for pattern in stats_patterns:
            stats_match = re.search(pattern, output)
            if stats_match:
                packets_sent = int(stats_match.group(1))
                packets_received = int(stats_match.group(2))
                packet_loss = float(stats_match.group(3))
                break

        # 提取RTT统计，支持不同系统格式
        # macOS: "round-trip min/avg/max/stddev = 1.234/2.345/3.456/0.123 ms"
        # Linux: "rtt min/avg/max/mdev = 1.234/2.345/3.456/0.123 ms"
        min_rtt = max_rtt = avg_rtt = std_dev = None
        rtt_patterns = [
            r'round-trip min/avg/max/stddev = ([^/]+)/([^/]+)/([^/]+)/([^\s]+) ms',  # macOS
            r'rtt min/avg/max/mdev = ([^/]+)/([^/]+)/([^/]+)/([^\s]+) ms',          # Linux
        ]

        for pattern in rtt_patterns:
            rtt_match = re.search(pattern, output)
            if rtt_match:
                min_rtt = float(rtt_match.group(1))
                avg_rtt = float(rtt_match.group(2))
                max_rtt = float(rtt_match.group(3))
                std_dev = float(rtt_match.group(4))
                break

        return ICMPInfo(
            target_host=host,
            target_ip=target_ip,
            packets_sent=packets_sent,
            packets_received=packets_received,
            packet_loss_percent=packet_loss,
            min_rtt_ms=min_rtt,
            max_rtt_ms=max_rtt,
            avg_rtt_ms=avg_rtt,
            std_dev_rtt_ms=std_dev,
            packet_size=self.packet_size,
            timeout_ms=self.timeout_ms,
            ping_command=' '.join(ping_cmd),
            execution_time_ms=execution_time,
            is_successful=packets_received > 0,
            error_message=None if packets_received > 0 else "No packets received"
        )

    def _create_timeout_result(self, host: str, ping_cmd: List[str]) -> ICMPInfo:
        """创建超时结果"""
        return ICMPInfo(
            target_host=host,
            target_ip=host,
            packets_sent=self.packet_count,
            packets_received=0,
            packet_loss_percent=100.0,
            min_rtt_ms=None,
            max_rtt_ms=None,
            avg_rtt_ms=None,
            std_dev_rtt_ms=None,
            packet_size=self.packet_size,
            timeout_ms=self.timeout_ms,
            ping_command=' '.join(ping_cmd),
            execution_time_ms=self.timeout_ms,
            is_successful=False,
            error_message="Ping command timed out"
        )

    def _create_error_result(self, host: str, ping_cmd: List[str], execution_time: float, error_msg: str) -> ICMPInfo:
        """创建错误结果"""
        return ICMPInfo(
            target_host=host,
            target_ip=host,
            packets_sent=0,
            packets_received=0,
            packet_loss_percent=100.0,
            min_rtt_ms=None,
            max_rtt_ms=None,
            avg_rtt_ms=None,
            std_dev_rtt_ms=None,
            packet_size=self.packet_size,
            timeout_ms=self.timeout_ms,
            ping_command=' '.join(ping_cmd) if ping_cmd else "ping (failed to build command)",
            execution_time_ms=execution_time,
            is_successful=False,
            error_message=error_msg
        )
