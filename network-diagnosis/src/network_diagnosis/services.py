"""
网络诊断服务模块 - 核心功能实现
"""
import asyncio
import json
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

from .models import (
    DNSResolutionInfo, TCPConnectionInfo, TLSInfo, SSLCertificateInfo,
    HTTPResponseInfo, NetworkPathInfo, TraceRouteHop,
    NetworkDiagnosisResult, DiagnosisRequest, PublicIPInfo
)
from .logger import get_logger
from .config import settings

logger = get_logger(__name__)


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

        # 首先尝试使用mtr
        if settings.SUDO_PASSWORD:
            result = await self._trace_with_mtr(host)
            if result:
                return result

        # 如果mtr失败或不可用，使用traceroute
        return await self._trace_with_traceroute(host)

    async def _trace_with_mtr(self, host: str) -> Optional[NetworkPathInfo]:
        """使用mtr进行路径追踪"""
        try:
            # 构建mtr命令
            cmd = ['sudo', '-S', 'mtr', '-r', '-f', '3', '-w', '-n', '-c', '3', '--json', host]

            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # 提供sudo密码
            stdout, stderr = await process.communicate(
                input=f"{settings.SUDO_PASSWORD}\n".encode()
            )

            if process.returncode == 0:
                # 解析mtr JSON输出
                mtr_data = json.loads(stdout.decode())
                return self._parse_mtr_output(mtr_data, host)
            else:
                logger.warning(f"mtr failed: {stderr.decode()}")
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

        for hop_data in mtr_data.get('report', {}).get('hubs', []):
            hop = TraceRouteHop(
                hop_number=hop_data.get('count', 0),
                ip_address=hop_data.get('host'),
                response_times_ms=[hop_data.get('Avg', 0.0)],
                avg_response_time_ms=hop_data.get('Avg', 0.0),
                packet_loss_percent=hop_data.get('Loss%', 0.0)
            )
            hops.append(hop)

        # 计算总体统计
        avg_latency = sum(hop.avg_response_time_ms or 0 for hop in hops) / len(hops) if hops else None
        total_loss = sum(hop.packet_loss_percent for hop in hops) / len(hops) if hops else 0

        return NetworkPathInfo(
            target_host=host,
            target_ip=mtr_data.get('report', {}).get('dst'),
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
