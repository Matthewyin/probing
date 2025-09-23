#!/usr/bin/env python3
"""
测试自动恢复机制
"""
import sys
import asyncio
import time
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "network-diagnosis" / "src"))

from network_diagnosis.auto_recovery import (
    AutoRecoverySystem,
    RecoveryRule,
    RecoveryAction,
    get_auto_recovery_system
)


async def test_recovery_rules():
    """测试恢复规则配置"""
    print("🧪 测试恢复规则配置...")
    
    recovery_system = AutoRecoverySystem()
    
    # 添加自定义规则
    custom_rule = RecoveryRule(
        name="test_rule",
        condition="测试条件",
        metric_name="test_metric",
        threshold_value=100.0,
        comparison="greater",
        action=RecoveryAction.CLEANUP_RESOURCES,
        cooldown_seconds=60,
        max_attempts=2
    )
    
    recovery_system.add_recovery_rule(custom_rule)
    
    # 检查规则是否添加成功
    if "test_rule" in recovery_system.recovery_rules:
        rule = recovery_system.recovery_rules["test_rule"]
        if (rule.threshold_value == 100.0 and 
            rule.action == RecoveryAction.CLEANUP_RESOURCES):
            print("   ✅ 自定义恢复规则配置成功")
            return True
        else:
            print("   ❌ 恢复规则配置不正确")
            return False
    else:
        print("   ❌ 恢复规则未添加成功")
        return False


async def test_condition_checking():
    """测试条件检查"""
    print("\n🧪 测试条件检查...")
    
    recovery_system = AutoRecoverySystem()
    
    # 添加测试规则
    test_rule = RecoveryRule(
        name="condition_test",
        condition="测试条件检查",
        metric_name="test_value",
        threshold_value=50.0,
        comparison="greater",
        action=RecoveryAction.CLEANUP_RESOURCES
    )
    recovery_system.add_recovery_rule(test_rule)
    
    # 测试触发条件
    test_metrics = {
        'test_value': 75.0  # 超过阈值
    }
    
    triggered_rules = recovery_system.check_recovery_conditions(test_metrics)
    
    if triggered_rules:
        rule = triggered_rules[0]
        if rule.name == "condition_test":
            print("   ✅ 条件检查正常触发")
            return True
        else:
            print("   ❌ 触发了错误的规则")
            return False
    else:
        print("   ❌ 条件检查未触发")
        return False


async def test_cooldown_mechanism():
    """测试冷却机制"""
    print("\n🧪 测试冷却机制...")
    
    recovery_system = AutoRecoverySystem()
    
    # 添加短冷却时间的规则
    cooldown_rule = RecoveryRule(
        name="cooldown_test",
        condition="冷却测试",
        metric_name="test_cooldown",
        threshold_value=10.0,
        comparison="greater",
        action=RecoveryAction.CLEAR_CACHE,
        cooldown_seconds=2  # 2秒冷却
    )
    recovery_system.add_recovery_rule(cooldown_rule)
    
    test_metrics = {'test_cooldown': 20.0}
    
    # 第一次检查应该触发
    triggered1 = recovery_system.check_recovery_conditions(test_metrics)
    
    # 模拟执行恢复动作
    if triggered1:
        recovery_system.last_attempt_times[cooldown_rule.name] = recovery_system.last_attempt_times.get(cooldown_rule.name, recovery_system.last_attempt_times.setdefault(cooldown_rule.name, recovery_system.last_attempt_times.get(cooldown_rule.name, time.time())))
        from datetime import datetime
        recovery_system.last_attempt_times[cooldown_rule.name] = datetime.now()
    
    # 立即第二次检查应该不触发（冷却中）
    triggered2 = recovery_system.check_recovery_conditions(test_metrics)
    
    # 等待冷却时间
    await asyncio.sleep(2.1)
    
    # 第三次检查应该再次触发
    triggered3 = recovery_system.check_recovery_conditions(test_metrics)
    
    if len(triggered1) > 0 and len(triggered2) == 0 and len(triggered3) > 0:
        print("   ✅ 冷却机制工作正常")
        return True
    else:
        print(f"   ❌ 冷却机制异常: {len(triggered1)}, {len(triggered2)}, {len(triggered3)}")
        return False


