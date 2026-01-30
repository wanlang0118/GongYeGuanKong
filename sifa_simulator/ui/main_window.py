# -*- coding: utf-8 -*-
"""
主窗口：集成控制面板、网络画布、监控面板与日志控制台。
"""
from __future__ import annotations  # 允许在类型注解中使用类名，避免提前导入的问题
from PyQt6 import QtCore, QtGui, QtWidgets
from typing import Optional  # 导入Optional类型，用于表示某个参数或返回值可以为None

from PyQt6 import QtCore, QtWidgets  # 导入PyQt6的核心模块和窗口部件
import pyqtgraph as pg  # 导入pyqtgraph库，用于绘制图形和图表

import config as cfg  # 导入配置文件，命名为cfg
from sifa_simulator.core.simulation_engine import SimulationEngine, EngineCallbacks  # 导入模拟引擎及其回调接口
from sifa_simulator.core.data_structures import TrafficFlow  # 导入流量数据结构
from sifa_simulator.ui.control_panel import ControlPanel  # 导入控制面板类
from sifa_simulator.ui.network_canvas import NetworkCanvas  # 导入网络画布类
from sifa_simulator.ui.monitor_panel import MonitorPanel  # 导入监控面板类
from sifa_simulator.algorithms.performance_predictor import predict_performance  # 导入性能预测算法函数


