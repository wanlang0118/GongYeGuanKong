# -*- coding: utf-8 -*-
"""
核心数据结构定义

包含：
- CloudNode: 云原生网络节点
- NetworkLink: 节点间链路
- UserRequest: 用户请求
- ServiceChain: 服务链（节点路径）
- TrafficFlow: 流量对象

所有类均为纯本地数据结构，方便模拟与UI更新。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import random


@dataclass
class CloudNode:
    """
    云原生网络节点
    
    支持软时分(STD)时间矩阵：
    - timeslot_matrix: 时间矩阵列表，0表示空闲，1表示占用
    - 这样可以更真实地模拟论文第5章中的时隙资源管理
    """
    id: int
    total_compute: int
    used_compute: int
    total_timeslot: int
    used_timeslot: int
    x: float
    y: float
    # 新增：软时分时间矩阵 (0=空闲, 1=占用)
    timeslot_matrix: List[int] = field(default_factory=list)

    def __post_init__(self):
        """初始化时间矩阵"""
        if not self.timeslot_matrix:
            # 创建时间矩阵，全部初始化为0（空闲）
            self.timeslot_matrix = [0] * self.total_timeslot
            # 根据初始已用时隙，随机标记一些为占用
            if self.used_timeslot > 0:
                occupied_indices = random.sample(
                    range(self.total_timeslot),
                    min(self.used_timeslot, self.total_timeslot)
                )
                for idx in occupied_indices:
                    self.timeslot_matrix[idx] = 1

    def available_compute(self) -> int:
        """可用计算资源"""
        return self.total_compute - self.used_compute

    def available_timeslot(self) -> int:
        """可用时隙资源（基于时间矩阵）"""
        if self.timeslot_matrix:
            return self.timeslot_matrix.count(0)  # 统计空闲时隙数量
        return self.total_timeslot - self.used_timeslot

    def find_continuous_timeslots(self, count: int) -> Optional[int]:
        """
        在时间矩阵中寻找连续的空闲时隙
        
        参数:
        - count: 需要的连续时隙数量
        
        返回:
        - 起始索引，如果找不到返回None
        """
        if not self.timeslot_matrix or count <= 0:
            return None
        
        continuous = 0
        start_idx = -1
        
        for i, slot in enumerate(self.timeslot_matrix):
            if slot == 0:  # 空闲
                if start_idx == -1:
                    start_idx = i
                continuous += 1
                
                if continuous >= count:
                    return start_idx
            else:  # 占用
                continuous = 0
                start_idx = -1
        
        return None

    def allocate_timeslots(self, start: int, count: int) -> bool:
        """
        分配时隙资源
        
        参数:
        - start: 起始索引
        - count: 数量
        
        返回:
        - 是否成功分配
        """
        if not self.timeslot_matrix:
            return False
        
        # 检查范围
        if start < 0 or start + count > len(self.timeslot_matrix):
            return False
        
        # 检查是否全部空闲
        for i in range(start, start + count):
            if self.timeslot_matrix[i] != 0:
                return False
        
        # 分配
        for i in range(start, start + count):
            self.timeslot_matrix[i] = 1
        
        # 更新已用计数
        self.used_timeslot = sum(self.timeslot_matrix)
        return True

    def utilization_color(self) -> str:
        """根据资源利用率返回颜色字符串（green/yellow/red）。"""
        util_c = self.used_compute / max(1, self.total_compute)
        util_t = self.used_timeslot / max(1, self.total_timeslot)
        util = max(util_c, util_t)
        if util >= 0.95:
            return 'red'
        if util >= 0.80:
            return 'yellow'
        return 'green'

    def label_text(self) -> str:
        return f"Node {self.id}\nC: {self.used_compute}/{self.total_compute}\nT: {self.used_timeslot}/{self.total_timeslot}"


@dataclass
class NetworkLink:
    src: int
    dst: int
    bandwidth: float  # Mbps


@dataclass
class UserRequest:
    req_id: int
    arrival_time: float
    expire_time: float
    capability_needs: List[Tuple[str, int, int]]  # (name, compute, timeslot)
    flow_size_mb: float
    app_type: str
    true_class: str  # 控制/非控制


@dataclass
class ServiceChain:
    request_id: int
    node_path: List[int]
    color: Tuple[int, int, int] = (0, 150, 255)


@dataclass
class TrafficFlow:
    flow_id: int
    request_id: int
    features: Dict[str, float] = field(default_factory=dict)
    true_class: str = "非控制"
    app_type: str = ""
    predicted_class: Optional[str] = None
    fec_value: Optional[float] = None


@dataclass
class NetworkState:
    nodes: Dict[int, CloudNode] = field(default_factory=dict)
    links: List[NetworkLink] = field(default_factory=list)
    adjacency: Dict[int, Dict[int, NetworkLink]] = field(default_factory=dict)  # src->dst->link

    def clear(self):
        self.nodes.clear()
        self.links.clear()
        self.adjacency.clear()

    def add_node(self, node: CloudNode):
        self.nodes[node.id] = node
        self.adjacency.setdefault(node.id, {})

    def add_link(self, link: NetworkLink):
        self.links.append(link)
        self.adjacency.setdefault(link.src, {})[link.dst] = link
        self.adjacency.setdefault(link.dst, {})[link.src] = link  # 无向

    def path_bandwidth(self, path: List[int]) -> float:
        if len(path) < 2:
            return float('inf')
        # 路径瓶颈带宽（最小带宽）
        bws = []
        for a, b in zip(path[:-1], path[1:]):
            link = self.adjacency.get(a, {}).get(b)
            if not link:
                return 0.0
            bws.append(link.bandwidth)
        return min(bws) if bws else 0.0

    def random_color(self) -> Tuple[int, int, int]:
        return tuple(random.randint(50, 200) for _ in range(3))  # 柔和一些
