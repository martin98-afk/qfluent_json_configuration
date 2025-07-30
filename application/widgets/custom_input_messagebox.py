"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: custom_input_messagebox.py
@time: 2025/7/21 09:16
@desc: 
"""
from qfluentwidgets import MessageBoxBase, SubtitleLabel, LineEdit


class CustomMessageBox(MessageBoxBase):
    """ Custom message box """

    def __init__(self, title: str, placeholder: str, currenttext: str=None, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title)
        self.LineEdit = LineEdit()

        self.LineEdit.setPlaceholderText(placeholder)
        if currenttext:
            self.LineEdit.setText(currenttext)
        self.LineEdit.setClearButtonEnabled(True)

        # 将组件添加到布局中
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.LineEdit)
        self.LineEdit.returnPressed.connect(self.accept)

        # 设置对话框的最小宽度
        self.widget.setMinimumWidth(350)

    def get_text(self):
        return self.LineEdit.text()