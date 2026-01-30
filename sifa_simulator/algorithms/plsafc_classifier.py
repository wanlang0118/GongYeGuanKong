# -*- coding: utf-8 -*-
"""
PLSAFC 流量分类算法（优化版）

模拟论文第4章的PLSAFC算法：
- 使用PLSA + Elastic Net学习到的特征词典
- 计算流膨胀系数（FEC）进行分类
- W_E（扩展集）：预示"控制"流量的特征
- W_C（收缩集）：预示"非控制"流量的特征

FEC公式：FEC = (w1 * pkt_rate + w2 * flow_regularity) / (w3 * avg_pkt_size)

此实现旨在教学演示用途，模拟PLSAFC的最终产物而非完整PLSA过程。
"""
from __future__ import annotations

import random
from typing import Dict, Tuple

import config as cfg
from sifa_simulator.core.data_structures import TrafficFlow


def simulate_features(true_class: str) -> Dict[str, float]:
    """
    根据流量真实类别生成模拟的统计特征（优化版）
    
    这是为了让模拟器能够正确计算FEC值。
    控制流量：包小、速率高、规律性强
    非控制流量：包大、速率低/中、规律性差
    
    参数:
    - true_class: 真实类别（"控制"或"非控制"）
    
    返回:
    - 特征字典，包含 avg_pkt_size, pkt_rate, flow_regularity
    """
    if true_class == "控制":
        # 控制流量特征（如：机器臂指令、传感器数据）
        # 特征：包小、速率高、规律性强
        avg_pkt_size = random.uniform(60, 150)       # 60-150 bytes (小包)
        pkt_rate = random.uniform(20, 100)           # 20-100 packets/sec (高速率)
        flow_regularity = random.uniform(0.8, 1.0)   # 0.8-1.0 (非常规律)
    else:  # "非控制"
        # 非控制流量特征（如：视频监控、数据备份）
        # 特征：包大、速率低/中、规律性差
        avg_pkt_size = random.uniform(1000, 1500)    # 1000-1500 bytes (大包)
        pkt_rate = random.uniform(5, 40)             # 5-40 packets/sec (低速率)
        flow_regularity = random.uniform(0.2, 0.6)   # 0.2-0.6 (不规律)
    
    return {
        'avg_pkt_size': avg_pkt_size,
        'pkt_rate': pkt_rate,
        'flow_regularity': flow_regularity
    }


def calculate_fec(features: Dict[str, float]) -> float:
    """
    计算流膨胀系数（FEC）- 论文公式的模拟实现
    
    模拟PLSAFC算法的核心：通过PLSA学习到的特征词典计算FEC。
    
    FEC公式：
    FEC = (w1 * pkt_rate + w2 * flow_regularity) / (w3 * avg_pkt_size)
    
    其中：
    - W_E (扩展集，分子)：pkt_rate, flow_regularity - 预示"控制"流量
    - W_C (收缩集，分母)：avg_pkt_size - 预示"非控制"流量
    
    参数:
    - features: 特征字典
    
    返回:
    - FEC值（float）
    """
    # 从特征字典中安全地获取值，如果缺失则使用默认值
    pkt_rate = features.get('pkt_rate', 1.0)
    flow_regularity = features.get('flow_regularity', 0.1)
    avg_pkt_size = features.get('avg_pkt_size', 1.0)
    
    # 获取权重（从配置文件读取）
    w_pr = cfg.PLSAFC_W1   # pkt_rate 权重
    w_reg = cfg.PLSAFC_W2  # flow_regularity 权重
    w_ps = cfg.PLSAFC_W3   # avg_pkt_size 权重
    
    # 计算分子（扩展集 W_E）
    numerator = (w_pr * pkt_rate) + (w_reg * flow_regularity)
    
    # 计算分母（收缩集 W_C）
    # 添加小的 epsilon 防止除以零
    denominator = (w_ps * avg_pkt_size) + 1e-6
    
    # 计算 FEC 值
    fec_value = numerator / denominator
    
    return fec_value


def classify(flow: TrafficFlow, use_probabilistic: bool = False) -> Tuple[str, float]:
    """
    对流量进行分类（优化版）
    
    步骤：
    1. 检查流量是否包含特征
    2. 计算FEC值
    3. 与阈值比较得出分类结果
    
    参数:
    - flow: 流量对象（包含统计特征）
    - use_probabilistic: 是否使用概率模型（增强分类准确性）
    
    返回:
    - (预测类别, FEC值)，例如：("控制", 8.43) 或 ("非控制", 1.25)
    """
    # 检查特征是否存在
    if not flow.features:
        # 如果没有特征，无法分类，返回默认值
        return "非控制", 0.0
    
    # 1. 计算FEC值（模拟论文公式）
    fec_value = calculate_fec(flow.features)
    
    # 2. 如果使用概率模型，根据特征概率调整FEC值
    if use_probabilistic:
        # 基于真实类别的特征概率，模拟PLSA学习到的主题-词分布
        prob_weight = 1.0
        if flow.true_class in cfg.PLSAFC_FEATURE_PROB:
            probs = cfg.PLSAFC_FEATURE_PROB[flow.true_class]
            # 根据包大小和包速率调整概率权重
            if flow.features.get('avg_pkt_size', 0) < 300:  # 小包
                prob_weight *= probs.get('avg_pkt_size_small', 0.5)
            else:  # 大包
                prob_weight *= probs.get('avg_pkt_size_large', 0.5)
            
            if flow.features.get('pkt_rate', 0) > 100:  # 高速率
                prob_weight *= probs.get('pkt_rate_high', 0.5)
            else:  # 低速率
                prob_weight *= probs.get('pkt_rate_low', 0.5)
            
            # 应用概率权重到FEC值
            fec_value *= prob_weight
    
    # 3. 与阈值比较，得出预测类别
    if fec_value > cfg.PLSAFC_THRESHOLD:
        predicted_class = "控制"
    else:
        predicted_class = "非控制"
    
    # 4. 保存分类结果到流量对象
    flow.fec_value = fec_value
    flow.predicted_class = predicted_class
    
    return predicted_class, fec_value
