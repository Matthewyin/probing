# 网络诊断工具

> 🚀 **企业级网络诊断和监控平台** - 集成智能监控、自动恢复和高可用架构的专业网络分析工具

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

## 🌟 核心特性

### 🔧 **企业级稳定性**
- ✅ **零资源泄漏** - 完全解决"Too many open files"问题
- ✅ **智能监控** - 实时系统健康监控和告警
- ✅ **自动恢复** - 故障自动检测和恢复机制
- ✅ **长期运行** - 可稳定运行数月无需人工干预

### 🚀 **高性能诊断**
- 🔍 **全面诊断** - TCP、TLS、HTTP、DNS、网络路径一站式分析
- 🌐 **多IP并行** - 智能并行测试所有解析IP地址
- 📊 **批量处理** - 高效批量诊断多个目标
- ⏰ **定时任务** - 自动化定期监控

### 🛡️ **智能监控**
- 📈 **实时监控** - 系统资源和性能指标监控
- 🚨 **智能告警** - 可配置阈值和多种通知方式
- 🔄 **自动恢复** - 多种恢复策略和故障自愈
- 📊 **数据持久化** - 完整的监控数据和告警历史

## 🚀 快速开始

### 安装

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

### 基本使用

```bash
# 诊断HTTPS网站
uv run python main.py github.com

# 诊断HTTP网站
uv run python main.py httpbin.org --port 80

# 批量诊断多个目标
uv run python batch_main.py --create-sample  # 创建配置文件
uv run python batch_main.py -c network-diagnosis/input/targets.yaml  # 执行批量诊断

# 🆕 定时任务功能
uv run python scheduler_main.py --status -c input/targets_sample.yaml  # 查看调度器状态
uv run python scheduler_main.py -c input/targets_sample.yaml           # 启动定时任务

# 🆕 系统监控和测试
uv run python comprehensive_test.py           # 运行完整系统测试
uv run python test_phase3_integration.py     # 运行集成测试
```

## ✨ 功能矩阵

### 🔍 **网络诊断功能**

| 功能 | 描述 | 输出信息 |
|------|------|----------|
| 🔍 **DNS解析分析** | 域名解析性能和详情 | 解析时间、多IP地址、DNS服务器 |
| 🔌 **TCP连接测试** | 测试目标主机连接性能 | 连接时间、本地/远程地址、Socket信息 |
| 🔒 **TLS/SSL分析** | 收集安全连接信息 | 协议版本、证书详情、加密套件 |
| 🌐 **HTTP响应检查** | 分析Web服务响应 | 状态码、响应头、响应时间 |
| 🛣️ **网络路径追踪** | 追踪网络路径 | 跳点信息、延迟统计、丢包率 |
| 📊 **批量诊断** | 同时诊断多个目标 | 汇总统计、性能分析、安全评估 |
| ⏰ **定时任务** | 定时执行批量诊断 | 自动调度、配置热重载、历史记录 |

### 🆕 **增强功能**

| 功能 | 描述 | 输出信息 |
|------|------|----------|
| 🆕 **HTTP头增强解析** | 提取源站信息和CDN检测 | 源站IP、CDN提供商、安全头分析 |
| 🆕 **ICMP多IP拨测** | 并行测试所有DNS解析的IP | 多IP性能对比、最佳IP识别 |
| 🆕 **MTR多IP拨测** | 并行路径追踪和路径对比 | 共同跳点、路径差异、性能分析 |

### 🛡️ **企业级功能**

| 功能 | 描述 | 输出信息 |
|------|------|----------|
| 🔧 **单例日志管理** | 避免日志处理器泄漏 | 统一日志管理、资源复用 |
| 📊 **智能监控系统** | 实时系统健康监控 | 告警阈值、通知机制、数据持久化 |
| 🔄 **自动恢复机制** | 故障自动检测和恢复 | 多种恢复策略、冷却机制、状态监控 |
| 🧪 **综合测试套件** | 完整的功能验证 | 30+测试用例、集成测试、性能验证 |

