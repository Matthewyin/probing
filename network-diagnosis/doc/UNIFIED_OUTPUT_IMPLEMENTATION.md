# 统一输出函数实现总结 (方案3)

## 🎯 实现目标

实现方案3：创建统一的输出函数，既保持控制台输出的美观性，又确保所有业务日志完整保存到文件中。

## 🔧 技术实现

### 1. 核心函数：`log_and_print()`

在 `src/network_diagnosis/logger.py` 中新增统一输出函数：

```python
def log_and_print(message: str, level: str = "INFO", log_only: bool = False):
    """
    统一的输出函数：既打印到控制台又记录到日志
    
    Args:
        message: 要输出的消息
        level: 日志级别 (INFO, WARNING, ERROR, DEBUG)
        log_only: 如果为True，只记录到日志文件，不打印到控制台
    """
    # 控制台输出（保持原有美观格式）
    if not log_only:
        print(message)
    
    # 日志记录（带时间戳和模块信息）
    # 使用专门的business_log记录器，它只输出到文件
    business_logger = logging.getLogger("business_log")
    
    # 确保business_log记录器不传播到根记录器（避免重复输出到控制台）
    business_logger.propagate = False
    
    getattr(business_logger, level.lower())(message)
```

### 2. 专用日志记录器配置

增强 `setup_config_logging()` 函数，为业务日志创建专门的记录器：

```python
# 为business_log创建专门的文件处理器
business_logger = logging.getLogger("business_log")
business_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
business_logger.propagate = False  # 不传播到根记录器，避免重复输出

# 创建business_log专用的文件处理器
business_file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
business_file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
business_file_handler.setFormatter(file_formatter)
business_logger.addHandler(business_file_handler)
```

### 3. 批量替换print语句

在 `batch_main.py` 中将所有相关的 `print()` 语句替换为 `log_and_print()`：

```python
# 导入统一输出函数
from network_diagnosis.logger import get_logger, log_and_print

# 替换示例
# 原来：print(f"配置文件: {config_file}")
# 现在：log_and_print(f"配置文件: {config_file}")

# 错误信息使用ERROR级别
# log_and_print(f"错误: 配置文件不存在", "ERROR")
```

## 📊 实现效果对比

### **控制台输出（用户体验）**

**优化前**：
```
2025-09-10 16:08:31,917 - __main__ - INFO - Starting batch diagnosis...
📝 日志文件: log/config/diagnosis_xxx.log
2025-09-10 16:08:31,917 - business_log - INFO - 📝 日志文件: log/config/diagnosis_xxx.log
2025-09-10 16:08:31,917 - business_log - INFO - ================================================================================
================================================================================
2025-09-10 16:08:31,917 - business_log - INFO - 批量网络诊断结果摘要
批量网络诊断结果摘要
```
❌ **问题**：重复输出，冗长难读

**优化后**：
```
2025-09-10 16:21:48,778 - __main__ - INFO - Starting batch diagnosis from config: input/google_test.yaml
📝 日志文件: log/google_test/diagnosis_20250910_162148.log
2025-09-10 16:21:48,778 - network_diagnosis.batch_runner - INFO - Starting batch diagnosis...

================================================================================
批量网络诊断结果摘要
================================================================================
配置文件: input/google_test.yaml
总目标数: 2
成功诊断: 2
失败诊断: 0
成功率: 100.0%
```
✅ **效果**：简洁美观，易于阅读

### **日志文件（完整记录）**

```
2025-09-10 16:21:49,678 - business_log - INFO - 📝 日志文件: log/google_test/diagnosis_20250910_162148.log
2025-09-10 16:21:49,678 - network_diagnosis.batch_runner - INFO - Starting batch diagnosis...
2025-09-10 16:21:49,678 - business_log - INFO - ================================================================================
2025-09-10 16:21:49,678 - business_log - INFO - 批量网络诊断结果摘要
2025-09-10 16:21:49,678 - business_log - INFO - ================================================================================
2025-09-10 16:21:49,678 - business_log - INFO - 配置文件: input/google_test.yaml
2025-09-10 16:21:49,678 - business_log - INFO - 总目标数: 2
2025-09-10 16:21:49,678 - business_log - INFO - 成功诊断: 2
2025-09-10 16:21:49,678 - business_log - INFO - 失败诊断: 0
2025-09-10 16:21:49,678 - business_log - INFO - 成功率: 100.0%
2025-09-10 16:21:49,678 - business_log - INFO - 总执行时间: 898.93ms
```
✅ **效果**：包含所有业务日志，带时间戳，便于追踪

## 🎯 功能特点

### 1. **双重输出机制**
- **控制台**：美观的用户友好格式
- **日志文件**：详细的带时间戳记录

### 2. **智能日志分离**
- **系统日志**：通过标准logger记录，同时输出到控制台和文件
- **业务日志**：通过business_log记录器，只输出到文件，避免重复

### 3. **灵活的级别控制**
```python
log_and_print("正常信息", "INFO")      # 默认INFO级别
log_and_print("警告信息", "WARNING")   # 警告级别
log_and_print("错误信息", "ERROR")     # 错误级别
log_and_print("调试信息", "DEBUG")     # 调试级别
```

### 4. **可选的仅日志模式**
```python
log_and_print("仅记录到日志", log_only=True)  # 不输出到控制台
```

## 📁 目录结构效果

```
log/
├── google_test/
│   ├── diagnosis_20250910_160703.log    # 第一次执行
│   └── diagnosis_20250910_162148.log    # 第二次执行
├── nssa_io_simple/
│   ├── diagnosis_20250910_160616.log
│   └── diagnosis_20250910_162038.log
└── cubemgr-mobile_simple/
    ├── diagnosis_20250910_160831.log
    ├── diagnosis_20250910_161251.log
    ├── diagnosis_20250910_161353.log
    └── diagnosis_20250910_161410.log
```

## ✅ 验证结果

### 测试1：Google服务测试
```bash
uv run python batch_main.py -c google_test.yaml
```
**控制台输出**：✅ 简洁美观，无重复信息
**日志文件**：✅ 完整记录所有业务日志（65行）
**执行结果**：✅ 2/2 目标成功

### 测试2：nssa.io测试
```bash
uv run python batch_main.py -c nssa_io_simple.yaml
```
**控制台输出**：✅ 包含完整的批量诊断结果摘要
**日志文件**：✅ 记录了所有执行步骤和结果
**执行结果**：✅ 1/1 目标成功，包含网络路径追踪

## 🏆 方案3优势总结

1. **最佳用户体验**：控制台输出保持美观，易于实时查看
2. **完整日志记录**：所有业务信息都被详细保存到文件
3. **智能分离**：避免了重复输出的问题
4. **向后兼容**：不影响现有的系统日志功能
5. **灵活扩展**：支持不同日志级别和输出模式
6. **生产就绪**：适合实际部署和长期使用

## 🎉 总结

方案3的实现完美解决了业务日志收集的需求：
- ✅ **控制台美观**：用户看到的是简洁易读的输出
- ✅ **日志完整**：文件中保存了所有业务执行信息
- ✅ **无重复输出**：通过智能的日志记录器分离机制
- ✅ **易于维护**：统一的输出函数，便于后续扩展

现在所有的业务日志都被完整地保存到了对应配置文件的日志目录中，实现了您的需求！
