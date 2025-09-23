#!/usr/bin/env python3
"""
测试增强监控和告警系统
"""
import sys
import time
import json
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "network-diagnosis" / "src"))

from network_diagnosis.enhanced_monitor import (
    EnhancedMonitor,
    AlertThreshold,
    AlertLevel,
    AlertEvent,
    LogNotificationHandler,
    FileNotificationHandler,
    get_enhanced_monitor
)


def test_threshold_configuration():
    """测试告警阈值配置"""
    print("🧪 测试告警阈值配置...")
    
    monitor = EnhancedMonitor()
    
    # 添加自定义阈值
    custom_threshold = AlertThreshold(
        metric_name="test_metric",
        warning_threshold=50.0,
        critical_threshold=80.0,
        comparison="greater"
    )
    monitor.add_threshold(custom_threshold)
    
    # 检查阈值是否添加成功
    if "test_metric" in monitor.thresholds:
        threshold = monitor.thresholds["test_metric"]
        if (threshold.warning_threshold == 50.0 and 
            threshold.critical_threshold == 80.0):
            print("   ✅ 自定义阈值配置成功")
            return True
        else:
            print("   ❌ 阈值配置不正确")
            return False
    else:
        print("   ❌ 阈值未添加成功")
        return False


def test_metrics_collection():
    """测试指标收集"""
    print("\n🧪 测试指标收集...")
    
    monitor = EnhancedMonitor()
    
    # 收集指标
    metrics = monitor.collect_metrics()
    
    # 检查必要的指标
    required_metrics = ['timestamp', 'open_files', 'file_handlers', 'active_processes']
    missing_metrics = [m for m in required_metrics if m not in metrics]
    
    if not missing_metrics:
        print("   ✅ 所有必要指标收集成功")
        print(f"   📊 开放文件: {metrics.get('open_files', 'N/A')}")
        print(f"   📊 文件处理器: {metrics.get('file_handlers', 'N/A')}")
        print(f"   📊 活跃进程: {metrics.get('active_processes', 'N/A')}")
        return True
    else:
        print(f"   ❌ 缺少指标: {missing_metrics}")
        return False


def test_alert_generation():
    """测试告警生成"""
    print("\n🧪 测试告警生成...")
    
    monitor = EnhancedMonitor()
    
    # 设置低阈值以触发告警
    test_threshold = AlertThreshold(
        metric_name="test_value",
        warning_threshold=5.0,
        critical_threshold=10.0,
        comparison="greater"
    )
    monitor.add_threshold(test_threshold)
    
    # 模拟指标数据
    test_metrics = {
        'timestamp': '2023-01-01T00:00:00',
        'test_value': 15.0  # 超过critical阈值
    }
    
    # 检查告警
    alerts = monitor.check_thresholds(test_metrics)
    
    if alerts:
        alert = alerts[0]
        if (alert.level == AlertLevel.CRITICAL and 
            alert.metric_name == "test_value" and
            alert.current_value == 15.0):
            print("   ✅ 告警生成正确")
            print(f"   🚨 告警级别: {alert.level.value}")
            print(f"   🚨 告警消息: {alert.message}")
            return True
        else:
            print("   ❌ 告警内容不正确")
            return False
    else:
        print("   ❌ 未生成告警")
        return False


def test_notification_handlers():
    """测试通知处理器"""
    print("\n🧪 测试通知处理器...")
    
    # 创建测试告警
    from datetime import datetime
    test_alert = AlertEvent(
        timestamp=datetime.now(),
        level=AlertLevel.WARNING,
        metric_name="test_metric",
        current_value=75.0,
        threshold_value=50.0,
        message="Test alert message"
    )
    
    # 测试日志通知处理器
    log_handler = LogNotificationHandler()
    log_result = log_handler.send_notification(test_alert)
    
    # 测试文件通知处理器
    test_file = Path(__file__).parent / "test_alerts.jsonl"
    file_handler = FileNotificationHandler(str(test_file))
    file_result = file_handler.send_notification(test_alert)
    
    # 检查文件是否创建
    file_exists = test_file.exists()
    
    # 清理测试文件
    if test_file.exists():
        test_file.unlink()
    
    if log_result and file_result and file_exists:
        print("   ✅ 通知处理器工作正常")
        return True
    else:
        print(f"   ❌ 通知处理器失败: log={log_result}, file={file_result}, exists={file_exists}")
        return False


def test_data_persistence():
    """测试数据持久化"""
    print("\n🧪 测试数据持久化...")
    
    # 创建临时监控实例
    temp_dir = Path(__file__).parent / "temp_monitoring"
    monitor = EnhancedMonitor(data_dir=str(temp_dir))
    
    # 保存测试指标
    test_metrics = {
        'timestamp': '2023-01-01T00:00:00',
        'open_files': 10,
        'file_handlers': 2,
        'active_processes': 1
    }
    
    monitor.save_metrics(test_metrics)
    
    # 检查文件是否创建
    metrics_file = temp_dir / "metrics.jsonl"
    if metrics_file.exists():
        # 读取并验证内容
        with open(metrics_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                try:
                    saved_data = json.loads(content)
                    if saved_data.get('open_files') == 10:
                        print("   ✅ 数据持久化成功")
                        success = True
                    else:
                        print("   ❌ 保存的数据不正确")
                        success = False
                except json.JSONDecodeError:
                    print("   ❌ 保存的数据格式错误")
                    success = False
            else:
                print("   ❌ 文件为空")
                success = False
    else:
        print("   ❌ 指标文件未创建")
        success = False
    
    # 清理临时目录
    try:
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"   ⚠️  清理临时目录失败: {e}")
    
    return success