## 📋 系统要求

- **Python**: 3.11 或更高版本
- **包管理器**: uv (推荐) 或 pip
- **操作系统**: Linux、macOS、Windows
- **网络权限**: 能够访问目标网络地址
- **可选工具**: mtr (用于高级网络路径追踪)

## 📁 项目结构

```text
probing/
├── .env                    # 环境变量配置（需要创建）
├── .env.example           # 环境变量模板
├── .python-version        # Python版本文件
├── pyproject.toml         # uv项目配置
├── uv.lock               # 依赖锁定文件
├── main.py               # 单目标诊断主程序
├── batch_main.py         # 批量诊断主程序
├── scheduler_main.py     # 定时任务主程序
├── comprehensive_test.py # 综合测试脚本
├── test_*.py            # 各功能模块测试脚本
├── README.md            # 项目说明
└── network-diagnosis/   # 网络诊断工具目录
    ├── src/            # 源代码
    │   └── network_diagnosis/
    │       ├── config.py           # 配置管理
    │       ├── models.py           # 数据模型
    │       ├── services.py         # 核心服务
    │       ├── diagnosis.py        # 诊断协调器
    │       ├── batch_runner.py     # 批量运行器
    │       ├── scheduler_runner.py # 调度器
    │       ├── config_loader.py    # 配置加载器
    │       ├── logger.py           # 传统日志系统
    │       ├── 🆕 singleton_logger.py  # 单例日志管理器
    │       ├── 🆕 enhanced_monitor.py  # 增强监控系统
    │       ├── 🆕 auto_recovery.py     # 自动恢复机制
    │       ├── resource_monitor.py     # 资源监控
    │       └── process_manager.py      # 进程管理器
    ├── doc/                # 文档目录
    ├── input/              # 配置文件目录
    ├── output/             # 输出结果目录
    ├── log/                # 日志目录
    └── 🆕 monitoring_data/ # 监控数据目录
        ├── metrics.jsonl   # 系统指标数据
        └── alerts.jsonl    # 告警事件记录
```

### 配置文件示例

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
```

## 📊 输出格式

### 增强功能JSON诊断报告

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
      "cdn_provider": "cloudflare",
      "possible_origin_ips": ["192.168.1.100"]
    },
    "header_analysis": {
      "security_headers": {"x-frame-options": "DENY"},
      "custom_headers_count": 5
    }
  },
  "multi_ip_icmp": {
    "tested_ips": ["1.2.3.4", "5.6.7.8"],
    "summary": {
      "success_rate": 1.0,
      "best_performing_ip": "1.2.3.4"
    }
  },
  "multi_ip_network_path": {
    "tested_ips": ["1.2.3.4", "5.6.7.8"],
    "summary": {
      "common_hops": ["192.168.1.1"],
      "unique_paths": 2
    }
  }
}
```

### 批量诊断摘要

```text
================================================================================
批量网络诊断结果摘要
================================================================================
总目标数: 5
成功诊断: 4
失败诊断: 1
成功率: 80.0%

性能统计:
  平均诊断时间: 372.13ms
  平均TCP连接时间: 1.40ms

安全统计:
  启用TLS连接: 3
  TLS协议分布: TLSv1.3: 3
================================================================================
```

## 🆕 功能增强亮点

### 🌐 HTTP头信息增强解析

- **源站信息提取**：自动识别X-Real-IP、X-Forwarded-For等头信息
- **CDN检测**：智能识别Cloudflare、AWS CloudFront、Azure CDN等提供商
- **安全头分析**：分析X-Frame-Options、CSP等安全相关头信息
- **性能头分析**：Cache-Control、ETag等缓存和性能相关头信息

### 🔍 ICMP多IP拨测

