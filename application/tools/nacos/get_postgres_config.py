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


class GetPostgresConfig(BaseTool):

    def __init__(self,
                 host="http://172.16.134.122:8849",
                 username="nacos",
                 password="Luculent@2023!",
                 data_id="database.properties",
                 group="DEFAULT_GROUP",
                 namespace="test-nhyh",
                 parent=None, **kwargs):
        super().__init__(parent)
        self.database_config = {
            "host": host,
            "username": username,
            "password": password,
            "data_id": data_id,
            "group": group,
            "namespace": namespace
        }
        self.nacos_config = NacosConfig(**self.database_config)

    def call(self):
        """
        param:
        service_list: 服务列表：【服务名称，服务url】
        """

        return {
            "host": self.nacos_config.raw.get("datasource-ip-port").split(":")[0],
            "port": self.nacos_config.raw.get("datasource-ip-port").split(":")[1],
            "user": self.nacos_config.raw.get("datasource-username"),
            "password": self.nacos_config.raw.get("datasource-password"),
            "database": self.nacos_config.raw.get("datasource-business-database")
        }