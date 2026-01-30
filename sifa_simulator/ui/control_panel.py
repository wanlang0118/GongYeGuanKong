# -*- coding: utf-8 -*-
"""
左侧控制面板：
- 配置网络与生成
- 生成用户请求（单次或批量）
- 显示待处理请求队列
"""
from __future__ import annotations  # 使用未来的类型注解

import sys
from typing import List  # 导入列表类型注解
from PyQt6 import QtCore, QtWidgets  # 导入PyQt6的核心和小部件模块
import config as cfg  # 导入配置模块

class ControlPanel(QtWidgets.QWidget):  # 定义控制面板类，继承自QWidget
    generate_network_clicked = QtCore.pyqtSignal(int, tuple, tuple, tuple)  # 生成网络按钮点击信号
    generate_request_clicked = QtCore.pyqtSignal(str)  # 生成请求按钮点击信号
    batch_start_clicked = QtCore.pyqtSignal(int)  # 批量开始按钮点击信号
    batch_stop_clicked = QtCore.pyqtSignal()  # 批量停止按钮点击信号
    # 新增：模式切换信号
    mode_changed = QtCore.pyqtSignal(str)  # 模式切换信号

    def __init__(self, parent=None):  # 初始化方法
        super().__init__(parent)  # 调用父类的初始化方法
        self._setup_ui()  # 设置用户界面

    def _setup_ui(self):  # 设置用户界面的方法
        layout = QtWidgets.QVBoxLayout(self)  # 创建垂直布局管理器

        # 当前模式显示（原来的模式区域改为显示当前选择）
        gb_current_mode = QtWidgets.QGroupBox("当前运行模式")
        current_mode_layout = QtWidgets.QVBoxLayout(gb_current_mode)
        self.lbl_current_mode = QtWidgets.QLabel("SIFA智能模式（GA+PLSAFC+PSO）")
        self.lbl_current_mode.setStyleSheet("font-weight: bold; color: #2E8B57;")
        current_mode_layout.addWidget(self.lbl_current_mode)

        # 网络环境配置
        gb_net = QtWidgets.QGroupBox("🌐 网络配置")  # 创建网络配置组框
        form = QtWidgets.QFormLayout(gb_net)  # 创建表单布局管理器
        self.le_nodes = QtWidgets.QLineEdit(str(cfg.DEFAULT_NODE_COUNT))  # 创建节点数量输入框
        self.le_compute = QtWidgets.QLineEdit(f"{cfg.COMPUTE_RESOURCE_RANGE[0]}-{cfg.COMPUTE_RESOURCE_RANGE[1]}")  # 创建计算资源范围输入框
        self.le_timeslot = QtWidgets.QLineEdit(f"{cfg.TIMESLOT_RESOURCE_RANGE[0]}-{cfg.TIMESLOT_RESOURCE_RANGE[1]}")  # 创建时隙资源范围输入框
        self.le_bw = QtWidgets.QLineEdit(f"{cfg.LINK_BW_RANGE[0]}-{cfg.LINK_BW_RANGE[1]}")  # 创建带宽范围输入框
        form.addRow("节点数量", self.le_nodes)  # 将节点数量输入框添加到表单布局中
        form.addRow("计算资源范围", self.le_compute)  # 将计算资源范围输入框添加到表单布局中
        form.addRow("时隙资源范围", self.le_timeslot)  # 将时隙资源范围输入框添加到表单布局中
        form.addRow("带宽范围", self.le_bw)  # 将带宽范围输入框添加到表单布局中
        self.btn_gen_net = QtWidgets.QPushButton("🔄 生成网络")  # 创建生成网络按钮
        form.addRow(self.btn_gen_net)  # 将生成网络按钮添加到表单布局中

        # 用户请求与服务链部署
        gb_req = QtWidgets.QGroupBox("📋 创建请求")  # 创建请求生成组框
        v = QtWidgets.QVBoxLayout(gb_req)  # 创建垂直布局管理器
        self.cb_app = QtWidgets.QComboBox()  # 创建应用类型下拉框
        self.cb_app.addItems(list(cfg.APP_TYPES.keys()))  # 将应用类型添加到下拉框中
        self.btn_gen_req = QtWidgets.QPushButton("➕生成单个用户请求")  # 创建生成单个请求按钮


        self.spin_rps = QtWidgets.QSpinBox()  # 创建每秒请求数输入框
        self.spin_rps.setRange(1, 100)  # 设置每秒请求数输入框的范围
        self.spin_rps.setValue(2)  # 设置每秒请求数输入框的默认值
        self.btn_batch_start = QtWidgets.QPushButton("➕生成批量请求模拟")  # 创建批量开始按钮
        self.btn_batch_stop = QtWidgets.QPushButton("停止")  # 创建批量停止按钮


        v.addWidget(self.cb_app)  # 将应用类型下拉框添加到垂直布局中
        v.addWidget(self.btn_gen_req)  # 将生成单个请求按钮添加到垂直布局中

        v.addWidget(self.btn_batch_start)  # 将批量开始按钮添加到垂直布局中
        v.addWidget(QtWidgets.QLabel("每秒请求数"))
        v.addWidget(self.spin_rps)
        v.addWidget(self.btn_batch_stop)  # 将批量停止按钮添加到垂直布局中

        # 待处理队列表
        self.tbl_queue = QtWidgets.QTableWidget(0, 5)  # 创建待处理请求队列表
        self.tbl_queue.setHorizontalHeaderLabels(["请求ID", "到达时间", "过期时间", "应用类型", "真实类别"])  # 设置表头标签
        self.tbl_queue.horizontalHeader().setStretchLastSection(True)  # 设置最后一列自动拉伸
        self.tbl_queue.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # 设置表不可编辑
        self.tbl_queue.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)  # 设置选择行为为整行选择

        # layout.addWidget(gb_main_mode)  # 添加主要模式选择组框
        layout.addWidget(gb_current_mode)  # 添加当前模式显示组框
        layout.addWidget(gb_net)  # 将网络配置组框添加到垂直布局中
        layout.addWidget(gb_req)  # 将请求生成组框添加到垂直布局中
        self.lbl_queue = QtWidgets.QLabel("待处理的用户请求队列")  # 保存队列标签的引用
        layout.addWidget(self.lbl_queue)  # 将队列表标签添加到垂直布局中
        layout.addWidget(self.tbl_queue, 1)  # 将队列表添加到垂直布局中，并设置拉伸因子为1
        layout.addStretch(1)  # 添加垂直布局的拉伸空间

        # 设置请求队列默认不显示
        self.tbl_queue.setVisible(False)
        self.lbl_queue.setVisible(False)  # 直接使用保存的标签引用
        self.btn_gen_net.clicked.connect(self._emit_generate_network)  # 连接生成网络按钮点击信号到_emit_generate_network方法
        self.btn_gen_req.clicked.connect(self._emit_generate_request)  # 连接生成请求按钮点击信号到_emit_generate_request方法
        self.btn_batch_start.clicked.connect(self._emit_batch_start)  # 连接批量开始按钮点击信号到_emit_batch_start方法
        self.btn_batch_stop.clicked.connect(self.batch_stop_clicked)  # 连接批量停止按钮点击信号到batch_stop_clicked信号

    def _parse_range(self, text: str) -> tuple:  # 解析范围字符串的方法
        try:
            a, b = text.split("-")  # 将字符串按"-"分割成两个部分
            return int(float(a.strip())), int(float(b.strip()))  # 将两个部分转换为整数并返回
        except Exception:
            return 1, 10  # 如果解析失败，返回默认范围

    def _emit_generate_network(self):  # 发射生成网络信号的方法
        n = int(float(self.le_nodes.text() or "6"))  # 获取节点数量，如果为空则默认为6
        cr = self._parse_range(self.le_compute.text())  # 解析计算资源范围
        tr = self._parse_range(self.le_timeslot.text())  # 解析时隙资源范围
        br = self._parse_range(self.le_bw.text())  # 解析带宽范围
        self.generate_network_clicked.emit(n, cr, tr, br)  # 发射生成网络信号

    def _emit_generate_request(self):  # 发射生成请求信号的方法
        app_key = self.cb_app.currentText()  # 获取当前选中的应用类型
        self.generate_request_clicked.emit(app_key)  # 发射生成请求信号

    def _emit_batch_start(self):  # 发射批量开始信号的方法
        rps = int(self.spin_rps.value())  # 获取每秒请求数
        self.batch_start_clicked.emit(rps)  # 发射批量开始信号

    # --- 外部调用：更新队列表 ---
    def add_request_row(self, req_id: int, arrival: float, expire: float, app: str, true_class: str):  # 添加请求行的方法
        row = self.tbl_queue.rowCount()  # 获取当前队列表的行数
        self.tbl_queue.insertRow(row)  # 在队列表中插入新行
        for col, val in enumerate([req_id, f"{arrival:.1f}", f"{expire:.1f}", app, true_class]):  # 遍历每个值
            self.tbl_queue.setItem(row, col, QtWidgets.QTableWidgetItem(str(val)))  # 将值添加到队列表对应单元格中

    def remove_request_row(self, req_id: int):  # 移除请求行的方法
        for r in range(self.tbl_queue.rowCount()):  # 遍历队列表中的每一行
            if self.tbl_queue.item(r, 0) and self.tbl_queue.item(r, 0).text() == str(req_id):  # 检查请求ID是否匹配
                self.tbl_queue.removeRow(r)  # 移除匹配的行
                return  # 结束方法



    def toggle_queue_visibility(self):
        """切换请求队列的显示/隐藏状态"""
        is_visible = not self.tbl_queue.isVisible()
        self.tbl_queue.setVisible(is_visible)
        # 同时隐藏/显示队列标签
        self.lbl_queue.setVisible(is_visible)

    # 在文件末尾添加update_mode_display方法
    def update_mode_display(self, mode: str):
        """更新当前运行模式的显示"""
        # 根据模式名称显示对应的完整描述
        mode_display_map = {
            "SIFA": "SIFA智能模式（GA+PLSAFC+PSO）",
            "Traditional": "传统网络模式",
            "Advanced": "高级智能模式"
        }
        # 设置显示文本，如果模式不在映射中则直接显示模式名
        display_text = mode_display_map.get(mode, mode)
        self.lbl_current_mode.setText(display_text)

        # 可以根据不同模式设置不同的文本颜色
        if mode == "SIFA":
            self.lbl_current_mode.setStyleSheet("font-weight: bold; color: #2E8B57;")
        elif mode == "Traditional":
            self.lbl_current_mode.setStyleSheet("font-weight: bold; color: #4682B4;")
        elif mode == "Advanced":
            self.lbl_current_mode.setStyleSheet("font-weight: bold; color: #9370DB;")


if __name__ == "__main__":
    from PyQt6 import QtWidgets

    print("=" * 60)
    print("控制面板测试 (control_panel.py)")
    print("=" * 60)

    app = QtWidgets.QApplication(sys.argv)

    panel = ControlPanel()
    panel.setWindowTitle("SIFA控制面板")
    panel.resize(300, 500)

    panel.show()

    sys.exit(app.exec())

