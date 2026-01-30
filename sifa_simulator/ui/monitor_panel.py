# -*- coding: utf-8 -*-
"""
右侧监控与分析面板：
- 流量分类结果表
- 预测性能LCD
- 实时KPI显示
"""
from __future__ import annotations

import sys
import random
from typing import Dict

from PyQt6 import QtCore, QtWidgets, QtGui

# 导入PLSAFC分类器
from sifa_simulator.algorithms.plsafc_classifier import (
    simulate_features, classify, calculate_fec
)


class MonitorPanel(QtWidgets.QWidget):
    # 新增：数据导出信号
    export_kpi_clicked = QtCore.pyqtSignal()
    export_classification_clicked = QtCore.pyqtSignal()
    export_report_clicked = QtCore.pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # 新增：监控内容切换按钮组
        button_layout = QtWidgets.QHBoxLayout()
        self.btn_switch_prediction = QtWidgets.QPushButton("网络性能预测")
        self.btn_switch_classification = QtWidgets.QPushButton("流量分类结果")
        self.btn_switch_kpi = QtWidgets.QPushButton("实时KPI监控")

        # 设置按钮样式，第一个按钮默认选中
        self.btn_switch_prediction.setCheckable(True)
        self.btn_switch_classification.setCheckable(True)
        self.btn_switch_kpi.setCheckable(True)

        # 使用按钮组确保只有一个按钮被选中
        button_group = QtWidgets.QButtonGroup(self)
        button_group.addButton(self.btn_switch_prediction)
        button_group.addButton(self.btn_switch_classification)
        button_group.addButton(self.btn_switch_kpi)

        # 默认选中性能预测
        self.btn_switch_prediction.setChecked(True)

        # 将按钮添加到布局
        button_layout.addWidget(self.btn_switch_prediction)
        button_layout.addWidget(self.btn_switch_classification)
        button_layout.addWidget(self.btn_switch_kpi)

        layout.addLayout(button_layout)

        # 性能预测
        self.gb_pred = QtWidgets.QGroupBox("网络性能预测 (GNN模拟)")
        g = QtWidgets.QGridLayout(self.gb_pred)
        self.lcd_delay = QtWidgets.QLCDNumber()
        self.lcd_delay.setDigitCount(6)
        self.lcd_loss = QtWidgets.QLCDNumber()
        self.lcd_loss.setDigitCount(6)
        g.addWidget(QtWidgets.QLabel("预测网络时延 (ms)"), 0, 0)
        g.addWidget(self.lcd_delay, 0, 1)
        g.addWidget(QtWidgets.QLabel("预测丢包率 (%)"), 1, 0)
        g.addWidget(self.lcd_loss, 1, 1)

        # 流量分类结果
        self.gb_cls = QtWidgets.QGroupBox("流量分类结果 (PLSAFC模拟)")
        v = QtWidgets.QVBoxLayout(self.gb_cls)
        
        # 添加演示按钮
        demo_layout = QtWidgets.QHBoxLayout()
        self.btn_demo_control = QtWidgets.QPushButton("演示控制流量分类")
        self.btn_demo_noncontrol = QtWidgets.QPushButton("演示非控制流量分类")
        demo_layout.addWidget(self.btn_demo_control)
        demo_layout.addWidget(self.btn_demo_noncontrol)
        v.addLayout(demo_layout)
        
        self.tbl_cls = QtWidgets.QTableWidget(0, 6)
        self.tbl_cls.setHorizontalHeaderLabels(["流量ID", "应用类型", "真实类别", "预测类别", "FEC值", "结果"]) 
        self.tbl_cls.horizontalHeader().setStretchLastSection(True)
        self.tbl_cls.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        v.addWidget(self.tbl_cls)

        # KPI
        self.gb_kpi = QtWidgets.QGroupBox("实时KPI监控")
        kpi_layout = QtWidgets.QVBoxLayout(self.gb_kpi)
        form = QtWidgets.QFormLayout()
        self.lb_recv = QtWidgets.QLabel("0.0 %")
        self.lb_resp = QtWidgets.QLabel("0.000 s")
        self.lb_rtp = QtWidgets.QLabel("0.000")
        self.lb_util = QtWidgets.QLabel("0.0 %")
        form.addRow("用户请求接收率", self.lb_recv)
        form.addRow("平均响应时间 (s)", self.lb_resp)
        form.addRow("RTP 平均值", self.lb_rtp)
        form.addRow("整体资源利用率", self.lb_util)
        kpi_layout.addLayout(form)
        
        # 新增：数据导出按钮
        gb_export = QtWidgets.QGroupBox("数据导出")
        export_layout = QtWidgets.QVBoxLayout(gb_export)
        self.btn_export_kpi = QtWidgets.QPushButton("📊 导出KPI数据 (CSV)")
        self.btn_export_classification = QtWidgets.QPushButton("📋 导出分类结果 (CSV)")
        self.btn_export_report = QtWidgets.QPushButton("📄 导出统计报告 (TXT)")
        export_layout.addWidget(self.btn_export_kpi)
        export_layout.addWidget(self.btn_export_classification)
        export_layout.addWidget(self.btn_export_report)

        # 将监控组件添加到布局
        layout.addWidget(self.gb_pred)
        layout.addWidget(self.gb_cls, 1)
        layout.addWidget(self.gb_kpi)
        layout.addWidget(gb_export)
        
        # 初始状态设置 - 只显示性能预测，隐藏其他两个
        self.gb_cls.setVisible(False)
        self.gb_kpi.setVisible(False)

        # 信号连接
        self.btn_export_kpi.clicked.connect(self.export_kpi_clicked)
        self.btn_export_classification.clicked.connect(self.export_classification_clicked)
        self.btn_export_report.clicked.connect(self.export_report_clicked)

        # 连接切换按钮的点击事件
        self.btn_switch_prediction.clicked.connect(self._on_switch_prediction)
        self.btn_switch_classification.clicked.connect(self._on_switch_classification)
        self.btn_switch_kpi.clicked.connect(self._on_switch_kpi)
        
        # 连接演示按钮的点击事件
        self.btn_demo_control.clicked.connect(self._demo_control_flow)
        self.btn_demo_noncontrol.clicked.connect(self._demo_noncontrol_flow)

    def _demo_control_flow(self):
        """演示控制流量分类"""
        # 生成控制流量特征
        features = simulate_features("控制")
        
        # 使用PLSAFC分类器进行分类
        from sifa_simulator.core.data_structures import TrafficFlow
        flow = TrafficFlow(
            flow_id=random.randint(1000, 9999),
            request_id=random.randint(1000, 9999),
            features=features,
            true_class="控制",
            app_type="工业控制"
        )
        
        # 分类（使用calculate_fec方法）
        pred_class, fec_value = classify(flow, use_probabilistic=False)
        
        # 添加到表格
        self.add_classification_row(
            flow.flow_id, 
            flow.app_type, 
            flow.true_class, 
            pred_class, 
            fec_value
        )
    
    def _demo_noncontrol_flow(self):
        """演示非控制流量分类"""
        # 生成非控制流量特征
        features = simulate_features("非控制")
        
        # 使用PLSAFC分类器进行分类
        from sifa_simulator.core.data_structures import TrafficFlow
        flow = TrafficFlow(
            flow_id=random.randint(1000, 9999),
            request_id=random.randint(1000, 9999),
            features=features,
            true_class="非控制",
            app_type="多媒体"
        )
        
        # 分类（使用calculate_fec方法）
        pred_class, fec_value = classify(flow, use_probabilistic=False)
        
        # 添加到表格
        self.add_classification_row(
            flow.flow_id, 
            flow.app_type, 
            flow.true_class, 
            pred_class, 
            fec_value
        )

    # 切换显示性能预测
    def _on_switch_prediction(self):
        self.gb_pred.setVisible(True)
        self.gb_cls.setVisible(False)
        self.gb_kpi.setVisible(False)

    # 切换显示流量分类结果
    def _on_switch_classification(self):
        self.gb_pred.setVisible(False)
        self.gb_cls.setVisible(True)
        self.gb_kpi.setVisible(False)

    # 切换显示实时KPI监控
    def _on_switch_kpi(self):
        self.gb_pred.setVisible(False)
        self.gb_cls.setVisible(False)
        self.gb_kpi.setVisible(True)

    # --- 外部调用接口 ---
    def add_classification_row(self, flow_id: int, app_type: str, true_cls: str, pred_cls: str, fec: float):
        row = self.tbl_cls.rowCount()
        self.tbl_cls.insertRow(row)
        ok = (true_cls == pred_cls)
        vals = [flow_id, app_type, true_cls, pred_cls, f"{fec:.3f}", ("正确" if ok else "错误")]
        for c, val in enumerate(vals):
            item = QtWidgets.QTableWidgetItem(str(val))
            self.tbl_cls.setItem(row, c, item)
        # 行颜色
        color = QtGui.QColor(220, 255, 220) if ok else QtGui.QColor(255, 220, 220)
        for c in range(self.tbl_cls.columnCount()):
            it = self.tbl_cls.item(row, c)
            if it:
                it.setBackground(color)

    def set_predictions(self, delay_ms: float, loss_pct: float):
        self.lcd_delay.display(f"{delay_ms:.1f}")
        self.lcd_loss.display(f"{loss_pct:.3f}")

    def set_kpis(self, values: Dict[str, float]):
        self.lb_recv.setText(f"{values['receive_rate']:.1f} %")
        self.lb_resp.setText(f"{values['avg_response']:.3f} s")
        self.lb_rtp.setText(f"{values['avg_rtp']:.3f}")
        self.lb_util.setText(f"{values['overall_util']:.1f} %")



if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    print("=" * 60)
    print("监控面板测试 (monitor_panel.py)")
    print("=" * 60)

    app = QApplication(sys.argv)
    app.setApplicationName("SIFA监控面板")
    app.setOrganizationName("SIFA Project")

    panel = MonitorPanel()
    panel.setWindowTitle("SIFA监控面板")
    panel.resize(600, 500)
    panel.show()

    # 添加一些演示数据
    panel._demo_control_flow()
    panel._demo_noncontrol_flow()
    panel._demo_control_flow()

    print("✅ 监控面板已打开")
    print("   - 性能预测: 显示网络时延、丢包率")
    print("   - 流量分类: 显示分类结果表格（包含PLSAFC算法演示）")
    print("   - 实时KPI: 显示接收率、响应时间等")
    print("   - 点击演示按钮可以测试PLSAFC分类器算法")

    sys.exit(app.exec())