class MainWindow(QtWidgets.QMainWindow):  # 定义主窗口类，继承自QMainWindow
    def __init__(self):  # 定义类的构造函数
        super().__init__()  # 调用父类的构造函数
        self.setWindowTitle("软件定义工业互联网流量管控模拟器 (SIFA Simulator)")  # 设置窗口标题
        self.resize(1280, 800)  # 设置窗口大小为1280x800像素

        # 设置应用程序图标
        try:  # 尝试加载图标
            from pathlib import Path  # 导入Path类，用于处理文件路径
            icon_path = Path(__file__).parent.parent.parent / "img.png"  # 获取图标文件的路径
            if icon_path.exists():  # 检查图标文件是否存在
                from PyQt6.QtGui import QIcon  # 导入QIcon类
                self.setWindowIcon(QIcon(str(icon_path)))  # 设置窗口图标
        except Exception as e:  # 捕获异常
            print(f"加载图标失败: {e}")  # 打印错误信息

        self._setup_menu()  # 调用设置菜单栏的方法
        self._setup_ui()  # 调用设置用户界面的方法
        self._setup_engine()  # 调用设置模拟引擎的方法
        self._setup_timers()  # 调用设置定时器的方法
    
    def _setup_menu(self):
        """设置顶部菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        action_save_scene = file_menu.addAction("💾 保存网络场景...")
        action_save_scene.setShortcut("Ctrl+S")
        action_save_scene.triggered.connect(self.on_save_scene)
        
        action_load_scene = file_menu.addAction("📂 加载网络场景...")
        action_load_scene.setShortcut("Ctrl+O")
        action_load_scene.triggered.connect(self.on_load_scene)
        
        file_menu.addSeparator()
        
        action_exit = file_menu.addAction("🚪 退出")
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")
        
        action_clear_log = edit_menu.addAction("🗑️ 清空日志")
        action_clear_log.triggered.connect(lambda: self.txt_log.clear())
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")
        
        action_export_kpi = tools_menu.addAction("📊 导出KPI数据...")
        action_export_kpi.triggered.connect(self.on_export_kpi)
        
        action_export_cls = tools_menu.addAction("📋 导出分类结果...")
        action_export_cls.triggered.connect(self.on_export_classification)
        
        action_export_report = tools_menu.addAction("📄 导出统计报告...")
        action_export_report.triggered.connect(self.on_export_report)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        # 添加模式切换子菜单
        mode_menu = help_menu.addMenu("🔄 模拟模式切换")
        
        self.action_mode_sifa = mode_menu.addAction("SIFA智能模式")
        self.action_mode_sifa.setCheckable(True)
        self.action_mode_sifa.setChecked(True)  # 默认选中SIFA模式
        self.action_mode_sifa.triggered.connect(lambda: self.on_menu_mode_changed("SIFA"))
        
        self.action_mode_traditional = mode_menu.addAction("传统网络模式")
        self.action_mode_traditional.setCheckable(True)
        self.action_mode_traditional.triggered.connect(lambda: self.on_menu_mode_changed("Traditional"))
        
        self.action_mode_advanced = mode_menu.addAction("高级智能模式")
        self.action_mode_advanced.setCheckable(True)
        self.action_mode_advanced.triggered.connect(lambda: self.on_menu_mode_changed("Advanced"))
        
        # 设置为单选菜单组
        mode_group = QtGui.QActionGroup(self)
        mode_group.addAction(self.action_mode_sifa)
        mode_group.addAction(self.action_mode_traditional)
        mode_group.addAction(self.action_mode_advanced)
        mode_group.setExclusive(True)
        
        # 添加显示/隐藏请求队列的菜单项，默认不显示（未选中状态）
        help_menu.addSeparator()
        self.action_toggle_queue = help_menu.addAction("👁️ 显示/隐藏请求队列")
        self.action_toggle_queue.setCheckable(True)
        self.action_toggle_queue.setChecked(False)  # 默认不显示
        self.action_toggle_queue.triggered.connect(self.on_toggle_queue_visibility)
        
        help_menu.addSeparator()
        
        action_about = help_menu.addAction("ℹ️ 关于")
        action_about.triggered.connect(self.on_about)

    def on_menu_mode_changed(self, mode):
        """处理菜单中的模式切换"""
        # 更新UI中的选中状态
        if mode == "SIFA":
            self.action_mode_sifa.setChecked(True)
        elif mode == "Traditional":
            self.action_mode_traditional.setChecked(True)
        elif mode == "Advanced":
            self.action_mode_advanced.setChecked(True)
        
        # 调用原来的模式切换处理方法
        self.on_mode_changed(mode)
        
    def on_toggle_queue_visibility(self):
        """切换请求队列的显示/隐藏状态"""
        # 获取当前选中状态
        is_visible = self.action_toggle_queue.isChecked()
        
        # 调用控制面板的方法来切换队列显示状态
        # 假设控制面板有一个toggle_queue_visibility方法或set_queue_visibility方法
        if hasattr(self.panel_control, 'toggle_queue_visibility'):
            self.panel_control.toggle_queue_visibility()
        elif hasattr(self.panel_control, 'set_queue_visibility'):
            self.panel_control.set_queue_visibility(is_visible)
        else:
            # 如果控制面板没有相应方法，记录警告
            print("警告: 控制面板没有提供切换队列可见性的方法")

    def _setup_ui(self):
        """
        初始化并布局所有UI组件。
        该方法将界面分为可调节的上下两部分：
        - 上半部分：包含左侧控制面板、中间网络画布和右侧监控面板，三者之间也可调节。
        - 下半部分：日志输出区域。
        """
        # --- 1. 基础设置 ---
        from pathlib import Path
        style_path = Path(__file__).parent / "css/styles3.qss"
        with open(style_path, "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # --- 2. 创建上半部分 (三栏布局) ---
        # 使用水平QSplitter实现三栏可调节布局
        h_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # 2.1 左侧面板：控制区
        self.panel_control = ControlPanel()
        self.panel_control.setMinimumWidth(280)  # 直接设置最小宽度

        # 2.2 中间面板：网络画布
        self.canvas = NetworkCanvas(None)
        self.canvas.setMinimumWidth(300)  # 为画布设置最小宽度

        # 2.3 右侧面板：监控区
        self.panel_monitor = MonitorPanel()
        self.panel_monitor.setMinimumWidth(280)  # 防止面板被过度压缩

        # 将三部分添加到水平splitter中
        h_splitter.addWidget(self.panel_control)
        h_splitter.addWidget(self.canvas)
        h_splitter.addWidget(self.panel_monitor)

        # 设置拉伸因子，决定窗口缩放时各部分如何分配额外空间 (1:3:1)
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 3)
        h_splitter.setStretchFactor(2, 1)
        h_splitter.setSizes([540, 460, 260 ])  # 设置初始宽度分布

        # --- 3. 创建下半部分 (日志区域) ---
        log_widget = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 5, 0, 0)
        log_layout.addWidget(QtWidgets.QLabel("日志输出区 (Log Console)"))

        self.txt_log = QtWidgets.QTextEdit()
        self.txt_log.setReadOnly(True)
        log_layout.addWidget(self.txt_log)
        log_widget.setMinimumHeight(100)  # 防止日志区域被过度压缩

        # --- 4. 组装主窗口 ---
        # 使用垂直QSplitter将上下两部分组合起来
        v_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        v_splitter.addWidget(h_splitter)  # 上半部分
        v_splitter.addWidget(log_widget)  # 下半部分

        # 设置初始高度分布
        v_splitter.setSizes([700, 150])
        main_layout.addWidget(v_splitter)

        # --- 5. 连接信号与槽 ---
        self.panel_control.generate_network_clicked.connect(self.on_generate_network)
        self.panel_control.generate_request_clicked.connect(self.on_generate_request)
        self.panel_control.batch_start_clicked.connect(self.on_batch_start)
        self.panel_control.batch_stop_clicked.connect(self.on_batch_stop)
        # 模式切换
        self.panel_control.mode_changed.connect(self.on_mode_changed)
        # 数据导出
        self.panel_monitor.export_kpi_clicked.connect(self.on_export_kpi)
        self.panel_monitor.export_classification_clicked.connect(self.on_export_classification)
        self.panel_monitor.export_report_clicked.connect(self.on_export_report)

    def _setup_engine(self):  # 定义设置模拟引擎的方法
        # 构建回调
        cbs = EngineCallbacks(  # 创建引擎回调实例，并传入各种回调函数
            log=self._log,  # 日志回调函数
            update_topology=self._update_topology,  # 更新拓扑结构的回调函数
            update_node_labels=self._update_node_labels,  # 更新节点标签的回调函数
            highlight_path=self._highlight_path,  # 高亮路径的回调函数
            animate_flow=self._animate_flow,  # 动画显示流量的回调函数
            add_classification_row=self._add_classification_row,  # 添加分类结果行的回调函数
            update_kpis=self._update_kpis,  # 更新KPI的回调函数
            update_predictions=self._update_predictions,  # 更新预测结果的回调函数
            blink_nodes=self._blink_nodes,  # 触发节点闪烁的回调函数

        )
        self.engine = SimulationEngine(cbs)  # 创建模拟引擎实例，并传入回调接口
        # 让画布引用state
        self.canvas.state = self.engine.state  # 将模拟引擎的状态设置给网络画布

    def _setup_timers(self):  # 定义设置定时器的方法
        # KPI 刷新
        self.timer_kpi = QtCore.QTimer(self)  # 创建一个QTimer实例，用于定期更新KPI
        self.timer_kpi.setInterval(cfg.KPI_REFRESH_INTERVAL_MS)  # 设置KPI更新的时间间隔，单位为毫秒
        self.timer_kpi.timeout.connect(self._update_kpis)  # 连接定时器超时事件到更新KPI的方法
        self.timer_kpi.start()  # 启动KPI更新定时器
        # 预测刷新
        self.timer_pred = QtCore.QTimer(self)  # 创建一个QTimer实例，用于定期更新预测结果
        self.timer_pred.setInterval(int(cfg.PREDICT_INTERVAL_SEC * 1000))  # 设置预测更新的时间间隔，单位为毫秒
        self.timer_pred.timeout.connect(self._update_predictions)  # 连接定时器超时事件到更新预测结果的方法
        self.timer_pred.start()  # 启动预测更新定时器
        # 批量请求
        self.timer_batch = QtCore.QTimer(self)  # 创建一个QTimer实例，用于定期生成批量请求
        self.timer_batch.setInterval(cfg.BATCH_GEN_INTERVAL_MS)  # 设置批量请求生成的时间间隔，单位为毫秒
        self.timer_batch.timeout.connect(self._tick_batch)  # 连接定时器超时事件到生成批量请求的方法
        self._batch_rps = 0  # 初始化批量请求生成速率

    # --- 控制面板回调 ---
    def on_generate_network(self, n: int, cr: tuple, tr: tuple, br: tuple):  # 定义生成网络的回调函数
        self.engine.generate_network(n, cr, tr, br)  # 调用模拟引擎的生成网络方法

    def on_generate_request(self, app_key: str):  # 定义生成请求的回调函数
        req = self.engine.create_request(app_key)  # 调用模拟引擎的创建请求方法
        if req:  # 如果请求创建成功
            self.panel_control.add_request_row(req.req_id, req.arrival_time, req.expire_time, app_key,
                                               req.true_class)  # 在控制面板中添加请求行
            # 延迟处理请求，让用户能够看到队列中的请求
            QtCore.QTimer.singleShot(500, lambda: self._process_and_remove_request(req))

    def _add_classification_row(self, flow: TrafficFlow):  # 定义添加分类结果行的方法
        # 将分类结果写入右侧表
        self.panel_monitor.add_classification_row(flow.flow_id, flow.app_type, flow.true_class,
                                                  flow.predicted_class or "", flow.fec_value or 0.0)  # 在监控面板中添加分类结果行

    def _update_kpis(self):  # 定义更新KPI的方法
        kpi_values = self.engine.kpi_values()
        self.panel_monitor.set_kpis(kpi_values)  # 调用监控面板的设置KPI值方法，获取模拟引擎的KPI值
        # 记录KPI历史数据（用于导出）
        self.engine.kpi_history.append(kpi_values.copy())

    def on_batch_start(self, rps: int):  # 定义批量模拟启动的回调函数
        self._batch_rps = max(1, int(rps))  # 设置批量请求生成速率为传入值，最小为1
        self._batch_app_key = self.panel_control.cb_app.currentText()  # 获取控制面板中应用选择框的当前文本，作为批量请求的应用类型
        self.timer_batch.start()  # 启动批量请求生成定时器
        self._log(f"批量模拟已启动：{self._batch_rps} req/s", None)  # 记录批量模拟启动的日志信息

    def on_batch_stop(self):  # 定义批量模拟停止的回调函数
        self.timer_batch.stop()  # 停止批量请求生成定时器
        self._log("批量模拟已停止", None)  # 记录批量模拟停止的日志信息

    def _process_and_remove_request(self, req):  # 定义处理并移除请求的方法
        """处理请求并从队列中移除"""
        self.engine.process_request(req)  # 调用模拟引擎的处理请求方法
        self.panel_control.remove_request_row(req.req_id)  # 从控制面板中移除请求行

    def _tick_batch(self):  # 定义生成批量请求的定时器回调函数
        # 每秒生成 self._batch_rps 个请求
        for i in range(self._batch_rps):  # 根据批量请求生成速率循环生成请求
            req = self.engine.create_request(self._batch_app_key)  # 调用模拟引擎的创建请求方法
            if req:  # 如果请求创建成功
                self.panel_control.add_request_row(req.req_id, req.arrival_time, req.expire_time, self._batch_app_key,
                                                   req.true_class)  # 在控制面板中添加请求行
                # 延迟处理，让请求在队列中显示一段时间
                delay = 300 + i * 100  # 错开处理时间，避免同时处理
                QtCore.QTimer.singleShot(delay, lambda r=req: self._process_and_remove_request(r))

    # --- 引擎回调实现 ---
    def _log(self, text: str, color: Optional[str]):  # 定义日志记录方法
        if color:  # 如果有颜色参数
            self.txt_log.append(f"<span style='color:{color}'>" + text + "</span>")  # 使用指定颜色添加日志信息
        else:  # 如果没有颜色参数
            self.txt_log.append(text)  # 添加日志信息，不指定颜色

    def _update_topology(self):  # 定义更新拓扑结构的方法
        self.canvas.refresh_topology()  # 调用网络画布的刷新拓扑方法

    def _update_node_labels(self):  # 定义更新节点标签的方法
        self.canvas.refresh_node_labels()  # 调用网络画布的刷新节点标签方法

    def _highlight_path(self, path, color):  # 定义高亮路径的方法
        self.canvas.highlight_path(path, color)  # 调用网络画布的高亮路径方法

    def _animate_flow(self, path, color):  # 定义动画显示流量的方法
        self.canvas.animate_flow(path, color)  # 调用网络画布的动画显示流量方法

    def _update_predictions(self):  # 定义更新预测结果的方法
        load = self.engine.overall_load()  # 获取模拟引擎的整体负载
        chains = self.engine.active_chain_count()  # 获取模拟引擎的活动链路数量
        delay, loss = predict_performance(load, chains)  # 调用性能预测算法，获取延迟和损失值
        self.panel_monitor.set_predictions(delay, loss)  # 在监控面板中设置预测结果

    def _blink_nodes(self, node_ids: list):  # 定义触发节点闪烁的方法
        """触发节点闪烁动画"""
        self.canvas.blink_nodes(node_ids)  # 调用网络画布的节点闪烁方法，传入节点ID列表

    # --- 模式切换回调 ---
    # 修改on_mode_changed方法，添加更新控制面板显示的代码
    def on_mode_changed(self, mode: str):
        """处理模式切换"""
        self.engine.set_simulation_mode(mode)
        # 新增：更新控制面板上的模式显示
        if hasattr(self.panel_control, 'update_mode_display'):
            self.panel_control.update_mode_display(mode)
    
    # --- 新增：数据导出回调 ---
    def on_export_kpi(self):
        """导出KPI数据"""
        from sifa_simulator.utils.io_handler import export_kpi_csv
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存KPI数据", "", "CSV文件 (*.csv)"
        )
        if filename:
            try:
                kpi_data = self.engine.kpi_history
                if not kpi_data:
                    # 如果没有历史数据，至少导出当前KPI
                    kpi_data = [self.engine.kpi_values()]
                export_kpi_csv(filename, kpi_data)
                self._log(f"✅ KPI数据已导出到: {filename}", "green")
            except Exception as e:
                self._log(f"❌ 导出KPI数据失败: {str(e)}", "red")
    
    def on_export_classification(self):
        """导出分类结果"""
        from sifa_simulator.utils.io_handler import export_classification_csv
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存分类结果", "", "CSV文件 (*.csv)"
        )
        if filename:
            try:
                # 从表格中提取数据
                cls_data = []
                for row in range(self.panel_monitor.tbl_cls.rowCount()):
                    row_data = {
                        "flow_id": self.panel_monitor.tbl_cls.item(row, 0).text(),
                        "app_type": self.panel_monitor.tbl_cls.item(row, 1).text(),
                        "true_class": self.panel_monitor.tbl_cls.item(row, 2).text(),
                        "pred_class": self.panel_monitor.tbl_cls.item(row, 3).text(),
                        "fec_value": self.panel_monitor.tbl_cls.item(row, 4).text(),
                        "result": self.panel_monitor.tbl_cls.item(row, 5).text(),
                    }
                    cls_data.append(row_data)
                export_classification_csv(filename, cls_data)
                self._log(f"✅ 分类结果已导出到: {filename}", "green")
            except Exception as e:
                self._log(f"❌ 导出分类结果失败: {str(e)}", "red")
    
    def on_export_report(self):
        """导出统计报告"""
        from sifa_simulator.utils.io_handler import export_report_txt
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存统计报告", "", "文本文件 (*.txt)"
        )
        if filename:
            try:
                stats_data = {
                    "total_requests": self.engine.stats.total_requests,
                    "accepted": self.engine.stats.accepted,
                    "rejected": self.engine.stats.rejected,
                    "simulation_mode": self.engine.get_simulation_mode(),
                }
                export_report_txt(filename, self.engine.kpi_values(), stats_data)
                self._log(f"✅ 统计报告已导出到: {filename}", "green")
            except Exception as e:
                self._log(f"❌ 导出统计报告失败: {str(e)}", "red")
    
    def on_save_scene(self):
        """保存网络场景"""
        from sifa_simulator.utils.io_handler import save_scene
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存网络场景", "", "JSON文件 (*.json)"
        )
        if filename:
            try:
                save_scene(filename, self.engine.state)
                self._log(f"✅ 网络场景已保存到: {filename}", "green")
            except Exception as e:
                self._log(f"❌ 保存网络场景失败: {str(e)}", "red")
    
    def on_load_scene(self):
        """加载网络场景"""
        from sifa_simulator.utils.io_handler import load_scene
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "加载网络场景", "", "JSON文件 (*.json)"
        )
        if filename:
            try:
                new_state = load_scene(filename)
                self.engine.state = new_state
                self.canvas.state = new_state
                self._update_topology()
                self._update_node_labels()
                self._log(f"✅ 网络场景已从文件加载: {filename}", "green")
            except Exception as e:
                self._log(f"❌ 加载网络场景失败: {str(e)}", "red")
    
    def on_about(self):
        """显示关于对话框"""
        QtWidgets.QMessageBox.information(
            self,
            "关于 SIFA Simulator",
            "软件定义工业互联网流量管控模拟器\n\n"
            "版本: 2.0\n"
            "功能特性:\n"
            "- PSO粒子群资源编排算法（RDOTDR）\n"
            "- PLSAFC流量分类（概率模型）\n"
            "- GNN网络性能预测\n"
            "- A/B模式对比测试\n"
            "- 软时分（STD）时隙资源管理\n\n"
            "2024 © SIFA Research Group"
        )