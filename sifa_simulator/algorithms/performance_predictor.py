# -*- coding: utf-8 -*-
"""
基于GNN的网络性能预测器（增强版）

支持两种模式：
1. 真实模型模式：加载预训练的GNN模型（ONNX或PyTorch）进行推理
2. 简化模式：基于负载和服务链数量的公式预测
"""
from __future__ import annotations

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Any

# 全局模型实例（懒加载）
_model_instance: Optional[Any] = None
_model_type: Optional[str] = None  # "onnx", "pytorch", or None


def load_model(model_path: str = None) -> bool:
    """
    加载预训练的GNN模型
    
    参数:
    - model_path: 模型文件路径，如果为None则自动搜索
    
    返回:
    - 是否成功加载
    """
    global _model_instance, _model_type
    
    # 如果没有指定路径，搜索默认路径
    if model_path is None:
        models_dir = Path(__file__).parent / "models"
        
        # 优先尝试ONNX格式
        onnx_path = models_dir / "predictor.onnx"
        if onnx_path.exists():
            model_path = str(onnx_path)
        else:
            # 尝试PyTorch格式
            pt_path = models_dir / "predictor.pt"
            if pt_path.exists():
                model_path = str(pt_path)
    
    if model_path is None:
        return False
    
    try:
        # 根据文件扩展名加载模型
        if model_path.endswith('.onnx'):
            return _load_onnx_model(model_path)
        elif model_path.endswith('.pt') or model_path.endswith('.pth'):
            return _load_pytorch_model(model_path)
        else:
            print(f"不支持的模型格式: {model_path}")
            return False
    except Exception as e:
        print(f"加载模型失败: {e}")
        return False


def _load_onnx_model(model_path: str) -> bool:
    """加载ONNX模型"""
    global _model_instance, _model_type
    
    try:
        import onnxruntime as ort
        
        session = ort.InferenceSession(model_path)
        _model_instance = session
        _model_type = "onnx"
        
        print(f"✅ 成功加载ONNX模型: {model_path}")
        return True
    except ImportError:
        print("⚠️ 未安装onnxruntime，无法加载ONNX模型")
        print("   安装命令: pip install onnxruntime")
        return False
    except Exception as e:
        print(f"加载ONNX模型失败: {e}")
        return False


def _load_pytorch_model(model_path: str) -> bool:
    """加载PyTorch模型"""
    global _model_instance, _model_type
    
    try:
        import torch
        
        model = torch.load(model_path, map_location=torch.device('cpu'))
        model.eval()
        
        _model_instance = model
        _model_type = "pytorch"
        
        print(f"✅ 成功加载PyTorch模型: {model_path}")
        return True
    except ImportError:
        print("⚠️ 未安装PyTorch，无法加载PyTorch模型")
        print("   安装命令: pip install torch")
        return False
    except Exception as e:
        print(f"加载PyTorch模型失败: {e}")
        return False


def predict_with_model(node_features: np.ndarray, 
                      adjacency_matrix: np.ndarray) -> Tuple[float, float]:
    """
    使用真实模型进行预测
    
    参数:
    - node_features: 节点特征矩阵 (N, F)
    - adjacency_matrix: 邻接矩阵 (N, N)
    
    返回:
    - (时延, 丢包率)
    """
    global _model_instance, _model_type
    
    if _model_instance is None:
        raise RuntimeError("模型未加载，请先调用load_model()")
    
    try:
        if _model_type == "onnx":
            return _predict_onnx(node_features, adjacency_matrix)
        elif _model_type == "pytorch":
            return _predict_pytorch(node_features, adjacency_matrix)
        else:
            raise RuntimeError(f"未知的模型类型: {_model_type}")
    except Exception as e:
        print(f"模型推理失败: {e}")
        # 回退到简化预测
        return predict_performance_simple(0.5, 10)


def _predict_onnx(node_features: np.ndarray, 
                 adjacency_matrix: np.ndarray) -> Tuple[float, float]:
    """使用ONNX模型预测"""
    global _model_instance
    
    # 准备输入
    inputs = {
        _model_instance.get_inputs()[0].name: node_features.astype(np.float32),
        _model_instance.get_inputs()[1].name: adjacency_matrix.astype(np.float32)
    }
    
    # 推理
    outputs = _model_instance.run(None, inputs)
    
    # 解析输出
    delay = float(outputs[0])
    loss = float(outputs[1])
    
    return delay, loss


