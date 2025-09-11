"""
配置文件加载器 - 支持从YAML文件加载诊断目标
"""
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, validator, model_validator

from .models import DiagnosisRequest
from .logger import get_logger

logger = get_logger(__name__)


class TargetConfig(BaseModel):
    """单个诊断目标配置"""
    domain: Optional[str] = None
    port: int = 443
    url: Optional[str] = None  # 新增：支持URL配置
    include_trace: bool = False
    include_http: bool = True
    include_tls: bool = True
    include_icmp: bool = True  # 新增：是否包含ICMP探测
    description: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_domain_or_url(self):
        """验证domain和url至少提供一个"""
        if not self.domain and not self.url:
            raise ValueError("Either 'domain' or 'url' must be provided")

        # 如果提供了domain，验证格式
        if self.domain and not self.url:
            if not self.domain or len(str(self.domain).strip()) == 0:
                raise ValueError("Domain cannot be empty")
            self.domain = str(self.domain).strip().lower()

        return self
    
    @validator('port')
    def validate_port(cls, v):
        """验证端口范围"""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class GlobalSettings(BaseModel):
    """全局配置设置"""
    default_port: int = 443
    default_include_trace: bool = False
    default_include_http: bool = True
    default_include_tls: bool = True
    default_include_icmp: bool = True
    
    save_individual_files: bool = True
    save_summary_report: bool = False  # 默认关闭批量汇总报告
    
    max_concurrent: int = 3
    timeout_seconds: int = 60
    
    include_performance_analysis: bool = True
    include_security_analysis: bool = True
    
    @validator('max_concurrent')
    def validate_max_concurrent(cls, v):
        """验证并发数"""
        if not 1 <= v <= 10:
            raise ValueError("max_concurrent must be between 1 and 10")
        return v
    
    @validator('timeout_seconds')
    def validate_timeout(cls, v):
        """验证超时时间"""
        if not 10 <= v <= 300:
            raise ValueError("timeout_seconds must be between 10 and 300")
        return v


class SchedulerConfig(BaseModel):
    """调度器配置"""
    enabled: bool = False
    timezone: str = "Asia/Shanghai"
    trigger_type: Literal["cron", "interval"] = "cron"

    # cron配置
    cron: Optional[str] = None

    # interval配置
    interval_minutes: Optional[int] = None
    interval_hours: Optional[int] = None

    # 调度器选项
    max_instances: int = 1
    coalesce: bool = True
    misfire_grace_time: int = 300

    @model_validator(mode='after')
    def validate_trigger_config(self):
        """验证触发器配置"""
        if not self.enabled:
            return self

        if self.trigger_type == "cron":
            if not self.cron:
                raise ValueError("cron expression is required when trigger_type is 'cron'")
        elif self.trigger_type == "interval":
            if not self.interval_minutes and not self.interval_hours:
                raise ValueError("interval_minutes or interval_hours is required when trigger_type is 'interval'")
            if self.interval_minutes and self.interval_hours:
                raise ValueError("Only one of interval_minutes or interval_hours should be specified")

        return self

    @validator('interval_minutes')
    def validate_interval_minutes(cls, v):
        """验证分钟间隔"""
        if v is not None and not 1 <= v <= 1440:  # 1分钟到24小时
            raise ValueError("interval_minutes must be between 1 and 1440")
        return v

    @validator('interval_hours')
    def validate_interval_hours(cls, v):
        """验证小时间隔"""
        if v is not None and not 1 <= v <= 168:  # 1小时到7天
            raise ValueError("interval_hours must be between 1 and 168")
        return v

    @validator('max_instances')
    def validate_max_instances(cls, v):
        """验证最大实例数"""
        if not 1 <= v <= 5:
            raise ValueError("max_instances must be between 1 and 5")
        return v

    @validator('misfire_grace_time')
    def validate_misfire_grace_time(cls, v):
        """验证错过执行宽限时间"""
        if not 0 <= v <= 3600:  # 0到1小时
            raise ValueError("misfire_grace_time must be between 0 and 3600 seconds")
        return v


class DiagnosisConfig(BaseModel):
    """完整的诊断配置"""
    targets: List[TargetConfig]
    global_settings: GlobalSettings = Field(default_factory=GlobalSettings)
    scheduler: Optional[SchedulerConfig] = None

    @validator('targets')
    def validate_targets(cls, v):
        """验证目标列表"""
        if not v:
            raise ValueError("At least one target must be specified")
        return v


