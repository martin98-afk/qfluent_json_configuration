"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: app_config.py
@time: 2025/9/24 09:51
@desc: 
"""
from pathlib import Path

from qfluentwidgets import ConfigItem, RangeConfigItem, OptionsConfigItem, RangeValidator, OptionsValidator, QConfig
from qfluentwidgets import qconfig
from PyQt5.QtCore import QSettings


class UnifiedConfig(QConfig):
    """统一配置管理器（基础配置 + 版本控制）"""
    _instance = None

    settings = QSettings("config/app_config.ini", QSettings.IniFormat)

    # 基础服务配置
    global_host = ConfigItem(
        "Service", "host", "localhost",
        serializer=settings
    )
    platform_port = RangeConfigItem(
        "Service", "port", 8080, RangeValidator(1, 65535),
        serializer=settings
    )
    api_key = ConfigItem(
        "Service", "api_key", "",
        serializer=settings
    )

    # Nacos 配置
    nacos_host = ConfigItem(
        "Nacos", "host", "localhost",
        serializer=settings
    )
    nacos_port = RangeConfigItem(
        "Nacos", "port", 8848, RangeValidator(1, 65535),
        serializer=settings
    )
    nacos_username = ConfigItem(
        "Nacos", "username", "nacos",
        serializer=settings
    )
    nacos_password = ConfigItem(
        "Nacos", "password", "nacos",
        serializer=settings
    )
    nacos_namespace = ConfigItem(
        "Nacos", "namespace", "sushine",
        serializer=settings
    )

    # 数据库配置
    db_host = ConfigItem(
        "Database", "host", "localhost",
        serializer=settings
    )
    db_port = RangeConfigItem(
        "Database", "port", 5432, RangeValidator(1, 65535),
        serializer=settings
    )
    db_username = ConfigItem(
        "Database", "username", "postgres",
        serializer=settings
    )
    db_password = ConfigItem(
        "Database", "password", "postgres",
        serializer=settings
    )

    # 版本控制配置
    UPDATE_SOURCES = ["github", "gitcode", "gitea"]
    update_source = OptionsConfigItem(
        "Update", "source", "github",
        validator=OptionsValidator(UPDATE_SOURCES), serializer=settings
    )

    project_path = ConfigItem(
        "Update", "project_path", "",
        serializer=settings
    )

    auth_token = ConfigItem(
        "Update", "auth_token", "",
        serializer=settings
    )

    UPDATE_STRATEGIES = ["auto", "manual", "silent"]
    update_strategy = OptionsConfigItem(
        "Update", "strategy", "manual",
        validator=OptionsValidator(UPDATE_STRATEGIES), serializer=settings
    )


    def get_service_config(self):
        """获取服务配置"""
        return {
            "host": qconfig.get(self.global_host),
            "port": qconfig.get(self.platform_port),
            "api_key": qconfig.get(self.api_key)
        }

    def get_nacos_config(self):
        """获取 Nacos 配置"""
        return {
            "host": f"http://{qconfig.get(self.nacos_host)}:{qconfig.get(self.nacos_port)}",
            "username": qconfig.get(self.nacos_username),
            "password": qconfig.get(self.nacos_password),
            "namespace": qconfig.get(self.nacos_namespace)
        }

    def get_db_config(self):
        """获取数据库配置"""
        return {
            "host": qconfig.get(self.db_host),
            "port": qconfig.get(self.db_port),
            "username": qconfig.get(self.db_username),
            "password": qconfig.get(self.db_password)
        }

    def get_update_config(self):
        """获取更新配置"""
        return {
            "source": qconfig.get(self.update_source),
            "project_path": qconfig.get(self.project_path),
            "auth_token": qconfig.get(self.auth_token),
            "strategy": qconfig.get(self.update_strategy)
        }

    def set_update_config(self, config):
        """设置更新配置"""
        if "source" in config:
            qconfig.set(self.update_source, config["source"])
        if "project_path" in config:
            qconfig.set(self.project_path, config["project_path"])
        if "auth_token" in config:
            qconfig.set(self.auth_token, config["auth_token"])
        if "strategy" in config:
            qconfig.set(self.update_strategy, config["strategy"])

    # ========== 单例 + 持久化 ==========
    @classmethod
    def get_instance(cls):
        """获取配置实例（单例模式）"""
        if cls._instance is None:
            cls._instance = cls()
            CONFIG_FILE = str(Path.cwd() / "app.config")
            try:
                cls._instance.load(CONFIG_FILE)
            except Exception as e:
                # 首次运行或加载失败，保存默认配置
                cls._instance.save(CONFIG_FILE)
                print(f"✅ 已创建默认配置文件: {CONFIG_FILE}")
        return cls._instance

    @classmethod
    def save_config(cls):
        """保存配置到文件"""
        if cls._instance:
            CONFIG_FILE = str(Path.cwd() / "app.config")
            cls._instance.save(CONFIG_FILE)
            print(f"💾 配置已保存至: {CONFIG_FILE}")