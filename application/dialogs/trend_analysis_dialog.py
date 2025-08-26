import ctypes
import datetime

import matplotlib
import numpy as np
from PyQt5.QtCore import Qt, QThreadPool, QTimer, QRect, QTime, QDateTime
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFrame, QSizePolicy
)
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
    QSplitter,
    QComboBox,
    QWidget,
    QApplication,
    QStyle,
)
from loguru import logger
from qfluentwidgets import FluentIcon as FIF, ComboBox, SwitchButton, CommandBar, Action, TransparentTogglePushButton
from qfluentwidgets import SearchLineEdit, InfoBar, InfoBarPosition, Dialog, FastCalendarPicker, CompactTimeEdit, \
    ToolButton, TogglePushButton

from application.utils.threading_utils import Worker
from application.widgets.color_picker import ColorComboBox
from application.widgets.draggable_lines import DraggableLine

# 配置matplotlib支持中文
try:
    matplotlib.rcParams["font.sans-serif"] = [
        "SimHei",
        "Microsoft YaHei",
        "SimSun",
        "KaiTi",
        "FangSong",
        "Arial Unicode MS",
    ]
    matplotlib.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题
except:
    pass  # 如果字体设置失败，使用默认字体
from application.utils.utils import (
    get_icon,
    get_button_style_sheet, load_point_cache, save_point_cache
)
from application.widgets.trend_plot_widget import TrendPlotWidget
from application.widgets.correlation_matrix_widget import CorrelationMatrixWidget


