from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel
)
from qfluentwidgets import ComboBox, PushButton, MessageBoxBase, SubtitleLabel

from application.utils.utils import get_icon


class LoadHistoryDialog(MessageBoxBase):
    def __init__(self, file_map, filenames, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("选择历史记录")
        self.yesButton.hide()
        self.cancelButton.hide()

        self.file_map = file_map
        self.selected_file = None
        self.selected_version = None
        self.selected_config = None
        self.action = None

        # 文件下拉
        self.file_combobox = ComboBox()
        self.file_combobox.addItems(filenames)
        self.file_combobox.setMaxVisibleItems(10)

        # 版本下拉
        self.version_combobox = ComboBox()
        self.version_combobox.setMaxVisibleItems(10)

        # 文件+版本 同行布局
        select_layout = QHBoxLayout()
        select_layout.setSpacing(15)

        file_label = QLabel("选择文件：")
        version_label = QLabel("选择版本：")
        file_label.setFixedWidth(65)
        version_label.setFixedWidth(65)

        select_layout.addWidget(file_label)
        select_layout.addWidget(self.file_combobox, 1)

        time_layout = QHBoxLayout()
        time_layout.setSpacing(15)
        time_layout.addWidget(version_label)
        time_layout.addWidget(self.version_combobox, 1)

        self.load_button = PushButton("加载", icon=get_icon("加载配置"), parent=self.buttonGroup)
        self.compare_button = PushButton("对比", icon=get_icon("对比"), parent=self.buttonGroup)
        self.buttonLayout.addWidget(self.load_button, 1, Qt.AlignVCenter)
        self.buttonLayout.addWidget(self.compare_button, 1, Qt.AlignVCenter)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addLayout(select_layout)
        self.viewLayout.addLayout(time_layout)

        # 信号连接
        self.load_button.clicked.connect(self.on_load)
        self.compare_button.clicked.connect(self.on_compare)
        self.file_combobox.currentIndexChanged.connect(self.update_versions)

        # 初始化一次版本选择
        self.update_versions()

    def update_versions(self):
        self.selected_file = self.file_combobox.currentText()
        if self.selected_file:
            versions = self.file_map[self.selected_file]
            version_labels = [f"{ts}" for ts, _ in versions]
            self.version_combobox.clear()
            self.version_combobox.addItems(version_labels)

    def on_load(self):
        # 获取所选版本
        version_index = self.version_combobox.currentIndex()
        if version_index >= 0:
            selected_version_data = self.file_map[self.selected_file][version_index]
            self.selected_config = selected_version_data[1]  # 获取历史配置
            self.selected_version = self.version_combobox.currentText()  # ✅ 记录版本时间
            self.action = "load"  # 标记为加载动作
            self.accept()  # 关闭对话框，返回已选择的配置

    def on_compare(self):
        # 获取所选版本
        version_index = self.version_combobox.currentIndex()
        if version_index >= 0:
            selected_version_data = self.file_map[self.selected_file][version_index]
            self.selected_config = selected_version_data[1]  # 获取历史配置
            self.selected_version = self.version_combobox.currentText()  # ✅ 记录版本时间
            self.action = "compare"  # 标记为对比动作
            self.accept()  # 关闭对话框，返回已选择的配置