class ConfigLoader:
    """配置文件加载器"""
    
    def __init__(self, config_file: str = "input/targets.yaml"):
        self.config_file = Path(config_file)
        self.config: Optional[DiagnosisConfig] = None
    
    def load_config(self) -> DiagnosisConfig:
        """加载配置文件"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
            
            logger.info(f"Loading configuration from {self.config_file}")
            
            # 解析配置
            self.config = DiagnosisConfig(**raw_config)
            
            # 应用全局默认值到目标配置
            self._apply_global_defaults()
            
            logger.info(f"Loaded {len(self.config.targets)} targets from configuration")
            
            return self.config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in {self.config_file}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {str(e)}")
    
    def _apply_global_defaults(self):
        """将全局默认值应用到目标配置"""
        if not self.config:
            return
        
        global_settings = self.config.global_settings
        
        for target in self.config.targets:
            # 如果目标没有指定端口，使用全局默认值
            if not hasattr(target, '_port_explicitly_set'):
                # 检查原始配置中是否明确设置了端口
                # 这里简化处理，假设443是默认值
                pass
    
    def get_diagnosis_requests(self) -> List[DiagnosisRequest]:
        """将配置转换为诊断请求列表"""
        if not self.config:
            raise ValueError("Configuration not loaded. Call load_config() first.")
        
        requests = []
        for target in self.config.targets:
            # 构建请求参数
            request_params = {
                'include_trace': target.include_trace,
                'include_http': target.include_http,
                'include_tls': target.include_tls,
                'include_icmp': target.include_icmp
            }

            # 根据配置类型添加domain/port或url
            if target.url:
                request_params['url'] = target.url
            else:
                request_params['domain'] = target.domain
                request_params['port'] = target.port

            request = DiagnosisRequest(**request_params)
            requests.append(request)
        
        return requests
    
    def get_target_description(self, domain: str, port: int) -> Optional[str]:
        """获取目标的描述信息"""
        if not self.config:
            return None
        
        for target in self.config.targets:
            if target.domain == domain and target.port == port:
                return target.description
        
        return None
    
    def get_global_settings(self) -> GlobalSettings:
        """获取全局设置"""
        if not self.config:
            raise ValueError("Configuration not loaded. Call load_config() first.")

        return self.config.global_settings

    def get_scheduler_config(self) -> Optional[SchedulerConfig]:
        """获取调度器配置"""
        if not self.config:
            raise ValueError("Configuration not loaded. Call load_config() first.")

        return self.config.scheduler

    def has_scheduler_config(self) -> bool:
        """检查是否有调度器配置且已启用"""
        scheduler_config = self.get_scheduler_config()
        return scheduler_config is not None and scheduler_config.enabled

    def validate_config_file(self, config_file: str) -> bool:
        """验证配置文件格式"""
        try:
            temp_loader = ConfigLoader(config_file)
            temp_loader.load_config()
            return True
        except Exception as e:
            logger.error(f"Configuration validation failed: {str(e)}")
            return False
    
    def create_sample_config(self, output_file: str = "input/targets_sample.yaml"):
        """创建示例配置文件"""
        sample_config = {
            'targets': [
                {
                    'domain': 'google.com',
                    'port': 443,
                    'include_trace': False,
                    'include_http': True,
                    'include_tls': True,
                    'include_icmp': True,
                    'description': 'Google搜索引擎'
                },
                {
                    'domain': 'github.com',
                    'port': 443,
                    'include_trace': False,
                    'include_http': True,
                    'include_tls': True,
                    'include_icmp': True,
                    'description': 'GitHub代码托管平台'
                },
                {
                    'domain': 'httpbin.org',
                    'port': 80,
                    'include_trace': False,
                    'include_http': True,
                    'include_tls': False,
                    'include_icmp': True,
                    'description': 'HTTP测试服务'
                },
                {
                    'url': 'https://api.github.com/users/octocat',
                    'include_trace': False,
                    'include_http': True,
                    'include_tls': True,
                    'include_icmp': True,
                    'description': 'GitHub API - URL示例'
                },
                {
                    'url': 'http://httpbin.org/get?param=test',
                    'include_trace': False,
                    'include_http': True,
                    'include_tls': False,
                    'include_icmp': True,
                    'description': 'HTTP测试API - URL示例'
                }
            ],
            'global_settings': {
                'default_port': 443,
                'default_include_trace': False,
                'default_include_http': True,
                'default_include_tls': True,
                'default_include_icmp': True,
                'save_individual_files': True,
                'save_summary_report': False,  # 默认关闭批量汇总报告
                'max_concurrent': 3,
                'timeout_seconds': 60,
                'include_performance_analysis': True,
                'include_security_analysis': True
            },
            'scheduler': {
                'enabled': False,  # 默认关闭调度器
                'timezone': 'Asia/Shanghai',
                'trigger_type': 'cron',
                'cron': '0 */2 * * *',  # 每2小时执行一次
                # 'trigger_type': 'interval',  # 或使用间隔触发
                # 'interval_hours': 2,  # 每2小时执行一次
                'max_instances': 1,
                'coalesce': True,
                'misfire_grace_time': 300
            }
        }

        # 确保输出目录存在
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(sample_config, f, default_flow_style=False, allow_unicode=True, indent=2)

        logger.info(f"Sample configuration created: {output_file}")


def load_targets_from_config(config_file: str = "input/targets.yaml") -> tuple[List[DiagnosisRequest], GlobalSettings]:
    """便捷函数：从配置文件加载目标列表和全局设置"""
    loader = ConfigLoader(config_file)
    config = loader.load_config()
    requests = loader.get_diagnosis_requests()
    global_settings = loader.get_global_settings()
    
    return requests, global_settings
