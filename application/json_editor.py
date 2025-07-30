import copy
import json
import os
import re
from datetime import datetime
from typing import Any

from PyQt5.QtCore import (
    Qt,
    QPoint,
    QEvent,
    QPropertyAnimation,
    QAbstractAnimation,
    QRect,
    QTimer,
    QSize,
    QEasingCurve,
    QThreadPool, QUrl,
)
from PyQt5.QtGui import QColor, QGuiApplication, QIcon, QFontMetrics, QDesktopServices
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QWidget, QMenu, QMessageBox, QSizePolicy,
    QDesktopWidget, QStatusBar, QUndoStack, QAction, QLabel,
    QWidgetAction, QListWidget, QListWidgetItem, QFrame
)
from PyQt5.QtWidgets import (
    QFileDialog, QInputDialog, QShortcut, QAbstractItemView
)
from deepdiff import DeepDiff
from loguru import logger
from qfluentwidgets import FluentIcon as FIF, CommandBar, TabBar, SearchLineEdit, MessageBox, InfoBar, InfoBarPosition, \
    InfoBarIcon, Dialog, PushButton
from qfluentwidgets import RoundMenu, Action

from application.dialogs.histogram_range_set_dialog import IntervalPartitionDialog
from application.dialogs.load_history_dialog import LoadHistoryDialog
from application.dialogs.point_selector_dialog import PointSelectorDialog
from application.dialogs.range_input_dialog import RangeInputDialog
from application.dialogs.range_list_dialog import RangeListDialog
from application.dialogs.time_range_dialog import TimeRangeDialog
from application.dialogs.time_selector_dialog import TimeSelectorDialog
from application.dialogs.version_diff_dialog import VersionDiffDialog
from application.utils.config_handler import (
    load_config,
    save_history,
    save_config,
    HISTORY_PATH,
    PATH_PREFIX,
    FILE_FILTER,
)
from application.utils.data_format_transform import list2str
from application.utils.load_config import ParamConfigLoader
from application.utils.threading_utils import Worker
from application.utils.utils import (
    get_icon,
    get_file_name,
    error_catcher_decorator,
    get_button_style_sheet, get_unique_name, )
from application.widgets.copy_model_messagebox import CopyModelMessageBox
from application.widgets.custom_input_messagebox import CustomMessageBox
from application.widgets.custom_tree_item import ConfigurableTreeWidgetItem
from application.widgets.draggable_tree_widget import DraggableTreeWidget
from application.widgets.tree_edit_command import TreeEditCommand
from application.widgets.upload_dataset_messagebox import UploadDatasetMessageBox
from application.widgets.upload_model_messagebox import UploadModelMessageBox


