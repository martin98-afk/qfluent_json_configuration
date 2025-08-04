"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: get_service_path.py
@time: 2025/7/2 16:03
@desc: 
"""

from application.base import BaseTool
from application.utils.nacos_config import NacosConfig


class GetNacosServicePath(BaseTool):

    def __init__(self,
                 host="http://172.16.134.122:8849",
                 username="nacos",
                 password="Luculent@2023!",
                 data_id="sushine-eeoptimize.properties",
                 group="DEFAULT_GROUP",
                 namespace="test-nhyh",
                 parent=None, **kwargs):
        super().__init__(parent)
        self.eeoptimize_config = NacosConfig(
            **{"host": host,
             "username": username,
             "password": password,
             "data_id": data_id,
             "group": group,
             "namespace": namespace}
        )

    def call(self, service_list: list):
        """
        param:
        service_list: 服务列表：【服务名称，服务url】
        """
        return self.eeoptimize_config.raw.get("modelsUrl", "").split(",")