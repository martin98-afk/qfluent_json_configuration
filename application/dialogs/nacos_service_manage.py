"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: nacos_service_manage.py
@time: 2025/7/2 16:57
@desc: 
"""
from PyQt5.QtCore import QThreadPool, Qt
from PyQt5.QtWidgets import (QHBoxLayout,
                             QVBoxLayout, QPushButton,
                             QLabel, QMessageBox, QDialog)
from loguru import logger

from application.utils.threading_utils import Worker
from application.widgets.draggable_list_widget import DraggableListWidget


class ServiceConfigManager(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("下控配置")
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.parent = parent
        self.setWindowTitle("NACOS下控服务配置")
        self.resize(1000, 600)
        self.setWindowFlags(
            Qt.Window | Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
        )
        self.api_tools_flag = False
        self.database_tools_flag = False
        self.apply_modern_style()
        self.thread_pool = QThreadPool.globalInstance()
        self.initUI()

    def apply_modern_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f4f6f9;
                font-family: "Segoe UI", sans-serif;
                font-size: 18px;
            }

            QListWidget {
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #ffffff;
            }

            QListWidget::item:hover {
                background-color: #f1f3f5;
            }

            QLabel {
                font-weight: bold;
                padding: 4px;
                color: #343a40;
            }

            QPushButton {
                background-color: #339af0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }

            QPushButton:hover {
                background-color: #228be6;
            }

            QPushButton:pressed {
                background-color: #1c7ed6;
            }
        """)

    def get_service_list(self):
        worker = Worker(self.parent.config.api_tools.get("service_list"))
        worker.signals.finished.connect(self.load_config)
        self.thread_pool.start(worker)

    def initUI(self):
        main_layout = QVBoxLayout(self)

        list_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        self.left_label = QLabel("可用服务 （双击添加）")
        self.left_list = DraggableListWidget()
        left_layout.addWidget(self.left_label)
        left_layout.addWidget(self.left_list)

        right_layout = QVBoxLayout()
        self.right_label = QLabel("已配置服务 （双击去除）")
        self.right_list = DraggableListWidget()
        right_layout.addWidget(self.right_label)
        right_layout.addWidget(self.right_list)

        list_layout.addLayout(left_layout, 1)
        list_layout.addLayout(right_layout, 1)

        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_config)
        save_layout.addWidget(self.save_btn)

        main_layout.addLayout(list_layout)
        main_layout.addLayout(save_layout)

        self.left_list.doubleClicked.connect(self.move_to_right)
        self.right_list.doubleClicked.connect(self.move_to_left)

    def load_config(self, service_list):
        self.left_list.clear()
        self.right_list.clear()
        self.service_map = {name: url for name, url, _ in service_list}
        try:
            urls = self.parent.config.api_tools.get("get_service_path").call(service_list)
            configured = [name for name, url, _ in service_list if url in urls]
            available = [name for name, url, _ in service_list if url not in urls]
            self.left_list.addItems(available)
            self.right_list.addItems(configured)
        except Exception as e:
            import traceback
            logger.error(f"加载配置失败: {traceback.format_exc()}")

    def move_to_right(self):
        for item in self.left_list.selectedItems():
            self.right_list.addItem(item.text())
            self.left_list.takeItem(self.left_list.row(item))

    def move_to_left(self):
        for item in self.right_list.selectedItems():
            self.left_list.addItem(item.text())
            self.right_list.takeItem(self.right_list.row(item))

    def save_config(self):
        try:
            names = [self.right_list.item(i).text() for i in range(self.right_list.count())]
            urls = [self.service_map[name] for name in names]
            self.parent.config.api_tools.get("write_service_path").call(urls)
            QMessageBox.information(self, "成功", "配置保存成功")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def get_configured_urls(self):
        return [self.service_map[self.right_list.item(i).text()] for i in range(self.right_list.count())]


# 使用示例
if __name__ == '__main__':
    pass