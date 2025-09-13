"""
网络诊断协调器 - 统一管理所有诊断功能
"""
import asyncio
import json
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import NetworkDiagnosisResult, DiagnosisRequest
from .services import DNSResolutionService, EnhancedDNSResolutionService, TCPConnectionService, TLSService, HTTPService, NetworkPathService, ICMPService
from .service_adapters import NetworkServiceFactory
from .logger import get_logger
from .config import settings

logger = get_logger(__name__)


class NetworkDiagnosisCoordinator:
    """网络诊断协调器 - 统一管理所有诊断功能"""

    def __init__(self, output_dir: Optional[str] = None):
        # 使用增强的DNS解析服务，保留原服务作为降级备选
        self.dns_service = EnhancedDNSResolutionService()

        # 使用工厂模式创建服务（支持aiohttp和传统实现切换）
        self.tcp_service = NetworkServiceFactory.create_tcp_service()
        self.http_service = NetworkServiceFactory.create_http_service()
        self.tls_service = NetworkServiceFactory.create_tls_service()

        # 保持原有服务不变
        self.path_service = NetworkPathService()
        self.icmp_service = ICMPService()

        self.output_dir = output_dir  # 自定义输出目录
    
    async def diagnose(self, request: DiagnosisRequest) -> NetworkDiagnosisResult:
        """执行完整的网络诊断"""
        start_time = time.time()
        error_messages = []
        
        # 方案3：改进日志显示
        if request.url:
            logger.info(f"Starting network diagnosis for URL: {request.url}")
        else:
            logger.info(f"Starting network diagnosis for {request.domain}:{request.port}")

        # 1. DNS解析
        logger.info("Resolving domain name...")
        dns_result = await self.dns_service.resolve_domain(request.domain)
        target_ip = dns_result.primary_ip if dns_result.is_successful else None

        # 初始化结果对象
        result = NetworkDiagnosisResult(
            domain=request.domain,
            target_ip=target_ip,
            dns_resolution=dns_result,
            total_diagnosis_time_ms=0.0,
            success=False,
            error_messages=error_messages,
            # 方案2：填充URL相关信息
            original_url=request.url,
            url_path=getattr(request, 'parsed_path', None),
            url_protocol=getattr(request, 'parsed_protocol', None),
            is_url_based=bool(request.url)
        )

        if not dns_result.is_successful:
            error_messages.append(f"DNS resolution failed: {dns_result.error_message}")

        try:
            # 2. TCP连接测试（只有DNS解析成功才进行）
            if target_ip:
                logger.info("Testing TCP connection...")
                tcp_result = await self.tcp_service.test_connection(request.domain, request.port, target_ip)
                result.tcp_connection = tcp_result
            else:
                error_messages.append("Skipping TCP test due to DNS resolution failure")

                if not tcp_result.is_connected:
                    error_messages.append(f"TCP connection failed: {tcp_result.error_message}")

            # 3. TLS信息收集（根据配置和端口决定）
            if (request.include_tls and
                request.port in [443, 8443] and
                result.tcp_connection and
                result.tcp_connection.is_connected):
                logger.info("Collecting TLS information...")
                tls_result = await self.tls_service.get_tls_info(request.domain, request.port)
                result.tls_info = tls_result

                if tls_result and not tls_result.is_secure:
                    error_messages.append("TLS connection is not secure")
            
            # 4. HTTP响应信息收集
            if request.include_http and result.tcp_connection and result.tcp_connection.is_connected:
                logger.info("Collecting HTTP response information...")

                # 构建URL - 支持自定义路径
                if hasattr(request, 'parsed_protocol') and request.parsed_protocol:
                    protocol = request.parsed_protocol
                    path = request.parsed_path or "/"
                    # 对于标准端口，不显示端口号
                    if ((protocol == "https" and request.port == 443) or
                        (protocol == "http" and request.port == 80)):
                        url = f"{protocol}://{request.domain}{path}"
                    else:
                        url = f"{protocol}://{request.domain}:{request.port}{path}"
                else:
                    # 向后兼容：使用传统方式构建URL
                    protocol = "https" if request.port == 443 else "http"
                    url = f"{protocol}://{request.domain}:{request.port}"

                http_result = await self.http_service.get_http_info(url)
                result.http_response = http_result

                if not http_result:
                    error_messages.append("HTTP request failed")
            
            # 5. ICMP探测
            if request.include_icmp:
                logger.info("Performing ICMP ping test...")
                # 使用解析后的域名或原始域名
                target_domain = getattr(request, 'parsed_domain', None) or request.domain
                icmp_result = await self.icmp_service.ping(target_domain)
                result.icmp_info = icmp_result

                if not icmp_result or not icmp_result.is_successful:
                    error_messages.append("ICMP ping test failed")

            # 6. 网络路径追踪
            if request.include_trace:
                logger.info("Performing network path trace...")
                # 使用解析后的域名或原始域名
                target_domain = getattr(request, 'parsed_domain', None) or request.domain
                path_result = await self.path_service.trace_path(target_domain)
                result.network_path = path_result

                if not path_result:
                    error_messages.append("Network path trace failed")

            # 计算总诊断时间
            total_time = (time.time() - start_time) * 1000
            result.total_diagnosis_time_ms = total_time

            # 判断诊断是否成功
            result.success = tcp_result.is_connected and len(error_messages) == 0
            result.error_messages = error_messages



            logger.info(f"Network diagnosis completed in {total_time:.2f}ms, success: {result.success}")

            return result
            
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            error_msg = f"Diagnosis failed with exception: {str(e)}"
            logger.error(error_msg)
            
            result.total_diagnosis_time_ms = total_time
            result.success = False
            result.error_messages.append(error_msg)
            
            return result
    

    
    def save_result_to_file(self, result: NetworkDiagnosisResult) -> str:
        """将诊断结果保存到JSON文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 包含毫秒
        port = "unknown"
        if result.tcp_connection:
            port = str(result.tcp_connection.port)

        # 方案1 & 4：增强文件命名和目录结构
        if result.is_url_based and result.url_path:
            # URL探测：生成包含路径信息的文件名
            # 清理路径中的特殊字符，用于文件名
            clean_path = self._clean_path_for_filename(result.url_path)
            filename = f"network_diagnosis_{result.domain}_{port}_{clean_path}_{timestamp}.json"
            # 方案4：URL探测放在url_based子目录
            subdir = "url_based"
        else:
            # 域名探测：使用传统命名
            filename = f"network_diagnosis_{result.domain}_{port}_{timestamp}.json"
            # 方案4：域名探测放在domain_based子目录
            subdir = "domain_based"

        # 使用自定义输出目录或默认目录
        base_dir = self.output_dir if self.output_dir else settings.OUTPUT_DIR
        filepath = Path(base_dir) / subdir / filename

        try:
            # 确保输出目录存在
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # 保存JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result.to_json_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Diagnosis result saved to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to save result to file: {str(e)}")
            raise

    def _clean_path_for_filename(self, path: str) -> str:
        """清理URL路径，使其适合用作文件名"""
        if not path:
            return "root"

        # 移除开头的斜杠
        clean_path = path.lstrip('/')

        # 如果路径为空，使用root
        if not clean_path:
            return "root"

        # 替换特殊字符为下划线
        import re
        clean_path = re.sub(r'[^\w\-.]', '_', clean_path)

        # 限制长度，避免文件名过长
        if len(clean_path) > 50:
            clean_path = clean_path[:50]

        # 移除末尾的下划线
        clean_path = clean_path.rstrip('_')

        return clean_path or "root"


class DiagnosisRunner:
    """诊断运行器 - 提供便捷的运行接口"""

    def __init__(self, output_dir: Optional[str] = None):
        self.coordinator = NetworkDiagnosisCoordinator(output_dir)
    
    async def run_diagnosis(
        self,
        domain: str = None,
        port: int = 443,
        url: str = None,
        include_trace: bool = True,
        include_http: bool = True,
        include_tls: bool = True,
        include_icmp: bool = True,
        save_to_file: bool = True
    ) -> NetworkDiagnosisResult:
        """运行网络诊断并可选择保存结果"""
        
        # 创建诊断请求
        request_params = {
            'include_trace': include_trace,
            'include_http': include_http,
            'include_tls': include_tls,
            'include_icmp': include_icmp
        }

        if url:
            request_params['url'] = url
        else:
            request_params['domain'] = domain
            request_params['port'] = port

        request = DiagnosisRequest(**request_params)
        
        # 执行诊断
        result = await self.coordinator.diagnose(request)
        
        # 保存结果到文件
        if save_to_file:
            filepath = self.coordinator.save_result_to_file(result)
            logger.info(f"Results saved to: {filepath}")
        
        return result
