# -*- coding: utf-8 -*-
"""
SIFA-GA 部署算法的简化模拟实现。

- 染色体：长度等于能力数量的节点ID列表，允许重复（可配置），这里约束为不连续重复。
- 适应度函数：Fitness = γ * S_ru - (1 - γ) * T_Response
  其中：
    T_Response = 排队时延(当前时间 - 到达时间) + 传输时延(流量大小 / 路径瓶颈带宽)
    S_ru: 模拟资源均衡度，根据部署后节点剩余资源的均匀性给予得分 [0,1]

此实现旨在教学演示用途，非生产级优化器。
"""

# 导入必要的模块
from __future__ import annotations  # 使用注解类型
import random  # 用于生成随机数
import time  # 用于获取当前时间
from typing import List, Tuple, Optional  # 类型提示支持
import logging  # 用于日志记录

# 导入项目中的核心数据结构
from sifa_simulator.core.data_structures import NetworkState, UserRequest
# 导入配置文件
import config as cfg

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _check_node_resources(state: NetworkState, node_id: int, c_need: float, t_need: float) -> bool:
    """
    检查节点是否有足够的可用资源
    :param state: 网络状态对象
    :param node_id: 节点ID
    :param c_need: 所需计算资源
    :param t_need: 所需时间槽资源
    :return: 如果节点有足够资源则返回True，否则返回False
    """
    node = state.nodes.get(node_id)
    if not node:
        return False

    # 检查计算资源是否足够
    if node.used_compute + c_need > node.total_compute:
        return False

    # 检查时间槽资源是否足够
    if node.used_timeslot + t_need > node.total_timeslot:
        return False

    return True


def _get_available_nodes(state: NetworkState, req: UserRequest) -> List[int]:
    """
    获取所有能够满足至少一个能力需求的节点
    :param state: 网络状态对象
    :param req: 用户请求对象
    :return: 可用节点ID列表
    """
    available_nodes = set()

    # 检查每个节点是否能满足至少一个能力需求
    for node_id in state.nodes.keys():
        for _, c_need, t_need in req.capability_needs:
            if _check_node_resources(state, node_id, c_need, t_need):
                available_nodes.add(node_id)
                break

    return list(available_nodes)


def _check_resource_availability(state: NetworkState, req: UserRequest) -> bool:
    """
    检查网络资源可用性，当只剩下两个节点有可用资源时发出警告
    :param state: 网络状态对象
    :param req: 用户请求对象
    :return: 如果可以继续发送请求则返回True，否则返回False
    """
    # 获取所有可用节点
    available_nodes = _get_available_nodes(state, req)

    # 如果可用节点数量少于等于2，发出警告并返回False
    if len(available_nodes) <= 2:
        logger.warning(f"系统资源不足：仅剩{len(available_nodes)}个节点有可用资源，无法再发送请求。")
        print(f"警告：系统资源不足，仅剩{len(available_nodes)}个节点有可用资源，请等待资源释放后再尝试发送请求。")
        return False

    # 资源充足，可以继续处理请求
    return True


