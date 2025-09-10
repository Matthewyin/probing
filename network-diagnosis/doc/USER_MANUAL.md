# 网络诊断工具用户使用手册

## 📖 目录

1. [工具概述](#工具概述)
2. [安装和环境配置](#安装和环境配置)
3. [单目标诊断](#单目标诊断)
4. [批量诊断](#批量诊断)
5. [输出结果解读](#输出结果解读)
6. [常见问题排查](#常见问题排查)
7. [高级用法](#高级用法)
8. [性能优化](#性能优化)
9. [生产环境部署](#生产环境部署)

## 🎯 工具概述

### 什么是网络诊断工具？

网络诊断工具是一个专业的网络连接性和性能分析工具，能够对指定的域名、IP地址或URL进行全面的网络诊断，包括DNS解析、TCP连接测试、TLS/SSL安全分析、HTTP响应检查、网络路径追踪和公网IP信息收集。

### 主要功能

| 功能模块 | 描述 | 输出信息 |
|----------|------|----------|
| **DNS解析分析** | 域名解析性能和详情 | 解析时间、IP地址、DNS服务器信息 |
| **TCP连接测试** | 测试目标主机的TCP连接性能 | 连接时间、本地/远程地址、Socket信息 |
| **TLS/SSL分析** | 收集TLS握手和证书信息 | 协议版本、加密套件、证书详情、有效期 |
| **HTTP响应检查** | 分析HTTP/HTTPS请求和响应 | 状态码、响应头、响应时间、重定向链 |
| **网络路径追踪** | 追踪到目标的网络路径（mtr/traceroute） | 跳点信息、延迟统计、丢包率、ASN信息 |
| **公网IP信息** | 收集发起端公网IP地理位置信息 | IP地址、地理位置、ISP信息 |
| **URL检测** | 支持直接URL诊断 | 自动解析域名和端口，支持HTTP/HTTPS |
| **批量诊断** | 同时诊断多个目标 | 汇总统计、性能分析、安全评估 |

### 适用场景

- **网站性能监控**：定期检查网站的连接性能和安全状态
- **网络故障排查**：诊断网络连接问题和性能瓶颈
- **安全审计**：检查TLS配置和证书状态
- **服务器监控**：批量监控多个服务器的健康状态
- **网络基础设施评估**：分析网络路径和性能特征
- **API接口监控**：监控API服务的可用性和响应时间
- **CDN性能分析**：分析内容分发网络的性能表现

## 🛠️ 安装和环境配置

### 系统要求

- **操作系统**：Linux、macOS、Windows
- **Python版本**：3.11 或更高版本
- **网络权限**：能够访问目标网络地址
- **可选工具**：mtr（用于高级网络路径追踪）

### 安装步骤

#### 1. 安装uv包管理器

uv是现代化的Python包管理器，提供更快的依赖解析和安装速度。

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**验证安装:**
```bash
uv --version
```

#### 2. 获取项目代码

```bash
# 克隆项目到本地
git clone https://github.com/Matthewyin/probing.git
cd probing
```

#### 3. 安装项目依赖

```bash
# uv会自动创建虚拟环境并安装依赖
uv sync

# 或者手动安装依赖
uv add pydantic-settings httpx cryptography python-dotenv pyyaml
```

#### 4. 环境配置

创建环境配置文件：

```bash
# 复制环境变量模板（在项目根目录）
cp .env.example .env

# 编辑配置文件
nano .env
```

**.env 文件示例:**

```bash
# 应用配置
APP_NAME="Network Diagnosis Tool"
APP_VERSION="1.0.0"
DEBUG=false

# 网络配置
CONNECT_TIMEOUT=10
READ_TIMEOUT=30
MAX_REDIRECTS=5

# 输出配置
OUTPUT_DIR="./network-diagnosis/output"

# 日志配置
LOG_LEVEL="INFO"
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 系统配置（已弃用，现使用sudoers配置）
# SUDO_PASSWORD="your_password"
```

#### 5. 验证安装

```bash
# 测试基本功能
uv run python main.py --help

# 运行简单诊断
uv run python main.py google.com --no-trace
```

### 可选工具安装

#### 安装mtr（强烈推荐）

mtr提供更详细的网络路径追踪信息，包括ASN信息、丢包率统计等：

**Ubuntu/Debian:**

```bash
sudo apt-get install mtr-tiny
```

**CentOS/RHEL:**

```bash
sudo yum install mtr
```

**macOS:**

```bash
brew install mtr
```

**Windows:**

```bash
# 使用内置的tracert命令，无需额外安装
```

#### 配置mtr无密码执行（推荐）

为了避免每次执行mtr时输入密码，建议配置sudoers：

```bash
# 编辑sudoers文件
sudo visudo

# 添加以下行（替换为实际用户名）
username ALL=(ALL) NOPASSWD: /usr/bin/mtr, /opt/homebrew/sbin/mtr
```

## 🎯 单目标诊断

### 基本用法

单目标诊断用于对单个域名或IP地址进行详细的网络诊断。

#### 最简单的使用方式

```bash
# 诊断一个网站（使用默认端口443）
uv run python main.py google.com
```

#### 完整命令格式

```bash
uv run python main.py <domain> [options]
```

### 命令行参数详解

| 参数 | 类型 | 默认值 | 描述 | 示例 |
|------|------|--------|------|------|
| `domain` | 必需 | - | 目标域名或IP地址 | `google.com` |
| `--port` | 可选 | 443 | 目标端口号 | `--port 80` |
| `--no-trace` | 标志 | false | 跳过网络路径追踪 | `--no-trace` |
| `--no-http` | 标志 | false | 跳过HTTP响应收集 | `--no-http` |
| `--no-save` | 标志 | false | 不保存结果到文件 | `--no-save` |

### 使用示例

#### 1. 基本HTTPS网站诊断

```bash
# 诊断HTTPS网站（包含所有功能）
uv run python main.py github.com

# 输出示例：
# 2025-09-10 12:00:00 - INFO - Starting network diagnosis for github.com:443
# 2025-09-10 12:00:00 - INFO - Resolved github.com to 140.82.112.3
# 2025-09-10 12:00:00 - INFO - TCP connection successful in 45.23ms
# 2025-09-10 12:00:01 - INFO - TLS handshake completed in 156.78ms
# 2025-09-10 12:00:01 - INFO - HTTP request completed in 234.56ms
# 2025-09-10 12:00:02 - INFO - Network diagnosis completed in 567.89ms
```

#### 2. HTTP网站诊断

```bash
# 诊断HTTP网站（端口80）
uv run python main.py httpbin.org --port 80

# 跳过TLS分析（因为是HTTP）
uv run python main.py example.com --port 80 --no-trace
```

#### 3. 自定义端口诊断

```bash
# 诊断自定义端口
uv run python main.py example.com --port 8080

# 诊断数据库端口（只测试TCP连接）
uv run python main.py db.example.com --port 3306 --no-http --no-trace
```

#### 4. 快速连接测试

```bash
# 只测试TCP连接，跳过其他功能
uv run python main.py target.com --no-http --no-trace --no-save
```

#### 5. IP地址诊断

```bash
# 直接诊断IP地址
uv run python main.py 8.8.8.8 --port 53 --no-http

# 诊断内网IP
uv run python main.py 192.168.1.1 --port 80 --no-trace
```

### 诊断流程说明

1. **公网IP信息收集**：收集发起端的公网IP地理位置信息
2. **域名解析**：将域名解析为IP地址，记录解析时间
3. **TCP连接测试**：测试到目标的TCP连接，记录连接时间和Socket信息
4. **TLS握手**：如果启用TLS且是HTTPS端口，进行TLS握手和证书分析
5. **HTTP请求**：如果启用HTTP，发送HTTP请求并分析响应
6. **网络路径追踪**：如果启用追踪，使用mtr或traceroute追踪网络路径
7. **结果保存**：将诊断结果保存为JSON文件

### 新增功能特性

#### URL检测支持

工具现在支持直接使用URL进行诊断：

```bash
# 使用URL进行诊断（自动解析域名和端口）
uv run python main.py https://github.com/user/repo
uv run python main.py http://api.example.com:8080/health
```

#### TLS开关控制

可以通过配置文件控制是否进行TLS检测：

```yaml
targets:
  - domain: "example.com"
    port: 443
    include_tls: true    # 启用TLS检测
  - domain: "api.example.com"
    port: 80
    include_tls: false   # 禁用TLS检测
```

#### 增强的mtr网络追踪

使用mtr命令进行网络路径追踪，提供更详细的信息：

- ASN（自治系统号）信息
- 详细的丢包率统计
- 精确的延迟测量
- JSON格式输出

### 输出文件

每次诊断会在 `network-diagnosis/output/` 目录下生成一个JSON文件：

```text
network-diagnosis/output/network_diagnosis_github.com_443_20250910_120000_123.json
```

文件命名格式：`network_diagnosis_{domain}_{port}_{timestamp}_{random}.json`

## 📊 批量诊断

批量诊断允许您同时对多个目标进行网络诊断，适用于监控多个服务器或网站的场景。

### 配置文件编写指南

#### 1. 创建示例配置文件

```bash
# 创建示例配置文件
uv run python batch_main.py --create-sample

# 这会创建 targets_sample.yaml 文件
```

#### 2. 配置文件结构

```yaml
# targets.yaml
targets:
  # 域名+端口方式
  - domain: "google.com"
    port: 443
    include_trace: false
    include_http: true
    include_tls: true
    description: "Google搜索引擎"

  # URL方式（自动解析域名和端口）
  - url: "https://github.com/user/repo"
    include_trace: false
    include_http: true
    include_tls: true
    description: "GitHub代码托管平台"

  # HTTP服务（禁用TLS）
  - domain: "httpbin.org"
    port: 80
    include_trace: false
    include_http: true
    include_tls: false
    description: "HTTP测试服务"

  # API接口测试
  - url: "http://api.example.com:8080/health"
    include_trace: false
    include_http: true
    include_tls: false
    description: "API健康检查"

global_settings:
  # 默认设置
  default_port: 443
  default_include_trace: false
  default_include_http: true
  default_include_tls: true

  # 执行设置
  max_concurrent: 3
  timeout_seconds: 60

  # 输出设置
  save_individual_files: true
  save_summary_report: false  # 默认关闭批量汇总报告

  # 分析设置
  include_performance_analysis: true
  include_security_analysis: true
```

#### 3. 目标配置参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `domain` | string | ✓* | - | 域名或IP地址（与url二选一） |
| `url` | string | ✓* | - | 完整URL（与domain二选一） |
| `port` | integer | ✗ | 443 | 目标端口 (1-65535) |
| `include_trace` | boolean | ✗ | false | 是否执行网络路径追踪 |
| `include_http` | boolean | ✗ | true | 是否收集HTTP响应信息 |
| `include_tls` | boolean | ✗ | true | 是否进行TLS检测 |
| `description` | string | ✗ | null | 目标描述信息 |

*注：`domain` 和 `url` 必须提供其中一个

#### 4. 全局设置参数

| 参数 | 类型 | 默认值 | 范围 | 描述 |
|------|------|--------|------|------|
| `max_concurrent` | integer | 3 | 1-10 | 最大并发诊断数 |
| `timeout_seconds` | integer | 60 | 10-300 | 单个诊断超时时间 |
| `save_individual_files` | boolean | true | - | 是否保存单个JSON文件 |
| `save_summary_report` | boolean | false | - | 是否生成汇总报告 |
| `default_include_tls` | boolean | true | - | 默认TLS检测开关 |

### 批量诊断执行流程

#### 1. 验证配置文件

```bash
# 验证配置文件格式
uv run python batch_main.py --validate -c network-diagnosis/input/targets.yaml

# 输出示例：
# 2025-09-10 12:00:00 - INFO - Loading configuration from targets.yaml
# 2025-09-10 12:00:00 - INFO - Loaded 3 targets from configuration
# 配置文件格式正确: targets.yaml
```

#### 2. 执行批量诊断

```bash
# 使用默认配置文件 network-diagnosis/input/targets.yaml
uv run python batch_main.py

# 使用自定义配置文件
uv run python batch_main.py -c network-diagnosis/input/my_targets.yaml

# 静默模式（只显示错误）
uv run python batch_main.py --quiet -c network-diagnosis/input/targets.yaml

# 不显示详细摘要
uv run python batch_main.py --no-summary -c network-diagnosis/input/targets.yaml
```

#### 3. 批量诊断命令参数

| 参数 | 描述 | 示例 |
|------|------|------|
| `-c, --config` | 指定配置文件路径 | `-c targets.yaml` |
| `--validate` | 只验证配置文件，不执行诊断 | `--validate` |
| `--create-sample` | 创建示例配置文件 | `--create-sample` |
| `--quiet` | 静默模式，只显示错误 | `--quiet` |
| `--no-summary` | 不显示详细摘要 | `--no-summary` |

### 配置文件示例

#### 示例1：Web服务器监控

```yaml
targets:
  # 生产环境
  - domain: "api.example.com"
    port: 443
    include_http: true
    description: "生产API服务器"

  - domain: "www.example.com"
    port: 443
    include_http: true
    description: "生产Web服务器"

  # 测试环境
  - domain: "test-api.example.com"
    port: 443
    include_http: true
    description: "测试API服务器"

global_settings:
  max_concurrent: 2
  timeout_seconds: 30
  save_summary_report: true
```

#### 示例2：数据库服务器监控

```yaml
targets:
  - domain: "db1.example.com"
    port: 3306
    include_http: false
    include_trace: false
    description: "MySQL主数据库"

  - domain: "db2.example.com"
    port: 3306
    include_http: false
    include_trace: false
    description: "MySQL从数据库"

  - domain: "redis.example.com"
    port: 6379
    include_http: false
    include_trace: false
    description: "Redis缓存服务器"

global_settings:
  max_concurrent: 3
  timeout_seconds: 15
  save_individual_files: true
```

#### 示例3：DNS服务器监控

```yaml
targets:
  - domain: "8.8.8.8"
    port: 53
    include_http: false
    include_trace: true
    description: "Google DNS"

  - domain: "1.1.1.1"
    port: 53
    include_http: false
    include_trace: true
    description: "Cloudflare DNS"

  - domain: "208.67.222.222"
    port: 53
    include_http: false
    include_trace: true
    description: "OpenDNS"

global_settings:
  max_concurrent: 2
  timeout_seconds: 120  # 路径追踪需要更长时间
  include_performance_analysis: true
```

### 批量诊断输出

批量诊断会根据配置文件名创建独立的子目录，并在其中生成以下文件：

#### 目录结构
```
network-diagnosis/
├── output/
│   ├── test_nssa_io/                    # 基于 test_nssa_io.yaml
│   │   ├── network_diagnosis_nssa.io_443_*.json
│   │   └── network_diagnosis_nssa.io_80_*.json
│   ├── targets_simple/                 # 基于 targets_simple.yaml
│   │   ├── network_diagnosis_google.com_443_*.json
│   │   ├── network_diagnosis_github.com_443_*.json
│   │   └── network_diagnosis_httpbin.org_80_*.json
│   └── production_targets/             # 基于 production_targets.yaml
│       └── ...
└── log/
    ├── test_nssa_io/
    │   └── diagnosis_*.log
    ├── targets_simple/
    │   └── diagnosis_*.log
    └── production_targets/
        └── diagnosis_*.log
```

#### 文件类型

1. **单个诊断结果**：`network_diagnosis_{domain}_{port}_{timestamp}.json`
   - 每个目标（域名+端口）生成独立的JSON文件
   - 包含完整的诊断信息（DNS、TCP、TLS、HTTP等）
   - 便于后续统一分析和处理

2. **批量诊断报告**：`batch_diagnosis_report_{timestamp}.json`（默认关闭）
   - 包含所有目标的统计分析和汇总信息
   - 可通过配置 `save_summary_report: true` 启用

3. **文本分析报告**：`analysis_report_{timestamp}.txt`（可选）
   - 文本格式的分析摘要
   - 仅在启用批量诊断报告时生成

#### 批量诊断摘要示例

```
================================================================================
批量网络诊断结果摘要
================================================================================
配置文件: targets.yaml
总目标数: 3
成功诊断: 3
失败诊断: 0
成功率: 100.0%
总执行时间: 1116.38ms

性能统计:
  平均诊断时间: 372.13ms
  平均TCP连接时间: 1.40ms
  最快诊断: 345.72ms
  最慢诊断: 415.30ms

安全统计:
  启用TLS连接: 2
  安全连接率: 66.7%
  TLS协议分布:
    TLSv1.3: 2

HTTP状态码分布:
  200: 3

详细结果:
--------------------------------------------------------------------------------
 1. ✓ google.com - 415.30ms
 2. ✓ github.com - 395.72ms
 3. ✓ httpbin.org - 345.55ms
================================================================================
```

## 📋 输出结果解读

### 单个诊断结果格式

每个诊断结果包含以下主要部分：

#### 1. 基本信息

```json
{
  "domain": "example.com",
  "target_ip": "93.184.216.34",
  "timestamp": "2025-09-10T12:00:00.000000",
  "success": true,
  "total_time_ms": 567.89,
  "error_messages": []
}
```

**字段说明：**
- `domain`：诊断的目标域名
- `target_ip`：解析后的主要IP地址
- `timestamp`：诊断开始时间
- `success`：诊断是否成功
- `total_time_ms`：总诊断时间（毫秒）
- `error_messages`：错误信息列表

#### 2. DNS解析信息

```json
{
  "dns_resolution": {
    "domain": "example.com",
    "resolved_ips": [
      "93.184.216.34",
      "93.184.216.35"
    ],
    "primary_ip": "93.184.216.34",
    "resolution_time_ms": 15.23,
    "dns_server": "192.168.1.1",
    "record_type": "A",
    "is_successful": true,
    "error_message": null
  }
}
```

**DNS性能指标解读：**
- `< 20ms`：优秀的DNS解析性能
- `20-50ms`：良好的DNS解析性能
- `50-100ms`：一般的DNS解析性能
- `> 100ms`：较慢的DNS解析性能

**DNS信息说明：**
- `resolved_ips`：域名解析到的所有IP地址
- `primary_ip`：选择的主要IP地址
- `resolution_time_ms`：DNS查询耗时
- `dns_server`：使用的DNS服务器地址
- `record_type`：DNS记录类型（A、AAAA等）

#### 3. TCP连接信息

```json
{
  "tcp_connection": {
    "host": "example.com",
    "port": 443,
    "target_ip": "93.184.216.34",
    "connect_time_ms": 45.23,
    "is_connected": true,
    "socket_family": "IPv4",
    "local_address": "192.168.1.100",
    "local_port": 54321,
    "error_message": null
  }
}
```

**性能指标解读：**
- `< 50ms`：优秀的连接性能
- `50-100ms`：良好的连接性能
- `100-200ms`：一般的连接性能
- `> 200ms`：较慢的连接性能

**TCP连接信息说明：**
- `target_ip`：实际连接的目标IP地址
- `socket_family`：连接类型（IPv4或IPv6）
- `local_address`：本地连接地址
- `local_port`：本地连接端口

#### 4. TLS/SSL信息

```json
{
  "tls_info": {
    "protocol_version": "TLSv1.3",
    "cipher_suite": "TLS_AES_256_GCM_SHA384",
    "certificate": {
      "subject": {"CN": "example.com"},
      "issuer": {"CN": "DigiCert TLS RSA SHA256 2020 CA1"},
      "not_before": "2024-01-01T00:00:00",
      "not_after": "2025-01-01T00:00:00",
      "is_expired": false,
      "days_until_expiry": 120,
      "fingerprint_sha256": "abc123..."
    },
    "is_secure": true,
    "handshake_time_ms": 156.78
  }
}
```

**安全评估：**
- `TLSv1.3`：最新最安全的协议版本
- `TLSv1.2`：安全的协议版本
- `TLSv1.1及以下`：不推荐使用
- `days_until_expiry < 30`：证书即将过期，需要更新

#### 5. HTTP响应信息

```json
{
  "http_info": {
    "status_code": 200,
    "reason_phrase": "OK",
    "response_time_ms": 234.56,
    "headers": {
      "content-type": "text/html; charset=UTF-8",
      "server": "nginx/1.18.0"
    },
    "content_length": 1024,
    "redirects": []
  }
}
```

**状态码解读：**
- `2xx`：成功响应
- `3xx`：重定向响应
- `4xx`：客户端错误
- `5xx`：服务器错误

**性能指标：**
- `< 200ms`：优秀的响应性能
- `200-500ms`：良好的响应性能
- `500-1000ms`：一般的响应性能
- `> 1000ms`：较慢的响应性能

#### 6. 网络路径信息

```json
{
  "network_path": {
    "destination": "example.com",
    "hop_count": 8,
    "total_time_ms": 45.67,
    "trace_method": "mtr",
    "hops": [
      {
        "hop_number": 1,
        "ip_address": "192.168.1.1",
        "hostname": "gateway.local",
        "avg_time_ms": 1.23,
        "packet_loss_percent": 0.0
      },
      {
        "hop_number": 2,
        "ip_address": "10.0.0.1",
        "hostname": "isp.gateway",
        "avg_time_ms": 15.45,
        "packet_loss_percent": 0.0
      }
    ]
  }
}
```

**路径分析：**
- `hop_count`：网络跳数，通常8-15跳为正常
- `packet_loss_percent`：丢包率，应该为0%
- `avg_time_ms`：平均延迟，每跳增加5-20ms为正常

### 批量诊断报告解读

#### 1. 执行摘要

```json
{
  "execution_summary": {
    "total_targets": 5,
    "successful": 4,
    "failed": 1,
    "success_rate": 80.0,
    "total_execution_time_ms": 2345.67
  }
}
```

**关键指标：**
- `success_rate > 95%`：网络状况优秀
- `success_rate 80-95%`：网络状况良好
- `success_rate < 80%`：可能存在网络问题

#### 2. 性能统计

```json
{
  "performance_statistics": {
    "average_diagnosis_time_ms": 468.13,
    "average_tcp_connect_time_ms": 45.23,
    "fastest_diagnosis_ms": 234.56,
    "slowest_diagnosis_ms": 789.01
  }
}
```

#### 3. 安全统计

```json
{
  "security_statistics": {
    "tls_enabled_count": 3,
    "secure_connections_rate": 75.0,
    "tls_protocols": {
      "TLSv1.3": 2,
      "TLSv1.2": 1
    }
  }
}
```

## 🔧 常见问题排查

### 安装和配置问题

#### Q1: uv命令未找到

**问题：** `command not found: uv`

**解决方案：**
```bash
# 重新安装uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 重新加载shell配置
source ~/.bashrc  # 或 ~/.zshrc

# 验证安装
uv --version
```

#### Q2: Python版本不兼容

**问题：** `Python 3.11+ required`

**解决方案：**
```bash
# 检查Python版本
python --version

# 使用uv安装指定Python版本
uv python install 3.11

# 使用指定Python版本
uv run --python 3.11 python main.py google.com
```

#### Q3: 依赖安装失败

**问题：** 依赖包安装失败

**解决方案：**
```bash
# 清理缓存
uv cache clean

# 重新安装依赖
uv sync --reinstall

# 手动安装特定包
uv add pydantic-settings --force-reinstall
```

### 网络诊断问题

#### Q4: 连接超时

**问题：** `Connection timeout`

**可能原因和解决方案：**

1. **网络连接问题**
   ```bash
   # 检查网络连接
   ping google.com

   # 增加超时时间
   echo "CONNECT_TIMEOUT=30" >> .env
   ```

2. **防火墙阻止**
   ```bash
   # 检查防火墙状态
   sudo ufw status  # Ubuntu

   # 临时禁用防火墙测试
   sudo ufw disable
   ```

3. **目标服务器不可达**
   ```bash
   # 使用其他工具验证
   telnet example.com 443
   nc -zv example.com 443
   ```

#### Q5: TLS握手失败

**问题：** `TLS handshake failed`

**解决方案：**
```bash
# 检查TLS配置
openssl s_client -connect example.com:443

# 跳过TLS验证（仅用于测试）
echo "VERIFY_SSL=false" >> .env
```

#### Q6: HTTP请求失败

**问题：** `HTTP request failed`

**解决方案：**
```bash
# 检查HTTP响应
curl -I https://example.com

# 增加重定向次数
echo "MAX_REDIRECTS=10" >> .env

# 跳过HTTP检查
uv run python main.py example.com --no-http
```

### 权限问题

#### Q7: mtr命令需要sudo权限

**问题：** `mtr requires sudo privileges`

**解决方案：**

1. **设置sudo密码**
   ```bash
   echo "SUDO_PASSWORD=your_password" >> .env
   ```

2. **配置sudo免密码**
   ```bash
   # 编辑sudoers文件
   sudo visudo

   # 添加以下行（替换username为你的用户名）
   username ALL=(ALL) NOPASSWD: /usr/bin/mtr
   ```

3. **跳过路径追踪**
   ```bash
   uv run python main.py example.com --no-trace
   ```

#### Q8: 输出目录权限不足

**问题：** `Permission denied: output directory`

**解决方案：**
```bash
# 创建输出目录
mkdir -p output

# 设置权限
chmod 755 output

# 或更改输出目录
echo "OUTPUT_DIR=/tmp/network_diagnosis" >> .env
```

### 配置文件问题

#### Q9: YAML格式错误

**问题：** `YAML parsing error`

**解决方案：**
```bash
# 验证YAML格式
uv run python batch_main.py --validate -c targets.yaml

# 使用在线YAML验证器
# https://yamlchecker.com/

# 重新创建示例配置
uv run python batch_main.py --create-sample
```

#### Q10: 配置参数无效

**问题：** `Invalid configuration parameter`

**解决方案：**
```bash
# 检查参数范围
# max_concurrent: 1-10
# timeout_seconds: 10-300
# port: 1-65535

# 查看详细错误信息
uv run python batch_main.py -c targets.yaml --debug
```

### 性能问题

#### Q11: 诊断速度慢

**问题：** 批量诊断执行时间过长

**解决方案：**
```yaml
# 优化配置文件
global_settings:
  max_concurrent: 5  # 增加并发数
  timeout_seconds: 30  # 减少超时时间

targets:
  - domain: "example.com"
    include_trace: false  # 跳过耗时的路径追踪
```

#### Q12: 内存使用过高

**问题：** 内存使用过高

**解决方案：**
```yaml
# 减少并发数
global_settings:
  max_concurrent: 2

# 分批处理大量目标
# 将大配置文件拆分为多个小文件
```

## 🏭 生产环境部署

### 部署方式选择

#### 1. 直接部署（推荐用于小规模）

**适用场景：** 单机部署，监控目标数量 < 100

```bash
# 1. 创建专用用户
sudo useradd -m -s /bin/bash netdiag
sudo usermod -aG sudo netdiag

# 2. 配置sudoers（无密码执行mtr）
sudo visudo
# 添加：netdiag ALL=(ALL) NOPASSWD: /usr/bin/mtr

# 3. 安装依赖
sudo apt install -y mtr-tiny python3.11 python3.11-venv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 4. 部署应用
git clone https://github.com/Matthewyin/probing.git
cd probing
uv sync

# 5. 配置systemd服务
sudo tee /etc/systemd/system/network-diagnosis.service << EOF
[Unit]
Description=Network Diagnosis Service
After=network.target

[Service]
Type=simple
User=netdiag
WorkingDirectory=/home/netdiag/probing
ExecStart=/home/netdiag/.local/bin/uv run python batch_main.py -c network-diagnosis/input/production.yaml
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable network-diagnosis
sudo systemctl start network-diagnosis
```

#### 2. 容器化部署（推荐用于中大规模）

**适用场景：** 多节点部署，需要扩展性和隔离性

```dockerfile
# Dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    mtr-tiny \
    traceroute \
    dnsutils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# 创建应用目录
WORKDIR /app
COPY . .

# 安装Python依赖
RUN uv sync

# 配置sudoers（容器内安全）
RUN echo "root ALL=(ALL) NOPASSWD: /usr/bin/mtr" >> /etc/sudoers

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# 运行应用
CMD ["uv", "run", "python", "batch_main.py", "-c", "network-diagnosis/input/production.yaml"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  network-diagnosis:
    build: .
    volumes:
      - ./network-diagnosis/input:/app/network-diagnosis/input:ro
      - ./network-diagnosis/output:/app/network-diagnosis/output
      - ./network-diagnosis/log:/app/network-diagnosis/log
    environment:
      - LOG_LEVEL=INFO
      - MAX_CONCURRENT=5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
```

### 监控和运维

#### 1. 日志管理

```bash
# 配置日志轮转
sudo tee /etc/logrotate.d/network-diagnosis << EOF
/home/netdiag/probing/network-diagnosis/log/*/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 netdiag netdiag
}
EOF
```

#### 2. 性能监控

```bash
# 监控脚本示例
#!/bin/bash
# monitor.sh

LOG_DIR="/home/netdiag/probing/network-diagnosis/log"
OUTPUT_DIR="/home/netdiag/probing/network-diagnosis/output"

# 检查最近的执行状态
LATEST_LOG=$(find $LOG_DIR -name "*.log" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)

if [ -n "$LATEST_LOG" ]; then
    # 检查是否有错误
    ERROR_COUNT=$(grep -c "ERROR" "$LATEST_LOG")
    SUCCESS_COUNT=$(grep -c "SUCCESS" "$LATEST_LOG")

    echo "最近执行状态: 成功 $SUCCESS_COUNT, 错误 $ERROR_COUNT"

    # 检查磁盘使用
    DISK_USAGE=$(df -h $OUTPUT_DIR | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ $DISK_USAGE -gt 80 ]; then
        echo "警告: 磁盘使用率过高 ($DISK_USAGE%)"
    fi
fi
```

#### 3. 告警配置

```bash
# 集成到监控系统
# Prometheus + Grafana 示例配置

# prometheus.yml
scrape_configs:
  - job_name: 'network-diagnosis'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### 扩展性考虑

#### 1. 水平扩展

```yaml
# kubernetes部署示例
apiVersion: apps/v1
kind: Deployment
metadata:
  name: network-diagnosis
spec:
  replicas: 3
  selector:
    matchLabels:
      app: network-diagnosis
  template:
    metadata:
      labels:
        app: network-diagnosis
    spec:
      containers:
      - name: network-diagnosis
        image: network-diagnosis:latest
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        volumeMounts:
        - name: config-volume
          mountPath: /app/network-diagnosis/input
        - name: output-volume
          mountPath: /app/network-diagnosis/output
      volumes:
      - name: config-volume
        configMap:
          name: diagnosis-config
      - name: output-volume
        persistentVolumeClaim:
          claimName: diagnosis-output-pvc
```

#### 2. 负载均衡

```bash
# nginx配置示例
upstream network_diagnosis {
    server diagnosis-1:8080;
    server diagnosis-2:8080;
    server diagnosis-3:8080;
}

server {
    listen 80;
    location / {
        proxy_pass http://network_diagnosis;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🚀 高级用法

### 编程接口使用

#### 1. 基本编程接口

```python
import asyncio
from src.network_diagnosis.diagnosis import DiagnosisCoordinator
from src.network_diagnosis.models import DiagnosisRequest

async def main():
    # 创建诊断请求
    request = DiagnosisRequest(
        domain="google.com",
        port=443,
        include_trace=False,
        include_http=True
    )

    # 执行诊断
    coordinator = DiagnosisCoordinator()
    result = await coordinator.diagnose(request)

    # 处理结果
    print(f"诊断结果: {result.success}")
    print(f"总时间: {result.total_time_ms}ms")
    print(f"TCP连接时间: {result.tcp_connection.connect_time_ms}ms")

if __name__ == "__main__":
    asyncio.run(main())
```

#### 2. 批量诊断编程接口

```python
import asyncio
from src.network_diagnosis.batch_runner import BatchDiagnosisRunner

async def batch_diagnosis():
    # 创建批量诊断运行器
    runner = BatchDiagnosisRunner("targets.yaml")

    # 执行批量诊断
    result = await runner.run_batch_diagnosis()

    # 处理结果
    print(f"成功率: {result.summary.execution_summary.success_rate}%")
    print(f"平均诊断时间: {result.summary.performance_statistics.average_diagnosis_time_ms}ms")

    return result

if __name__ == "__main__":
    result = asyncio.run(batch_diagnosis())
```

### 自定义配置

#### 1. 环境特定配置

```bash
# 开发环境配置
cp .env .env.development
echo "DEBUG=true" >> .env.development
echo "LOG_LEVEL=DEBUG" >> .env.development

# 生产环境配置
cp .env .env.production
echo "DEBUG=false" >> .env.production
echo "LOG_LEVEL=INFO" >> .env.production

# 使用特定环境配置
ENV_FILE=.env.development uv run python main.py google.com
```

#### 2. 自定义输出格式

```python
# 自定义结果处理器
from src.network_diagnosis.models import NetworkDiagnosisResult
import csv

def export_to_csv(results: list[NetworkDiagnosisResult], filename: str):
    """将诊断结果导出为CSV格式"""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Domain', 'IP', 'Success', 'TCP Time', 'Total Time'])

        for result in results:
            writer.writerow([
                result.domain,
                result.target_ip,
                result.success,
                result.tcp_connection.connect_time_ms,
                result.total_time_ms
            ])
```

### 监控和告警

#### 1. 定时监控脚本

```bash
#!/bin/bash
# monitor.sh - 定时监控脚本

cd /path/to/network-diagnosis

# 执行诊断
uv run python batch_main.py -c production_targets.yaml --quiet

# 检查结果
if [ $? -eq 0 ]; then
    echo "$(date): 监控正常" >> monitor.log
else
    echo "$(date): 监控异常" >> monitor.log
    # 发送告警邮件
    echo "网络诊断监控异常" | mail -s "监控告警" admin@example.com
fi
```

#### 2. 结果分析脚本

```python
#!/usr/bin/env python3
# analyze_results.py - 结果分析脚本

import json
import glob
from datetime import datetime, timedelta

def analyze_recent_results(hours=24):
    """分析最近N小时的诊断结果"""
    cutoff_time = datetime.now() - timedelta(hours=hours)

    # 查找最近的结果文件
    pattern = "output/batch_diagnosis_report_*.json"
    files = glob.glob(pattern)

    recent_files = []
    for file in files:
        # 从文件名提取时间戳
        timestamp_str = file.split('_')[-1].replace('.json', '')
        file_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')

        if file_time > cutoff_time:
            recent_files.append(file)

    # 分析结果
    total_targets = 0
    total_successful = 0

    for file in recent_files:
        with open(file, 'r') as f:
            data = json.load(f)
            summary = data['summary']['execution_summary']
            total_targets += summary['total_targets']
            total_successful += summary['successful']

    if total_targets > 0:
        success_rate = (total_successful / total_targets) * 100
        print(f"最近{hours}小时成功率: {success_rate:.1f}%")

        if success_rate < 95:
            print("⚠️  成功率低于95%，需要关注")
    else:
        print("没有找到最近的诊断结果")

if __name__ == "__main__":
    analyze_recent_results(24)
```

### 集成其他工具

#### 1. 与Prometheus集成

```python
# prometheus_exporter.py
from prometheus_client import start_http_server, Gauge, Counter
import json
import time

# 定义指标
diagnosis_success_rate = Gauge('network_diagnosis_success_rate', 'Network diagnosis success rate')
diagnosis_response_time = Gauge('network_diagnosis_response_time_ms', 'Average response time', ['target'])
diagnosis_total = Counter('network_diagnosis_total', 'Total diagnoses', ['target', 'status'])

def export_metrics():
    """导出指标到Prometheus"""
    # 读取最新的批量诊断报告
    with open('output/latest_batch_report.json', 'r') as f:
        data = json.load(f)

    # 更新指标
    summary = data['summary']
    diagnosis_success_rate.set(summary['execution_summary']['success_rate'])

    for result in data['individual_results']:
        target = result['domain']
        status = 'success' if result['success'] else 'failure'

        diagnosis_total.labels(target=target, status=status).inc()
        if result['success']:
            diagnosis_response_time.labels(target=target).set(result['total_time_ms'])

if __name__ == '__main__':
    start_http_server(8000)
    while True:
        export_metrics()
        time.sleep(60)
```

#### 2. 与Grafana集成

```json
{
  "dashboard": {
    "title": "网络诊断监控",
    "panels": [
      {
        "title": "成功率",
        "type": "stat",
        "targets": [
          {
            "expr": "network_diagnosis_success_rate",
            "legendFormat": "成功率"
          }
        ]
      },
      {
        "title": "响应时间",
        "type": "graph",
        "targets": [
          {
            "expr": "network_diagnosis_response_time_ms",
            "legendFormat": "{{target}}"
          }
        ]
      }
    ]
  }
}
```

## ⚡ 性能优化

### 并发配置指导

#### 1. 并发数选择

根据不同场景选择合适的并发数：

| 场景 | 推荐并发数 | 原因 |
|------|------------|------|
| 本地测试 | 1-2 | 避免对目标服务器造成压力 |
| 内网监控 | 3-5 | 平衡性能和稳定性 |
| 互联网监控 | 2-3 | 避免被误认为攻击 |
| 大规模监控 | 5-10 | 最大化性能，需要优质网络 |

#### 2. 超时时间配置

```yaml
global_settings:
  timeout_seconds: 30   # 快速网络
  # timeout_seconds: 60   # 一般网络
  # timeout_seconds: 120  # 慢速网络或包含路径追踪
```

#### 3. 性能优化建议

**减少诊断时间：**
```yaml
targets:
  - domain: "example.com"
    include_trace: false  # 跳过耗时的路径追踪
    include_http: true    # 保留HTTP检查
```

**批量处理优化：**
```bash
# 分批处理大量目标
# 将100个目标分成5个文件，每个文件20个目标
# targets_batch1.yaml, targets_batch2.yaml, ...

for i in {1..5}; do
    uv run python batch_main.py -c targets_batch${i}.yaml &
done
wait
```

### 资源使用优化

#### 1. 内存优化

```python
# 大批量诊断时的内存优化
import gc

async def memory_efficient_batch_diagnosis(targets, batch_size=50):
    """内存高效的批量诊断"""
    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]

        # 处理当前批次
        results = await process_batch(batch)

        # 保存结果并清理内存
        save_batch_results(results)
        del results
        gc.collect()

        # 批次间休息
        await asyncio.sleep(1)
```

#### 2. 网络优化

```yaml
# 网络优化配置
global_settings:
  max_concurrent: 3
  timeout_seconds: 30

  # 减少HTTP重定向次数
  max_redirects: 3

  # 优化连接超时
  connect_timeout: 10
  read_timeout: 20
```

### 监控和调优

#### 1. 性能监控

```python
# performance_monitor.py
import time
import psutil
from src.network_diagnosis.batch_runner import BatchDiagnosisRunner

class PerformanceMonitor:
    def __init__(self):
        self.start_time = None
        self.start_memory = None

    def start_monitoring(self):
        self.start_time = time.time()
        self.start_memory = psutil.Process().memory_info().rss

    def stop_monitoring(self):
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss

        duration = end_time - self.start_time
        memory_used = (end_memory - self.start_memory) / 1024 / 1024  # MB

        print(f"执行时间: {duration:.2f}秒")
        print(f"内存使用: {memory_used:.2f}MB")

        return {
            'duration': duration,
            'memory_used_mb': memory_used
        }

# 使用示例
async def monitored_diagnosis():
    monitor = PerformanceMonitor()
    monitor.start_monitoring()

    runner = BatchDiagnosisRunner("targets.yaml")
    result = await runner.run_batch_diagnosis()

    stats = monitor.stop_monitoring()
    print(f"诊断了{len(result.individual_results)}个目标")
    print(f"平均每个目标耗时: {stats['duration']/len(result.individual_results):.2f}秒")
```

#### 2. 自动调优

```python
# auto_tuning.py
def calculate_optimal_settings(target_count, network_quality='good'):
    """根据目标数量和网络质量自动计算最优设置"""

    # 基础并发数
    base_concurrent = {
        'poor': 1,
        'fair': 2,
        'good': 3,
        'excellent': 5
    }.get(network_quality, 3)

    # 根据目标数量调整
    if target_count <= 5:
        max_concurrent = min(base_concurrent, target_count)
    elif target_count <= 20:
        max_concurrent = min(base_concurrent + 1, 5)
    else:
        max_concurrent = min(base_concurrent + 2, 10)

    # 根据并发数调整超时时间
    timeout_seconds = max(30, 60 - (max_concurrent * 5))

    return {
        'max_concurrent': max_concurrent,
        'timeout_seconds': timeout_seconds
    }

# 使用示例
settings = calculate_optimal_settings(target_count=15, network_quality='good')
print(f"推荐设置: {settings}")
```

### 最佳实践总结

#### 1. 配置最佳实践

```yaml
# 推荐的生产环境配置
global_settings:
  # 保守的并发设置
  max_concurrent: 3
  timeout_seconds: 60

  # 完整的输出设置
  save_individual_files: true
  save_summary_report: true
  include_performance_analysis: true
  include_security_analysis: true

  # 默认设置
  default_port: 443
  default_include_trace: false  # 生产环境建议关闭
  default_include_http: true

targets:
  # 为每个目标添加描述
  - domain: "api.example.com"
    description: "生产API服务器"
    port: 443
    include_http: true
    include_trace: false
```

#### 2. 运维最佳实践

```bash
#!/bin/bash
# production_monitor.sh - 生产环境监控脚本

# 设置工作目录
cd /opt/network-diagnosis

# 设置日志
LOG_FILE="/var/log/network-diagnosis.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# 执行诊断
echo "[$DATE] 开始网络诊断" >> $LOG_FILE

if uv run python batch_main.py -c production_targets.yaml --quiet; then
    echo "[$DATE] 诊断成功完成" >> $LOG_FILE

    # 检查成功率
    SUCCESS_RATE=$(python3 -c "
import json, glob
files = glob.glob('output/batch_diagnosis_report_*.json')
if files:
    with open(max(files), 'r') as f:
        data = json.load(f)
        print(data['summary']['execution_summary']['success_rate'])
else:
    print(0)
")

    if (( $(echo "$SUCCESS_RATE < 95" | bc -l) )); then
        echo "[$DATE] 警告: 成功率低于95% ($SUCCESS_RATE%)" >> $LOG_FILE
        # 发送告警
        echo "网络诊断成功率低于95%: $SUCCESS_RATE%" | \
            mail -s "网络监控告警" admin@example.com
    fi
else
    echo "[$DATE] 诊断执行失败" >> $LOG_FILE
    # 发送错误告警
    echo "网络诊断执行失败，请检查系统状态" | \
        mail -s "网络监控错误" admin@example.com
fi

# 清理旧文件（保留最近7天）
find output/ -name "*.json" -mtime +7 -delete
find /var/log/ -name "network-diagnosis.log.*" -mtime +30 -delete

echo "[$DATE] 监控任务完成" >> $LOG_FILE
```

#### 3. 安全最佳实践

```bash
# 1. 设置适当的文件权限
chmod 600 .env                    # 配置文件只有所有者可读写
chmod 755 output/                 # 输出目录可读可执行
chmod 644 output/*.json           # 输出文件可读

# 2. 定期轮换日志
logrotate -f /etc/logrotate.d/network-diagnosis

# 3. 监控异常访问
tail -f /var/log/network-diagnosis.log | grep -i "error\|fail\|timeout"
```

---

## 📚 总结

本用户手册涵盖了网络诊断工具的完整使用方法，从基础安装到高级优化。主要内容包括：

- **基础使用**：单目标和批量诊断的基本操作
- **配置管理**：环境变量和YAML配置文件的使用
- **结果解读**：详细的输出格式说明和性能指标解读
- **问题排查**：常见问题的诊断和解决方案
- **高级功能**：编程接口、监控集成和性能优化

通过遵循本手册的指导，您可以充分利用网络诊断工具的所有功能，实现高效的网络监控和故障排查。

如需更多技术细节，请参考：
- [架构文档](ARCHITECTURE.md) - 详细的技术架构说明
- [配置指南](CONFIG_USAGE.md) - 配置文件详细说明
- [项目总结](PROJECT_SUMMARY.md) - 项目功能概述
