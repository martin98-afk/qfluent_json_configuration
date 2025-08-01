"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: component_log_message_box.py
@time: 2025/8/1 09:56
@desc: 
"""
from PyQt5.QtCore import Qt
from qfluentwidgets import MessageBoxBase, SubtitleLabel, PlainTextEdit, PrimaryPushButton

class LogMessageBox(MessageBoxBase):
    def __init__(self, log_content, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('模型日志', self)
        self.logTextEdit = PlainTextEdit(self)
        self.logTextEdit.setReadOnly(True)
        self.logTextEdit.setPlainText(log_content)
        self.logTextEdit.setMinimumHeight(int(0.7 * parent.window_height))
        self.logTextEdit.setMinimumWidth(900) # 设置最小宽度，避免太窄

        # 将内容控件添加到布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.logTextEdit)

        # 创建按钮
        self.yesButton.hide()
        self.cancelButton.setText('关闭')