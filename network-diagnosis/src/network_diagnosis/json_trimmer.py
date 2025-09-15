"""
JSON重复数据裁剪器 - 临时解决方案
用于移除网络诊断结果中的重复数据块
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def trim_json_file(input_path: str, output_path: Optional[str] = None) -> bool:
    """
    裁剪JSON文件中的重复数据
    
    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径，如果为None则覆盖输入文件
    
    Returns:
        bool: 是否成功裁剪
    """
    try:
        # 读取JSON文件
        with open(input_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # 裁剪重复数据
        trimmed_data = trim_json_data(json_data)
        
        # 确定输出路径
        if output_path is None:
            output_path = input_path
        
        # 写入裁剪后的数据
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(trimmed_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Successfully trimmed JSON file: {input_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to trim JSON file {input_path}: {e}")
        return False


def trim_json_string(json_str: str) -> str:
    """
    裁剪JSON字符串中的重复数据
    
    Args:
        json_str: 输入JSON字符串
    
    Returns:
        str: 裁剪后的JSON字符串
    """
    try:
        json_data = json.loads(json_str)
        trimmed_data = trim_json_data(json_data)
        return json.dumps(trimmed_data, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to trim JSON string: {e}")
        return json_str


def trim_json_data(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    裁剪JSON数据中的重复块
    
    Args:
        json_data: 输入JSON数据
    
    Returns:
        Dict: 裁剪后的JSON数据
    """
    # 创建数据副本，避免修改原数据
    trimmed_data = json_data.copy()
    
    # 检测并移除ICMP重复数据
    if _is_icmp_duplicate(json_data):
        if 'icmp_info' in trimmed_data:
            del trimmed_data['icmp_info']
            logger.debug("Removed duplicate icmp_info field")
    
    # 检测并移除MTR重复数据
    if _is_mtr_duplicate(json_data):
        if 'network_path' in trimmed_data:
            del trimmed_data['network_path']
            logger.debug("Removed duplicate network_path field")
    
    return trimmed_data


def _is_icmp_duplicate(json_data: Dict[str, Any]) -> bool:
    """
    检测ICMP数据是否重复
    
    Args:
        json_data: JSON数据
    
    Returns:
        bool: 是否存在重复
    """
    # 检查必要字段是否存在
    if not ('icmp_info' in json_data and json_data['icmp_info']):
        return False
    
    if not ('multi_ip_icmp' in json_data and json_data['multi_ip_icmp']):
        return False
    
    # 获取primary_ip
    primary_ip = json_data.get('target_ip')
    if not primary_ip:
        return False
    
    # 检查multi_ip结果中是否有primary_ip的数据
    multi_icmp = json_data['multi_ip_icmp']
    icmp_results = multi_icmp.get('icmp_results', {})
    
    if primary_ip not in icmp_results or not icmp_results[primary_ip]:
        return False
    
    # 比较关键字段
    traditional = json_data['icmp_info']
    multi_ip_data = icmp_results[primary_ip]
    
    # 定义需要比较的关键字段
    key_fields = [
        'packets_sent', 'packets_received', 'packet_loss_percent',
        'avg_rtt_ms', 'min_rtt_ms', 'max_rtt_ms', 'std_dev_rtt_ms'
    ]
    
    # 逐个比较字段
    for field in key_fields:
        traditional_value = traditional.get(field)
        multi_ip_value = multi_ip_data.get(field)
        
        # 如果字段值不同，则不是重复
        if traditional_value != multi_ip_value:
            return False
    
    logger.debug(f"ICMP duplication detected for IP {primary_ip}")
    return True


def _is_mtr_duplicate(json_data: Dict[str, Any]) -> bool:
    """
    检测MTR数据是否重复
    
    Args:
        json_data: JSON数据
    
    Returns:
        bool: 是否存在重复
    """
    # 检查必要字段是否存在
    if not ('network_path' in json_data and json_data['network_path']):
        return False
    
    if not ('multi_ip_network_path' in json_data and json_data['multi_ip_network_path']):
        return False
    
    # 获取primary_ip
    primary_ip = json_data.get('target_ip')
    if not primary_ip:
        return False
    
    # 检查multi_ip结果中是否有primary_ip的数据
    multi_path = json_data['multi_ip_network_path']
    path_results = multi_path.get('path_results', {})
    
    if primary_ip not in path_results or not path_results[primary_ip]:
        return False
    
    # 比较关键字段
    traditional = json_data['network_path']
    multi_ip_data = path_results[primary_ip]
    
    # 定义需要比较的关键字段
    key_fields = [
        'total_hops', 'avg_latency_ms', 'packet_loss_percent', 'trace_method'
    ]
    
    # 逐个比较字段
    for field in key_fields:
        traditional_value = traditional.get(field)
        multi_ip_value = multi_ip_data.get(field)
        
        # 如果字段值不同，则不是重复
        if traditional_value != multi_ip_value:
            return False
    
    # 额外检查hops数组的长度（不需要逐个比较，长度一致基本可以确认重复）
    traditional_hops = traditional.get('hops', [])
    multi_ip_hops = multi_ip_data.get('hops', [])
    
    if len(traditional_hops) != len(multi_ip_hops):
        return False
    
    logger.debug(f"MTR duplication detected for IP {primary_ip}")
    return True


# 命令行接口（可选）
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python json_trimmer.py <input_file> [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = trim_json_file(input_file, output_file)
    if success:
        print(f"Successfully trimmed {input_file}")
    else:
        print(f"Failed to trim {input_file}")
        sys.exit(1)