class TrendAnalysisDialog(QDialog):
    def __init__(self, parent=None, home=None):
        super().__init__(parent)
        self.setObjectName("趋势分析")
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.parent = parent
        self.home = home
        self.thread_pool = QThreadPool.globalInstance()

        # === 优化点1: 数据源明确分离 ===
        # 存储所有本地测点数据，是数据的“唯一真相源”
        self.local_cache = {}
        # 当前在左侧列表中显示的测点列表（经过搜索和过滤后的结果）
        self.displayed_items = []

        self.point_type = None
        self.selected_points = []
        self.cut_lines = []
        self.partitioning = False
        self.data_cache = {}  # 缓存数据，用于多种图表展示
        self.current_plot_type = 0  # 默认为曲线图
        self.setWindowTitle("趋势分析")
        self.color = "#FF0000"
        # 设置字体
        self.setFont(QFont("Microsoft YaHei", 10))
        # 添加窗口标志
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        # 构建UI
        self._build_ui()
        self.trend_update_timer = QTimer(self)
        self.trend_update_timer.setSingleShot(True)
        self.trend_update_timer.timeout.connect(self._update_trends)
        self.point_update_timer = QTimer(self)
        self.point_update_timer.setSingleShot(True)
        self.point_update_timer.timeout.connect(self._start_fetch)

    def apply_modern_style(self):
        """应用现代化样式表"""
        self.setStyleSheet(
            """
            QDialog {
                background-color: #f8f9fa;
            }
            QSplitter::handle {
                background-color: #e9ecef;
                margin: 1px;
            }
            QTableWidget {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #e7f5ff;
                selection-color: #212529;
                gridline-color: #e9ecef;
            }
            QTableWidget::item:hover {
                background-color: #f1f3f5;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 6px;
                border: none;
                font-weight: bold;
                color: #495057;
            }
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
            QLineEdit:hover {
                border-color: #adb5bd;
            }
            QLineEdit:focus {
                border-color: #4dabf7;
            }
            QPushButton {
                background-color: #339af0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #228be6;
            }
            QPushButton:pressed {
                background-color: #1c7ed6;
            }
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
            QComboBox:hover {
                border-color: #adb5bd;
                color: #212529;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(:/icons/arrow_down.png);
                width: 12px;
                height: 12px;
            }
            QLabel {
                color: #495057;
            }
            QScrollBar:vertical {
                border: none;
                background: #f8f9fa;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #adb5bd;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #868e96;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #f8f9fa;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #adb5bd;
                border-radius: 5px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #868e96;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """
        )

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        # 创建水平分割器
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(6)  # 加宽到6px，更容易点击
        self.splitter.setStyleSheet('''
            QSplitter::handle {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 #dcdcdc, stop:1 #eaeaea);
                border: 1px solid #bbbbbb;
            }
            QSplitter::handle:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 #cfe8f9, stop:1 #a7d4f0);
                border: 1px solid #5ca3cc;
            }
        ''')
        # 禁止折叠分割器的两侧
        for i in range(2):
            self.splitter.setCollapsible(i, False)
        # 左侧：搜索和测点列表
        left = QWidget()
        left.setObjectName("leftPanel")
        left.setStyleSheet(
            "#leftPanel {background-color: #f8f9fa; border-radius: 6px;}"
        )
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        # 左侧面板标题 - 简化设计
        left_layout.addSpacing(2)
        # 搜索框和按钮优化
        search_h = QHBoxLayout()
        search_h.setSpacing(8)
        self.cmb_search_type = ComboBox(self)
        self.cmb_search_type.addItems(["本地搜索", "平台搜索"])
        self.cmb_search_type.setCurrentIndex(0)
        # === 优化点2: 统一事件绑定 ===
        # 只绑定一次，由 _perform_search 决定行为
        self.cmb_search_type.currentIndexChanged.connect(self._on_search_mode_changed)
        self.search_input = SearchLineEdit()
        # 只绑定一次，由 _perform_search 决定行为
        self.search_input.returnPressed.connect(self._perform_search)
        self.search_input.searchSignal.connect(self._perform_search)
        self.search_input.clearSignal.connect(self._perform_search)
        search_h.addWidget(self.cmb_search_type)
        search_h.addWidget(self.search_input)
        left_layout.addLayout(search_h)
        # 测点列表增强
        list_frame = QFrame()
        list_frame.setFrameShape(QFrame.StyledPanel)
        list_frame.setStyleSheet(
            """
            QFrame {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
            }
        """
        )
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(1, 1, 1, 1)  # 紧凑的内边距
        list_label = QLabel("可选测点列表 (双击添加)")
        list_label.setStyleSheet("color: #6c757d; font-size: 12px; padding: 2px 5px;")
        list_layout.addWidget(list_label)
        self.left_table = QTableWidget()
        self.left_table.setSortingEnabled(True)
        self.left_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.left_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.left_table.setAlternatingRowColors(True)  # 启用交替行颜色
        self.left_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.left_table.verticalHeader().setVisible(False)  # 隐藏垂直表头
        self.left_table.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #e9ecef;
                selection-background-color: #e7f5ff;
                selection-color: #212529;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """
        )
        self.left_table.cellDoubleClicked.connect(lambda r, c: self._add_point())
        list_layout.addWidget(self.left_table)
        left_layout.addWidget(list_frame, 1)  # 使列表占据剩余空间
        # 右侧：控制区、信息区、曲线
        right = QWidget()
        right.setObjectName("rightPanel")
        right.setStyleSheet(
            "#rightPanel {background-color: #f8f9fa; border-radius: 6px;}"
        )
        # 右侧布局重构
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 8, 10, 8)
        right_layout.setSpacing(8)
        # 已选测点区域
        selected_frame = QFrame()
        selected_layout = QVBoxLayout(selected_frame)
        selected_layout.setContentsMargins(8, 8, 8, 8)
        selected_layout.setSpacing(5)
        parameter_type = QHBoxLayout()
        param_label = QLabel("当前参数类型：")
        parameter_type.addWidget(param_label)
        self.param_type_combo = ComboBox()
        self.param_types = self.parent.config.get_params_name()
        self.param_type_combo.addItems(self.param_types)
        if len(self.param_types) > 0:
            self.param_type_combo.setCurrentText(self.param_types[0])
        self.param_type_combo.currentIndexChanged.connect(self._load_points)
        parameter_type.addWidget(self.param_type_combo)
        self.load_points_btn = QPushButton()
        self.load_points_btn.setIcon(get_icon("save"))
        self.load_points_btn.setToolTip("初始化新加入测点")
        self.load_points_btn.setStyleSheet(get_button_style_sheet())
        self.load_points_btn.clicked.connect(self.add_tags)
        parameter_type.addWidget(self.load_points_btn)
        parameter_type.addStretch()
        # 简化标题与提示
        selected_header = QHBoxLayout()
        selected_title = QLabel("已选测点列表 (双击移除)")
        selected_title.setStyleSheet(
            "color: #495057; font-size: 12px; border: 1px solid #dee2e6;border-radius: 4px;background-color: white;")
        selected_header.addWidget(selected_title)
        selected_layout.addLayout(parameter_type)
        selected_layout.addLayout(selected_header)
        # 表格
        self.selected_table = QTableWidget()
        self.selected_table.setAlternatingRowColors(True)
        self.selected_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.selected_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.selected_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.selected_table.verticalHeader().setVisible(True)
        self.selected_table.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #e9ecef;
                selection-background-color: #e7f5ff;
                selection-color: #212529;
            }
            QTableWidget::item {
                padding: 4px;
                text-align: center;
            }
            QTableWidget::item:first-child {
                width: 50px;
                max-width: 50px;
                min-width: 50px;
            }
        """
        )
        self.selected_table.cellDoubleClicked.connect(lambda r, c: self._remove_point())
        selected_layout.addWidget(self.selected_table)
        right_layout.addWidget(selected_frame)
        # 控制面板：图表类型选择 + 时间选择 + 应用
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background-color: #f1f3f5;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        control_layout = QVBoxLayout(control_frame)
        control_layout.setContentsMargins(8, 6, 8, 6)
        control_layout.setSpacing(6)

        # 控制行
        row3 = QHBoxLayout()
        self.commandBar_row3 = CommandBar(self)
        self.commandBar_row3.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        row3.addWidget(self.commandBar_row3, 0)
        # 图表类型选择
        self.cmb_plot_type = ComboBox()
        self.cmb_plot_type.addItems(["趋势曲线", "频数直方", "相关系数"])
        self.cmb_plot_type.currentIndexChanged.connect(self._on_plot_type_changed)
        self.commandBar_row3.addWidget(self.cmb_plot_type)
        self.commandBar_row3.addSeparator()
        self.range_combo = ComboBox()
        self.range_combo.addItems(
            ["自定义", "最近1小时", "最近12小时", "最近24小时", "最近7天"]
        )

        self.commandBar_row3.addWidget(QLabel("快速选择:"))
        self.commandBar_row3.addWidget(self.range_combo)
        self.commandBar_row3.addSeparator()
        # 时间选择
        current_datetime = QDateTime.currentDateTime()
        start_datetime = current_datetime.addSecs(-12 * 3600)
        self.start_dt = FastCalendarPicker(self)
        self.start_dt.setDate(start_datetime.date())
        self.start_time_edit = CompactTimeEdit(self)
        self.start_time_edit.setTimeRange(QTime(0, 0), QTime(23, 59))
        self.start_time_edit.setTime(start_datetime.time())
        self.end_dt = FastCalendarPicker(self)
        self.end_dt.setDate(current_datetime.date())
        self.end_time_edit = CompactTimeEdit(self)
        self.end_time_edit.setTimeRange(QTime(0, 0), QTime(23, 59))
        self.end_time_edit.setTime(current_datetime.time())
        self.commandBar_row3.addWidget(self.start_dt)
        self.commandBar_row3.addWidget(self.start_time_edit)
        self.commandBar_row3.addWidget(QLabel("~"))
        self.commandBar_row3.addWidget(self.end_dt)
        self.commandBar_row3.addWidget(self.end_time_edit)
        # 采样选择
        sample_label = QLabel("采样:")
        self.commandBar_row3.addWidget(sample_label)
        self.cmb_sample = ComboBox()
        self.cmb_sample.addItems([" 600", "2000", "5000"])
        self.commandBar_row3.addWidget(self.cmb_sample)
        # 应用按钮
        self.btn_apply = QPushButton()
        self.btn_apply.setIcon(get_icon("change"))
        self.btn_apply.setToolTip("使用当前设置更新图表")
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.setStyleSheet(get_button_style_sheet())
        self.btn_apply.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_apply.clicked.connect(self._update_trends)
        self.commandBar_row3.addWidget(self.btn_apply)

        # 检查当前时间与设置的时间的关系，以确定当前选择
        now = datetime.datetime.now()
        start, end = self._get_start_end_time()
        time_diff = (now - start).total_seconds()
        # 根据时间差来设置下拉列表当前选项
        if abs((now - end).total_seconds()) < 300:  # 结束时间接近当前时间（5分钟内）
            if 3500 <= time_diff <= 3700:  # 近似1小时
                self.range_combo.setCurrentIndex(1)
            elif 43000 <= time_diff <= 44000:  # 近似12小时
                self.range_combo.setCurrentIndex(2)
            elif 86000 <= time_diff <= 87000:  # 近似24小时
                self.range_combo.setCurrentIndex(3)
            elif 604000 <= time_diff <= 605000:  # 近似7天
                self.range_combo.setCurrentIndex(4)

        control_layout.addLayout(row3)
        right_layout.addWidget(control_frame)
        # 图表区域
        chart_frame = QFrame()
        chart_frame.setObjectName("chartFrame")
        chart_frame.setStyleSheet(
            """
            #chartFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
            }
        """
        )
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(10, 10, 10, 10)
        chart_layout.setSpacing(5)
        # 图表容器
        self.plot_area = QVBoxLayout()
        self.plot_area.setContentsMargins(0, 0, 0, 0)
        chart_layout.addLayout(self.plot_area)
        # 创建图表容器及其子容器
        self.plot_container = QWidget()
        self.plot_container.setStyleSheet("background-color: white;")
        self.plot_container_layout = QVBoxLayout(self.plot_container)
        self.plot_container_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_container_layout.setSpacing(0)
        # 趋势图容器
        self.trend_plot_widget = QWidget()
        self.trend_plot_layout = QVBoxLayout(self.trend_plot_widget)
        self.trend_plot_layout.setContentsMargins(0, 0, 0, 0)
        self.trend_plot_layout.setSpacing(0)
        self.trend_plot = None  # 将在需要时创建
        # 频数直方图容器
        self.histogram_widget = QWidget()
        self.histogram_widget.setStyleSheet("background-color: white;")
        self.histogram_layout = QVBoxLayout(self.histogram_widget)
        self.histogram_layout.setContentsMargins(0, 0, 0, 0)
        self.histogram_layout.setSpacing(8)
        # 相关系数矩阵容器
        self.correlation_widget = QWidget()
        self.correlation_widget.setStyleSheet("background-color: white;")
        self.correlation_layout = QVBoxLayout(self.correlation_widget)
        self.correlation_layout.setContentsMargins(0, 0, 0, 0)
        self.correlation_layout.setSpacing(8)
        # 相关系数矩阵控件会在需要时创建
        self.corr_matrix_widget = None
        # 默认添加趋势图容器
        self.plot_container_layout.addWidget(self.trend_plot_widget)
        # 添加图表容器到主布局
        self.plot_area.addWidget(self.plot_container)
        # 美化的初始占位符
        self.plot_placeholder = QFrame()
        self.plot_placeholder.setMinimumHeight(300)
        self.plot_placeholder.setStyleSheet(
            """
            background-color: #f8f9fa; 
            border: 1px dashed #adb5bd;
            border-radius: 5px;
        """
        )
        # 在占位符中添加提示文本
        placeholder_layout = QVBoxLayout(self.plot_placeholder)
        placeholder_layout.setAlignment(Qt.AlignCenter)
        placeholder_icon = QLabel()
        placeholder_icon.setAlignment(Qt.AlignCenter)
        placeholder_icon.setPixmap(
            QApplication.style()
            .standardIcon(QStyle.SP_FileDialogInfoView)
            .pixmap(48, 48)
        )
        placeholder_layout.addWidget(placeholder_icon)
        placeholder_text = QLabel("选择测点并点击'应用'按钮加载数据")
        placeholder_text.setAlignment(Qt.AlignCenter)
        placeholder_text.setStyleSheet("color: #6c757d; font-size: 14px;")
        placeholder_layout.addWidget(placeholder_text)
        placeholder_subtext = QLabel("可以从左侧列表双击添加测点")
        placeholder_subtext.setAlignment(Qt.AlignCenter)
        placeholder_subtext.setStyleSheet("color: #868e96; font-size: 12px;")
        placeholder_layout.addWidget(placeholder_subtext)
        self.trend_plot_layout.addWidget(self.plot_placeholder)
        right_layout.addWidget(chart_frame, 1)  # 图表区域占据主要空间
        self.range_combo.currentIndexChanged.connect(self._quick_time_range)
        # 主布局组装
        # 将左右两侧添加到分割器
        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        # 设置拉伸因子，使右侧能够自适应填满空间
        self.splitter.setStretchFactor(1, 2)  # 左侧不拉伸
        self.splitter.setStretchFactor(1, 4)  # 增大右侧拉伸比例
        # 初始分割比例设置：减小左侧宽度，确保右侧图表有更多空间
        self.splitter.setSizes([400, self.width() - 400])
        # 将分割器添加到主布局
        main_layout.addWidget(self.splitter)
        # 连接窗口大小变化信号
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._adjust_layout)

    # === 优化点3: 新增统一的搜索入口和模式切换方法 ===
    def _on_search_mode_changed(self):
        """搜索模式切换时，清空搜索框并刷新为完整本地数据"""
        self.search_input.clear()  # 清空输入框
        # 重置为显示全部本地数据
        self._reset_to_full_local()

    def _perform_search(self):
        """统一的搜索入口，根据当前模式决定搜索方式"""
        keyword = self.search_input.text().strip()
        if not keyword:
            # 无关键词时，重置为完整本地数据
            self._reset_to_full_local()
            return

        if self.cmb_search_type.currentText() == "本地搜索":
            self._search_local(keyword)
        else:
            self._search_remote(keyword)

    def _search_local(self, keyword: str):
        """从本地缓存中搜索"""
        results = {}
        # 使用 self.local_cache 作为数据源
        for tag_type, points in self.local_cache.items():
            # 支持多个关键词搜索
            kws = keyword.lower().split()
            matched = [
                p for p in points
                if all(kw in "".join(str(v) for v in p.values()).lower() for kw in kws)
            ]
            if matched:
                results[tag_type] = matched
        # 将搜索结果设置为当前显示列表
        self._update_displayed_items(results)

    def _search_remote(self, keyword: str):
        """调用远程接口搜索"""
        worker = Worker(self.parent.config.get_tools_by_type("point-search"), search_text=keyword)
        worker.signals.finished.connect(self._on_search_complete)
        worker.signals.error.connect(lambda e: self.create_errorbar("搜索失败: " + str(e)))
        self.thread_pool.start(worker)

    def _on_search_complete(self, results: dict):
        """处理远程搜索完成后的结果"""
        # 将远程结果合并到本地缓存（可选策略）
        self._merge_remote_results(results)
        # 将搜索结果直接作为当前显示列表
        self._update_displayed_items(results)

    def _merge_remote_results(self, remote_results: dict):
        """将远程结果合并到本地缓存中，避免重复"""
        for tag_type, points in remote_results.items():
            if tag_type not in self.local_cache:
                self.local_cache[tag_type] = []
            # 按“测点名”去重
            existing_names = {p["测点名"] for p in self.local_cache[tag_type]}
            for p in points:
                if p["测点名"] not in existing_names:
                    self.local_cache[tag_type].append(p)
        # 合并后持久化
        save_point_cache(self.local_cache)

    def _update_displayed_items(self, data: dict):
        """根据传入的数据更新 displayed_items 并刷新 UI"""
        all_items = [(t, p) for t, l in data.items() for p in l]
        # 过滤掉已选中的测点
        self.displayed_items = [pt for pt in all_items if pt[1] not in self.selected_points]
        self._refresh_left()

    def _reset_to_full_local(self):
        """重置为显示全部本地数据"""
        # 根据当前参数类型过滤，或显示所有类型
        filtered_data = {
            tag_type: points
            for tag_type, points in self.local_cache.items()
            # if tag_type == self.point_type  # 如果需要按类型过滤，取消注释此行
        }
        self._update_displayed_items(filtered_data)

    def _get_start_end_time(self):
        start_date = self.start_dt.getDate().toPyDate()
        end_date = self.end_dt.getDate().toPyDate()
        start_time = self.start_time_edit.dateTime().toPyDateTime()
        end_time = self.end_time_edit.dateTime().toPyDateTime()
        start_time = QTime(start_time.hour, start_time.minute, start_time.second).toPyTime()
        end_time = QTime(end_time.hour, end_time.minute, end_time.second).toPyTime()
        return datetime.datetime.combine(start_date, start_time), datetime.datetime.combine(end_date, end_time)

    def resizeEvent(self, event):
        """响应窗口大小变化，调整布局比例"""
        super().resizeEvent(event)
        # 使用计时器延迟处理，避免频繁调整
        self.timer.start(100)

    def _adjust_layout(self):
        """根据窗口大小重新调整分割器比例"""
        window_width = self.width()
        # 减小左侧面板宽度，为图表区域留出更多空间
        left_width = min(max(400, int(window_width * 0.2)), 400)  # 进一步减小左侧比例
        right_width = window_width - left_width
        self.splitter.setSizes([left_width, right_width])
        # 如果有数据且窗口大小变化明显，刷新当前显示的图表
        if hasattr(self, "data_cache") and self.data_cache:
            # 获取当前显示的图表类型，仅刷新当前显示的图表
            if self.current_plot_type == 0:
                # 为了避免频繁重绘，只有当窗口尺寸变化较大时才重绘
                if (
                        self.trend_plot
                        and hasattr(self, "last_width")
                        and abs(self.width() - self.last_width) > 100
                ):
                    self.trend_plot.plot_multiple(self.data_cache)
            # 保存当前宽度以供下次比较
            self.last_width = self.width()

    def _load_points(self):
        # 初始化default_points
        self.point_type = self.param_type_combo.currentText()
        self.selected_points = []
        self.default_points = [
            p.split("\n")[0] for p in self.parent.gather_tags(type=self.point_type)
        ]
        # 从缓存加载已有点信息
        self.local_cache = load_point_cache() or {}
        all_items = [(t, p) for t, l in self.local_cache.items() for p in l]
        # 左侧列表排除默认点，默认点将在_fetch后加入
        self.left_items = []
        selected_points = []
        for pt in all_items:
            if pt[1].get("测点名") in self.default_points and pt[1].get("测点名") not in selected_points:
                self.selected_points.append(pt[1])
                selected_points.append(pt[1].get("测点名"))
            else:
                self.left_items.append(pt)
        self._reset_to_full_local()
        self._refresh_left()
        self._refresh_selected()
        # 启动后台任务获取初始数据
        self._debounced_update_trends()
        self._debounced_fetch_points()

    def _start_fetch(self):
        # 没有切到当前界面就不进行抓取
        w = Worker(self.parent.config.get_tools_by_type("point-search"))
        w.signals.finished.connect(self._on_fetch)
        w.signals.error.connect(self._fetch_error)
        self.thread_pool.start(w)

    def _on_fetch(self, results):
        # 将获取的结果合并到本地缓存
        for t, l in results.items():
            if t in self.local_cache:
                points = [p.get("测点名") for p in l]
                self.local_cache[t].extend([p for p in l if p.get("测点名") not in points])
            else:
                self.local_cache[t] = l
        # 保存合并后的缓存
        save_point_cache(self.local_cache)
        # 重新加载本地数据
        self._reset_to_full_local()

    def _refresh_left(self):
        """优化版：刷新左侧列表UI，避免全量重建，提高性能"""
        # 如果没有要显示的项，清空表格
        if not self.displayed_items:
            self.left_table.setRowCount(0)
            return

        # 获取表头列名
        all_keys = set()
        for _, p in self.displayed_items:
            all_keys.update(p.keys())
        keys = ["测点名"] + [k for k in all_keys if k != "测点名"]

        # 只有当列结构改变时才重置列
        if self.left_table.columnCount() != len(keys):
            self.left_table.setColumnCount(len(keys))
            self.left_table.setHorizontalHeaderLabels(keys)
        else:
            # 检查列名是否一致，不一致则重置
            current_header_labels = [self.left_table.horizontalHeaderItem(i).text() for i in
                                     range(self.left_table.columnCount())]
            if current_header_labels != keys:
                self.left_table.setHorizontalHeaderLabels(keys)

        # 获取当前和目标行数
        current_row_count = self.left_table.rowCount()
        target_row_count = len(self.displayed_items)

        # 调整行数
        if current_row_count > target_row_count:
            # 移除多余的行
            for _ in range(current_row_count - target_row_count):
                self.left_table.removeRow(target_row_count)
        elif current_row_count < target_row_count:
            # 添加缺失的行
            for _ in range(target_row_count - current_row_count):
                self.left_table.insertRow(current_row_count)

        # 填充数据，只更新内容，不重新创建行
        for row_idx, (tag_type, point) in enumerate(self.displayed_items):
            for col_idx, key in enumerate(keys):
                value = str(point.get(key, ""))
                # 获取或创建单元格
                item = self.left_table.item(row_idx, col_idx)
                if item is None:
                    item = QTableWidgetItem(value)
                    self.left_table.setItem(row_idx, col_idx, item)
                else:
                    # 只有当内容不同时才更新，减少不必要的刷新
                    if item.text() != value:
                        item.setText(value)

    def _add_point(self):
        """从左侧列表添加测点到已选列表"""
        row = self.left_table.currentRow()
        if row < 0:
            return

        # 获取表头列名
        keys = [
            self.left_table.horizontalHeaderItem(i).text()
            for i in range(self.left_table.columnCount())
        ]
        # 找到测点名列的索引
        name_column = keys.index("测点名") if "测点名" in keys else 0
        # 获取测点名
        name = self.left_table.item(row, name_column).text()

        # 查找完整的测点信息
        found = False
        selected_point = None
        for pt in self.displayed_items:
            if pt[1].get("测点名") == name:
                # 检查是否已经添加过
                if pt[1] in self.selected_points:
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Information)
                    msg.setWindowTitle("提示")
                    msg.setText(f"测点 '{name}' 已经添加到列表中")
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.setStyleSheet(
                        """
                        QMessageBox {
                            background-color: #f8f9fa;
                        }
                        QLabel {
                            color: #495057;
                        }
                    """
                    )
                    msg.exec_()
                    return
                # 保存要添加的测点信息
                selected_point = pt[1]
                found = True
                break

        if not found or selected_point is None:
            return

        # ========== 性能优化：增量更新 ==========
        # 1. 将找到的测点添加到已选列表
        self.selected_points.append(selected_point)

        # 2. 直接从 displayed_items 中移除该测点
        self.displayed_items = [pt for pt in self.displayed_items if pt[1].get("测点名") != name]

        # 3. **关键：不再调用 _refresh_left()**
        # 我们只移除了一个特定的行，直接用 QTableWidget 的 removeRow 方法
        self.left_table.removeRow(row)
        # ========== 性能优化结束 ==========

        # 更新已选测点列表
        self._refresh_selected()

        # 高亮显示最后添加的测点
        for row_idx in range(self.selected_table.rowCount()):
            item = self.selected_table.item(row_idx, 0)
            if item and item.text() == name:
                self.selected_table.selectRow(row_idx)
                self.selected_table.scrollToItem(item)
                break

        # 始终更新趋势图，无论是否已有数据
        self._debounced_update_trends()

        # 确保图表显示最新数据
        if self.plot_placeholder and self.plot_placeholder.parent():
            self.plot_placeholder.setParent(None)
            self.plot_placeholder = None

    def _remove_point(self):
        """从已选列表中移除测点"""
        row = self.selected_table.currentRow()
        if row < 0:
            return

        # 获取表头列名
        keys = [
            self.selected_table.horizontalHeaderItem(i).text()
            for i in range(self.selected_table.columnCount())
        ]
        # 找到测点名列的索引
        name_column = keys.index("测点名") if "测点名" in keys else 0
        # 获取要移除的测点名
        removed_name = self.selected_table.item(row, name_column).text()

        # 从表格中移除该行
        self.selected_table.removeRow(row)

        # 重建已选测点列表
        new_selected = []
        for r in range(self.selected_table.rowCount()):
            row_vals = {}
            for c in range(self.selected_table.columnCount()):
                column_name = self.selected_table.horizontalHeaderItem(c).text()
                cell_value = self.selected_table.item(r, c).text()
                row_vals[column_name] = cell_value
            new_selected.append(row_vals)
        # 更新已选测点列表
        self.selected_points = new_selected

        # ========== 性能优化：增量更新 ==========
        # 1. 从本地缓存中找到被移除的测点的完整信息
        restored_point = None
        for tag_type, points in self.local_cache.items():
            for point in points:
                if point.get("测点名") == removed_name:
                    restored_point = (tag_type, point)
                    break
            if restored_point:
                break

        # 2. 如果找到了该测点，并且它当前不在 displayed_items 中，则将其加回去
        if restored_point and restored_point[1] not in [pt[1] for pt in self.displayed_items]:
            # 检查是否已经在 selected_points 中
            if restored_point[1] not in self.selected_points:
                # 将测点添加回 displayed_items
                self.displayed_items.append(restored_point)
                # 保持列表有序（可选）
                self.displayed_items.sort(key=lambda x: x[1].get("测点名", ""))

                # **关键：直接在表格末尾插入一行，而不是刷新整个列表**
                new_row = self.left_table.rowCount()
                self.left_table.insertRow(new_row)
                # 使用当前的表头
                current_keys = [self.left_table.horizontalHeaderItem(i).text() for i in
                                range(self.left_table.columnCount())]
                for col_idx, key in enumerate(current_keys):
                    value = str(restored_point[1].get(key, ""))
                    self.left_table.setItem(new_row, col_idx, QTableWidgetItem(value))
        # ========== 性能优化结束 ==========

        # 在左侧列表中查找并高亮刚移除的测点
        for row_idx in range(self.left_table.rowCount()):
            item = self.left_table.item(
                row_idx,
                name_column if name_column < self.left_table.columnCount() else 0,
            )
            if item and item.text() == removed_name:
                self.left_table.selectRow(row_idx)
                self.left_table.scrollToItem(item)
                break

        # 更新趋势图
        if self.selected_points:
            if hasattr(self, "data_cache") and removed_name in self.data_cache:
                del self.data_cache[removed_name]
            self._debounced_update_trends()
        else:
            self._clear_plot_area()
            self.data_cache = {}
            # 创建空图表提示
            empty_frame = QFrame()
            empty_frame.setStyleSheet(
                """
                QFrame {
                    background-color: #f8f9fa; 
                    border: 1px dashed #adb5bd;
                    border-radius: 5px;
                }
            """
            )
            empty_layout = QVBoxLayout(empty_frame)
            empty_layout.setAlignment(Qt.AlignCenter)
            icon = QLabel()
            icon.setAlignment(Qt.AlignCenter)
            icon.setPixmap(
                QApplication.style()
                .standardIcon(QStyle.SP_MessageBoxInformation)
                .pixmap(48, 48)
            )
            empty_layout.addWidget(icon)
            message = QLabel("所有测点已移除")
            message.setAlignment(Qt.AlignCenter)
            message.setStyleSheet("color: #495057; font-size: 14px; font-weight: bold;")
            empty_layout.addWidget(message)
            instruction = QLabel("从左侧列表中选择测点并添加")
            instruction.setAlignment(Qt.AlignCenter)
            instruction.setStyleSheet("color: #6c757d; font-size: 12px;")
            empty_layout.addWidget(instruction)
            # 根据当前显示的图表类型添加提示框
            if self.current_plot_type == 0:
                self.trend_plot_layout.addWidget(empty_frame)
            elif self.current_plot_type == 1:
                self.histogram_layout.addWidget(empty_frame)
            elif self.current_plot_type == 2:
                self.correlation_layout.addWidget(empty_frame)

    def _refresh_selected(self):
        sel = self.selected_points
        # refresh selected table
        if not sel:
            self.selected_table.clear()
            return
        keys = list(sel[0].keys())
        self.selected_table.setColumnCount(len(keys))
        self.selected_table.setHorizontalHeaderLabels(keys)
        self.selected_table.setRowCount(len(sel))
        for r, p in enumerate(sel):
            for c, k in enumerate(keys):
                self.selected_table.setItem(r, c, QTableWidgetItem(str(p.get(k, ""))))

    def _on_plot_type_changed(self, index):
        # 保存当前选择的图表类型
        self.current_plot_type = index
        # 隐藏所有图表容器
        self.trend_plot_widget.hide()
        self.histogram_widget.hide()
        self.correlation_widget.hide()
        # 根据选择显示对应的图表容器
        if index == 0:  # 曲线图
            self.plot_container_layout.addWidget(self.trend_plot_widget)
            self.trend_plot_widget.show()
            self.setWindowTitle("趋势分析 - 曲线图")
        elif index == 1:  # 频数直方图
            self.plot_container_layout.addWidget(self.histogram_widget)
            self.histogram_widget.show()
            self.setWindowTitle("趋势分析 - 频数直方图")
            # 清空旧内容
            for i in reversed(range(self.histogram_layout.count())):
                item = self.histogram_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setParent(None)
            # 如果没有数据，添加提示标签
            if not hasattr(self, "data_cache") or not self.data_cache:
                label = QLabel("请先选择测点并获取数据")
                label.setAlignment(Qt.AlignCenter)
                self.histogram_layout.addWidget(label)
        elif index == 2:  # 相关系数矩阵
            self.plot_container_layout.addWidget(self.correlation_widget)
            self.correlation_widget.show()
            self.setWindowTitle("趋势分析 - 相关系数矩阵")
            # 清空旧内容
            for i in reversed(range(self.correlation_layout.count())):
                item = self.correlation_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setParent(None)
            # 如果没有数据，添加提示标签
            if not hasattr(self, "data_cache") or not self.data_cache:
                label = QLabel("请先选择至少两个测点并获取数据")
                label.setAlignment(Qt.AlignCenter)
                self.correlation_layout.addWidget(label)
        # 如果有数据，则更新图表
        if hasattr(self, "data_cache") and self.data_cache:
            # 先清空当前显示
            self._clear_plot_area()
            # 然后重新生成对应类型的图表
            self._update_plots()

    def _update_plots(self):
        """根据当前选择的图表类型更新图表"""
        if not self.data_cache:
            return
        # 清除现有图表
        self._clear_plot_area()
        # 显示加载中的状态
        loading_label = QLabel("正在生成图表，请稍候...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("font-size: 14px; color: #333;")
        if self.current_plot_type == 0:  # 曲线图
            self.trend_plot_layout.addWidget(loading_label)
            self._show_trend_plot()
        elif self.current_plot_type == 1:  # 频数直方图
            self.histogram_layout.addWidget(loading_label)
            self._show_histogram_plot()
        elif self.current_plot_type == 2:  # 相关系数矩阵
            self.correlation_layout.addWidget(loading_label)
            try:
                self._show_correlation_plot()
            except Exception as e:
                import traceback
                logger.error(f"显示相关系数矩阵时出错: {e}\n{traceback.format_exc()}")
                # 紧急恢复措施 - 创建相关系数矩阵组件
                from application.widgets.correlation_matrix_widget import (
                    CorrelationMatrixWidget,
                )
                self._clear_plot_area()
                self.corr_matrix_widget = CorrelationMatrixWidget()
                self.correlation_layout.addWidget(self.corr_matrix_widget)
                # 尝试设置数据
                if self.data_cache:
                    processed_data = {}
                    for point_name, (timestamps, values) in self.data_cache.items():
                        if (
                                point_name in self.selected_points
                                and timestamps is not None
                                and len(timestamps) > 0
                        ):
                            # 过滤掉NaN值
                            valid_mask = ~np.isnan(values)
                            if np.any(valid_mask):
                                processed_data[point_name] = values[valid_mask]
                    if processed_data:
                        self.corr_matrix_widget.set_data(processed_data)
            # 确保显示关联矩阵小部件
            if hasattr(self, "corr_matrix_widget") and self.corr_matrix_widget:
                self.corr_matrix_widget.show()
        # 加载完成后移除加载标签
        if loading_label.parent():
            loading_label.setParent(None)

    def _debounced_fetch_points(self):
        """启动节流定时器，在短时间内合并多次请求"""
        self.point_update_timer.start(5000)  # 300ms 内连续添加点只触发一次请求

    def _debounced_update_trends(self):
        """启动节流定时器，在短时间内合并多次请求"""
        self.trend_update_timer.start(1000)  # 300ms 内连续添加点只触发一次请求

    def createErrorInfoBar(self, title: str, content: str, duration: int = 5000):
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=duration,  # won't disappear automatically
            parent=self
        )

    def _update_trends(self):
        """更新趋势图，显示选定的测点数据"""
        # 清除当前图表区域
        self._clear_plot_area()
        if not self.selected_points:
            self.createErrorInfoBar("提示", "请先选择至少一个测点！")
            return
        # 获取选定的测点名
        names = [p.get("测点名") for p in self.selected_points]
        # 首先禁用应用按钮，防止重复点击
        self.btn_apply.setEnabled(False)
        self.btn_apply.setIcon(get_icon("沙漏"))
        # 创建加载动画框
        loading_frame = QFrame()
        loading_frame.setStyleSheet(
            """
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """
        )
        loading_layout = QVBoxLayout(loading_frame)
        loading_layout.setAlignment(Qt.AlignCenter)
        # 加载图标
        loading_icon = QLabel()
        loading_icon.setAlignment(Qt.AlignCenter)
        loading_icon.setPixmap(get_icon("change").pixmap(64, 64))
        loading_layout.addWidget(loading_icon)
        # 加载提示文本
        waiting_label = QLabel("正在获取数据，请稍候...")
        waiting_label.setAlignment(Qt.AlignCenter)
        waiting_label.setStyleSheet("font-size: 14px; color: #495057; margin: 10px;")
        loading_layout.addWidget(waiting_label)
        # 添加测点数量信息
        points_info = QLabel(f"正在加载 {len(names)} 个测点的数据")
        points_info.setAlignment(Qt.AlignCenter)
        points_info.setStyleSheet("font-size: 12px; color: #6c757d;")
        loading_layout.addWidget(points_info)
        # 添加时间范围信息
        start_time, end_time = self._get_start_end_time()
        time_range_text = f"时间范围: {start_time.strftime('%Y-%m-%d %H:%M')} 至 {end_time.strftime('%Y-%m-%d %H:%M')}"
        time_info = QLabel(time_range_text)
        time_info.setAlignment(Qt.AlignCenter)
        time_info.setStyleSheet("font-size: 12px; color: #6c757d;")
        loading_layout.addWidget(time_info)
        # 根据当前图表类型添加到相应容器
        if self.current_plot_type == 0:
            self.trend_plot_layout.addWidget(loading_frame)
        elif self.current_plot_type == 1:
            self.histogram_layout.addWidget(loading_frame)
        elif self.current_plot_type == 2:
            self.correlation_layout.addWidget(loading_frame)
        # 获取数据参数
        sample = self.cmb_sample.currentText().replace(" ", "")
        # 创建并启动数据获取工作线程
        w = Worker(
            self.parent.config.get_tools_by_type("trenddb-fetcher")[0],
            names, start_time, end_time, sample, batch=True
        )
        w.signals.finished.connect(lambda data: self._on_data(data, loading_frame))
        w.signals.error.connect(lambda data: self._fetch_error(data, loading_frame))
        self.thread_pool.start(w)

    def _fetch_error(self, data, loading_frame=None):
        # 重新启用应用按钮
        self.btn_apply.setEnabled(True)
        self.btn_apply.setIcon(get_icon("change"))
        # 移除等待组件
        if loading_frame and loading_frame.parent():
            loading_frame.setParent(None)
        # 添加提示标签 - 美化
        error_frame = QFrame()
        error_frame.setStyleSheet(
            """
            QFrame {
                background-color: #fff3cd;
                border: 1px solid #ffeeba;
                border-radius: 8px;
                margin: 20px;
                padding: 20px;
            }
        """
        )
        error_layout = QVBoxLayout(error_frame)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setPixmap(
            QApplication.style()
            .standardIcon(QStyle.SP_MessageBoxWarning)
            .pixmap(48, 48)
        )
        error_layout.addWidget(icon_label)
        message_label = QLabel("获取时序数据接口超时")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setStyleSheet(
            "color: #856404; font-size: 14px; font-weight: bold;"
        )
        error_layout.addWidget(message_label)
        self.plot_container_layout.addWidget(error_frame)
        error_frame.deleteLater()

    def _on_data(self, data, loading_widget=None):
        """处理获取到的数据并更新图表"""
        # 重新启用应用按钮
        self.btn_apply.setEnabled(True)
        self.btn_apply.setIcon(get_icon("change"))
        # 移除等待组件
        if loading_widget and loading_widget.parent():
            loading_widget.setParent(None)
        # 检查是否有有效数据
        valid_data = {
            name: (ts, ys)
            for name, (ts, ys) in data.items()
            if ts is not None and len(ts) > 0
        }
        if not valid_data:
            # 显示没有数据的提示信息
            no_data_frame = QFrame()
            no_data_frame.setStyleSheet(
                """
                QFrame {
                    background-color: #fff3cd;
                    border: 1px solid #ffeeba;
                    border-radius: 8px;
                }
            """
            )
            no_data_layout = QVBoxLayout(no_data_frame)
            no_data_layout.setAlignment(Qt.AlignCenter)
            # 警告图标
            warning_icon = QLabel()
            warning_icon.setAlignment(Qt.AlignCenter)
            warning_icon.setPixmap(
                QApplication.style()
                .standardIcon(QStyle.SP_MessageBoxWarning)
                .pixmap(48, 48)
            )
            no_data_layout.addWidget(warning_icon)
            # 警告文本
            no_data_label = QLabel("所选时间范围内没有有效数据")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet(
                "font-size: 14px; color: #856404; margin: 10px;"
            )
            no_data_layout.addWidget(no_data_label)
            # 建议文本
            suggestion_label = QLabel("请尝试调整时间范围或选择其他测点")
            suggestion_label.setAlignment(Qt.AlignCenter)
            suggestion_label.setStyleSheet("font-size: 12px; color: #856404;")
            no_data_layout.addWidget(suggestion_label)
            # 根据当前图表类型添加到相应容器
            if self.current_plot_type == 0:
                self.trend_plot_layout.addWidget(no_data_frame)
            elif self.current_plot_type == 1:
                self.histogram_layout.addWidget(no_data_frame)
            elif self.current_plot_type == 2:
                self.correlation_layout.addWidget(no_data_frame)
            return
        # 更新数据缓存
        self.data_cache = valid_data
        # 显示数据点统计信息
        total_points = 0
        for name, (ts, ys) in valid_data.items():
            if ts is not None:
                total_points += len(ts)
        # 根据当前选择的图表类型展示数据
        self._update_plots()

    def _show_trend_plot(self):
        """显示曲线图"""
        self._current_plot_mode = 0  # 默认为标准线图
        # 清除旧的趋势图控件，但保留trend_plot和data_stats_frame
        for i in reversed(range(self.trend_plot_layout.count())):
            item = self.trend_plot_layout.itemAt(i)
            if (
                    item
                    and item.widget()
                    and item.widget() != self.trend_plot
                    and (
                    not hasattr(self, "data_stats_frame")
                    or item.widget() != self.data_stats_frame
            )
            ):
                item.widget().setParent(None)
        # 创建包装框架，提供标题和额外信息
        chart_wrapper = QFrame()
        chart_wrapper.setStyleSheet(
            """
                QFrame {
                    background-color: #f1f8ff;
                    border-radius: 4px;
                    margin-bottom: 5px;
                    padding: 5px;
                }
            """
        )
        wrapper_layout = QVBoxLayout(chart_wrapper)
        wrapper_layout.setContentsMargins(10, 5, 10, 5)
        # 创建标题和图例区域
        header = QHBoxLayout()
        self.commandBar = CommandBar(self)
        self.commandBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        header.addWidget(self.commandBar, 0)
        # 增加时间标记功能
        # 划分开关按钮
        self.switchButton = TransparentTogglePushButton('共享y轴', self)
        self.switchButton.toggled.connect(self.onCheckedChanged)
        self.commandBar.addWidget(self.switchButton)
        self.commandBar.addSeparator()
        self.commandBar.addAction(Action(FIF.PIN, '标记模式',  triggered=self._on_partition_toggled, checkable=True))
        self.color_combo = ColorComboBox(color=self.color)
        self.color_combo.setToolTip('曲线颜色选择')
        self.color_combo.colorChanged.connect(self.set_color)
        self.commandBar.addWidget(self.color_combo)
        self.btn_clear = ToolButton(get_icon("删除"))
        self.btn_clear.setToolTip('清空标记点')
        self.btn_clear.clicked.connect(self._clear_all_lines)
        self.commandBar.addWidget(self.btn_clear)
        wrapper_layout.addLayout(header)
        # 添加到布局
        self.trend_plot_layout.addWidget(chart_wrapper)
        # 创建新的趋势图
        self.trend_plot = TrendPlotWidget(home=self.home)
        # 连接标记相关信号
        self.trend_plot_layout.addWidget(self.trend_plot, 1)  # 图表占据大部分空间
        # 创建信息区域显示数据统计
        info_bar = QFrame()
        info_bar.setMaximumHeight(30)
        status_layout = QHBoxLayout(info_bar)
        status_layout.setContentsMargins(10, 0, 10, 0)
        # 统计测点数量
        point_count = QLabel(f"测点数量: {len(self.data_cache)}")
        point_count.setStyleSheet("color: #6c757d; font-size: 11px;")
        status_layout.addWidget(point_count)
        status_layout.addStretch()
        # 显示时间范围
        start, end = self._get_start_end_time()
        time_range = QLabel(
            f"时间范围: {start.strftime('%Y-%m-%d %H:%M')} 至 {end.strftime('%Y-%m-%d %H:%M')}"
        )
        time_range.setStyleSheet("color: #6c757d; font-size: 11px;")
        status_layout.addWidget(time_range)
        self.trend_plot_layout.addWidget(info_bar)
        # 绘制数据
        self.trend_plot.plot_multiple(self.data_cache)
        self._update_plot_mode(self._current_plot_mode)
        self._restore_cut_lines()

    def onCheckedChanged(self, isChecked: bool):
        button_text = "独立y轴" if isChecked else "共享y轴"
        self.switchButton.setText(button_text)
        self.trend_plot.set_independent_y(isChecked)

    def set_color(self, color):
        """设置曲线颜色"""
        self.color = color

    def _quick_time_range(self, index):
        """根据快速选择更新时间范围"""
        if index == 0:  # 自定义，不做处理
            return
        now = QDateTime.currentDateTime()
        self.end_dt.setDate(now.date())
        self.end_time_edit.setTime(now.time())
        if index == 1:  # 最近1小时
            self.start_dt.setDate(now.addSecs(-3600).date())
            self.start_time_edit.setTime(now.addSecs(-3600).time())
        elif index == 2:  # 最近12小时
            self.start_dt.setDate(now.addSecs(-3600 * 12).date())
            self.start_time_edit.setTime(now.addSecs(-3600 * 12).time())
        elif index == 3:  # 最近24小时
            self.start_dt.setDate(now.addSecs(-3600 * 24).date())
            self.start_time_edit.setTime(now.addSecs(-3600 * 24).time())
        elif index == 4:  # 最近7天
            self.start_dt.setDate(now.addDays(-7).date())
            self.start_time_edit.setTime(now.addDays(-7).time())
        # 自动应用新的时间范围
        self._update_trends()

    def _update_plot_mode(self, index):
        """更新曲线图的显示模式"""
        self._current_plot_mode = index
        # 如果有数据和图表，更新显示
        if hasattr(self, "data_cache") and self.data_cache and self.trend_plot:
            # 临时保存当前显示范围
            view_range = self.trend_plot.getViewBox().viewRange()
            # 移除旧曲线
            for curve in self.trend_plot.curves:
                self.trend_plot.removeItem(curve)
            self.trend_plot.curves.clear()
            # 重新添加曲线，使用新的样式
            modes = {0: "line", 1: "fill", 2: "scatter"}
            self.trend_plot.plot_multiple(self.data_cache, mode=modes[index])

    def _clear_plot_area(self):
        # 清除所有图表区域的控件
        for layout in [
            self.trend_plot_layout,
            self.histogram_layout,
            self.correlation_layout,
        ]:
            for i in reversed(range(layout.count())):
                widget = layout.itemAt(i).widget()
                # 保留相关系数矩阵小部件，只是暂时隐藏它
                if widget is not None:
                    widget.setParent(None)
        if self.plot_placeholder is not None:
            self.trend_plot_layout.removeWidget(self.plot_placeholder)
            self.plot_placeholder.deleteLater()
            self.plot_placeholder = None

    def _show_histogram_plot(self):
        """显示频数直方图"""
        # 清除旧的直方图控件
        for i in reversed(range(self.histogram_layout.count())):
            widget = self.histogram_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        # 检查是否有数据
        if not hasattr(self, "data_cache") or not self.data_cache:
            # 添加提示标签
            no_data_label = QLabel("请先选择测点并获取数据")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet(
                "color: #6c757d; font-size: 14px; padding: 20px;"
            )
            self.histogram_layout.addWidget(no_data_label)
            return
        # 初始化直方图组件（如果不存在）
        if (
                not hasattr(self, "histogram_widget_instance")
                or not self.histogram_widget_instance
        ):
            from application.widgets.histogram_widget import HistogramWidget
            self.histogram_widget_instance = HistogramWidget(self)
        # 添加到布局
        self.histogram_layout.addWidget(self.histogram_widget_instance)
        # 设置数据
        self.histogram_widget_instance.set_data(self.data_cache)

    def _show_correlation_plot(self):
        """显示相关系数矩阵"""
        # 清除旧的相关系数矩阵控件
        for i in reversed(range(self.correlation_layout.count())):
            widget = self.correlation_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        # 检查是否有数据
        if not hasattr(self, "data_cache") or not self.data_cache:
            # 添加提示标签
            no_data_label = QLabel("请先选择测点并获取数据")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet(
                "color: #6c757d; font-size: 14px; padding: 20px;"
            )
            self.correlation_layout.addWidget(no_data_label)
            return
        # 收集所有数据点
        data_points = {}
        for name, (ts, ys) in self.data_cache.items():
            if ts is None or len(ts) == 0:
                continue
            data_points[name] = ys
        if not data_points or len(data_points) < 2:
            # 添加提示标签 - 美化
            error_frame = QFrame()
            error_frame.setStyleSheet(
                """
                QFrame {
                    background-color: #fff3cd;
                    border: 1px solid #ffeeba;
                    border-radius: 8px;
                    margin: 20px;
                    padding: 20px;
                }
            """
            )
            error_layout = QVBoxLayout(error_frame)
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setPixmap(
                QApplication.style()
                .standardIcon(QStyle.SP_MessageBoxWarning)
                .pixmap(48, 48)
            )
            error_layout.addWidget(icon_label)
            message_label = QLabel("需要至少两个测点才能计算相关系数矩阵")
            message_label.setAlignment(Qt.AlignCenter)
            message_label.setStyleSheet(
                "color: #856404; font-size: 14px; font-weight: bold;"
            )
            error_layout.addWidget(message_label)
            help_label = QLabel("请从左侧列表中选择更多测点，然后点击'应用'按钮")
            help_label.setAlignment(Qt.AlignCenter)
            help_label.setStyleSheet("color: #856404; font-size: 12px;")
            error_layout.addWidget(help_label)
            self.correlation_layout.addWidget(error_frame)
            return
        # 创建相关系数矩阵小部件
        self.corr_matrix_widget = CorrelationMatrixWidget(self)
        # 设置数据到小部件
        self.corr_matrix_widget.set_data(data_points)
        # 添加到布局
        self.correlation_layout.addWidget(self.corr_matrix_widget, 1)

    def _add_cut_line(self, x: float, initial=False):
        ln = DraggableLine(x, color=self.color)
        ln.setZValue(10)  # 设置较高的Z值
        self.cut_lines.append(ln)
        if initial:
            try:
                self.trend_plot.addItem(ln)
            except:
                pass

    def _delete_line(self, line):
        if line in self.cut_lines:
            self.trend_plot.removeItem(line)
            self.cut_lines.remove(line)

    def _restore_cut_lines(self):
        """恢复断点"""
        previous_lines = [ln.value() for ln in self.cut_lines]
        line_colors = [ln.color for ln in self.cut_lines]
        self._clear_all_lines()
        for x, color in zip(previous_lines, line_colors):
            ln = DraggableLine(x, color=color)
            ln.setZValue(10)  # 设置较高的Z值
            self.cut_lines.append(ln)
            self.trend_plot.addItem(ln)

    def _clear_all_lines(self):
        for ln in list(self.cut_lines):
            self._delete_line(ln)

    def _on_partition_toggled(self, checked: bool):
        # 划分模式切换样式
        self.partitioning = checked
        # 动态连接/断开 点击添加断点
        if checked:
            self.trend_plot.scene().sigMouseClicked.connect(self._on_click)
        else:
            try:
                self.trend_plot.scene().sigMouseClicked.disconnect(self._on_click)
            except TypeError:
                pass

    def _on_click(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        vb = self.trend_plot.getViewBox()
        pos = ev.scenePos()
        if not vb.sceneBoundingRect().contains(pos):
            return
        x = vb.mapSceneToView(pos).x()
        self._add_cut_line(x, initial=True)

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x00A3:
                if self.isMaximized():
                    self.showNormal()
                else:
                    self.showMaximized()
                return True, 0
        return super().nativeEvent(eventType, message)

    def add_tags(self):
        tag_list = [
            f"{point['测点名']}\n{' | '.join(list(point.values()))}"
            for point in self.selected_points
        ]
        new_tags = []  # 用于记录新增的测点名称
        for i in range(self.parent.tree.topLevelItemCount()):
            item = self.parent.tree.topLevelItem(i)
            if item.text(0) == self.point_type:
                for tag in tag_list:
                    existing_tags = [
                        p.split("\n")[0]
                        for p in self.parent.gather_tags(type=self.point_type)
                    ]
                    if tag.split("\n")[0] not in existing_tags:
                        self.parent.add_sub_param(item, tag)
                        new_tags.append(tag.split("\n")[1])  # 记录新增的测点名称
                break
        # 如果有新增的测点，显示弹窗
        if new_tags:
            msg_box = Dialog(
                "新增测点配置",
                f"已成功向 {self.point_type} 添加以下测点配置：\n"
                + "\n".join(new_tags)
                + f"\n共 {len(new_tags)} 个"
            )
            msg_box.yesButton.setText("继续添加测点")
            msg_box.cancelButton.setText("返回配置列表")
            if msg_box.exec():
                pass
            else:
                self.home.switchTo(self.home.editor)

    def create_successbar(self, title: str, content: str = "", duration: int = 5000):
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM,
            duration=duration,  # won't disappear automatically
            parent=self
        )

    def create_errorbar(self, title: str, content: str = "", duration: int = 5000):
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM,
            duration=duration,  # won't disappear automatically
            parent=self
        )