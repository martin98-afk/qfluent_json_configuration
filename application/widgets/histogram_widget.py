import numpy as np
import json
from loguru import logger
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QComboBox, QFrame, QScrollArea, QSizePolicy, QCheckBox)
from PyQt5.QtWebEngineWidgets import QWebEngineView  # 新增
from pyecharts import options as opts
from pyecharts.charts import Histogram, Line, Grid
from pyecharts.commons.utils import JsCode


class HistogramWidget(QWidget):
    """使用 pyecharts 重构的直方图控件，支持高级交互和现代化可视化"""

    # 信号定义
    histogramUpdated = pyqtSignal()  # 直方图更新完成信号

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置基本属性
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 配置参数
        self.hist_type = 0  # 0:标准直方图, 1:核密度估计, 2:组合显示
        self.color_theme = 0  # 0:蓝色, 1:彩虹, 2:绿色, 3:暖色
        self.bin_count = 'auto'  # 柱状图区间数量
        self.data_dict = {}  # 数据字典 {名称: (时间序列,值序列)}
        self.current_page = 0  # 当前页码
        self.items_per_page = 4  # 每页固定显示4个图表
        self.statistics = {}  # 统计信息缓存
        self.show_stats = True  # 是否显示统计信息

        # 初始化UI
        self._init_ui()

    def _init_ui(self):
        """初始化用户界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        # 顶部控制面板 (保持原有设计)
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background-color: #f1f8ff;
                border-radius: 4px;
                margin-bottom: 5px;
                padding: 5px;
            }
        """)
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(10, 5, 10, 5)

        # 标题标签
        title = QLabel("频数分布直方图")
        title.setStyleSheet("font-weight: bold; color: #1864ab; font-size: 13px;")
        control_layout.addWidget(title)

        # 添加分页控制
        page_label = QLabel("页码:")
        page_label.setStyleSheet("color: #495057; font-size: 12px;")
        control_layout.addWidget(page_label)

        self.page_combo = QComboBox()
        self.page_combo.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 11px;
                background-color: white;
                color: black;
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black;
            }"""
        )
        self.page_combo.currentIndexChanged.connect(self._on_page_changed)
        control_layout.addWidget(self.page_combo)

        control_layout.addStretch()

        # 直方图类型选择
        type_label = QLabel("图表类型:")
        type_label.setStyleSheet("color: #495057; font-size: 12px;")
        control_layout.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["标准直方图", "核密度估计", "组合显示"])
        self.type_combo.setCurrentIndex(0)
        self.type_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 11px;
                background-color: white;
                color: black;
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black;
            }
        """)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        control_layout.addWidget(self.type_combo)

        # 颜色主题选择
        color_label = QLabel("颜色主题:")
        color_label.setStyleSheet("color: #495057; font-size: 12px;")
        control_layout.addWidget(color_label)

        self.color_combo = QComboBox()
        self.color_combo.addItems(["蓝色", "彩虹", "绿色", "暖色"])
        self.color_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 11px;
                background-color: white;
                color: black;
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black;
            }
        """)
        self.color_combo.currentIndexChanged.connect(self._on_color_changed)
        control_layout.addWidget(self.color_combo)

        # 区间数量控制
        bins_label = QLabel("区间数:")
        bins_label.setStyleSheet("color: #495057; font-size: 12px; margin-left: 5px;")
        control_layout.addWidget(bins_label)

        self.bins_combo = QComboBox()
        self.bins_combo.addItems(["自动", "10", "20", "30", "50"])
        self.bins_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 11px;
                background-color: white;
                color: black;
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black;
            }
        """)
        self.bins_combo.currentIndexChanged.connect(self._on_bins_changed)
        control_layout.addWidget(self.bins_combo)

        # 统计信息显示设置
        stats_label = QLabel("统计信息:")
        stats_label.setStyleSheet("color: #495057; font-size: 12px;")
        control_layout.addWidget(stats_label)

        self.stats_checkbox = QCheckBox("")
        self.stats_checkbox.setChecked(True)
        self.stats_checkbox.setStyleSheet("""
            QCheckBox {
                color: #495057;
                font-size: 11px;
            }
        """)
        self.stats_checkbox.stateChanged.connect(self._on_stats_changed)
        control_layout.addWidget(self.stats_checkbox)

        main_layout.addWidget(control_frame)

        # 创建 Web 引擎视图 (替换 matplotlib)
        self.web_view = QWebEngineView()
        self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 设置滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.web_view)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
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
        """)
        main_layout.addWidget(self.scroll_area, 1)

        # 状态区域
        status_frame = QFrame()
        status_frame.setMaximumHeight(30)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 0, 10, 0)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.data_info_label = QLabel("无数据")
        self.data_info_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        status_layout.addWidget(self.data_info_label)

        main_layout.addWidget(status_frame)

        # 初始状态下显示无数据提示
        self._show_no_data_message()

    def _on_type_changed(self, index):
        """处理直方图类型变更"""
        self.hist_type = index
        self.status_label.setText(f"已切换到{self.type_combo.currentText()}")
        if self.data_dict:
            self._update_histograms()

    def _on_color_changed(self, index):
        """处理颜色主题变更"""
        self.color_theme = index
        self.status_label.setText(f"已切换到{self.color_combo.currentText()}主题")
        if self.data_dict:
            self._update_histograms()

    def _on_bins_changed(self, index):
        """处理区间数量变更"""
        if index == 0:
            self.bin_count = 'auto'
        else:
            self.bin_count = int(self.bins_combo.currentText())
        self.status_label.setText(f"已设置区间数为{self.bins_combo.currentText()}")
        if self.data_dict:
            self._update_histograms()

    def _on_stats_changed(self, state):
        """处理统计信息显示设置变更"""
        self.show_stats = (state == Qt.Checked)
        self.status_label.setText(f"{'显示' if self.show_stats else '隐藏'}统计信息")
        if self.data_dict:
            self._update_histograms()

    def _on_page_changed(self, index):
        """处理页码变更"""
        self.current_page = index
        self.status_label.setText(f"已切换到第{index + 1}页")
        if self.data_dict:
            self._update_histograms()

    def set_data(self, data_dict):
        """设置要显示的数据"""
        valid_data = {}
        for name, (ts, ys) in data_dict.items():
            if ts is not None and len(ts) > 0 and len(ys) > 0:
                valid_data[name] = (ts, ys)

        if not valid_data:
            self._show_no_data_message()
            return

        self.data_dict = valid_data
        n_points = len(valid_data)

        # 计算总页数
        total_pages = (n_points + self.items_per_page - 1) // self.items_per_page

        # 更新页码选择框
        self.page_combo.blockSignals(True)
        self.page_combo.clear()
        for i in range(total_pages):
            self.page_combo.addItem(f"{i + 1}/{total_pages}")

        if self.current_page >= total_pages:
            self.current_page = 0
        self.page_combo.setCurrentIndex(self.current_page)
        self.page_combo.blockSignals(False)

        # 更新数据信息标签
        total_points = sum(len(ys) for _, (_, ys) in valid_data.items())
        self.data_info_label.setText(f"样本数量: {total_points}")

        # 计算统计信息
        self._calculate_statistics()

        # 更新直方图
        self._update_histograms()

        self.status_label.setText(f"测点数量: {n_points}")

    def _calculate_statistics(self):
        """计算并缓存每个测点的统计信息"""
        self.statistics = {}

        for name, (_, ys) in self.data_dict.items():
            if len(ys) == 0:
                continue

            stats = {
                'mean': np.mean(ys),
                'median': np.median(ys),
                'std': np.std(ys),
                'min': np.min(ys),
                'max': np.max(ys),
                'count': len(ys)
            }

            try:
                stats['q1'] = np.percentile(ys, 25)
                stats['q3'] = np.percentile(ys, 75)
                stats['iqr'] = stats['q3'] - stats['q1']
            except:
                stats['q1'] = stats['q3'] = stats['iqr'] = float('nan')

            try:
                lower_bound = stats['q1'] - 1.5 * stats['iqr']
                upper_bound = stats['q3'] + 1.5 * stats['iqr']
                outliers = [y for y in ys if y < lower_bound or y > upper_bound]
                stats['outliers_count'] = len(outliers)
                stats['outliers_percent'] = (len(outliers) / len(ys)) * 100 if len(ys) > 0 else 0
            except:
                stats['outliers_count'] = stats['outliers_percent'] = float('nan')

            self.statistics[name] = stats

    def _update_histograms(self):
        """更新直方图显示 (使用 pyecharts)"""
        # 获取当前页的数据
        data_items = list(self.data_dict.items())
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(data_items))
        current_page_data = data_items[start_idx:end_idx]

        if not current_page_data:
            self._show_no_data_message()
            return

        # 创建 Grid 布局 (2x2)
        grid = Grid(init_opts=opts.InitOpts(
            width="100%",
            height="100%",
            page_title="直方图分析",
            theme="light"
        ))

        # 颜色主题映射
        color_themes = {
            0: ["#1c7ed6", "#4dabf7"],  # 蓝色
            1: ["#ff9e4a", "#ff6b6b", "#4ecdc4", "#45b7d1"],  # 彩虹
            2: ["#2b8a3e", "#37b24d"],  # 绿色
            3: ["#e67700", "#fd7e14"]  # 暖色
        }

        # 每个图表的尺寸配置
        chart_width = "48%"
        chart_height = "45%"

        # 为每个数据集创建图表
        for idx, (name, (ts, ys)) in enumerate(current_page_data):
            if len(ys) == 0:
                continue

            # 计算分组
            if self.bin_count == 'auto':
                n_bins = int(np.ceil(np.log2(len(ys)) + 1))
                n_bins = max(10, min(30, n_bins))
            else:
                n_bins = self.bin_count

            # 创建直方图
            hist = Histogram()

            # 计算直方图数据
            counts, bins = np.histogram(ys, bins=n_bins)
            bin_centers = (bins[:-1] + bins[1:]) / 2
            bin_labels = [f"{bins[i]:.2f}-{bins[i + 1]:.2f}" for i in range(len(bins) - 1)]

            # 添加直方图
            if self.hist_type == 0 or self.hist_type == 2:
                hist.add_yaxis(
                    series_name="频数",
                    y_axis=counts.tolist(),
                    xaxis_index=0,
                    yaxis_index=0,
                    label_opts=opts.LabelOpts(is_show=False),
                    itemstyle_opts=opts.ItemStyleOpts(
                        color=color_themes[self.color_theme][0]
                    )
                )

            # 添加核密度估计
            if self.hist_type == 1 or self.hist_type == 2:
                try:
                    from scipy.stats import gaussian_kde
                    kde = gaussian_kde(ys)
                    x_range = np.linspace(min(ys), max(ys), 1000)
                    kde_values = kde(x_range)

                    # 创建折线图
                    line = (
                        Line()
                        .add_xaxis(xaxis_data=x_range.tolist())
                        .add_yaxis(
                            series_name="KDE",
                            y_axis=kde_values.tolist(),
                            is_smooth=True,
                            linestyle_opts=opts.LineStyleOpts(width=2),
                            label_opts=opts.LabelOpts(is_show=False),
                            itemstyle_opts=opts.ItemStyleOpts(color="#e03131")
                        )
                    )

                    # 合并到直方图
                    hist.overlap(line)
                except Exception as e:
                    logger.error(f"核密度估计失败: {e}")

            # 配置全局选项
            title_opts = opts.TitleOpts(
                title=name,
                subtitle=self._get_stats_text(name) if self.show_stats else None,
                title_textstyle_opts=opts.TextStyleOpts(font_size=14, font_weight="bold"),
                pos_left="center"
            )

            hist.set_global_opts(
                title_opts=title_opts,
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="shadow",
                    formatter=JsCode("""
                        function(params) {
                            return params.map(function(param) {
                                return param.seriesName + ': ' + param.value;
                            }).join('<br/>');
                        }
                    """)
                ),
                xaxis_opts=opts.AxisOpts(
                    type_="category",
                    data=bin_labels,
                    axislabel_opts=opts.LabelOpts(rotate=45, interval=0),
                    name="数值区间",
                    name_location="center",
                    name_gap=30
                ),
                yaxis_opts=opts.AxisOpts(
                    type_="value",
                    name="频数",
                    name_location="center",
                    name_gap=30,
                    splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(opacity=0.2))
                ),
                legend_opts=opts.LegendOpts(pos_top="5%"),
                grid_opts=opts.GridOpts(
                    pos_left="8%",
                    pos_right="8%",
                    pos_top="15%",
                    pos_bottom="20%"
                )
            )

            # 添加到 Grid 布局
            pos_left = "2%" if idx % 2 == 0 else "52%"
            pos_top = "2%" if idx < 2 else "52%"

            grid.add(
                chart=hist,
                grid_opts=opts.GridOpts(
                    pos_left=pos_left,
                    pos_top=pos_top,
                    width=chart_width,
                    height=chart_height
                )
            )

        # 生成 HTML
        html = grid.render_embed()

        # 添加自定义 CSS 样式
        custom_css = """
        <style>
            body {
                background-color: #f8f9fa;
                margin: 10px;
                font-family: 'Microsoft YaHei', Arial, sans-serif;
            }
            .chart-container {
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                padding: 15px;
                margin: 10px;
            }
            .stats-panel {
                background-color: #e7f5ff;
                border-radius: 4px;
                padding: 8px;
                margin-top: 5px;
                font-size: 12px;
                color: #495057;
            }
        </style>
        """

        # 注入自定义样式
        html = html.replace('<body>', f'<body>{custom_css}')

        # 加载到 Web 视图
        self.web_view.setHtml(html)

        # 发送信号
        self.histogramUpdated.emit()

    def _get_stats_text(self, name):
        """获取统计信息文本"""
        if name not in self.statistics:
            return ""

        stats = self.statistics[name]
        return (
            f"均值:{stats['mean']:.2f} | "
            f"中位数:{stats['median']:.2f} | "
            f"标准差:{stats['std']:.2f} | "
            f"数据量:{stats['count']}"
        )

    def _show_no_data_message(self):
        """显示无数据提示"""
        html = """
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {
                    font-family: 'Microsoft YaHei', Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100%;
                    background-color: #f8f9fa;
                    margin: 0;
                }
                .message {
                    text-align: center;
                    padding: 30px;
                    background-color: #f8f9fa;
                    border: 1px dashed #ced4da;
                    border-radius: 8px;
                    color: #6c757d;
                    font-size: 16px;
                    max-width: 80%;
                }
                .icon {
                    font-size: 48px;
                    margin-bottom: 15px;
                    color: #adb5bd;
                }
            </style>
        </head>
        <body>
            <div class="message">
                <div class="icon">📊</div>
                <div>没有可用的数据进行分析。请选择测点并获取数据。</div>
            </div>
        </body>
        </html>
        """
        self.web_view.setHtml(html)

    def clear(self):
        """清除所有数据和图表"""
        self.data_dict = {}
        self.statistics = {}
        self.current_page = 0

        self.page_combo.blockSignals(True)
        self.page_combo.clear()
        self.page_combo.blockSignals(False)

        self.data_info_label.setText("无数据")
        self.status_label.setText("已清除所有数据")

        self._show_no_data_message()

    def sizeHint(self):
        """返回推荐的部件尺寸"""
        return QSize(800, 600)

    def minimumSizeHint(self):
        """返回最小建议尺寸"""
        return QSize(400, 300)