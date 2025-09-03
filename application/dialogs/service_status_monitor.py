import time
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, QThreadPool
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QHBoxLayout,
    QSizePolicy
)
from loguru import logger
from qfluentwidgets import FluentIcon as FIF, ComboBox, TogglePushButton
from qfluentwidgets import (
    SwitchButton,
    TableWidget,
    InfoBar,
    InfoBarPosition,
    PushButton
)

from application.tools.api_service.servicves_test import ServicesTest
from application.utils.threading_utils import Worker


class ServiceStatusMonitor(QWidget):
    """独立的服务状态监控界面"""

    STATUS_COLORS = {
        '成功': '#32CD32',
        '失败': '#f44747',
        '未监控': '#808080',
        '检查中...': '#ffcb6b',
        '重启中...': '#dcdcaa'
    }

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.home = parent
        self.setObjectName("服务监控")
        self.editor = editor
        self.service_tester = ServicesTest()
        self.monitoring_services = {}  # 存储监控服务信息
        self.monitoring_timer = QTimer(self)
        self.thread_pool = QThreadPool.globalInstance()
        self.monitoring_records = []  # 存储监控记录
        self.current_service_filter = None  # 当前服务过滤器
        self.current_record_btn = None  # 当前选中的记录按钮
        self.last_selected_service_id = None  # 保存上次选中的服务ID
        self.loading_services = False  # 标记是否正在加载服务
        self.record_limit = 1000  # 默认记录保留数量
        self.log_panel_visible = False  # 标记日志面板是否可见

        # 初始化UI
        self.init_ui()

        # 设置定时器 (10秒检查一次)
        self.monitoring_timer.timeout.connect(self.check_all_services)
        self.monitoring_timer.setInterval(10000)  # 10秒

        # 自动加载服务列表
        self.load_services()

    def init_ui(self):
        """初始化UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("🛠️ 服务状态监控")
        title_label.setFont(QFont("微软雅黑", 16, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 控制按钮
        control_layout = QHBoxLayout()

        self.start_all_btn = PushButton(FIF.PLAY, "全部开启监控", self)
        self.start_all_btn.clicked.connect(self.start_all_monitoring)
        control_layout.addWidget(self.start_all_btn)

        self.stop_all_btn = PushButton(FIF.PAUSE, "全部停止监控", self)
        self.stop_all_btn.clicked.connect(self.stop_all_monitoring)
        control_layout.addWidget(self.stop_all_btn)

        self.refresh_btn = PushButton(FIF.SYNC, "刷新服务列表", self)
        self.refresh_btn.clicked.connect(self.load_services)
        control_layout.addWidget(self.refresh_btn)

        # 添加监控日志切换按钮
        self.log_toggle_btn = TogglePushButton("监控日志", self)
        self.log_toggle_btn.setCheckable(True)
        self.log_toggle_btn.setChecked(False)
        self.log_toggle_btn.clicked.connect(self.toggle_log_panel)
        control_layout.addWidget(self.log_toggle_btn)
        control_layout.addStretch()

        # 状态说明
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("状态说明:"))

        status_items = [
            ("成功", "#32CD32"),
            ("失败", "#f44747"),
            ("未监控", "#808080"),
            ("检查中...", "#ffcb6b"),
            ("重启中...", "#dcdcaa")
        ]

        for text, color in status_items:
            item = QLabel(f"● {text}")
            item.setStyleSheet(f"color: {color};")
            item.setFont(QFont("微软雅黑", 9))
            status_layout.addWidget(item)

        status_layout.addStretch()

        # 监控表格 (8列：服务名称、状态监控、服务状态、监控间隔、自动重启、最大重启次数、手动重启、监控记录)
        self.monitoring_table = TableWidget()
        self.monitoring_table.setColumnCount(8)
        self.monitoring_table.setHorizontalHeaderLabels(
            ["服务名称", "状态监控", "服务状态", "监控间隔", "自动重启", "最大重启次数", "手动重启", "监控记录"])
        self.monitoring_table.verticalHeader().setVisible(False)
        self.monitoring_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.monitoring_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.monitoring_table.setAlternatingRowColors(True)
        self.monitoring_table.setWordWrap(True)
        self.monitoring_table.setSortingEnabled(False)

        # 设置列宽比例 - 按照要求设置
        self.monitoring_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # 服务名称
        self.monitoring_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 状态监控
        self.monitoring_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 服务状态
        self.monitoring_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 监控间隔
        self.monitoring_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 自动重启
        self.monitoring_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 最大重启次数
        self.monitoring_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 手动重启
        self.monitoring_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 监控记录

        # 设置表格样式 - 移除行选中时的蓝色背景
        self.monitoring_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: transparent;
                color: inherit;
                border: none;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 6px;
                border: none;
                border-right: 1px solid #e0e0e0;
                font-weight: bold;
            }
        """)

        # 创建监控日志容器
        self.log_container = QWidget()
        self.log_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        log_container_layout = QVBoxLayout(self.log_container)
        log_container_layout.setContentsMargins(0, 0, 0, 0)
        log_container_layout.setSpacing(5)

        # 记录标题和按钮
        record_title_layout = QHBoxLayout()
        record_title = QLabel("📊 监控记录")
        record_title.setFont(QFont("微软雅黑", 12, QFont.Bold))
        record_title_layout.addWidget(record_title)

        self.view_all_records_btn = PushButton("查看全部记录")
        self.view_all_records_btn.clicked.connect(self.view_all_records)
        record_title_layout.addWidget(self.view_all_records_btn)

        # 记录保留数量下拉框
        record_limit_layout = QHBoxLayout()
        record_limit_layout.addWidget(QLabel("记录保留数量:"))

        self.record_limit_combo = ComboBox()
        self.record_limit_combo.addItems(["1000行", "2000行", "5000行"])
        self.record_limit_combo.setCurrentIndex(0)  # 默认1000行
        self.record_limit_combo.currentIndexChanged.connect(self.on_record_limit_changed)
        record_limit_layout.addWidget(self.record_limit_combo)

        record_title_layout.addLayout(record_limit_layout)
        record_title_layout.addStretch()

        log_container_layout.addLayout(record_title_layout)

        self.record_table = TableWidget()
        self.record_table.setColumnCount(4)
        self.record_table.setHorizontalHeaderLabels(["时间", "服务名称", "状态", "操作"])
        self.record_table.verticalHeader().setVisible(False)
        self.record_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.record_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.record_table.setAlternatingRowColors(True)
        self.record_table.setWordWrap(True)
        self.record_table.setSortingEnabled(True)

        # 设置记录表格列宽
        self.record_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.record_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.record_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.record_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        # 设置记录表格样式
        self.record_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 6px;
                border: none;
                border-right: 1px solid #e0e0e0;
                font-weight: bold;
            }
        """)

        log_container_layout.addWidget(self.record_table)

        # 默认隐藏日志容器
        self.log_container.setVisible(False)
        self.log_container.setMinimumHeight(0)
        self.log_container.setMaximumHeight(0)

        # 添加到主布局
        main_layout.addLayout(title_layout)
        main_layout.addLayout(control_layout)
        main_layout.addLayout(status_layout)
        main_layout.addWidget(self.monitoring_table)
        main_layout.addWidget(self.log_container)  # 添加日志容器

    def toggle_log_panel(self, checked):
        """切换监控日志面板的显示状态"""
        self.log_panel_visible = checked
        self.log_toggle_btn.setChecked(checked)

        if checked:
            # 展开日志面板
            self.log_container.setMinimumHeight(0)
            self.log_container.setMaximumHeight(16777215)  # Qt默认的最大高度
            self.log_container.setVisible(True)
        else:
            # 折叠日志面板
            self.log_container.setMinimumHeight(0)
            self.log_container.setMaximumHeight(0)
            self.log_container.setVisible(False)

        # 更新记录表格
        self.update_record_table()

    def on_record_limit_changed(self, index):
        """记录保留数量变化处理"""
        limits = [1000, 2000, 5000]
        self.record_limit = limits[index]

        # 限制现有记录数量
        if len(self.monitoring_records) > self.record_limit:
            self.monitoring_records = self.monitoring_records[:self.record_limit]
            self.update_record_table()

    def load_services(self):
        """加载服务列表"""
        worker = Worker(self.editor.config.api_tools.get("service_list", None))
        worker.signals.finished.connect(self.on_services_load)
        worker.signals.error.connect(self.on_services_load_error)
        self.thread_pool.start(worker)

        # 显示加载状态
        self.monitoring_table.setRowCount(0)
        self.monitoring_table.insertRow(0)
        self.monitoring_table.setItem(0, 0, QTableWidgetItem("加载中..."))
        self.monitoring_table.setSpan(0, 0, 1, 8)  # 8列
        self.monitoring_table.item(0, 0).setTextAlignment(Qt.AlignCenter)

    def on_services_load(self, services):
        """处理服务列表加载结果，保留之前的监控状态"""
        # 标记开始加载服务
        self.loading_services = True

        # 保存当前选中的服务ID
        if self.current_record_btn:
            try:
                self.last_selected_service_id = self.current_record_btn.property("service_id")
            except RuntimeError:
                # 如果按钮已删除，重置相关状态
                self.current_record_btn = None
                self.last_selected_service_id = None
        else:
            self.last_selected_service_id = None

        # 重置当前记录按钮，避免引用已删除的对象
        self.current_record_btn = None

        # 保存当前的监控状态
        current_states = {}
        for sid, info in self.monitoring_services.items():
            current_states[sid] = {
                'monitoring': info['monitoring'],
                'interval': info.get('interval', 10),  # 保存监控间隔
                'auto_restart': info['auto_restart'],
                'max_restart': info.get('max_restart', 3),  # 保存最大重启次数
                'status': info.get('status', '未监控'),  # 保存状态
                'last_check': info.get('last_check', 0),  # 保存最后检查时间
                'restart_count': info.get('restart_count', 0),  # 保存重启计数
                'last_restart': info.get('last_restart', 0)  # 保存最后重启时间
            }

        # 清空表格但保留状态数据
        self.monitoring_table.setRowCount(0)
        new_monitoring_services = {}

        if not services:
            self.monitoring_table.setRowCount(1)
            self.monitoring_table.setItem(0, 0, QTableWidgetItem("没有可用的服务"))
            self.monitoring_table.setSpan(0, 0, 1, 8)  # 8列
            self.monitoring_table.item(0, 0).setTextAlignment(Qt.AlignCenter)
            self.monitoring_services = new_monitoring_services
            self.loading_services = False  # 标记加载结束
            return

        # 将服务分为两组：正在监控的和未监控的
        monitoring_services = []
        non_monitoring_services = []

        for name, path, sid in services:
            # 检查是否已有该服务的状态
            prev_state = current_states.get(sid, {
                'monitoring': False,  # 默认不监控
                'interval': 10,  # 默认10秒
                'auto_restart': False,
                'max_restart': 3,  # 默认最大重启次数为3
                'status': '未监控',  # 默认状态
                'last_check': 0,
                'restart_count': 0,
                'last_restart': 0
            })

            if prev_state['monitoring']:
                monitoring_services.append((name, path, sid, prev_state))
            else:
                non_monitoring_services.append((name, path, sid, prev_state))

        # 先添加正在监控的服务
        for name, path, sid, prev_state in monitoring_services:
            self.add_service_to_monitoring_table(name, path, sid, prev_state)
            new_monitoring_services[sid] = self.monitoring_services[sid]

        # 再添加未监控的服务
        for name, path, sid, prev_state in non_monitoring_services:
            self.add_service_to_monitoring_table(name, path, sid, prev_state)
            new_monitoring_services[sid] = self.monitoring_services[sid]

        self.monitoring_services = new_monitoring_services

        # 检查是否还有服务在监控，决定是否继续运行定时器
        if any(info['monitoring'] for info in new_monitoring_services.values()):
            if not self.monitoring_timer.isActive():
                self.monitoring_timer.start()
        else:
            self.monitoring_timer.stop()

        # 尝试恢复之前选中的服务
        if self.last_selected_service_id and self.last_selected_service_id in self.monitoring_services:
            self.restore_selected_service()

        # 标记加载结束
        self.loading_services = False

    def restore_selected_service(self):
        """恢复之前选中的服务状态"""
        for row in range(self.monitoring_table.rowCount()):
            record_btn = self.monitoring_table.cellWidget(row, 7)
            if record_btn and record_btn.property("service_id") == self.last_selected_service_id:
                # 取消之前可能的选中状态
                if self.current_record_btn:
                    self.current_record_btn.setChecked(False)

                # 设置当前选中的按钮
                self.current_record_btn = record_btn
                record_btn.setChecked(True)
                service_name = record_btn.property("service_name")
                self.current_service_filter = service_name
                self.update_record_table()
                break

    def on_services_load_error(self, error):
        """处理服务列表加载错误"""
        self.monitoring_table.setRowCount(1)
        error_item = QTableWidgetItem(f"加载服务失败: {str(error)}")
        error_item.setForeground(Qt.red)
        self.monitoring_table.setItem(0, 0, error_item)
        self.monitoring_table.setSpan(0, 0, 1, 8)  # 8列
        self.monitoring_table.item(0, 0).setTextAlignment(Qt.AlignCenter)

        # 标记加载结束
        self.loading_services = False

    def add_service_to_monitoring_table(self, name, path, sid, prev_state=None):
        """将服务添加到监控表格"""
        if prev_state is None:
            prev_state = {
                'monitoring': False,  # 默认不监控
                'interval': 10,  # 默认10秒
                'auto_restart': False,
                'max_restart': 3,  # 默认最大重启次数为3
                'status': '未监控',  # 默认状态
                'last_check': 0,
                'restart_count': 0,
                'last_restart': 0
            }

        row = self.monitoring_table.rowCount()
        self.monitoring_table.insertRow(row)

        # 服务名称
        name_item = QTableWidgetItem(name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.monitoring_table.setItem(row, 0, name_item)

        # 状态监控开关
        monitor_switch = SwitchButton("")
        monitor_switch._onText = self.tr('')
        monitor_switch.setProperty("service_id", sid)
        monitor_switch.checkedChanged.connect(self.on_monitoring_switch_changed)
        monitor_switch.setChecked(prev_state['monitoring'])
        self.monitoring_table.setCellWidget(row, 1, monitor_switch)

        # 服务状态 - 使用之前保存的状态，而不是总是"检查中..."
        status_text = prev_state['status']
        status_label = QLabel(status_text)
        status_label.setAlignment(Qt.AlignCenter)
        color = self.STATUS_COLORS.get(status_text, self.STATUS_COLORS['未监控'])
        status_label.setStyleSheet(f"color: {color};")
        self.monitoring_table.setCellWidget(row, 2, status_label)

        # 监控间隔下拉框
        interval_combo = ComboBox()
        interval_combo.addItems(["5秒", "10秒", "30秒", "60秒"])
        # 根据之前的间隔设置当前索引
        intervals = [5, 10, 30, 60]
        if prev_state['interval'] in intervals:
            interval_combo.setCurrentIndex(intervals.index(prev_state['interval']))
        else:
            interval_combo.setCurrentIndex(1)  # 默认10秒
        interval_combo.setProperty("service_id", sid)
        interval_combo.currentIndexChanged.connect(self.on_interval_changed)
        self.monitoring_table.setCellWidget(row, 3, interval_combo)

        # 自动重启开关
        restart_switch = SwitchButton("")
        restart_switch._onText = self.tr('')
        restart_switch.setProperty("service_id", sid)
        restart_switch.checkedChanged.connect(self.on_auto_restart_switch_changed)
        restart_switch.setChecked(prev_state['auto_restart'])
        self.monitoring_table.setCellWidget(row, 4, restart_switch)

        # 最大重启次数下拉框
        max_restart_combo = ComboBox()
        max_restart_combo.addItems(["1次", "2次", "3次", "5次", "10次"])
        max_restart_combo.setCurrentIndex(prev_state['max_restart'] - 1 if 1 <= prev_state['max_restart'] <= 10 else 2)
        max_restart_combo.setProperty("service_id", sid)
        max_restart_combo.currentIndexChanged.connect(self.on_max_restart_changed)
        self.monitoring_table.setCellWidget(row, 5, max_restart_combo)

        # 手动重启按钮
        restart_btn = PushButton("重启")
        restart_btn.setProperty("service_id", sid)
        restart_btn.clicked.connect(self.on_manual_restart)
        self.monitoring_table.setCellWidget(row, 6, restart_btn)

        # 监控记录按钮 - 使用TogglePushButton
        record_btn = TogglePushButton("记录")
        record_btn.setProperty("service_id", sid)
        record_btn.setProperty("service_name", name)
        record_btn.setCheckable(True)
        record_btn.clicked.connect(self.on_view_record)
        self.monitoring_table.setCellWidget(row, 7, record_btn)

        # 初始化监控状态 - 使用之前的状态
        self.monitoring_services[sid] = {
            'service_name': name,
            'service_path': path,
            'monitoring': prev_state['monitoring'],
            'interval': prev_state['interval'],
            'auto_restart': prev_state['auto_restart'],
            'max_restart': prev_state['max_restart'],
            'status': status_text,  # 使用之前的状态
            'last_check': prev_state['last_check'],
            'status_label': status_label,
            'restart_count': prev_state['restart_count'],
            'last_restart': prev_state['last_restart'],
            'record_btn': record_btn  # 保存按钮引用
        }

    def on_interval_changed(self, index):
        """监控间隔下拉框变化处理"""
        combo = self.sender()
        sid = combo.property("service_id")

        if sid in self.monitoring_services:
            # 从"5秒"、"10秒"等文本中提取数字
            text = combo.currentText()
            interval = int(text.replace("秒", ""))
            self.monitoring_services[sid]['interval'] = interval

            # 重新计算定时器间隔
            self.update_monitoring_timer_interval()

    def update_monitoring_timer_interval(self):
        """更新监控定时器的间隔"""
        # 找出所有正在监控的服务中最小的间隔
        min_interval = float('inf')
        for info in self.monitoring_services.values():
            if info['monitoring']:
                min_interval = min(min_interval, info['interval'])

        # 如果没有服务在监控，停止定时器
        if min_interval == float('inf'):
            self.monitoring_timer.stop()
            return

        # 设置定时器间隔为最小间隔（毫秒）
        new_interval = min_interval * 1000
        if self.monitoring_timer.interval() != new_interval:
            self.monitoring_timer.setInterval(new_interval)
        if not self.monitoring_timer.isActive():
            self.monitoring_timer.start()

    def on_view_record(self, checked):
        """查看服务监控记录"""
        btn = self.sender()

        # 检查按钮是否仍然有效
        try:
            sid = btn.property("service_id")
            service_name = btn.property("service_name")
        except RuntimeError:
            # 按钮已删除，重置相关状态
            self.current_record_btn = None
            self.last_selected_service_id = None
            return

        # 如果点击的是当前选中的按钮，取消选中
        if self.current_record_btn == btn:
            btn.setChecked(False)
            self.current_record_btn = None
            self.last_selected_service_id = None
            self.current_service_filter = None
        else:
            # 取消之前选中的按钮
            if self.current_record_btn:
                try:
                    self.current_record_btn.setChecked(False)
                except RuntimeError:
                    pass

            # 设置当前选中的按钮
            self.current_record_btn = btn
            self.last_selected_service_id = sid
            btn.setChecked(True)
            self.current_service_filter = service_name

        # 更新记录表格
        self.update_record_table()

    def view_all_records(self):
        """查看全部监控记录"""
        # 取消之前选中的按钮
        if self.current_record_btn:
            try:
                self.current_record_btn.setChecked(False)
                self.last_selected_service_id = None
            except RuntimeError:
                pass

        self.current_record_btn = None
        self.current_service_filter = None
        self.update_record_table()

    def update_record_table(self):
        """更新记录表格，根据当前过滤器"""
        # 如果日志面板不可见，直接返回
        if not self.log_panel_visible:
            return

        self.record_table.setRowCount(0)  # 先清空

        # 筛选记录
        if self.current_service_filter:
            filtered_records = [r for r in self.monitoring_records if r['service_name'] == self.current_service_filter]
        else:
            filtered_records = self.monitoring_records

        # 修复记录时间顺序问题 - 确保最新记录在最上面
        # 按时间降序排序（最新记录在最前面）
        filtered_records.sort(key=lambda x: x['time'], reverse=True)

        # 显示最近记录
        records_to_show = filtered_records[:self.record_limit]

        for record in records_to_show:
            row = self.record_table.rowCount()
            self.record_table.insertRow(row)

            # 时间
            time_item = QTableWidgetItem(record['time'])
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            self.record_table.setItem(row, 0, time_item)

            # 服务名称
            service_item = QTableWidgetItem(record['service_name'])
            service_item.setFlags(service_item.flags() & ~Qt.ItemIsEditable)
            self.record_table.setItem(row, 1, service_item)

            # 状态
            status_item = QTableWidgetItem(record['status'])
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            # 根据状态设置颜色
            if record['status'] == "成功":
                status_item.setForeground(QColor(self.STATUS_COLORS['成功']))
            elif record['status'] in ["失败", "警告"]:
                status_item.setForeground(QColor(self.STATUS_COLORS['失败']))
            elif record['status'] == "未监控":
                status_item.setForeground(QColor(self.STATUS_COLORS['未监控']))
            self.record_table.setItem(row, 2, status_item)

            # 操作 - 修复空操作问题
            operation = record['operation'] or "未知操作"
            operation_item = QTableWidgetItem(operation)
            operation_item.setFlags(operation_item.flags() & ~Qt.ItemIsEditable)
            self.record_table.setItem(row, 3, operation_item)

        # 滚动到最新记录
        self.record_table.scrollToTop()

    def on_max_restart_changed(self, index):
        """最大重启次数下拉框变化处理"""
        combo = self.sender()
        sid = combo.property("service_id")

        if sid in self.monitoring_services:
            # 从"1次"、"2次"等文本中提取数字
            text = combo.currentText()
            max_restart = int(text.replace("次", ""))
            self.monitoring_services[sid]['max_restart'] = max_restart

            # 显示配置信息
            service_name = self.monitoring_services[sid]['service_name']

    def on_manual_restart(self):
        """手动重启服务"""
        btn = self.sender()
        sid = btn.property("service_id")

        if sid not in self.monitoring_services:
            return

        info = self.monitoring_services[sid]

        # 记录监控记录
        self.add_monitoring_record(
            service_name=info['service_name'],
            status="手动重启",
            operation="执行手动重启"
        )

        # 更新状态为"重启中..."
        if 'status_label' in info and info['status_label']:
            try:
                info['status_label'].setText("重启中...")
                info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['重启中...']};")
            except RuntimeError:
                # 如果标签已删除，忽略错误
                pass

        # 执行重启
        worker = Worker(self.editor.config.api_tools.get("service_reonline"), sid)
        worker.signals.finished.connect(lambda: self.on_manual_restart_finished(sid))
        worker.signals.error.connect(lambda e: self.on_manual_restart_error(sid, e))
        self.thread_pool.start(worker)

    def on_manual_restart_finished(self, sid):
        """手动重启成功处理"""
        if sid in self.monitoring_services:
            info = self.monitoring_services[sid]
            self.create_successbar(f"服务 {info['service_name']} 重启成功")

            # 记录监控记录
            self.add_monitoring_record(
                service_name=info['service_name'],
                status="成功",
                operation="手动重启成功"
            )

            # 重启后状态暂时设为检查中
            if 'status_label' in info and info['status_label']:
                try:
                    info['status_label'].setText("检查中...")
                    info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['检查中...']};")
                except RuntimeError:
                    pass

    def on_manual_restart_error(self, sid, error):
        """手动重启失败处理"""
        if sid in self.monitoring_services:
            info = self.monitoring_services[sid]
            self.create_errorbar(f"服务 {info['service_name']} 重启失败", str(error))

            # 记录监控记录
            self.add_monitoring_record(
                service_name=info['service_name'],
                status="失败",
                operation=f"手动重启失败: {str(error)}"
            )

            # 重启失败后状态仍为失败
            if 'status_label' in info and info['status_label']:
                try:
                    info['status_label'].setText("失败")
                    info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['失败']};")
                except RuntimeError:
                    pass

    def on_monitoring_switch_changed(self, checked):
        """状态监控开关变化处理"""
        btn = self.sender()
        sid = btn.property("service_id")

        if sid not in self.monitoring_services:
            return

        info = self.monitoring_services[sid]
        info['monitoring'] = checked

        # 只有在用户手动操作时才记录，加载服务时不记录
        if not self.loading_services:
            # 记录监控状态变化
            operation = "开启监控" if checked else "关闭监控"
            self.add_monitoring_record(
                service_name=info['service_name'],
                status="监控状态变更",
                operation=operation
            )

        # 更新状态显示
        if 'status_label' in info and info['status_label']:
            try:
                if checked:
                    # 不要立即设置为"检查中..."，而是保留之前的状态
                    # 只有在开始检查时才更新为"检查中..."
                    pass
                else:
                    info['status'] = "未监控"
                    info['status_label'].setText("未监控")
                    info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['未监控']};")
            except RuntimeError:
                pass

        # 更新定时器
        self.update_monitoring_timer_interval()

    def on_auto_restart_switch_changed(self, checked):
        """自动重启开关变化处理"""
        btn = self.sender()
        sid = btn.property("service_id")

        if sid in self.monitoring_services:
            info = self.monitoring_services[sid]
            info['auto_restart'] = checked

            # 只有在用户手动操作时才记录，加载服务时不记录
            if not self.loading_services:
                # 记录监控记录
                operation = "启用" if checked else "禁用"
                self.add_monitoring_record(
                    service_name=info['service_name'],
                    status="自动重启",
                    operation=f"{operation}自动重启"
                )

    def start_all_monitoring(self):
        """开启所有服务的监控"""
        for sid, info in self.monitoring_services.items():
            info['monitoring'] = True

            # 查找表格中的监控开关并设置状态
            for row in range(self.monitoring_table.rowCount()):
                monitor_switch = self.monitoring_table.cellWidget(row, 1)
                if monitor_switch and monitor_switch.property("service_id") == sid:
                    monitor_switch.setChecked(True)
                    break

            # 更新状态显示 - 不要立即设置为"检查中..."
            # 只有在开始检查时才更新为"检查中..."
            if 'status_label' in info and info['status_label']:
                try:
                    # 保留之前的状态，不要立即改为"检查中..."
                    pass
                except RuntimeError:
                    pass

        # 启动监控定时器
        self.update_monitoring_timer_interval()

        # 只有在用户手动操作时才记录，加载服务时不记录
        if not self.loading_services:
            # 记录开启所有监控
            self.add_monitoring_record(
                service_name="所有服务",
                status="监控状态变更",
                operation="开启全部监控"
            )
            self.create_infobar("服务监控", "已开启所有服务监控")

    def stop_all_monitoring(self):
        """停止所有服务的监控"""
        for sid, info in self.monitoring_services.items():
            info['monitoring'] = False

            # 查找表格中的监控开关并设置状态
            for row in range(self.monitoring_table.rowCount()):
                monitor_switch = self.monitoring_table.cellWidget(row, 1)
                if monitor_switch and monitor_switch.property("service_id") == sid:
                    monitor_switch.setChecked(False)
                    break

            # 更新状态显示
            if 'status_label' in info and info['status_label']:
                try:
                    info['status'] = "未监控"
                    info['status_label'].setText("未监控")
                    info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['未监控']};")
                except RuntimeError:
                    pass

        # 停止监控定时器
        self.monitoring_timer.stop()

        # 只有在用户手动操作时才记录，加载服务时不记录
        if not self.loading_services:
            # 记录停止所有监控
            self.add_monitoring_record(
                service_name="所有服务",
                status="监控状态变更",
                operation="关闭全部监控"
            )
            self.create_infobar("服务监控", "已停止所有服务监控")

    def check_all_services(self):
        """检查所有开启监控的服务状态"""
        current_time = time.time()

        for sid, info in list(self.monitoring_services.items()):
            if not info['monitoring']:
                continue

            # 检查是否到达检查时间
            if current_time - info['last_check'] < info['interval']:
                continue

            # 更新最后检查时间
            info['last_check'] = current_time

            # 更新状态为"检查中..."
            if 'status_label' in info and info['status_label']:
                try:
                    info['status'] = "检查中..."
                    info['status_label'].setText("检查中...")
                    info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['检查中...']};")
                except RuntimeError:
                    pass

            # 异步检查服务状态
            worker = Worker(self.check_service_status, sid, info['service_path'])
            worker.signals.finished.connect(self.handle_service_status_result)
            self.thread_pool.start(worker)

    def check_service_status(self, sid, service_path):
        """检查单个服务状态"""
        try:
            # 使用空请求测试服务
            result = self.service_tester._test_single(service_path, {"data": {}})
            if ("data" in result and not result["data"]["flag"] and
                    result["data"][
                        "result"] == "模型调用异常, 原因:ConnectException: Connection refused (Connection refused)"):
                return sid, False

            return sid, True  # 服务正常
        except Exception as e:
            logger.warning(f"服务 {sid} 状态检查失败: {str(e)}")
            return sid, False  # 服务异常

    def handle_service_status_result(self, result):
        """处理服务状态检查结果"""
        sid, is_healthy = result
        if sid not in self.monitoring_services:
            return

        info = self.monitoring_services[sid]
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 记录监控结果
        if is_healthy:
            self.add_monitoring_record(
                service_name=info['service_name'],
                status="成功",
                operation="服务正常"
            )
        else:
            self.add_monitoring_record(
                service_name=info['service_name'],
                status="失败",
                operation="服务异常"
            )

        # 更新状态显示
        if is_healthy:
            info['status'] = "成功"
            if 'status_label' in info and info['status_label']:
                try:
                    info['status_label'].setText("成功")
                    info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['成功']};")
                except RuntimeError:
                    pass
            info['restart_count'] = 0  # 重置重启计数
        else:
            info['status'] = "失败"
            if 'status_label' in info and info['status_label']:
                try:
                    info['status_label'].setText("失败")
                    info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['失败']};")
                except RuntimeError:
                    pass

            # 检查是否需要自动重启
            if info['auto_restart']:
                self.handle_auto_restart(sid, info)

    def handle_auto_restart(self, sid, info):
        """处理自动重启逻辑"""
        current_time = time.time()

        # 防止短时间内重复重启
        if current_time - info['last_restart'] < 30:  # 30秒冷却时间
            return

        # 连续失败重启次数限制
        if info['restart_count'] >= info['max_restart']:
            warning_msg = f"服务 {info['service_name']} 连续重启{info['max_restart']}次失败，已停止自动重启"
            self.create_warningbar(f"服务 {info['service_name']} 连续重启失败", warning_msg)
            info['auto_restart'] = False
            # 更新自动重启开关状态
            self.update_auto_restart_switch(sid, False)

            # 记录监控记录
            self.add_monitoring_record(
                service_name=info['service_name'],
                status="警告",
                operation=warning_msg
            )
            return

        # 执行重启
        info['restart_count'] += 1
        info['last_restart'] = current_time

        # 记录监控记录
        self.add_monitoring_record(
            service_name=info['service_name'],
            status="自动重启",
            operation=f"第 {info['restart_count']}/{info['max_restart']} 次自动重启"
        )

        # 更新状态为"重启中..."
        if 'status_label' in info and info['status_label']:
            try:
                info['status'] = "重启中..."
                info['status_label'].setText("重启中...")
                info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['重启中...']};")
            except RuntimeError:
                pass

        worker = Worker(self.editor.config.api_tools.get("service_reonline"), sid)
        worker.signals.finished.connect(lambda: self.on_restart_finished(sid))
        worker.signals.error.connect(lambda e: self.on_restart_error(sid, e))
        self.thread_pool.start(worker)

    def on_restart_finished(self, sid):
        """重启成功处理"""
        if sid in self.monitoring_services:
            info = self.monitoring_services[sid]
            self.create_successbar(f"服务 {info['service_name']} 重启成功")

            # 记录监控记录
            self.add_monitoring_record(
                service_name=info['service_name'],
                status="成功",
                operation="自动重启成功"
            )

            # 重启后状态暂时设为检查中
            if 'status_label' in info and info['status_label']:
                try:
                    info['status'] = "检查中..."
                    info['status_label'].setText("检查中...")
                    info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['检查中...']};")
                except RuntimeError:
                    pass

    def on_restart_error(self, sid, error):
        """重启失败处理"""
        if sid in self.monitoring_services:
            info = self.monitoring_services[sid]
            self.create_errorbar(f"服务 {info['service_name']} 重启失败", str(error))

            # 记录监控记录
            self.add_monitoring_record(
                service_name=info['service_name'],
                status="失败",
                operation=f"自动重启失败: {str(error)}"
            )

            # 重启失败后状态仍为失败
            if 'status_label' in info and info['status_label']:
                try:
                    info['status'] = "失败"
                    info['status_label'].setText("失败")
                    info['status_label'].setStyleSheet(f"color: {self.STATUS_COLORS['失败']};")
                except RuntimeError:
                    pass

    def update_auto_restart_switch(self, sid, state):
        """更新表格中自动重启开关的状态"""
        for row in range(self.monitoring_table.rowCount()):
            restart_switch = self.monitoring_table.cellWidget(row, 4)
            if restart_switch and restart_switch.property("service_id") == sid:
                restart_switch.setChecked(state)
                break

    def add_monitoring_record(self, service_name, status, operation):
        """添加监控记录"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 确保操作描述不为空
        if not operation:
            operation = "未知操作"

        # 添加到记录列表
        self.monitoring_records.insert(0, {
            'time': timestamp,
            'service_name': service_name,
            'status': status,
            'operation': operation
        })

        # 限制记录数量
        if len(self.monitoring_records) > self.record_limit:
            self.monitoring_records = self.monitoring_records[:self.record_limit]

        # 更新记录表格
        self.update_record_table()

    # ===== 通知方法 =====
    def create_successbar(self, title: str, content: str = "", duration: int = 5000):
        if self.home.stackedWidget.currentWidget().objectName() != self.objectName():
            return
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM,
            duration=duration,
            parent=self
        )

    def create_errorbar(self, title: str, content: str = "", duration=5000):
        if self.home.stackedWidget.currentWidget().objectName() != self.objectName():
            return
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM,
            duration=duration,
            parent=self
        )

    def create_warningbar(self, title: str, content: str = "", duration=5000):
        if self.home.stackedWidget.currentWidget().objectName() != self.objectName():
            return
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM,
            duration=duration,
            parent=self
        )

    def create_infobar(self, title: str, content: str = "", duration=5000):
        if self.home.stackedWidget.currentWidget().objectName() != self.objectName():
            return
        InfoBar.info(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM,
            duration=duration,
            parent=self
        )