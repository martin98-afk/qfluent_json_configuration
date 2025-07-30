"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: di_flow_params.py
@time: 2025/6/27 17:14
@desc: 
"""
import psycopg2

from loguru import logger
from psycopg2 import OperationalError

from application.base import BaseTool


class DiFlow(BaseTool):

    def __init__(self,
                 host: str="172.16.134.122",
                 port: str="5030",
                 user: str="postgres",
                 password: str="Sushine@2024Nov!",
                 database: str="sushine_business",
                 parent=None):
        super().__init__(parent)
        self.conn_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database
        }

    # 查询数据
    def get_flows(self, flow_nam, with_flow_no, with_flow_json, with_flow_pic):
        """
        查询流程信息

        参数:
            flow_nam (str): 流程名称，如果为None则返回所有流程
            with_flow_no (bool): 是否包含流程编号
            with_flow_json (bool): 是否包含流程JSON数据
            with_flow_pic (bool): 是否包含流程图数据

        返回:
            list: 查询结果列表。如果只查询单个字段，则返回该字段值的列表；
                  如果查询多个字段，则返回每个记录的列表集合
        """
        with psycopg2.connect(**self.conn_params) as conn:
            try:
                cur = conn.cursor()
                columns = ["flow_nam"]
                if with_flow_no:
                    columns.append("flow_no")
                if with_flow_json:
                    columns.append("flow_json")
                if with_flow_pic:
                    columns.append("flow_pic")
                execute_sql = f"SELECT {','.join(columns)} FROM di_flow"
                execute_sql = execute_sql + f" WHERE flow_nam='{flow_nam}'" if flow_nam else execute_sql
                cur.execute(execute_sql + " ORDER BY fstusr_dtm DESC")  # 替换为你的查询语句
                rows = cur.fetchall()
                if len(columns) == 1:
                    return [row[0] for row in rows]
                else:
                    return [list(row) for row in rows]
            except OperationalError as e:
                logger.error(f"模型画布查询失败: {e}")

    def call(self, flow_nam=None, with_flow_no=False, with_flow_json=False, with_flow_pic=False):

        return self.get_flows(flow_nam, with_flow_no, with_flow_json, with_flow_pic)


if __name__ == "__main__":
    flows = DiFlow()
    result = flows.call()
