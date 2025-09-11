"""
网络诊断工具主程序入口
遵循十二要素应用原则的网络诊断工具
"""
import asyncio
import argparse
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "network-diagnosis" / "src"))

from network_diagnosis.diagnosis import DiagnosisRunner
from network_diagnosis.logger import get_logger
from network_diagnosis.config import settings

logger = get_logger(__name__)


async def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description="网络诊断工具 - 收集TCP、TLS、HTTP和网络路径信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py google.com
  python main.py github.com --port 443 --no-trace
  python main.py example.com --port 80 --no-http
        """
    )

    parser.add_argument(
        "domain",
        help="要诊断的域名"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=443,
        help="目标端口 (默认: 443)"
    )

    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="跳过网络路径追踪"
    )

    parser.add_argument(
        "--no-http",
        action="store_true",
        help="跳过HTTP响应收集"
    )

    parser.add_argument(
        "--no-icmp",
        action="store_true",
        help="跳过ICMP探测"
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="不保存结果到文件"
    )

    args = parser.parse_args()

    try:
        logger.info(f"Starting network diagnosis for {args.domain}:{args.port}")
        logger.info(f"Configuration: trace={not args.no_trace}, http={not args.no_http}, icmp={not args.no_icmp}, save={not args.no_save}")

        # 创建诊断运行器
        runner = DiagnosisRunner()

        # 执行诊断
        result = await runner.run_diagnosis(
            domain=args.domain,
            port=args.port,
            include_trace=not args.no_trace,
            include_http=not args.no_http,
            include_icmp=not args.no_icmp,
            save_to_file=not args.no_save
        )

        # 输出简要结果
        print("\n" + "="*60)
        print(f"网络诊断结果 - {args.domain}:{args.port}")
        print("="*60)

        print(f"目标IP: {result.target_ip or 'Unknown'}")
        print(f"诊断时间: {result.total_diagnosis_time_ms:.2f}ms")
        print(f"诊断状态: {'成功' if result.success else '失败'}")

        if result.tcp_connection:
            tcp = result.tcp_connection
            print(f"TCP连接: {'成功' if tcp.is_connected else '失败'} ({tcp.connect_time_ms:.2f}ms)")

        if result.tls_info:
            tls = result.tls_info
            print(f"TLS协议: {tls.protocol_version}")
            print(f"加密套件: {tls.cipher_suite}")
            if tls.certificate:
                cert = tls.certificate
                print(f"证书有效期: {cert.days_until_expiry}天")

        if result.http_response:
            http = result.http_response
            print(f"HTTP状态: {http.status_code} {http.reason_phrase}")
            print(f"响应时间: {http.response_time_ms:.2f}ms")

        if result.icmp_info:
            icmp = result.icmp_info
            print(f"ICMP探测: {icmp.packets_received}/{icmp.packets_sent} 包")
            print(f"丢包率: {icmp.packet_loss_percent:.1f}%")
            if icmp.avg_rtt_ms:
                print(f"平均RTT: {icmp.avg_rtt_ms:.2f}ms")

        if result.network_path:
            path = result.network_path
            print(f"网络跳数: {path.total_hops}")
            print(f"平均延迟: {path.avg_latency_ms:.2f}ms" if path.avg_latency_ms else "平均延迟: N/A")

        if result.error_messages:
            print("\n错误信息:")
            for error in result.error_messages:
                print(f"  - {error}")

        print("="*60)

        if result.success:
            logger.info("Network diagnosis completed successfully")
            return 0
        else:
            logger.error("Network diagnosis completed with errors")
            return 1

    except KeyboardInterrupt:
        logger.info("Diagnosis interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