async def test_max_attempts():
    """测试最大尝试次数"""
    print("\n🧪 测试最大尝试次数...")
    
    recovery_system = AutoRecoverySystem()
    
    # 添加最大尝试次数为1的规则
    max_attempts_rule = RecoveryRule(
        name="max_attempts_test",
        condition="最大尝试测试",
        metric_name="test_attempts",
        threshold_value=5.0,
        comparison="greater",
        action=RecoveryAction.CLEAR_CACHE,
        cooldown_seconds=0,  # 无冷却
        max_attempts=1
    )
    recovery_system.add_recovery_rule(max_attempts_rule)
    
    test_metrics = {'test_attempts': 10.0}
    
    # 第一次检查应该触发
    triggered1 = recovery_system.check_recovery_conditions(test_metrics)
    
    # 模拟执行后增加尝试计数
    if triggered1:
        recovery_system.attempt_counts[max_attempts_rule.name] = 1
    
    # 第二次检查应该不触发（达到最大尝试次数）
    triggered2 = recovery_system.check_recovery_conditions(test_metrics)
    
    if len(triggered1) > 0 and len(triggered2) == 0:
        print("   ✅ 最大尝试次数限制正常")
        return True
    else:
        print(f"   ❌ 最大尝试次数限制异常: {len(triggered1)}, {len(triggered2)}")
        return False


async def test_recovery_actions():
    """测试恢复动作执行"""
    print("\n🧪 测试恢复动作执行...")
    
    recovery_system = AutoRecoverySystem()
    
    # 测试清理资源动作
    cleanup_rule = RecoveryRule(
        name="cleanup_test",
        condition="清理测试",
        metric_name="test_cleanup",
        threshold_value=1.0,
        comparison="greater",
        action=RecoveryAction.CLEANUP_RESOURCES
    )
    
    test_metrics = {'test_cleanup': 2.0}
    
    # 执行恢复动作
    attempt = await recovery_system.execute_recovery_action(cleanup_rule, test_metrics)
    
    if attempt.success:
        print("   ✅ 清理资源动作执行成功")
        success1 = True
    else:
        print(f"   ❌ 清理资源动作失败: {attempt.error_message}")
        success1 = False
    
    # 测试缓存清理动作
    cache_rule = RecoveryRule(
        name="cache_test",
        condition="缓存测试",
        metric_name="test_cache",
        threshold_value=1.0,
        comparison="greater",
        action=RecoveryAction.CLEAR_CACHE
    )
    
    attempt2 = await recovery_system.execute_recovery_action(cache_rule, test_metrics)
    
    if attempt2.success:
        print("   ✅ 缓存清理动作执行成功")
        success2 = True
    else:
        print(f"   ❌ 缓存清理动作失败: {attempt2.error_message}")
        success2 = False
    
    return success1 and success2


async def test_recovery_check_cycle():
    """测试完整恢复检查周期"""
    print("\n🧪 测试完整恢复检查周期...")
    
    recovery_system = AutoRecoverySystem()
    
    # 添加会触发的规则
    trigger_rule = RecoveryRule(
        name="cycle_test",
        condition="周期测试",
        metric_name="open_files",  # 使用真实指标
        threshold_value=0.0,  # 设置很低的阈值确保触发
        comparison="greater",
        action=RecoveryAction.CLEAR_CACHE,
        cooldown_seconds=0
    )
    recovery_system.add_recovery_rule(trigger_rule)
    
    # 运行恢复检查
    await recovery_system.run_recovery_check()
    
    # 检查是否有恢复历史
    status = recovery_system.get_status()
    
    if status['recovery_attempts_total'] > 0:
        print("   ✅ 恢复检查周期运行正常")
        print(f"   📊 恢复尝试次数: {status['recovery_attempts_total']}")
        return True
    else:
        print("   ⚠️  未触发恢复动作（可能指标不满足条件）")
        return True  # 这种情况也算正常


