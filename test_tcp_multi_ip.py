#!/usr/bin/env python3
"""
TCP多IP功能测试脚本
验证TCP多IP测试功能是否正常工作
"""

import json
import sys
import os
from pathlib import Path

def test_tcp_multi_ip_functionality():
    """测试TCP多IP功能"""
    print("🔍 测试TCP多IP功能...")
    
    # 查找最新的测试文件
    output_dir = Path("network-diagnosis/output/domain_based")
    json_files = list(output_dir.glob("network_diagnosis_*.json"))
    
    if not json_files:
        print("❌ 未找到测试文件")
        return False
    
    # 使用最新的文件
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    print(f"📁 使用文件: {latest_file.name}")
    
    # 读取文件内容
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 检查TCP相关字段
    has_tcp_connection = 'tcp_connection' in data and data['tcp_connection'] is not None
    has_multi_tcp = 'multi_ip_tcp' in data and data['multi_ip_tcp'] is not None
    
    print(f"📊 TCP字段状态:")
    print(f"   tcp_connection: {'✅' if has_tcp_connection else '❌'}")
    print(f"   multi_ip_tcp: {'✅' if has_multi_tcp else '❌'}")
    
    if has_multi_tcp:
        multi_tcp = data['multi_ip_tcp']
        tested_ips = multi_tcp.get('tested_ips', [])
        tcp_results = multi_tcp.get('tcp_results', {})
        summary = multi_tcp.get('summary', {})
        
        print(f"\n📋 多IP TCP测试详情:")
        print(f"   目标域名: {multi_tcp.get('target_domain')}")
        print(f"   目标端口: {multi_tcp.get('target_port')}")
        print(f"   测试IP数量: {len(tested_ips)}")
        print(f"   测试IP列表: {tested_ips}")
        
        print(f"\n📊 连接结果:")
        for ip in tested_ips:
            if ip in tcp_results and tcp_results[ip]:
                result = tcp_results[ip]
                status = "✅ 成功" if result.get('is_connected') else "❌ 失败"
                time_ms = result.get('connect_time_ms', 0)
                print(f"   {ip}: {status} ({time_ms:.2f}ms)")
            else:
                print(f"   {ip}: ❌ 无结果")
        
        print(f"\n📈 汇总统计:")
        print(f"   总IP数: {summary.get('total_ips', 0)}")
        print(f"   成功连接: {summary.get('successful_connections', 0)}")
        print(f"   失败连接: {summary.get('failed_connections', 0)}")
        print(f"   成功率: {summary.get('success_rate', 0):.1f}%")
        
        if summary.get('fastest_connection_ip'):
            print(f"   最快IP: {summary.get('fastest_connection_ip')} ({summary.get('fastest_connection_time_ms', 0):.2f}ms)")
        
        if summary.get('recommended_ip'):
            print(f"   推荐IP: {summary.get('recommended_ip')}")
            print(f"   推荐理由: {summary.get('recommendation_reason', 'N/A')}")
        
        return True
    else:
        print("❌ 未找到multi_ip_tcp字段")
        return False


def test_json_trimming_for_tcp():
    """测试TCP字段的JSON裁剪功能"""
    print("\n🧪 测试TCP字段裁剪功能...")
    
    # 创建测试数据
    test_data = {
        "domain": "test.com",
        "target_ip": "1.2.3.4",
        "tcp_connection": {
            "host": "test.com",
            "port": 443,
            "target_ip": "1.2.3.4",
            "connect_time_ms": 10.5,
            "is_connected": True,
            "socket_family": "IPv4"
        },
        "multi_ip_tcp": {
            "target_domain": "test.com",
            "target_port": 443,
            "tested_ips": ["1.2.3.4"],
            "tcp_results": {
                "1.2.3.4": {
                    "host": "test.com",
                    "port": 443,
                    "target_ip": "1.2.3.4",
                    "connect_time_ms": 10.5,
                    "is_connected": True,
                    "socket_family": "IPv4"
                }
            }
        }
    }
    
    print("📋 原始数据包含字段:")
    for key in test_data.keys():
        print(f"   - {key}")
    
    # 添加network-diagnosis模块路径
    sys.path.insert(0, str(Path(__file__).parent / "network-diagnosis" / "src"))
    
    try:
        from network_diagnosis.json_trimmer import trim_json_data
        
        # 执行裁剪
        trimmed_data = trim_json_data(test_data)
        
        print("✂️  裁剪后数据包含字段:")
        for key in trimmed_data.keys():
            print(f"   - {key}")
        
        # 验证结果
        has_tcp_connection = 'tcp_connection' in trimmed_data
        has_multi_tcp = 'multi_ip_tcp' in trimmed_data
        
        print(f"\n📊 裁剪结果:")
        print(f"   tcp_connection 被移除: {'✅' if not has_tcp_connection else '❌'}")
        print(f"   multi_ip_tcp 保留: {'✅' if has_multi_tcp else '❌'}")
        
        return not has_tcp_connection and has_multi_tcp
        
    except ImportError as e:
        print(f"❌ 无法导入裁剪模块: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 TCP多IP功能测试")
    print("=" * 50)
    
    # 测试1: TCP多IP功能
    tcp_multi_ip_ok = test_tcp_multi_ip_functionality()
    
    # 测试2: TCP字段裁剪功能
    tcp_trimming_ok = test_json_trimming_for_tcp()
    
    print("\n" + "=" * 50)
    print("📋 测试总结:")
    print(f"   TCP多IP功能: {'✅ 通过' if tcp_multi_ip_ok else '❌ 失败'}")
    print(f"   TCP字段裁剪: {'✅ 通过' if tcp_trimming_ok else '❌ 失败'}")
    
    if tcp_multi_ip_ok and tcp_trimming_ok:
        print("\n🎉 所有测试通过！TCP多IP功能正常工作。")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查实现。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
