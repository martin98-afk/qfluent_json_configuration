"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: utils.py
@time: 2025/4/27 10:03
@desc: 
"""
import os
import pickle
import re
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QDateTimeEdit
from loguru import logger


def sanitize_path(path):
    # 定义需要替换的非法字符模式（包括常见操作系统不允许的字符）
    illegal_chars = r'[\\/:*?"<>|]'  # 可根据需求扩展字符集
    # 规范化路径并拆分处理每个层级
    normalized = os.path.normpath(path)
    parts = []
    while True:
        head, tail = os.path.split(normalized)
        if tail:
            parts.append(tail)
            normalized = head
        else:
            if head:
                parts.append(head)
            break
    # 反转并清理每个路径部分
    parts.reverse()
    cleaned = [re.sub(illegal_chars, '_', p) for p in parts]
    # 重新组合路径
    return os.path.join(*cleaned) if cleaned else ''


def save_point_cache(data, filename='point_cache.pkl'):
    with open(filename, 'wb') as f:
        pickle.dump(data, f)


def load_point_cache(filename='point_cache.pkl'):
    try:
        with open(filename, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return {}


def error_catcher_decorator(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            import traceback
            logger.error(f"Error in {func.__name__}: {traceback.format_exc()}")
            return None

    return wrapper


def get_file_name(path: str):
    return ".".join(os.path.basename(path).split(".")[:-1])


# 日期控件设置
def styled_dt(dt_edit: QDateTimeEdit) -> QDateTimeEdit:
    dt_edit.setCalendarPopup(True)
    dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
    dt_edit.setFont(QFont("Segoe UI", 10))
    dt_edit.setMinimumWidth(180)

    dt_edit.setStyleSheet("""
        QDateTimeEdit {
            padding: 6px 10px;
            border: 1px solid #ccc;
            border-radius: 8px;
            background-color: #f5f5f5;
        }
        QDateTimeEdit:hover {
            border-color: #888;
        }
        QDateTimeEdit:focus {
            border-color: #007ACC;
            background-color: #ffffff;
        }
        QToolButton {
            color: black;
            border-radius: 4px;
            padding: 2px 6px;
            background-color: transparent;
        }
        QToolButton:hover {
            background-color: #e0e0e0;
        }
        QToolButton:pressed {
            background-color: #c0c0c0;
        }
    """)

    calendar = dt_edit.calendarWidget()
    calendar.setAttribute(Qt.WA_Hover, True)  # 关键：启用 hover 事件
    calendar.setFixedSize(300, 250)
    calendar.setStyleSheet("""
        QCalendarWidget {
            border: 1px solid #aaa;
            border-radius: 10px;
            background-color: white;
        }
        QCalendarWidget QWidget {
            color: black;
            background-color: white;
            font-family: "Segoe UI";
            font-size: 10pt;
        }
        QCalendarWidget::day-button {
            padding: 6px;
            border-radius: 6px;
            font-size: 10pt;
        }
        QCalendarWidget::day-button:hover {
            background-color: #e0e0e0;
            color: #000;
            border: 1px solid #ccc;
        }
        QCalendarWidget::day-button:selected {
            background-color: #007ACC;
            color: white;
            font-weight: bold;
            border: 1px solid #005FA3;
        }
    """)

    return dt_edit


def resource_path(relative_path):
    """获取打包后资源文件的绝对路径"""
    if hasattr(sys, '_MEIPASS'):
        # 如果是打包后的环境
        base_path = sys._MEIPASS
    else:
        # 开发环境，直接使用当前路径
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)



def get_unique_name(base_name, existing_names):
    if base_name not in existing_names:
        return base_name
    i = 1
    while f"{base_name}_{i}" in existing_names:
        i += 1
    return f"{base_name}_{i}"


def get_icon(icon_name):
    icons = {}
    relative_path = "icons"
    for name in os.listdir(resource_path(relative_path)):
        if name.endswith(".png"):
            icons[name[:-4]] = os.path.join(resource_path(relative_path), name)

    return QIcon(icons.get(icon_name, "icons/icon_unknown.png"))


def get_button_style_sheet(bg_color=None):
    bg_color = bg_color if bg_color else "#e9ecef"
    return f"""
            QPushButton {{
                background-color: {bg_color};
                border: none;
                border-radius: 6px;
                color: #495057;
                font-size: 15px;
                padding: 10px 10px;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: #adb5bd;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: #868e96;
            }}
            QPushButton:focus {{
                outline: none;
                border: none;
            }}
        """


def seed_everything(seed: int = 1):
    import random
    import os
    import numpy as np
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)


def wrap_widget(widget, stretch=True):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.addWidget(widget)
    layout.setAlignment(Qt.AlignCenter)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    if stretch:
        layout.addStretch()
    container.setLayout(layout)
    container.setAttribute(Qt.WA_TranslucentBackground)  # 启用透明背景支持
    container.setStyleSheet("background-color: transparent;")  # 关键：设置背景透明
    return container