def _init_population(state: NetworkState, req: UserRequest, pop_size: int) -> List[List[int]]:
    """
    初始化种群：生成初始的染色体集合（优化版）
    优先生成无重复节点的路径，当节点数不足时才允许重复
    :param state: 网络状态对象
    :param req: 用户请求对象
    :param pop_size: 种群大小
    :return: 初始种群（染色体列表）
    """
    node_ids = list(state.nodes.keys())  # 获取所有节点ID列表
    L = len(req.capability_needs)  # 获取所需能力的数量，即染色体长度
    pop = []  # 存储生成的染色体

    # 判断是否有足够节点生成无重复路径
    can_generate_unique = len(node_ids) >= L

    attempts = 0  # 尝试次数计数器
    max_attempts = pop_size * 20

    # 获取网络中节点总数
    total_nodes = len(node_ids)

    # 循环直到生成足够的不重复染色体或达到最大尝试次数
    while len(pop) < pop_size and attempts < max_attempts:
        attempts += 1  # 增加尝试次数
        chromo = []  # 当前染色体
        used_nodes = set()  # 记录已使用的节点
        valid = True  # 标记当前染色体是否有效

        # 为每个能力需求选择一个节点
        for i in range(L):
            # 获取当前位置需要的资源
            _, c_need, t_need = req.capability_needs[i]  # 获取该位置的能力需求

            # 基本限制：不能与前一个节点相同，并且节点必须有足够资源
            available_nodes = []
            for n in node_ids:
                # 检查节点是否满足基本条件（不与前一个相同且有足够资源）
                if (i == 0 or n != chromo[-1]) and _check_node_resources(state, n, c_need, t_need):
                    available_nodes.append(n)

            # 如果没有可用节点，当前染色体无效
            if not available_nodes:
                valid = False
                break

            # 优先使用未使用过的节点
            unused_nodes = [n for n in available_nodes if n not in used_nodes]

            # 策略：
            # 1. 如果还有未使用的节点，优先选择它们（概率提高到90%）
            # 2. 只有在必要时才重复使用已用节点
            if unused_nodes and random.random() < 0.9:
                nid = random.choice(unused_nodes)
            else:
                # 如果没有未使用节点或随机选择重复使用
                nid = random.choice(available_nodes)

            chromo.append(nid)  # 添加到染色体中
            used_nodes.add(nid)  # 记录已使用的节点

        # 确保染色体唯一性（避免完全相同的部署方案）并且有效
        if valid and chromo not in pop:
            pop.append(chromo)  # 加入种群

    # 如果没有生成任何有效染色体，则尝试生成一个简单的染色体
    if not pop:
        # 尝试生成一个简单的染色体，只选择有足够资源的节点
        simple_chromo = []
        for i in range(L):
            _, c_need, t_need = req.capability_needs[i]
            # 找到第一个有足够资源的节点
            for nid in node_ids:
                if (i == 0 or nid != simple_chromo[-1]) and _check_node_resources(state, nid, c_need, t_need):
                    simple_chromo.append(nid)
                    break
            else:
                # 如果找不到合适的节点，使用任意节点
                if node_ids:
                    simple_chromo.append(random.choice(node_ids))
        if simple_chromo:
            pop.append(simple_chromo)

    return pop  # 返回初始化的种群


def _path_bandwidth(state: NetworkState, path: List[int]) -> float:
    """
    计算路径带宽：压缩连续重复节点后的路径带宽
    :param state: 网络状态对象
    :param path: 节点路径列表
    :return: 路径带宽值
    """
    # 压缩连续重复节点
    reduced = []
    for n in path:
        # 如果是第一个节点或者与上一个节点不同，则添加
        if not reduced or reduced[-1] != n:
            reduced.append(n)

    # 如果路径少于两个节点，则认为带宽无限大
    if len(reduced) < 2:
        return float('inf')

    # 调用NetworkState的path_bandwidth方法计算带宽
    return state.path_bandwidth(reduced)


def _transmission_delay(flow_size_mb: float, bw_mbps: float) -> float:
    """
    计算传输时延：数据传输所需的时间
    :param flow_size_mb: 流量大小（MB）
    :param bw_mbps: 带宽（Mbps）
    :return: 传输时延（秒）
    """
    # 如果带宽小于等于0，则时延为无穷大
    if bw_mbps <= 0:
        return float('inf')

    # 转换MB到Mb（1字节=8位）
    flow_size_mbit = flow_size_mb * 8.0
    # 计算传输时延：大小/带宽
    return flow_size_mbit / bw_mbps


