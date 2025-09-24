import ctypes
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QThreadPool, QPropertyAnimation, QEasingCurve, QDate, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QListWidget, QWidget, QSplitter
)
from qfluentwidgets import (
    SearchLineEdit, ComboBox, PushButton, LineEdit, InfoBar,
    InfoBarPosition, FastCalendarPicker, FluentIcon as FIF
)

from application.utils.threading_utils import Worker
from application.utils.utils import load_point_cache, save_point_cache, get_icon
from application.widgets.trend_plot_widget import TrendPlotWidget


class PointSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName("测点选择")
        self.setWindowFlags(Qt.Window |
                            Qt.WindowMinimizeButtonHint |
                            Qt.WindowMaximizeButtonHint |
                            Qt.WindowCloseButtonHint)
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.thread_pool = QThreadPool.globalInstance()
        self.selected_point = None
        self.selected_point_description = ""

        # ✅ 加载本地缓存
        self.raw_points = load_point_cache() or {}
        self.remote_cache = {}
        self.current_view = []

        # 防抖
        self.fetch_debounce_timer = QTimer()
        self.fetch_debounce_timer.setSingleShot(True)
        self.fetch_debounce_timer.timeout.connect(self._execute_pending_fetch)
        self.pending_fetch_params = None

        # 窗口设置
        self.setWindowTitle("选择测点")
        self.resize(1100, 750)
        font = QFont("Microsoft YaHei", 10)
        self.setFont(font)

        pg.setConfigOptions(useOpenGL=False, antialias=True)

        self.init_ui()

        # 初始化 UI 后填充类型列表
        self.populate_type_list()
        if self.type_list.count() > 0:
            self.type_list.setCurrentRow(0)
            self.on_type_selected(self.type_list.item(0))

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # === 顶部：搜索类型 + 搜索框 ===
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        self.cmb_search_type = ComboBox()
        self.cmb_search_type.addItems(["本地搜索", "平台搜索"])
        self.cmb_search_type.setFixedWidth(100)
        self.cmb_search_type.currentIndexChanged.connect(self.on_search_type_changed)

        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("输入关键词搜索测点...")
        self.search_input.searchSignal.connect(self.on_search)
        self.search_input.clearSignal.connect(self.on_search_clear)

        top_layout.addWidget(QLabel("搜索类型:"))
        top_layout.addWidget(self.cmb_search_type)
        top_layout.addWidget(QLabel("搜索:"))
        top_layout.addWidget(self.search_input, 1)
        main_layout.addLayout(top_layout)

        # === 主体：左类型 + 右内容 ===
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # === 左侧：带标题的测点类型容器 ===
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 标题
        title_widget = QLabel("测点类型列表")
        title_widget.setAlignment(Qt.AlignCenter)
        title_widget.setStyleSheet("""
            background-color: #409EFF;
            color: white;
            font-weight: bold;
            font-size: 10pt;
            padding: 6px 0px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        """)

        # 测点类型列表
        self.type_list = QListWidget()
        self.type_list.setStyleSheet("""
            QListWidget {
                font-size: 13px;
                padding: 4px;
                border: 1px solid #409EFF;        /* 边框与标题同色 */
                border-top: none;                 /* 顶部边框去掉，与标题融合 */
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                height: 30px;
                padding-left: 10px;
                color: #333;
            }
            QListWidget::item:hover {
                background-color: #e6f7ff;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """)

        # 添加到容器
        left_layout.addWidget(title_widget)
        left_layout.addWidget(self.type_list)

        # 连接信号
        self.type_list.itemClicked.connect(self.on_type_selected)

        # 右侧：手动输入 + 表格 + 趋势
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # 手动输入
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("手动输入:"))
        self.manual_input = LineEdit()
        self.manual_input.setPlaceholderText("输入后按回车确认")
        self.manual_input.returnPressed.connect(self.accept_selection)
        manual_layout.addWidget(self.manual_input)
        right_layout.addLayout(manual_layout)

        # 表格
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.cellClicked.connect(self._on_table_clicked)
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 1px solid #ccc;
                gridline-color: #eee;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """)
        right_layout.addWidget(self.table)

        # ================================
        # 趋势分析面板
        # ================================
        self.trend_panel = QWidget()
        self.trend_panel.setStyleSheet("background: white; border-top: 1px solid #ddd;")
        trend_layout = QVBoxLayout(self.trend_panel)
        trend_layout.setContentsMargins(10, 8, 10, 8)
        trend_layout.setSpacing(6)

        # 动画控制
        self.trend_anim = QPropertyAnimation(self.trend_panel, b"maximumHeight")
        self.trend_anim.setDuration(250)
        self.trend_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.trend_expanded = False
        self.trend_panel.setMaximumHeight(0)
        self.trend_panel.setMinimumHeight(0)
        # 控制行
        ctrl_layout = QHBoxLayout()
        self.curve_name_label = QLabel("当前曲线: --")
        self.curve_name_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 10pt;")
        ctrl_layout.addWidget(self.curve_name_label)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(QLabel("开始:"))
        self.start_dt = FastCalendarPicker(self)
        self.end_dt = FastCalendarPicker(self)
        now = QDate.currentDate()
        self.end_dt.setDate(now)
        self.start_dt.setDate(now.addDays(-1))

        ctrl_layout.addWidget(self.start_dt)
        ctrl_layout.addWidget(QLabel("结束:"))
        ctrl_layout.addWidget(self.end_dt)

        self.cmb_sample = ComboBox()
        self.cmb_sample.addItems(["600", "2000", "5000"])
        self.cmb_sample.setCurrentIndex(0)
        ctrl_layout.addWidget(QLabel("采样数:"))
        ctrl_layout.addWidget(self.cmb_sample)

        self.btn_apply_trend = PushButton(get_icon("change"), "更新")
        self.btn_apply_trend.clicked.connect(self.update_trend)
        ctrl_layout.addWidget(self.btn_apply_trend)

        trend_layout.addLayout(ctrl_layout)

        # 趋势图 + 统计信息
        body_layout = QHBoxLayout()
        body_layout.setSpacing(10)

        # 统计信息
        self.statistics_panel = QWidget()
        stats_layout = QVBoxLayout(self.statistics_panel)
        self.mean_label = QLabel("平均值: --")
        self.max_label = QLabel("最大值: --")
        self.min_label = QLabel("最小值: --")
        self.std_dev_label = QLabel("标准差: --")
        for label in [self.mean_label, self.max_label, self.min_label, self.std_dev_label]:
            label.setStyleSheet("font-size: 10pt; padding: 2px 0;")
        stats_layout.addWidget(self.mean_label)
        stats_layout.addWidget(self.max_label)
        stats_layout.addWidget(self.min_label)
        stats_layout.addWidget(self.std_dev_label)
        stats_layout.addStretch()

        self.trend_plot = TrendPlotWidget(legend=False, parent=self.parent, show_service=False)
        self.trend_plot.getPlotItem().showGrid(x=True, y=True, alpha=0.3)

        body_layout.addWidget(self.statistics_panel, stretch=1)
        body_layout.addWidget(self.trend_plot, stretch=5)
        trend_layout.addLayout(body_layout)

        # ================================
        # 折叠按钮
        # ================================
        self.btn_toggle_trend = PushButton(text="展开趋势分析", icon=FIF.ADD, parent=self)
        self.btn_toggle_trend.setFixedHeight(32)
        self.btn_toggle_trend.clicked.connect(self._toggle_trend_panel)

        # 布局顺序：表格 → 按钮 → 趋势面板
        right_layout.addWidget(self.btn_toggle_trend)
        right_layout.addWidget(self.trend_panel)

        # 设置伸缩比例
        right_layout.setStretch(0, 0)  # 手动输入
        right_layout.setStretch(1, 1)  # 表格（占满）
        right_layout.setStretch(2, 0)  # 按钮
        right_layout.setStretch(3, 1)  # 趋势面板

        # 添加到 splitter
        splitter.addWidget(left_container)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)  # 右侧占满

        main_layout.addWidget(splitter)

    def start_fetching(self, fetchers, current_text: str):
        current_text = current_text.strip().split("\n")[0]
        self.manual_input.setText(current_text)
        self.pending_fetch_params = (fetchers, current_text)
        self.fetch_debounce_timer.start(300)

    def _execute_pending_fetch(self):
        if not self.pending_fetch_params:
            return
        fetchers, current_text = self.pending_fetch_params
        is_search = bool(current_text)
        worker = Worker(fetchers, **({"search_text": current_text} if is_search else {}))
        worker.signals.finished.connect(
            lambda results: self._on_fetch_complete(results, is_search, current_text)
        )
        self.thread_pool.start(worker)
        self.pending_fetch_params = None

    def _on_fetch_complete(self, results, is_search: bool, keyword: str):
        if is_search:
            flat_results = [item for sublist in results.values() for item in sublist]
            self.remote_cache[keyword] = flat_results
            self.current_view = flat_results
            self.refresh_table(flat_results)
        else:
            self.raw_points.update(results)
            save_point_cache(results)
            self.populate_type_list()
            if self.type_list.count() > 0:
                self.type_list.setCurrentRow(0)
                self.on_type_selected(self.type_list.item(0))

    def populate_type_list(self):
        self.type_list.clear()
        for t in sorted(self.raw_points.keys()):
            self.type_list.addItem(t)

    def on_type_selected(self, item):
        if not item:
            return
        data = self.raw_points.get(item.text(), [])
        self.current_view = data
        self.refresh_table(data)

    def on_search_type_changed(self, index):
        self.search_input.searchSignal.disconnect()
        if index == 0:
            self.search_input.searchSignal.connect(self.filter_table_offline)
        else:
            self.search_input.searchSignal.connect(self.on_search)

    def on_search(self):
        kw = self.search_input.text().strip()
        if not kw:
            self.on_search_clear()
            return
        fetchers = self.parent.config.get_tools_by_type("point-search")
        if fetchers:
            self.start_fetching(fetchers, kw)

    def on_search_clear(self):
        item = self.type_list.currentItem()
        if item:
            self.on_type_selected(item)

    def filter_table_offline(self):
        kw = self.search_input.text().strip().lower()
        if not kw:
            self.on_search_clear()
            return
        filtered = [
            p for pts in self.raw_points.values() for p in pts
            if any(kw in str(v).lower() for v in p.values())
        ]
        self.current_view = filtered
        self.refresh_table(filtered)

    def refresh_table(self, data_list):
        self.table.clearContents()
        self.table.setRowCount(0)
        if not data_list:
            return
        headers = list(data_list[0].keys())
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        for p in data_list:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, h in enumerate(headers):
                self.table.setItem(row, col, QTableWidgetItem(str(p.get(h, ""))))
        self.table.setSortingEnabled(True)

    def _on_table_clicked(self, row, col):
        name = self.get_point_name_from_row(row)
        if name:
            self.selected_point = name
            if self.trend_expanded:
                self.update_trend()

    def _on_table_double_clicked(self, row, col):
        name = self.get_point_name_from_row(row)
        if name:
            self.selected_point = name
            self.selected_point_description = self.get_description_for_point(name)
            self.accept()

    def get_point_name_from_row(self, row):
        for col in range(self.table.columnCount()):
            if self.table.horizontalHeaderItem(col).text() == "测点名":
                item = self.table.item(row, col)
                return item.text() if item else ""
        return self.table.item(row, 0).text() if self.table.item(row, 0) else ""

    def get_description_for_point(self, name):
        for pts in list(self.raw_points.values()) + list(self.remote_cache.values()):
            for pt in pts:
                if name in pt.values():
                    return " | ".join(str(v) for v in pt.values())
        return name

    def accept_selection(self):
        txt = self.manual_input.text().strip()
        if not txt:
            InfoBar.warning(
                title="提示",
                content="请输入测点名",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1500
            )
            return
        self.selected_point = txt
        self.selected_point_description = self.get_description_for_point(txt)
        self.accept()

    def _toggle_trend_panel(self):
        self.trend_anim.stop()

        if self.trend_expanded:
            # 收起
            self.trend_anim.setStartValue(self.trend_panel.height())
            self.trend_anim.setEndValue(0)
            self.btn_toggle_trend.setText("展开趋势分析")
            self.btn_toggle_trend.setIcon(FIF.ADD)
            self.trend_expanded = False
        else:
            # 展开
            self.trend_panel.show()
            self.trend_anim.setStartValue(0)
            self.trend_anim.setEndValue(800)  # 更高
            self.btn_toggle_trend.setText("收起趋势分析")
            self.btn_toggle_trend.setIcon(FIF.REMOVE)
            self.trend_expanded = True
            self.update_trend()

        def on_finished():
            if self.trend_expanded:
                self.trend_panel.setMaximumHeight(10000)
            else:
                self.trend_panel.setMaximumHeight(0)
                self.trend_panel.hide()
            self.trend_anim.finished.disconnect(on_finished)

        self.trend_anim.finished.connect(on_finished)
        self.trend_anim.start()

    def update_trend(self):
        self.btn_apply_trend.setEnabled(False)
        self.btn_apply_trend.setIcon(get_icon("沙漏"))
        if not self.selected_point:
            self.trend_plot.clear()
            self.curve_name_label.setText("当前曲线: --")
            self.clear_stats()
            self.btn_apply_trend.setEnabled(True)
            self.btn_apply_trend.setIcon(get_icon("change"))
            return

        self.curve_name_label.setText(f"当前曲线: {self.selected_point}")
        start = self.start_dt.date.toPyDate()
        end = self.end_dt.date.toPyDate()
        sample = int(self.cmb_sample.currentText())

        worker = Worker(
            self.parent.config.get_tools_by_type("trenddb-fetcher")[0],
            self.selected_point, start, end, sample
        )
        worker.signals.finished.connect(self._on_data_fetched)
        self.thread_pool.start(worker)

    def _on_data_fetched(self, data):
        self.trend_plot.clear()
        ts, ys = data.get(self.selected_point, (None, None))
        if ts is None or len(ts) == 0:
            self.clear_stats()
            self.btn_apply_trend.setEnabled(True)
            self.btn_apply_trend.setIcon(get_icon("change"))
            return

        self.trend_plot.plot_multiple(data)
        self.update_stats(ys)
        self.btn_apply_trend.setEnabled(True)
        self.btn_apply_trend.setIcon(get_icon("change"))

    def update_stats(self, data):
        mean_val = np.mean(data)
        max_val = np.max(data)
        min_val = np.min(data)
        std_val = np.std(data)
        self.mean_label.setText(f"平均值: {mean_val:.2f}")
        self.max_label.setText(f"最大值: {max_val:.2f}")
        self.min_label.setText(f"最小值: {min_val:.2f}")
        self.std_dev_label.setText(f"标准差: {std_val:.2f}")

    def clear_stats(self):
        self.mean_label.setText("平均值: --")
        self.max_label.setText("最大值: --")
        self.min_label.setText("最小值: --")
        self.std_dev_label.setText("标准差: --")

    def nativeEvent(self, eventType, message):
        if eventType == b'windows_generic_MSG':
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x00A3:
                if self.isMaximized():
                    self.showNormal()
                else:
                    self.showMaximized()
                return True, 0
        return super().nativeEvent(eventType, message)