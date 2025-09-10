# TLS开关与URL探测功能实现文档

## 📋 功能概述

本次实现了两个重要功能：
1. **TLS开关控制**：在配置文件中通过 `include_tls: true/false` 控制是否进行TLS探测
2. **URL探测支持**：支持直接使用URL进行网络诊断，自动解析域名、端口、协议和路径

## 🎯 功能1：TLS开关控制

### 实现原理
- 在 `DiagnosisRequest` 模型中添加 `include_tls: bool = True` 字段
- 在配置文件的 `TargetConfig` 中支持 `include_tls` 配置
- 在诊断逻辑中根据开关决定是否执行TLS信息收集

### 配置示例
```yaml
targets:
  # 启用TLS探测
  - domain: "baidu.com"
    port: 443
    include_tls: true
    
  # 禁用TLS探测
  - domain: "github.com"
    port: 443
    include_tls: false
```

### 实现效果
- **启用TLS**：收集完整的TLS证书信息、协议版本、加密套件等
- **禁用TLS**：跳过TLS信息收集，`tls_info` 字段为 `null`
- **性能优化**：禁用TLS可以显著减少诊断时间

## 🌐 功能2：URL探测支持

### 实现原理
- 扩展 `DiagnosisRequest` 模型，添加 `url` 字段和URL解析功能
- 使用 `urllib.parse` 自动解析URL组件
- 支持HTTP/HTTPS协议、自定义端口、路径和查询参数
- 保持向后兼容，支持传统的 domain+port 方式

### URL解析功能
```python
# 输入URL: https://api.github.com/users/octocat
# 自动解析为:
parsed_domain = "api.github.com"
parsed_port = 443
parsed_protocol = "https"
parsed_path = "/users/octocat"
```

### 配置示例
```yaml
targets:
  # 传统方式
  - domain: "baidu.com"
    port: 443
    
  # URL方式 - HTTPS API
  - url: "https://api.github.com/users/octocat"
    
  # URL方式 - HTTP API
  - url: "http://httpbin.org/get?test=url"
    
  # URL方式 - 自定义端口
  - url: "https://httpbin.org:8443/json"
```

### 支持的URL格式
- ✅ `https://example.com` - 标准HTTPS，默认443端口
- ✅ `http://example.com` - 标准HTTP，默认80端口
- ✅ `https://example.com:8443` - 自定义端口
- ✅ `https://api.example.com/v1/users` - 带路径
- ✅ `https://api.example.com/search?q=test` - 带查询参数

## 📊 验证结果

### TLS开关测试
```bash
uv run python batch_main.py -c test_tls_switch.yaml
```

**结果**：
- ✅ baidu.com (include_tls: true) - 收集了完整TLS信息
- ✅ github.com (include_tls: false) - TLS信息为null，节省了诊断时间

### URL探测测试
```bash
uv run python batch_main.py -c test_url_detection.yaml
```

**结果**：
- ✅ 传统方式：baidu.com:443 - 正常工作
- ✅ GitHub API：`https://api.github.com/users/octocat` - 正确访问API端点
- ✅ HTTPBin JSON：`https://httpbin.org/json` - 正确访问JSON端点
- ✅ 自动端口解析：HTTPS默认443，HTTP默认80

## 🔧 技术实现细节

### 数据模型扩展
```python
class DiagnosisRequest(BaseModel):
    domain: Optional[str] = None
    port: int = 443
    url: Optional[str] = None  # 新增URL支持
    include_tls: bool = True   # 新增TLS开关
    
    # 自动解析的URL组件
    parsed_domain: Optional[str] = None
    parsed_port: Optional[int] = None
    parsed_protocol: Optional[str] = None
    parsed_path: Optional[str] = None
```

### URL解析逻辑
- 使用 `urllib.parse.urlparse()` 解析URL
- 自动提取协议、域名、端口、路径
- 处理默认端口（HTTP:80, HTTPS:443）
- 支持查询参数和URL片段

### HTTP请求构建
```python
# 智能URL构建
if request.parsed_protocol:
    protocol = request.parsed_protocol
    path = request.parsed_path or "/"
    # 标准端口不显示端口号
    if ((protocol == "https" and port == 443) or 
        (protocol == "http" and port == 80)):
        url = f"{protocol}://{domain}{path}"
    else:
        url = f"{protocol}://{domain}:{port}{path}"
```

## 🎉 功能优势

### TLS开关优势
1. **性能优化**：可选择性跳过TLS检测，提升诊断速度
2. **灵活配置**：针对不同目标设置不同的检测策略
3. **资源节约**：减少不必要的TLS握手开销

### URL探测优势
1. **使用便捷**：直接使用URL，无需手动分离域名和端口
2. **功能完整**：支持API端点、路径参数、查询字符串
3. **向后兼容**：不影响现有的domain+port配置方式
4. **自动解析**：智能处理协议、端口、路径等组件

## 📝 配置文件示例

完整的配置文件示例：
```yaml
targets:
  # 传统配置 + TLS开关
  - domain: "baidu.com"
    port: 443
    include_trace: false
    include_http: true
    include_tls: true
    description: "百度搜索 - 启用TLS"
    
  # URL配置 + TLS开关
  - url: "https://api.github.com/users/octocat"
    include_trace: false
    include_http: true
    include_tls: false
    description: "GitHub API - 禁用TLS"
    
  # HTTP URL配置
  - url: "http://httpbin.org/get?test=url"
    include_trace: false
    include_http: true
    include_tls: false
    description: "HTTP测试API"

global_settings:
  default_include_tls: true
  max_concurrent: 3
  timeout_seconds: 30
```

现在网络诊断系统具备了更强大的配置灵活性和URL处理能力！
