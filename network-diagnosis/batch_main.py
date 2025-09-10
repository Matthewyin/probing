#!/usr/bin/env python3
"""
批量网络诊断工具主程序
从配置文件读取目标列表并执行批量诊断
"""
import asyncio
import argparse
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from network_diagnosis.batch_runner import BatchDiagnosisRunner
from network_diagnosis.config_loader import ConfigLoader
from network_diagnosis.logger import get_logger, log_and_print
from config import settings

logger = get_logger(__name__)


def resolve_config_path(config_path: str) -> str:
    """
    解析配置文件路径，支持智能查找

    Args:
        config_path: 用户提供的配置文件路径

    Returns:
        解析后的完整路径

    Rules:
        1. 如果是绝对路径，直接使用
        2. 如果包含路径分隔符，按相对路径处理
        3. 如果只是文件名，在input目录中查找
    """
    config_path = Path(config_path)

    # 如果是绝对路径，直接返回
    if config_path.is_absolute():
        return str(config_path)

    # 如果包含路径分隔符（如 input/xxx.yaml），按相对路径处理
    if len(config_path.parts) > 1:
        return str(config_path)

    # 如果只是文件名，在input目录中查找
    input_path = Path("input") / config_path
    if input_path.exists():
        return str(input_path)

    # 如果input目录中不存在，返回原路径（让后续错误处理）
    return str(config_path)


def print_batch_summary(batch_result):
    """打印批量诊断摘要"""
    summary = batch_result.get_summary()
    exec_summary = summary["execution_summary"]
    perf_stats = summary["performance_statistics"]
    sec_stats = summary["security_statistics"]
    http_stats = summary["http_statistics"]

    log_and_print("\n" + "="*80)
    log_and_print("批量网络诊断结果摘要")
    log_and_print("="*80)

    # 执行摘要
    log_and_print(f"配置文件: {exec_summary.get('config_file', 'Unknown')}")
    log_and_print(f"总目标数: {exec_summary['total_targets']}")
    log_and_print(f"成功诊断: {exec_summary['successful']}")
    log_and_print(f"失败诊断: {exec_summary['failed']}")
    log_and_print(f"成功率: {exec_summary['success_rate']:.1f}%")
    log_and_print(f"总执行时间: {exec_summary['total_execution_time_ms']:.2f}ms")
    
    # 性能统计
    log_and_print(f"\n性能统计:")
    log_and_print(f"  平均诊断时间: {perf_stats['average_diagnosis_time_ms']:.2f}ms")
    log_and_print(f"  平均TCP连接时间: {perf_stats['average_tcp_connect_time_ms']:.2f}ms")
    if perf_stats['fastest_diagnosis_ms'] > 0:
        log_and_print(f"  最快诊断: {perf_stats['fastest_diagnosis_ms']:.2f}ms")
        log_and_print(f"  最慢诊断: {perf_stats['slowest_diagnosis_ms']:.2f}ms")
    
    # 安全统计
    log_and_print(f"\n安全统计:")
    log_and_print(f"  启用TLS连接: {sec_stats['tls_enabled_count']}")
    log_and_print(f"  安全连接率: {sec_stats['secure_connections_rate']:.1f}%")
    if sec_stats['tls_protocols']:
        log_and_print(f"  TLS协议分布:")
        for protocol, count in sec_stats['tls_protocols'].items():
            log_and_print(f"    {protocol}: {count}")
    
    # HTTP状态码统计
    if http_stats['status_codes']:
        log_and_print(f"\nHTTP状态码分布:")
        for status_code, count in sorted(http_stats['status_codes'].items()):
            log_and_print(f"  {status_code}: {count}")

    # 详细结果
    log_and_print(f"\n详细结果:")
    log_and_print("-" * 80)
    for i, result in enumerate(batch_result.results, 1):
        status = "✓" if result.success else "✗"
        log_and_print(f"{i:2d}. {status} {result.domain} - {result.total_diagnosis_time_ms:.2f}ms")

        if not result.success and result.error_messages:
            for error in result.error_messages:
                log_and_print(f"     错误: {error}")

    log_and_print("="*80)


