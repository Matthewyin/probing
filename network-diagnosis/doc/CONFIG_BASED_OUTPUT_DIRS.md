# 基于配置文件的输出目录功能

## 🎯 功能概述

根据用户需求，实现了基于不同配置文件的独立子目录输出功能。现在每个配置文件的测试结果都会输出到独立的子目录中，便于组织和管理不同批次的测试结果。

## 🏗️ 实现原理

### 目录命名规则
- 从配置文件路径提取文件名（不含扩展名）
- 在 `output/` 目录下创建以配置文件名命名的子目录
- 例如：`test_nssa_io.yaml` → `output/test_nssa_io/`

### 代码修改点

#### 1. 诊断协调器增强 (`diagnosis.py`)
```python
class NetworkDiagnosisCoordinator:
    def __init__(self, output_dir: Optional[str] = None):
        # ... 现有服务初始化
        self.output_dir = output_dir  # 支持自定义输出目录

    def save_result_to_file(self, result: NetworkDiagnosisResult) -> str:
        # 使用自定义输出目录或默认目录
        base_dir = self.output_dir if self.output_dir else settings.OUTPUT_DIR
        filepath = Path(base_dir) / filename
```

#### 2. 诊断运行器更新 (`diagnosis.py`)
```python
class DiagnosisRunner:
    def __init__(self, output_dir: Optional[str] = None):
        self.coordinator = NetworkDiagnosisCoordinator(output_dir)
```

#### 3. 批量诊断运行器增强 (`batch_runner.py`)
```python
class BatchDiagnosisRunner:
    def __init__(self, config_file: str = "targets.yaml"):
        # 生成基于配置文件的输出子目录
        config_name = Path(config_file).stem  # 获取文件名（不含扩展名）
        self.output_subdir = Path(settings.OUTPUT_DIR) / config_name
        
        # 创建诊断运行器，使用子目录作为输出目录
        self.diagnosis_runner = DiagnosisRunner(str(self.output_subdir))
```

## 📊 实际效果展示

### 目录结构对比

#### 修改前（所有结果混在一起）
```
output/
├── network_diagnosis_nssa.io_443_*.json
├── network_diagnosis_nssa.io_80_*.json
├── network_diagnosis_google.com_443_*.json
├── network_diagnosis_github.com_443_*.json
└── network_diagnosis_httpbin.org_80_*.json
```

#### 修改后（按配置文件分组）
```
output/
├── test_nssa_io/                    # test_nssa_io.yaml 的结果
│   ├── network_diagnosis_nssa.io_443_20250910_143809_156.json
│   └── network_diagnosis_nssa.io_80_20250910_143809_320.json
├── targets_simple/                 # targets_simple.yaml 的结果
│   ├── network_diagnosis_github.com_443_20250910_143844_495.json
│   ├── network_diagnosis_google.com_443_20250910_143854_500.json
│   └── network_diagnosis_httpbin.org_80_20250910_143856_256.json
└── network_diagnosis_httpbin.org_80_20250910_143928_730.json  # 单个诊断结果
```

### 测试日志示例

```bash
# 使用 test_nssa_io.yaml 配置
2025-09-10 14:38:08,352 - src.network_diagnosis.batch_runner - INFO - Starting batch diagnosis from config file: test_nssa_io.yaml
2025-09-10 14:38:08,352 - src.network_diagnosis.batch_runner - INFO - Output directory: output/test_nssa_io
2025-09-10 14:38:09,157 - src.network_diagnosis.diagnosis - INFO - Diagnosis result saved to output/test_nssa_io/network_diagnosis_nssa.io_443_20250910_143809_156.json

# 使用 targets_simple.yaml 配置
2025-09-10 14:38:34,475 - src.network_diagnosis.batch_runner - INFO - Starting batch diagnosis from config file: targets_simple.yaml
2025-09-10 14:38:34,475 - src.network_diagnosis.batch_runner - INFO - Output directory: output/targets_simple
2025-09-10 14:38:44,497 - src.network_diagnosis.diagnosis - INFO - Diagnosis result saved to output/targets_simple/network_diagnosis_github.com_443_20250910_143844_495.json
```

## ✅ 功能特点

### 1. 自动目录创建
- 批量诊断开始时自动创建子目录
- 使用 `mkdir(parents=True, exist_ok=True)` 确保目录存在
- 避免手动创建目录的麻烦

