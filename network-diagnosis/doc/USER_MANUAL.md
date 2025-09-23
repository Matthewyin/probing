# 网络诊断工具用户使用手册

> 🚀 **企业级网络诊断和监控平台** - 完整的使用指南和最佳实践

## 📖 目录

1. [工具概述](#工具概述)
2. [快速开始](#快速开始)
3. [基础功能使用](#基础功能使用)
4. [企业级功能](#企业级功能)
5. [监控和告警](#监控和告警)
6. [自动恢复](#自动恢复)
7. [测试和验证](#测试和验证)
8. [故障排查](#故障排查)
9. [最佳实践](#最佳实践)
10. [生产部署](#生产部署)

## 1. 工具概述

### 什么是网络诊断工具？

网络诊断工具是一个**企业级网络诊断和监控平台**，集成了智能监控、自动恢复和高可用架构。它不仅能够对指定的域名、IP地址或URL进行全面的网络诊断，还提供了完整的系统监控、告警和自动恢复机制，确保长期稳定运行。

### 🌟 核心优势

- **🛡️ 企业级稳定性** - 零资源泄漏，可稳定运行数月
- **📊 智能监控** - 实时系统健康监控和告警
- **🔄 自动恢复** - 故障自动检测和恢复机制
- **⚡ 高性能** - 优化的架构设计，支持大规模并发
- **🧪 全面测试** - 30+测试用例确保功能可靠性

### 主要功能

#### 🔍 **网络诊断功能**

| 功能模块 | 描述 | 输出信息 |
|----------|------|----------|
| **DNS解析分析** | 域名解析性能和详情 | 解析时间、多IP地址、DNS服务器信息 |
| **TCP连接测试** | 测试目标主机的TCP连接性能 | 连接时间、本地/远程地址、Socket信息 |
| **TLS/SSL分析** | 收集TLS握手和证书信息 | 协议版本、加密套件、证书详情、有效期 |
| **HTTP响应检查** | 分析HTTP/HTTPS请求和响应 | 状态码、响应头、响应时间、重定向链 |
| **ICMP探测** | 使用ping命令测试网络连通性 | RTT统计、丢包率、数据包统计 |
| **网络路径追踪** | 追踪到目标的网络路径 | 跳点信息、延迟统计、丢包率、ASN信息 |
| **批量诊断** | 同时诊断多个目标 | 汇总统计、性能分析、安全评估 |

#### 🆕 **增强功能**

| 功能模块 | 描述 | 输出信息 |
|----------|------|----------|
| **HTTP头增强解析** | 提取源站信息和CDN检测 | 源站IP、CDN提供商、安全头分析 |
| **ICMP多IP拨测** | 并行测试所有DNS解析的IP | 多IP性能对比、最佳IP识别 |
| **MTR多IP拨测** | 并行路径追踪和路径对比 | 共同跳点、路径差异、性能分析 |

#### 🛡️ **企业级功能**

| 功能模块 | 描述 | 输出信息 |
|----------|------|----------|
| **单例日志管理** | 避免日志处理器泄漏 | 统一日志管理、资源复用 |
| **智能监控系统** | 实时系统健康监控 | 告警阈值、通知机制、数据持久化 |
| **自动恢复机制** | 故障自动检测和恢复 | 多种恢复策略、冷却机制、状态监控 |
| **定时任务调度** | 自动化定期监控 | 灵活调度、配置热重载、历史记录 |

## 2. 快速开始

### 2.1 安装

```bash
# 1. 安装uv包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆项目并安装依赖
git clone https://github.com/Matthewyin/probing.git
cd probing
uv sync

# 3. 运行第一个诊断
uv run python main.py google.com
```

### 2.2 基本使用

```bash
# 诊断HTTPS网站
uv run python main.py github.com

# 诊断HTTP网站
uv run python main.py httpbin.org --port 80

# 批量诊断多个目标
uv run python batch_main.py --create-sample  # 创建配置文件
uv run python batch_main.py -c network-diagnosis/input/targets.yaml

# 定时任务功能
uv run python scheduler_main.py --status -c input/targets_sample.yaml
uv run python scheduler_main.py -c input/targets_sample.yaml

# 系统监控和测试
uv run python comprehensive_test.py           # 运行完整系统测试
uv run python test_phase3_integration.py     # 运行集成测试
```

### 2.3 验证安装

```bash
# 快速验证系统状态
uv run python -c "
import sys
sys.path.insert(0, 'network-diagnosis/src')
from network_diagnosis.enhanced_monitor import get_enhanced_monitor
from network_diagnosis.auto_recovery import get_auto_recovery_system
monitor = get_enhanced_monitor()
recovery = get_auto_recovery_system()
print('✅ 监控系统状态:', monitor.get_status()['monitoring_enabled'])
print('✅ 恢复系统状态:', recovery.get_status()['enabled'])
print('🎉 系统安装成功！')
"
```

## 3. 基础功能使用

### 3.1 单目标诊断

```bash
# 基本诊断
uv run python main.py example.com

# 指定端口
uv run python main.py example.com --port 8080

# 详细输出
uv run python main.py example.com --verbose

# 保存结果到文件
uv run python main.py example.com --output results.json
```

### 3.2 批量诊断

#### 创建配置文件

```bash
# 创建示例配置文件
uv run python batch_main.py --create-sample
```

#### 配置文件示例

```yaml
targets:
  - domain: "google.com"
    port: 443
    description: "Google搜索引擎"
  
  - domain: "httpbin.org"
    port: 80
    description: "HTTP测试服务"

global_settings:
  max_concurrent: 3      # 并发数 (1-10)
  timeout_seconds: 60    # 超时时间
  save_summary_report: true

# 🆕 调度器配置
scheduler:
  enabled: true
  trigger_type: "cron"   # 或 "interval"
  cron: "0 */2 * * *"    # 每2小时执行一次
  # interval_minutes: 30 # 或每30分钟执行一次
```

#### 执行批量诊断

```bash
# 执行批量诊断
uv run python batch_main.py -c network-diagnosis/input/targets.yaml

# 启动定时任务
uv run python scheduler_main.py -c network-diagnosis/input/targets.yaml

# 查看调度器状态
uv run python scheduler_main.py --status -c network-diagnosis/input/targets.yaml
```

### 3.3 输出结果解读

#### JSON诊断报告

```json
{
  "domain": "example.com",
  "target_ip": "93.184.216.34",
  "success": true,
  "total_time_ms": 567.89,
  "tcp_connection": {
    "connect_time_ms": 45.23,
    "is_connected": true
  },
  "tls_info": {
    "protocol_version": "TLSv1.3",
    "cipher_suite": "TLS_AES_256_GCM_SHA384"
  },
  "http_response": {
    "status_code": 200,
    "response_time_ms": 234.56,
    "origin_info": {
      "real_ip": "192.168.1.100",
      "cdn_provider": "cloudflare"
    }
  },
  "multi_ip_icmp": {
    "tested_ips": ["1.2.3.4", "5.6.7.8"],
    "summary": {
      "success_rate": 1.0,
      "best_performing_ip": "1.2.3.4"
    }
  }
}
```

## 4. 企业级功能

### 4.1 单例日志管理

#### 特性说明

- **零资源泄漏**: 完全解决"Too many open files"问题
- **线程安全**: 支持并发访问的单例模式
- **配置复用**: 避免重复创建日志处理器
- **自动清理**: 智能资源管理和释放

#### 使用方式

```python
from network_diagnosis.singleton_logger import get_singleton_logger_manager

# 获取单例日志管理器
logger_manager = get_singleton_logger_manager()

# 获取配置好的日志器
logger = logger_manager.get_logger("my_module")

# 使用日志器
logger.info("这是一条日志消息")
```

### 4.2 智能监控系统

#### 特性说明

- **实时监控**: 系统资源、进程状态、性能指标
- **智能告警**: 可配置阈值、多级告警、自动通知
- **数据持久化**: 完整的监控数据和告警历史
- **多种通知**: 日志、文件、邮件等通知方式

#### 使用方式

```python
from network_diagnosis.enhanced_monitor import get_enhanced_monitor

# 获取监控系统
monitor = get_enhanced_monitor()

# 获取系统状态
status = monitor.get_status()
print(f"监控状态: {status['monitoring_enabled']}")

# 收集指标
metrics = monitor.collect_metrics()
print(f"当前指标: {metrics}")

# 检查告警
alerts = monitor.check_thresholds(metrics)
for alert in alerts:
    print(f"告警: {alert.message}")
```

#### 配置告警阈值

```python
from network_diagnosis.enhanced_monitor import AlertThreshold

# 配置自定义阈值
thresholds = [
    AlertThreshold(
        metric_name="open_files",
        warning_threshold=100,
        critical_threshold=200,
        comparison="greater"
    ),
    AlertThreshold(
        metric_name="memory_usage_mb",
        warning_threshold=500,
        critical_threshold=1000,
        comparison="greater"
    )
]

# 应用配置
monitor.configure_thresholds(thresholds)
```

### 4.3 自动恢复机制

#### 特性说明

- **故障检测**: 自动识别系统异常和资源问题
- **智能恢复**: 多种恢复策略（资源清理、服务重启等）
- **冷却机制**: 防止频繁恢复操作
- **状态监控**: 完整的恢复历史和状态跟踪

#### 使用方式

```python
from network_diagnosis.auto_recovery import get_auto_recovery_system

# 获取自动恢复系统
recovery = get_auto_recovery_system()

# 获取系统状态
status = recovery.get_status()
print(f"恢复系统状态: {status['enabled']}")

# 手动触发恢复检查
await recovery.check_and_recover()

# 获取恢复历史
history = recovery.get_recovery_history()
for attempt in history:
    print(f"恢复尝试: {attempt.action} - {attempt.success}")
```

#### 配置恢复规则

```python
from network_diagnosis.auto_recovery import RecoveryRule, RecoveryAction

# 配置恢复规则
rules = [
    RecoveryRule(
        name="high_file_handles",
        trigger_condition="open_files > 150",
        action=RecoveryAction.CLEANUP_RESOURCES,
        max_attempts=3,
        cooldown_seconds=300
    ),
    RecoveryRule(
        name="memory_leak",
        trigger_condition="memory_usage_mb > 800",
        action=RecoveryAction.RESTART_LOGGING,
        max_attempts=2,
        cooldown_seconds=600
    )
]

# 应用配置
recovery.configure_rules(rules)
```

## 5. 监控和告警

### 5.1 监控数据

#### 系统指标

- **open_files**: 当前打开的文件数量
- **file_handlers**: 日志文件处理器数量
- **active_processes**: 活跃进程数量
- **memory_usage_mb**: 内存使用量（MB）
- **cpu_usage_percent**: CPU使用率

#### 数据存储

监控数据存储在 `network-diagnosis/monitoring_data/` 目录：

- **metrics.jsonl**: 系统指标数据（JSON Lines格式）
- **alerts.jsonl**: 告警事件记录（JSON Lines格式）

#### 查看监控数据

```bash
# 查看最新指标
tail -f network-diagnosis/monitoring_data/metrics.jsonl

# 查看告警历史
tail -f network-diagnosis/monitoring_data/alerts.jsonl

# 分析监控数据
cat network-diagnosis/monitoring_data/metrics.jsonl | jq '.'
```

### 5.2 告警配置

#### 默认告警阈值

```python
DEFAULT_THRESHOLDS = [
    AlertThreshold("open_files", 100, 200, "greater"),
    AlertThreshold("file_handlers", 10, 20, "greater"),
    AlertThreshold("active_processes", 50, 100, "greater"),
    AlertThreshold("memory_usage_mb", 500, 1000, "greater"),
    AlertThreshold("cpu_usage_percent", 80, 95, "greater")
]
```

#### 自定义告警

```python
# 创建自定义告警阈值
custom_threshold = AlertThreshold(
    metric_name="custom_metric",
    warning_threshold=50.0,
    critical_threshold=80.0,
    comparison="greater",
    enabled=True
)

# 添加到监控系统
monitor.add_threshold(custom_threshold)
```

## 6. 自动恢复

### 6.1 恢复策略

#### 可用的恢复动作

- **CLEANUP_RESOURCES**: 清理系统资源
- **RESTART_LOGGING**: 重启日志系统
- **KILL_PROCESSES**: 终止异常进程
- **EMERGENCY_SHUTDOWN**: 紧急关闭系统

#### 恢复规则配置

```python
# 高文件句柄数恢复规则
high_files_rule = RecoveryRule(
    name="high_file_handles",
    trigger_condition="open_files > 150",
    action=RecoveryAction.CLEANUP_RESOURCES,
    max_attempts=3,
    cooldown_seconds=300,
    enabled=True
)

# 内存泄漏恢复规则
memory_leak_rule = RecoveryRule(
    name="memory_leak",
    trigger_condition="memory_usage_mb > 800",
    action=RecoveryAction.RESTART_LOGGING,
    max_attempts=2,
    cooldown_seconds=600,
    enabled=True
)
```

### 6.2 恢复历史

#### 查看恢复历史

```python
# 获取恢复历史
recovery_system = get_auto_recovery_system()
history = recovery_system.get_recovery_history()

for attempt in history:
    print(f"时间: {attempt.timestamp}")
    print(f"规则: {attempt.rule_name}")
    print(f"动作: {attempt.action}")
    print(f"成功: {attempt.success}")
    print(f"消息: {attempt.message}")
    print("---")
```

#### 恢复统计

```python
# 获取恢复统计
stats = recovery_system.get_recovery_stats()
print(f"总恢复尝试: {stats['total_attempts']}")
print(f"成功恢复: {stats['successful_recoveries']}")
print(f"失败恢复: {stats['failed_recoveries']}")
print(f"成功率: {stats['success_rate']:.2%}")
```

## 7. 测试和验证

### 7.1 运行测试套件

```bash
# 运行完整系统测试
uv run python comprehensive_test.py

# 运行单例日志管理器测试
uv run python test_singleton_logger.py

# 运行增强监控系统测试
uv run python test_enhanced_monitor.py

# 运行自动恢复机制测试
uv run python test_auto_recovery.py

# 运行集成测试
uv run python test_phase3_integration.py
```

### 7.2 测试结果解读

#### 成功的测试输出

```
✅ 单例日志管理器测试: 6/6 通过
✅ 增强监控系统测试: 8/8 通过
✅ 自动恢复机制测试: 9/9 通过
✅ 集成测试: 7/7 通过

🎉 所有测试通过！系统运行正常。
```

#### 测试失败处理

如果测试失败，请检查：

1. **依赖安装**: 确保所有依赖正确安装
2. **权限问题**: 确保有足够的文件和网络权限
3. **资源限制**: 检查系统资源限制
4. **配置问题**: 验证配置文件格式正确

### 7.3 性能测试

```bash
# 运行性能测试
uv run python -c "
import time
import sys
sys.path.insert(0, 'network-diagnosis/src')
from network_diagnosis.enhanced_monitor import get_enhanced_monitor

monitor = get_enhanced_monitor()
start_time = time.time()

# 收集100次指标
for i in range(100):
    metrics = monitor.collect_metrics()

end_time = time.time()
avg_time = (end_time - start_time) / 100 * 1000

print(f'平均指标收集时间: {avg_time:.2f}ms')
print('✅ 性能测试通过' if avg_time < 10 else '❌ 性能测试失败')
"
```

## 8. 故障排查

### 8.1 常见问题

#### "Too many open files" 错误

**症状**: 系统报告文件句柄耗尽

**解决方案**:
```bash
# 检查当前文件句柄使用情况
uv run python -c "
import sys
sys.path.insert(0, 'network-diagnosis/src')
from network_diagnosis.resource_monitor import ResourceMonitor
monitor = ResourceMonitor()
status = monitor.get_comprehensive_status()
print(f'文件句柄使用: {status[\"file_handles\"]}')
print(f'系统状态: {status[\"overall_status\"]}')
"

# 手动触发资源清理
uv run python -c "
import sys
sys.path.insert(0, 'network-diagnosis/src')
from network_diagnosis.auto_recovery import get_auto_recovery_system
recovery = get_auto_recovery_system()
import asyncio
asyncio.run(recovery.check_and_recover())
"
```

#### 监控系统无响应

**症状**: 监控数据不更新

**解决方案**:
```bash
# 重启监控系统
uv run python -c "
import sys
sys.path.insert(0, 'network-diagnosis/src')
from network_diagnosis.enhanced_monitor import get_enhanced_monitor
monitor = get_enhanced_monitor()
monitor.restart()
print('✅ 监控系统已重启')
"
```

#### 自动恢复不工作

**症状**: 系统异常但未自动恢复

**解决方案**:
```bash
# 检查恢复系统状态
uv run python -c "
import sys
sys.path.insert(0, 'network-diagnosis/src')
from network_diagnosis.auto_recovery import get_auto_recovery_system
recovery = get_auto_recovery_system()
status = recovery.get_status()
print(f'恢复系统启用: {status[\"enabled\"]}')
print(f'活跃规则数: {len(status[\"active_rules\"])}')
for rule in status['active_rules']:
    print(f'  - {rule}')
"
```

### 8.2 日志分析

#### 查看系统日志

```bash
# 查看应用日志
tail -f network-diagnosis/log/app.log

# 查看错误日志
tail -f network-diagnosis/log/error.log

# 查看监控日志
tail -f network-diagnosis/log/monitor.log
```

#### 日志级别调整

```python
# 设置详细日志级别
import logging
logging.getLogger().setLevel(logging.DEBUG)

# 或在环境变量中设置
export LOG_LEVEL=DEBUG
```

### 8.3 系统健康检查

```bash
# 完整的系统健康检查
uv run python -c "
import sys
sys.path.insert(0, 'network-diagnosis/src')

# 检查单例日志管理器
from network_diagnosis.singleton_logger import get_singleton_logger_manager
logger_manager = get_singleton_logger_manager()
print(f'✅ 日志管理器状态: {logger_manager.get_status()[\"initialized\"]}')

# 检查监控系统
from network_diagnosis.enhanced_monitor import get_enhanced_monitor
monitor = get_enhanced_monitor()
print(f'✅ 监控系统状态: {monitor.get_status()[\"monitoring_enabled\"]}')

# 检查恢复系统
from network_diagnosis.auto_recovery import get_auto_recovery_system
recovery = get_auto_recovery_system()
print(f'✅ 恢复系统状态: {recovery.get_status()[\"enabled\"]}')

# 检查资源状态
from network_diagnosis.resource_monitor import ResourceMonitor
resource_monitor = ResourceMonitor()
status = resource_monitor.get_comprehensive_status()
print(f'✅ 系统整体状态: {status[\"overall_status\"]}')

print('🎉 系统健康检查完成！')
"
```

## 9. 最佳实践

### 9.1 生产环境配置

#### 监控阈值配置

```python
# 生产环境推荐阈值
PRODUCTION_THRESHOLDS = [
    AlertThreshold("open_files", 200, 400, "greater"),
    AlertThreshold("file_handlers", 20, 50, "greater"),
    AlertThreshold("active_processes", 100, 200, "greater"),
    AlertThreshold("memory_usage_mb", 1000, 2000, "greater"),
    AlertThreshold("cpu_usage_percent", 70, 90, "greater")
]
```

#### 恢复策略配置

```python
# 生产环境恢复规则
PRODUCTION_RECOVERY_RULES = [
    RecoveryRule(
        name="critical_file_handles",
        trigger_condition="open_files > 350",
        action=RecoveryAction.CLEANUP_RESOURCES,
        max_attempts=5,
        cooldown_seconds=180
    ),
    RecoveryRule(
        name="memory_pressure",
        trigger_condition="memory_usage_mb > 1500",
        action=RecoveryAction.RESTART_LOGGING,
        max_attempts=3,
        cooldown_seconds=300
    )
]
```

### 9.2 性能优化

#### 并发配置

```yaml
# 批量诊断性能配置
global_settings:
  max_concurrent: 5          # 根据系统性能调整
  timeout_seconds: 30        # 适当的超时时间
  save_summary_report: true
  
# 调度器性能配置
scheduler:
  enabled: true
  trigger_type: "cron"
  cron: "0 */1 * * *"        # 根据需求调整频率
```

#### 资源限制

```bash
# 设置系统资源限制
ulimit -n 4096              # 增加文件句柄限制
ulimit -u 2048              # 增加进程数限制
```

### 9.3 监控策略

#### 关键指标监控

1. **文件句柄使用率**: 监控 `open_files` 指标
2. **内存使用情况**: 监控 `memory_usage_mb` 指标
3. **进程健康状态**: 监控 `active_processes` 指标
4. **系统响应时间**: 监控诊断执行时间

#### 告警策略

1. **分级告警**: 设置警告和严重两级阈值
2. **告警抑制**: 配置适当的冷却时间
3. **告警聚合**: 避免告警风暴
4. **告警路由**: 不同级别告警发送给不同人员

## 10. 生产部署

### 10.1 部署前检查

```bash
# 1. 运行完整测试套件
uv run python comprehensive_test.py

# 2. 检查系统资源
uv run python -c "
import psutil
print(f'CPU核心数: {psutil.cpu_count()}')
print(f'内存总量: {psutil.virtual_memory().total // (1024**3)}GB')
print(f'磁盘空间: {psutil.disk_usage(\"/\").free // (1024**3)}GB')
"

# 3. 验证网络连接
uv run python main.py google.com
```

### 10.2 部署配置

#### 环境变量配置

```bash
# 创建生产环境配置
cp .env.example .env

# 编辑环境变量
cat > .env << EOF
LOG_LEVEL=INFO
MAX_CONCURRENT=5
TIMEOUT_SECONDS=30
MONITORING_ENABLED=true
AUTO_RECOVERY_ENABLED=true
ALERT_COOLDOWN_SECONDS=300
EOF
```

#### 系统服务配置

```bash
# 创建systemd服务文件
sudo tee /etc/systemd/system/network-diagnosis.service << EOF
[Unit]
Description=Network Diagnosis Tool
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/probing
ExecStart=/path/to/uv run python scheduler_main.py -c network-diagnosis/input/targets.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启用并启动服务
sudo systemctl enable network-diagnosis
sudo systemctl start network-diagnosis
```

### 10.3 监控和维护

#### 日常监控

```bash
# 检查服务状态
sudo systemctl status network-diagnosis

# 查看实时日志
sudo journalctl -u network-diagnosis -f

# 检查系统健康
uv run python -c "
import sys
sys.path.insert(0, 'network-diagnosis/src')
from network_diagnosis.resource_monitor import ResourceMonitor
monitor = ResourceMonitor()
status = monitor.get_comprehensive_status()
print(f'系统状态: {status[\"overall_status\"]}')
"
```

#### 定期维护

```bash
# 每周执行的维护任务
#!/bin/bash

# 1. 清理旧日志文件
find network-diagnosis/log -name "*.log" -mtime +7 -delete

# 2. 清理旧监控数据
find network-diagnosis/monitoring_data -name "*.jsonl" -mtime +30 -delete

# 3. 运行系统测试
uv run python comprehensive_test.py

# 4. 检查系统状态
uv run python -c "
import sys
sys.path.insert(0, 'network-diagnosis/src')
from network_diagnosis.resource_monitor import ResourceMonitor
monitor = ResourceMonitor()
status = monitor.get_comprehensive_status()
if status['overall_status'] != 'healthy':
    print('⚠️ 系统状态异常，需要检查')
    exit(1)
else:
    print('✅ 系统状态正常')
"
```

### 10.4 备份和恢复

#### 数据备份

```bash
# 备份配置文件
tar -czf backup-$(date +%Y%m%d).tar.gz \
    network-diagnosis/input/ \
    network-diagnosis/monitoring_data/ \
    .env

# 备份到远程位置
rsync -av backup-*.tar.gz user@backup-server:/backup/network-diagnosis/
```

#### 灾难恢复

```bash
# 恢复配置
tar -xzf backup-20240923.tar.gz

# 重启服务
sudo systemctl restart network-diagnosis

# 验证恢复
uv run python comprehensive_test.py
```

---

**🎉 本用户手册提供了网络诊断工具的完整使用指南，包括基础功能、企业级特性、监控告警、故障排查和生产部署的最佳实践。**