- **并行测试**：对DNS解析的所有IP地址进行并行ping测试
- **性能对比**：自动识别最佳性能的IP地址
- **统计分析**：提供详细的RTT统计和丢包率分析
- **智能切换**：单IP域名使用传统逻辑，多IP域名自动启用并行测试

### 🛣️ MTR多IP拨测

- **并行路径追踪**：对所有IP地址进行并行网络路径追踪
- **路径对比分析**：识别共同跳点和路径差异
- **性能统计**：提供最短路径、最快路径等统计信息
- **向后兼容**：保持现有单IP测试逻辑不变

## 🛡️ 企业级架构特性

### 🔧 单例日志管理

- **零资源泄漏**：完全解决"Too many open files"问题
- **线程安全**：支持并发访问的单例模式
- **配置复用**：避免重复创建日志处理器
- **自动清理**：智能资源管理和释放

### 📊 智能监控系统

- **实时监控**：系统资源、进程状态、性能指标
- **智能告警**：可配置阈值、多级告警、自动通知
- **数据持久化**：完整的监控数据和告警历史
- **多种通知**：日志、文件、邮件等通知方式

### 🔄 自动恢复机制

- **故障检测**：自动识别系统异常和资源问题
- **智能恢复**：多种恢复策略（资源清理、服务重启等）
- **冷却机制**：防止频繁恢复操作
- **状态监控**：完整的恢复历史和状态跟踪

### 🧪 综合测试套件

- **30+测试用例**：覆盖所有核心功能
- **集成测试**：验证组件间协作
- **性能测试**：确保高性能运行
- **稳定性测试**：长期运行验证

## 📚 文档

| 文档 | 描述 |
|------|------|
| [用户手册](network-diagnosis/doc/USER_MANUAL.md) | 详细的使用指南和最佳实践 |
| [架构文档](network-diagnosis/doc/ARCHITECTURE.md) | 技术架构和设计原理 |

## 🔧 环境配置

复制环境变量模板并根据需要修改：

```bash
cp .env.example .env
# 编辑 .env 文件设置你的配置
```

## ⏰ 定时任务功能

网络诊断工具现在支持定时任务功能，可以按照配置的时间间隔自动执行批量网络诊断：

### 主要特性

- ✅ **多种触发方式**: 支持cron表达式和间隔时间
- ✅ **配置热重载**: 无需重启即可更新调度配置
- ✅ **向后兼容**: 完全保留原有功能
- ✅ **轻量化设计**: 基于APScheduler，简单易用

### 快速开始

```bash
# 1. 创建包含调度器配置的示例文件
uv run python batch_main.py --create-sample

# 2. 启用调度器（编辑配置文件）
# scheduler:
#   enabled: true
#   trigger_type: "cron"
#   cron: "0 */2 * * *"  # 每2小时执行一次

# 3. 启动定时任务
uv run python scheduler_main.py -c input/targets_sample.yaml
```

## 🧪 测试和验证

### 运行测试套件

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

### 系统健康检查

```bash
# 检查系统状态
uv run python -c "
import sys
sys.path.insert(0, 'network-diagnosis/src')
from network_diagnosis.enhanced_monitor import get_enhanced_monitor
from network_diagnosis.auto_recovery import get_auto_recovery_system
monitor = get_enhanced_monitor()
recovery = get_auto_recovery_system()
print('监控系统状态:', monitor.get_status()['monitoring_enabled'])
print('恢复系统状态:', recovery.get_status()['enabled'])
"
```

## 🚀 生产部署

### 部署检查清单

- ✅ 运行完整测试套件确保功能正常
- ✅ 配置适当的监控阈值和告警规则
- ✅ 设置自动恢复策略和冷却时间
- ✅ 配置日志轮转和存储策略
- ✅ 设置系统资源监控和告警

### 长期运行建议

- 📊 定期检查监控数据和告警历史
- 🔧 根据实际使用情况调整阈值配置
- 📈 监控系统性能和资源使用趋势
- 🛡️ 定期更新和维护恢复策略

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。