"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: nacos_config.py
@time: 2025/7/2 15:29
@desc: 支持保留格式注释的Nacos配置管理
"""

import json
import time
from typing import Optional, Dict, Any

import httpx

try:
    from ruamel.yaml import YAML  # 支持注释保留的YAML库
    _has_ruamel = True
except ImportError:
    _has_ruamel = False

def build_recursion(obj: dict, prefix: str = "") -> Dict[str, Any]:
    """递归展平配置字典"""
    results = {}
    for key, value in obj.items():
        name = f"{prefix}.{key}" if prefix else key
        results[name] = value
        if isinstance(value, dict):
            results.update(build_recursion(value, name))
    return results

class NacosConfig():
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        data_id: str,
        group: str,
        namespace: Optional[str] = None,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.data_id = data_id
        self.group = group
        self.namespace = namespace

        self.access_token = None
        self.expired_at = None
        self.raw = None       # 解析后的配置字典
        self.raw_text = None  # 原始配置文本
        self.configs = None   # 展平后的配置
        self.loaded = False
        self.load()

    def login(self):
        """增强的登录方法（支持自动刷新）"""
        if self.expired_at and time.time() < self.expired_at:
            return

        resp = httpx.post(
            f"{self.host}/nacos/v1/auth/login",
            data={"username": self.username, "password": self.password},
            timeout=10
        )
        resp.raise_for_status()

        try:
            data = resp.json()
            self.access_token = data["accessToken"]
            self.expired_at = time.time() + data["tokenTtl"] - 1
        except (KeyError, json.JSONDecodeError) as e:
            raise ValueError(f"Login response error: {e}")

    def read_properties(self, text: str):
        """增强兼容性的Properties解析"""
        properties = {}
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                properties[key.strip()] = value.strip()
            else:
                properties[line] = ""

        self.raw = properties
        self.configs = build_recursion(properties)

    def read_json(self, text: str):
        """带异常处理的JSON解析"""
        try:
            self.raw = json.loads(text)
            self.configs = build_recursion(self.raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")

    def read_yaml(self, text: str):
        """带注释保留的YAML解析"""
        if not _has_ruamel:
            raise RuntimeError("ruamel.yaml required for YAML comment preservation")

        yaml = YAML()
        yaml.preserve_quotes = True
        try:
            self.raw = yaml.load(text)
            self.configs = build_recursion(self.raw)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}")

    def write(self):
        """写入配置（保留原始格式和注释）"""
        if not self.loaded:
            raise RuntimeError("Configuration not loaded")

        config_type = self._get_config_type()
        content = self._serialize_config(config_type)

        params = {
            "dataId": self.data_id,
            "group": self.group,
            "tenant": self.namespace,
            "content": content,
            "accessToken": self.access_token,
            "type": config_type  # 显式指定配置类型 [[1]][[7]]
        }

        resp = httpx.post(
            f"{self.host}/nacos/v1/cs/configs",
            params=params,
            timeout=10
        )
        resp.raise_for_status()
        if resp.text.lower() != "true":
            raise ValueError(f"Write failed: {resp.text}")

    def _get_config_type(self) -> str:
        """根据data_id推断配置类型"""
        ext_map = {
            ".yaml": "yaml", ".yml": "yaml",
            ".json": "json", ".properties": "properties"
        }
        for ext, cfg_type in ext_map.items():
            if self.data_id.endswith(ext):
                return cfg_type
        return "text"

    def _serialize_config(self, config_type: str) -> str:
        """统一配置序列化入口"""
        if config_type == "properties":
            return self._serialize_properties_with_comments()
        elif config_type == "yaml":
            return self._serialize_yaml_with_comments()
        elif config_type == "json":
            return json.dumps(self.raw, indent=2)
        else:
            raise ValueError(f"Unsupported type: {config_type}")

    def _serialize_properties_with_comments(self) -> str:
        """保留注释和格式的properties序列化"""
        modified_lines = []
        keys_to_update = {k: v for k, v in self.raw.items()
                         if not isinstance(v, dict)}

        for line in self.raw_text.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                modified_lines.append(line)
                continue

            if '=' in line:
                key = stripped.split('=', 1)[0]
                if key in keys_to_update:
                    # 保留原始行的格式（缩进、空格等）
                    indent = line[:line.find(key)]
                    modified_lines.append(f"{indent}{key}={keys_to_update[key]}")
                else:
                    modified_lines.append(line)
            else:
                modified_lines.append(line)

        return '\n'.join(modified_lines)

    def _serialize_yaml_with_comments(self) -> str:
        """保留注释的YAML序列化"""
        if not _has_ruamel:
            raise RuntimeError("ruamel.yaml required for YAML comment preservation")

        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)

        # 更新原始内容中的值
        def update_dict(d1, d2):
            for k, v in d2.items():
                if isinstance(v, dict) and k in d1:
                    update_dict(d1[k], v)
                elif k in d1:
                    d1[k] = v

        update_dict(self.raw, self._unflatten_config())
        import io
        stream = io.StringIO()
        yaml.dump(self.raw, stream)
        return stream.getvalue()

    def _unflatten_config(self) -> dict:
        """将展平的配置还原为嵌套结构"""
        nested = {}
        for flat_key, value in self.configs.items():
            parts = flat_key.split('.')
            current = nested
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = value
        return nested

    def load(self):
        """加载Nacos配置（保留原始文本）"""
        self.login()  # 自动刷新token

        resp = httpx.get(
            f"{self.host}/nacos/v1/cs/configs",
            params={
                "dataId": self.data_id,
                "group": self.group,
                "tenant": self.namespace,
                "accessToken": self.access_token,
            },
            timeout=10
        )
        resp.raise_for_status()

        config_type = resp.headers.get("Config-Type", "text")
        self.raw_text = resp.text  # 保存原始文本

        if config_type == "properties":
            self.read_properties(self.raw_text)
        elif config_type == "json":
            self.read_json(self.raw_text)
        elif config_type == "yaml":
            self.read_yaml(self.raw_text)
        else:
            raise ValueError(f"Unsupported config type {config_type}")

        self.loaded = True

    def get(self, name: str, default: Optional[str] = None, required: bool = True):
        """获取Nacos配置"""
        if not self.loaded:
            self.load()

        if self.configs is None:
            value = None
        else:
            value = self.configs.get(name, default)

        if required and value is None:
            raise KeyError(f"Nacos config {name} is not found")
        return value


if __name__ == "__main__":
    # 使用示例
    nacos_config = NacosConfig(
        host="http://172.16.134.122:8849",
        username="nacos",
        password="Luculent@2023!",
        data_id="sushine-eeoptimize.properties",
        group="DEFAULT_GROUP",
        namespace="test-nhyh"
    )

    # 修改配置并写回
    nacos_config.raw["modelsUrl"] = f"{nacos_config.raw['modelsUrl']},http://172.16.134.122:8900/rest/di/service/modelPublish/1/1933076943960276992"
    nacos_config.write()