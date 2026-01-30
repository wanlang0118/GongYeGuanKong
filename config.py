# -*- coding: utf-8 -*-
"""
全局配置参数
本文件包含应用类型、资源范围、算法参数等常量定义，支持离线运行。
"""
from __future__ import annotations

from dataclasses import dataclass


# ============ 基础配置 ============
# 随机种子（可选）。如为 None 则每次运行不同。
RANDOM_SEED: int | None = None


# 模拟模式：SIFA智能模式 vs 传统网络模式
# 修改SIMULATION_MODE配置项，添加对Advanced模式的支持
SIMULATION_MODE = "SIFA"  # 可选: "SIFA", "Traditional" 或 "Advanced"

# 网络生成默认范围
DEFAULT_NODE_COUNT = 6
COMPUTE_RESOURCE_RANGE = (20, 60)  # 每个节点的总计算资源范围
TIMESLOT_RESOURCE_RANGE = (50, 120)  # 每个节点的总时隙资源范围
LINK_BW_RANGE = (50, 200)  # 链路带宽范围（单位：Mbps）

# ============ GA 参数 ============
GA_POP_SIZE = 30
GA_ITERATIONS = 100
GA_TOURNAMENT_K = 3
GA_CROSSOVER_RATE = 0.8
GA_MUTATION_RATE = 0.1
GAMMA_FITNESS = 0.6  # Fitness = γ * S_ru - (1 - γ) * T_Response

# ============ PSO 参数 ============
PSO_SWARM_SIZE = 20  # 粒子群大小
PSO_MAX_ITERATIONS = 50  # 最大迭代次数
PSO_INERTIA_WEIGHT = 0.7  # 惯性权重 w
PSO_COGNITIVE_COEFF = 1.5  # 认知系数 c1 (个体学习因子)
PSO_SOCIAL_COEFF = 1.5  # 社会系数 c2 (群体学习因子)
PSO_MAX_VELOCITY = 0.5  # 最大速度限制
PSO_FITNESS_THRESHOLD = 8.0  # 适应度阈值（提前终止条件）

# ============ PLSAFC 分类器配置 ============
# 权重与阈值（需满足控制类FEC较高、非控制类FEC较低）
PLSAFC_W1 = 0.08
PLSAFC_W2 = 0.12
PLSAFC_W3 = 0.02
PLSAFC_THRESHOLD = 2.5

# 特征-词概率映射（模拟论文第4章的概率模型）
# 用于更真实地计算FEC值
PLSAFC_FEATURE_PROB = {
    "控制": {
        "avg_pkt_size_small": 0.85,   # 控制流量倾向小包
        "avg_pkt_size_large": 0.15,
        "pkt_rate_high": 0.90,         # 控制流量包率高
        "pkt_rate_low": 0.10,
        "flow_duration_short": 0.95,   # 控制流量持续时间短
        "flow_duration_long": 0.05,
    },
    "非控制": {
        "avg_pkt_size_small": 0.20,   # 非控制流量倾向大包
        "avg_pkt_size_large": 0.80,
        "pkt_rate_high": 0.15,         # 非控制流量包率低
        "pkt_rate_low": 0.85,
        "flow_duration_short": 0.10,   # 非控制流量持续时间长
        "flow_duration_long": 0.90,
    }
}

# 预测定时（秒）
PREDICT_INTERVAL_SEC = 2
KPI_REFRESH_INTERVAL_MS = 1000
BATCH_GEN_INTERVAL_MS = 1000

# 应用类型定义：能力列表、资源需求、流量大小与类别
# 资源需求按每个能力的计算与时隙需求
@dataclass(frozen=True)
class CapabilityNeed:
    name: str
    compute: int
    timeslot: int


APP_TYPES = {
    "视频编解码": {
        "capabilities": [
            CapabilityNeed("分类", 5, 5),
            CapabilityNeed("转发", 3, 2),
            CapabilityNeed("解码", 8, 6),
        ],
        "flow_size_mb": 50,  # 模拟流量大小
        "app_type": "多媒体",
        "true_class": "非控制",
    },
    "AGV控制": {
        "capabilities": [
            CapabilityNeed("分类", 3, 2),
            CapabilityNeed("调度", 4, 4),
            CapabilityNeed("转发", 2, 2),
        ],
        "flow_size_mb": 5,
        "app_type": "工业控制",
        "true_class": "控制",
    },
    "数据采集": {
        "capabilities": [
            CapabilityNeed("分类", 2, 2),
            CapabilityNeed("转发", 2, 1),
        ],
        "flow_size_mb": 10,
        "app_type": "传感数据",
        "true_class": "非控制",
    },
}

# 特征模拟范围（控制 vs 非控制）
FEATURE_RANGES = {
    "控制": {
        "avg_pkt_size": (60, 150),     # 字节
        "pkt_rate": (200, 600),        # pps
        "flow_duration": (0.05, 0.5),  # 秒
    },
    "非控制": {
        "avg_pkt_size": (400, 1200),
        "pkt_rate": (10, 80),
        "flow_duration": (5.0, 60.0),
    },
}