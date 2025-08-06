"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: custom_input_messagebox.py
@time: 2025/7/21 09:16
@desc: 
"""
from PyQt5.QtWidgets import QHBoxLayout, QLabel
from qfluentwidgets import MessageBoxBase, SubtitleLabel, LineEdit, ComboBox


class CopyModelMessageBox(MessageBoxBase):
    """ Custom message box """

    def __init__(self, model_names: list, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("复制模型")
        # 选择上传文件行
        model_layout = QHBoxLayout()
        model_label = QLabel("选择要复制的模型：")
        self.model_combo = ComboBox()
        self.model_combo.setMaxVisibleItems(10)
        self.model_combo.addItems([item[0] for item in model_names])
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        # 选择运行环境行
        new_model_layout = QHBoxLayout()
        new_model_label = QLabel("输入新模型名称：")
        self.line_edit = LineEdit()
        # 示例运行环境，可以替换成实际调用接口返回的内容
        new_model_layout.addWidget(new_model_label)
        new_model_layout.addWidget(self.line_edit)

        # 将组件添加到布局中
        self.viewLayout.addLayout(model_layout)
        self.viewLayout.addLayout(new_model_layout)

        # 设置对话框的最小宽度
        self.widget.setMinimumWidth(350)

    def get_text(self):
        return self.model_combo.currentIndex(), self.line_edit.text()