def _resource_score(state: NetworkState, req: UserRequest, chromo: List[int]) -> float:
    """
    计算资源评分：衡量部署后资源利用的均衡程度（优化版）
    考虑路径上节点的总空闲资源和最小空闲资源（均衡性）
    :param state: 网络状态对象
    :param req: 用户请求对象
    :param chromo: 染色体（部署方案）
    :return: 资源均衡度得分 [0,1]
    """
    if not chromo:
        return 0.0

    # 初始化每个节点的已使用资源
    used_c = {nid: state.nodes[nid].used_compute for nid in state.nodes}  # 计算资源
    used_t = {nid: state.nodes[nid].used_timeslot for nid in state.nodes}  # 时间槽资源

    # 根据染色体模拟部署，更新各节点资源使用情况
    for (idx, gene) in enumerate(chromo):
        _, c_need, t_need = req.capability_needs[idx]  # 获取该位置的能力需求
        used_c[gene] += c_need  # 更新计算资源使用
        used_t[gene] += t_need  # 更新时间槽资源使用

    # 统计路径上节点的空闲资源
    total_free_resource = 0.0
    min_free_resource = float('inf')

    # 遍历路径上的节点（去重）
    for nid in set(chromo):
        node = state.nodes[nid]
        # 计算空闲资源（归一化到[0,1]）
        free_c = max(0.0, (node.total_compute - used_c[nid]) / max(1, node.total_compute))
        free_t = max(0.0, (node.total_timeslot - used_t[nid]) / max(1, node.total_timeslot))

        # 取两种资源的最小值（短板效应）
        free_resource = min(free_c, free_t)

        # 检查资源是否过载（硬约束）
        if free_resource < 0:
            return 0.0  # 资源不足，返回最低分

        total_free_resource += free_resource
        min_free_resource = min(min_free_resource, free_resource)

    # 综合评分：总空闲资源 + 最小空闲资源（强调均衡性）
    # 归一化到[0,1]范围
    unique_nodes = len(set(chromo))
    if unique_nodes == 0:
        return 0.0

    avg_free = total_free_resource / unique_nodes
    # 评分公式：平均空闲资源 * 0.6 + 最小空闲资源 * 0.4
    # 这样既考虑总量，又强调均衡性
    score = 0.6 * avg_free + 0.4 * min_free_resource

    return max(0.0, min(1.0, score))


def _fitness(state: NetworkState, req: UserRequest, chromo: List[int], now_time: float) -> float:
    """
    计算适应度：衡量染色体质量的指标
    :param state: 网络状态对象
    :param req: 用户请求对象
    :param chromo: 染色体（部署方案）
    :param now_time: 当前时间戳
    :return: 适应度值
    """
    # 首先检查染色体是否有效（所有节点都有足够资源）
    for i, gene in enumerate(chromo):
        _, c_need, t_need = req.capability_needs[i]
        if not _check_node_resources(state, gene, c_need, t_need):
            # 如果有节点资源不足，给予严重惩罚
            return float('-inf')

    # 检查是否所有节点都相同（无效路径），添加惩罚
    if len(set(chromo)) == 1:
        # 对全重复节点路径给予严重惩罚，使其适应度极低
        return float('-inf')
    
    # 获取路径带宽
    bw = _path_bandwidth(state, chromo)
    # 计算排队时延（当前时间 - 请求到达时间）
    t_queue = max(0.0, now_time - req.arrival_time)
    # 计算传输时延
    t_trans = _transmission_delay(req.flow_size_mb, bw)
    # 总响应时间 = 排队时延 + 传输时延
    t_resp = t_queue + t_trans
    # 获取资源评分
    s_ru = _resource_score(state, req, chromo)
    # 获取适应度权重γ
    gamma = cfg.GAMMA_FITNESS

    # 大幅增强节点多样性奖励，使其成为适应度计算的主导因素
    node_diversity = len(set(chromo))
    total_nodes = len(state.nodes)

    # 计算使用节点的比例
    node_usage_ratio = node_diversity / total_nodes

    # 极度强调节点多样性的奖励机制
    diversity_bonus = 0.0

    # 根据使用节点数量给予不同级别的奖励
    if node_diversity >= total_nodes:
        # 使用了所有节点，给予极高奖励
        diversity_bonus = 20.0
    elif node_diversity >= total_nodes * 0.8:
        # 使用了80%以上的节点，给予高奖励
        diversity_bonus = 15.0
    elif node_diversity >= total_nodes * 0.6:
        # 使用了60%以上的节点，给予中高奖励
        diversity_bonus = 10.0
    elif node_diversity >= total_nodes * 0.4:
        # 使用了40%以上的节点，给予中等奖励
        diversity_bonus = 5.0
    elif node_diversity >= total_nodes * 0.2:
        # 使用了20%以上的节点，给予基础奖励
        diversity_bonus = 2.0

    # 额外奖励：基于节点使用率的非线性奖励
    diversity_bonus += 10.0 * node_usage_ratio ** 2

    # 计算适应度公式，大幅提高多样性奖励的影响
    # 调整公式，使多样性奖励成为主要因素
    fit = (gamma * s_ru * 0.5) - ((1.0 - gamma) * t_resp * 0.3) + diversity_bonus

    # 对不可达路径进行严重惩罚
    if bw <= 0:
        fit -= 1000.0

    return fit


