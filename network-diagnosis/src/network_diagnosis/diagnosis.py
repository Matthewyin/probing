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
from .services import DNSResolutionService, TCPConnectionService, TLSService, HTTPService, NetworkPathService
from .logger import get_logger
from config import settings

logger = get_logger(__name__)


class NetworkDiagnosisCoordinator:
    """网络诊断协调器 - 统一管理所有诊断功能"""

    def __init__(self, output_dir: Optional[str] = None):
        self.dns_service = DNSResolutionService()
        self.tcp_service = TCPConnectionService()
        self.tls_service = TLSService()
        self.http_service = HTTPService()
        self.path_service = NetworkPathService()
        self.output_dir = output_dir  # 自定义输出目录
    
    async def diagnose(self, request: DiagnosisRequest) -> NetworkDiagnosisResult:
        """执行完整的网络诊断"""
        start_time = time.time()
        error_messages = []
        
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
            error_messages=error_messages
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
            
            # 5. 网络路径追踪
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
        # 生成文件名，包含端口号以避免冲突
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 包含毫秒
        port = "unknown"
        if result.tcp_connection:
            port = str(result.tcp_connection.port)
        filename = f"network_diagnosis_{result.domain}_{port}_{timestamp}.json"

        # 使用自定义输出目录或默认目录
        base_dir = self.output_dir if self.output_dir else settings.OUTPUT_DIR
        filepath = Path(base_dir) / filename
        
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
        save_to_file: bool = True
    ) -> NetworkDiagnosisResult:
        """运行网络诊断并可选择保存结果"""
        
        # 创建诊断请求
        request_params = {
            'include_trace': include_trace,
            'include_http': include_http,
            'include_tls': include_tls
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
