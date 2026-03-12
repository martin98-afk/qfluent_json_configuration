import os.path
import re
import shutil
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


class ParamConfigLoader(QObject):
    params_loaded = pyqtSignal()
    api_tools_loaded = pyqtSignal()
    database_tools_loaded = pyqtSignal()

    def __init__(self, param_definitions_path="default.yaml"):
        super().__init__()
        self.param_definitions_path = param_definitions_path
        # 如果默认配置不存在，则复制一份备用配置
        if not os.path.exists(param_definitions_path):
            self.restore_default_params()
        self.title = "Json配置工具"
        self.threadpool = QThreadPool.globalInstance()

    def _reset_params_config(self):
        self.param_structure = {}  # 当前参数结构
        self.init_params = {}  # 参数初始化数据
        self.params_type = {}  # 参数类型
        self.require_flag = {}  # 是否为必填参数 （当前未实装，展示效果不好）
        self.params_default = {}  # 参数默认值
        self.params_options = {}  # 参数可选值
        self.params_desc = {}  # 参数填写说明
        self.subchildren_default = {}  # 子参数默认值
        self.model_binding_structure = {}  # 参数配置绑定模型结构

    def _reset_tools_config(self):
        # 还原所有配置
        self.patch_info = {}   # 版本更新记录
        self.api_tools = {}
        self.tab_names = {}   # 配置标签中文名称
        self.tool_type_dict = {}
        self.param_templates = {}

    def restore_default_params(self):
        yaml = YAML()
        config_path = Path(self.param_definitions_path)

        if not os.path.exists(config_path):
            # 读取默认的yaml配置，并保存到本地
            try:
                shutil.copy(resource_path("default.yaml"), "default.yaml")
            except:
                logger.error("Failed to copy default.yaml")
            self.param_definitions_path = "default.yaml"
        else:
            # 由于api-tools栏经常有版本变动，加载老版本的配置自动更新成新版
            with config_path.open("r", encoding="utf-8") as f:
                cfg = yaml.load(f)

            # 如果是旧版配置，转换为新版
            if cfg.get("api-tools", {}).get("prefix") is not None:
                # 旧版配置，自动转换为新版配置
                prefix = cfg["api-tools"].pop("prefix")
                host = prefix.split("//")[1].split(":")[0]
                port = prefix.split("//")[1].split(":")[1]
                api_key = cfg["api-tools"].get("api-key")
                nacos_cfg = cfg.get("api-tools", {}).get("nacos")
                protocol = "http"
            else:
                # 新版配置
                nacos_cfg = cfg.get("api-tools", {}).get("nacos")
                host = cfg.get("api-tools", {}).get("全局服务地址")
                port = cfg.get("api-tools", {}).get("平台端口")
                api_key = cfg.get("api-tools", {}).get("平台鉴权码") if "平台鉴权码" in cfg.get("api-tools", {}) \
                    else cfg.get("api-tools", {}).get("api-key")
                protocol = cfg.get("api-tools", {}).get("接口协议类型")

            default_path = Path(resource_path("default.yaml"))

            with default_path.open("r", encoding="utf-8") as f:
                new_cfg = yaml.load(f)

            if nacos_cfg is not None:
                new_cfg["api-tools"]["nacos端口"] = nacos_cfg.get("port")
                new_cfg["api-tools"]["nacos用户名"] = nacos_cfg.get("username")
                new_cfg["api-tools"]["nacos密码"] = nacos_cfg.get("password")
                new_cfg["api-tools"]["nacos命名空间"] = nacos_cfg.get("namespace")
                new_cfg["api-tools"]["postgres地址(不填时使用全局地址)"] = nacos_cfg.get("postgres-host")
            else:
                new_cfg["api-tools"]["nacos端口"] = cfg.get("api-tools", {}).get("nacos端口")
                new_cfg["api-tools"]["nacos用户名"] = cfg.get("api-tools", {}).get("nacos用户名")
                new_cfg["api-tools"]["nacos密码"] = cfg.get("api-tools", {}).get("nacos密码")
                new_cfg["api-tools"]["nacos命名空间"] = cfg.get("api-tools", {}).get("nacos命名空间")
                new_cfg["api-tools"]["postgres地址(不填时使用全局地址)"] = cfg.get("api-tools", {}).get("postgres地址(不填时使用全局地址)")

            # 更新默认配置中的对应内容
            new_cfg["api-tools"]["接口协议类型"] = protocol
            new_cfg["api-tools"]["全局服务地址"] = host
            new_cfg["api-tools"]["平台端口"] = port
            new_cfg["api-tools"]["平台鉴权码"] = api_key
            cfg["api-tools"] = new_cfg["api-tools"]

            with config_path.open("w", encoding="utf-8") as f:
                yaml.dump(cfg, f)
                logger.info("Old version config updated successfully")

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

    def load_tools_async(self):
        """异步加载全部配置"""
        cfg = self._read_config()
        cfg = cfg.get("api-tools", cfg.get("api-search", {}))
        if "全局服务地址" not in cfg or "nacos" in cfg:
            self.restore_default_params()

        self.global_host = cfg.pop("全局服务地址", "")
        self.platform_port = cfg.pop("平台端口", "")
        self.global_api_key = cfg.pop("平台鉴权码", "")

        # 导入nacos工具
        type_cfg = {
            "nacos": {
                "host": self.global_host if cfg.get("nacos地址(不填时使用全局地址)") == "" else cfg.get("nacos地址(不填时使用全局地址)"),
                "port": cfg.get("nacos端口"),
                "username": cfg.get("nacos用户名"),
                "password": cfg.get("nacos密码"),
                "namespace": cfg.get("nacos命名空间"),
                "postgres-host": self.global_host if cfg.get("postgres地址(不填时使用全局地址)") == "" else cfg.get("postgres地址(不填时使用全局地址)")
            },
            "接口协议类型": cfg.get("接口协议类型", "http")
        }
        logger.info(f"Launching asynchronous nacos tools load!")
        worker = Worker(self._load_tools_parallel, type_cfg)
        worker.signals.finished.connect(
            lambda _: (
                logger.info(f"nacos Tools async load finished"),
                self.database_tools_loaded.emit(),
            )
        )
        worker.signals.error.connect(
            lambda err: logger.error(f"Async full load nacos tools error: {err}")
        )
        self.threadpool.start(worker)

        if "api" in cfg:
            # 导入接口工具
            type_cfg = {"api": cfg["api"], "接口协议类型": cfg.get("接口协议类型", "http")}
            logger.info(f"Launching asynchronous api tools load!")
            worker = Worker(self._load_tools_parallel, type_cfg)
            worker.signals.finished.connect(
                lambda _: (
                    logger.info(f"api Tools async load finished"),
                    self.api_tools_loaded.emit(),
                )
            )
            worker.signals.error.connect(
                lambda err: logger.error(f"Async full load nacos tools error: {err}")
            )
            self.threadpool.start(worker)
        else:
            self.api_tools_loaded.emit()

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
    # 🔧 工具加载函数
    # ==============================
    def _load_tools_parallel(self, cfg: dict) -> dict:
        """并行加载工具实例"""
        # 优先加载postgres工具
        logger.debug("Parallel tool load started for tools: {}", list(cfg.keys()))
        tool_list = {}
        self.protocol_type = cfg.get("接口协议类型", "http")
        # 增加连接postgres数据库的工具
        if "nacos" in cfg:
            nacos_cfg = cfg.pop("nacos", {})
            nacos_cfg = nacos_cfg
            nacos_cfg.update({
                "host": f"http://{self.global_host if 'host' not in nacos_cfg else nacos_cfg['host']}:{nacos_cfg.get('port', '8849')}",
                "username": nacos_cfg.get("username", "nacos"),
                "password": nacos_cfg.get("password", "nacos"),
                "namespace": nacos_cfg.get("namespace", "sushine"),
            })
            try:
                tool_list["get_service_path"] = GetNacosServicePath(**nacos_cfg)
                tool_list["write_service_path"] = WriteNacosServicePath(**nacos_cfg)
            except:
                logger.error("Failed to load eeoptimize nacos config")

            tool_list["get_postgres_config"] = GetPostgresConfig(**nacos_cfg)
            postgres_cfg = tool_list["get_postgres_config"].call()
            # 如果postgres中host配置不是真实的地址，则检测是否有postgres单独配置的地址，否则使用全局host
            if not re.search(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", postgres_cfg["host"]):
                postgres_cfg["host"] = nacos_cfg.pop("postgres-host", self.global_host)
            tool_list["di_flow"] = DiFlow(**postgres_cfg)
            tool_list["di_env"] = DiEnv(**postgres_cfg)
            tool_list["di_flow_params"] = DiFlowParams(**postgres_cfg)
            tool_list["di_flow_params_modify"] = DiFlowParamsModify(**postgres_cfg)
            self.api_tools.update(tool_list)
            return
        else:
            cfg = cfg.get("api", cfg)

        def create_searcher(tool_name, cfg_tool):
            prefix = cfg_tool.pop("prefix", f"{self.protocol_type}://{self.global_host}:{self.platform_port}")
            api_key = cfg_tool.pop("api-key", self.global_api_key)
            tool_type = cfg_tool.get("type")
            if tool_type == "point-search":
                return tool_name, tool_type, PointSearcher(prefix, api_key, **cfg_tool)
            elif tool_type == "rtsp-search":
                return tool_name, tool_type, RTSPSearcher(prefix, api_key, **cfg_tool)
            elif tool_type == "file-upload":
                return tool_name, tool_type, DatasetUploader(prefix, api_key, **cfg_tool)
            elif tool_type == "model-upload":
                return tool_name, tool_type, ModelUploader(prefix, api_key, **cfg_tool)
            elif tool_type == "model-duplicate":
                return tool_name, tool_type, ModelDuplicate(prefix, api_key, **cfg_tool)
            elif tool_type == "model-logger":
                return tool_name, tool_type, ModelLogger(prefix, api_key, **cfg_tool)
            elif tool_type == "model-execute":
                return tool_name, tool_type, ModelExecute(prefix, api_key, **cfg_tool)
            elif tool_type == "trenddb-fetcher":
                return tool_name, tool_type, TrenddbFetcher(prefix, api_key, **cfg_tool)
            elif tool_type == "services-list":
                return tool_name, tool_type, SeviceListSearcher(prefix, api_key, **cfg_tool)
            elif tool_type == "services-params":
                return tool_name, tool_type, ServiceParamsFetcher(prefix, api_key, **cfg_tool)
            elif tool_type == "services-logs":
                return tool_name, tool_type, ServiceLogger(prefix, api_key, **cfg_tool)
            elif tool_type == "services-reonline":
                return tool_name, tool_type, ServiceReonline(prefix, api_key, **cfg_tool)
            else:
                logger.error(f"未知的工具类型: {tool_type}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_map = {
                executor.submit(create_searcher, name, spec): name
                for name, spec in cfg.items()
            }
            for future in as_completed(future_map):
                tool_name = future_map[future]
                try:
                    name, tool_type, searcher = future.result()
                    if searcher:
                        tool_list[name] = searcher
                        self.tool_type_dict.setdefault(tool_type, []).append(name)
                except Exception as e:
                    logger.error(f"加载工具 {tool_name} 失败: {e}")

        self.api_tools.update(tool_list)
        return

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
        self.init_params.update(self._recursive_parse(
            self.model_binding_structure, self.params_type, self.require_flag, self.params_default, self.params_options, self.params_desc
        ))

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