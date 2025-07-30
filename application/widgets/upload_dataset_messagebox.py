"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: custom_input_messagebox.py
@time: 2025/7/21 09:16
@desc: 
"""
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QFileDialog, QSizePolicy, QPushButton
from qfluentwidgets import MessageBoxBase, SubtitleLabel, LineEdit, PushButton, ComboBox

from application.utils.utils import get_icon, resource_path, get_button_style_sheet


class UploadDatasetMessageBox(MessageBoxBase):
    """ Custom message box """

    def __init__(self, upload_paths: list[str], parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("选择数据集上传目标组件")
        # 选择上传文件行
        env_label = QLabel("请选择配置文件上传数据集后同步的目标组件：")
        self.env_combo = ComboBox()
        self.env_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # 示例运行环境，可以替换成实际调用接口返回的内容
        self.env_combo.addItems(upload_paths)
        self.viewLayout.addWidget(env_label)
        self.viewLayout.addWidget(self.env_combo)

        # 设置对话框的最小宽度
        self.widget.setMinimumWidth(350)

    def get_text(self):
        return self.env_combo.currentText()