def _predict_pytorch(node_features: np.ndarray,
                    adjacency_matrix: np.ndarray) -> Tuple[float, float]:
    """使用PyTorch模型预测"""
    global _model_instance
    import torch
    
    # 准备输入
    node_features_tensor = torch.from_numpy(node_features).float()
    adjacency_tensor = torch.from_numpy(adjacency_matrix).float()
    
    # 推理（无梯度）
    with torch.no_grad():
        outputs = _model_instance(node_features_tensor, adjacency_tensor)
    
    # 解析输出
    if isinstance(outputs, tuple):
        delay = float(outputs[0])
        loss = float(outputs[1])
    else:
        delay = float(outputs[0])
        loss = float(outputs[1])
    
    return delay, loss


def predict_performance_simple(overall_load: float, 
                              active_chain_count: int) -> Tuple[float, float]:
    """
    简化的性能预测（基于公式）
    
    参数:
    - overall_load: [0,1] 整体负载
    - active_chain_count: 活动服务链数量
    
    返回:
    - (时延ms, 丢包率%)
    """
    # 基于负载的时延预测
    delay_ms = 20.0 + (overall_load * 100.0) + (active_chain_count * 5.0)
    
    # 基于负载的丢包率预测
    loss_pct = 0.01 + (overall_load ** 2) * 5.0
    
    return delay_ms, loss_pct


def predict_performance(overall_load: float, 
                       active_chain_count: int,
                       network_state: Any = None,
                       use_model: bool = False) -> Tuple[float, float]:
    """
    网络性能预测（统一接口）
    
    参数:
    - overall_load: [0,1] 整体负载
    - active_chain_count: 活动服务链数量
    - network_state: 网络状态对象（用于构建特征）
    - use_model: 是否尝试使用真实模型
    
    返回:
    - (时延ms, 丢包率%)
    """
    # 如果启用真实模型且模型已加载
    if use_model and _model_instance is not None and network_state is not None:
        try:
            # 构建特征
            node_features, adjacency = _build_graph_features(network_state)
            return predict_with_model(node_features, adjacency)
        except Exception as e:
            print(f"模型预测失败，回退到简化模式: {e}")
    
    # 回退到简化预测
    return predict_performance_simple(overall_load, active_chain_count)


def _build_graph_features(network_state: Any) -> Tuple[np.ndarray, np.ndarray]:
    """
    从网络状态构建图特征
    
    返回:
    - (节点特征矩阵, 邻接矩阵)
    """
    nodes = list(network_state.nodes.values())
    n = len(nodes)
    
    # 构建节点特征矩阵 (N, 4)
    # 特征：[计算利用率, 时隙利用率, 总计算资源, 总时隙资源]
    node_features = np.zeros((n, 4), dtype=np.float32)
    
    for i, node in enumerate(nodes):
        compute_util = node.used_compute / max(1, node.total_compute)
        timeslot_util = node.used_timeslot / max(1, node.total_timeslot)
        
        node_features[i] = [
            compute_util,
            timeslot_util,
            float(node.total_compute),
            float(node.total_timeslot)
        ]
    
    # 构建邻接矩阵 (N, N)
    adjacency = np.zeros((n, n), dtype=np.float32)
    
    node_id_to_idx = {node.id: i for i, node in enumerate(nodes)}
    
    for link in network_state.links:
        if link.src in node_id_to_idx and link.dst in node_id_to_idx:
            i = node_id_to_idx[link.src]
            j = node_id_to_idx[link.dst]
            # 使用带宽作为边权重（归一化）
            weight = link.bandwidth / 200.0  # 假设最大带宽200
            adjacency[i, j] = weight
            adjacency[j, i] = weight  # 无向图
    
    return node_features, adjacency


# 模块初始化时尝试自动加载模型
try:
    load_model()
except Exception:
    pass  # 忽略加载失败，使用简化模式


