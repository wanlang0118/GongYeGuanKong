# -*- coding: utf-8 -*-
"""
数据导入导出处理器

功能：
- 导出KPI时间序列数据为CSV
- 保存/加载网络拓扑场景为JSON
- 导出分类结果为CSV
"""
from __future__ import annotations

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from sifa_simulator.core.data_structures import CloudNode, NetworkLink, NetworkState


class IOHandler:
    """数据输入输出处理器"""
    
    @staticmethod
    def export_kpi_to_csv(kpi_history: List[Dict[str, float]], 
                         filepath: str) -> bool:
        """
        导出KPI历史数据到CSV文件
        
        参数:
        - kpi_history: KPI历史数据列表
        - filepath: 导出文件路径
        
        返回:
        - 是否成功
        """
        try:
            if not kpi_history:
                return False
            
            # 确保目录存在
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # 获取所有字段
            fieldnames = ['timestamp'] + list(kpi_history[0].keys())
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for idx, kpi in enumerate(kpi_history):
                    row = {'timestamp': idx}
                    row.update(kpi)
                    writer.writerow(row)
            
            return True
        except Exception as e:
            print(f"导出KPI数据失败: {e}")
            return False
    
    @staticmethod
    def export_classification_to_csv(classification_data: List[Dict[str, Any]],
                                    filepath: str) -> bool:
        """
        导出流量分类结果到CSV文件
        
        参数:
        - classification_data: 分类数据列表
        - filepath: 导出文件路径
        
        返回:
        - 是否成功
        """
        try:
            if not classification_data:
                return False
            
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            fieldnames = ['flow_id', 'app_type', 'true_class', 'predicted_class', 'fec_value']
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(classification_data)
            
            return True
        except Exception as e:
            print(f"导出分类数据失败: {e}")
            return False
    
    @staticmethod
    def save_network_scene(network_state: NetworkState, 
                          filepath: str,
                          metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存网络场景到JSON文件
        
        参数:
        - network_state: 网络状态对象
        - filepath: 保存文件路径
        - metadata: 元数据（可选）
        
        返回:
        - 是否成功
        """
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # 构建场景数据
            scene_data = {
                'metadata': metadata or {
                    'created_at': datetime.now().isoformat(),
                    'version': '1.0'
                },
                'nodes': [],
                'links': []
            }
            
            # 序列化节点
            for node in network_state.nodes.values():
                node_data = {
                    'id': node.id,
                    'total_compute': node.total_compute,
                    'used_compute': node.used_compute,
                    'total_timeslot': node.total_timeslot,
                    'used_timeslot': node.used_timeslot,
                    'x': node.x,
                    'y': node.y,
                    'timeslot_matrix': node.timeslot_matrix if hasattr(node, 'timeslot_matrix') else []
                }
                scene_data['nodes'].append(node_data)
            
            # 序列化链路
            for link in network_state.links:
                link_data = {
                    'src': link.src,
                    'dst': link.dst,
                    'bandwidth': link.bandwidth
                }
                scene_data['links'].append(link_data)
            
            # 写入JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(scene_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"保存网络场景失败: {e}")
            return False
    
    @staticmethod
    def load_network_scene(filepath: str) -> Optional[Dict[str, Any]]:
        """
        从JSON文件加载网络场景
        
        参数:
        - filepath: 文件路径
        
        返回:
        - 场景数据字典或None
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                scene_data = json.load(f)
            
            return scene_data
        except Exception as e:
            print(f"加载网络场景失败: {e}")
            return None
    
    @staticmethod
    def restore_network_state(scene_data: Dict[str, Any]) -> Optional[NetworkState]:
        """
        从场景数据恢复网络状态
        
        参数:
        - scene_data: 场景数据字典
        
        返回:
        - NetworkState对象或None
        """
        try:
            state = NetworkState()
            
            # 恢复节点
            for node_data in scene_data.get('nodes', []):
                node = CloudNode(
                    id=node_data['id'],
                    total_compute=node_data['total_compute'],
                    used_compute=node_data['used_compute'],
                    total_timeslot=node_data['total_timeslot'],
                    used_timeslot=node_data['used_timeslot'],
                    x=node_data['x'],
                    y=node_data['y'],
                    timeslot_matrix=node_data.get('timeslot_matrix', [])
                )
                state.add_node(node)
            
            # 恢复链路
            for link_data in scene_data.get('links', []):
                link = NetworkLink(
                    src=link_data['src'],
                    dst=link_data['dst'],
                    bandwidth=link_data['bandwidth']
                )
                state.add_link(link)
            
            return state
        except Exception as e:
            print(f"恢复网络状态失败: {e}")
            return None
    
    @staticmethod
    def export_statistics_report(stats: Dict[str, Any],
                                filepath: str) -> bool:
        """
        导出统计报告到文本文件
        
        参数:
        - stats: 统计数据字典
        - filepath: 导出文件路径
        
        返回:
        - 是否成功
        """
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("SIFA 仿真统计报告\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for key, value in stats.items():
                    f.write(f"{key}: {value}\n")
                
                f.write("\n" + "=" * 60 + "\n")
            
            return True
        except Exception as e:
            print(f"导出统计报告失败: {e}")
            return False


# --- 导出函数包装器（用于向后兼容） ---

def export_kpi_csv(filepath: str, kpi_data: List[Dict[str, float]]) -> bool:
    """
    导出KPI数据到CSV文件（包装器函数）
    
    参数:
    - filepath: 导出文件路径
    - kpi_data: KPI数据列表
    
    返回:
    - 是否成功
    """
    return IOHandler.export_kpi_to_csv(kpi_data, filepath)


def export_classification_csv(filepath: str, classification_data: List[Dict[str, Any]]) -> bool:
    """
    导出分类结果到CSV文件（包装器函数）
    
    参数:
    - filepath: 导出文件路径
    - classification_data: 分类数据列表
    
    返回:
    - 是否成功
    """
    return IOHandler.export_classification_to_csv(classification_data, filepath)


def export_report_txt(filepath: str, kpi_data: Dict[str, float], stats_data: Dict[str, Any]) -> bool:
    """
    导出统计报告到文本文件（包装器函数）
    
    参数:
    - filepath: 导出文件路径
    - kpi_data: KPI数据字典
    - stats_data: 统计数据字典
    
    返回:
    - 是否成功
    """
    # 合并KPI和统计数据
    combined_stats = {}
    combined_stats.update(kpi_data)
    combined_stats.update(stats_data)
    return IOHandler.export_statistics_report(combined_stats, filepath)


def save_scene(filepath: str, network_state: NetworkState) -> bool:
    """
    保存网络场景到JSON文件（包装器函数）
    
    参数:
    - filepath: 保存文件路径
    - network_state: 网络状态对象
    
    返回:
    - 是否成功
    """
    return IOHandler.save_network_scene(network_state, filepath)


def load_scene(filepath: str) -> Optional[NetworkState]:
    """
    从JSON文件加载网络场景（包装器函数）
    
    参数:
    - filepath: 文件路径
    
    返回:
    - NetworkState对象或None
    """
    scene_data = IOHandler.load_network_scene(filepath)
    if scene_data:
        return IOHandler.restore_network_state(scene_data)
    return None