def _tournament_select(pop: List[List[int]], fits: List[float], k: int) -> List[int]:
    """
    锦标赛选择：从种群中选择一个较优个体
    :param pop: 当前种群
    :param fits: 对应的适应度值列表
    :param k: 参与锦标赛的个体数
    :return: 被选中的染色体副本
    """
    # 随机选取k个个体参与竞争（不超过种群大小）
    idxs = random.sample(range(len(pop)), k=min(k, len(pop)))
    # 找到适应度最高的个体索引
    best = max(idxs, key=lambda i: fits[i])
    # 返回该个体的副本
    return pop[best][:]


def _fix_chromosome(chromo: List[int], node_ids: List[int], target_length: int) -> List[int]:
    """
    修复染色体：去除重复节点并补充到目标长度（优化后的交叉操作需要）
    :param chromo: 待修复的染色体
    :param node_ids: 可用节点ID列表
    :param target_length: 目标染色体长度
    :return: 修复后的染色体
    """
    # 去除重复节点，保持顺序
    used_nodes = set()
    fixed = []
    for nid in chromo:
        if nid not in used_nodes:
            fixed.append(nid)
            used_nodes.add(nid)

    # 如果长度不足，补充新节点
    if len(fixed) < target_length:
        available = [nid for nid in node_ids if nid not in used_nodes]
        needed = target_length - len(fixed)

        if len(available) >= needed:
            # 有足够的可用节点
            fixed.extend(random.sample(available, needed))
        else:
            # 节点数不足，允许重复但避免连续重复
            for _ in range(needed):
                nid = random.choice(node_ids)
                # 尝试避免与最后一个节点相同
                if fixed and nid == fixed[-1]:
                    for _ in range(3):
                        new_nid = random.choice(node_ids)
                        if new_nid != fixed[-1]:
                            nid = new_nid
                            break
                fixed.append(nid)

    return fixed[:target_length]


def _crossover(p1: List[int], p2: List[int], node_ids: List[int]) -> Tuple[List[int], List[int]]:
    """
    交叉操作：两个父代产生两个子代（优化版，添加重复节点修复）
    :param p1: 第一个父代染色体
    :param p2: 第二个父代染色体
    :param node_ids: 可用节点ID列表
    :return: 两个子代染色体
    """
    # 如果染色体长度小于2，无法交叉，直接返回副本
    if len(p1) < 2:
        return p1[:], p2[:]

    # 在随机位置切割染色体
    cut = random.randrange(1, len(p1))
    # 生成两个子代
    c1 = p1[:cut] + p2[cut:]  # 第一个子代
    c2 = p2[:cut] + p1[cut:]  # 第二个子代

    # 修复子代中可能出现的重复节点
    c1 = _fix_chromosome(c1, node_ids, len(p1))
    c2 = _fix_chromosome(c2, node_ids, len(p2))

    return c1, c2

