"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: image_desc_flyout.py
@time: 2025/9/17 11:03
@desc: 
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QLabel
from qfluentwidgets import FlyoutViewBase, BodyLabel


class ImageDescFlyoutView(FlyoutViewBase):
    def __init__(self, desc_text: str, image_path: str = None, image_size=(60, 60), parent=None):
        super().__init__(parent)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setSpacing(10)
        self.vBoxLayout.setContentsMargins(16, 14, 16, 14)

        # 创建内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        # 创建文字标签
        self.text_label = BodyLabel()
        self.text_label.setTextFormat(Qt.RichText)
        self.text_label.setText(desc_text)
        self.text_label.setWordWrap(True)
        self.text_label.setMaximumWidth(480)
        content_layout.addWidget(self.text_label)

        # 如果有图片，创建图片标签
        if image_path:
            self.image_label = QLabel()
            pixmap = QPixmap(image_path)

            # ✅ 设定固定大小，保持比例
            scaled_pixmap = pixmap.scaled(
                image_size[0], image_size[1],
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setAlignment(Qt.AlignCenter)
            content_layout.addWidget(self.image_label)

        self.vBoxLayout.addWidget(content_widget)

    def paintEvent(self, e):
        pass  # 不绘制默认背景
