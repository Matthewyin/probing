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
from .process_manager import managed_subprocess

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

    async def test_multiple_connections(self, domain: str, port: int, ip_list: List[str]) -> "MultiIPTCPInfo":
        """
        对多个IP地址进行TCP连接测试

        Args:
            domain: 目标域名
            port: 目标端口
            ip_list: 要测试的IP地址列表

        Returns:
            MultiIPTCPInfo: 多IP TCP连接测试结果
        """
        from .models import MultiIPTCPInfo, TCPSummary

        start_time = time.time()
        logger.info(f"Starting multi-IP TCP connection test to {domain}:{port} with {len(ip_list)} IPs: {ip_list}")

        # 并发执行所有IP的TCP连接测试
        tasks = []
        for ip in ip_list:
            task = self.test_connection_to_ip(domain, port, ip)
            tasks.append(task)

        # 等待所有测试完成
        tcp_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        results_dict = {}
        successful_connections = 0
        failed_connections = 0
        connection_times = []

        for i, result in enumerate(tcp_results):
            ip = ip_list[i]

            if isinstance(result, Exception):
                # 处理异常情况
                logger.error(f"TCP test to {ip} failed with exception: {result}")
                results_dict[ip] = None
                failed_connections += 1
            else:
                results_dict[ip] = result
                if result.is_connected:
                    successful_connections += 1
                    connection_times.append((ip, result.connect_time_ms))
                else:
                    failed_connections += 1

        # 计算汇总统计
        summary = self._create_tcp_summary(
            ip_list, successful_connections, failed_connections, connection_times
        )

        total_time = (time.time() - start_time) * 1000

        logger.info(f"Multi-IP TCP test completed: {successful_connections}/{len(ip_list)} successful connections")

        return MultiIPTCPInfo(
            target_domain=domain,
            target_port=port,
            tested_ips=ip_list,
            tcp_results=results_dict,
            summary=summary,
            total_execution_time_ms=total_time,
            concurrent_execution=True
        )

    async def test_connection_to_ip(self, domain: str, port: int, ip: str) -> "TCPConnectionInfo":
        """
        对单个IP进行TCP连接测试（内部方法）

        Args:
            domain: 域名
            port: 端口
            ip: IP地址

        Returns:
            TCPConnectionInfo: TCP连接结果
        """
        try:
            return await self.test_connection(domain, port, ip)
        except Exception as e:
            logger.error(f"TCP connection test to {ip} failed: {e}")
            from .models import TCPConnectionInfo
            return TCPConnectionInfo(
                host=domain,
                port=port,
                target_ip=ip,
                connect_time_ms=0.0,
                is_connected=False,
                socket_family="IPv4",
                error_message=str(e)
            )

    def _create_tcp_summary(self, ip_list: List[str], successful: int, failed: int,
                           connection_times: List[tuple]) -> "TCPSummary":
        """
        创建TCP连接汇总统计

        Args:
            ip_list: IP列表
            successful: 成功连接数
            failed: 失败连接数
            connection_times: 连接时间列表 [(ip, time_ms), ...]

        Returns:
            TCPSummary: TCP汇总统计
        """
        from .models import TCPSummary

        total_ips = len(ip_list)
        success_rate = (successful / total_ips) * 100 if total_ips > 0 else 0.0

        # 性能统计
        fastest_ip = None
        fastest_time = None
        slowest_ip = None
        slowest_time = None
        average_time = None

        if connection_times:
            # 按连接时间排序
            sorted_times = sorted(connection_times, key=lambda x: x[1])

            fastest_ip, fastest_time = sorted_times[0]
            slowest_ip, slowest_time = sorted_times[-1]

            # 计算平均时间
            total_time = sum(time for _, time in connection_times)
            average_time = total_time / len(connection_times)

        # 推荐IP（选择最快的连接IP）
        recommended_ip = fastest_ip
        recommendation_reason = None
        if recommended_ip:
            recommendation_reason = f"连接时间最短 ({fastest_time:.2f}ms)"
        elif successful > 0:
            # 如果没有连接时间数据但有成功连接，推荐第一个成功的
            for ip in ip_list:
                # 这里需要从结果中找到第一个成功的IP
                # 简化处理，推荐第一个IP
                recommended_ip = ip_list[0]
                recommendation_reason = "首个可用连接"
                break

        return TCPSummary(
            total_ips=total_ips,
            successful_connections=successful,
            failed_connections=failed,
            success_rate=success_rate,
            fastest_connection_ip=fastest_ip,
            fastest_connection_time_ms=fastest_time,
            slowest_connection_ip=slowest_ip,
            slowest_connection_time_ms=slowest_time,
            average_connection_time_ms=average_time,
            recommended_ip=recommended_ip,
            recommendation_reason=recommendation_reason
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

                # 解析HTTP头信息
                headers_dict = dict(response.headers)
                origin_info = self._parse_origin_info(headers_dict)
                header_analysis = self._analyze_headers(headers_dict)

                return HTTPResponseInfo(
                    status_code=response.status_code,
                    reason_phrase=response.reason_phrase,
                    headers=headers_dict,
                    response_time_ms=response_time,
                    content_length=len(response.content) if response.content else None,
                    content_type=response.headers.get('content-type'),
                    server=response.headers.get('server'),
                    redirect_count=redirect_count,
                    final_url=str(response.url),
                    origin_info=origin_info,
                    header_analysis=header_analysis
                )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"HTTP request failed: {str(e)}")
            return None

    def _parse_origin_info(self, headers: Dict[str, str]) -> Optional['OriginServerInfo']:
        """解析源站信息"""
        from .models import OriginServerInfo
        import re

        # 提取各种源站相关的头信息
        real_ip = headers.get('x-real-ip')
        original_ip = headers.get('x-original-ip')
        source_ip = headers.get('x-source-ip')
        client_ip = headers.get('x-client-ip')

        # 解析X-Forwarded-For
        forwarded_for_raw = headers.get('x-forwarded-for')
        forwarded_for = None
        if forwarded_for_raw:
            # 分割并清理IP地址
            forwarded_for = [ip.strip() for ip in forwarded_for_raw.split(',') if ip.strip()]

        # 后端服务器信息
        backend_server = headers.get('x-backend-server')
        upstream_server = headers.get('x-upstream-server')
        server_name = headers.get('x-server-name')

        # CDN和缓存信息
        cache_status = headers.get('x-cache') or headers.get('cache-status')
        cdn_provider = self._detect_cdn_provider(headers)
        edge_location = headers.get('x-edge-location') or headers.get('cf-ray')

        # 解析Via头
        via_raw = headers.get('via')
        via_chain = None
        if via_raw:
            # 简单解析Via头，提取代理信息
            via_chain = [via.strip() for via in via_raw.split(',') if via.strip()]

        # 服务器技术栈
        powered_by = headers.get('x-powered-by')

        # 提取所有可能的源站IP
        possible_origin_ips = self._extract_possible_origin_ips(headers)

        # 如果没有任何源站相关信息，返回None
        if not any([real_ip, original_ip, source_ip, client_ip, forwarded_for,
                   backend_server, upstream_server, cache_status, via_chain, powered_by]):
            return None

        return OriginServerInfo(
            real_ip=real_ip,
            original_ip=original_ip,
            source_ip=source_ip,
            client_ip=client_ip,
            forwarded_for=forwarded_for,
            forwarded_for_raw=forwarded_for_raw,
            backend_server=backend_server,
            upstream_server=upstream_server,
            server_name=server_name,
            cache_status=cache_status,
            cdn_provider=cdn_provider,
            edge_location=edge_location,
            via_chain=via_chain,
            via_raw=via_raw,
            powered_by=powered_by,
            possible_origin_ips=possible_origin_ips
        )

    def _analyze_headers(self, headers: Dict[str, str]) -> 'HTTPHeaderAnalysis':
        """分析HTTP头"""
        from .models import HTTPHeaderAnalysis

        security_headers = {}
        performance_headers = {}
        custom_headers = {}

        # 安全相关头
        security_header_names = {
            'strict-transport-security', 'x-frame-options', 'x-content-type-options',
            'x-xss-protection', 'content-security-policy', 'referrer-policy',
            'permissions-policy', 'cross-origin-embedder-policy', 'cross-origin-opener-policy'
        }

        # 性能相关头
        performance_header_names = {
            'cache-control', 'expires', 'etag', 'last-modified', 'x-cache',
            'cache-status', 'age', 'vary', 'x-cache-hits'
        }

        for name, value in headers.items():
            name_lower = name.lower()

            if name_lower in security_header_names:
                security_headers[name_lower] = value
            elif name_lower in performance_header_names:
                performance_headers[name_lower] = value
            elif name_lower.startswith('x-') or name_lower.startswith('cf-'):
                custom_headers[name_lower] = value

        return HTTPHeaderAnalysis(
            security_headers=security_headers,
            performance_headers=performance_headers,
            custom_headers=custom_headers,
            total_headers_count=len(headers),
            custom_headers_count=len(custom_headers)
        )

    def _detect_cdn_provider(self, headers: Dict[str, str]) -> Optional[str]:
        """检测CDN提供商"""
        # 检查常见的CDN特征头
        if 'cf-ray' in headers or 'cf-cache-status' in headers:
            return 'cloudflare'
        elif 'x-amz-cf-id' in headers or 'x-amz-cf-pop' in headers:
            return 'amazon_cloudfront'
        elif 'x-azure-ref' in headers:
            return 'azure_cdn'
        elif 'x-fastly-request-id' in headers:
            return 'fastly'
        elif 'x-akamai-edgescape' in headers or 'akamai-origin-hop' in headers:
            return 'akamai'
        elif 'x-cdn' in headers:
            cdn_value = headers['x-cdn'].lower()
            if 'cloudflare' in cdn_value:
                return 'cloudflare'
            elif 'fastly' in cdn_value:
                return 'fastly'

        # 检查Server头中的CDN信息
        server = headers.get('server', '').lower()
        if 'cloudflare' in server:
            return 'cloudflare'
        elif 'fastly' in server:
            return 'fastly'

        return None

    def _extract_possible_origin_ips(self, headers: Dict[str, str]) -> List[str]:
        """从各种头中提取可能的源站IP地址"""
        import re

        possible_ips = []
        ip_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')

        # 检查各种可能包含IP的头
        ip_headers = [
            'x-real-ip', 'x-original-ip', 'x-source-ip', 'x-client-ip',
            'x-forwarded-for', 'x-backend-server', 'x-upstream-server'
        ]

        for header_name in ip_headers:
            header_value = headers.get(header_name)
            if header_value:
                # 提取所有IP地址
                ips = ip_pattern.findall(header_value)
                for ip in ips:
                    # 简单验证IP地址（排除明显的内网地址）
                    if self._is_valid_public_ip(ip) and ip not in possible_ips:
                        possible_ips.append(ip)

        return possible_ips

    def _is_valid_public_ip(self, ip: str) -> bool:
        """检查是否为有效的公网IP地址"""
        try:
            parts = [int(part) for part in ip.split('.')]
            if len(parts) != 4 or any(part < 0 or part > 255 for part in parts):
                return False

            # 排除私有IP地址范围
            if (parts[0] == 10 or
                (parts[0] == 172 and 16 <= parts[1] <= 31) or
                (parts[0] == 192 and parts[1] == 168) or
                parts[0] == 127 or  # 回环地址
                parts[0] == 0):     # 无效地址
                return False

            return True
        except (ValueError, IndexError):
            return False


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

            # 🔧 优化：使用统一的进程管理器
            async with managed_subprocess(
                *cmd,
                timeout=300.0,
                description=f"mtr trace to {host}"
            ) as process:
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    # 解析mtr JSON输出
                    try:
                        mtr_data = json.loads(stdout.decode())
                        return self._parse_mtr_output(mtr_data, host)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse mtr JSON output for {host}: {e}")
                        return None
                else:
                    logger.warning(f"mtr failed for {host}: {stderr.decode()}")
                    return None

        except Exception as e:
            logger.error(f"mtr execution failed: {str(e)}")
            return None

    async def _trace_with_traceroute(self, host: str) -> Optional[NetworkPathInfo]:
        """使用traceroute进行路径追踪"""
        try:
            # 构建traceroute命令
            cmd = ['traceroute', '-n', '-m', '30', '-w', '2', host]

            # 🔧 优化：使用统一的进程管理器
            async with managed_subprocess(
                *cmd,
                timeout=300.0,
                description=f"traceroute to {host}"
            ) as process:
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

    async def trace_multiple_ips(self, domain: str, ip_list: List[str]) -> 'MultiIPNetworkPathInfo':
        """对多个IP进行并行网络路径追踪"""
        from .models import MultiIPNetworkPathInfo, PathSummary

        logger.info(f"Starting multi-IP network path trace to {domain} with {len(ip_list)} IPs: {ip_list}")
        start_time = time.time()

        # 创建并发任务
        tasks = []
        for ip in ip_list:
            task = asyncio.create_task(self.trace_ip_directly(ip))
            tasks.append((ip, task))

        # 等待所有任务完成
        results = {}
        for ip, task in tasks:
            try:
                result = await task
                results[ip] = result
                if result:
                    logger.info(f"Network path trace to {ip} successful: {result.total_hops} hops")
                else:
                    logger.warning(f"Network path trace to {ip} failed")
            except Exception as e:
                logger.error(f"Network path trace to {ip} failed with exception: {str(e)}")
                results[ip] = None

        total_execution_time = (time.time() - start_time) * 1000

        # 创建汇总统计
        summary = self._create_path_summary(results)

        # 确定使用的追踪方法（优先mtr）
        trace_method = "mtr"
        for result in results.values():
            if result and result.trace_method:
                trace_method = result.trace_method
                break

        return MultiIPNetworkPathInfo(
            target_domain=domain,
            tested_ips=ip_list,
            path_results=results,
            summary=summary,
            total_execution_time_ms=total_execution_time,
            concurrent_execution=True,
            trace_method=trace_method
        )

    async def trace_ip_directly(self, ip: str) -> Optional[NetworkPathInfo]:
        """直接追踪指定IP地址的网络路径"""
        logger.debug(f"Starting direct network path trace to IP {ip}")

        # 首先尝试使用mtr
        result = await self._trace_with_mtr_direct(ip)
        if result:
            return result

        # 如果mtr失败，使用traceroute
        return await self._trace_with_traceroute_direct(ip)

    async def _trace_with_mtr_direct(self, ip: str) -> Optional[NetworkPathInfo]:
        """使用mtr直接追踪IP地址"""
        try:
            # 构建mtr命令 - 直接使用IP地址
            cmd = ['sudo', 'mtr', '-rwc', '5', '-f', '1', '-n', '-i', '1', '-4', '-z', '--json', ip]
            logger.debug(f"Executing direct mtr command: {' '.join(cmd)}")

            # 🔧 优化：使用统一的进程管理器
            async with managed_subprocess(
                *cmd,
                timeout=300.0,
                description=f"direct mtr trace to {ip}"
            ) as process:
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    # 解析mtr JSON输出
                    try:
                        mtr_data = json.loads(stdout.decode())
                        return self._parse_mtr_output(mtr_data, ip)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse direct mtr JSON output for {ip}: {e}")
                        return None
                else:
                    logger.warning(f"Direct mtr failed for {ip}: {stderr.decode()}")
                    return None

        except Exception as e:
            logger.error(f"Direct mtr to {ip} failed: {str(e)}")
            return None

    async def _trace_with_traceroute_direct(self, ip: str) -> Optional[NetworkPathInfo]:
        """使用traceroute直接追踪IP地址"""
        try:
            # 构建traceroute命令 - 直接使用IP地址
            cmd = ['traceroute', '-n', '-w', '3', '-q', '3', '-m', '30', ip]
            logger.debug(f"Executing direct traceroute command: {' '.join(cmd)}")

            # 🔧 优化：使用统一的进程管理器
            async with managed_subprocess(
                *cmd,
                timeout=300.0,
                description=f"direct traceroute to {ip}"
            ) as process:
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    # 解析traceroute输出
                    output = stdout.decode('utf-8', errors='ignore')
                    return self._parse_traceroute_output(output, ip)
                else:
                    error_output = stderr.decode('utf-8', errors='ignore')
                    logger.warning(f"Direct traceroute to {ip} failed: {error_output}")
                    return None

        except Exception as e:
            logger.error(f"Direct traceroute to {ip} failed: {str(e)}")
            return None

    def _create_path_summary(self, results: Dict[str, Optional[NetworkPathInfo]]) -> 'PathSummary':
        """创建网络路径追踪汇总统计"""
        from .models import PathSummary

        total_ips = len(results)
        successful_results = [r for r in results.values() if r is not None]
        successful_traces = len(successful_results)
        failed_traces = total_ips - successful_traces
        success_rate = successful_traces / total_ips if total_ips > 0 else 0.0

        # 计算路径统计
        avg_hops = None
        min_hops = None
        max_hops = None
        avg_latency_ms = None
        min_latency_ms = None
        max_latency_ms = None
        fastest_ip = None
        shortest_path_ip = None

        if successful_results:
            # 计算跳数统计
            hop_counts = [r.total_hops for r in successful_results if r.total_hops > 0]
            if hop_counts:
                avg_hops = sum(hop_counts) / len(hop_counts)
                min_hops = min(hop_counts)
                max_hops = max(hop_counts)

                # 找到跳数最少的IP
                for ip, result in results.items():
                    if result and result.total_hops == min_hops:
                        shortest_path_ip = ip
                        break

            # 计算延迟统计
            latencies = [r.avg_latency_ms for r in successful_results if r.avg_latency_ms is not None]
            if latencies:
                avg_latency_ms = sum(latencies) / len(latencies)
                min_latency_ms = min(latencies)
                max_latency_ms = max(latencies)

                # 找到延迟最低的IP
                for ip, result in results.items():
                    if result and result.avg_latency_ms == min_latency_ms:
                        fastest_ip = ip
                        break

        # 分析共同跳点
        common_hops = self._find_common_hops(successful_results)

        # 计算不同路径数量
        unique_paths = self._count_unique_paths(successful_results)

        return PathSummary(
            total_ips=total_ips,
            successful_traces=successful_traces,
            failed_traces=failed_traces,
            success_rate=success_rate,
            avg_hops=avg_hops,
            min_hops=min_hops,
            max_hops=max_hops,
            avg_latency_ms=avg_latency_ms,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            common_hops=common_hops,
            unique_paths=unique_paths,
            fastest_ip=fastest_ip,
            shortest_path_ip=shortest_path_ip
        )

    def _find_common_hops(self, results: List[NetworkPathInfo]) -> List[str]:
        """找到所有路径中的共同跳点"""
        if not results:
            return []

        # 获取第一个结果的跳点作为基准
        if not results[0].hops:
            return []

        common_ips = set()
        for hop in results[0].hops:
            if hop.ip_address:
                common_ips.add(hop.ip_address)

        # 与其他结果求交集
        for result in results[1:]:
            if not result.hops:
                common_ips.clear()
                break

            result_ips = {hop.ip_address for hop in result.hops if hop.ip_address}
            common_ips &= result_ips

        return list(common_ips)

    def _count_unique_paths(self, results: List[NetworkPathInfo]) -> int:
        """计算不同路径的数量"""
        if not results:
            return 0

        # 使用路径签名来识别不同的路径
        path_signatures = set()

        for result in results:
            if result.hops:
                # 创建路径签名（使用跳点IP序列）
                signature = tuple(hop.ip_address for hop in result.hops if hop.ip_address)
                path_signatures.add(signature)

        return len(path_signatures)


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

            # 🔧 优化：使用统一的进程管理器
            async with managed_subprocess(
                *ping_cmd,
                timeout=self.timeout_ms / 1000 + 15,  # 额外15秒缓冲
                description=f"ping to {host}"
            ) as process:
                stdout, stderr = await process.communicate()
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

    async def ping_multiple_ips(self, domain: str, ip_list: List[str]) -> 'MultiIPICMPInfo':
        """对多个IP进行并行ICMP测试"""
        from .models import MultiIPICMPInfo, ICMPSummary

        logger.info(f"Starting multi-IP ICMP ping to {domain} with {len(ip_list)} IPs: {ip_list}")
        start_time = time.time()

        # 创建并发任务
        tasks = []
        for ip in ip_list:
            task = asyncio.create_task(self.ping_ip_directly(ip))
            tasks.append((ip, task))

        # 等待所有任务完成
        results = {}
        for ip, task in tasks:
            try:
                result = await task
                results[ip] = result
                if result and result.is_successful:
                    logger.info(f"ICMP ping to {ip} successful: {result.avg_rtt_ms:.2f}ms avg RTT")
                else:
                    logger.warning(f"ICMP ping to {ip} failed")
            except Exception as e:
                logger.error(f"ICMP ping to {ip} failed with exception: {str(e)}")
                # 创建失败结果
                results[ip] = self._create_error_result(ip, [], 0, str(e))

        total_execution_time = (time.time() - start_time) * 1000

        # 创建汇总统计
        summary = self._create_icmp_summary(results)

        return MultiIPICMPInfo(
            target_domain=domain,
            tested_ips=ip_list,
            icmp_results=results,
            summary=summary,
            total_execution_time_ms=total_execution_time,
            concurrent_execution=True
        )

    async def ping_ip_directly(self, ip: str) -> Optional[ICMPInfo]:
        """直接ping指定IP地址"""
        logger.debug(f"Starting direct ICMP ping to IP {ip}")
        start_time = time.time()

        try:
            # 构建ping命令（直接使用IP地址）
            ping_cmd = self._build_ping_command(ip)

            # 🔧 优化：使用统一的进程管理器
            async with managed_subprocess(
                *ping_cmd,
                timeout=self.timeout_ms / 1000 + 15,  # 额外15秒缓冲
                description=f"direct ping to {ip}"
            ) as process:
                stdout, stderr = await process.communicate()
                execution_time = (time.time() - start_time) * 1000

                if process.returncode == 0:
                    # 解析ping输出
                    output = stdout.decode('utf-8', errors='ignore')
                    return self._parse_ping_output(output, ip, ping_cmd, execution_time)
                else:
                    # ping失败
                    error_output = stderr.decode('utf-8', errors='ignore')
                    logger.warning(f"Direct ping to {ip} failed with return code {process.returncode}: {error_output}")
                    return self._create_error_result(ip, ping_cmd, execution_time, error_output)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Direct ping to {ip} failed: {str(e)}")
            return self._create_error_result(ip, [], execution_time, str(e))

    def _create_icmp_summary(self, results: Dict[str, Optional[ICMPInfo]]) -> 'ICMPSummary':
        """创建ICMP测试汇总统计"""
        from .models import ICMPSummary

        total_ips = len(results)
        successful_results = [r for r in results.values() if r and r.is_successful]
        successful_ips = len(successful_results)
        failed_ips = total_ips - successful_ips
        success_rate = successful_ips / total_ips if total_ips > 0 else 0.0

        # 计算整体性能统计
        avg_rtt_ms = None
        min_rtt_ms = None
        max_rtt_ms = None
        best_performing_ip = None
        worst_performing_ip = None

        if successful_results:
            # 计算平均RTT
            valid_rtts = [r.avg_rtt_ms for r in successful_results if r.avg_rtt_ms is not None]
            if valid_rtts:
                avg_rtt_ms = sum(valid_rtts) / len(valid_rtts)
                min_rtt_ms = min(valid_rtts)
                max_rtt_ms = max(valid_rtts)

                # 找到性能最佳和最差的IP
                for ip, result in results.items():
                    if result and result.is_successful and result.avg_rtt_ms is not None:
                        if result.avg_rtt_ms == min_rtt_ms:
                            best_performing_ip = ip
                        if result.avg_rtt_ms == max_rtt_ms:
                            worst_performing_ip = ip

        # 计算整体丢包统计
        total_packets_sent = sum(r.packets_sent for r in results.values() if r)
        total_packets_received = sum(r.packets_received for r in results.values() if r)
        overall_packet_loss_percent = 0.0
        if total_packets_sent > 0:
            overall_packet_loss_percent = ((total_packets_sent - total_packets_received) / total_packets_sent) * 100

        return ICMPSummary(
            total_ips=total_ips,
            successful_ips=successful_ips,
            failed_ips=failed_ips,
            success_rate=success_rate,
            avg_rtt_ms=avg_rtt_ms,
            min_rtt_ms=min_rtt_ms,
            max_rtt_ms=max_rtt_ms,
            best_performing_ip=best_performing_ip,
            worst_performing_ip=worst_performing_ip,
            total_packets_sent=total_packets_sent,
            total_packets_received=total_packets_received,
            overall_packet_loss_percent=overall_packet_loss_percent
        )
