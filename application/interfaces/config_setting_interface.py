"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: config_setting_interface.py
@time: 2025/9/24 09:58
@desc: 
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel
from qfluentwidgets import (
    ScrollArea, ExpandGroupSettingCard,
    LineEdit, ComboBox, FluentIcon as FIF  # 添加图标导入
)

from application.utils.app_config import UnifiedConfig


class ConfigSettingsInterface(ScrollArea):
    """配置设置界面"""

    def __init__(self):
        super().__init__()
        self.setObjectName("configSettingsInterface")
        self.config = UnifiedConfig.get_instance()
        # 创建主布局
        self.view = QWidget()
        self.vBoxLayout = QVBoxLayout(self.view)

        # 创建配置卡片
        self.service_card = self.create_service_config_card()
        self.nacos_card = self.create_nacos_config_card()
        self.db_card = self.create_db_config_card()
        self.update_card = self.create_update_config_card()

        self.vBoxLayout.addWidget(self.service_card)
        self.vBoxLayout.addWidget(self.nacos_card)
        self.vBoxLayout.addWidget(self.db_card)
        self.vBoxLayout.addWidget(self.update_card)
        self.vBoxLayout.addStretch(1)

        self.setWidget(self.view)
        self.setWidgetResizable(True)

    def create_service_config_card(self):
        """创建服务配置卡片"""
        card = ExpandGroupSettingCard(
            FIF.GLOBE,  # 添加图标参数
            title="服务配置",
            content="配置平台服务连接信息"
        )

        # Host
        self.host_edit = LineEdit()
        self.host_edit.setText(self.config.global_host.value)
        self.host_edit.textChanged.connect(
            lambda text: setattr(self.config.global_host, 'value', text)
        )

        # Port
        self.port_edit = LineEdit()
        self.port_edit.setText(str(self.config.platform_port.value))
        self.port_edit.textChanged.connect(
            lambda text: setattr(self.config.platform_port, 'value',
                               int(text) if text.isdigit() else 8080)
        )

        # API Key
        self.api_key_edit = LineEdit()
        self.api_key_edit.setText(self.config.api_key.value)
        self.api_key_edit.textChanged.connect(
            lambda text: setattr(self.config.api_key, 'value', text)
        )

        # 添加到卡片 - 使用 addGroupWidget
        card.addGroupWidget(QLabel("服务地址"))
        card.addGroupWidget(self.host_edit)
        card.addGroupWidget(QLabel("端口"))
        card.addGroupWidget(self.port_edit)
        card.addGroupWidget(QLabel("API密钥"))
        card.addGroupWidget(self.api_key_edit)

        return card

    def create_nacos_config_card(self):
        """创建 Nacos 配置卡片"""
        card = ExpandGroupSettingCard(
            FIF.SETTING,  # 添加图标参数
            title="Nacos 配置",
            content="配置 Nacos 服务连接信息"
        )

        self.nacos_host_edit = LineEdit()
        self.nacos_host_edit.setText(self.config.nacos_host.value)
        self.nacos_host_edit.textChanged.connect(
            lambda text: setattr(self.config.nacos_host, 'value', text)
        )

        self.nacos_port_edit = LineEdit()
        self.nacos_port_edit.setText(str(self.config.nacos_port.value))
        self.nacos_port_edit.textChanged.connect(
            lambda text: setattr(self.config.nacos_port, 'value',
                               int(text) if text.isdigit() else 8848)
        )

        self.nacos_username_edit = LineEdit()
        self.nacos_username_edit.setText(self.config.nacos_username.value)
        self.nacos_username_edit.textChanged.connect(
            lambda text: setattr(self.config.nacos_username, 'value', text)
        )

        self.nacos_password_edit = LineEdit()
        self.nacos_password_edit.setEchoMode(QLineEdit.Password)
        self.nacos_password_edit.setText(self.config.nacos_password.value)
        self.nacos_password_edit.textChanged.connect(
            lambda text: setattr(self.config.nacos_password, 'value', text)
        )

        # 添加到卡片
        card.addGroupWidget(QLabel("Host"))
        card.addGroupWidget(self.nacos_host_edit)
        card.addGroupWidget(QLabel("Port"))
        card.addGroupWidget(self.nacos_port_edit)
        card.addGroupWidget(QLabel("用户名"))
        card.addGroupWidget(self.nacos_username_edit)
        card.addGroupWidget(QLabel("密码"))
        card.addGroupWidget(self.nacos_password_edit)

        return card

    def create_db_config_card(self):
        """创建数据库配置卡片"""
        card = ExpandGroupSettingCard(
            FIF.TAG,  # 添加图标参数
            title="数据库配置",
            content="配置数据库连接信息"
        )

        self.db_host_edit = LineEdit()
        self.db_host_edit.setText(self.config.db_host.value)
        self.db_host_edit.textChanged.connect(
            lambda text: setattr(self.config.db_host, 'value', text)
        )

        self.db_port_edit = LineEdit()
        self.db_port_edit.setText(str(self.config.db_port.value))
        self.db_port_edit.textChanged.connect(
            lambda text: setattr(self.config.db_port, 'value',
                               int(text) if text.isdigit() else 5432)
        )

        self.db_username_edit = LineEdit()
        self.db_username_edit.setText(self.config.db_username.value)
        self.db_username_edit.textChanged.connect(
            lambda text: setattr(self.config.db_username, 'value', text)
        )

        self.db_password_edit = LineEdit()
        self.db_password_edit.setEchoMode(QLineEdit.Password)
        self.db_password_edit.setText(self.config.db_password.value)
        self.db_password_edit.textChanged.connect(
            lambda text: setattr(self.config.db_password, 'value', text)
        )

        # 添加到卡片
        card.addGroupWidget(QLabel("Host"))
        card.addGroupWidget(self.db_host_edit)
        card.addGroupWidget(QLabel("Port"))
        card.addGroupWidget(self.db_port_edit)
        card.addGroupWidget(QLabel("用户名"))
        card.addGroupWidget(self.db_username_edit)
        card.addGroupWidget(QLabel("密码"))
        card.addGroupWidget(self.db_password_edit)

        return card

    def create_update_config_card(self):
        """创建更新配置卡片"""
        card = ExpandGroupSettingCard(
            FIF.SYNC,  # 添加图标参数
            title="更新配置",
            content="配置软件更新策略和源"
        )

        # 更新源
        self.update_source_combo = ComboBox()
        self.update_source_combo.addItems(["github", "gitcode", "gitea"])
        self.update_source_combo.setCurrentText(self.config.update_source.value)
        self.update_source_combo.currentTextChanged.connect(
            lambda text: setattr(self.config.update_source, 'value', text)
        )

        # 项目路径
        self.project_path_edit = LineEdit()
        self.project_path_edit.setText(self.config.project_path.value)
        self.project_path_edit.textChanged.connect(
            lambda text: setattr(self.config.project_path, 'value', text)
        )

        # 鉴权码
        self.auth_token_edit = LineEdit()
        self.auth_token_edit.setEchoMode(QLineEdit.Password)
        self.auth_token_edit.setText(self.config.auth_token.value)
        self.auth_token_edit.textChanged.connect(
            lambda text: setattr(self.config.auth_token, 'value', text)
        )

        # 更新策略
        self.update_strategy_combo = ComboBox()
        self.update_strategy_combo.addItems(["auto", "manual", "silent"])
        self.update_strategy_combo.setCurrentText(self.config.update_strategy.value)
        self.update_strategy_combo.currentTextChanged.connect(
            lambda text: setattr(self.config.update_strategy, 'value', text)
        )

        # 添加到卡片
        card.addGroupWidget(QLabel("更新源"))
        card.addGroupWidget(self.update_source_combo)
        card.addGroupWidget(QLabel("项目路径"))
        card.addGroupWidget(self.project_path_edit)
        card.addGroupWidget(QLabel("鉴权码"))
        card.addGroupWidget(self.auth_token_edit)
        card.addGroupWidget(QLabel("更新策略"))
        card.addGroupWidget(self.update_strategy_combo)

        return card