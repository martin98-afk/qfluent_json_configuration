# -*- coding: utf-8 -*-
"""
LLM Chat Interface wrapper for FluentWindow integration
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel


class LLMAgentInterface(QWidget):
    """
    Wrapper interface that embeds the OpenAIChatToolWindow
    into the FluentWindow navigation system.
    Uses lazy import to avoid crashes during module load.
    """

    def __init__(self, parent=None, homepage=None):
        super().__init__(parent)
        self.setObjectName("OpenAIChatToolWindow")
        self.homepage = homepage
        self._chat_window = None
        self._ui_initialized = False
        self._basic_layout = QVBoxLayout(self)
        self._basic_layout.setContentsMargins(0, 0, 0, 0)
        self._basic_layout.setSpacing(0)

    def _get_chat_window_class(self):
        """Lazy import to avoid startup crash"""
        from application.interfaces.llm_chatter.main_widget import OpenAIChatToolWindow

        return OpenAIChatToolWindow

    def showEvent(self, event):
        """Setup UI when first shown"""
        if not self._ui_initialized:
            self._do_setup_ui()
        super().showEvent(event)

    def _do_setup_ui(self):
        """Actually setup the UI"""
        if self._ui_initialized:
            return

        if self.homepage:
            try:
                chat_class = self._get_chat_window_class()
                self._chat_window = chat_class(homepage=self.homepage, button=None)
                self._chat_window.setup_ui()
                self._basic_layout.addWidget(self._chat_window)
                self._ui_initialized = True
            except Exception as e:
                from loguru import logger

                logger.error(f"Failed to initialize LLM chat: {e}")
                import traceback

                logger.error(traceback.format_exc())
                label = QLabel(f"LLM Chat 初始化失败: {e}", self)
                label.setAlignment(Qt.AlignCenter)
                self._basic_layout.addWidget(label)
                self._ui_initialized = True
        else:
            label = QLabel("LLM Chat 初始化失败: 缺少 homepage 引用", self)
            label.setAlignment(Qt.AlignCenter)
            self._basic_layout.addWidget(label)
            self._ui_initialized = True

    def setup_ui(self):
        """Manual setup - safe to call multiple times"""
        if not self._ui_initialized:
            self._do_setup_ui()

    def get_chat_window(self):
        return self._chat_window
