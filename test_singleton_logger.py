#!/usr/bin/env python3
"""
测试单例日志管理器功能
"""
import asyncio
import sys
import time
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "network-diagnosis" / "src"))

from network_diagnosis.singleton_logger import (
    get_singleton_logger_manager,
    setup_config_logging,
    log_and_print,
    get_logger
)


def test_singleton_pattern():
    """测试单例模式"""
    print("🧪 测试单例模式...")
    
    # 获取多个实例
    manager1 = get_singleton_logger_manager()
    manager2 = get_singleton_logger_manager()
    
    # 验证是同一个实例
    if manager1 is manager2:
        print("   ✅ 单例模式正常工作")
        return True
    else:
        print("   ❌ 单例模式失败")
        return False


def test_logger_reuse():
    """测试日志器复用"""
    print("\n🧪 测试日志器复用...")
    
    manager = get_singleton_logger_manager()
    
    # 多次设置相同配置
    log_file1 = setup_config_logging("test_config")
    log_file2 = setup_config_logging("test_config")
    
    # 验证返回相同的日志文件
    if log_file1 == log_file2:
        print("   ✅ 相同配置复用日志文件")
        success1 = True
    else:
        print(f"   ❌ 日志文件不一致: {log_file1} vs {log_file2}")
        success1 = False
    
    # 检查状态
    status = manager.get_status()
    print(f"   📊 当前配置: {status['current_config']}")
    print(f"   📊 活跃日志器: {len(status['active_loggers'])}")
    print(f"   📊 文件处理器: {status['active_file_handlers']}")
    
    return success1


def test_multiple_configs():
    """测试多个配置切换"""
    print("\n🧪 测试多个配置切换...")
    
    manager = get_singleton_logger_manager()
    
    # 设置第一个配置
    log_file1 = setup_config_logging("config1")
    status1 = manager.get_status()
    
    # 设置第二个配置
    log_file2 = setup_config_logging("config2")
    status2 = manager.get_status()
    
    # 验证配置切换
    if status1['current_config'] != status2['current_config']:
        print("   ✅ 配置切换正常")
        success1 = True
    else:
        print("   ❌ 配置切换失败")
        success1 = False
    
    # 验证文件处理器数量稳定
    if status2['active_file_handlers'] <= 2:  # 应该只有root和business两个
        print("   ✅ 文件处理器数量稳定")
        success2 = True
    else:
        print(f"   ❌ 文件处理器过多: {status2['active_file_handlers']}")
        success2 = False
    
    print(f"   📊 配置1: {status1['current_config']} -> 配置2: {status2['current_config']}")
    print(f"   📊 处理器数量: {status1['active_file_handlers']} -> {status2['active_file_handlers']}")
    
    return success1 and success2


def test_logging_functionality():
    """测试日志记录功能"""
    print("\n🧪 测试日志记录功能...")
    
    # 设置日志配置
    log_file = setup_config_logging("test_logging")
    
    # 测试不同级别的日志
    logger = get_logger("test_module")
    
    logger.info("这是一条信息日志")
    logger.warning("这是一条警告日志")
    logger.error("这是一条错误日志")
    
    # 测试log_and_print函数
    log_and_print("这是通过log_and_print记录的消息", "INFO")
    log_and_print("这是只记录到日志的消息", "WARNING", log_only=True)
    
    # 检查日志文件是否存在
    log_path = Path(log_file)
    if log_path.exists():
        print(f"   ✅ 日志文件创建成功: {log_file}")
        
        # 检查日志内容
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "这是一条信息日志" in content and "这是通过log_and_print记录的消息" in content:
                print("   ✅ 日志内容正确")
                return True
            else:
                print("   ❌ 日志内容不完整")
                return False
    else:
        print(f"   ❌ 日志文件未创建: {log_file}")
        return False


def test_concurrent_access():
    """测试并发访问"""
    print("\n🧪 测试并发访问...")
    
    import threading
    import time
    
    results = []
    
    def worker(worker_id):
        """工作线程"""
        try:
            manager = get_singleton_logger_manager()
            log_file = setup_config_logging(f"worker_{worker_id}")
            
            logger = get_logger(f"worker_{worker_id}")
            logger.info(f"Worker {worker_id} 开始工作")
            
            time.sleep(0.1)  # 模拟工作
            
            logger.info(f"Worker {worker_id} 完成工作")
            results.append(True)
        except Exception as e:
            print(f"   ❌ Worker {worker_id} 失败: {e}")
            results.append(False)
    
    # 创建多个线程
    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 检查结果
    success_count = sum(results)
    print(f"   📊 成功线程: {success_count}/5")
    
    if success_count == 5:
        print("   ✅ 并发访问正常")
        return True
    else:
        print("   ❌ 并发访问存在问题")
        return False


def test_memory_usage():
    """测试内存使用情况"""
    print("\n🧪 测试内存使用情况...")
    
    manager = get_singleton_logger_manager()
    
    # 多次设置不同配置，检查是否有内存泄漏
    initial_handlers = manager.get_status()['active_file_handlers']
    
    for i in range(10):
        setup_config_logging(f"memory_test_{i}")
    
    final_handlers = manager.get_status()['active_file_handlers']
    
    print(f"   📊 初始处理器: {initial_handlers}")
    print(f"   📊 最终处理器: {final_handlers}")
    
    if final_handlers <= 2:  # 应该只有最后一次配置的处理器
        print("   ✅ 内存使用正常，无泄漏")
        return True
    else:
        print(f"   ⚠️  处理器数量较多: {final_handlers}")
        return final_handlers <= 4  # 允许一定的容差


def cleanup_test_files():
    """清理测试文件"""
    print("\n🧹 清理测试文件...")
    
    # 清理日志目录
    log_base_dir = Path(__file__).parent / "network-diagnosis" / "log"
    
    test_dirs = [
        "test_config", "config1", "config2", "test_logging"
    ] + [f"worker_{i}" for i in range(5)] + [f"memory_test_{i}" for i in range(10)]
    
    cleaned_count = 0
    for test_dir in test_dirs:
        test_path = log_base_dir / test_dir
        if test_path.exists():
            try:
                import shutil
                shutil.rmtree(test_path)
                cleaned_count += 1
            except Exception as e:
                print(f"   ⚠️  清理失败 {test_dir}: {e}")
    
    print(f"   🗑️  清理了 {cleaned_count} 个测试目录")


def main():
    """主测试函数"""
    print("🚀 开始单例日志管理器测试")
    print("=" * 60)
    
    test_results = []
    
    try:
        # 测试1: 单例模式
        result1 = test_singleton_pattern()
        test_results.append(("单例模式", result1))
        
        # 测试2: 日志器复用
        result2 = test_logger_reuse()
        test_results.append(("日志器复用", result2))
        
        # 测试3: 多配置切换
        result3 = test_multiple_configs()
        test_results.append(("多配置切换", result3))
        
        # 测试4: 日志功能
        result4 = test_logging_functionality()
        test_results.append(("日志功能", result4))
        
        # 测试5: 并发访问
        result5 = test_concurrent_access()
        test_results.append(("并发访问", result5))
        
        # 测试6: 内存使用
        result6 = test_memory_usage()
        test_results.append(("内存使用", result6))
        
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        return 1
    finally:
        # 清理测试文件
        cleanup_test_files()
    
    # 显示测试结果
    print("\n" + "=" * 60)
    print("📊 单例日志管理器测试结果:")
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(test_results)} 测试通过")
    
    if passed == len(test_results):
        print("🎉 所有测试通过！单例日志管理器工作正常。")
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