def _mutate(chromo: List[int], node_ids: List[int], rate: float, state: NetworkState, req: UserRequest) -> None:
    """
    变异操作：以一定概率交换染色体中的两个基因（优化版）
    交换策略比替换策略能更好地保持优秀基因
    :param chromo: 待变异的染色体
    :param node_ids: 可选节点ID列表
    :param rate: 变异率
    :param state: 网络状态对象
    :param req: 用户请求对象
    """
    # 获取网络中所有节点
    total_nodes = len(node_ids)
    # 获取当前路径中已使用的节点
    used_nodes = set(chromo)
    # 计算未使用的节点
    unused_nodes = [n for n in node_ids if n not in used_nodes]

    # 遍历染色体的每一个基因
    for i in range(len(chromo)):
        # 以变异率的概率进行变异
        if random.random() < rate:
            # 获取当前位置需要的资源
            _, c_need, t_need = req.capability_needs[i]

            # 基本限制：不能与当前节点相同，并且节点必须有足够资源
            available_nodes = []
            for n in node_ids:
                # 检查节点是否满足基本条件
                if n != chromo[i] and _check_node_resources(state, n, c_need, t_need):
                    # 位置限制：不能与相邻节点相同
                    if 0 < i < len(chromo) - 1:
                        if n != chromo[i-1] and n != chromo[i+1]:
                            available_nodes.append(n)
                    elif i > 0:
                        if n != chromo[i-1]:
                            available_nodes.append(n)
                    elif i < len(chromo) - 1:
                        if n != chromo[i+1]:
                            available_nodes.append(n)
                    else:
                        available_nodes.append(n)

            # 如果没有可用节点，则无法变异
            if not available_nodes:
                continue

            # 优先选择未使用的节点
            available_unused = [n for n in available_nodes if n not in used_nodes]

            # 极度倾向于选择未使用节点
            # 如果还有未使用节点，95%的概率选择它们
            if available_unused and random.random() < 0.95:
                nid = random.choice(available_unused)
                # 更新已使用节点集合
                used_nodes.add(nid)
            else:
                # 只有在无法选择未使用节点时才选择已使用节点
                nid = random.choice(available_nodes)

            # 应用变异
            chromo[i] = nid


def run_ga(state: NetworkState, req: UserRequest) -> Optional[List[int]]:
    """
    运行遗传算法：主入口函数
    :param state: 网络状态对象
    :param req: 用户请求对象
    :return: 最佳部署路径（节点ID列表），找不到则返回None
    :raises ResourceWarning: 当系统资源不足时发出警告
    """
    # 首先检查资源可用性
    if not _check_resource_availability(state, req):
        # 资源不足，返回None
        return None

    # 从配置文件读取参数
    pop_size = cfg.GA_POP_SIZE  # 种群大小
    iterations = cfg.GA_ITERATIONS  # 迭代次数
    k = cfg.GA_TOURNAMENT_K  # 锦标赛规模
    cr = cfg.GA_CROSSOVER_RATE  # 交叉率
    mr = cfg.GA_MUTATION_RATE  # 变异率

    # 初始化种群
    pop = _init_population(state, req, pop_size)
    # 获取节点ID列表
    node_ids = list(state.nodes.keys())

    # 初始化最佳解
    best_ch = None  # 最佳染色体
    best_fit = float('-inf')  # 最佳适应度值

    # 开始迭代进化过程
    for _ in range(iterations):
        now = time.time()  # 获取当前时间
        # 计算当前种群中每个个体的适应度
        fits = [_fitness(state, req, ch, now) for ch in pop]

        # 更新全局最佳解
        for ch, f in zip(pop, fits):
            if f > best_fit:
                best_fit = f
                best_ch = ch[:]

        # 生成下一代种群
        new_pop: List[List[int]] = []
        # 不断生成新个体直到达到种群大小
        while len(new_pop) < pop_size:
            # 选择两个父代
            p1 = _tournament_select(pop, fits, k)
            p2 = _tournament_select(pop, fits, k)

            # 以一定概率进行交叉
            if random.random() < cr:
                c1, c2 = _crossover(p1, p2, node_ids)
            else:
                c1, c2 = p1[:], p2[:]

            # 对子代进行变异，传入state和req参数以检查资源
            _mutate(c1, node_ids, mr, state, req)
            _mutate(c2, node_ids, mr, state, req)

            # 检查变异后的染色体是否有效（所有节点都有足够资源）
            c1_valid = all(_check_node_resources(state, gene, req.capability_needs[i][1], req.capability_needs[i][2])
                          for i, gene in enumerate(c1))
            c2_valid = all(_check_node_resources(state, gene, req.capability_needs[i][1], req.capability_needs[i][2])
                          for i, gene in enumerate(c2))

            # 添加有效的个体到新种群
            if c1_valid:
                new_pop.append(c1)
            if c2_valid and len(new_pop) < pop_size:
                new_pop.append(c2)

        # 截取所需数量的个体作为新一代种群
        pop = new_pop[:pop_size]

    # 返回最佳部署方案
    return best_ch