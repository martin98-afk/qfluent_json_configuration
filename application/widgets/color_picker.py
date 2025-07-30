"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: color_picker.py
@time: 2025/7/30 09:49
@desc: 
"""
import sys
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QGridLayout, QToolButton, QMenu, QWidgetAction, QVBoxLayout
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, pyqtSignal


class ColorPicker(QWidget):
    """4x4网格颜色选择器，最后一个位置是"更多"按钮"""
    colorSelected = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 100)

        # 预定义15种颜色（留一个位置给"更多"按钮）
        self.colors = [
            "#FF0000", "#00FF00", "#0000FF", "#FFFF00",
            "#FF00FF", "#00FFFF", "#800000", "#008000",
            "#000080", "#808000", "#800080", "#008080",
            "#C0C0C0", "#808080", "#9999FF"
        ]

        # 使用网格布局（4x4）
        layout = QGridLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        # 添加15种颜色
        for i, color_hex in enumerate(self.colors):
            row = i // 4
            col = i % 4
            self._add_color_button(layout, color_hex, row, col)

        # 添加"更多"按钮在最后一个位置 (3, 3)
        self._add_more_button(layout, 3, 3)

    def _add_color_button(self, layout, color_hex, row, col):
        """添加颜色按钮到网格"""
        color_btn = QWidget()
        color_btn.setFixedSize(20, 20)
        color_btn.setStyleSheet(f"background-color: {color_hex}; border-radius: 3px;")
        color_btn.mousePressEvent = lambda e, c=QColor(color_hex): self._handle_color_click(c)
        layout.addWidget(color_btn, row, col)

    def _handle_color_click(self, color):
        """处理颜色点击事件并关闭菜单"""
        self.colorSelected.emit(color)
        # 尝试关闭父菜单
        parent = self.parent()
        while parent and not isinstance(parent, QMenu):
            parent = parent.parent()
        if parent and isinstance(parent, QMenu):
            parent.close()

    def _add_more_button(self, layout, row, col):
        """添加"更多"按钮到指定位置"""
        more_btn = QWidget()
        more_btn.setFixedSize(20, 20)
        more_btn.setStyleSheet("background-color: white; border: 1px solid #999; border-radius: 3px;")
        more_btn.mousePressEvent = self.open_full_dialog
        layout.addWidget(more_btn, row, col)

    def open_full_dialog(self, event):
        from PyQt5.QtWidgets import QColorDialog
        dialog = QColorDialog(self)
        dialog.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        dialog.setCurrentColor(QColor(self.colors[0]))

        def handle_color_selected(color):
            self.colorSelected.emit(color)
            # 尝试关闭父菜单
            parent = self.parent()
            while parent and not isinstance(parent, QMenu):
                parent = parent.parent()
            if parent and isinstance(parent, QMenu):
                parent.close()
            dialog.close()

        dialog.currentColorChanged.connect(handle_color_selected)
        dialog.show()
        dialog.move(self.mapToGlobal(self.rect().bottomLeft()))


class ColorComboBox(QToolButton):
    """精简版下拉颜色选择按钮（无文字，仅颜色块）"""
    colorChanged = pyqtSignal(QColor)

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 25)  # 与色块大小一致
        self.setPopupMode(QToolButton.InstantPopup)
        self.setColor(QColor(color))  # 默认青色

        # 创建菜单
        self.menu = QMenu(self)
        self.color_picker = ColorPicker()
        self.color_picker.colorSelected.connect(self.setColor)

        # 将颜色选择器放入菜单
        action = QWidgetAction(self)
        action.setDefaultWidget(self.color_picker)
        self.menu.addAction(action)
        self.setMenu(self.menu)

    def setColor(self, color):
        """设置按钮颜色（仅背景，无文字）"""
        self._color = color
        # 更新样式 - 仅设置背景颜色，无文字
        self.setStyleSheet(f"""
            QToolButton {{
                background-color: {color.name()};
                border: 1px solid #555;
                border-radius: 3px;
            }}
            QToolButton:hover {{
                border: 1px solid #333;
            }}
        """)

        self.colorChanged.emit(color)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 创建主窗口
    window = QWidget()
    window.setWindowTitle("下拉颜色选择器演示")
    window.setGeometry(100, 100, 300, 150)

    # 创建布局
    layout = QVBoxLayout(window)
    layout.setContentsMargins(20, 20, 20, 20)

    # 添加说明
    layout.addWidget(QWidget())  # 顶部空白

    # 创建颜色选择器
    color_combo = ColorComboBox()
    color_combo.colorChanged.connect(lambda color: print(f"已选择颜色: {color.name()}"))

    layout.addWidget(color_combo)
    layout.addStretch()

    window.show()

    sys.exit(app.exec_())