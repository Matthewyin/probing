# Input目录实现总结

## 🎯 实现目标

根据用户需求，将所有拨测配置文件（YAML文件）统一放到专门的 `input/` 目录下，实现输入配置和输出结果的清晰分离。

## 📁 目录结构优化

### 优化前的结构
```
network-diagnosis/
├── src/                           # 源代码
├── output/                        # 输出结果
├── targets.yaml                   # 配置文件散落在根目录
├── targets_simple.yaml
├── test_nssa_io.yaml
├── targets_sample.yaml
├── main.py
├── batch_main.py
└── ...
```

**问题**：
- 配置文件与代码文件混在一起
- 项目根目录显得杂乱
- 输入和输出没有明确分离

### 优化后的清晰结构
```
network-diagnosis/
├── src/                           # 源代码目录
│   └── network_diagnosis/
│       ├── diagnosis.py
│       ├── services.py
│       └── ... (其他模块)
├── input/                         # 输入配置目录 ✨ 新增
│   ├── targets.yaml              # 默认配置文件
│   ├── targets_simple.yaml       # 简单测试配置
│   ├── test_nssa_io.yaml         # nssa.io测试配置
│   └── targets_sample.yaml       # 示例配置文件
├── output/                        # 输出结果目录
│   ├── targets/                   # 基于targets.yaml的结果
│   ├── test_nssa_io/             # 基于test_nssa_io.yaml的结果
│   └── ... (其他配置的结果)
├── doc/                          # 文档目录
├── main.py                       # 单个诊断入口
├── batch_main.py                 # 批量诊断入口
├── config.py                     # 全局配置
└── ... (其他项目文件)
```

## 🔧 技术实现

### 1. 智能路径解析功能

新增了 `resolve_config_path()` 函数，支持多种配置文件路径格式：

```python
def resolve_config_path(config_path: str) -> str:
    """
    解析配置文件路径，支持智能查找
    
    Rules:
        1. 如果是绝对路径，直接使用
        2. 如果包含路径分隔符，按相对路径处理
        3. 如果只是文件名，在input目录中查找
    """
    config_path = Path(config_path)
    
    # 如果是绝对路径，直接返回
    if config_path.is_absolute():
        return str(config_path)
    
    # 如果包含路径分隔符（如 input/xxx.yaml），按相对路径处理
    if len(config_path.parts) > 1:
        return str(config_path)
    
    # 如果只是文件名，在input目录中查找
    input_path = Path("input") / config_path
    if input_path.exists():
        return str(input_path)
    
    # 如果input目录中不存在，返回原路径（让后续错误处理）
    return str(config_path)
```

### 2. 默认路径更新

更新了所有相关类和函数的默认配置文件路径：

#### batch_main.py
```python
# 更新前
default="targets.yaml"

# 更新后  
default="input/targets.yaml"
```

#### ConfigLoader类
```python
# 更新前
def __init__(self, config_file: str = "targets.yaml"):

# 更新后
def __init__(self, config_file: str = "input/targets.yaml"):
```

#### BatchDiagnosisRunner类
```python
# 更新前
def __init__(self, config_file: str = "targets.yaml"):

# 更新后
def __init__(self, config_file: str = "input/targets.yaml"):
```

### 3. 示例配置文件创建增强

更新了示例配置文件的创建逻辑：

```python
def create_sample_config(self, output_file: str = "input/targets_sample.yaml"):
    """创建示例配置文件"""
    # ... 配置内容定义
    
    # 确保输出目录存在
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(sample_config, f, default_flow_style=False, allow_unicode=True, indent=2)
```

## ✅ 功能验证

### 1. 完整路径测试
```bash
uv run python batch_main.py -c input/test_nssa_io.yaml
```
**结果**：✅ 正常工作，使用指定的完整路径

### 2. 简化路径测试（智能查找）
```bash
uv run python batch_main.py -c test_nssa_io.yaml
```
**结果**：✅ 自动在input目录中查找并使用 `input/test_nssa_io.yaml`

