"""
批量诊断运行器 - 支持从配置文件批量执行网络诊断
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config_loader import ConfigLoader, GlobalSettings
from .diagnosis import DiagnosisRunner
from .models import NetworkDiagnosisResult, DiagnosisRequest, PublicIPInfo
from .logger import get_logger, setup_config_logging
from .services import PublicIPService
from .config import settings
from .resource_monitor import ResourceMonitor

logger = get_logger(__name__)


class BatchDiagnosisResult:
    """批量诊断结果"""
    
    def __init__(self):
        self.results: List[NetworkDiagnosisResult] = []
        self.start_time: datetime = datetime.now()
        self.end_time: Optional[datetime] = None
        self.total_time_ms: float = 0.0
        self.successful_count: int = 0
        self.failed_count: int = 0
        self.config_file: Optional[str] = None
    
    def add_result(self, result: NetworkDiagnosisResult):
        """添加单个诊断结果"""
        self.results.append(result)
        if result.success:
            self.successful_count += 1
        else:
            self.failed_count += 1
    
    def finalize(self):
        """完成批量诊断，计算总时间"""
        self.end_time = datetime.now()
        self.total_time_ms = (self.end_time - self.start_time).total_seconds() * 1000
    
    def get_summary(self) -> Dict[str, Any]:
        """获取汇总信息"""
        if not self.results:
            return {}
        
        # 计算性能统计
        response_times = [r.total_diagnosis_time_ms for r in self.results if r.success]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # 计算连接统计
        tcp_times = [r.tcp_connection.connect_time_ms for r in self.results 
                    if r.tcp_connection and r.tcp_connection.is_connected]
        avg_tcp_time = sum(tcp_times) / len(tcp_times) if tcp_times else 0
        
        # TLS统计
        tls_results = [r for r in self.results if r.tls_info and r.tls_info.is_secure]
        tls_protocols = {}
        for result in tls_results:
            protocol = result.tls_info.protocol_version
            tls_protocols[protocol] = tls_protocols.get(protocol, 0) + 1
        
        # HTTP状态码统计
        http_status_codes = {}
        for result in self.results:
            if result.http_response:
                status = result.http_response.status_code
                http_status_codes[status] = http_status_codes.get(status, 0) + 1
        
        return {
            "execution_summary": {
                "total_targets": len(self.results),
                "successful": self.successful_count,
                "failed": self.failed_count,
                "success_rate": (self.successful_count / len(self.results)) * 100 if self.results else 0,
                "total_execution_time_ms": self.total_time_ms,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "config_file": self.config_file
            },
            "performance_statistics": {
                "average_diagnosis_time_ms": avg_response_time,
                "average_tcp_connect_time_ms": avg_tcp_time,
                "fastest_diagnosis_ms": min(response_times) if response_times else 0,
                "slowest_diagnosis_ms": max(response_times) if response_times else 0
            },
            "security_statistics": {
                "tls_enabled_count": len(tls_results),
                "tls_protocols": tls_protocols,
                "secure_connections_rate": (len(tls_results) / len(self.results)) * 100 if self.results else 0
            },
            "http_statistics": {
                "status_codes": http_status_codes,
                "http_enabled_count": len([r for r in self.results if r.http_response])
            }
        }
    
    def to_json_dict(self) -> Dict[str, Any]:
        """转换为JSON字典"""
        return {
            "summary": self.get_summary(),
            "individual_results": [result.to_json_dict() for result in self.results]
        }


class BatchDiagnosisRunner:
    """批量诊断运行器"""
    
    def __init__(self, config_file: str = "input/targets.yaml"):
        self.config_file = config_file
        self.config_loader = ConfigLoader(config_file)

        # 生成基于配置文件的输出子目录
        config_name = Path(config_file).stem  # 获取文件名（不含扩展名）
        self.config_name = config_name
        self.output_subdir = Path(settings.OUTPUT_DIR) / config_name

        # 设置基于配置文件的日志记录
        self.log_filepath = setup_config_logging(config_name)

        # 创建诊断运行器，使用子目录作为输出目录
        self.diagnosis_runner = DiagnosisRunner(str(self.output_subdir))

        # 创建公网IP服务
        self.public_ip_service = PublicIPService()
        self.public_ip_info: Optional[PublicIPInfo] = None
    
    async def run_batch_diagnosis(self) -> BatchDiagnosisResult:
        """执行批量诊断"""
        logger.info(f"Starting batch diagnosis from config file: {self.config_file}")
        logger.info(f"Output directory: {self.output_subdir}")
        logger.info(f"Log file: {self.log_filepath}")

        # 🔍 监控：记录开始时的资源状态
        ResourceMonitor.log_status_summary()

        # 确保输出目录存在
        self.output_subdir.mkdir(parents=True, exist_ok=True)

        # 加载配置
        try:
            config = self.config_loader.load_config()
            requests = self.config_loader.get_diagnosis_requests()
            global_settings = self.config_loader.get_global_settings()
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise
        
        # 创建批量结果对象
        batch_result = BatchDiagnosisResult()
        batch_result.config_file = self.config_file
        
        logger.info(f"Loaded {len(requests)} targets for diagnosis")
        logger.info(f"Max concurrent: {global_settings.max_concurrent}")

        # 获取公网IP信息（在诊断开始前获取一次）
        logger.info("Getting public IP information...")
        try:
            self.public_ip_info = await self.public_ip_service.get_public_ip_info()
            if self.public_ip_info:
                logger.info(f"Public IP: {self.public_ip_info.ip} ({self.public_ip_info.service_provider})")
                if self.public_ip_info.city and self.public_ip_info.isp:
                    logger.info(f"Location: {self.public_ip_info.city}, ISP: {self.public_ip_info.isp}")
            else:
                logger.warning("Failed to get public IP information")
        except Exception as e:
            logger.warning(f"Error getting public IP information: {e}")
            self.public_ip_info = None

        # 创建信号量控制并发数
        semaphore = asyncio.Semaphore(global_settings.max_concurrent)
        
        # 创建诊断任务
        tasks = []
        for i, request in enumerate(requests):
            task = self._diagnose_with_semaphore(
                semaphore, request, i + 1, len(requests), global_settings
            )
            tasks.append(task)
        
        # 执行所有诊断任务
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Target {i+1} failed with exception: {str(result)}")
                    # 创建一个失败的结果
                    failed_result = NetworkDiagnosisResult(
                        domain=requests[i].domain,
                        total_diagnosis_time_ms=0.0,
                        success=False,
                        error_messages=[f"Exception: {str(result)}"],
                        public_ip_info=self.public_ip_info
                    )
                    batch_result.add_result(failed_result)
                else:
                    batch_result.add_result(result)
            
        except Exception as e:
            logger.error(f"Batch diagnosis failed: {str(e)}")
            raise
        
        # 完成批量诊断
        batch_result.finalize()
        
        # 保存结果
        if global_settings.save_summary_report:
            await self._save_batch_report(batch_result, global_settings)
        
        logger.info(f"Batch diagnosis completed: {batch_result.successful_count}/{len(requests)} successful")

        # 🔍 监控：记录结束时的资源状态
        ResourceMonitor.log_status_summary()

        return batch_result
    
    async def _diagnose_with_semaphore(
        self, 
        semaphore: asyncio.Semaphore, 
        request: DiagnosisRequest, 
        current: int, 
        total: int,
        global_settings: GlobalSettings
    ) -> NetworkDiagnosisResult:
        """使用信号量控制的诊断任务"""
        async with semaphore:
            # 方案3：改进日志显示
            if request.url:
                logger.info(f"[{current}/{total}] Starting diagnosis for URL: {request.url}")
            else:
                logger.info(f"[{current}/{total}] Starting diagnosis for {request.domain}:{request.port}")
            
            try:
                # 执行诊断
                result = await asyncio.wait_for(
                    self.diagnosis_runner.coordinator.diagnose(request),
                    timeout=global_settings.timeout_seconds
                )
                
                # 添加公网IP信息到诊断结果
                if self.public_ip_info:
                    result.public_ip_info = self.public_ip_info

                # 保存单个文件
                if global_settings.save_individual_files:
                    self.diagnosis_runner.coordinator.save_result_to_file(result)

                status = "SUCCESS" if result.success else "FAILED"
                # 方案3：改进日志显示
                if request.url:
                    logger.info(f"[{current}/{total}] {request.url} - {status} ({result.total_diagnosis_time_ms:.2f}ms)")
                else:
                    logger.info(f"[{current}/{total}] {request.domain}:{request.port} - {status} ({result.total_diagnosis_time_ms:.2f}ms)")

                return result
                
            except asyncio.TimeoutError:
                # 方案3：改进错误日志显示
                if request.url:
                    logger.error(f"[{current}/{total}] {request.url} - TIMEOUT")
                else:
                    logger.error(f"[{current}/{total}] {request.domain}:{request.port} - TIMEOUT")
                timeout_result = NetworkDiagnosisResult(
                    domain=request.domain,
                    total_diagnosis_time_ms=global_settings.timeout_seconds * 1000,
                    success=False,
                    error_messages=[f"Diagnosis timeout after {global_settings.timeout_seconds} seconds"],
                    public_ip_info=self.public_ip_info
                )
                return timeout_result
            except Exception as e:
                # 方案3：改进错误日志显示
                if request.url:
                    logger.error(f"[{current}/{total}] {request.url} - ERROR: {str(e)}")
                else:
                    logger.error(f"[{current}/{total}] {request.domain}:{request.port} - ERROR: {str(e)}")
                error_result = NetworkDiagnosisResult(
                    domain=request.domain,
                    total_diagnosis_time_ms=0.0,
                    success=False,
                    error_messages=[f"Diagnosis failed: {str(e)}"],
                    public_ip_info=self.public_ip_info
                )
                return error_result
    
    async def _save_batch_report(self, batch_result: BatchDiagnosisResult, global_settings: GlobalSettings):
        """保存批量诊断报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_diagnosis_report_{timestamp}.json"
        filepath = Path(settings.OUTPUT_DIR) / filename
        
        try:
            # 确保输出目录存在
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存JSON报告
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(batch_result.to_json_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Batch diagnosis report saved to {filepath}")
            
            # 如果启用了分析功能，生成分析报告
            if global_settings.include_performance_analysis or global_settings.include_security_analysis:
                await self._generate_analysis_report(batch_result, global_settings)
                
        except Exception as e:
            logger.error(f"Failed to save batch report: {str(e)}")
    
    async def _generate_analysis_report(self, batch_result: BatchDiagnosisResult, global_settings: GlobalSettings):
        """生成分析报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analysis_report_{timestamp}.txt"
        filepath = Path(settings.OUTPUT_DIR) / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("网络诊断分析报告\n")
                f.write("=" * 50 + "\n\n")
                
                summary = batch_result.get_summary()
                
                # 执行摘要
                exec_summary = summary["execution_summary"]
                f.write(f"执行摘要:\n")
                f.write(f"  总目标数: {exec_summary['total_targets']}\n")
                f.write(f"  成功数: {exec_summary['successful']}\n")
                f.write(f"  失败数: {exec_summary['failed']}\n")
                f.write(f"  成功率: {exec_summary['success_rate']:.1f}%\n")
                f.write(f"  总执行时间: {exec_summary['total_execution_time_ms']:.2f}ms\n\n")
                
                # 性能分析
                if global_settings.include_performance_analysis:
                    perf_stats = summary["performance_statistics"]
                    f.write(f"性能分析:\n")
                    f.write(f"  平均诊断时间: {perf_stats['average_diagnosis_time_ms']:.2f}ms\n")
                    f.write(f"  平均TCP连接时间: {perf_stats['average_tcp_connect_time_ms']:.2f}ms\n")
                    f.write(f"  最快诊断: {perf_stats['fastest_diagnosis_ms']:.2f}ms\n")
                    f.write(f"  最慢诊断: {perf_stats['slowest_diagnosis_ms']:.2f}ms\n\n")
                
                # 安全分析
                if global_settings.include_security_analysis:
                    sec_stats = summary["security_statistics"]
                    f.write(f"安全分析:\n")
                    f.write(f"  启用TLS的连接数: {sec_stats['tls_enabled_count']}\n")
                    f.write(f"  安全连接率: {sec_stats['secure_connections_rate']:.1f}%\n")
                    f.write(f"  TLS协议分布:\n")
                    for protocol, count in sec_stats['tls_protocols'].items():
                        f.write(f"    {protocol}: {count}\n")
                    f.write("\n")
                
                # HTTP状态码分析
                http_stats = summary["http_statistics"]
                f.write(f"HTTP状态码分布:\n")
                for status_code, count in http_stats['status_codes'].items():
                    f.write(f"  {status_code}: {count}\n")
            
            logger.info(f"Analysis report saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to generate analysis report: {str(e)}")


async def run_batch_from_config(config_file: str = "input/targets.yaml") -> BatchDiagnosisResult:
    """便捷函数：从配置文件运行批量诊断"""
    runner = BatchDiagnosisRunner(config_file)
    return await runner.run_batch_diagnosis()
