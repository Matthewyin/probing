# 网络诊断工具

> 一个专业的网络连接性和性能分析工具，支持TCP、TLS、HTTP诊断和网络路径追踪

## 🚀 快速开始

### 安装

```bash
# 1. 安装uv包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 安装项目依赖
cd network-diagnosis
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
uv run python batch_main.py -c targets.yaml  # 执行批量诊断
```

## ✨ 核心功能

| 功能 | 描述 | 输出信息 |
|------|------|----------|
| 🔍 **DNS解析分析** | 域名解析性能和详情 | 解析时间、多IP地址、DNS服务器 |
| 🔌 **TCP连接测试** | 测试目标主机连接性能 | 连接时间、本地/远程地址、Socket信息 |
| 🔒 **TLS/SSL分析** | 收集安全连接信息 | 协议版本、证书详情、加密套件 |
| 🌐 **HTTP响应检查** | 分析Web服务响应 | 状态码、响应头、响应时间 |
| 🛣️ **网络路径追踪** | 追踪网络路径 | 跳点信息、延迟统计、丢包率 |
| 📊 **批量诊断** | 同时诊断多个目标 | 汇总统计、性能分析、安全评估 |

## 📋 系统要求

- **Python**: 3.11 或更高版本
- **包管理器**: uv (推荐) 或 pip
- **操作系统**: Linux、macOS、Windows
- **网络权限**: 能够访问目标网络地址
- **可选工具**: mtr (用于高级网络路径追踪)

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

### JSON诊断报告

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
  "http_info": {
    "status_code": 200,
    "response_time_ms": 234.56
  }
}
```

### 批量诊断摘要

```
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

## 📚 文档

| 文档 | 描述 |
|------|------|
| [用户手册](USER_MANUAL.md) | 详细的使用指南和最佳实践 |
| [配置指南](CONFIG_USAGE.md) | 配置文件编写和参数说明 |
| [架构文档](ARCHITECTURE.md) | 技术架构和设计原理 |
| [项目总结](PROJECT_SUMMARY.md) | 功能概述和实现总结 |

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

