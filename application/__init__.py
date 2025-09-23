import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QFont, QPalette
from PyQt5.QtWidgets import QApplication

from application.fluent_json_editor import FluentJSONEditor
from application.utils.config_handler import load_config, save_history, save_config, HISTORY_PATH
from application.utils.utils import seed_everything


def enable_dpi_scale():
    # enable dpi scale
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)


def run_app():
    seed_everything()
    # os.environ["OMP_NUM_THREADS"] = "3"
    enable_dpi_scale()

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)
    QApplication.setDoubleClickInterval(600)  # 全局设置为 300 毫秒
    font = QFont("微软雅黑", 10)
    app.setFont(font)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f4f6f9"))
    app.setPalette(palette)
    editor = FluentJSONEditor()
    editor.show()
    sys.exit(app.exec_())