async def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description="批量网络诊断工具 - 从配置文件读取目标列表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
配置文件格式 (YAML):
  targets:
    - domain: "google.com"
      port: 443
      include_trace: false
      include_http: true
      description: "Google搜索引擎"
    - domain: "github.com"
      port: 443
      include_trace: false
      include_http: true
      description: "GitHub代码托管平台"
  
  global_settings:
    max_concurrent: 3
    timeout_seconds: 60
    save_individual_files: true
    save_summary_report: true

示例用法:
  python batch_main.py                           # 使用默认配置文件 input/targets.yaml
  python batch_main.py -c input/custom.yaml     # 使用自定义配置文件
  python batch_main.py -c custom.yaml           # 自动在input目录中查找
  python batch_main.py --create-sample          # 创建示例配置文件
  python batch_main.py --validate               # 验证配置文件格式
        """
    )
    
    parser.add_argument(
        "-c", "--config",
        default="input/targets.yaml",
        help="配置文件路径 (默认: input/targets.yaml)"
    )
    
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="创建示例配置文件"
    )
    
    parser.add_argument(
        "--validate",
        action="store_true",
        help="验证配置文件格式"
    )
    
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="不显示详细摘要"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式，只显示错误"
    )
    
    args = parser.parse_args()
    
    try:
        # 创建示例配置文件
        if args.create_sample:
            config_loader = ConfigLoader()
            sample_file = "input/targets_sample.yaml"
            config_loader.create_sample_config(sample_file)
            log_and_print(f"示例配置文件已创建: {sample_file}")
            return 0
        
        # 解析配置文件路径
        resolved_config = resolve_config_path(args.config)

        # 验证配置文件
        if args.validate:
            config_loader = ConfigLoader(resolved_config)
            if config_loader.validate_config_file(resolved_config):
                log_and_print(f"配置文件格式正确: {resolved_config}")
                return 0
            else:
                log_and_print(f"配置文件格式错误: {resolved_config}", "ERROR")
                return 1

        # 检查配置文件是否存在
        config_path = Path(resolved_config)
        if not config_path.exists():
            log_and_print(f"错误: 配置文件不存在: {resolved_config}", "ERROR")
            log_and_print("使用 --create-sample 创建示例配置文件")
            log_and_print("提示: 配置文件应放在 input/ 目录下")
            return 1
        
        if not args.quiet:
            logger.info(f"Starting batch diagnosis from config: {resolved_config}")

        # 创建批量诊断运行器
        runner = BatchDiagnosisRunner(resolved_config)

        # 显示日志文件路径
        if not args.quiet:
            log_and_print(f"📝 日志文件: {runner.log_filepath}")

        # 执行批量诊断
        batch_result = await runner.run_batch_diagnosis()
        
        # 显示结果摘要
        if not args.no_summary and not args.quiet:
            print_batch_summary(batch_result)
        elif not args.quiet:
            # 简化输出
            summary = batch_result.get_summary()
            exec_summary = summary["execution_summary"]
            log_and_print(f"\n批量诊断完成: {exec_summary['successful']}/{exec_summary['total_targets']} 成功")
            log_and_print(f"总耗时: {exec_summary['total_execution_time_ms']:.2f}ms")
        
        # 返回适当的退出码
        if batch_result.failed_count > 0:
            if not args.quiet:
                logger.warning(f"Batch diagnosis completed with {batch_result.failed_count} failures")
            return 1
        else:
            if not args.quiet:
                logger.info("Batch diagnosis completed successfully")
            return 0
            
    except KeyboardInterrupt:
        if not args.quiet:
            logger.info("Batch diagnosis interrupted by user")
        return 130
    except FileNotFoundError as e:
        log_and_print(f"错误: {str(e)}", "ERROR")
        return 1
    except ValueError as e:
        log_and_print(f"配置错误: {str(e)}", "ERROR")
        return 1
    except Exception as e:
        if not args.quiet:
            logger.error(f"Unexpected error: {str(e)}")
        log_and_print(f"未预期的错误: {str(e)}", "ERROR")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
