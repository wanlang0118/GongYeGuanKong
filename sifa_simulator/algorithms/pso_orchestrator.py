# -*- coding: utf-8 -*-
"""
PSO (Particle Swarm Optimization) 资源动态编排算法（优化版）
实现论文第5章的RDOTDR (Resource Dynamic Orchestration for Time-Deterministic Requirements)

核心思想：
- 对于时间确定性流量（控制类），需同时平衡计算、链路、时隙三种资源
- 使用粒子群优化寻找最佳时隙预留方案
- 目标：最小化最晚完成时间（即尽早完成任务）

优化点：
- 简化粒子表示：直接使用时隙起始位置而非比例编码
- 简化适应度函数：直接使用最晚完成时间作为成本
- 提升性能：减少不必要的编码/解码开销
"""
from __future__ import annotations

import random
import numpy as np
from typing import List, Dict, Optional, Tuple

import config as cfg


class Particle:
    """粒子：表示一个完整的资源预留方案（优化版）"""
    
    def __init__(self, path_length: int, max_slots: int):
        """
        初始化粒子
        :param path_length: 路径长度（节点数）
        :param max_slots: 最大时隙数
        """
        # 位置：每个节点的时隙起始位置（直接表示，无需编码）
        # 例如 position = [5, 8, 12] 表示在第0个节点从slot 5开始，第1个节点从slot 8开始...
        self.position = np.random.randint(0, max_slots, path_length, dtype=np.float64)
        
        # 速度：位置的变化量
        self.velocity = np.random.rand(path_length) - 0.5  # [-0.5, 0.5]
        
        # 个体历史最佳
        self.pBest_position = np.copy(self.position)
        self.pBest_fitness = float('inf')  # 成本（最晚完成时间），越小越好