### 3. 默认配置文件测试
```bash
uv run python batch_main.py
```
**结果**：✅ 自动使用 `input/targets.yaml` 作为默认配置

### 4. 示例配置文件创建测试
```bash
uv run python batch_main.py --create-sample
```
**结果**：✅ 在 `input/targets_sample.yaml` 创建示例配置文件

## 🎯 用户体验提升

### 1. 多种使用方式支持

用户现在可以使用多种方式指定配置文件：

```bash
# 方式1：使用完整路径
python batch_main.py -c input/my_config.yaml

# 方式2：使用简化路径（推荐）
python batch_main.py -c my_config.yaml

# 方式3：使用默认配置
python batch_main.py

# 方式4：使用相对路径
python batch_main.py -c ../other_configs/special.yaml
```

### 2. 清晰的错误提示

当配置文件不存在时，提供更友好的错误信息：

```
错误: 配置文件不存在: input/nonexistent.yaml
使用 --create-sample 创建示例配置文件
提示: 配置文件应放在 input/ 目录下
```

### 3. 更新的帮助信息

```bash
示例用法:
  python batch_main.py                           # 使用默认配置文件 input/targets.yaml
  python batch_main.py -c input/custom.yaml     # 使用自定义配置文件
  python batch_main.py -c custom.yaml           # 自动在input目录中查找
  python batch_main.py --create-sample          # 创建示例配置文件
  python batch_main.py --validate               # 验证配置文件格式
```

## 📊 实际测试结果

### 测试1：智能路径解析
```bash
# 输入：test_nssa_io.yaml
# 解析：input/test_nssa_io.yaml
# 输出：output/test_nssa_io/
# 结果：✅ 成功，2/2 目标诊断成功
```

### 测试2：默认配置文件
```bash
# 输入：（无，使用默认）
# 解析：input/targets.yaml
# 输出：output/targets/
# 结果：✅ 成功，4/7 目标诊断成功（部分网络限制正常）
```

### 测试3：示例配置创建
```bash
# 命令：--create-sample
# 创建：input/targets_sample.yaml
# 结果：✅ 成功创建示例配置文件
```

## 🏗️ 目录结构最终效果

```
network-diagnosis/
├── input/                         # 📁 输入配置目录
│   ├── targets.yaml              # 默认配置文件
│   ├── targets_simple.yaml       # 简单测试配置
│   ├── test_nssa_io.yaml         # nssa.io测试配置
│   └── targets_sample.yaml       # 示例配置文件
├── output/                        # 📁 输出结果目录
│   ├── targets/                   # targets.yaml的结果
│   │   ├── network_diagnosis_github.com_443_*.json
│   │   ├── network_diagnosis_stackoverflow.com_443_*.json
│   │   └── ... (其他结果)
│   └── test_nssa_io/             # test_nssa_io.yaml的结果
│       ├── network_diagnosis_nssa.io_443_*.json
│       └── network_diagnosis_nssa.io_80_*.json
├── src/                          # 📁 源代码目录
│   └── network_diagnosis/
├── doc/                          # 📁 文档目录
├── main.py                       # 单个诊断入口
├── batch_main.py                 # 批量诊断入口
└── config.py                     # 全局配置
```

## 🎉 总结

通过实现input目录功能，我们成功实现了：

1. **清晰的目录分离**：输入配置（input/）和输出结果（output/）完全分离
2. **智能路径解析**：支持多种配置文件路径格式，用户体验友好
3. **向后兼容**：所有现有功能保持不变，无破坏性变更
4. **便于管理**：配置文件统一管理，项目结构更加清晰
5. **用户友好**：提供多种使用方式和清晰的错误提示

这个实现不仅满足了用户的需求，还提升了整个项目的组织性和可维护性，为后续的功能扩展奠定了良好的基础。
