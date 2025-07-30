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
from qfluentwidgets import SearchLineEdit, InfoBar, InfoBarPosition, Dialog, FastCalendarPicker, CompactTimeEdit, \
    PushButton, SwitchButton, ToolButton

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
        self.points_data = {}
        self.left_items = []
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

        # 应用现代化样式
        self.apply_modern_style()
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

        self.search_input = SearchLineEdit()
        self.search_input.returnPressed.connect(self._filter_left)
        self.search_input.searchSignal.connect(self._filter_left)
        self.search_input.clearSignal.connect(self._filter_left)

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

        self.param_type_combo = QComboBox()
        self.param_types = self.parent.config.get_params_name()
        self.param_type_combo.addItems(self.param_types)
        if len(self.param_types) > 0:
            self.param_type_combo.setCurrentText(self.param_types[0])
        self.param_type_combo.setStyleSheet(
            """
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #1890ff;
                border-radius: 4px;
                background-color: white;
                color: black; /* 默认字体颜色 */
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black; /* 鼠标悬浮时字体颜色 */
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border-left: none;
            }
        """
        )
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
        selected_title.setStyleSheet("color: #495057; font-size: 12px; border: 1px solid #dee2e6;border-radius: 4px;background-color: white;")
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
        row3.setSpacing(8)

        # 图表类型选择
        plot_label = QLabel("图表类型:")
        plot_label.setStyleSheet("color: #495057;")
        row3.addWidget(plot_label)
        self.cmb_plot_type = QComboBox()
        self.cmb_plot_type.addItems(["曲线图 📈", "频数直方图 📊", "相关系数矩阵 🔢"])
        self.cmb_plot_type.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cmb_plot_type.setStyleSheet("""
            QComboBox {
                padding: 2px 4px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
                color: black;
            }
            QComboBox:hover {
                border-color: #40a9ff;
            }
        """)
        self.cmb_plot_type.currentIndexChanged.connect(self._on_plot_type_changed)
        row3.addWidget(self.cmb_plot_type)

        row3.addStretch()  # 添加弹性空间

        # 时间选择
        start_label = QLabel("开始:")
        start_label.setStyleSheet("color: #495057;")
        row3.addWidget(start_label)
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

        row3.addWidget(self.start_dt)
        row3.addWidget(self.start_time_edit)

        end_label = QLabel("结束:")
        end_label.setStyleSheet("color: #495057;")
        row3.addWidget(end_label)

        row3.addWidget(self.end_dt)
        row3.addWidget(self.end_time_edit)

        # 采样选择
        sample_label = QLabel("采样:")
        sample_label.setStyleSheet("color: #495057;")
        row3.addWidget(sample_label)
        self.cmb_sample = QComboBox()
        self.cmb_sample.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cmb_sample.setStyleSheet("""
            QComboBox {
                padding: 2px 4px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
                color: black;
            }
            QComboBox:hover {
                border-color: #40a9ff;
            }
        """)
        for v in (600, 2000, 5000):
            self.cmb_sample.addItem(str(v), v)
        row3.addWidget(self.cmb_sample)

        # 应用按钮
        self.btn_apply = QPushButton()
        self.btn_apply.setIcon(get_icon("change"))
        self.btn_apply.setToolTip("使用当前设置更新图表")
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.setStyleSheet(get_button_style_sheet())
        self.btn_apply.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_apply.clicked.connect(self._update_trends)
        row3.addWidget(self.btn_apply)

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
        self.points_data = load_point_cache() or {}
        all_items = [(t, p) for t, l in self.points_data.items() for p in l]
        # 左侧列表排除默认点，默认点将在_fetch后加入
        self.left_items = []
        selected_points = []
        for pt in all_items:
            if pt[1].get("测点名") in self.default_points and pt[1].get("测点名") not in selected_points:
                self.selected_points.append(pt[1])
                selected_points.append(pt[1].get("测点名"))
            else:
                self.left_items.append(pt)
        self._refresh_left()
        self._refresh_selected()
        self._debounced_update_trends()
        self._debounced_fetch_points()

    def _start_fetch(self):
        # 没有切到当前界面就不进行抓取
        if self.home.stackedWidget.currentWidget().objectName() != self.objectName():
            return
        w = Worker(self.parent.config.get_tools_by_type("point-search"))
        w.signals.finished.connect(self._on_fetch)
        w.signals.error.connect(self._fetch_error)
        self.thread_pool.start(w)

    def merge_point_cache(self, cache, new_cache):
        for t, l in cache.items():
            if t in new_cache:
                points = [p.get("测点名") for p in l]
                cache[t].extend([p for p in new_cache[t] if p.get("测点名") not in points])
            else:
                cache[t] = new_cache[t]

        return cache

    def _on_fetch(self, results):
        # 在原有基础上添加结果
        if len(self.points_data) > 0:
            self.points_data = self.merge_point_cache(self.points_data, results)

        save_point_cache(results)
        # 重新筛选测点
        all_items = [
            (t, p)
            for t, l in self.points_data.items()
            for p in l
        ]
        # 剩余可选
        self.left_items = [pt for pt in all_items if pt[1].get("测点名") not in self.default_points]
        self._refresh_left()

    def _refresh_left(self):
        self.left_table.setRowCount(0)
        if not self.left_items:
            self.left_table.clear()
            return

        # 找出所有可能出现的key
        all_keys = set()
        for _, p in self.left_items:
            all_keys.update(p.keys())
        keys = ["测点名"]  # Start with 测点名
        # other_keys = sorted([k for k in all_keys if k != "测点名"])  # Other keys sorted
        keys.extend([k for k in all_keys if k != "测点名"])  # Combine lists

        self.left_table.setColumnCount(len(keys))
        self.left_table.setHorizontalHeaderLabels(keys)
        self.left_table.setRowCount(0)

        for _, p in self.left_items:
            r = self.left_table.rowCount()
            self.left_table.insertRow(r)
            for c, k in enumerate(keys):
                self.left_table.setItem(r, c, QTableWidgetItem(str(p.get(k, ""))))

    def _filter_left(self):
        kws = self.search_input.text().lower().split()
        all_items = [(t, p) for t, l in self.points_data.items() for p in l]
        self.left_items = [
            pt
            for pt in all_items
            if all(kw in "".join(map(str, pt[1].values())).lower() for kw in kws)
            and pt[1] not in self.selected_points
        ]
        self._refresh_left()

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
        if "测点名" in keys:
            name_column = keys.index("测点名")
        else:  # 如果没有测点名列，使用第一列
            name_column = 0

        # 获取测点名
        name = self.left_table.item(row, name_column).text()

        # 查找完整的测点信息
        found = False
        for pt in self.left_items:
            if pt[1].get("测点名") == name:
                # 检查是否已经添加过
                if pt[1] in self.selected_points:
                    # 显示已添加的提示信息
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

                # 添加到已选测点
                self.selected_points.append(pt[1])
                found = True

                break

        if not found:
            return

        # 更新左侧列表内容
        all_items = [(t, p) for t, l in self.points_data.items() for p in l]
        self.left_items = [pt for pt in all_items if pt[1] not in self.selected_points]
        self._refresh_left()

        # 如果搜索框有内容，应用过滤
        if len(self.search_input.text()) > 0:
            self._filter_left()

        # 更新已选测点列表
        self._refresh_selected()

        # 高亮显示最后添加的测点
        for row in range(self.selected_table.rowCount()):
            item = self.selected_table.item(row, 0)
            if item and item.text() == name:
                self.selected_table.selectRow(row)
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
        if "测点名" in keys:
            name_column = keys.index("测点名")
        else:  # 如果没有测点名列，使用第一列
            name_column = 0

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

        # 更新左侧可选测点列表
        all_items = [(t, p) for t, l in self.points_data.items() for p in l]
        self.left_items = [pt for pt in all_items if pt[1] not in self.selected_points]
        self._refresh_left()

        # 如果搜索框有内容，重新应用过滤
        if len(self.search_input.text()) > 0:
            self._filter_left()

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
        if self.selected_points:  # 如果还有其他测点，更新图表
            # 确保从数据缓存中移除已删除测点的数据
            if hasattr(self, "data_cache") and removed_name in self.data_cache:
                del self.data_cache[removed_name]
            self._debounced_update_trends()
        else:  # 如果没有测点了，清空图表区域并显示提示
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

    def createErrorInfoBar(self, title: str, content: str, duration: int=5000):
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=duration,    # won't disappear automatically
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
        sample = self.cmb_sample.currentData()
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
        title = QLabel("趋势曲线图")
        title.setStyleSheet("font-weight: bold; color: #1864ab; font-size: 13px;")
        header.addWidget(title)
        self._current_plot_mode = 0  # 默认为标准线图

        # 增加时间标记功能
        # 划分开关按钮
        mode_label = QLabel("标记模式:")
        # mode_label.setStyleSheet("color: #495057; font-size: 12px; margin-left: 10px;")
        header.addWidget(mode_label)

        self.btn_partition = SwitchButton(self)
        self.btn_partition.setOffText("")
        self.btn_partition.setOnText("")
        self.btn_partition.checkedChanged.connect(self._on_partition_toggled)
        header.addWidget(self.btn_partition)

        # 曲线颜色
        self.color_combo = ColorComboBox(color=self.color)
        self.color_combo.setToolTip('曲线颜色选择')
        self.color_combo.colorChanged.connect(self.set_color)
        header.addWidget(self.color_combo)

        # 清空断点
        self.btn_clear = ToolButton(get_icon("删除"))
        self.btn_clear.setToolTip('清空标记点')
        self.btn_clear.clicked.connect(self._clear_all_lines)
        header.addWidget(self.btn_clear)

        # 添加快速时间范围选择
        header.addStretch()
        self.range_combo = QComboBox()
        self.range_combo.addItems(
            ["自定义", "最近1小时", "最近12小时", "最近24小时", "最近7天"]
        )
        self.range_combo.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 11px;
                background-color: white;
                color: black; /* 默认字体颜色 */
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black; /* 鼠标悬浮时字体颜色 */
            }
        """
        )
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

        self.range_combo.currentIndexChanged.connect(self._quick_time_range)

        header.addWidget(QLabel("快速选择:"))
        header.addWidget(self.range_combo)

        wrapper_layout.addLayout(header)

        # 添加到布局
        self.trend_plot_layout.addWidget(chart_wrapper)
        # 创建新的趋势图
        self.trend_plot = TrendPlotWidget(home=self.home)
        # 设置趋势图样式
        self.trend_plot.setBackground("w")  # 白色背景
        self.trend_plot.showGrid(x=True, y=True, alpha=0.3)  # 显示网格线
        # 确保tooltip不会使用无效的矩形
        self.trend_plot.tooltip_widget.rect = QRect(0, 0, 300, 200)  # 提供默认矩形
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