def test_monitoring_cycle():
    """测试完整监控周期"""
    print("\n🧪 测试完整监控周期...")
    
    # 创建临时监控实例
    temp_dir = Path(__file__).parent / "temp_cycle_test"
    monitor = EnhancedMonitor(data_dir=str(temp_dir))
    
    # 设置低阈值以便触发告警
    low_threshold = AlertThreshold(
        metric_name="open_files",
        warning_threshold=1.0,
        critical_threshold=2.0,
        comparison="greater"
    )
    monitor.add_threshold(low_threshold)
    
    # 运行监控周期
    monitor.run_monitoring_cycle()
    
    # 检查状态
    status = monitor.get_status()
    
    # 验证结果
    success = True
    
    if not status.get('monitoring_enabled', False):
        print("   ❌ 监控未启用")
        success = False
    
    if status.get('active_alerts_count', 0) == 0:
        print("   ⚠️  未触发告警（可能阈值设置过低）")
    else:
        print(f"   📊 触发告警数量: {status['active_alerts_count']}")
    
    # 检查数据文件
    metrics_file = temp_dir / "metrics.jsonl"
    if not metrics_file.exists():
        print("   ❌ 指标文件未创建")
        success = False
    else:
        print("   ✅ 指标文件创建成功")
    
    # 清理临时目录
    try:
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"   ⚠️  清理临时目录失败: {e}")
    
    if success:
        print("   ✅ 监控周期运行正常")
    
    return success


def test_global_instance():
    """测试全局实例"""
    print("\n🧪 测试全局实例...")
    
    # 获取两个全局实例
    monitor1 = get_enhanced_monitor()
    monitor2 = get_enhanced_monitor()
    
    # 验证是同一个实例
    if monitor1 is monitor2:
        print("   ✅ 全局实例单例模式正常")
        return True
    else:
        print("   ❌ 全局实例不是单例")
        return False


def test_alert_resolution():
    """测试告警解决"""
    print("\n🧪 测试告警解决...")
    
    monitor = EnhancedMonitor()
    
    # 设置阈值
    threshold = AlertThreshold(
        metric_name="test_resolution",
        warning_threshold=50.0,
        critical_threshold=80.0,
        comparison="greater"
    )
    monitor.add_threshold(threshold)
    
    # 触发告警
    high_metrics = {
        'timestamp': '2023-01-01T00:00:00',
        'test_resolution': 90.0  # 超过critical
    }
    
    alerts = monitor.check_thresholds(high_metrics)
    monitor.process_alerts(alerts)
    
    initial_alert_count = len(monitor.active_alerts)
    
    # 恢复正常
    normal_metrics = {
        'timestamp': '2023-01-01T00:01:00',
        'test_resolution': 30.0  # 低于warning
    }
    
    monitor.resolve_alerts(normal_metrics)
    
    final_alert_count = len(monitor.active_alerts)
    
    if initial_alert_count > 0 and final_alert_count < initial_alert_count:
        print("   ✅ 告警解决机制正常")
        print(f"   📊 告警数量: {initial_alert_count} -> {final_alert_count}")
        return True
    else:
        print(f"   ❌ 告警解决失败: {initial_alert_count} -> {final_alert_count}")
        return False


def main():
    """主测试函数"""
    print("🚀 开始增强监控系统测试")
    print("=" * 60)
    
    test_results = []
    
    try:
        # 测试1: 阈值配置
        result1 = test_threshold_configuration()
        test_results.append(("阈值配置", result1))
        
        # 测试2: 指标收集
        result2 = test_metrics_collection()
        test_results.append(("指标收集", result2))
        
        # 测试3: 告警生成
        result3 = test_alert_generation()
        test_results.append(("告警生成", result3))
        
        # 测试4: 通知处理器
        result4 = test_notification_handlers()
        test_results.append(("通知处理器", result4))
        
        # 测试5: 数据持久化
        result5 = test_data_persistence()
        test_results.append(("数据持久化", result5))
        
        # 测试6: 监控周期
        result6 = test_monitoring_cycle()
        test_results.append(("监控周期", result6))
        
        # 测试7: 全局实例
        result7 = test_global_instance()
        test_results.append(("全局实例", result7))
        
        # 测试8: 告警解决
        result8 = test_alert_resolution()
        test_results.append(("告警解决", result8))
        
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        return 1
    
    # 显示测试结果
    print("\n" + "=" * 60)
    print("📊 增强监控系统测试结果:")
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(test_results)} 测试通过")
    
    if passed == len(test_results):
        print("🎉 所有测试通过！增强监控系统工作正常。")
        return 0
    else:
        print("⚠️  部分测试失败，需要进一步检查。")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        sys.exit(130)
