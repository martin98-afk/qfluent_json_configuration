"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: write_service_path.py
@time: 2025/7/2 16:09
@desc: 
"""
from application.base import BaseTool
from application.utils.nacos_config import NacosConfig


class WriteNacosServicePath(BaseTool):

    def __init__(self,
                 host="http://172.16.134.122:8849",
                 username="nacos",
                 password="Luculent@2023!",
                 data_id="sushine-eeoptimize.properties",
                 group="DEFAULT_GROUP",
                 namespace="test-nhyh",
                 parent=None, **kwargs):
        super().__init__(parent)
        self.nacos_kwargs = {"host": host,
                             "username": username,
                             "password": password,
                             "data_id": data_id,
                             "group": group,
                             "namespace": namespace}

    def call(self, service_urls: list[str]):
        """
        param:
        service_list: 服务列表：【服务名称，服务url】
        """
        eeoptimize_config = NacosConfig(**self.nacos_kwargs)
        eeoptimize_config.raw["modelsUrl"] = ",".join(service_urls)
        eeoptimize_config.write()