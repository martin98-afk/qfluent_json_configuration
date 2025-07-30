"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: datetime_select.py
@time: 2025/7/16 11:40
@desc: 
"""
import sys
from datetime import datetime

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import QDate, QTime
from qfluentwidgets import FastCalendarPicker, TimePicker


class DateTimePicker(QWidget):
    def __init__(self, default_datetime=None):
        super().__init__()

        # 初始化UI
        self.setWindowTitle("Date and Time Picker with QFluentWidgets")

        # 如果没有传入默认的 datetime，则使用当前 datetime
        if default_datetime is None:
            default_datetime = datetime.now()

        # 创建主布局
        layout = QVBoxLayout()

        # 创建水平布局，将日期选择器和时间选择器放在一起
        picker_layout = QHBoxLayout()

        # 创建并添加日历选择器控件
        self.calendar_picker = FastCalendarPicker()
        self.calendar_picker.setFixedWidth(130)  # 设置日期选择器宽度
        self.calendar_picker.setDate(
            QDate(default_datetime.year, default_datetime.month, default_datetime.day))  # 设置默认日期
        picker_layout.addWidget(self.calendar_picker)

        # 创建并添加时间选择器控件
        self.time_picker = TimePicker()
        self.time_picker.setMinimumWidth(10)  # 尝试设置最小宽度
        self.time_picker.setFixedSize(90, 32)  # 强制设置一个更小的尺寸
        self.time_picker.setTime(QTime(default_datetime.hour, default_datetime.minute))  # 设置默认时间
        picker_layout.addWidget(self.time_picker)

        layout.addLayout(picker_layout)

        # 设置主布局
        self.setLayout(layout)

    def get_current_datetime(self):
        # 获取当前选中的日期和时间
        selected_date = self.calendar_picker.date
        selected_time = self.time_picker.time
        return f"{selected_date.toString('yyyy-MM-dd')} {selected_time.toString('HH:mm')}"


if __name__ == "__main__":
    # 传入默认日期和时间（例如：2023年5月15日 12:30）
    default_date = datetime.now()

    app = QApplication(sys.argv)
    window = DateTimePicker(default_datetime=default_date)
    window.show()
    sys.exit(app.exec_())
