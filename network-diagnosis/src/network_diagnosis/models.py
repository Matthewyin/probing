"""
数据模型定义 - 使用Pydantic进行数据验证和序列化
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse
from pydantic import BaseModel, Field, validator, model_validator


class DNSResolutionInfo(BaseModel):
    """DNS解析信息"""
    domain: str
    resolved_ips: List[str] = Field(default_factory=list, description="解析到的IP地址列表")
    primary_ip: Optional[str] = None
    resolution_time_ms: float = Field(..., description="DNS解析时间（毫秒）")
    dns_server: Optional[str] = None
    record_type: str = "A"  # A, AAAA, CNAME等
    ttl: Optional[int] = None
    is_successful: bool
    error_message: Optional[str] = None


class TCPConnectionInfo(BaseModel):
    """TCP连接信息"""
    host: str
    port: int
    target_ip: str
    connect_time_ms: float = Field(..., description="连接时间（毫秒）")
    is_connected: bool
    socket_family: str = "IPv4"  # IPv4 或 IPv6
    local_address: Optional[str] = None
    local_port: Optional[int] = None
    error_message: Optional[str] = None


class SSLCertificateInfo(BaseModel):
    """SSL证书信息"""
    subject: Dict[str, str]
    issuer: Dict[str, str]
    version: int
    serial_number: str
    not_before: datetime
    not_after: datetime
    signature_algorithm: str
    public_key_algorithm: str
    public_key_size: Optional[int] = None
    fingerprint_sha256: str
    is_expired: bool
    days_until_expiry: int


class TLSInfo(BaseModel):
    """TLS/SSL连接信息"""
    protocol_version: str
    cipher_suite: str
    certificate: Optional[SSLCertificateInfo] = None
    certificate_chain_length: int = 0
    is_secure: bool
    handshake_time_ms: float = Field(..., description="TLS握手时间（毫秒）")


class HTTPResponseInfo(BaseModel):
    """HTTP响应信息"""
    status_code: int
    reason_phrase: str
    headers: Dict[str, str]
    response_time_ms: float = Field(..., description="响应时间（毫秒）")
    content_length: Optional[int] = None
    content_type: Optional[str] = None
    server: Optional[str] = None
    redirect_count: int = 0
    final_url: str


class TraceRouteHop(BaseModel):
    """路由跟踪跳点信息"""
    hop_number: int
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    response_times_ms: List[float] = Field(default_factory=list)
    avg_response_time_ms: Optional[float] = None
    packet_loss_percent: float = 0.0

    # mtr增强字段
    asn: Optional[str] = Field(None, description="自治系统号")
    packets_sent: Optional[int] = Field(None, description="发送的数据包数量")
    best_time_ms: Optional[float] = Field(None, description="最佳响应时间")
    worst_time_ms: Optional[float] = Field(None, description="最差响应时间")
    std_dev_ms: Optional[float] = Field(None, description="响应时间标准差")


class NetworkPathInfo(BaseModel):
    """网络路径信息"""
    target_host: str
    target_ip: Optional[str] = None
    trace_method: str = Field(..., description="使用的跟踪方法：mtr或traceroute")
    hops: List[TraceRouteHop] = Field(default_factory=list)
    total_hops: int = 0
    avg_latency_ms: Optional[float] = None
    packet_loss_percent: float = 0.0


class ICMPInfo(BaseModel):
    """ICMP探测信息"""
    target_host: str = Field(..., description="目标主机")
    target_ip: str = Field(..., description="目标IP地址")
    packets_sent: int = Field(..., description="发送的数据包数量")
    packets_received: int = Field(..., description="接收的数据包数量")
    packet_loss_percent: float = Field(..., description="丢包率（百分比）")

    # 时间统计（毫秒）
    min_rtt_ms: Optional[float] = Field(None, description="最小往返时间")
    max_rtt_ms: Optional[float] = Field(None, description="最大往返时间")
    avg_rtt_ms: Optional[float] = Field(None, description="平均往返时间")
    std_dev_rtt_ms: Optional[float] = Field(None, description="往返时间标准差")

    # 探测配置
    packet_size: int = Field(default=32, description="数据包大小（字节）")
    timeout_ms: int = Field(default=1000, description="超时时间（毫秒）")

    # 执行信息
    ping_command: str = Field(..., description="执行的ping命令")
    execution_time_ms: float = Field(..., description="总执行时间")
    is_successful: bool = Field(..., description="探测是否成功")
    error_message: Optional[str] = Field(None, description="错误信息")


class PublicIPInfo(BaseModel):
    """公网IP信息"""
    ip: str = Field(..., description="公网IP地址")
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    isp: Optional[str] = None
    continent: Optional[str] = None
    zipcode: Optional[str] = None
    adcode: Optional[str] = None
    service_provider: Optional[str] = None  # 数据来源服务商
    query_time_ms: Optional[float] = None   # 查询耗时


class NetworkDiagnosisResult(BaseModel):
    """网络诊断完整结果"""
    domain: str
    target_ip: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    # URL相关信息（方案2：添加URL标识字段）
    original_url: Optional[str] = None
    url_path: Optional[str] = None
    url_protocol: Optional[str] = None
    is_url_based: bool = False

    # 各项诊断结果
    dns_resolution: Optional[DNSResolutionInfo] = None
    tcp_connection: Optional[TCPConnectionInfo] = None
    tls_info: Optional[TLSInfo] = None
    http_response: Optional[HTTPResponseInfo] = None
    network_path: Optional[NetworkPathInfo] = None
    icmp_info: Optional[ICMPInfo] = None  # 新增：ICMP探测信息
    public_ip_info: Optional[PublicIPInfo] = None  # 发起端公网IP信息

    # 总体统计
    total_diagnosis_time_ms: float = Field(..., description="总诊断时间（毫秒）")
    success: bool = Field(..., description="诊断是否成功完成")
    error_messages: List[str] = Field(default_factory=list)
    
    @validator('domain')
    def validate_domain(cls, v):
        """验证域名格式"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Domain cannot be empty")
        return v.strip().lower()
    
    def to_json_dict(self) -> Dict[str, Any]:
        """转换为JSON字典，处理datetime序列化"""
        return self.model_dump(mode='json')


