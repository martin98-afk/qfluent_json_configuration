"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: fluent_json_editor.py
@time: 2025/7/16 17:05
@desc: 
"""
import json
import os
from datetime import datetime

from PyQt5.QtCore import QSize, QMetaObject, Qt, Q_ARG
from PyQt5.QtGui import QIcon, QFont, QGuiApplication
from PyQt5.QtWidgets import QApplication, QDesktopWidget, QDialog, QMessageBox, QPlainTextEdit
from loguru import logger
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import NavigationItemPosition, FluentWindow, SplashScreen

from application.dialogs.config_setting_dialog import ConfigSettingDialog
from application.dialogs.load_history_dialog import LoadHistoryDialog
from application.dialogs.logger_dialog import QTextEditLogger
from application.dialogs.nacos_service_manage import ServiceConfigManager
from application.dialogs.service_test_dialog import JSONServiceTester
from application.dialogs.trend_analysis_dialog import TrendAnalysisDialog
from application.dialogs.update_checker import UpdateChecker
from application.dialogs.version_diff_dialog import VersionDiffDialog
from application.json_editor import JSONEditor
from application.utils.config_handler import (
    HISTORY_PATH,
)
from application.utils.utils import get_icon, error_catcher_decorator


class FluentJSONEditor(FluentWindow):
    def __init__(self):
        super().__init__()
        screen_rect = QDesktopWidget().screenGeometry()
        screen_width, screen_height = screen_rect.width(), screen_rect.height()
        self.window_width = int(screen_width * 0.6)
        self.window_height = int(screen_height * 0.75)
        self.resize(self.window_width, self.window_height)
        screen = QGuiApplication.primaryScreen()
        self.scale = int(screen.logicalDotsPerInch() / 96.0)  # 96 DPI 为基准
        self.font_size = round(10 * self.scale)
        self.setup_log_viwer()
        # create sub interface
        self.editor = JSONEditor(home=self)
        self.navigationInterface.setAcrylicEnabled(True)
        # 1. 创建启动页面
        self.setWindowIcon(get_icon("logo"))
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(130, 130))
        # 2. 在创建其他子页面前先显示主界面
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)
        self.show()
        # 3. 初始化界面
        self._init_menu()
        self._initNavigation()
        self.initWindow()
        # 4. 隐藏启动页面
        self.splashScreen.finish()


    def _init_menu(self):
        self.trend_analysis_dialog = TrendAnalysisDialog(
            parent=self.editor,
            home=self
        )
        self.service_config_manager = ServiceConfigManager(
            parent=self.editor
        )
        self.service_test = JSONServiceTester("", self.editor, self)
        self.config_setting = ConfigSettingDialog(self.editor)

    @error_catcher_decorator
    def _initNavigation(self):
        self.navigationInterface.setExpandWidth(200)
        # 上半部分按钮
        self.addSubInterface(self.editor, FIF.HOME, '配置界面')
        trend_interface = self.addSubInterface(self.trend_analysis_dialog, get_icon("趋势分析"), '趋势分析')
        trend_interface.clicked.connect(self.trend_analysis_dialog._load_points)
        service_interface = self.addSubInterface(self.service_test, get_icon("服务接口配置"), '服务测试')
        service_interface.clicked.connect(self.service_test.load_services)
        nacos_interface = self.addSubInterface(self.service_config_manager, get_icon("nacos"), 'Nacos下控服务配置')
        nacos_interface.clicked.connect(self.service_config_manager.get_service_list)
        self.updater = UpdateChecker(self.editor, self)
        self.updater.check_update()
        self.window_title = f"{self.editor.config.title} - V{self.updater.current_version}"
        # 下半部分按钮
        self.addSubInterface(self.log_viewer, get_icon("系统运行日志"), '执行日志', NavigationItemPosition.BOTTOM)
        self.navigationInterface.addItem(
            routeKey='update',
            icon=FIF.SYNC,
            text='检查更新',
            onClick=self.updater.check_update,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )
        self.config_setting_interface = (
            self.addSubInterface(
                self.config_setting, FIF.SETTING, '设置', NavigationItemPosition.BOTTOM)
        )
        self.navigationInterface.addItem(
            routeKey='about',
            icon=FIF.INFO,
            text='关于',
            onClick=self.show_about_dialog,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        self.navigationInterface.setCurrentItem(self.editor.objectName())

    def initWindow(self):
        self.setWindowTitle(self.window_title)
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def show_history_menu(self):
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
                history_filename = self.tab_bar.add_tab(history_filename)
                self.open_files[history_filename] = selected_config
                self.switch_to_file(history_filename)

            elif load_history_dialog.action == "compare":
                # 对比功能保持不变
                compare_dialog = VersionDiffDialog(
                    selected_config, current_config,
                    lambda config: self.reload_tree(config),
                    selected_file, selected_version
                )
                compare_dialog.exec_()

    def show_about_dialog(self):
        QMessageBox.about(self, "关于",
                          f"配置编辑器 v{self.updater.current_version}\n"
                          "© 2025 Luculent\n"
                          "用于多配置文件编辑与管理")

    def setup_log_viwer(self):
        if not hasattr(self, 'log_viewer'):
            self.log_viewer = QPlainTextEdit()
            self.log_viewer.setObjectName('运行日志')
            self.log_viewer.setReadOnly(True)
            self.log_viewer.setFont(QFont("Consolas", 11))
            self.log_viewer.setStyleSheet(f"""
                QPlainTextEdit {{
                    background-color: #0e1117;
                    color: white;
                    border: 1px solid #2c2f36;
                    font-family: Consolas, monospace;
                    font-size: {2 * self.font_size}px;
                    padding: 10px;
                }}
                /* 纵向滚动条 */
                QTextEdit QScrollBar:vertical {{
                    background: transparent;
                    width: 8px;
                    margin: 0px;
                }}
                QTextEdit QScrollBar::handle:vertical {{
                    background: #555555;
                    border-radius: 4px;
                    min-height: 20px;
                }}
                QTextEdit QScrollBar::handle:vertical:hover {{
                    background: #888888;
                }}
                QTextEdit QScrollBar::add-line:vertical,
                QTextEdit QScrollBar::sub-line:vertical {{
                    height: 0px;
                    background: none;
                    border: none;
                }}
                QTextEdit QScrollBar::add-page:vertical, QTextEdit QScrollBar::sub-page:vertical {{
                    background: none;
                }}

                /* 横向滚动条 */
                QTextEdit QScrollBar:horizontal {{
                    background: transparent;
                    height: 8px;
                    margin: 0px;
                }}
                QTextEdit QScrollBar::handle:horizontal {{
                    background: #555555;
                    border-radius: 4px;
                    min-width: 20px;
                }}
                QTextEdit QScrollBar::handle:horizontal:hover {{
                    background: #888888;
                }}
                QTextEdit QScrollBar::add-line:horizontal,
                QTextEdit QScrollBar::sub-line:horizontal {{
                    width: 0px;
                    background: none;
                    border: none;
                }}
                QTextEdit QScrollBar::add-page:horizontal, QTextEdit QScrollBar::sub-page:horizontal {{
                    background: none;
                }}
            """)

            def safe_scroll_to_bottom(min_val, max_val):
                """安全滚动到底部，防止对象销毁后访问"""
                # 1. 检查对象是否仍然有效
                if not hasattr(self, 'log_viewer') or self.log_viewer is None:
                    return

                try:
                    # 2. 检查滚动条是否有效 (关键!)
                    scrollbar = self.log_viewer.verticalScrollBar()
                    if not scrollbar or scrollbar.parent() is None:
                        return

                    # 3. 通过队列确保在对象有效时执行
                    QMetaObject.invokeMethod(
                        scrollbar,
                        "setValue",
                        Qt.QueuedConnection,
                        Q_ARG(int, max_val)
                    )
                except RuntimeError as e:
                    # 捕获"underlying C/C++ object has been deleted"
                    if "deleted" in str(e).lower():
                        logger.debug("Ignored scroll on destroyed log viewer")
                    else:
                        logger.error(f"Scroll error: {str(e)}")

            # 启用垂直滚动条自动到底部
            self.log_viewer.verticalScrollBar().rangeChanged.connect(safe_scroll_to_bottom)
            # 创建 sink
            self.text_logger = QTextEditLogger(self.log_viewer, max_lines=1000)
            logger.remove()
            logger.add(self.text_logger, format="{time:HH:mm:ss} | {level} | {file}:{line} {message}", level="DEBUG")
