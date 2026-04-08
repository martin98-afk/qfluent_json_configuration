# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from qfluentwidgets import CardWidget, isDarkTheme
from application.utils.utils import get_unified_font


class TodoFloatingWidget(CardWidget):
    """TODO 悬浮框组件"""

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._todo_list = []
        self._setup_ui()

    def _setup_ui(self):
        is_dark = isDarkTheme()
        self.setSizePolicy(1, 0)
        if is_dark:
            card_bg = "rgba(40, 40, 45, 252)"
        else:
            card_bg = "rgba(240, 240, 245, 252)"
        self.setStyleSheet(f"""
            CardWidget {{
                background-color: {card_bg};
                border: 1px solid #6366f1;
                border-radius: 10px;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(10)

        title_icon = QLabel("📋", self)
        title_icon.setFont(get_unified_font(14))

        title = QLabel("待办事项", self)
        title.setFont(get_unified_font(11, True))
        title_color = "#f0f0f0" if is_dark else "#333333"
        title.setStyleSheet(f"color: {title_color};")

        self.progress_label = QLabel("", self)
        self.progress_label.setFont(get_unified_font(10, True))
        self.progress_label.setStyleSheet("color: #818cf8;")

        header.addWidget(title_icon)
        header.addWidget(title)
        header.addWidget(self.progress_label)
        header.addStretch()

        close_btn = QPushButton("✕", self)
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        if is_dark:
            close_btn_bg = "rgba(255, 255, 255, 0.1)"
            close_btn_color = "#a0a0a0"
            close_btn_hover_bg = "rgba(255, 255, 255, 0.2)"
            close_btn_hover_color = "#ffffff"
        else:
            close_btn_bg = "rgba(0, 0, 0, 0.08)"
            close_btn_color = "#666666"
            close_btn_hover_bg = "rgba(0, 0, 0, 0.15)"
            close_btn_hover_color = "#333333"
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {close_btn_bg};
                color: {close_btn_color};
                border: none;
                border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {close_btn_hover_bg};
                color: {close_btn_hover_color};
            }}
        """)
        close_btn.clicked.connect(self._on_close)
        header.addWidget(close_btn)

        self.content_label = QLabel("暂无待办", self)
        self.content_label.setFont(get_unified_font(10))
        content_color = "#b0b0b0" if is_dark else "#666666"
        self.content_label.setStyleSheet(f"color: {content_color};")
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.content_label.setAlignment(Qt.AlignTop)

        main_layout.addLayout(header)
        main_layout.addWidget(self.content_label, 1)

    def _on_close(self):
        self.setVisible(False)
        self.closed.emit()

    def update_todos(self, todos):
        """更新 TODO 列表显示"""
        self._todo_list = todos or []

        if not self._todo_list:
            self.setVisible(False)
            return

        self.setVisible(True)

        is_dark = isDarkTheme()
        lines = []
        completed = 0
        in_progress = 0
        for todo in self._todo_list:
            status = todo.get("status", "")
            content = todo.get("content", "")
            priority = todo.get("priority", "medium")

            if status == "completed":
                completed += 1
                status_icon = "✓"
            elif status == "in_progress":
                in_progress += 1
                status_icon = "▶"
            else:
                status_icon = "○"

            priority_colors = {"high": "#f87171", "medium": "#fbbf24", "low": "#34d399"}
            priority_color = priority_colors.get(priority, "#fbbf24")

            priority_labels = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            priority_icon = priority_labels.get(priority, "🟡")

            if status == "completed":
                content_style = (
                    "color: #808080; text-decoration: line-through;"
                    if is_dark
                    else "color: #999999; text-decoration: line-through;"
                )
            elif status == "in_progress":
                content_style = (
                    "color: #60a5fa; font-weight: bold;"
                    if is_dark
                    else "color: #0078d4; font-weight: bold;"
                )
            else:
                content_style = "color: #e0e0e0;" if is_dark else "color: #333333;"

            lines.append(
                f'<span style="color: #818cf8; font-weight: bold;">{status_icon}</span> '
                f'<span style="color: {priority_color};">{priority_icon}</span> '
                f'<span style="{content_style}">{content}</span>'
            )

        total = len(self._todo_list)
        done_count = completed + in_progress
        if done_count == total and done_count > 0:
            if in_progress > 0:
                progress_text = f"⏳ {in_progress}进行中 + {completed}完成"
                self.progress_label.setStyleSheet(
                    "color: #60a5fa; font-weight: bold;"
                    if is_dark
                    else "color: #0078d4; font-weight: bold;"
                )
            else:
                progress_text = f"🎉 {completed}/{total} 全部完成"
                self.progress_label.setStyleSheet(
                    "color: #34d399; font-weight: bold;"
                    if is_dark
                    else "color: #28a745; font-weight: bold;"
                )
        else:
            progress_text = f"{completed}完成/{in_progress}进行中/{total}"
            self.progress_label.setStyleSheet("color: #818cf8; font-weight: bold;")

        self.progress_label.setText(progress_text)
        self.content_label.setText("<br>".join(lines))

    def clear(self):
        """清空 TODO 显示"""
        self._todo_list = []
        self.setVisible(False)
