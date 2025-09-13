"""
基于socket + asyncio的纯TCP连接测试服务
提供真正的TCP层连通性测试，不涉及应用层协议
"""
import asyncio
import socket
import time
from typing import Optional, Dict, Any, List
import errno

from .logger import get_logger
from .config import settings
from .models import EnhancedTCPConnectionInfo

logger = get_logger(__name__)


class TCPErrorClassifier:
    """TCP连接错误分类器 - 增强版"""

    # 错误码映射 (errno -> 错误类型)
    ERROR_PATTERNS = {
        # 连接被拒绝
        "connection_refused": [61, 111],  # ECONNREFUSED (macOS/Linux)
        # 连接超时
        "connection_timeout": [60, 110],  # ETIMEDOUT
        # 网络不可达
        "network_unreachable": [51, 101], # ENETUNREACH
        # 主机不可达
        "host_unreachable": [65, 113],    # EHOSTUNREACH
        # 权限拒绝
        "permission_denied": [13],        # EACCES
        # 地址已在使用
        "address_in_use": [48, 98],       # EADDRINUSE
        # 网络已关闭
        "network_down": [50, 100],        # ENETDOWN
        # 连接重置
        "connection_reset": [54, 104],    # ECONNRESET
        # 管道破裂
        "broken_pipe": [32],              # EPIPE
    }

    # 错误严重程度
    ERROR_SEVERITY = {
        "connection_refused": "high",      # 服务未运行或端口关闭
        "connection_timeout": "medium",    # 可能是网络延迟或防火墙
        "network_unreachable": "high",     # 路由问题
        "host_unreachable": "high",        # 主机离线
        "permission_denied": "medium",     # 权限问题
        "address_in_use": "low",          # 本地端口冲突
        "network_down": "high",           # 网络接口问题
        "connection_reset": "medium",     # 连接被远程重置
        "broken_pipe": "medium"           # 连接中断
    }
    
    @classmethod
    def classify_error(cls, error: Exception, host: str = None, port: int = None) -> Dict[str, Any]:
        """分类连接错误 - 增强版"""
        if isinstance(error, asyncio.TimeoutError):
            return {
                "error_type": "timeout",
                "error_category": "network",
                "severity": "medium",
                "is_retryable": True,
                "retry_delay_seconds": 5,
                "max_retries": 3,
                "suggested_action": "检查网络连接或增加超时时间",
                "detailed_suggestions": [
                    "检查网络连接是否稳定",
                    "尝试增加连接超时时间",
                    "检查是否有防火墙阻止连接",
                    f"使用 telnet {host} {port} 手动测试连接" if host and port else "使用 telnet 手动测试连接"
                ],
                "system_errno": None,
                "troubleshooting_commands": [
                    f"ping {host}" if host else "ping <target_host>",
                    f"traceroute {host}" if host else "traceroute <target_host>",
                    f"nmap -p {port} {host}" if host and port else "nmap -p <port> <host>"
                ]
            }

        elif isinstance(error, OSError):
            errno_val = error.errno
            error_type = cls._classify_by_errno(errno_val)
            severity = cls.ERROR_SEVERITY.get(error_type, "medium")

            return {
                "error_type": error_type,
                "error_category": "system",
                "severity": severity,
                "system_errno": errno_val,
                "is_retryable": error_type in ["connection_timeout", "network_unreachable", "connection_reset"],
                "retry_delay_seconds": cls._get_retry_delay(error_type),
                "max_retries": cls._get_max_retries(error_type),
                "suggested_action": cls._get_suggested_action(error_type),
                "detailed_suggestions": cls._get_detailed_suggestions(error_type, host, port),
                "troubleshooting_commands": cls._get_troubleshooting_commands(error_type, host, port)
            }

        else:
            return {
                "error_type": "unknown",
                "error_category": "unknown",
                "severity": "high",
                "system_errno": None,
                "is_retryable": False,
                "retry_delay_seconds": 0,
                "max_retries": 0,
                "suggested_action": "检查网络配置和目标服务器状态",
                "detailed_suggestions": [
                    "检查网络配置",
                    "验证目标服务器状态",
                    "查看系统日志获取更多信息"
                ],
                "troubleshooting_commands": [
                    "netstat -an | grep LISTEN",
                    "ss -tuln"
                ]
            }
    
    @classmethod
    def _classify_by_errno(cls, errno_val: int) -> str:
        """根据errno分类错误"""
        for error_type, errno_list in cls.ERROR_PATTERNS.items():
            if errno_val in errno_list:
                return error_type
        return "unknown_system_error"
    
    @classmethod
    def _get_retry_delay(cls, error_type: str) -> int:
        """获取重试延迟时间（秒）"""
        delays = {
            "connection_timeout": 5,
            "network_unreachable": 10,
            "connection_reset": 3,
            "connection_refused": 0,  # 立即失败，不重试
            "host_unreachable": 0,
            "permission_denied": 0
        }
        return delays.get(error_type, 5)

    @classmethod
    def _get_max_retries(cls, error_type: str) -> int:
        """获取最大重试次数"""
        retries = {
            "connection_timeout": 3,
            "network_unreachable": 2,
            "connection_reset": 2,
            "connection_refused": 0,
            "host_unreachable": 0,
            "permission_denied": 0
        }
        return retries.get(error_type, 1)

    @classmethod
    def _get_suggested_action(cls, error_type: str) -> str:
        """获取建议的解决方案"""
        suggestions = {
            "connection_refused": "检查目标端口是否开放，服务是否运行",
            "connection_timeout": "检查网络连接，考虑增加超时时间",
            "network_unreachable": "检查网络路由和防火墙设置",
            "host_unreachable": "检查目标主机是否在线",
            "permission_denied": "检查是否有足够的权限访问网络",
            "address_in_use": "端口已被占用，尝试其他端口",
            "network_down": "检查网络接口状态",
            "connection_reset": "连接被远程重置，检查服务器配置",
            "broken_pipe": "连接中断，检查网络稳定性"
        }
        return suggestions.get(error_type, "检查网络配置和目标服务器状态")

    @classmethod
    def _get_detailed_suggestions(cls, error_type: str, host: str = None, port: int = None) -> List[str]:
        """获取详细的解决建议"""
        base_suggestions = {
            "connection_refused": [
                "确认目标服务正在运行",
                f"检查端口 {port} 是否开放" if port else "检查目标端口是否开放",
                "验证防火墙规则",
                "检查服务绑定的IP地址"
            ],
            "connection_timeout": [
                "检查网络连接稳定性",
                "增加连接超时时间",
                "检查防火墙是否阻止连接",
                "验证路由配置"
            ],
            "network_unreachable": [
                "检查网络路由表",
                "验证网关配置",
                "检查网络接口状态",
                "确认目标网络可达"
            ],
            "host_unreachable": [
                "确认目标主机在线",
                "检查主机防火墙设置",
                "验证IP地址正确性",
                "检查ARP表"
            ],
            "connection_reset": [
                "检查服务器负载",
                "验证连接限制配置",
                "检查服务器日志",
                "确认协议匹配"
            ]
        }

        suggestions = base_suggestions.get(error_type, [
            "检查网络配置",
            "验证目标服务状态",
            "查看系统日志"
        ])

        # 添加主机特定的建议
        if host:
            suggestions.append(f"尝试从其他主机连接到 {host}")

        return suggestions

    @classmethod
    def _get_troubleshooting_commands(cls, error_type: str, host: str = None, port: int = None) -> List[str]:
        """获取故障排除命令"""
        commands = []

        if host:
            commands.extend([
                f"ping {host}",
                f"traceroute {host}",
                f"nslookup {host}"
            ])

            if port:
                commands.extend([
                    f"telnet {host} {port}",
                    f"nmap -p {port} {host}",
                    f"nc -zv {host} {port}"
                ])

        # 添加错误类型特定的命令
        type_commands = {
            "connection_refused": [
                "netstat -an | grep LISTEN",
                "ss -tuln"
            ],
            "network_unreachable": [
                "route -n",
                "ip route show"
            ],
            "permission_denied": [
                "id",
                "sudo netstat -an"
            ]
        }

        commands.extend(type_commands.get(error_type, []))

        return commands