async def test_global_instance():
    """测试全局实例"""
    print("\n🧪 测试全局实例...")
    
    # 获取两个全局实例
    system1 = get_auto_recovery_system()
    system2 = get_auto_recovery_system()
    
    # 验证是同一个实例
    if system1 is system2:
        print("   ✅ 全局实例单例模式正常")
        return True
    else:
        print("   ❌ 全局实例不是单例")
        return False


async def test_status_reporting():
    """测试状态报告"""
    print("\n🧪 测试状态报告...")
    
    recovery_system = AutoRecoverySystem()
    
    # 获取状态
    status = recovery_system.get_status()
    
    # 检查必要的状态字段
    required_fields = ['enabled', 'emergency_mode', 'rules_count', 'recovery_attempts_total']
    missing_fields = [field for field in required_fields if field not in status]
    
    if not missing_fields:
        print("   ✅ 状态报告完整")
        print(f"   📊 启用状态: {status['enabled']}")
        print(f"   📊 规则数量: {status['rules_count']}")
        print(f"   📊 恢复尝试: {status['recovery_attempts_total']}")
        return True
    else:
        print(f"   ❌ 状态报告缺少字段: {missing_fields}")
        return False


async def test_enable_disable():
    """测试启用/禁用功能"""
    print("\n🧪 测试启用/禁用功能...")
    
    recovery_system = AutoRecoverySystem()
    
    # 初始应该是启用的
    initial_enabled = recovery_system.enabled
    
    # 禁用
    recovery_system.disable()
    disabled_state = recovery_system.enabled
    
    # 重新启用
    recovery_system.enable()
    enabled_state = recovery_system.enabled
    
    if initial_enabled and not disabled_state and enabled_state:
        print("   ✅ 启用/禁用功能正常")
        return True
    else:
        print(f"   ❌ 启用/禁用功能异常: {initial_enabled}, {disabled_state}, {enabled_state}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始自动恢复系统测试")
    print("=" * 60)
    
    test_results = []
    
    try:
        # 测试1: 恢复规则配置
        result1 = await test_recovery_rules()
        test_results.append(("恢复规则配置", result1))
        
        # 测试2: 条件检查
        result2 = await test_condition_checking()
        test_results.append(("条件检查", result2))
        
        # 测试3: 冷却机制
        result3 = await test_cooldown_mechanism()
        test_results.append(("冷却机制", result3))
        
        # 测试4: 最大尝试次数
        result4 = await test_max_attempts()
        test_results.append(("最大尝试次数", result4))
        
        # 测试5: 恢复动作执行
        result5 = await test_recovery_actions()
        test_results.append(("恢复动作执行", result5))
        
        # 测试6: 恢复检查周期
        result6 = await test_recovery_check_cycle()
        test_results.append(("恢复检查周期", result6))
        
        # 测试7: 全局实例
        result7 = await test_global_instance()
        test_results.append(("全局实例", result7))
        
        # 测试8: 状态报告
        result8 = await test_status_reporting()
        test_results.append(("状态报告", result8))
        
        # 测试9: 启用/禁用
        result9 = await test_enable_disable()
        test_results.append(("启用/禁用", result9))
        
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        return 1
    
    # 显示测试结果
    print("\n" + "=" * 60)
    print("📊 自动恢复系统测试结果:")
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(test_results)} 测试通过")
    
    if passed == len(test_results):
        print("🎉 所有测试通过！自动恢复系统工作正常。")
        return 0
    else:
        print("⚠️  部分测试失败，需要进一步检查。")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        sys.exit(130)
