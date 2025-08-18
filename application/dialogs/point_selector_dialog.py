import ctypes
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QThreadPool, QPropertyAnimation, QEasingCurve, QDate, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QListWidget, QDateTimeEdit,
    QComboBox, QWidget, QSplitter
)
from qfluentwidgets import SearchLineEdit, FastCalendarPicker, ComboBox

from application.utils.threading_utils import Worker
from application.widgets.trend_plot_widget import TrendPlotWidget
from application.utils.utils import (
    load_point_cache,
    save_point_cache,
    styled_dt,
    get_icon,
    get_button_style_sheet,
)


class PointSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setObjectName("测点选择")
        # 添加以下代码
        self.setWindowFlags(Qt.Window |
                            Qt.WindowMinimizeButtonHint |
                            Qt.WindowMaximizeButtonHint |
                            Qt.WindowCloseButtonHint)
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.thread_pool = QThreadPool.globalInstance()
        self.selected_point = None
        # 窗口设置
        self.setWindowTitle("选择测点")
        self.resize(1000, 600)
        font = QFont("Microsoft YaHei", 10)
        self.setFont(font)
        self.setStyleSheet("""
            QWidget { background:#f5f5f5; font-family:'Microsoft YaHei'; font-size:10pt; }
            QLineEdit,QDateTimeEdit,QComboBox { padding:4px; border:1px solid #ccc; border-radius:4px; }
            QPushButton { padding:6px 12px; background:#0078d7; color:white; border:none; border-radius:4px; }
            QPushButton:hover { background:#005a9e; }
            QListWidget,QTableWidget,pg.PlotWidget { background:white; border:1px solid #ccc; }
            QHeaderView::section { background:#e0e0e0; padding:4px; border:none; }
        """)
        pg.setConfigOptions(useOpenGL=False, antialias=False)
        # 顶部：搜索框 + 全屏
        top_layout = QHBoxLayout()
        # 增加线上搜索与线下搜索下拉框
        self.cmb_search_type = ComboBox(self)
        self.cmb_search_type.addItems(["平台搜索", "本地搜索"])
        self.cmb_search_type.setCurrentIndex(0)
        self.cmb_search_type.currentIndexChanged.connect(self.change_search_type)
        self.search_input = SearchLineEdit()
        self.search_input.returnPressed.connect(self.filter_table)
        self.search_input.searchSignal.connect(self.filter_table)
        self.search_input.clearSignal.connect(self.filter_table)
        top_layout.addWidget(QLabel("类型:"))
        top_layout.addWidget(self.cmb_search_type)
        top_layout.addWidget(QLabel("搜索:"))
        top_layout.addWidget(self.search_input)

        self.btn_toggle_trend = QPushButton()
        self.btn_toggle_trend.setIcon(get_icon("趋势分析"))
        self.btn_toggle_trend.setStyleSheet(get_button_style_sheet())
        self.btn_toggle_trend.setToolTip("趋势分析")  # 将文字作为 tooltip
        self.btn_toggle_trend.setCheckable(True)
        self.btn_toggle_trend.clicked.connect(self._toggle_trend_panel)
        top_layout.addWidget(self.btn_toggle_trend)
        # 左侧：点类型列表
        self.type_list = QListWidget()
        self.type_list.setFixedWidth(150)
        self.type_list.itemClicked.connect(self.on_type_selected)
        self.type_list.setStyleSheet("""
            QListWidget {
                font-size: 13px;
                padding: 4px;
                border: 1px solid #ccc;
                background-color: #fafafa;
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
                background-color: #1890ff;
                color: white;
            }
        """)

        # 右上：手动输入 + 趋势分析
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("手动输入:"))
        self.manual_input = QLineEdit("")
        self.manual_input.setPlaceholderText("输入后按回车确认")
        self.manual_input.returnPressed.connect(self.accept_selection)
        manual_layout.addWidget(self.manual_input)

        # 表格
        self.table = QTableWidget(0, 0)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.cellClicked.connect(self._on_table_clicked)
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("""
                QTableWidget::item:selected {
                    background-color: #1890ff;
                    color: white;
                }
            """)

        # 趋势分析面板
        self.trend_panel = QWidget()
        trend_layout = QVBoxLayout(self.trend_panel)
        trend_layout.setContentsMargins(10, 5, 10, 5)
        trend_layout.setSpacing(5)
        # 动画控制（加入初始化）
        self.trend_anim = QPropertyAnimation(self.trend_panel, b"maximumHeight")
        self.trend_anim.setDuration(250)  # 动画时长，单位毫秒
        self.trend_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.trend_expanded = False  # 初始未展开
        # 控件行
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(5)
        # ➤ 左上：当前曲线名标签
        self.curve_name_label = QLabel("当前曲线: --")
        self.curve_name_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 10pt;")
        ctrl_layout.addWidget(self.curve_name_label)
        # 空间拉伸项（推控件靠右）
        ctrl_layout.addStretch()

        self.start_dt = FastCalendarPicker(self)
        self.end_dt = FastCalendarPicker(self)
        now = QDate.currentDate()
        self.end_dt.setDate(now)
        self.start_dt.setDate(now.addDays(-1))

        # 采样
        self.cmb_sample = QComboBox()
        self.cmb_sample.setFont(QFont("Microsoft YaHei", 10))
        self.cmb_sample.setFixedWidth(80)
        self.cmb_sample.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 15px;
                background-color: white;
                color: black; /* 默认字体颜色 */
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black; /* 鼠标悬浮时字体颜色 */
            }
        """
        )
        for v in (600, 2000, 5000):
            self.cmb_sample.addItem(f"{v}", v)

        # 按钮
        self.btn_apply_trend = QPushButton()
        self.btn_apply_trend.setIcon(get_icon("change"))
        self.btn_apply_trend.setStyleSheet(get_button_style_sheet())
        self.btn_apply_trend.setToolTip("更新曲线")
        self.btn_apply_trend.clicked.connect(self.update_trend)

        # 添加控件（靠右）
        ctrl_layout.addWidget(QLabel("开始:"))
        ctrl_layout.addWidget(self.start_dt)
        ctrl_layout.addWidget(QLabel("结束:"))
        ctrl_layout.addWidget(self.end_dt)
        ctrl_layout.addWidget(QLabel("采样数:"))
        ctrl_layout.addWidget(self.cmb_sample)
        ctrl_layout.addWidget(self.btn_apply_trend)

        trend_layout.addLayout(ctrl_layout)
        # trend_plot 和 statistics_panel 横向排列
        trend_body_layout = QHBoxLayout()
        # 新增统计信息区域
        self.statistics_panel = QWidget()
        stats_layout = QVBoxLayout(self.statistics_panel)
        self.mean_label = QLabel("平均值: --", self)
        self.max_label = QLabel("最大值: --", self)
        self.min_label = QLabel("最小值: --", self)
        self.std_dev_label = QLabel("标准差: --", self)

        stats_layout.addWidget(self.mean_label)
        stats_layout.addWidget(self.max_label)
        stats_layout.addWidget(self.min_label)
        stats_layout.addWidget(self.std_dev_label)

        trend_body_layout.addWidget(self.statistics_panel, stretch=1)

        self.trend_plot = TrendPlotWidget(legend=False, parent=self.parent, show_service=False)
        trend_body_layout.addWidget(self.trend_plot, stretch=9)
        self.trend_panel.hide()

        trend_layout.addLayout(trend_body_layout)
        # 主布局
        main = QVBoxLayout(self)
        main.addLayout(top_layout)
        body = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("点类型", alignment=Qt.AlignCenter))
        left.addWidget(self.type_list)
        body.addLayout(left)
        # 替换你原来的 right 部分布局：
        right = QVBoxLayout()
        right.addLayout(manual_layout)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.trend_panel)
        splitter.setSizes([350, 250])  # 初始高度按需调整

        right.addWidget(splitter)
        body.addLayout(right)
        main.addLayout(body)

        # 加载 & 异步拉取
        self.all_points = load_point_cache()
        if self.all_points:
            self.populate_ui(self.all_points)

        # 添加防抖定时器 (300ms)
        self.fetch_debounce_timer = QTimer()
        self.fetch_debounce_timer.setSingleShot(True)
        self.fetch_debounce_timer.timeout.connect(self._execute_pending_fetch)
        self.pending_fetch_params = None  # 存储待执行的参数

    def change_search_type(self, type_id: int):
        if type_id == 0:
            self.search_input.returnPressed.connect(self.filter_table)
            self.search_input.searchSignal.connect(self.filter_table)
            self.search_input.clearSignal.connect(self.filter_table)
            print("切换为线上搜索")
        else:
            self.search_input.returnPressed.connect(self.filter_table_offline)
            self.search_input.searchSignal.connect(self.filter_table_offline)
            self.search_input.clearSignal.connect(self.filter_table_offline)
            print("切换为线下搜索")

    def set_curve_name(self, name: str):
        self.curve_name_label.setText(f"当前曲线: {name}")

    def start_fetching(self, fetchers, current_text: str = ""):
        """修改为防抖版本，不立即执行获取，而是等待一段时间"""
        current_text = current_text.split("\n")[0]
        self.manual_input.setText(current_text)
        # 存储参数，等待防抖
        self.pending_fetch_params = (fetchers, current_text)
        # 重置定时器，如果在300ms内再次调用则重新计时
        self.fetch_debounce_timer.start(300)

    def _execute_pending_fetch(self):
        """执行实际的获取操作"""
        if self.pending_fetch_params is None:
            return

        fetchers, current_text = self.pending_fetch_params

        # 检查缓存中是否已有数据，避免不必要的请求
        if not self._should_fetch_new_data(current_text):
            self.highlight_current_point(self.all_points, current_text)
            return

        w = Worker(fetchers)
        w.signals.progress.connect(self._on_fetch_complete)
        w.signals.finished.connect(lambda results: self.highlight_current_point(results, current_text))
        self.thread_pool.start(w)

        # 清空待处理参数
        self.pending_fetch_params = None

    def _on_fetch_complete(self, results):
        self.all_points.update(results)
        if len(results) > 100: save_point_cache(results)
        self.populate_ui(results)

    def populate_ui(self, results):
        old_set = set(self.type_list.item(i).text() for i in range(self.type_list.count()))

        # 添加新增项
        for t in results:
            if t not in old_set:
                self.type_list.addItem(t)

        # 保持选中状态或默认选第一个
        if self.type_list.count():
            if self.type_list.currentRow() == -1:
                self.type_list.setCurrentRow(0)
            self.on_type_selected(self.type_list.currentItem())

    def on_type_selected(self, item):
        pts = self.all_points.get(item.text(), [])
        headers = list(pts[0].keys()) if pts else []
        self.table.setSortingEnabled(False)
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(0)
        for p in pts:
            r = self.table.rowCount();
            self.table.insertRow(r)
            for c, h in enumerate(headers):
                self.table.setItem(r, c, QTableWidgetItem(str(p.get(h, ""))))
        self.table.setSortingEnabled(True)

    def filter_table(self):
        kw = self.search_input.text().strip().lower()
        search_fetcher = self.parent.config.get_tools_by_type("point-search")
        worker = Worker(search_fetcher, search_text=kw)
        worker.signals.finished.connect(self._on_search_complete)
        self.thread_pool.start(worker)

    def filter_table_offline(self):
        kw = self.search_input.text().strip().lower()
        rows = [p for pts in self.all_points.values() for p in pts
                if any(kw in str(v).lower() for v in p.values())]
        hdrs = [self.table.horizontalHeaderItem(i).text()
                for i in range(self.table.columnCount())]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for p in rows:
            r = self.table.rowCount();
            self.table.insertRow(r)
            for c, h in enumerate(hdrs):
                self.table.setItem(r, c, QTableWidgetItem(str(p.get(h, ""))))
        self.table.setSortingEnabled(True)

    def _on_search_complete(self, results):
        self.all_points.update(results)
        results = [item for item in results.values()][0]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for p in results:
            r = self.table.rowCount();
            self.table.insertRow(r)
            for c, h in enumerate(p.keys()):
                self.table.setItem(r, c, QTableWidgetItem(str(p.get(h, ""))))
        self.table.setSortingEnabled(True)

    def _on_table_clicked(self, row, col):
        # 寻找表头中列名为"测点名"的索引
        point_column_index = -1
        for column_index in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(column_index)
            if header_item and header_item.text() == "测点名":
                point_column_index = column_index
                break

        if point_column_index == -1:
            point_column_index = col

        it = self.table.item(row, point_column_index)
        if it:
            self.selected_point = it.text()
            # 点击后立即更新趋势图
            self.update_trend()

    def _on_table_double_clicked(self, row, col):
        # 寻找表头中列名为"测点名"的索引
        point_column_index = -1
        for column_index in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(column_index)
            if header_item and header_item.text() == "测点名":
                point_column_index = column_index
                break

        if point_column_index == -1:
            point_column_index = col

        # 通过找到的列索引获取数据
        it = self.table.item(row, point_column_index)
        if it:
            self.selected_point = it.text()
            # 更新描述
            self.selected_point_description = self.get_description_for_point(self.selected_point)
            self.accept()

    def accept_selection(self):
        txt = self.manual_input.text().strip()
        if not txt:
            QMessageBox.warning(self, "提示", "请先选择或输入测点后按回车。")
            return
        self.selected_point = txt
        # 同样更新 description
        self.selected_point_description = self.get_description_for_point(txt)
        self.accept()

    def get_description_for_point(self, name):
        for pts in self.all_points.values():
            for pt in pts:
                if name in list(pt.values()):
                    return " | ".join([item for item in list(pt.values())])
        return ""

    def _toggle_trend_panel(self, checked):
        self.trend_anim.stop()

        if checked:
            self.trend_panel.show()
            self.trend_anim.setStartValue(0)
            self.trend_anim.setEndValue(250)  # 或你趋势面板目标高度
            self.trend_anim.start()
            self.trend_expanded = True
        else:
            self.trend_anim.setStartValue(self.trend_panel.height())
            self.trend_anim.setEndValue(0)

            # 动画结束后再 hide
            def on_finished():
                self.trend_panel.hide()
                self.trend_anim.finished.disconnect(on_finished)
                self.trend_expanded = False

            self.trend_anim.finished.connect(on_finished)
            self.trend_anim.start()

        if checked: self.update_trend()

    def update_trend(self):
        self.btn_apply_trend.setEnabled(False)
        self.btn_apply_trend.setIcon(get_icon("沙漏"))
        if not self.selected_point:
            # 清空曲线
            self.trend_plot.clear()
            self.trend_plot.curves = []
            self.set_curve_name("--")
            # 清空统计信息
            self.mean_label.setText("平均值: --")
            self.max_label.setText("最大值: --")
            self.min_label.setText("最小值: --")
            self.std_dev_label.setText("标准差: --")
            return

        self.set_curve_name(self.selected_point)
        start = self.start_dt.getDate().toPyDate()
        end = self.end_dt.getDate().toPyDate()
        sample = self.cmb_sample.currentData()
        worker = Worker(self.parent.config.get_tools_by_type("trenddb-fetcher")[0], self.selected_point, start, end, sample)
        worker.signals.finished.connect(self._on_data_fetched)
        self.thread_pool.start(worker)

    def update_statistics(self, data):
        """ 更新统计信息 """
        mean_value = np.mean(data)
        max_value = np.max(data)
        min_value = np.min(data)
        std_dev = np.std(data)

        self.mean_label.setText(f"平均值: {mean_value:.2f}")
        self.max_label.setText(f"最大值: {max_value:.2f}")
        self.min_label.setText(f"最小值: {min_value:.2f}")
        self.std_dev_label.setText(f"标准差: {std_dev:.2f}")

    def _on_data_fetched(self, data):
        self.trend_plot.clear()
        self.trend_plot.curves = []

        # 检查是否还有选中的测点
        if not self.selected_point:
            # 清空统计信息
            self.mean_label.setText("平均值: --")
            self.max_label.setText("最大值: --")
            self.min_label.setText("最小值: --")
            self.std_dev_label.setText("标准差: --")
            return

        ts, ys = data.get(self.selected_point, (None, None))
        if ts is None or len(ts) == 0:
            # 清空统计信息
            self.mean_label.setText("平均值: --")
            self.max_label.setText("最大值: --")
            self.min_label.setText("最小值: --")
            self.std_dev_label.setText("标准差: --")
            return

        # 绘制曲线
        self.trend_plot.plot_multiple(data)
        self.update_statistics(ys)
        self.btn_apply_trend.setEnabled(True)
        self.btn_apply_trend.setIcon(get_icon("change"))

    def highlight_current_point(self, results, target):
        self.selected_point = target

        # 自动跳转并高亮匹配的行
        manual_text = self.manual_input.text().strip()
        if manual_text:
            for point_type, points in results.items():
                for point in points:
                    if any(manual_text == str(v) for v in point.values()):
                        # 切换到匹配的点类型
                        items = self.type_list.findItems(point_type, Qt.MatchExactly)
                        if items:
                            self.type_list.setCurrentItem(items[0])
                            self.on_type_selected(items[0])
                            # 在表格中查找并高亮匹配的行
                            for row in range(self.table.rowCount()):
                                for col in range(self.table.columnCount()):
                                    item = self.table.item(row, col)
                                    if item and item.text() == manual_text:
                                        self.table.selectRow(row)
                                        self.table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                                        return
        # 如果没有匹配项，默认选择第一个点类型
        if self.type_list.count() > 0:
            self.type_list.setCurrentRow(0)
            self.on_type_selected(self.type_list.currentItem())

    def _should_fetch_new_data(self, current_text):
        """检查是否真的需要获取新数据"""
        # 如果缓存中已有数据且不是空搜索，可以跳过获取
        if self.all_points and current_text:
            # 检查current_text是否可能在已有数据中
            for points in self.all_points.values():
                for point in points:
                    if any(current_text in str(v) for v in point.values()):
                        return False
        return True

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