class AsyncTCPService:
    """基于socket + asyncio的纯TCP连接测试服务"""
    
    def __init__(self):
        self.timeout = settings.CONNECT_TIMEOUT
    
    async def test_connection(self, host: str, port: int, target_ip: str) -> EnhancedTCPConnectionInfo:
        """
        测试TCP连接 - 纯网络层连通性测试
        
        Args:
            host: 主机名
            port: 端口号
            target_ip: 目标IP地址
            
        Returns:
            EnhancedTCPConnectionInfo: 增强的TCP连接信息
        """
        start_time = time.time()
        
        try:
            # 创建socket连接
            result = await self._create_socket_connection(target_ip, port, self.timeout)
            
            if result["success"]:
                connect_time = (time.time() - start_time) * 1000
                
                logger.info(f"AsyncTCP connection to {host}:{port} ({target_ip}) successful in {connect_time:.2f}ms")
                
                return EnhancedTCPConnectionInfo(
                    host=host,
                    port=port,
                    target_ip=target_ip,
                    connect_time_ms=connect_time,
                    is_connected=True,
                    socket_family=result["socket_info"]["family"],
                    local_address=result["socket_info"]["local_address"],
                    local_port=result["socket_info"]["local_port"],
                    error_message=None,

                    # AsyncTCP专用字段
                    remote_address=result["socket_info"]["remote_address"],
                    remote_port=result["socket_info"]["remote_port"],

                    # 增强信息
                    timing_breakdown={
                        "tcp_connect_ms": connect_time,
                        "total_time_ms": connect_time
                    },
                    connection_pool_info=None,  # 纯TCP连接无连接池
                    transport_info={
                        "connection_method": "socket_asyncio",
                        "socket_type": result["socket_info"]["socket_type"],
                        "protocol": "TCP",
                        "is_reused_connection": False
                    }
                )
            else:
                # 连接失败
                connect_time = (time.time() - start_time) * 1000
                error_info = result["error_info"]
                
                logger.warning(f"AsyncTCP connection to {host}:{port} ({target_ip}) failed: {result['error_message']}")
                
                return EnhancedTCPConnectionInfo(
                    host=host,
                    port=port,
                    target_ip=target_ip,
                    connect_time_ms=connect_time,
                    is_connected=False,
                    socket_family="IPv4",
                    error_message=result["error_message"],

                    # 增强错误信息
                    timing_breakdown={
                        "tcp_connect_ms": connect_time,
                        "total_time_ms": connect_time
                    },
                    connection_pool_info=None,
                    transport_info={
                        "connection_method": "socket_asyncio",
                        "error_classification": error_info,
                        "is_retryable": error_info.get("is_retryable", False)
                    },
                    # 增强错误分析
                    error_classification=error_info
                )
                
        except Exception as e:
            # 意外错误
            connect_time = (time.time() - start_time) * 1000
            error_info = TCPErrorClassifier.classify_error(e, host, port)

            logger.error(f"AsyncTCP connection to {host}:{port} ({target_ip}) failed with unexpected error: {str(e)}")

            return EnhancedTCPConnectionInfo(
                host=host,
                port=port,
                target_ip=target_ip,
                connect_time_ms=connect_time,
                is_connected=False,
                socket_family="IPv4",
                error_message=str(e),
                timing_breakdown={
                    "tcp_connect_ms": connect_time,
                    "total_time_ms": connect_time
                },
                transport_info={
                    "connection_method": "socket_asyncio",
                    "error_classification": error_info,
                    "unexpected_error": True
                },
                # 增强错误信息
                error_classification=error_info
            )
    
    async def _create_socket_connection(self, target_ip: str, port: int, timeout: int) -> Dict[str, Any]:
        """
        创建异步socket连接
        
        Returns:
            Dict包含success, socket_info, error_info等信息
        """
        sock = None
        try:
            # 创建socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            
            # 异步连接
            await asyncio.wait_for(
                asyncio.get_event_loop().sock_connect(sock, (target_ip, port)),
                timeout=timeout
            )
            
            # 获取连接信息（在关闭前）
            socket_info = self._extract_socket_info(sock, target_ip, port)

            # 立即关闭连接（纯TCP测试）
            sock.close()
            
            return {
                "success": True,
                "socket_info": socket_info,
                "error_message": None,
                "error_info": None
            }
            
        except asyncio.TimeoutError:
            if sock:
                sock.close()
            error_info = TCPErrorClassifier.classify_error(asyncio.TimeoutError(), target_ip, port)
            return {
                "success": False,
                "socket_info": None,
                "error_message": f"Connection timeout after {timeout}s",
                "error_info": error_info
            }

        except Exception as e:
            if sock:
                sock.close()
            error_info = TCPErrorClassifier.classify_error(e, target_ip, port)
            return {
                "success": False,
                "socket_info": None,
                "error_message": str(e),
                "error_info": error_info
            }
    
    def _extract_socket_info(self, sock: socket.socket, target_ip: str, port: int) -> Dict[str, Any]:
        """提取socket详细信息"""
        socket_info = {}

        try:
            # 获取本地地址信息
            local_addr = sock.getsockname()
            socket_info.update({
                "local_address": local_addr[0],
                "local_port": local_addr[1],
            })

            # 获取远程地址信息
            try:
                remote_addr = sock.getpeername()
                socket_info.update({
                    "remote_address": remote_addr[0],
                    "remote_port": remote_addr[1],
                })
            except Exception:
                # 如果getpeername失败，使用传入的目标信息
                socket_info.update({
                    "remote_address": target_ip,
                    "remote_port": port,
                })

            # 获取socket属性
            socket_info.update({
                "family": "IPv6" if sock.family == socket.AF_INET6 else "IPv4",
                "socket_type": "SOCK_STREAM",
                "protocol": "TCP"
            })

        except Exception as e:
            logger.debug(f"Failed to extract socket info: {e}")
            # 提供默认值，包含目标信息
            socket_info = {
                "local_address": None,
                "local_port": None,
                "remote_address": target_ip,
                "remote_port": port,
                "family": "IPv4",
                "socket_type": "SOCK_STREAM",
                "protocol": "TCP"
            }

        return socket_info
