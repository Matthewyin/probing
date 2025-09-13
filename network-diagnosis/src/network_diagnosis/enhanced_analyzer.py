"""
增强网络诊断分析器
提供详细的网络问题分析和解决建议
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from .logger import get_logger
from .models import EnhancedTCPConnectionInfo, EnhancedHTTPResponseInfo, EnhancedTLSInfo

logger = get_logger(__name__)


class NetworkDiagnosisAnalyzer:
    """网络诊断分析器 - 提供智能分析和建议"""
    
    def __init__(self):
        self.analysis_rules = self._load_analysis_rules()
    
    def analyze_diagnosis_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """分析诊断结果并提供详细报告"""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "target": f"{result.get('domain', 'unknown')}:{result.get('port', 'unknown')}",
            "overall_status": result.get("success", False),
            "analysis_summary": {},
            "detailed_analysis": {},
            "recommendations": [],
            "troubleshooting_guide": {},
            "performance_insights": {},
            "security_assessment": {}
        }
        
        # 分析各个组件
        analysis["detailed_analysis"]["dns"] = self._analyze_dns(result.get("dns_resolution"))
        analysis["detailed_analysis"]["tcp"] = self._analyze_tcp(result.get("tcp_connection"))
        analysis["detailed_analysis"]["tls"] = self._analyze_tls(result.get("tls_info"))
        analysis["detailed_analysis"]["http"] = self._analyze_http(result.get("http_response"))
        
        # 生成综合分析
        analysis["analysis_summary"] = self._generate_summary(analysis["detailed_analysis"])
        analysis["recommendations"] = self._generate_recommendations(analysis["detailed_analysis"])
        analysis["troubleshooting_guide"] = self._generate_troubleshooting_guide(analysis["detailed_analysis"])
        analysis["performance_insights"] = self._analyze_performance(result)
        analysis["security_assessment"] = self._assess_security(result)
        
        return analysis
    
    def _analyze_dns(self, dns_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """分析DNS解析"""
        if not dns_info:
            return {"status": "not_tested", "issues": [], "recommendations": []}
        
        analysis = {
            "status": "success" if dns_info.get("resolved_ips") else "failed",
            "resolution_time_ms": dns_info.get("resolution_time_ms", 0),
            "resolved_ips": dns_info.get("resolved_ips", []),
            "issues": [],
            "recommendations": [],
            "performance_rating": "unknown"
        }
        
        # 性能评估
        resolution_time = analysis["resolution_time_ms"]
        if resolution_time < 50:
            analysis["performance_rating"] = "excellent"
        elif resolution_time < 200:
            analysis["performance_rating"] = "good"
        elif resolution_time < 1000:
            analysis["performance_rating"] = "fair"
        else:
            analysis["performance_rating"] = "poor"
            analysis["issues"].append("DNS解析时间过长")
            analysis["recommendations"].append("考虑使用更快的DNS服务器")
        
        # 检查多IP情况
        if len(analysis["resolved_ips"]) > 1:
            analysis["recommendations"].append("目标有多个IP地址，可能使用了负载均衡")
        
        return analysis
    
    def _analyze_tcp(self, tcp_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """分析TCP连接"""
        if not tcp_info:
            return {"status": "not_tested", "issues": [], "recommendations": []}
        
        analysis = {
            "status": "success" if tcp_info.get("is_connected") else "failed",
            "connect_time_ms": tcp_info.get("connect_time_ms", 0),
            "connection_method": tcp_info.get("transport_info", {}).get("connection_method", "unknown"),
            "issues": [],
            "recommendations": [],
            "performance_rating": "unknown",
            "error_analysis": None
        }
        
        if analysis["status"] == "success":
            # 性能评估
            connect_time = analysis["connect_time_ms"]
            if connect_time < 10:
                analysis["performance_rating"] = "excellent"
            elif connect_time < 50:
                analysis["performance_rating"] = "good"
            elif connect_time < 200:
                analysis["performance_rating"] = "fair"
            else:
                analysis["performance_rating"] = "poor"
                analysis["issues"].append("TCP连接时间较长")
                analysis["recommendations"].append("检查网络延迟和服务器响应时间")
        else:
            # 错误分析
            error_classification = tcp_info.get("error_classification")
            if error_classification:
                analysis["error_analysis"] = {
                    "error_type": error_classification.get("error_type"),
                    "severity": error_classification.get("severity"),
                    "is_retryable": error_classification.get("is_retryable"),
                    "suggested_actions": error_classification.get("detailed_suggestions", []),
                    "troubleshooting_commands": error_classification.get("troubleshooting_commands", [])
                }
                analysis["issues"].append(f"TCP连接失败: {error_classification.get('error_type')}")
                analysis["recommendations"].extend(error_classification.get("detailed_suggestions", []))
        
        return analysis
    
    def _analyze_tls(self, tls_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """分析TLS连接"""
        if not tls_info:
            return {"status": "not_tested", "issues": [], "recommendations": []}
        
        analysis = {
            "status": "success" if tls_info.get("is_secure") else "failed",
            "protocol_version": tls_info.get("protocol_version"),
            "cipher_suite": tls_info.get("cipher_suite"),
            "handshake_time_ms": tls_info.get("handshake_time_ms", 0),
            "issues": [],
            "recommendations": [],
            "security_rating": "unknown",
            "certificate_analysis": None
        }
        
        if analysis["status"] == "success":
            # 协议版本检查
            protocol = analysis["protocol_version"]
            if protocol in ["TLSv1.3"]:
                analysis["security_rating"] = "excellent"
            elif protocol in ["TLSv1.2"]:
                analysis["security_rating"] = "good"
            elif protocol in ["TLSv1.1", "TLSv1.0"]:
                analysis["security_rating"] = "poor"
                analysis["issues"].append(f"使用了过时的TLS协议: {protocol}")
                analysis["recommendations"].append("升级到TLS 1.2或更高版本")
            
            # 证书分析
            cert_info = tls_info.get("certificate")
            if cert_info:
                analysis["certificate_analysis"] = self._analyze_certificate(cert_info)
        else:
            # TLS失败分析
            mutual_tls_info = tls_info.get("mutual_tls_info", {})
            ssl_type = mutual_tls_info.get("ssl_type")
            if ssl_type:
                analysis["issues"].append(f"TLS连接问题: {ssl_type}")
                if "双向SSL" in ssl_type or "client certificate" in mutual_tls_info.get("error_details", ""):
                    analysis["recommendations"].append("服务器要求客户端证书，这是双向SSL认证")
                    analysis["recommendations"].append("联系服务器管理员获取客户端证书")
        
        return analysis
    
    def _analyze_http(self, http_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """分析HTTP响应"""
        if not http_info:
            return {"status": "not_tested", "issues": [], "recommendations": []}
        
        analysis = {
            "status": "success" if http_info.get("status_code", 0) < 400 else "failed",
            "status_code": http_info.get("status_code"),
            "response_time_ms": http_info.get("response_time_ms", 0),
            "issues": [],
            "recommendations": [],
            "performance_rating": "unknown"
        }
        
        # 状态码分析
        status_code = analysis["status_code"]
        if status_code:
            if 200 <= status_code < 300:
                analysis["status"] = "success"
            elif 300 <= status_code < 400:
                analysis["issues"].append(f"HTTP重定向: {status_code}")
                analysis["recommendations"].append("检查重定向配置")
            elif 400 <= status_code < 500:
                analysis["issues"].append(f"客户端错误: {status_code}")
                analysis["recommendations"].append("检查请求格式和权限")
            elif status_code >= 500:
                analysis["issues"].append(f"服务器错误: {status_code}")
                analysis["recommendations"].append("检查服务器状态和配置")
        
        # 性能评估
        response_time = analysis["response_time_ms"]
        if response_time < 200:
            analysis["performance_rating"] = "excellent"
        elif response_time < 1000:
            analysis["performance_rating"] = "good"
        elif response_time < 3000:
            analysis["performance_rating"] = "fair"
        else:
            analysis["performance_rating"] = "poor"
            analysis["issues"].append("HTTP响应时间过长")
            analysis["recommendations"].append("优化服务器性能或检查网络连接")
        
        return analysis
    
    def _analyze_certificate(self, cert_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析SSL证书"""
        analysis = {
            "validity": "unknown",
            "days_until_expiry": cert_info.get("days_until_expiry", 0),
            "issuer": cert_info.get("issuer", {}),
            "subject": cert_info.get("subject", {}),
            "issues": [],
            "recommendations": []
        }
        
        # 证书有效期检查
        days_left = analysis["days_until_expiry"]
        if days_left < 0:
            analysis["validity"] = "expired"
            analysis["issues"].append("证书已过期")
            analysis["recommendations"].append("立即更新SSL证书")
        elif days_left < 30:
            analysis["validity"] = "expiring_soon"
            analysis["issues"].append(f"证书将在{days_left}天后过期")
            analysis["recommendations"].append("计划更新SSL证书")
        else:
            analysis["validity"] = "valid"
        
        return analysis
    
    def _generate_summary(self, detailed_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成分析摘要"""
        components = ["dns", "tcp", "tls", "http"]
        summary = {
            "total_components": len(components),
            "successful_components": 0,
            "failed_components": 0,
            "overall_health": "unknown",
            "critical_issues": [],
            "performance_bottlenecks": []
        }
        
        for component in components:
            comp_analysis = detailed_analysis.get(component, {})
            if comp_analysis.get("status") == "success":
                summary["successful_components"] += 1
            elif comp_analysis.get("status") == "failed":
                summary["failed_components"] += 1
                summary["critical_issues"].extend(comp_analysis.get("issues", []))
        
        # 整体健康评估
        success_rate = summary["successful_components"] / summary["total_components"]
        if success_rate >= 0.8:
            summary["overall_health"] = "good"
        elif success_rate >= 0.5:
            summary["overall_health"] = "fair"
        else:
            summary["overall_health"] = "poor"
        
        return summary
    
    def _generate_recommendations(self, detailed_analysis: Dict[str, Any]) -> List[str]:
        """生成综合建议"""
        recommendations = []
        
        for component, analysis in detailed_analysis.items():
            if analysis.get("recommendations"):
                recommendations.extend([
                    f"[{component.upper()}] {rec}" for rec in analysis["recommendations"]
                ])
        
        return list(set(recommendations))  # 去重
    
    def _generate_troubleshooting_guide(self, detailed_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成故障排除指南"""
        guide = {
            "immediate_actions": [],
            "diagnostic_commands": [],
            "escalation_steps": []
        }
        
        # 收集所有故障排除命令
        for component, analysis in detailed_analysis.items():
            if analysis.get("status") == "failed":
                error_analysis = analysis.get("error_analysis")
                if error_analysis:
                    guide["diagnostic_commands"].extend(
                        error_analysis.get("troubleshooting_commands", [])
                    )
        
        # 去重
        guide["diagnostic_commands"] = list(set(guide["diagnostic_commands"]))
        
        return guide
    
    def _analyze_performance(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """性能分析"""
        dns_info = result.get("dns_resolution") or {}
        tcp_info = result.get("tcp_connection") or {}
        tls_info = result.get("tls_info") or {}
        http_info = result.get("http_response") or {}

        return {
            "total_time_ms": result.get("total_time_ms", 0),
            "component_breakdown": {
                "dns_time_ms": dns_info.get("resolution_time_ms", 0),
                "tcp_time_ms": tcp_info.get("connect_time_ms", 0),
                "tls_time_ms": tls_info.get("handshake_time_ms", 0),
                "http_time_ms": http_info.get("response_time_ms", 0)
            }
        }
    
    def _assess_security(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """安全评估"""
        assessment = {
            "overall_security": "unknown",
            "tls_enabled": False,
            "certificate_valid": False,
            "security_issues": [],
            "security_recommendations": []
        }

        tls_info = result.get("tls_info") or {}
        if tls_info.get("is_secure"):
            assessment["tls_enabled"] = True
            assessment["overall_security"] = "good"

            cert_info = tls_info.get("certificate")
            if cert_info and cert_info.get("days_until_expiry", 0) > 0:
                assessment["certificate_valid"] = True
        else:
            assessment["security_issues"].append("TLS连接失败或未启用")
            assessment["security_recommendations"].append("确保启用HTTPS和有效的SSL证书")

        return assessment
    
    def _load_analysis_rules(self) -> Dict[str, Any]:
        """加载分析规则"""
        # 这里可以从配置文件加载规则
        return {
            "performance_thresholds": {
                "dns_excellent": 50,
                "dns_good": 200,
                "tcp_excellent": 10,
                "tcp_good": 50,
                "tls_excellent": 100,
                "tls_good": 500,
                "http_excellent": 200,
                "http_good": 1000
            }
        }
