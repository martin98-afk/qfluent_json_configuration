"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: param_template_manager.py
@time: 2025/9/24 09:52
@desc: 
"""
import os.path
import re
import shutil

from qfluentwidgets import QConfig
from ruamel.yaml import YAML
from pathlib import Path

from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool

from application.tools.api_service.file_uploader import DatasetUploader
from application.tools.api_service.model_duplicate import ModelDuplicate
from application.tools.api_service.model_execute import ModelExecute
from application.tools.api_service.model_logger import ModelLogger
from application.tools.api_service.model_uploader import ModelUploader
from application.tools.api_service.point_search import PointSearcher
from application.tools.api_service.rtsp_search import RTSPSearcher
from application.tools.api_service.service_logger import ServiceLogger
from application.tools.api_service.service_params import ServiceParamsFetcher
from application.tools.api_service.service_reonline import ServiceReonline
from application.tools.api_service.services_search import SeviceListSearcher
from application.tools.api_service.trenddb_fectcher import TrenddbFetcher
from application.tools.database.di_env import DiEnv
from application.tools.database.di_flow import DiFlow
from application.tools.database.di_flow_param_modify import DiFlowParamsModify
from application.tools.database.di_flow_params import DiFlowParams
from application.tools.nacos.get_postgres_config import GetPostgresConfig
from application.tools.nacos.get_service_path import GetNacosServicePath
from application.tools.nacos.write_service_path import WriteNacosServicePath
from application.utils.threading_utils import Worker
from application.utils.utils import resource_path


class ParamConfigLoader(QConfig):
    _instance = None

    param_structure = {}  # 当前参数结构
    init_params = {}  # 参数初始化数据
    params_type = {}  # 参数类型
    require_flag = {}  # 是否为必填参数 （当前未实装，展示效果不好）
    params_default = {}  # 参数默认值
    params_options = {}  # 参数可选值
    params_desc = {}  # 参数填写说明
    subchildren_default = {}  # 子参数默认值
    model_binding_structure = {}  # 参数配置绑定模型结构
    param_templates = {}

    def _read_config(self):
        yaml = YAML()
        config_path = Path(self.param_definitions_path)

        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.load(f)

        return cfg

    # ==============================
    # ✅ 公共接口
    # ==============================
    def load_async(self):
        self._reset_params_config()
        self._reset_tools_config()
        self.load_params_async()
        self.load_tools_async()

    def load_params_async(self):
        """异步加载全部配置"""
        logger.info("Launching asynchronous params load")
        worker = Worker(self.load_params)
        worker.signals.finished.connect(
            lambda _: (
                logger.info("Params async load finished"),
                self.params_loaded.emit(),
            )
        )
        worker.signals.error.connect(
            lambda err: logger.error("Async params load error: {}", err)
        )
        self.threadpool.start(worker)

    # ==============================
    # 📊 参数解析函数
    # ==============================
    def load_params(self):
        """同步加载并解析参数结构"""
        logger.info("Starting synchronous param parsing")
        try:
            if os.path.exists(self.param_definitions_path):
                cfg = self._read_config()
                self.title = cfg.get("title", self.title)
                logger.success("Loaded title: {}", self.title)
                self._load_params(cfg.get("param-structure", {}))
                self.param_templates = cfg.get("param-template", {})
                self.tab_names = cfg.get("tab-names", {})
                self.patch_info = cfg.get("version-control", {})
            else:
                logger.error(
                    "Configuration file not found: {}", self.param_definitions_path
                )
        except Exception as e:
            logger.exception("Failed to parse parameters")

    def _load_params(self, param_structure: dict):
        """实际参数解析逻辑"""
        self.param_structure = param_structure
        self.init_params = self._recursive_parse(
            param_structure, self.params_type, self.require_flag, self.params_default, self.params_options, self.params_desc
        )

    def add_binding_model_params(self, param_structure: dict):
        self.model_binding_structure = param_structure
        self.init_params = self.init_params | self._recursive_parse(
            self.model_binding_structure, self.params_type, self.require_flag, self.params_default, self.params_options, self.params_desc
        )

    def remove_binding_model_params(self):
        self.params_type = {}
        self.require_flag = {}
        self.params_default = {}
        self.params_options = {}
        self.params_desc = {}
        self.subchildren_default = {}
        self.model_binding_structure = {}
        self.init_params = self._recursive_parse(
            self.param_structure, self.params_type, self.require_flag, self.params_default, self.params_options, self.params_desc
        )

    def _recursive_parse(
            self, structure, type_dict, require_flag, default_dict, options_dict, desc_dict, path_prefix=""
    ):
        result = {}
        for key, node in structure.items():
            full_path = f"{path_prefix}/{key}" if path_prefix else key
            type_dict[full_path] = node.get("type", "unknown")
            require_flag[full_path] = node.get("required", False)

            if "default" in node:
                default_dict[full_path] = node["default"]
            if "describe" in node:
                desc_dict[full_path] = node["describe"]
            if "options" in node:
                options_dict[full_path] = node["options"]

            if "children" in node:
                result[key] = self._recursive_parse(
                    node["children"], type_dict, require_flag, default_dict, options_dict, desc_dict, full_path
                )
            elif "subchildren" in node:
                result[key] = ""
                self.subchildren_default[full_path] = self._recursive_parse(
                    node["subchildren"],
                    type_dict,
                    require_flag,
                    default_dict,
                    options_dict,
                    desc_dict,
                    full_path,
                )
            else:
                result[key] = node.get("default", "")

        return result

    # ==============================
    # 📦 工具访问接口
    # ==============================
    def get_tools_by_type(self, tool_type: str):
        """根据类型获取工具"""
        return [
            self.api_tools.get(item) for item in self.tool_type_dict.get(tool_type, [])
        ]

    def get_tools_by_path(self, path: str):
        """根据路径获取工具"""
        try:
            return [
                self.api_tools.get(tool_name) for tool_name in self.params_options[path]
            ]
        except Exception as e:
            logger.error(f"获取工具失败: {str(e)}")
            return []

    def get_params_name(self):
        return [
            key
            for key, value in self.param_structure.items()
            if value.get("type") == "subgroup" and "测点名" in value.get("subchildren")
        ]

    def get_all_upload_paths(self, structure=None, path_prefix=""):
        if structure is None:
            structure = self.model_binding_structure

        upload_paths = []

        for key, value in structure.items():
            current_path = f"{path_prefix}/{key}" if path_prefix else key

            if value.get("type") == "upload":
                upload_paths.append(current_path)
            elif value.get("children") is not None:
                upload_paths.extend(self.get_all_upload_paths(value.get("children"), current_path))

        return upload_paths

    def get_model_binding_param_no(self, path):
        names = path.split("/")
        model_name = names[0]
        component_name = names[1]
        param_name = "/".join(names[2:]) if len(names) > 3 else names[2]
        return self.model_binding_structure.get(model_name).get("children").get(component_name).get("children").get(
            param_name).get("id")

    def get_model_binding_node_no(self, path):
        names = path.split("/")
        model_name = names[0]
        component_name = names[1]
        return self.model_binding_structure.get(model_name).get("children").get(component_name).get("id")