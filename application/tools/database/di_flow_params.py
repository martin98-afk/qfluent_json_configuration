"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: di_flow_params.py
@time: 2025/6/27 17:14
@desc: 
"""
import copy
import json
import psycopg2

from collections import defaultdict
from loguru import logger
from psycopg2 import OperationalError

from application.base import BaseTool
from application.utils.utils import get_unique_name


class DiFlowParams(BaseTool):

    def __init__(self,
                 host: str = "172.16.134.122",
                 port: str = "5030",
                 user: str = "postgres",
                 password: str = "Sushine@2024Nov!",
                 database: str = "sushine_business",
                 parent=None):
        super().__init__(parent)
        self.type_dict = {
            "1": "checkbox",
            "2": "dropdown",
            "3": "multiselect_dropdown",
            "10": "upload"
        }
        self.conn_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database
        }

    # 查询数据
    def get_flow_nodes(self, conn, flow_nam='能耗优化模型(v6)'):
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT flow_json FROM di_flow where flow_nam='{flow_nam}'")  # 替换为你的查询语句
            rows = cur.fetchall()
            result = {
                dict["id"]: (dict["text"], dict["name"].split("-")[1], dict["rect"]["x"], dict["rect"]["y"])
                for dict in json.loads(rows[0][0])["pens"] if "unit" in dict["name"]
            }
            # 根据x, y坐标顺序进行排序
            return dict(sorted(result.items(), key=lambda item: (item[1][2], item[1][3])))

        except OperationalError as e:
            logger.error(f"画布流程查询失败: {e}")
        except Exception as e:
            logger.error(f"画布流程查询失败: {e}")

    # 查询组件参数
    def get_unit_params(self, conn, unit_no):
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT param_no, field_type, param_name, default_val, require_flag FROM di_unit_param where unit_no='{unit_no}' and param_type='0'")  # 替换为你的查询语句
            rows = cur.fetchall()
            result = {row[0]: (row[1], row[2], row[3], row[4] == 1) for row in rows}
            return dict(sorted(result.items(), key=lambda item: item[0]))
        except OperationalError as e:
            logger.error(f"组件参数查询失败: {e}")

    # 查询组件参数
    def get_node_params_value(self, conn, node_no):
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT param_no, unit_param_no, param_val FROM di_flow_node_param where node_no='{node_no}'")  # 替换为你的查询语句
            rows = cur.fetchall()
            result = {row[0]: (row[1], row[2]) for row in rows}
            return dict(sorted(result.items(), key=lambda item: item[1][0]))
        except OperationalError as e:
            logger.error(f"参数数值查询失败: {e}")

    def get_node_params_options(self, conn, param_no):
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT option_val, option_nam FROM di_unit_param_option where param_no='{param_no}'")  # 替换为你的查询语句
            rows = cur.fetchall()
            return {row[0]: row[1] for row in rows}
        except OperationalError as e:
            logger.error(f"下拉参数候选值查询失败: {e}")

    def call(self, prefix: str, service_name: str):
        with psycopg2.connect(**self.conn_params) as conn:
            flow_nodes = self.get_flow_nodes(conn, service_name)
            if not flow_nodes:
                logger.error(f"未找到 {service_name} 的流程内容！")
                return None, None, None

            flow_params = {
                value[1]: self.get_unit_params(conn, value[1])
                for value in set(flow_nodes.values())
            }
            option2val = {}
            flow_params_value = defaultdict(dict)
            for key, value in flow_nodes.items():
                results = self.get_node_params_value(conn, key)
                if len(results) > 0:
                    for k, v in results.items():
                        name = flow_params.get(value[1], {}).get(v[0], ("", ""))[1]
                        if name == "": continue
                        type = flow_params.get(value[1], {}).get(v[0], ("", ""))[0]
                        if type not in ["7", "8", "9"]:  # 去除特征、标签、预测字段选择
                            if type == "1":
                                select_options = ["否", "是"]
                                option2val[k] = {vv: kk for kk, vv in enumerate(select_options)}
                                flow_params_value[key] = flow_params_value[key] | {
                                    k: {
                                        "param_name": name,
                                        "default": select_options[int(v[1])] if v[1] else "",
                                        "type": self.type_dict.get(type, "text"),
                                        "required": flow_params.get(value[1], {}).get(v[0], ("", ""))[-1],
                                        "options": select_options
                                    }
                                }
                            elif type == "2":
                                options = self.get_node_params_options(conn, v[0])
                                option2val[k] = {vv: kk for kk, vv in options.items()}
                                flow_params_value[key] = flow_params_value[key] | {
                                    k: {
                                        "param_name": name,
                                        "default": options.get(v[1], ""),
                                        "type": self.type_dict.get(type, "text"),
                                        "required": flow_params.get(value[1], {}).get(v[0], ("", ""))[-1],
                                        "options": list(options.values())
                                    }
                                }
                            elif type == "3":
                                options = self.get_node_params_options(conn, v[0])
                                option2val[k] = {vv: kk for kk, vv in options.items()}
                                flow_params_value[key] = flow_params_value[key] | {
                                    k: {
                                        "param_name": name,
                                        "default": ", ".join([options.get(item, "") for item in v[1].split(",")]),
                                        "type": self.type_dict.get(type, "text"),
                                        "required": flow_params.get(value[1], {}).get(v[0], ("", ""))[-1],
                                        "options": list(options.values())
                                    }
                                }
                            else:
                                flow_params_value[key] = flow_params_value[key] | {
                                    k: {
                                        "param_name": name,
                                        "default": v[1],
                                        "required": flow_params.get(value[1], {}).get(v[0], ("", ""))[-1],
                                        "type": self.type_dict.get(type, "text"),
                                    }
                                }

                    if not flow_params_value[key]:
                        flow_params_value.pop(key)
                        continue
                    flow_params_value[key]["name"] = value[0]

        # 构建参数读取结构
        structure_params = copy.deepcopy(flow_params_value)
        children = {}
        for key, param in structure_params.items():
            children = children | {
                get_unique_name(param.pop("name"), children.keys()): {
                    "type": "group",
                    "id": key,
                    "children": {
                        v.pop("param_name"): v | {"id": k}
                        for k, v in param.items()
                    }
                }
            }
        param_structure = {
            f"{prefix}{service_name}": {
                "type": "group",
                "children": children
            }
        }

        return flow_params_value, param_structure, option2val


if __name__ == "__main__":
    flow_params = DiFlowParams()
    result = flow_params.call("", "数据建模")