class PSOOrchestrator:
    """PSO资源编排器（优化版）"""
    
    def __init__(self, network_state, verbose: bool = False):
        """
        参数:
        - network_state: NetworkState 网络状态对象
        - verbose: 是否输出详细日志
        """
        self.state = network_state
        self.verbose = verbose
        
        # PSO超参数（从配置文件读取）
        self.w = cfg.PSO_INERTIA_WEIGHT    # 惯性权重
        self.c1 = cfg.PSO_COGNITIVE_COEFF  # 个体学习因子
        self.c2 = cfg.PSO_SOCIAL_COEFF     # 群体学习因子
        # 使用时隙资源范围的上限作为最大时隙数
        self.max_slots = cfg.TIMESLOT_RESOURCE_RANGE[1]
        
        # 全局最佳
        self.global_best_position: Optional[np.ndarray] = None
        self.global_best_fitness: float = float('inf')  # 成本，越小越好
    
    def run_pso(self, 
                path: List[int],
                capability_needs: List[Tuple[str, int, int]],
                req_id: int) -> Optional[Dict[int, Dict[str, any]]]:
        """
        运行PSO算法寻找最优资源预留方案（优化版）
        
        参数:
        - path: 服务链路径（节点ID列表）
        - capability_needs: 每个节点的资源需求 [(name, compute, timeslot), ...]
        - req_id: 请求ID
        
        返回:
        - 资源分配方案字典: {node_id: {'compute': int, 'timeslot_start': int, 'timeslot_count': int}}
        - None 表示无法找到可行方案
        """
        if not path or not capability_needs:
            return None
        
        path_length = len(path)
        
        # 1. 初始化粒子群
        swarm = [Particle(path_length, self.max_slots) for _ in range(cfg.PSO_SWARM_SIZE)]
        
        # 重置全局最佳
        self.global_best_position = None
        self.global_best_fitness = float('inf')
        
        # 2. 开始迭代
        for iteration in range(cfg.PSO_MAX_ITERATIONS):
            # 评估所有粒子的适应度（成本）
            for particle in swarm:
                fitness = self._calculate_fitness(particle.position, path, capability_needs)
                
                # 更新个体历史最佳 (pBest)
                if fitness < particle.pBest_fitness:
                    particle.pBest_fitness = fitness
                    particle.pBest_position = np.copy(particle.position)
                
                # 更新全局历史最佳 (gBest)
                if fitness < self.global_best_fitness:
                    self.global_best_fitness = fitness
                    self.global_best_position = np.copy(particle.position)
            
            # 更新所有粒子的速度和位置
            for particle in swarm:
                self._update_velocity_position(particle, capability_needs)
            
            # 可选：早停策略（找到足够好的解）
            if self.global_best_fitness < float('inf') and iteration > cfg.PSO_MAX_ITERATIONS // 2:
                if self.verbose:
                    print(f"PSO在第{iteration}轮找到可行解，成本={self.global_best_fitness:.2f}")
                break
        
        # 3. 检查是否找到有效解
        if self.global_best_fitness == float('inf'):
            if self.verbose:
                print(f"❌ PSO未找到可行方案（请求{req_id}）")
            return None
        
        # 4. 构建预留方案
        allocation = self._build_reservation_plan(self.global_best_position, path, capability_needs)
        
        if self.verbose:
            print(f"✅ PSO找到可行方案（请求{req_id}），成本={self.global_best_fitness:.2f}")
        
        return allocation
    
    def _calculate_fitness(self, 
                           position: np.ndarray,
                           path: List[int],
                           capability_needs: List[Tuple[str, int, int]]) -> float:
        """
        计算适应度（成本函数）- 优化版
        
        成本 = 最晚完成时间（越小越好）
        如果方案无效（资源不足或时隙冲突），返回无穷大
        
        参数:
        - position: 粒子位置（每个节点的时隙起始位置）
        - path: 服务链路径
        - capability_needs: 资源需求列表
        
        返回:
        - 成本值（float），越小越好
        """
        is_valid = True
        latest_finish_time = 0  # 最晚完成时间
        
        for idx, node_id in enumerate(path):
            if idx >= len(capability_needs):
                break
            
            node = self.state.nodes.get(node_id)
            if not node:
                return float('inf')
            
            _, compute_need, timeslot_need = capability_needs[idx]
            
            # 获取时隙起始位置（取整）
            slot_start = int(round(position[idx]))
            slot_end = slot_start + timeslot_need
            
            # 1. 检查时隙是否越界
            if slot_start < 0 or slot_end > self.max_slots:
                is_valid = False
                break
            
            # 2. 检查计算资源是否充足
            if node.available_compute() < compute_need:
                is_valid = False
                break
            
            # 3. 检查时隙是否被占用（核心检查）
            if hasattr(node, 'timeslot_matrix') and node.timeslot_matrix:
                # 使用时间矩阵模式
                try:
                    # 检查 [slot_start, slot_end) 区间是否有被占用的时隙
                    if slot_end > len(node.timeslot_matrix):
                        is_valid = False
                        break
                    if any(node.timeslot_matrix[j] != 0 for j in range(slot_start, slot_end)):
                        is_valid = False
                        break
                except (IndexError, ValueError):
                    is_valid = False
                    break
            else:
                # 简单模式：只检查总量
                if node.available_timeslot() < timeslot_need:
                    is_valid = False
                    break
            
            # 更新最晚完成时间
            latest_finish_time = max(latest_finish_time, slot_end)
        
        # 返回成本
        if not is_valid:
            return float('inf')  # 无效方案
        else:
            return float(latest_finish_time)  # 有效方案，成本=最晚完成时间
    
    def _update_velocity_position(self, particle: Particle, capability_needs: List[Tuple[str, int, int]]):
        """
        更新粒子的速度和位置（PSO标准更新公式）- 优化版
        
        v = w*v + c1*r1*(pBest - x) + c2*r2*(gBest - x)
        x = x + v
        """
        if self.global_best_position is None:
            return
        
        r1 = random.random()
        r2 = random.random()
        
        # 向量化速度更新
        new_velocity = (self.w * particle.velocity +
                       self.c1 * r1 * (particle.pBest_position - particle.position) +
                       self.c2 * r2 * (self.global_best_position - particle.position))
        
        # 限制速度范围
        max_velocity = cfg.PSO_MAX_VELOCITY * self.max_slots  # 速度需要乘以时隙范围
        new_velocity = np.clip(new_velocity, -max_velocity, max_velocity)
        
        # 位置更新
        new_position = particle.position + new_velocity
        
        # 边界处理：时隙起始位置不能为负，也不能太大
        # 保证 slot_start + slot_count <= max_slots
        max_timeslot_need = max([needs[2] for needs in capability_needs]) if capability_needs else 10
        max_start = self.max_slots - max_timeslot_need
        new_position = np.clip(new_position, 0, max_start)
        
        particle.velocity = new_velocity
        particle.position = new_position
    
    def _build_reservation_plan(self,
                                position: np.ndarray,
                                path: List[int],
                                capability_needs: List[Tuple[str, int, int]]) -> Dict[int, Dict[str, any]]:
        """
        将最优粒子位置转换为可读的预留方案字典（优化版）
        
        参数:
        - position: 最优粒子位置（每个节点的时隙起始位置）
        - path: 服务链路径
        - capability_needs: 资源需求列表
        
        返回:
        - 预留方案字典
        """
        allocation = {}
        
        for idx, node_id in enumerate(path):
            if idx >= len(capability_needs):
                break
            
            _, compute_need, timeslot_need = capability_needs[idx]
            slot_start = int(round(position[idx]))
            
            allocation[node_id] = {
                'compute': compute_need,
                'timeslot_start': slot_start,
                'timeslot_count': timeslot_need,
            }
        
        return allocation
    
    def apply_allocation(self, 
                        allocation: Dict[int, Dict[str, any]],
                        path: List[int]) -> bool:
        """
        应用资源分配方案，实际预留资源
        
        返回: 是否成功应用
        """
        # 先检查是否所有资源都可用
        for node_id, alloc in allocation.items():
            node = self.state.nodes.get(node_id)
            if not node:
                return False
            
            compute_alloc = alloc['compute']
            timeslot_start = alloc['timeslot_start']
            timeslot_count = alloc['timeslot_count']
            
            # 检查计算资源
            if node.available_compute() < compute_alloc:
                return False
            
            # 检查时隙资源
            if hasattr(node, 'timeslot_matrix') and node.timeslot_matrix:
                # 使用时间矩阵模式
                for i in range(timeslot_start, timeslot_start + timeslot_count):
                    if i >= len(node.timeslot_matrix) or node.timeslot_matrix[i] != 0:
                        return False
            else:
                # 简单模式
                if node.available_timeslot() < timeslot_count:
                    return False
        
        # 应用资源分配
        for node_id, alloc in allocation.items():
            node = self.state.nodes.get(node_id)
            if not node:
                continue
            
            # 分配计算资源
            node.used_compute += alloc['compute']
            
            # 分配时隙资源
            if hasattr(node, 'timeslot_matrix') and node.timeslot_matrix:
                # 标记时隙为占用
                for i in range(alloc['timeslot_start'], alloc['timeslot_start'] + alloc['timeslot_count']):
                    if i < len(node.timeslot_matrix):
                        node.timeslot_matrix[i] = 1
                # 更新已用时隙数量
                node.used_timeslot = sum(node.timeslot_matrix)
            else:
                # 简单模式
                node.used_timeslot += alloc['timeslot_count']
        
        return True


def run_pso_orchestration(network_state, 
                         path: List[int],
                         capability_needs: List[Tuple[str, int, int]],
                         req_id: int,
                         verbose: bool = False) -> Optional[Dict[int, Dict[str, any]]]:
    """
    便捷函数：运行PSO资源编排（优化版）
    
    返回资源分配方案或None
    """
    orchestrator = PSOOrchestrator(network_state, verbose=verbose)
    allocation = orchestrator.run_pso(path, capability_needs, req_id)
    
    if allocation:
        # 应用分配方案
        success = orchestrator.apply_allocation(allocation, path)
        if success:
            return allocation
    
    return None