class DiagnosisRequest(BaseModel):
    """诊断请求模型"""
    domain: Optional[str] = None
    port: int = 443
    url: Optional[str] = None  # 新增：支持URL输入
    include_trace: bool = True
    include_http: bool = True
    include_tls: bool = True
    include_icmp: bool = True  # 新增：是否包含ICMP探测

    # 解析后的URL组件（自动填充）
    parsed_domain: Optional[str] = None
    parsed_port: Optional[int] = None
    parsed_protocol: Optional[str] = None
    parsed_path: Optional[str] = None
    
    def __init__(self, **data):
        """初始化时解析URL或验证domain"""
        super().__init__(**data)

        # 如果提供了URL，解析URL并填充相关字段
        if self.url:
            self._parse_url()
        elif self.domain:
            # 如果只提供了domain，使用domain
            self.parsed_domain = self.domain.strip().lower()
            self.parsed_port = self.port
            self.parsed_protocol = "https" if self.port == 443 else "http"
            self.parsed_path = "/"
        else:
            raise ValueError("Either 'domain' or 'url' must be provided")

    def _parse_url(self):
        """解析URL并填充相关字段"""
        if not self.url:
            return

        parsed = urlparse(self.url)

        if not parsed.netloc:
            raise ValueError(f"Invalid URL: {self.url}")

        # 提取域名
        self.parsed_domain = parsed.hostname
        if not self.parsed_domain:
            raise ValueError(f"Cannot extract domain from URL: {self.url}")

        # 提取协议
        self.parsed_protocol = parsed.scheme or "http"
        if self.parsed_protocol not in ["http", "https"]:
            raise ValueError(f"Unsupported protocol: {self.parsed_protocol}")

        # 提取端口
        if parsed.port:
            self.parsed_port = parsed.port
        else:
            self.parsed_port = 443 if self.parsed_protocol == "https" else 80

        # 提取路径
        self.parsed_path = parsed.path or "/"
        if parsed.query:
            self.parsed_path += f"?{parsed.query}"

        # 更新domain和port字段以保持兼容性
        self.domain = self.parsed_domain
        self.port = self.parsed_port

    @model_validator(mode='after')
    def validate_domain_or_url_final(self):
        """最终验证domain和url"""
        if not self.domain and not self.url:
            raise ValueError("Either 'domain' or 'url' must be provided")
        return self

    @validator('port')
    def validate_port(cls, v):
        """验证端口范围"""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @validator('url')
    def validate_url(cls, v):
        """验证URL格式"""
        if v and not v.strip():
            raise ValueError("URL cannot be empty")
        return v.strip() if v else v