class JSONEditor(QWidget):
    def __init__(self, home=None):
        super().__init__()
        self.setObjectName("配置编辑")
        self.home = home
        screen_rect = QDesktopWidget().screenGeometry()
        screen_width, screen_height = screen_rect.width(), screen_rect.height()
        self.window_width = int(screen_width * 0.6)
        self.window_height = int(screen_height * 0.75)
        window_icon = get_icon("logo")
        self.setWindowIcon(QIcon(window_icon.pixmap(QSize(128, 128))))
        self.resize(self.window_width, self.window_height)
        # 窗口大小由外部 showMaximized() 或动态 resize 控制
        self.setAcceptDrops(True)
        self.database_loaded = False  # 当前数据库工具是否完成加载
        self.clipboard_item = None
        self.thread_pool = QThreadPool.globalInstance()
        # 文件管理
        self.open_files = {}  # 原有文件内容存储
        self.orig_files = {}  # 存储原始文件路径，用于对比配置差异
        self.model_bindings = {}  # 存储每个文件绑定的模型 {filename: model_id}
        self.model_binding_prefix = "当前关联模型参数："
        self.model_binding_structures = {}
        self.file_format = {}  # 存储文件格式信息
        self.file_states = {}  # 新增：存储每个文件的树状态
        self.current_file = None
        self.untitled_count = 1
        self.active_input = None
        # 动态字体大小
        screen = QGuiApplication.primaryScreen()
        self.scale = int(screen.logicalDotsPerInch() / 96.0)  # 96 DPI 为基准
        base_font = QFont("微软雅黑")
        base_font.setPointSizeF(6 * self.scale)
        self.setFont(base_font)
        # 根据 scale 计算常用间距/圆角
        self.font_size = round(10 * self.scale)

        # 撤销/重做系统
        self.undo_stacks = {}  # 每个文件单独的撤销栈
        self.bind_shortcuts()
        self.init_ui()
        # 配置参数加载
        self.load_config()

    def load_config(self, config_path="default.yaml"):
        if hasattr(self, "config"):
            del self.config

        self.config = ParamConfigLoader(config_path)
        self.config.params_loaded.connect(self.on_config_loaded)
        self.config.load_async()

    def on_config_loaded(self):
        if len(self.open_files) == 0:
            self.new_config()

    def init_ui(self):
        # —— 高 DPI 缩放参数 ——
        px6 = int(6 * self.scale)
        px12 = int(14 * self.scale)
        pt11 = round(10 * self.scale)
        pt12 = round(12 * self.scale)

        # 样式表
        self.setStyleSheet(f"""
            QWidget {{ font-family: "Microsoft YaHei"; font-size: {pt11}pt; background-color: #f5f7fa; }}
            QTreeWidget {{ font-size: {pt12}pt; background-color: #ffffff; border: none; }}
            QTreeWidget::item {{ padding: {px6}px; }}
            QPushButton {{
                padding: {px6}px {px12}px;
                border-radius: {px6}px;
                background-color: #0078d7;
                color: white;
                border: none;
            }}
            QPushButton:hover {{ background-color: #3399ff; }}
            QPushButton:pressed {{ background-color: #005a9e; }}
            QLineEdit {{
                padding: {px6}px;
                border: 1px solid #ccc;
                border-radius: {px6}px;
                background: white;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px;
            }}

            QScrollBar::handle:vertical {{
                background: #adb5bd;
                border-radius: 5px;
                min-height: 30px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: #868e96;
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # 整体布局（保持原有逻辑，仅缩放数值已用 f-string）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.commandBar = CommandBar()
        self._define_command_bar()
        right_widget = QWidget()
        content_layout = QVBoxLayout(right_widget)
        self.tab_bar = TabBar()
        self.tab_bar.setMovable(True)
        self.tab_bar.setScrollable(True)
        self.tab_bar.setTabShadowEnabled(True)
        self.tab_bar.tabAddRequested.connect(self.new_config)
        self.tab_bar.tabCloseRequested.connect(self._on_close)
        self.tree = DraggableTreeWidget(self, draggable=False)
        self.tree.setHeaderLabels(["参数", "值"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setFont(QFont("微软雅黑", 12))
        self.tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.itemDoubleClicked.connect(self.edit_item_value)
        self.tree.setHeaders()
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_tree_context_menu)

        content_layout.addWidget(self.commandBar)
        self.search_line = SearchLineEdit()
        self.search_line.returnPressed.connect(self.on_search)
        self.search_line.searchSignal.connect(self.on_search)
        self.search_line.clearSignal.connect(self.on_search)

        # 创建一个底部对齐的容器
        self.log_container = QFrame()
        self.log_container.setStyleSheet("background-color: transparent; border: none;")  # 保持透明背景
        self.log_container.setFixedHeight(0)  # 初始高度为 0

        # 使用 QVBoxLayout 并设置底部对齐
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_layout.setSpacing(0)
        self.log_layout.setAlignment(Qt.AlignBottom)  # 关键：底部对齐

        # 将 search_line 添加到容器中
        self.log_layout.addWidget(self.search_line, alignment=Qt.AlignBottom)

        # 将容器添加到主布局中（例如右侧趋势面板）
        content_layout.addWidget(self.log_container)

        # 动画控制（加入初始化）
        self.log_anim = QPropertyAnimation(self.search_line, b"maximumHeight")
        self.log_anim.setDuration(250)  # 动画时长，单位毫秒
        self.log_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.log_expanded = False  # 初始未展开
        self.log_container.hide()
        content_layout.addWidget(self.tab_bar)
        content_layout.addWidget(self.tree)

        main_layout.addWidget(right_widget)
        # 添加紧凑型状态栏
        self.status_bar = QStatusBar(self)
        self.status_bar.setStyleSheet("""
                    QStatusBar {
                        background-color: #f8f9fa;
                        border-top: 1px solid #e9ecef;
                        color: #6c757d;
                        padding: 1px 8px;
                        font-size: 9pt;
                        min-height: 20px;
                        max-height: 20px;
                    }
                    QStatusBar::item {
                        border: none;
                        margin: 0px;
                    }
                """)
        self.status_bar.setFixedHeight(20)  # 固定高度使其更紧凑

        # 创建模型选择按钮（带下拉箭头）
        self.model_selector_btn = QPushButton("<无关联模型>")  # 允许水平扩展
        self.model_selector_btn.setToolTip(
            "<div style='background-color:#f0f0f0; color:#333333; "
            "border:1px solid #cccccc; padding:4px 8px;'>绑定数智模型</div>"
        )
        self.model_selector_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; color: #666; padding: 0px 4px; }"
            "QPushButton:hover { color: #1890ff; }"
        )
        self.model_selector_btn.clicked.connect(self.show_model_dropdown)

        # 替换原来的文件信息标签
        self.status_bar.addPermanentWidget(self.model_selector_btn)

        # 添加状态栏到主布局
        main_layout.addWidget(self.status_bar)

    def _define_command_bar(self):
        self.commandBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 逐个添加动作
        self.commandBar.addActions(
            [
                Action(FIF.FOLDER, '打开文件', triggered=self.import_config),
                Action(FIF.SAVE, '保存文件', triggered=self.auto_save),
                Action(FIF.SAVE_AS, '另存文件', triggered=self.export_config),
                Action(get_icon("上传"), '上传配置', triggered=self.do_upload),
            ]
        )
        self.commandBar.addSeparator()

        self.commandBar.addActions(
            [
                Action(get_icon("撤销"), '撤销', triggered=self.undo_action),
                Action(get_icon("恢复"), '恢复', triggered=self.redo_action),
            ]
        )
        self.commandBar.addSeparator()

        # 添加分隔符
        self.commandBar.addActions(
            [
                Action(get_icon("重命名"), '重命名', triggered=self.show_rename_message_box),
                Action(FIF.COPY, '复制配置', triggered=self.show_copy_message_box),
            ]
        )
        self.commandBar.addSeparator()

        # 批量添加动作
        self.commandBar.addActions([
            Action(FIF.HISTORY, '历史记录', triggered=self.load_history_menu),
            Action(FIF.FILTER, '筛选过滤', triggered=self.toggle_viewer),
        ])

        # 添加始终隐藏的动作
        self.commandBar.addHiddenAction(
            Action(
                FIF.GLOBE,
                '前往平台',
                triggered=self._open_platform
            )
        )
        self.commandBar.addHiddenAction(Action(FIF.SETTING, '结构设置', triggered=self._goto_structure_settings))

    @error_catcher_decorator
    def show_model_dropdown(self, *args, **kwargs):

        if hasattr(self, "infobar"):
            try:
                self.infobar.close()
            except Exception:
                pass
            del self.infobar

        if self.config.api_tools.get("di_flow") is None:
            self.create_errorbar("错误", "模型配置错误，请检查！", show_button=True, button_fn=self._goto_api_settings)
            return

        worker = Worker(fn=self.config.api_tools.get("di_flow"))
        worker.signals.finished.connect(self.on_di_flow_get)
        worker.signals.error.connect(self.on_di_flow_get)
        self.thread_pool.start(worker)

    def on_di_flow_get(self, model_names):
        if not isinstance(model_names, list):
            self.create_errorbar("错误", "模型列表获取失败", show_button=True, button_fn=self._goto_api_settings)
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 10pt;
                margin: 0px;
                padding: 0px;
            }
            QMenu::item:selected {
                background-color: #e6f7ff;
                color: #003366;
            }
            QMenu::separator {
                height: 1px;
                background: #ddd;
                margin: 4px 0px;
            }
        """)

        # 添加标题
        title_widget = QLabel("模型列表")
        title_widget.setAlignment(Qt.AlignCenter)
        title_widget.setStyleSheet("""
            background-color: #409EFF;  /* 深蓝标题 */
            color: white;
            font-weight: bold;
            padding: 4px 0px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        """)
        title_action = QWidgetAction(menu)
        title_action.setDefaultWidget(title_widget)
        menu.addAction(title_action)

        def get_max_item_width(menu, model_names):
            font = menu.font()
            fm = QFontMetrics(font)
            max_width = 0
            for item in model_names:
                text_width = fm.width(item)
                max_width = max(max_width, text_width)
            return max_width + 70

        def get_max_item_height(menu, model_names):
            font = menu.font()
            fm = QFontMetrics(font)
            item_height = fm.height() + 8
            return min(2 * item_height * len(model_names), int(0.6 * self.window_height))

        # 创建 QListWidget
        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.SingleSelection)
        list_widget.setFixedHeight(get_max_item_height(menu, model_names))
        list_widget.setFixedWidth(get_max_item_width(menu, model_names))
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #f9f9f9;  /* 浅灰背景 */
                outline: 0px;
                font-size: 10pt;
                border: none;
                padding: 0px;
            }
            QListWidget::item {
                padding: 4px 10px;
            }
            QListWidget::item:selected {
                background-color: #409EFF;  /* 深蓝背景 */
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e6f7ff;
                color: #003366;
            }
        """)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 将 QListWidget 封装为 QWidgetAction
        list_action = QWidgetAction(menu)
        list_action.setDefaultWidget(list_widget)
        menu.addAction(list_action)

        # 添加模型项
        current_model = self.model_bindings.get(self.current_file)
        for model_name in model_names:
            item = QListWidgetItem(model_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if model_name == current_model else Qt.Unchecked)
            list_widget.addItem(item)

        # 连接点击事件
        list_widget.itemClicked.connect(lambda item: self.handle_model_selected(item, menu))

        # 添加分隔线
        menu.addSeparator()

        # 添加"无关联模型"选项
        no_model_action = QAction("<无关联模型>", menu)
        no_model_action.setCheckable(True)
        no_model_action.setChecked(current_model is None)
        no_model_action.triggered.connect(lambda: self.bind_model(None))
        menu.addAction(no_model_action)
        # 添加分隔线
        menu.addSeparator()

        # 添加“添加新模型”选项（带上传图标）
        add_upload_action = QAction("上传新模型", menu)
        add_upload_action.triggered.connect(lambda: self.handle_upload_model())
        menu.addAction(add_upload_action)
        # 添加分隔线
        menu.addSeparator()
        # 添加“复制模型”选项（带复制图标）
        add_copy_action = QAction("复制现有模型", menu)
        add_copy_action.triggered.connect(lambda: self.handle_copy_model())
        menu.addAction(add_copy_action)
        # 计算弹窗位置
        pos = self.model_selector_btn.mapToGlobal(QPoint(0, 0))
        menu_height = menu.sizeHint().height()
        menu_width = menu.sizeHint().width()
        target_pos = QPoint(pos.x() - int(0.9 * menu_width), pos.y() - menu_height)
        menu.exec_(target_pos)

    def handle_model_selected(self, item, menu):
        model_name = item.text()
        self.bind_model(model_name)
        menu.close()  # 点击后关闭菜单

    def bind_model(self, model_id):
        if not self.current_file:
            return
        self.file_states[self.current_file] = self.capture_tree_state()
        # 获取当前模型参数
        current_model = self.model_bindings.get(self.current_file)
        current_data = self.capture_tree_data()

        # 创建撤销命令
        old_state = copy.deepcopy(current_data)

        # 去除之前关联的模型
        current_data = {
            key: value for key, value in current_data.items()
            if not re.search(f"{self.model_binding_prefix}", key)
        }

        # 更新绑定关系
        if not model_id or model_id == "<无关联模型>":
            self.model_bindings.pop(self.current_file, None)
            self.model_selector_btn.setText("<无关联模型>")
            self.model_selector_btn.setIcon(QIcon())
            self.undo_stack.push(TreeEditCommand(self, old_state, "取消模型绑定"))
            self.config.remove_binding_model_params()
            self.tree.clear()
            self.load_tree(current_data)
            return

        self.model_bindings[self.current_file] = model_id
        worker = Worker(self.config.api_tools.get("di_flow_params"), self.model_binding_prefix,
                        model_id)
        worker.signals.finished.connect(self.on_model_binded)
        self.thread_pool.start(worker)

    def merge_model_params(self, current_data, model_params, model_name):
        """将模型参数合并到当前配置中"""
        merged = copy.deepcopy(current_data)

        # 查找合适的插入位置（假设插入到根目录）
        model_name = f"{self.model_binding_prefix}{model_name}"
        merged[model_name] = {}

        # 转换模型参数格式
        for param_id, param_info in model_params.items():
            name = param_info.pop("name")
            # 处理组件名称重复
            name = get_unique_name(name, merged[model_name].keys())
            merged[model_name][name] = {}
            for keym, value in param_info.items():
                merged[model_name][name][value.get("param_name")] = value.get("default")

        return merged

    def undo_action(self):
        """执行撤销操作"""
        if self.undo_stack.canUndo():
            self.undo_stack.undo()
            self.show_status_message("已撤销上一操作", "info", 2000)
        else:
            self.show_status_message("没有可撤销的操作", "warning", 2000)

    def redo_action(self):
        """执行重做操作"""
        if self.undo_stack.canRedo():
            self.undo_stack.redo()
            self.show_status_message("已重做操作", "info", 2000)
        else:
            self.show_status_message("没有可重做的操作", "warning", 2000)

    def do_upload(self, name=None):
        name = name if name else self.current_file
        self.auto_save()
        work = Worker(
            self.config.api_tools.get("file_upload"),
            file_path=os.path.join(
                PATH_PREFIX,
                f"{self.current_file}.{self.file_format.get(self.current_file, 'json')}",
            ),
            dataset_name=name,
            dataset_desc=f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            tree_name="0",
            tree_no="0",
        )
        work.signals.finished.connect(self.update_config)
        self.thread_pool.start(work)

    def update_config(self, file_upload_result):
        if "filePath" not in file_upload_result:
            return
        file_url = file_upload_result['filePath']
        upload_paths = self.config.get_all_upload_paths()  # 获取所有 upload 路径

        if not upload_paths:
            self.show_status_message("未找到可同步的配置项", "info")
            return

        # 只有一个，直接使用
        if len(upload_paths) == 1:
            selected_path = upload_paths[0]
        else:
            # 多个路径，弹出选择框
            upload_messagebox = UploadDatasetMessageBox(upload_paths, self)
            if upload_messagebox.exec():
                selected_path = upload_messagebox.get_text()
            else:
                self.show_status_message("用户取消了文件上传操作", "info")
                return

        # 执行更新逻辑
        upload_item = self.get_item_by_path(selected_path)
        if not upload_item:
            self.show_status_message("目标项不存在", "error")
            return

        old_state = self.capture_tree_data()  # 保存旧状态

        upload_item.setText(1, file_url)
        self.config.api_tools.get("di_flow_params_modify").call(
            param_no=self.config.get_model_binding_param_no(selected_path),
            param_val=file_url
        )

        self.undo_stack.push(TreeEditCommand(self, old_state, f"更新文件地址为: {file_url}"))
        self.show_status_message(f"文件地址已同步到: {selected_path}", "success")

    def capture_tree_state(self):
        """
        遍历当前 tree，记录所有展开节点的路径和当前选中节点路径
        """
        expanded = set()

        def recurse(item, path):
            key = f"{path}/{item.text(0)}"
            if item.isExpanded():
                expanded.add(key)
            for i in range(item.childCount()):
                recurse(item.child(i), key)

        for i in range(self.tree.topLevelItemCount()):
            recurse(self.tree.topLevelItem(i), "root")

        selected = None
        item = self.tree.currentItem()
        if item:
            path_parts = []
            node = item
            while node:
                path_parts.insert(0, node.text(0))
                node = node.parent()
            selected = '/'.join(path_parts)
        return {'expanded': expanded, 'selected': selected}

    def capture_tree_data(self, tree_root=None):
        """
        将当前 tree 结构及值转换为字典形式，用于保存到 open_files
        """

        def recurse(item):
            node = {}
            # 以节点文本作为 key，若有子节点则递归，否则以文本值作为 leaf
            if item.childCount() == 0:
                return item.text(1)
            else:
                for i in range(item.childCount()):
                    child = item.child(i)
                    node[child.text(0)] = recurse(child)
                return node

        result = {}
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            result[top.text(0)] = recurse(top)
        return result

    def restore_tree_state(self, filename):
        """
        根据保存的状态展开节点并选中节点
        """
        state = self.file_states.get(filename)
        if not state:
            return
        expanded = state['expanded']
        selected = state['selected']

        def recurse(item, path):
            key = f"{path}/{item.text(0)}"
            if key in expanded:
                item.setExpanded(True)
            for i in range(item.childCount()):
                recurse(item.child(i), key)

        for i in range(self.tree.topLevelItemCount()):
            recurse(self.tree.topLevelItem(i), "root")

        if selected:
            parts = selected.split('/')

            def find_item(item, parts):
                if item.text(0) != parts[0]:
                    return None
                if len(parts) == 1:
                    return item
                for i in range(item.childCount()):
                    res = find_item(item.child(i), parts[1:])
                    if res:
                        return res
                return None

            for i in range(self.tree.topLevelItemCount()):
                res = find_item(self.tree.topLevelItem(i), parts)
                if res:
                    self.tree.setCurrentItem(res)
                    break

    def restore_tree_state_only(self, state):
        """
        仅恢复树的展开状态，不改变当前选中项
        用于撤销/重做操作中保持树的展开状态
        """
        if not state:
            return
        expanded = state['expanded']

        def recurse(item, path):
            key = f"{path}/{item.text(0)}"
            if key in expanded:
                item.setExpanded(True)
            for i in range(item.childCount()):
                recurse(item.child(i), key)

        for i in range(self.tree.topLevelItemCount()):
            recurse(self.tree.topLevelItem(i), "root")

    def switch_to_file(self, filename):
        if filename == self.current_file:
            return

        # 如果有当前文件，先保存其数据和状态
        if self.current_file is not None:
            # 1. 保存当前文件配置数据
            self.open_files[self.current_file] = self.capture_tree_data()
            # 2. 保存展开/选中状态
            self.file_states[self.current_file] = self.capture_tree_state()
            if hasattr(self, 'undo_stack'):
                self.undo_stacks[self.current_file] = self.undo_stack

        # 切换逻辑
        self.current_file = filename
        self.tree.clear()
        # 从 open_files 中加载配置数据并生成树节点
        self.load_tree(self.open_files[filename])
        # 恢复展开/选中状态
        self.restore_tree_state(filename)

        # 获取目标文件的 undo stack 或新建一个
        self.undo_stack = self.undo_stacks.get(filename, QUndoStack(self))

    def is_same_as_file(self, name):
        # 判断当前配置是否与文件内容一致
        path = self.orig_files.get(name, f"configurations/{name}.{self.file_format.get(name, 'json')}")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                orig_data = json.load(f)
                diff = DeepDiff(self.tree_to_dict(), orig_data, ignore_order=True)
                return len(diff) == 0
        else:
            return False

    def close_file(self, filename):
        # 1. 确认要关闭的确实是打开列表里的
        if filename not in self.open_files:
            return
        tab_names = [k for k in self.tab_bar.itemMap]
        # 5. 从数据模型和状态里删
        self.open_files = {
            k: v for k, v in self.open_files.items() if k in tab_names
        }
        self.orig_files = {
            k: v for k, v in self.orig_files.items() if k in tab_names
        }
        self.file_format = {
            k: v for k, v in self.file_format.items() if k in tab_names
        }
        self.file_states = {
            k: v for k, v in self.file_states.items() if k in tab_names
        }
        self.undo_stacks = {
            k: v for k, v in self.undo_stacks.items() if k in tab_names
        }

    def show_status_message(self, message, message_type="info", duration=3000):
        """在状态栏显示美观的临时消息

        参数:
            message: 要显示的消息
            message_type: 消息类型 ("info", "success", "warning", "error")
            duration: 显示时长(毫秒)，0表示永久显示
        """
        # 根据消息类型设置样式
        icon = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "loading": "⏳"
        }.get(message_type, "ℹ️")

        color = {
            "info": "#1890ff",
            "success": "#52c41a",
            "warning": "#faad14",
            "error": "#f5222d",
            "loading": "#1890ff"
        }.get(message_type, "#1890ff")

        # 创建消息标签
        msg_label = QPushButton(f"{icon} {message}")
        msg_label.setStyleSheet(f"""
            QPushButton {{ 
                border: none; 
                background: transparent; 
                color: {color}; 
                padding: 0px 4px;
            }}
        """)

        # 添加到状态栏
        self.status_bar.addWidget(msg_label)

        # 如果设置了显示时长，则定时移除
        if duration > 0:
            QTimer.singleShot(duration, lambda: self.status_bar.removeWidget(msg_label))

        return msg_label

    def new_config(self):
        # 1. 造名、注册模型
        name = f"未命名{self.untitled_count}"
        self.untitled_count += 1
        # 2. 加 UI tab
        name = self.add_tab(name)
        self.tab_bar.setCurrentIndex(self.tab_bar.count() - 1)
        self.config.remove_binding_model_params()
        # 记录打开的配置文件
        self.open_files[name] = copy.deepcopy(self.config.init_params)
        self.file_format[name] = "json"
        # 为新文件创建一个新的撤销栈
        self.undo_stacks[name] = QUndoStack(self)

        # 3. 立即切到这个新 tab
        #    这样 current_file、tree、状态 都会被正确赋值
        self.switch_to_file(name)

        # 显示状态消息
        self.show_status_message(f"已创建新配置", "success", 500)
        self.create_infobar("可以通过右下角按钮关联、上传或复制数智模型", "", duration=-1)

    def create_toggle_handler(self, wrapper, anim, field):
        def handler():
            # —— 如果有别的输入框打开，先隐藏它 —— #
            if self.active_input and self.active_input[0] is not wrapper:
                prev_wrapper, prev_anim, prev_field = self.active_input
                self.hide_input(prev_anim, prev_field)

            # —— 面板宽度动画（保持不变） —— #
            target_w = 300 if (not self.active_input or self.active_input[0] is not wrapper) else 80
            self.panel_anim.stop()
            self.panel_anim.setStartValue(self.left_panel.width())
            self.panel_anim.setEndValue(target_w)
            self.panel_anim.start()

            # —— 切换当前 wrapper —— #
            is_currently_collapsed = not (self.active_input and self.active_input[0] is wrapper)
            if is_currently_collapsed:
                # 展开
                anim.setDirection(QAbstractAnimation.Forward)
                anim.start()
                field.show()
                field.setFocus()
                self.active_input = (wrapper, anim, field)
            else:
                # 收起
                self.hide_input(anim, field)
                self.active_input = None

        return handler

    def hide_input(self, anim, field):
        # 收拢面板
        self.panel_anim.stop()
        self.panel_anim.setStartValue(self.left_panel.width())
        self.panel_anim.setEndValue(85 * self.scale)
        self.panel_anim.start()

        # 隐藏输入框
        anim.setDirection(QAbstractAnimation.Backward)
        anim.start()
        field.hide()

        # 重置
        self.active_input = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and self.active_input:
            wrapper, anim, field = self.active_input

            # 把 wrapper 转为全局矩形
            top_left = wrapper.mapToGlobal(QPoint(0, 0))
            rect = QRect(top_left, wrapper.size())

            # 如果点击位置不在 wrapper（包含 field）内，就收起
            if not rect.contains(event.globalPos()):
                self.hide_input(anim, field)
        # 一定要返回父类的过滤结果
        return super().eventFilter(obj, event)

    def toggle_search_bar(self, tool_name):
        """显示/隐藏输入框（保持原功能）"""
        input_field = self.tool_inputs.get(tool_name)
        if input_field:
            input_field.setVisible(not input_field.isVisible())
            if input_field.isVisible():
                input_field.setFocus()

    @error_catcher_decorator
    def edit_item_value(self, item, column):
        if column != 1 or item.data(0, Qt.UserRole):
            return

        full_path = self.get_path_by_item(item)
        param_name = item.text(0)
        current_value = item.text(1)

        # 保存当前状态用于撤销
        old_state = self.capture_tree_data()

        # 使用动画效果突出显示当前编辑的项
        orig_bg = item.background(1)
        item.setBackground(1, QColor('#e6f7ff'))

        param_type = self.config.params_type.get(full_path)

        # 编辑完成后恢复原背景的回调函数
        def restore_background():
            item.setBackground(1, orig_bg)
            self.tree.update()

        if param_type == "time":
            dlg = TimeSelectorDialog(current_value)
            dlg.setWindowTitle(f"选择 {param_name} 时间")
            if dlg.exec_() == QDialog.Accepted:
                item.setText(1, dlg.get_time())
            restore_background()
        elif param_type == "time_range_select":
            # 显示加载提示
            self.show_status_message("正在加载时间范围选择器...")

            # 创建并显示时间范围选择对话框，优化标题和UI
            curve_viewer = TimeRangeDialog(
                self.config.get_tools_by_type("trenddb-fetcher")[0],
                current_text=current_value,
                parent=self
            )
            self.home.addSubInterface(curve_viewer, get_icon("框选"), '训练数据框选', parent=self)
            self.home.switchTo(curve_viewer)
            if curve_viewer.exec_() == QDialog.Accepted:
                # 获取用户选择的时间范围
                new_value = curve_viewer.get_selected_time_ranges()
                item.setText(1, new_value)
                # 高亮显示变化
                if new_value != current_value:
                    item.setForeground(1, QColor('#1890ff'))
                    QTimer.singleShot(2000, lambda: item.setForeground(1, QColor('black')))
            self.home.removeInterface(curve_viewer)
            self.home.switchTo(self)
            restore_background()
        elif param_type == "partition":
            # 获取同级测点名列表
            parent = item.parent()
            select_point = None

            # 寻找测点名参数
            for i in range(parent.childCount()):
                if parent.child(i).text(0) == "测点名":
                    select_point = parent.child(i).text(1).split("\n")[0]
                    break

            if select_point:
                # 显示加载提示
                self.show_status_message(f"正在为测点 {select_point} 加载数据...")

                # 弹出划分对话框
                dlg = IntervalPartitionDialog(
                    dfs=self.config.get_tools_by_type("trenddb-fetcher"),
                    point_name=select_point,
                    current_text=current_value,
                    type="partition",
                    parent=self
                )
                self.home.addSubInterface(dlg, get_icon("框选"), '区间选择', parent=self)
                self.home.switchTo(dlg)
                # 用户需要先在主界面勾选测点，再使用对话框中的时间范围和分箱宽度获取数据
                if dlg.exec_() == QDialog.Accepted:
                    intervals = dlg.get_intervals()
                    # 格式化区间字符串，增加易读性
                    text = list2str(intervals)
                    item.setText(1, text)
                    # 高亮显示变化
                    if text != current_value:
                        item.setForeground(1, QColor("#1890ff"))
                        QTimer.singleShot(
                            2000, lambda: item.setForeground(1, QColor("black"))
                        )
                self.home.removeInterface(dlg)
                self.home.switchTo(self)
                restore_background()
            else:
                # 如果没有找到测点，使用纯手动编辑模式
                dlg = RangeListDialog(current_value)
                dlg.setWindowTitle(f"区间列表编辑 - {param_name}")
                if dlg.exec_() == QDialog.Accepted:
                    new_value = dlg.get_ranges()
                    if new_value != current_value:
                        item.setText(1, new_value)
                        # 高亮新值
                        item.setForeground(1, QColor('#1890ff'))
                        QTimer.singleShot(2000, lambda: item.setForeground(1, QColor('black')))
            restore_background()
        elif param_type == "range":
            # 获取同级测点名列表
            parent = item.parent()
            select_point = None

            # 查找相关测点
            for i in range(parent.childCount()):
                if parent.child(i).text(0) == "测点名":
                    select_point = parent.child(i).text(1).split("\n")[0]
                    break

            if select_point:
                # 显示加载状态
                self.show_status_message(f"正在为测点 {select_point} 加载数据范围...")

                # 弹出划分对话框
                dlg = IntervalPartitionDialog(
                    dfs=self.config.get_tools_by_type("trenddb-fetcher"),
                    point_name=select_point,
                    current_text=current_value,
                    type="range",
                    parent=self
                )
                self.home.addSubInterface(dlg, get_icon("框选"), '范围选择', parent=self)
                self.home.switchTo(dlg)
                # 用户需要先在主界面勾选测点，再使用对话框中的时间范围和分箱宽度获取数据
                if dlg.exec_() == QDialog.Accepted:
                    intervals = dlg.get_intervals()
                    # 格式化区间字符串为整体范围
                    text = list2str(intervals)
                    if text != current_value:
                        item.setText(1, text)
                        # 高亮新值
                        item.setForeground(1, QColor("#1890ff"))
                        QTimer.singleShot(
                            2000, lambda: item.setForeground(1, QColor("black"))
                        )
                self.home.removeInterface(dlg)
                self.home.switchTo(self)
            else:
                # 如果没有找到测点，使用纯手动编辑模式
                dlg = RangeInputDialog(current_value)
                dlg.setWindowTitle(f"范围输入 - {param_name}")
                if dlg.exec_() == QDialog.Accepted:
                    if dlg.result != current_value:
                        item.setText(1, dlg.result)
                        # 高亮显示新值
                        item.setForeground(1, QColor('#1890ff'))
                        QTimer.singleShot(2000, lambda: item.setForeground(1, QColor('black')))
            restore_background()
        elif param_type == "fetch":
            # 显示加载状态
            self.show_status_message("正在加载测点选择器...")

            # 获取当前编辑路径的测点获取工具
            fetchers = self.config.get_tools_by_path(full_path)
            # 创建并显示测点选择对话框
            dlg = PointSelectorDialog(
                fetchers=fetchers,
                data_fetcher=self.config.get_tools_by_type("trenddb-fetcher")[0],
                current_value=current_value,
                parent=self
            )
            self.home.addSubInterface(dlg, get_icon("选择器"), '测点选择', parent=self)
            self.home.switchTo(dlg)
            if dlg.exec_() == QDialog.Accepted:
                selected_point = dlg.selected_point
                selected_description = dlg.selected_point_description

                # 确保 selected_description 是字符串类型
                selected_description = str(selected_description)

                # 组合显示值
                new_value = f"{selected_point}\n{selected_description}"

                if new_value != current_value:
                    item.setText(1, new_value)

                    # 高亮新值
                    item.setForeground(1, QColor("#1890ff"))
                    QTimer.singleShot(
                        2000, lambda: item.setForeground(1, QColor("black"))
                    )

            self.home.removeInterface(dlg)
            self.home.switchTo(self)
            restore_background()
            # —— 其他类型分支 —— #
        elif param_type in ["slider", "checkbox", "text", "dropdown", "multiselect_dropdown", "upload"]:
            pass  # 一直在界面显示
        else:
            raise ValueError(f"未知参数类型：{param_type}")

        self.tree.updateGeometries()  # 强制更新布局信息
        self.tree.viewport().update()
        # 记录撤销操作

        self.undo_stack.push(TreeEditCommand(self, old_state, f"编辑 {param_name}"))

    # ================= 增强的导入/导出方法 =================
    def import_config(self):
        """导入配置文件，支持覆盖/保留/跳过"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", PATH_PREFIX, "配置文件 (*.json *.yaml *.yml *.ini)"
        )
        if not path:
            return

        filename = get_file_name(path)
        # 文件名冲突处理
        if filename in self.open_files:
            box = MessageBox("文件已存在", f"文件“{filename}”已经打开，是否覆盖当前配置？", self)
            box.yesButton.setText("覆盖")
            box.cancelButton.setText("保留")

            if box.exec():
                config = load_config(path)
                self.open_files[filename] = config
                self.orig_files[filename] = path
                if self.current_file == filename:
                    self.tree.clear()
                    self.load_tree(config)
                else:
                    self.tab_bar.setCurrentTab(filename)
                    self.switch_to_file(filename)
                return
            else:
                # 自动重命名
                base, ext = os.path.splitext(filename)
                i = 1
                new_filename = f"{base}_{i}{ext}"
                while new_filename in self.open_files:
                    i += 1
                    new_filename = f"{base}_{i}{ext}"
                filename = new_filename

        # 正常添加新文件
        config = load_config(path)
        self.open_files[filename] = config
        self.orig_files[filename] = path
        self.file_format[filename] = path.split(".")[-1]
        self.add_tab(filename)
        self.tab_bar.setCurrentIndex(self.tab_bar.count() - 1)
        self.switch_to_file(filename)
        self.create_successbar("文件加载成功！")

    def auto_save(self):
        if not self.current_file:
            return

        # 获取数据并保存
        data = self.tree_to_dict()
        file_name = f"{self.current_file}.{self.file_format.get(self.current_file, 'json')}"
        save_config(os.path.join(PATH_PREFIX, file_name), data)
        save_history(os.path.join(PATH_PREFIX, file_name), data)
        # 显示保存成功消息
        save_time = datetime.now().strftime("%H:%M:%S")
        self.create_successbar(f"文件已保存! ({save_time})")

    def rename_file(self, old_name, new_name):
        if old_name == new_name:
            return
        # 更新 open_files
        if old_name in self.file_states:
            self.file_states.pop(old_name)
        if old_name in self.open_files:
            self.open_files.pop(old_name)
        if old_name in self.orig_files:
            self.orig_files.pop(old_name)
        if self.current_file is not None:
            # 1. 保存当前文件配置数据
            self.open_files[new_name] = self.capture_tree_data()
            # 2. 保存展开/选中状态
            self.file_states[new_name] = self.capture_tree_state()
            self.file_format[new_name] = self.file_format.pop(old_name)
            if hasattr(self, 'undo_stack'):
                self.undo_stacks[new_name] = self.undo_stack

        self.current_file = new_name
        if old_name in self.model_bindings:
            self.model_bindings[new_name] = self.model_bindings.pop(old_name)
            self.model_binding_structures[new_name] = self.model_binding_structures.pop(old_name)

        index = self.tab_bar._currentIndex
        self.tab_bar.removeTabByKey(old_name)
        self.tab_bar.insertTab(
            index=index,
            routeKey=new_name,
            text=new_name,
            onClick=lambda: (
                self.switch_to_file(new_name)
            )
        )
        self.tab_bar.setCurrentIndex(index)
        self.create_successbar(f"文件已重命名!")

    def export_config(self):
        if not self.current_file:
            return
        data = self.tree_to_dict()
        path, _ = QFileDialog.getSaveFileName(
            self, "保存配置", os.path.join(PATH_PREFIX, self.current_file), FILE_FILTER)
        if not path:
            return
        save_config(path, data)
        save_history(path, data)
        save_time = datetime.now().strftime("%H:%M:%S")
        self.create_successbar(f"文件已保存! ({save_time})!")
        self.orig_files[".".join(os.path.basename(path).split(".")[:-1])] = path
        self.tab_bar.rename_tab(self.current_file, ".".join(os.path.basename(path).split(".")[:-1]))

    def bind_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self, self.export_config)
        QShortcut(QKeySequence("Ctrl+A"), self, self.add_sub_param)
        QShortcut(QKeySequence("Delete"), self, self.remove_param)
        QShortcut(QKeySequence("Tab"), self, self.load_history_menu)

        # 添加撤销/重做快捷键
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo_action)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.redo_action)

    def on_tree_context_menu(self, pos: QPoint):
        # 获取当前项
        item = self.tree.itemAt(pos)
        full_path = self.get_path_by_item(item)
        # 创建上下文菜单
        menu = RoundMenu()
        if item and self.config.params_type.get(self.get_path_by_item(item)) == "subgroup":
            menu.addActions(
                [
                    Action(FIF.FOLDER_ADD, "添加子参数", triggered=lambda: self.add_sub_param(None, None))
                ]
            )
        # 创建一级菜单项
        menu.addActions(
            [
                Action(FIF.ADD, "新增参数", triggered=self.add_param)
            ]
        )
        if item:
            # 删除操作
            menu.addAction(Action(FIF.DELETE, "删除参数", triggered=self.remove_param))

        if item and self.model_binding_prefix in full_path and len(full_path.split("/")) == 2:
            menu.addAction(Action(FIF.PLAY, "运行至该组件", triggered=self.run_param))

        menu.addSeparator()
        # 视图操作作为一级菜单项
        if item and item.childCount() > 0:
            menu.addAction(Action(FIF.DOWN, "展开", triggered=lambda: item.setExpanded(True)))
            menu.addAction(Action(FIF.UP, "折叠", triggered=lambda: item.setExpanded(False)))
        else:
            menu.addAction(Action(FIF.DOWN, "展开全部", triggered=self.tree.expandAll))
            menu.addAction(Action(FIF.UP, "折叠全部", triggered=self.tree.collapseAll))

        menu.addSeparator()
        menu.addAction(Action(FIF.SETTING, "参数设置", triggered=lambda: self._goto_structure_settings(full_path.split("/")[0])))

        menu.exec_(self.tree.viewport().mapToGlobal(pos), ani=False)

    def clone_item(self, item):
        new_item = ConfigurableTreeWidgetItem(item.text(0), item.text(1), item.full_path, item.control_type, self)
        for i in range(item.childCount()):
            child = item.child(i)
            new_child = self.clone_item(child)
            new_item.addChild(new_child)
        return new_item

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def gather_tags(self,
                    data: dict = None,
                    tag_name: str = "测点名",
                    type: Any = "",
                    with_type: bool = False) -> list:
        """
        将配置文件中的配置参数名称进行提取

        :param data: 待提取配置文件
        :param tag_name: 标签名，默认为测点名
        :param type: 标签类型，比如：控制参数、目标参数。。。
        :param with_type: 提取结果是否带标签信息
        :return:
        """
        data = self.tree_to_dict() if data is None else data

        tags = []
        for k, v in data.items():
            if len(type) > 0 and k not in type: continue
            if isinstance(v, dict):
                new_tags = self.gather_tags(v)
                tags.extend(
                    [f"{k}:{tag}" for tag in new_tags]
                    if with_type
                    else new_tags
                )
            elif k == tag_name and len(v) > 0:
                tags.append(v)
                return tags

        return tags

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.split(".")[-1] not in ["json", "yaml", "yml", "ini"]:
                continue

            filename = get_file_name(path)

            if filename in self.open_files:
                box = MessageBox("文件已存在", f"文件“{filename}”已经打开，是否覆盖当前配置？", self)
                box.yesButton.setText("覆盖")
                box.cancelButton.setText("保留")

                if box.exec():
                    config = load_config(path)
                    self.open_files[filename] = config
                    self.orig_files[filename] = path
                    if self.current_file == filename:
                        self.tree.clear()
                        self.load_tree(config)
                    else:
                        self.tab_bar.setCurrentTab(filename)
                        self.switch_to_file(filename)
                    return
                else:
                    # 自动重命名
                    base, ext = os.path.splitext(filename)
                    i = 1
                    new_filename = f"{base}_{i}{ext}"
                    while new_filename in self.open_files:
                        i += 1
                        new_filename = f"{base}_{i}{ext}"
                    filename = new_filename

            # 没有重复或选择保留 -> 正常添加
            config = load_config(path)
            self.open_files[filename] = config
            self.orig_files[filename] = path
            self.file_format[filename] = path.split(".")[-1]
            self.add_tab(filename)
            self.tab_bar.setCurrentIndex(self.tab_bar.count() - 1)
            self.switch_to_file(filename)

    def show_rename_message_box(self):
        rename_message_box = CustomMessageBox("重命名配置", "输入新配置名称", self.current_file, self)

        if rename_message_box.exec():
            filename = rename_message_box.get_text()
            self.rename_file(self.current_file, filename)
        else:
            return

    def show_copy_message_box(self):
        copy_message_box = CustomMessageBox("复制配置", "输入新配置名称", parent=self)

        if copy_message_box.exec():
            filename = copy_message_box.get_text()
            self.open_files[filename] = self.capture_tree_data()
            self.orig_files[filename] = os.path.join(PATH_PREFIX, filename)
            self.file_format[filename] = self.file_format[self.current_file]
            self.add_tab(filename)
            self.tab_bar.setCurrentIndex(self.tab_bar.count() - 1)
            self.switch_to_file(filename)
        else:
            return

    def reload_tree(self, data: dict = None):
        if data is None:
            data = self.tree_to_dict()

        self.tree.clear()
        self.load_tree(data)

    def get_path_by_item(self, item):
        parts = []
        while item:
            if not re.search(r' [参数]*[0-9]+', item.text(0)): parts.insert(0, item.text(0))
            item = item.parent()

        return "/".join(parts)

    def get_item_by_path(self, path):
        """
        根据路径字符串查找对应的 ConfigurableTreeWidgetItem
        :param path: 路径字符串，如 "根节点/子节点/目标节点"
        :return: 匹配的 ConfigurableTreeWidgetItem 或 None
        """
        if not path or not self.tree:
            return None

        # 分割路径
        target_parts = path.split('/')

        # 从顶层节点开始查找
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            result = self._find_child_by_path(top_item, target_parts)
            if result:
                return result

        return None

    def _find_child_by_path(self, item, parts):
        """
        递归查找子节点
        :param item: 当前检查的节点
        :param parts: 剩余路径部分
        :return: 匹配的 ConfigurableTreeWidgetItem 或 None
        """
        if not parts:
            return item  # 路径已匹配完成

        current_part = parts[0]

        # 检查当前节点是否匹配路径段（同时考虑正则排除逻辑）
        if item.text(0) == current_part:
            if len(parts) == 1:
                return item  # 最后一个路径段匹配成功
            else:
                # 继续查找子节点
                for i in range(item.childCount()):
                    child = item.child(i)
                    match = self._find_child_by_path(child, parts[1:])
                    if match:
                        return match
        return None

    def lock_item(self, key, parent, item):
        full_path = self.get_path_by_item(item)
        if self.config.params_type.get(full_path) in ["group", "subgroup"]:
            self.mark_item_locked(item, self.config.params_type.get(full_path))
        if parent and re.search(r' [参数]*[0-9]+', key):
            parent_path = self.get_path_by_item(parent)
            if self.config.params_type.get(parent_path) == "subgroup":
                self.mark_item_locked(item)

    @error_catcher_decorator
    def load_tree(self, data, parent=None, path_prefix="", bind_model=True):
        # 加载配置时如果有对应绑定模型后的配置，自动关联到对应模型
        matched_key = next((key for key in data if self.model_binding_prefix in key), None)
        if bind_model and matched_key and self.config.api_tools.get("di_flow_params"):
            model_match = re.findall(rf"{self.model_binding_prefix}(.+)", matched_key)
            if model_match:
                model_name = model_match[0]
                if model_name != self.model_bindings.get(self.current_file):
                    self.model_bindings[self.current_file] = model_name
                    worker = Worker(self.config.api_tools.get("di_flow_params"), self.model_binding_prefix,
                                    model_name)
                    worker.signals.finished.connect(lambda result: self.on_model_binded(result, data))
                    self.thread_pool.start(worker)
                    return
            self.config.remove_binding_model_params()
            self.config.add_binding_model_params(self.model_binding_structures[self.current_file])
            self.model_selector_btn.setText(self.model_bindings.get(self.current_file))
            self.model_selector_btn.setIcon(get_icon("模型管理"))
        elif bind_model and not matched_key:
            self.config.remove_binding_model_params()
            self.model_selector_btn.setText("<无关联模型>")
            self.model_selector_btn.setIcon(QIcon())
        # 如果有没有在初始化参数中出现的参数，则自动根据初始化参数添加
        data = self.config.init_params | data if not path_prefix else data
        # 正常加载参数配置
        for key, value in data.items():
            full_path = f"{path_prefix}/{key}" if path_prefix and not re.search(r' [参数]*[0-9]+', key) else key
            param_type = self.config.params_type.get(full_path)
            required = self.config.require_flag.get(full_path)
            if isinstance(value, list):
                item = ConfigurableTreeWidgetItem(key, list2str(value), editor=self, required=required)

                if parent:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)

            elif isinstance(value, dict):
                item = ConfigurableTreeWidgetItem(key, "", editor=self, required=required)
                if parent:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)

                self.lock_item(key, parent, item)
                if re.search(r' [参数]*[0-9]+', full_path):
                    self.load_tree(value, item, path_prefix=path_prefix, bind_model=False)
                else:
                    self.load_tree(value, item, path_prefix=full_path, bind_model=False)
            else:

                item = ConfigurableTreeWidgetItem(
                    key,
                    value,
                    full_path,
                    control_type=param_type,
                    editor=self,
                    required=required
                )
                if parent:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
                self.lock_item(key, parent, item)

            item.set_item_widget()

    def on_model_binded(self, result, current_data=None):
        self.config.remove_binding_model_params()
        current_data = self.capture_tree_data() if current_data is None else current_data
        # 去除之前关联的模型
        current_data = {
            key: value for key, value in current_data.items()
            if not re.search(f"{self.model_binding_prefix}", key)
        }
        model_params, param_structure, self.option2val = result
        if model_params is None:
            self.load_tree(current_data, bind_model=False)
        else:
            self.model_binding_structures[self.current_file] = param_structure
            self.config.add_binding_model_params(param_structure)
            self.model_selector_btn.setText(self.model_bindings.get(self.current_file))
            self.model_selector_btn.setIcon(get_icon("模型管理"))

            merged_data = self.merge_model_params(current_data, model_params,
                                                  self.model_bindings.get(self.current_file))
            self.open_files[self.current_file] = merged_data
            # 更新树
            self.tree.clear()
            self.load_tree(merged_data, bind_model=False)
            self.restore_tree_state(self.current_file)
            # 更新撤销栈
            self.undo_stack.push(
                TreeEditCommand(self, current_data, f"绑定模型: {self.model_bindings.get(self.current_file)}"))

            self.create_successbar(f"已绑定模型: {self.model_bindings.get(self.current_file)}")

    def add_param(self):
        item = self.tree.currentItem()
        name, ok = QInputDialog.getText(self, "参数名称", "请输入参数名称:")
        if ok and name:
            value, ok = QInputDialog.getText(self, "参数值", "请输入参数值:")
            if ok:
                # 保存当前状态用于撤销
                old_state = self.capture_tree_data()

                new_item = ConfigurableTreeWidgetItem(name, value)
                if item:
                    item.addChild(new_item)
                else:
                    self.tree.addTopLevelItem(new_item)

                # 记录撤销操作
                self.undo_stack.push(TreeEditCommand(self, old_state, f"添加参数 {name}"))

    def add_sub_param(self, item=None, tag_name=None):
        """添加预制子参数"""
        item = self.tree.currentItem() if item is None else item
        full_path = self.get_path_by_item(item)
        if item and self.config.params_type.get(full_path) == "subgroup":
            # 保存当前状态用于撤销
            old_state = self.capture_tree_data()
            parent_name = item.text(0)
            sub_params_dict = {parent_name: self.config.subchildren_default[full_path]} \
                if self.config.params_type[full_path] == "subgroup" else {}

            sub_params = sub_params_dict.get(parent_name, {})
            sub_param_item = ConfigurableTreeWidgetItem(f"{parent_name} {item.childCount() + 1}", "", editor=self)
            self.mark_item_locked(sub_param_item)  # 为预制参数容器锁定
            item.addChild(sub_param_item)

            for sub_param, value in sub_params.items():
                sub_param_path = f"{full_path}/{sub_param}"
                param_type = self.config.params_type.get(sub_param_path)
                required = self.config.require_flag.get(sub_param_path)
                if param_type == "fetch" and tag_name is not None:
                    value = tag_name
                sub_item = ConfigurableTreeWidgetItem(
                    sub_param,
                    value,
                    sub_param_path,
                    control_type=param_type,
                    editor=self,
                    required=required
                )

                sub_param_item.addChild(sub_item)
                sub_item.set_item_widget()
                self.lock_item(sub_param, sub_item, sub_item)

            # 记录撤销操作
            self.undo_stack.push(TreeEditCommand(self, old_state, f"添加子参数到 {parent_name}"))

    def remove_param(self):
        item = self.tree.currentItem()
        if item:
            # 保存当前状态用于撤销
            old_state = self.capture_tree_data()
            param_name = item.text(0)

            parent = item.parent()
            if parent:
                parent.removeChild(item)
            else:
                index = self.tree.indexOfTopLevelItem(item)
                self.tree.takeTopLevelItem(index)

            # 记录撤销操作
            self.undo_stack.push(TreeEditCommand(self, old_state, f"删除参数 {param_name}"))
            self.show_status_message("已删除配置", "success")

    def run_param(self):
        item = self.tree.currentItem()
        full_path = self.get_path_by_item(item)
        param_no = self.config.get_model_binding_node_no(full_path)
        flow_nam, flow_no, flow_json, flow_pic = self.config.api_tools.get("di_flow").call(
            flow_nam=self.model_bindings.get(self.current_file),
            with_flow_no=True,
            with_flow_json=True,
            with_flow_pic=True
        )[0]
        self.config.api_tools.get("model_execute").call(
            flow_no,
            flow_json,
            flow_pic,
            param_no
        )
        self.create_successbar("开始运行模型！")

    def load_history_menu(self):
        if not os.path.exists(HISTORY_PATH):
            return

        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            history = json.load(f)

        file_map = {}
        for record in history:
            file, timestamp, config = record
            if file not in file_map:
                file_map[file] = []
            file_map[file].append((timestamp, config))

        filenames = list(file_map.keys())

        for versions in file_map.values():
            versions.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S"), reverse=True)

        # 新的加载对话框
        load_history_dialog = LoadHistoryDialog(file_map, filenames, self)

        if load_history_dialog.exec_() == QDialog.Accepted:
            selected_file = load_history_dialog.selected_file
            selected_version = load_history_dialog.selected_version
            selected_config = load_history_dialog.selected_config

            current_config = self.get_current_config()

            if load_history_dialog.action == "load":
                # 新增逻辑：作为新配置打开
                history_filename = f"[历史]{os.path.basename(selected_file)}-{selected_version}"
                history_filename = self.add_tab(history_filename)
                self.open_files[history_filename] = selected_config
                self.tab_bar.setCurrentIndex(self.tab_bar.count() - 1)
                self.switch_to_file(history_filename)

            elif load_history_dialog.action == "compare":
                # 对比功能保持不变
                compare_dialog = VersionDiffDialog(
                    selected_config, current_config,
                    lambda config: self.reload_tree(config),
                    selected_file, selected_version
                )
                self.home.addSubInterface(compare_dialog, FIF.HISTORY, '历史对比', parent=self)
                self.home.switchTo(compare_dialog)
                if compare_dialog.exec_() == QDialog.Accepted:
                    self.home.removeInterface(compare_dialog)
                    self.home.switchTo(self)

    def get_current_config(self):
        def extract_item(item):
            data = {}
            for i in range(item.childCount()):
                child = item.child(i)
                key = child.text(0)
                value = child.text(1)
                if child.childCount() > 0:
                    data[key] = extract_item(child)
                else:
                    data[key] = value
            return data

        config = {}
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            key = top_item.text(0)
            value = top_item.text(1)
            if top_item.childCount() > 0:
                config[key] = extract_item(top_item)
            else:
                config[key] = value
        return config

    def tree_to_dict(self, item=None):
        def parse_item(itm):
            children = [parse_item(itm.child(i)) for i in range(itm.childCount())]
            key = itm.text(0)
            val = itm.text(1)
            full_path = self.get_path_by_item(itm)
            param_type = self.config.params_type.get(full_path)

            if children:
                if all(c[0] == "" for c in children):
                    return key, [c[1] for c in children]
                else:
                    child_dict = {}
                    key_counts = {}
                    for k, v in children:
                        if k in child_dict:
                            key_counts[k] = key_counts.get(k, 1) + 1
                            new_key = f"{k}_{key_counts[k]}"
                        else:
                            key_counts[k] = 1
                            new_key = k
                        child_dict[new_key] = v
                    return key, child_dict
            else:
                if param_type == "range":
                    return RangeInputDialog.save(key, val)
                elif param_type == "partition":
                    return RangeListDialog.save(key, val)
                elif param_type == "time_range_select":
                    return TimeRangeDialog.save(key, val)

                return key, val

        result = {}
        key_counts = {}
        for i in range(self.tree.topLevelItemCount()):
            key, val = parse_item(self.tree.topLevelItem(i))
            if key in result:
                key_counts[key] = key_counts.get(key, 1) + 1
                new_key = f"{key}_{key_counts[key]}"
            else:
                key_counts[key] = 1
                new_key = key
            result[new_key] = val
        return result

    def mark_item_locked(self, item, type=None):
        """标记项目为锁定状态，更显眼的视觉提示"""
        # 仅禁用编辑，但保留可选中以显示高亮
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)

        # 参数组标题使用蓝灰色背景
        if type == "subgroup":
            item.setForeground(0, QColor("#444444"))
            item.setForeground(1, QColor("#444444"))
            item.setBackground(0, QColor("#e6f7ff"))
            item.setBackground(1, QColor("#e6f7ff"))
        elif type == "group":
            item.setForeground(0, QColor("#444444"))
            item.setForeground(1, QColor("#444444"))
            item.setBackground(0, QColor("#fafafa"))
            item.setBackground(1, QColor("#fafafa"))
        # 设置字体加粗
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)

        # 标记为锁定
        item.setData(0, Qt.UserRole, True)

    def on_search(self):
        text = self.search_line.text()
        # 先展开所有节点
        self.expand_all_items(self.tree.invisibleRootItem())

        # 如果搜索框为空，就直接显示所有节点
        if text is None or not text.strip():
            self.show_all_items(self.tree.invisibleRootItem())
            return

        # 否则按逗号分隔成多个关键字
        text = text.replace("；", ";").replace(",", ";").replace("，", ";").replace(" ", ";").replace("　", ";")
        filters = [
            kw.strip().lower() for kw in text.split(';') if kw.strip()
        ]

        # 递归更新可见性
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self.update_item_visibility(item, filters)

    def show_all_items(self, parent_item):
        """递归把所有项都设为可见"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setHidden(False)
            self.show_all_items(child)

    def update_item_visibility(self, item, filters):
        """更新单项可见性（任意关键字命中或有子项命中就显示）"""
        match_in_children = False
        for i in range(item.childCount()):
            child = item.child(i)
            if self.update_item_visibility(child, filters):
                match_in_children = True

        match_in_self = self.search_item_in_all_columns(item, filters)
        item.setHidden(not (match_in_self or match_in_children))
        return match_in_self or match_in_children

    def search_item_in_all_columns(self, item, filters):
        """任意关键字在任一列出现就算命中，如果 filters 为空总是返回 True
        如果匹配，增加高亮显示"""
        if not filters:
            # 清除所有高亮
            for col in range(item.columnCount()):
                item.setBackground(col, QColor('transparent'))
            return True

        match = False
        match_in_columns = set()

        for col in range(item.columnCount()):
            txt = item.text(col).lower()
            for kw in filters:
                if kw in txt:
                    match = True
                    match_in_columns.add(col)

        return match

    def expand_all_items(self, parent_item):
        """递归展开所有项"""
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            child_item.setExpanded(True)  # 展开当前项
            self.expand_all_items(child_item)  # 递归展开子项

    def toggle_viewer(self):
        self.log_anim.stop()

        if not self.log_expanded:
            # 向上展开：从 0 到目标高度
            self.log_container.setFixedHeight(0)  # 重置固定高度
            self.log_container.show()

            # 动画：控制 maximumHeight 和 pos
            self.log_anim = QPropertyAnimation(self.log_container, b"maximumHeight")
            self.log_anim.setDuration(250)
            self.log_anim.setStartValue(0)
            self.log_anim.setEndValue(int(0.4 * self.window_height))
            self.log_anim.setEasingCurve(QEasingCurve.OutCubic)

            # 同时调整位置（可选）
            self.pos_anim = QPropertyAnimation(self.log_container, b"pos")
            self.pos_anim.setDuration(250)
            self.pos_anim.setStartValue(self.log_container.pos())
            self.pos_anim.setEndValue(self.log_container.pos() - QPoint(0, int(0.4 * self.window_height)))
            self.pos_anim.setEasingCurve(QEasingCurve.OutCubic)

            # 启动动画
            self.log_anim.start()
            self.pos_anim.start()
            self.log_expanded = True
        else:
            # 向上收缩：从当前高度到 0
            self.log_anim = QPropertyAnimation(self.log_container, b"maximumHeight")
            self.log_anim.setDuration(250)
            self.log_anim.setStartValue(self.log_container.height())
            self.log_anim.setEndValue(0)
            self.log_anim.setEasingCurve(QEasingCurve.InCubic)

            # 同时调整位置（可选）
            self.pos_anim = QPropertyAnimation(self.log_container, b"pos")
            self.pos_anim.setDuration(250)
            self.pos_anim.setStartValue(self.log_container.pos())
            self.pos_anim.setEndValue(self.log_container.pos() + QPoint(0, self.log_container.height()))
            self.pos_anim.setEasingCurve(QEasingCurve.InCubic)

            # 动画结束后隐藏控件
            def on_finished():
                self.log_container.hide()
                self.log_container.setFixedHeight(0)  # 重置固定高度
                self.log_anim.finished.disconnect(on_finished)
                self.log_expanded = False

            self.log_anim.finished.connect(on_finished)
            self.log_anim.start()
            self.pos_anim.start()

    def handle_upload_model(self):
        dialog = UploadModelMessageBox(self)
        if dialog.exec():
            file_path, selected_env = dialog.get_text()
            if file_path:
                # 此处调用上传接口并附带运行环境信息，如有需要
                worker = Worker(
                    self.config.api_tools.get("model_upload"),
                    file_path, selected_env
                )
                self.thread_pool.start(worker)

    def handle_copy_model(self):
        model_names = self.config.api_tools.get("di_flow").call(with_flow_no=True)

        dialog = CopyModelMessageBox(model_names, self)

        if dialog.exec():
            selected_model, new_model_name = dialog.get_text()
            self.config.api_tools.get("model_duplicate").call(model_names[selected_model][1], new_model_name)

    def _goto_structure_settings(self, item_name=None):
        self.home.switchTo(self.home.config_setting)
        self.home.config_setting.switch_to("param-structure", item_name)

    def _goto_api_settings(self):
        self.home.switchTo(self.home.config_setting)
        self.home.config_setting.switch_to("api-tools")

    def add_tab(self, filename):
        """
        新建一个 QFrame 作为“标签页”外壳（container）：
          • 固定高度 40px
          • 根据文件名动态算最小宽度，保证文字不截断
          • 点击 container 任意位置都能切换到该 tab
          • 选中时样式：白底+3px蓝色下边框
          • 未选中时样式：灰底+3px透明下边框
          • 内部布局： [ tab_btn(文字) + stretch + close_btn ]
        """
        # 获取不重复的文件名
        filename = self.ensure_new_name(filename)
        self.tab_bar.addTab(
            routeKey=filename,
            text=filename,
            onClick=lambda: (
                self.switch_to_file(filename)
            )
        )

        return filename

    def ensure_new_name(self, new, ori_btn=None):
        """双击重命名出现相同名称时，自动增加后缀，直到名称唯一"""
        original_name = new
        existing_names = self.tab_bar.itemMap.keys()

        # 如果名称唯一，直接返回
        if new not in existing_names:
            return new

        # 否则不断尝试增加后缀
        count = 1
        while True:
            new = f"{original_name}_{count}"
            if new not in existing_names:
                return new
            count += 1

    def _on_close(self, index: int):
        name = self.tab_bar.tabText(index)
        if hasattr(self, "is_same_as_file") and self.is_same_as_file(
                name
        ):
            self.tab_bar.removeTab(index)
            self.close_file(name)
        else:

            box = MessageBox(f"关闭文件 - {name}", f"文件 '{name}' 已修改, 是否保存更改并关闭文件？", self)
            if box.exec():
                self.switch_to_file(name)
                self.auto_save()

            self.tab_bar.removeTab(index)
            self.close_file(name)

        self.current_file = None
        # 如果没有标签自动创建新标签
        if self.tab_bar.count() == 0:
            self.new_config()
        else:
            self.switch_to_file(self.tab_bar.tabText(self.tab_bar._currentIndex))

    # 消息框
    def create_infobar(self, title: str, content: str = "", duration: int = 5000):
        if hasattr(self, "infobar"):
            try:
                self.infobar.close()
            except Exception:
                pass
            del self.infobar

        self.infobar = InfoBar(
            icon=InfoBarIcon.INFORMATION,
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=duration,  # won't disappear automatically
            parent=self
        )
        self.infobar.show()

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

    def create_errorbar(self, title: str, content: str = "", duration: int = 5000, show_button: bool = False,
                        button_fn=None):
        bar = InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=duration,  # won't disappear automatically
            parent=self
        )
        if show_button:
            jump_button = PushButton("前往配置")
            bar.addWidget(jump_button)
            jump_button.clicked.connect(button_fn)

        bar.show()

    def _open_platform(self):
        QDesktopServices.openUrl(
            QUrl(f"http://{self.config.global_host}:{self.config.platform_port}")
        )