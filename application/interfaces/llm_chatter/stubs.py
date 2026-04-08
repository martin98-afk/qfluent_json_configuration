# -*- coding: utf-8 -*-
"""
Stub implementations for llm_chatter module dependencies
that don't exist in the current project structure.
"""

from PyQt5.QtWidgets import QWidget
from enum import Enum


class DockPosition(Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    CENTER = "center"


class ToolWindow(QWidget):
    """
    Stub ToolWindow class to adapt llm_chatter to work without
    the original side_dock_area plugin infrastructure.
    """

    name = "LLM Chat"
    icon = None
    singleton = True
    default_position = DockPosition.BOTTOM
    display_order = 0

    def __init__(self, homepage=None, button=None):
        super().__init__(homepage)
        self.homepage = homepage
        self.button = button

    def showEvent(self, event):
        super().showEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)


class CustomVariable:
    """Stub for CustomVariable from app.components.base"""

    def __init__(self, value=None):
        self.value = value


from PyQt5.QtWidgets import QComboBox


class SearchableEditableComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditable(True)

    def setText(self, text):
        if text not in [self.itemText(i) for i in range(self.count())]:
            self.addItem(text)
        self.setCurrentText(text)


class WebhookManagerStub:
    """Stub for WebhookManager from app.plugins.trigger_plugins.webhook_trigger"""

    def __init__(self):
        pass

    def get_webhook_url(self, endpoint):
        return None

    def trigger(self, endpoint, data=None, callback_url=None, timeout=300):
        return {"success": False, "error": "WebhookManager not available"}


class WebhookManager:
    """Alias for the stub"""

    pass


class Settings:
    """
    Compatibility wrapper that maps llm_chatter's Settings API
    to the current project's UnifiedConfig singleton.
    Provides attribute-style access to config items.
    """

    _instance = None

    def __init__(self):
        from application.utils.app_config import UnifiedConfig

        self._config = UnifiedConfig.get_instance()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Settings()
        return cls._instance

    def __getattr__(self, name):
        """Delegate attribute access to the underlying config."""
        if name.startswith("_"):
            return super().__getattribute__(name)
        return getattr(self._config, name)

    def set(self, config_item, value, save=False):
        """Set a config item value."""
        from qfluentwidgets import qconfig

        qconfig.set(config_item, value)
        if save:
            self.save_config()

    def save_config(self):
        """Save config using qconfig's mechanism"""
        from qfluentwidgets import qconfig

        try:
            qconfig.save()
        except Exception as e:
            from loguru import logger

            logger.warning(f"qconfig.save failed: {e}")
            try:
                self._config.save_config()
            except Exception:
                pass

    @property
    def llm_model(self):
        return self._config.llm_model

    @property
    def llm_api_key(self):
        return self._config.llm_api_key

    @property
    def llm_api_base(self):
        return self._config.llm_api_base

    @property
    def llm_max_tokens(self):
        return self._config.llm_max_tokens

    @property
    def llm_temperature(self):
        return self._config.llm_temperature

    @property
    def llm_enable_thinking(self):
        return self._config.llm_enable_thinking

    @property
    def llm_selected_model(self):
        return self._config.llm_selected_model

    @property
    def llm_saved_providers(self):
        return self._config.llm_saved_providers

    @property
    def canvas_font_selected(self):
        return self._config.canvas_font_selected

    @property
    def SERPAPI_KEY(self):
        return self._config.SERPAPI_KEY
