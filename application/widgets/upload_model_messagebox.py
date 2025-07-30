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


class UploadModelMessageBox(MessageBoxBase):
    """ Custom message box """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("上传模型")
        # 选择上传文件行
        file_layout = QHBoxLayout()
        file_label = QLabel("选择模型文件：")
        self.file_line_edit = LineEdit()
        self.file_line_edit.setReadOnly(True)
        browse_button = QPushButton()
        browse_button.setIcon(get_icon("打开文件"))
        browse_button.setStyleSheet(get_button_style_sheet())
        def browse_file():
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择模型文件", resource_path("./预制模型"), "Model Files (*.zip)"
            )
            if file_path:
                self.file_line_edit.setText(file_path)

        browse_button.clicked.connect(browse_file)
        file_layout.addWidget(file_label)
        file_layout.addWidget(self.file_line_edit)
        file_layout.addWidget(browse_button)
        # 选择运行环境行
        env_layout = QHBoxLayout()
        env_label = QLabel("选择运行环境：")
        self.env_combo = ComboBox()
        self.env_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        env_list = parent.config.api_tools.get("di_env").call()
        # 示例运行环境，可以替换成实际调用接口返回的内容
        self.env_combo.addItems([item[0] for item in env_list])
        env_layout.addWidget(env_label)
        env_layout.addWidget(self.env_combo)

        # 将组件添加到布局中
        self.viewLayout.addLayout(file_layout)
        self.viewLayout.addLayout(env_layout)

        # 设置对话框的最小宽度
        self.widget.setMinimumWidth(350)

    def get_text(self):
        return self.file_line_edit.text(), self.env_combo.currentText()