# -*- coding: utf-8 -*-
"""
网络拓扑可视化画布（pyqtgraph）
- 绘制节点与链路
- 显示节点标签与资源利用率颜色
- 鼠标悬停链路显示带宽
- 高亮服务链路径，并在路径上动画小圆点表示流量
- 支持节点闪烁动画效果
"""
from __future__ import annotations  # 启用前向引用，允许类名在定义前出现

import sys
from typing import Dict, List, Tuple, Set  # 引入常用容器类型提示

from PyQt6 import QtCore, QtGui, QtWidgets  # Qt6 核心 GUI 部件
import pyqtgraph as pg  # 高性能绘图库
from PyQt6.QtCore import QTimer


class MockNode:
    """
    Mock 网络节点数据结构，用于演示和测试。
    """
    def __init__(self, id, x, y, compute=100, timeslot=100):
        self.id = id
        self.x = x
        self.y = y
        self.total_compute = compute
        self.used_compute = 0
        self.total_timeslot = timeslot
        self.used_timeslot = 0

    def utilization_color(self) -> str:
        util_c = self.used_compute / max(1, self.total_compute)
        util_t = self.used_timeslot / max(1, self.total_timeslot)
        util = max(util_c, util_t)
        if util > 0.95: return 'red'
        if util > 0.80: return 'yellow'
        return 'green'


class MockLink:
    """
    Mock 网络链路数据结构，用于演示和测试。
    """
    def __init__(self, src, dst, bandwidth=1000):
        self.src = src
        self.dst = dst
        self.bandwidth = bandwidth


class MockState:
    """
    Mock 网络状态数据结构，用于演示和测试。
    """
    def __init__(self):
        self.nodes: Dict[int, MockNode] = {}
        self.links: List[MockLink] = []


NetworkState = MockState





