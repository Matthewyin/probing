#!/usr/bin/env python3
"""
综合测试脚本 - 验证所有修复效果和系统稳定性
"""
import asyncio
import sys
import time
import subprocess
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "network-diagnosis" / "src"))

from network_diagnosis.process_manager import process_manager, managed_subprocess
from network_diagnosis.resource_monitor import ResourceMonitor
from network_diagnosis.logger import get_logger
from network_diagnosis.batch_runner import BatchDiagnosisRunner

logger = get_logger(__name__)


async def test_resource_stability():
    """测试资源稳定性 - 模拟长期运行"""
    print("🧪 测试资源稳定性...")
    
    initial_status = ResourceMonitor.get_comprehensive_status()
    print(f"📊 初始状态: {initial_status['overall_status']}")
    
    # 模拟多次批量诊断
    config_file = "network-diagnosis/input/probe_lottery.yaml"
    
    for i in range(5):
        print(f"🔄 第 {i+1}/5 次批量诊断...")
        
        try:
            # 创建BatchDiagnosisRunner实例
            runner = BatchDiagnosisRunner(config_file)
            result = await runner.run_batch_diagnosis()
            
            total_count = result.successful_count + result.failed_count
            print(f"   ✅ 完成 - 成功: {result.successful_count}/{total_count}")
            
            # 检查资源状态
            status = ResourceMonitor.get_comprehensive_status()
            print(f"   📊 状态: {status['overall_status']}")
            print(f"   📊 活跃进程: {status['process_status']['active_processes']}")
            print(f"   📊 日志处理器: {status['handler_status']['total_file_handlers']}")
            
            if status['overall_status'] == 'critical':
                print(f"   ❌ 检测到严重问题: {status['errors']}")
                return False
                
        except Exception as e:
            print(f"   ❌ 批量诊断失败: {e}")
            return False
        
        # 等待一下再进行下一次测试
        await asyncio.sleep(2)
    
    # 检查最终状态
    final_status = ResourceMonitor.get_comprehensive_status()
    print(f"📊 最终状态: {final_status['overall_status']}")
    
    return final_status['overall_status'] in ['healthy', 'warning']


async def test_process_management():
    """测试进程管理功能"""
    print("\n🧪 测试进程管理功能...")
    
    initial_count = process_manager.get_process_count()
    print(f"📊 初始进程数: {initial_count}")
    
    # 测试并发进程
    tasks = []
    for i in range(10):
        task = asyncio.create_task(run_test_subprocess(i))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success_count = sum(1 for r in results if r is True)
    
    print(f"   ✅ 并发进程测试: {success_count}/10 成功")
    
    # 等待清理
    await asyncio.sleep(3)
    
    final_count = process_manager.get_process_count()
    print(f"   📊 最终进程数: {final_count}")
    
    if final_count <= initial_count:
        print("   ✅ 进程管理正常")
        return True
    else:
        print(f"   ❌ 可能存在进程泄漏: {final_count - initial_count} 个进程")
        return False


async def run_test_subprocess(index: int) -> bool:
    """运行单个测试子进程"""
    try:
        async with managed_subprocess(
            'ping', '-c', '2', '127.0.0.1',
            timeout=10.0,
            description=f"test subprocess {index}"
        ) as proc:
            stdout, stderr = await proc.communicate()
            return proc.returncode == 0
    except Exception as e:
        logger.warning(f"Test subprocess {index} failed: {e}")
        return False


async def test_error_recovery():
    """测试错误恢复能力"""
    print("\n🧪 测试错误恢复能力...")
    
    # 测试超时处理
    print("   测试超时处理...")
    try:
        async with managed_subprocess(
            'sleep', '30',
            timeout=2.0,
            description="timeout test"
        ) as proc:
            await proc.communicate()
    except asyncio.TimeoutError:
        print("   ✅ 超时处理正常")
    except Exception as e:
        print(f"   ❌ 超时处理异常: {e}")
        return False
    
    # 测试无效命令处理
    print("   测试无效命令处理...")
    try:
        async with managed_subprocess(
            'nonexistent_command_12345',
            description="invalid command test"
        ) as proc:
            await proc.communicate()
    except FileNotFoundError:
        print("   ✅ 无效命令处理正常")
    except Exception as e:
        print(f"   ❌ 无效命令处理异常: {e}")
        return False
    
    # 检查进程状态
    await asyncio.sleep(1)
    process_count = process_manager.get_process_count()
    print(f"   📊 错误测试后进程数: {process_count}")
    
    return True


def test_system_resources():
    """测试系统资源使用"""
    print("\n🧪 测试系统资源使用...")
    
    try:
        # 检查文件描述符使用
        result = subprocess.run(['lsof', '-p', str(os.getpid())], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            fd_count = len(result.stdout.strip().split('\n')) - 1  # 减去标题行
            print(f"   📊 当前文件描述符: {fd_count}")
        else:
            print("   ⚠️  无法获取文件描述符信息")
        
        # 检查内存使用
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        print(f"   📊 内存使用: {memory_info.rss / 1024 / 1024:.1f} MB")
        
        return True
        
    except ImportError:
        print("   ⚠️  psutil未安装，跳过系统资源检查")
        return True
    except Exception as e:
        print(f"   ❌ 系统资源检查失败: {e}")
        return False


async def test_scheduler_simulation():
    """模拟调度器运行"""
    print("\n🧪 模拟调度器运行...")
    
    config_file = "network-diagnosis/input/probe_lottery.yaml"
    
    # 模拟调度器每分钟执行的场景
    for minute in range(3):
        print(f"   🕐 模拟第 {minute + 1} 分钟执行...")
        
        # 创建新的BatchDiagnosisRunner（模拟调度器行为）
        runner = BatchDiagnosisRunner(config_file)
        
        try:
            result = await runner.run_batch_diagnosis()
            total_count = result.successful_count + result.failed_count
            print(f"      ✅ 执行完成: {result.successful_count}/{total_count}")
        except Exception as e:
            print(f"      ❌ 执行失败: {e}")
            return False
        
        # 检查资源状态
        status = ResourceMonitor.get_comprehensive_status()
        print(f"      📊 资源状态: {status['overall_status']}")
        
        if status['overall_status'] == 'critical':
            print(f"      ❌ 资源状态严重: {status['errors']}")
            return False
        
        # 等待下一分钟
        await asyncio.sleep(1)
    
    print("   ✅ 调度器模拟测试完成")
    return True


async def main():
    """主测试函数"""
    print("🚀 开始综合测试验证")
    print("=" * 60)
    
    test_results = []
    
    try:
        # 测试1: 资源稳定性
        result1 = await test_resource_stability()
        test_results.append(("资源稳定性", result1))
        
        # 测试2: 进程管理
        result2 = await test_process_management()
        test_results.append(("进程管理", result2))
        
        # 测试3: 错误恢复
        result3 = await test_error_recovery()
        test_results.append(("错误恢复", result3))
        
        # 测试4: 系统资源
        result4 = test_system_resources()
        test_results.append(("系统资源", result4))
        
        # 测试5: 调度器模拟
        result5 = await test_scheduler_simulation()
        test_results.append(("调度器模拟", result5))
        
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        logger.error(f"Comprehensive test failed: {e}")
        return 1
    
    # 显示测试结果
    print("\n" + "=" * 60)
    print("📊 综合测试结果:")
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(test_results)} 测试通过")
    
    if passed == len(test_results):
        print("🎉 所有测试通过！系统稳定性验证成功。")
        return 0
    else:
        print("⚠️  部分测试失败，需要进一步检查。")
        return 1


if __name__ == "__main__":
    import os
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        sys.exit(130)