### 2. 向后兼容
- **单个诊断**：仍然使用默认的 `output/` 目录
- **批量诊断**：使用基于配置文件的子目录
- 现有脚本和工具无需修改

### 3. 清晰的组织结构
- 每个配置文件的结果独立存储
- 便于按项目、环境、测试批次分类
- 避免不同测试结果混淆

### 4. 灵活的命名规则
- 基于配置文件名自动生成目录名
- 支持任意配置文件名（如 `prod_servers.yaml` → `output/prod_servers/`）
- 目录名清晰易懂

## 🎯 使用场景

### 1. 多环境测试
```bash
# 开发环境测试
uv run python batch_main.py -c dev_targets.yaml
# 结果保存到: output/dev_targets/

# 生产环境测试
uv run python batch_main.py -c prod_targets.yaml
# 结果保存到: output/prod_targets/

# 测试环境测试
uv run python batch_main.py -c test_targets.yaml
# 结果保存到: output/test_targets/
```

### 2. 不同项目测试
```bash
# 项目A的网络诊断
uv run python batch_main.py -c project_a_servers.yaml
# 结果保存到: output/project_a_servers/

# 项目B的网络诊断
uv run python batch_main.py -c project_b_services.yaml
# 结果保存到: output/project_b_services/
```

### 3. 定期监控
```bash
# 每日监控
uv run python batch_main.py -c daily_monitoring.yaml
# 结果保存到: output/daily_monitoring/

# 每周深度检查
uv run python batch_main.py -c weekly_deep_check.yaml
# 结果保存到: output/weekly_deep_check/
```

## 📈 分析便利性

### 1. 按配置分析
```python
import glob
import json

def analyze_config_results(config_name):
    """分析特定配置的所有结果"""
    pattern = f"output/{config_name}/network_diagnosis_*.json"
    files = glob.glob(pattern)
    
    results = []
    for file in files:
        with open(file, 'r') as f:
            results.append(json.load(f))
    
    return results

# 分析 test_nssa_io 配置的结果
nssa_results = analyze_config_results("test_nssa_io")
print(f"nssa.io 测试结果: {len(nssa_results)} 个目标")
```

### 2. 跨配置对比
```python
def compare_configs(config1, config2):
    """对比两个配置的测试结果"""
    results1 = analyze_config_results(config1)
    results2 = analyze_config_results(config2)
    
    # 对比成功率、平均响应时间等
    success_rate1 = sum(1 for r in results1 if r['success']) / len(results1)
    success_rate2 = sum(1 for r in results2 if r['success']) / len(results2)
    
    print(f"{config1} 成功率: {success_rate1:.1%}")
    print(f"{config2} 成功率: {success_rate2:.1%}")

# 对比不同环境的测试结果
compare_configs("dev_targets", "prod_targets")
```

### 3. 历史趋势分析
```python
def analyze_trends(config_name, days=7):
    """分析特定配置的历史趋势"""
    pattern = f"output/{config_name}/network_diagnosis_*.json"
    files = sorted(glob.glob(pattern))
    
    # 按时间分组分析
    daily_stats = {}
    for file in files:
        # 从文件名提取日期
        # 分析每日的成功率、响应时间等
        pass
    
    return daily_stats
```

## 🔧 配置建议

### 1. 命名规范
建议使用有意义的配置文件名：
- `prod_web_servers.yaml` - 生产环境Web服务器
- `dev_api_endpoints.yaml` - 开发环境API端点
- `monitoring_critical.yaml` - 关键服务监控
- `daily_health_check.yaml` - 日常健康检查

### 2. 目录管理
```bash
# 定期清理旧结果
find output/ -name "*.json" -mtime +30 -delete

# 按月归档
mkdir -p archive/2025-09/
mv output/*/network_diagnosis_*_202509*.json archive/2025-09/
```

## 🎉 总结

这个功能增强带来了以下好处：

1. **更好的组织性**：不同配置的结果分别存储，避免混乱
2. **便于管理**：可以按项目、环境、时间等维度组织测试结果
3. **简化分析**：针对特定配置的结果分析更加方便
4. **向后兼容**：现有功能和脚本无需修改
5. **自动化友好**：支持自动化脚本和CI/CD集成

现在您可以为不同的测试场景创建不同的配置文件，每个配置文件的结果都会整齐地存储在独立的子目录中，大大提升了测试结果的管理效率！