class MinimapOverlay(pg.GraphicsLayoutWidget):
    """
    可拖动的小地图预览窗口
    """

    def __init__(self, main_plot_item: pg.PlotItem, parent=None):
        super().__init__(parent=parent)
        self.main_plot_item = main_plot_item  # 保存主画布 PlotItem 的引用
        self._drag_start_pos: QtCore.QPoint | None = None  # 用于拖动

        # --- 基础设置 ---
        self.setFixedSize(150, 150)  # 固定大小 150x150
        self.move(10, 10)  # 初始位置
        self.setStyleSheet(
            "background-color: rgba(14, 99, 156, 0.85); "
            "border: 2px solid rgba(14, 99, 156, 0.8); "
            "border-radius: 4px;"
        )  # 半透明深紫背景 + 紫色边框 + 圆角


        self.minimap_plot = self.addPlot(row=0, col=0)
        self.minimap_plot.hideAxis('bottom')
        self.minimap_plot.hideAxis('left')
        self.minimap_plot.setMouseEnabled(x=False, y=False)  # 禁止小地图内部拖动
        self.minimap_plot.setMenuEnabled(False)
        self.minimap_plot.getViewBox().setBackgroundColor(None)  # 背景透明

        # 隐藏边框和内边距
        self.minimap_plot.setContentsMargins(0, 0, 0, 0)

        # 小地图中的节点和链路
        self._minimap_nodes = pg.ScatterPlotItem(size=6, brush=pg.mkBrush(14, 99, 156))
        self._minimap_links: List[pg.PlotDataItem] = []
        self.minimap_plot.addItem(self._minimap_nodes)

        # 视口指示器（显示主画布的可见区域）
        self._viewport_rect = QtWidgets.QGraphicsRectItem()
        self._viewport_rect.setPen(QtGui.QPen(QtGui.QColor(14, 99, 156, 200), 0.8))
        self._viewport_rect.setBrush(QtGui.QBrush(QtGui.QColor(14, 99, 156, 20)))
        self.minimap_plot.addItem(self._viewport_rect)

        # --- 信号连接 ---
        # 连接主视图的信号以更新视口指示器
        self.main_plot_item.sigRangeChanged.connect(self.update_viewport_indicator)

    # --- 拖动功能 ---
    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """鼠标按下，准备拖动"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()  # 记录在小地图内的点击位置
            event.accept()
        else:
            self._drag_start_pos = None
            event.ignore()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """鼠标移动，更新小地图位置"""
        if self._drag_start_pos and (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
            delta = event.pos() - self._drag_start_pos
            self.move(self.pos() + delta)  # 移动小地图
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        """鼠标释放，停止拖动"""
        self._drag_start_pos = None
        event.accept()

    # --- 拓扑更新 ---
    def update_topology(self, state: NetworkState):
        """(重构) 完整更新小地图（链路+节点+视口矩形）"""
        if not state.nodes:
            return

        # 清除旧链路
        for link_item in self._minimap_links:
            self.minimap_plot.removeItem(link_item)
        self._minimap_links.clear()

        # 绘制小地图链路
        for link in state.links:
            a = state.nodes[link.src]
            b = state.nodes[link.dst]
            link_plot = pg.PlotDataItem(
                [a.x, b.x], [a.y, b.y],
                pen=pg.mkPen(color=(14, 99, 156, 200), width=1.5)
            )
            self.minimap_plot.addItem(link_plot)
            self._minimap_links.append(link_plot)

        # 绘制小地图节点
        self.update_nodes(state)

        # 自动调整小地图范围以显示所有节点
        if state.nodes:
            xs = [n.x for n in state.nodes.values()]
            ys = [n.y for n in state.nodes.values()]
            margin = 5  # 留边
            self.minimap_plot.setXRange(min(xs) - margin, max(xs) + margin, padding=0)
            self.minimap_plot.setYRange(min(ys) - margin, max(ys) + margin, padding=0)

        # 更新视口指示器
        self.update_viewport_indicator()

    def update_nodes(self, state: NetworkState):
        """(重构) 仅更新小地图中的节点颜色"""
        if not hasattr(self, '_minimap_nodes'):
            return

        mini_spots = []
        for nid, node in state.nodes.items():
            color = node.utilization_color()
            if color == 'red':
                brush = pg.mkBrush(255, 82, 82)
            elif color == 'yellow':
                brush = pg.mkBrush(255, 193, 7)
            else:
                brush = pg.mkBrush(0,82,92)

            mini_spots.append({
                "pos": (node.x, node.y),
                "brush": brush,
                "size": 6
            })
        self._minimap_nodes.setData(mini_spots)

    def update_viewport_indicator(self):
        """(重构) 更新视口指示器（主画布可见区域矩形）"""
        view_range = self.main_plot_item.viewRange()
        x_range, y_range = view_range[0], view_range[1]

        x_min, x_max = x_range
        y_min, y_max = y_range
        width = x_max - x_min
        height = y_max - y_min

        self._viewport_rect.setRect(x_min, y_min, width, height)


class NetworkCanvas(pg.PlotWidget):
    """网络拓扑可视化画布主类"""

    def __init__(self, state: NetworkState, parent=None):
        super().__init__(parent=parent)
        self.state = state

        # --- (新增) 优化主画布外观 ---
        self.getPlotItem().hideAxis('left')  # 隐藏左侧 Y 轴
        self.getPlotItem().hideAxis('bottom')  # 隐藏底部 X 轴

        self.setBackground(pg.mkColor(1,1,1))  # 设置深色背景
        self.setAntialiasing(True)  # 开启抗锯齿

        # --- 绘图项 ---
        self._node_scatter = pg.ScatterPlotItem(size=10, brush=pg.mkBrush(100, 200, 120))
        self._node_scatter.setZValue(10)
        self._node_labels: Dict[int, pg.TextItem] = {}
        self.addItem(self._node_scatter)

        self._link_items: List[QtWidgets.QGraphicsLineItem] = []
        self._highlight_items: List[QtWidgets.QGraphicsLineItem] = []

        # --- (重构) 创建小地图 ---
        # MinimapOverlay 现在是 self 的子控件，可以被拖动
        self.minimap = MinimapOverlay(self.getPlotItem(), parent=self)

        # --- 动画点 ---
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.setInterval(40)  # 约 25 fps
        self._anim_path: List[Tuple[float, float]] = []
        self._anim_pos = 0.0
        self._anim_color = (0, 150, 255)
        self._anim_spot = pg.ScatterPlotItem(size=12, brush=pg.mkBrush(*self._anim_color))
        self.addItem(self._anim_spot)
        self._anim_timer.timeout.connect(self._tick_anim)

        # --- 节点闪烁 ---
        self._blink_timer = QtCore.QTimer(self)
        self._blink_timer.setInterval(100)  # 闪烁频率
        self._blink_nodes: Set[int] = set()
        self._blink_count = 0
        self._blink_state = False
        self._blink_timer.timeout.connect(self._tick_blink)

    # --- 绘制拓扑 ---
    def refresh_topology(self):
        """完整刷新拓扑（链路+节点+标签+小地图）"""

        # 清除旧链路
        scene = self.getPlotItem().vb.scene()
        if scene:
            for link_item in self._link_items:
                scene.removeItem(link_item)
        self._link_items.clear()

        # 绘制链路（新增）
        for link in self.state.links:
            src_node = self.state.nodes.get(link.src)
            dst_node = self.state.nodes.get(link.dst)
            if src_node and dst_node:
                line = QtWidgets.QGraphicsLineItem(src_node.x, src_node.y, dst_node.x, dst_node.y)
                pen = QtGui.QPen(QtGui.QColor(100, 150, 200), 0.07)  # 线条宽度从2.0改为1.0
                pen.setStyle(QtCore.Qt.PenStyle.DashLine)  # 添加虚线样式
                pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
                line.setPen(pen)
                line.setZValue(0)
                line.setToolTip(f"链路: N{link.src}→N{link.dst} (带宽: {link.bandwidth})")
                self.addItem(line)
                self._link_items.append(line)

        # 绘制节点
        self._update_nodes()

        # 标签
        for ti in self._node_labels.values():
            self.removeItem(ti)
        self._node_labels.clear()

        for nid, node in self.state.nodes.items():
            label_text = self._create_node_label(node)
            text = pg.TextItem(anchor=(0.5, -0.3), color=(224, 212, 247))
            text.setHtml(
                f'<div style="background-color: rgba(1, 1, 1, 0.3); '
                f'padding: 6px 8px; border-radius: 5px; '
                f'border: 1px solid rgba(123, 82, 171, 0.8);">'
                f'<p style="color: #e0d4f7; margin: 0; line-height: 1.2; '
                f'font-size: 6pt; text-align: center; white-space: pre;">{label_text}</p>'
                f'</div>'
            )
            text.setPos(node.x, node.y)
            text.setZValue(5)
            self._node_labels[nid] = text
            self.addItem(text)

        # 更新小地图（完整拓扑更新）
        if hasattr(self.minimap, 'update_topology'):
            self.minimap.update_topology(self.state)
        # 手动更新一次视口，确保初始加载正确
        self.minimap.update_viewport_indicator()

    def _create_node_label(self, node) -> str:
        """生成节点标签文本（CPU/时隙利用率）"""
        util_c = node.used_compute / max(1, node.total_compute) * 100
        util_t = node.used_timeslot / max(1, node.total_timeslot) * 100
        return (f"节点 {node.id}\n"
                f"C: {node.used_compute}/{node.total_compute} ({util_c:.0f}%)\n"
                f"T: {node.used_timeslot}/{node.total_timeslot} ({util_t:.0f}%)")

    def _update_nodes(self):
        """根据利用率更新节点颜色"""
        spots = []
        for nid, node in self.state.nodes.items():
            color = node.utilization_color()
            if color == 'red':
                brush = pg.mkBrush(255, 82, 82)
            elif color == 'yellow':
                brush = pg.mkBrush(255, 193, 7)
            else:
                brush = pg.mkBrush(0,82,92)

            # 检查是否在闪烁状态
            if nid in self._blink_nodes and self._blink_state:
                brush = pg.mkBrush(183, 148, 246)  # 亮紫色

            spots.append({
                "pos": (node.x, node.y),
                "data": nid,
                "brush": brush,
                "size": 22
            })
        self._node_scatter.setData(spots)

    def refresh_node_labels(self):
        """实时更新节点标签和颜色"""
        for nid, node in self.state.nodes.items():
            if nid in self._node_labels:
                label_text = self._create_node_label(node)
                self._node_labels[nid].setHtml(
                    f'<div style="background-color: rgba(1, 1, 1, 0.3); '
                    f'padding: 6px 8px; border-radius: 5px; '
                    f'border: 1px solid rgba(123, 82, 171, 0.8);">'
                    f'<p style="color: #e0d4f7; margin: 0; line-height: 1.2; '
                    f'font-size: 6pt; text-align: center; white-space: pre;">{label_text}</p>'
                    f'</div>'
                )
        self._update_nodes()

        # (重构) 同步更新小地图的节点颜色
        self.minimap.update_nodes(self.state)

    # --- 高亮路径 & 动画 ---
    def highlight_path(self, path: List[int], color: Tuple[int, int, int]):
        """用指定颜色高亮服务链路径（带发光效果）"""
        scene = self.getPlotItem().vb.scene()
        if not scene:
            return

        for a, b in zip(path[:-1], path[1:]):
            try:
                na = self.state.nodes[a]
                nb = self.state.nodes[b]
            except KeyError:
                continue  # 节点不存在

            # 外层发光效果
            glow_line = QtWidgets.QGraphicsLineItem(na.x, na.y, nb.x, nb.y)
            glow_pen = QtGui.QPen(QtGui.QColor(*color, 80), 8.0)
            glow_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            glow_line.setPen(glow_pen)
            glow_line.setZValue(1)
            scene.addItem(glow_line)
            self._highlight_items.append(glow_line)

            # 主线条
            line = QtWidgets.QGraphicsLineItem(na.x, na.y, nb.x, nb.y)
            pen = QtGui.QPen(QtGui.QColor(*color), 4.0)
            pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            line.setPen(pen)
            line.setZValue(2)
            line.setToolTip(f"服务链路径: N{a}→N{b}")
            scene.addItem(line)
            self._highlight_items.append(line)

    def animate_flow(self, path: List[int], color: Tuple[int, int, int]):
        """在路径上显示流量动画（小圆点移动）"""
        pts: List[Tuple[float, float]] = []
        try:
            for nid in path:
                n = self.state.nodes[nid]
                pts.append((n.x, n.y))
        except KeyError:
            print(f"动画路径节点 {nid} 不存在, 停止动画。")
            return

        self._anim_path = pts
        self._anim_pos = 0.0
        self._anim_color = color
        self._anim_spot.setBrush(pg.mkBrush(*color))
        self._anim_spot.setSize(14)
        self._anim_timer.start()

    def _tick_anim(self):
        """流量动画帧更新（每 40 ms 调用）"""
        if len(self._anim_path) < 2:
            self._anim_timer.stop()
            return
        segs = len(self._anim_path) - 1
        self._anim_pos += 0.08  # 步进速度
        if self._anim_pos >= segs:
            self._anim_timer.stop()
            self._anim_spot.setData([], [])  # 清除动画点
            return
        i = int(self._anim_pos)
        t = self._anim_pos - i
        x0, y0 = self._anim_path[i]
        x1, y1 = self._anim_path[i + 1]
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        self._anim_spot.setData([x], [y])

    def blink_nodes(self, node_ids: List[int], duration_ms: int = 1000):
        """让指定节点闪烁（资源编排成功时调用）"""
        self._blink_nodes = set(node_ids)
        self._blink_count = duration_ms // 100  # 闪烁次数
        self._blink_state = False
        self._blink_timer.start()

    def _tick_blink(self):
        """闪烁动画帧更新（每 100 ms 调用）"""
        if self._blink_count <= 0:
            self._blink_timer.stop()
            self._blink_nodes.clear()
            self._update_nodes()  # 恢复正常颜色
            return

        self._blink_state = not self._blink_state  # 切换亮暗
        self._blink_count -= 1
        self._update_nodes()  # 刷新节点颜色

    # --- (新增) 动画演示 ---
    def run_animation_demo(self):
        """(新) 运行一个演示，展示路径高亮、流量和闪烁动画"""
        print("开始运行动画演示...")
        if not self.state.nodes:
            print("演示失败：拓扑中没有节点。")
            return

        path_to_animate = []
        if len(self.state.nodes) >= 3:
            # 随便找三个节点
            path_to_animate = list(self.state.nodes.keys())[:3]
        elif self.state.links:
            # 至少找一条链路
            link = self.state.links[0]
            path_to_animate = [link.src, link.dst]

        if not path_to_animate:
            print("演示失败：无法找到用于演示的路径。")
            return

        # 1. 高亮
        highlight_color = (0, 255, 150)  # 亮绿色
        print(f"演示高亮路径: {path_to_animate}")
        self.highlight_path(path_to_animate, highlight_color)

        # 2. 流量
        flow_color = (0, 150, 255)  # 亮蓝色
        print(f"演示流量动画: {path_to_animate}")
        self.animate_flow(path_to_animate, flow_color)

        # 3. 闪烁
        nodes_to_blink = path_to_animate
        print(f"演示节点闪烁: {nodes_to_blink}")
        self.blink_nodes(nodes_to_blink, duration_ms=2000)  # 闪烁 2 秒

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    print("=" * 60)
    print("网络画布测试 (network_canvas.py)")
    print("=" * 60)

    app = QApplication(sys.argv)
    app.setApplicationName("SIFA网络画布")
    app.setOrganizationName("SIFA Project")

    # 创建测试网络状态
    state = MockState()
    for i in range(1, 7):  # 修改为6个节点
        import random
        node = MockNode(
            id=i,
            x=i * 20.0,
            y=random.uniform(20, 80),
            compute=random.randint(40, 80),
            timeslot=random.randint(80, 150)

        )
        state.nodes[i] = node
    # 添加链路
    for i in range(1, 6):  # 修改为5条链路以适应6个节点
        state.links.append(MockLink(i, i + 1, 100.0))

    canvas = NetworkCanvas(state)
    canvas.refresh_topology()  # 必须调用此方法来绘制节点和链路

    canvas.setWindowTitle("SIFA网络拓扑可视化")
    canvas.resize(800, 600)
    canvas.show()

    # 测试路径高亮
    test_path = [1, 2, 3, 4]
    test_color = (255, 0, 0)
    canvas.highlight_path(test_path, test_color)

    # 测试动画
    QTimer.singleShot(1000, lambda: canvas.animate_flow(test_path, (0, 255, 0)))

    print("✅ 网络画布已打开")
    print("   - 显示6个节点")  # 更新打印信息
    print("   - 高亮路径: 1->2->3->4")
    print("   - 1秒后开始流量动画")
    sys.exit(app.exec())




