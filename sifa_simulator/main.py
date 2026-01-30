
"""
应用程序入口：初始化并运行PyQt应用。
"""
# 启用注解类型支持
from __future__ import annotations

# 导入系统模块，用于处理命令行参数和程序退出
import sys
# 导入PyQt6的QtWidgets模块，用于创建GUI组件
from PyQt6 import QtWidgets

# 导入自定义的主窗口类
from sifa_simulator.ui.main_window import MainWindow


def main():
    # 创建QApplication实例，这是所有PyQt应用的起点，传递命令行参数
    app = QtWidgets.QApplication(sys.argv)

    # 设置应用程序图标
    try:
        # 导入路径处理模块和图标处理模块
        from pathlib import Path
        from PyQt6.QtGui import QIcon
        # 构造图标文件路径，指向项目根目录下的img.png文件
        icon_path = Path(__file__).parent.parent / "img.png"
        # 检查图标文件是否存在
        if icon_path.exists():
            # 设置应用程序图标
            app.setWindowIcon(QIcon(str(icon_path)))
    # 捕获设置图标过程中可能出现的异常
    except Exception as e:
        # 打印错误信息
        print(f"加载应用图标失败: {e}")

    # 创建主窗口实例
    win = MainWindow()
    # 显示主窗口
    win.show()
    # 启动事件循环，等待用户交互，并在窗口关闭时退出程序
    sys.exit(app.exec())


# 判断是否为直接运行此脚本（而非被导入）
if __name__ == "__main__":
    # 调用main函数启动应用
    main()