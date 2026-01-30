# -*- coding: utf-8 -*-
"""
模拟引擎：
- 维护网络状态、统计信息、服务链与流量对象
- 提供请求创建、GA部署、PLSAFC分类与PSO资源检查的流程接口
- 供UI调用并回调更新
- 支持SIFA智能模式和传统网络模式的A/B对比测试
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import QCoreApplication, QTimer

import config as cfg
from sifa_simulator.core.data_structures import (
    CloudNode,
    NetworkLink,
    NetworkState,
    ServiceChain,
    TrafficFlow,
    UserRequest,
)
from sifa_simulator.algorithms.ga_deployer import run_ga
from sifa_simulator.algorithms import plsafc_classifier as pcls
from sifa_simulator.algorithms.pso_orchestrator import PSOOrchestrator


@dataclass
class Stats:
    total_requests: int = 0
    accepted: int = 0
    rejected: int = 0
    response_time_sum: float = 0.0
    rtp_sum: float = 0.0

    def reset(self):
        self.total_requests = 0
        self.accepted = 0
        self.rejected = 0
        self.response_time_sum = 0.0
        self.rtp_sum = 0.0


@dataclass
class EngineCallbacks:
    log: Callable[[str, Optional[str]], None]  # (text, color) color可为None
    update_topology: Callable[[], None]
    update_node_labels: Callable[[], None]
    highlight_path: Callable[[List[int], Tuple[int, int, int]], None]
    animate_flow: Callable[[List[int], Tuple[int, int, int]], None]
    add_classification_row: Callable[[TrafficFlow], None]
    update_kpis: Callable[[], None]
    update_predictions: Callable[[], None]
    blink_nodes: Callable[[List[int]], None]  # 新增：节点闪烁效果


class SimulationEngine:
    """核心模拟控制器。"""

    def __init__(self, callbacks: EngineCallbacks):
        if cfg.RANDOM_SEED is not None:
            random.seed(cfg.RANDOM_SEED)
        self.state = NetworkState()
        self.stats = Stats()
        self.callbacks = callbacks
        self._next_req_id = 1
        self._next_flow_id = 1
        self.active_chains: Dict[int, ServiceChain] = {}
        self.pending_requests: List[UserRequest] = []
        
        # 新增：模拟模式（SIFA智能模式 vs 传统网络模式）
        self.simulation_mode = cfg.SIMULATION_MODE
        
        # 新增：PSO编排器（懒加载）
        self._pso_orchestrator: Optional[PSOOrchestrator] = None
        
        # 新增：KPI历史记录（用于数据导出）
        self.kpi_history: List[Dict[str, float]] = []

    # --- 网络生成 ---
    def generate_network(self, node_count: int,
                         compute_range: Tuple[int, int],
                         timeslot_range: Tuple[int, int],
                         bw_range: Tuple[int, int]):
        self.state.clear()
        # 随机放置节点
        for i in range(1, node_count + 1):
            total_c = random.randint(*compute_range)
            total_t = random.randint(*timeslot_range)
            node = CloudNode(
                id=i,
                total_compute=total_c,
                used_compute=random.randint(0, max(0, total_c // 4)),
                total_timeslot=total_t,
                used_timeslot=random.randint(0, max(0, total_t // 4)),
                x=random.uniform(0, 100),
                y=random.uniform(0, 100),
            )
            self.state.add_node(node)
        # 全连接链路
        ids = list(self.state.nodes.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                bw = random.uniform(*bw_range)
                self.state.add_link(NetworkLink(src=ids[i], dst=ids[j], bandwidth=bw))
        self.callbacks.update_topology()
        self.callbacks.log("网络已生成。", None)

    # --- 请求创建 ---
    def create_request(self, app_key: str) -> Optional[UserRequest]:
        if app_key not in cfg.APP_TYPES:
            return None
        app = cfg.APP_TYPES[app_key]
        capability_needs = [(c.name, c.compute, c.timeslot) for c in app["capabilities"]]
        req = UserRequest(
            req_id=self._next_req_id,
            arrival_time=time.time(),
            expire_time=time.time() + 30.0,  # 简化：30秒过期
            capability_needs=capability_needs,
            flow_size_mb=float(app["flow_size_mb"]),
            app_type=str(app["app_type"]),
            true_class=str(app["true_class"]),
        )
        self._next_req_id += 1
        self.pending_requests.append(req)
        self.stats.total_requests += 1
        return req

    # --- 模式切换 ---
    def set_simulation_mode(self, mode: str):
        """设置模拟模式"""
        if mode in ["SIFA", "Traditional"]:
            self.simulation_mode = mode
            self.callbacks.log(f"✅ 模拟模式已切换至: {mode}", "green")
        else:
            self.callbacks.log(f"❌ 无效的模拟模式: {mode}", "red")
    
    def get_simulation_mode(self) -> str:
        """获取当前模拟模式"""
        return self.simulation_mode
    
    # --- 部署流程（GA -> 可视化 -> PLSAFC -> PSO）---
    def process_request(self, req: UserRequest):
        """处理用户请求（支持SIFA和Traditional两种模式）"""
        if self.simulation_mode == "SIFA":
            self._process_request_sifa(req)
        else:
            self._process_request_traditional(req)
    
    def _process_request_sifa(self, req: UserRequest):
        """SIFA智能模式的请求处理流程"""
        # 1) GA 计算最优路径
        path = run_ga(self.state, req)
        if not path:
            self.callbacks.log(f"❌ [SIFA] 请求[{req.req_id}]部署失败: 无可用资源/路径。", "red")
            self.stats.rejected += 1
            self.callbacks.update_kpis()
            return
        path_color = self.state.random_color()
        # 2) 可视化高亮
        self.callbacks.highlight_path(path, path_color)
        # 确保动画能够显示，即使后续资源编排失败
        self.callbacks.animate_flow(path, path_color)
        
        # 将复杂计算部分移到定时器中执行，给动画留出时间显示
        # 保存必要的参数到实例变量，以便在延迟函数中使用
        self._temp_req = req
        self._temp_path = path
        self._temp_path_color = path_color
        
        # 使用QTimer延迟执行后续复杂计算，让动画有足够时间显示
        QTimer.singleShot(1000, self._continue_sifa_processing)  # 延迟1秒执行
    
    # 在_continue_sifa_processing方法中，删除从"# 使用Qt的事件循环处理机制"开始到方法结束的重复代码
    # 正确的方法实现应该只保留第一次的分类和处理逻辑
    
    def _continue_sifa_processing(self):
        """继续执行SIFA模式的复杂计算部分"""
        # 添加临时变量存在性检查，避免方法被重复调用时出错
        if not hasattr(self, '_temp_req') or not hasattr(self, '_temp_path') or not hasattr(self, '_temp_path_color'):
            self.callbacks.log("⚠️ [SIFA] 跳过重复的处理请求，临时变量不存在", "orange")
            return
            
        req = self._temp_req
        path = self._temp_path
        path_color = self._temp_path_color
        
        # 3) PLSAFC 特征与分类
        flow = TrafficFlow(flow_id=self._next_flow_id, request_id=req.req_id, true_class=req.true_class, app_type=req.app_type)
        self._next_flow_id += 1
        flow.features = pcls.simulate_features(flow.true_class)
        pred, fec = pcls.classify(flow, use_probabilistic=True)  # 使用增强的概率模型
        self.callbacks.add_classification_row(flow)
        
        # 4) PSO 资源编排与预留（仅对"控制"类流量触发）
        success = True
        if pred == "控制":
            success = self._pso_reserve_advanced(req, path)
        else:
            # 非控制流量，简单检查资源
            success = self._simple_reserve(req, path)
        
        if success:
            # 记录服务链
            sc = ServiceChain(request_id=req.req_id, node_path=path, color=path_color)
            self.active_chains[req.req_id] = sc
            self.callbacks.log(
                f"✅ [SIFA] 请求{req.req_id}已部署，最优路径: " + "→".join([f"N{n}" for n in path]),
                "green",
            )
            # 响应时间（简化，以GA后时间差 + 传输时间）
            bw = self.state.path_bandwidth(path)
            t_resp = (time.time() - req.arrival_time) + (req.flow_size_mb * 8.0) / max(1e-6, bw)
            self.stats.response_time_sum += t_resp
            self.stats.accepted += 1
            # RTP模拟（按资源-时间乘积简化）
            rtp = sum(c + t for _, c, t in req.capability_needs)
            self.stats.rtp_sum += rtp
        else:
            self.callbacks.log(f"❌ [SIFA] 请求[{req.req_id}]部署失败: 无可用资源", "red")
            self.stats.rejected += 1
        
        # 更新
        self.pending_requests = [r for r in self.pending_requests if r.req_id != req.req_id]
        self.callbacks.update_node_labels()
        self.callbacks.update_kpis()
        
        # 清理临时变量
        del self._temp_req
        del self._temp_path
        del self._temp_path_color
    
    def _process_request_traditional(self, req: UserRequest):
        """传统网络模式的请求处理流程"""
        # 1) 固定路径：使用简单路径选择
        path = self._simple_path_selection(req)
        if not path:
            self.callbacks.log(f"❌ [传统] 请求[{req.req_id}]部署失败: 无可用路径", "orange")
            self.stats.rejected += 1
            self.callbacks.update_kpis()
            return
        
        path_color = self.state.random_color()
        # 2) 可视化高亮
        self.callbacks.highlight_path(path, path_color)
        self.callbacks.animate_flow(path, path_color)
        
        # 3) 无分类：所有流量视为"尽力而为"
        # 4) 无资源预留：抢占式资源分配
        success = self._best_effort_allocate(req, path)
        
        if success:
            sc = ServiceChain(request_id=req.req_id, node_path=path, color=path_color)
            self.active_chains[req.req_id] = sc
            self.callbacks.log(
                f"✅ [传统] 请求{req.req_id}已部署（尽力而为），路径: " + "→".join([f"N{n}" for n in path]),
                None,
            )
            bw = self.state.path_bandwidth(path)
            t_resp = (time.time() - req.arrival_time) + (req.flow_size_mb * 8.0) / max(1e-6, bw)
            self.stats.response_time_sum += t_resp
            self.stats.accepted += 1
            rtp = sum(c + t for _, c, t in req.capability_needs)
            self.stats.rtp_sum += rtp
        else:
            self.callbacks.log(f"❌ [传统] 请求[{req.req_id}]部署失败: 资源不足", "orange")
            self.stats.rejected += 1
        
        self.pending_requests = [r for r in self.pending_requests if r.req_id != req.req_id]
        self.callbacks.update_node_labels()
        self.callbacks.update_kpis()
    
    # --- 辅助方法：传统模式 ---
    def _simple_path_selection(self, req: UserRequest) -> Optional[List[int]]:
        """简单路径选择：随机选择有资源的节点（改进版）"""
        if not self.state.nodes:
            return None
        
        # 获取所有节点ID列表
        node_ids = list(self.state.nodes.keys())
        num_capabilities = len(req.capability_needs)
        
        if len(node_ids) < num_capabilities:
            return None
        
        # 选择有足够资源的节点（传统模式不严格保证资源，但至少尝试选择可用节点）
        available_nodes = []
        for nid in node_ids:
            node = self.state.nodes[nid]
            # 检查节点是否至少能满足一个能力需求
            can_serve = False
            for _, c_need, t_need in req.capability_needs:
                if node.available_compute() >= c_need and node.available_timeslot() >= t_need:
                    can_serve = True
                    break
            if can_serve:
                available_nodes.append(nid)
        
        # 如果没有可用节点，返回None
        if not available_nodes:
            return None
        
        # 随机选择节点作为路径（允许重复）
        path = []
        for _ in range(num_capabilities):
            if available_nodes:
                # 从可用节点中随机选择
                nid = random.choice(available_nodes)
                path.append(nid)
            else:
                # 如果可用节点耗尽，从所有节点中选择
                path.append(random.choice(node_ids))
        
        return path
    
    def _best_effort_allocate(self, req: UserRequest, path: List[int]) -> bool:
        """尽力而为的资源分配（不保证QoS）"""
        for idx, nid in enumerate(path):
            if idx >= len(req.capability_needs):
                break
            node = self.state.nodes.get(nid)
            if not node:
                return False
            _, c_need, t_need = req.capability_needs[idx]
            # 尽力分配，即使资源不足也尝试分配
            if node.available_compute() >= c_need and node.available_timeslot() >= t_need:
                node.used_compute += c_need
                node.used_timeslot += t_need
            else:
                # 传统模式：即使资源不足也尝试分配（降级服务）
                node.used_compute += min(c_need, node.available_compute())
                node.used_timeslot += min(t_need, node.available_timeslot())
        return True
    
    # --- 辅助方法：SIFA模式 ---
    def _pso_reserve_advanced(self, req: UserRequest, path: List[int]) -> bool:
        """使用PSO进行高级资源编排"""
        # 懒加载PSO编排器
        if self._pso_orchestrator is None:
            self._pso_orchestrator = PSOOrchestrator(self.state, verbose=False)
        
        self.callbacks.log(
            f"🔧 [PSO] 开始为请求[{req.req_id}]进行资源编排...",
            "#b794f6"
        )
        
        # 运行PSO算法
        allocation = self._pso_orchestrator.run_pso(path, req.capability_needs, req.req_id)
        
        if allocation:
            # 应用分配方案
            success = self._pso_orchestrator.apply_allocation(allocation, path)
            if success:
                path_str = "→".join([f"N{n}" for n in path])
                self.callbacks.log(
                    f"✅ [PSO] 流量[{req.req_id}]资源编排成功！路径: {path_str}",
                    "#00cc66"
                )
                # 触发节点闪烁效果，突出显示资源编排成功
                self.callbacks.blink_nodes(path)
                return True
        
        self.callbacks.log(
            f"❌ [PSO] 流量[{req.req_id}]资源编排失败",
            "red"
        )
        return False
    
    def _simple_reserve(self, req: UserRequest, path: List[int]) -> bool:
        """简单的资源预留（非控制流量）"""
        # 第一遍：检查所有节点资源是否充足
        for idx, nid in enumerate(path):
            if idx >= len(req.capability_needs):
                break
            node = self.state.nodes.get(nid)
            if not node:
                return False
            _, c_need, t_need = req.capability_needs[idx]
            if node.available_compute() < c_need or node.available_timeslot() < t_need:
                return False
        
        # 第二遍：分配资源
        for idx, nid in enumerate(path):
            if idx >= len(req.capability_needs):
                break
            node = self.state.nodes[nid]
            _, c_need, t_need = req.capability_needs[idx]
            node.used_compute += c_need
            node.used_timeslot += t_need
        
        return True

    # --- PSO: 资源预留检查（保留旧版本用于向后兼容） ---
    def _pso_reserve(self, req: UserRequest, path: List[int]) -> bool:
        """PSO资源预留检查并提供详细反馈（已弃用，使用_pso_reserve_advanced）"""
        return self._pso_reserve_advanced(req, path)

    # --- KPI与预测辅助 ---
    def overall_load(self) -> float:
        if not self.state.nodes:
            return 0.0
        util_sum = 0.0
        for node in self.state.nodes.values():
            util_c = node.used_compute / max(1, node.total_compute)
            util_t = node.used_timeslot / max(1, node.total_timeslot)
            util_sum += max(util_c, util_t)
        return util_sum / len(self.state.nodes)

    def active_chain_count(self) -> int:
        return len(self.active_chains)

    def kpi_values(self) -> Dict[str, float]:
        recv_rate = (self.stats.accepted / self.stats.total_requests * 100.0) if self.stats.total_requests else 0.0
        avg_resp = (self.stats.response_time_sum / max(1, self.stats.accepted)) if self.stats.accepted else 0.0
        avg_rtp = (self.stats.rtp_sum / max(1, self.stats.accepted)) if self.stats.accepted else 0.0
        overall_util = self.overall_load() * 100.0
        return {
            "receive_rate": recv_rate,
            "avg_response": avg_resp,
            "avg_rtp": avg_rtp,
            "overall_util": overall_util,
        }