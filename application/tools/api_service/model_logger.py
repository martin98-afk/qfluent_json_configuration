"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: model_uploader.py
@time: 2025/7/10 15:09
@desc: 
"""
import json
import os
import zipfile
from typing import Optional, Dict

import httpx
from loguru import logger

from application.base import BaseTool


class ModelLogger(BaseTool):
    """
    DatasetUploader 用于：
      1. 上传本地文件或文件夹到 dataset/upload 接口（自动压缩为 ZIP），获取返回的 data.filePath 和 data.fileName。
      2. 调用 dataset/add 接口，保存一条记录（表单 form-data 方式）。
    """

    def __init__(self, base_url: str, api_key: str = "", log_path: str = "/rest/di/flow/run", **kwargs):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.log_path = log_path
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def execute(self, node_no: str) -> None:
        """
        保存记录（表单请求），返回 True/False
        """
        url = f"{self.base_url}{self.log_path}"
        data = {
            "nodeNo": node_no
        }
        try:
            with httpx.Client(timeout=self.timeout, verify=False) as client:
                resp = client.get(url, headers=self.headers, params=data)
            resp.raise_for_status()
            result = resp.json()
            # 假设返回字段 code == 0 表示成功
            if result.get("code") == 0:
                logger.info(f"组件日志查询成功!")
                return result["data"]["nodeLog"]
            else:
                raise Exception(f"组件日志查询失败, 返回信息: {result}")
        except httpx.RequestError as exc:
            raise Exception(f"组件日志查询请求错误：{exc}")
        except httpx.HTTPStatusError as exc:
            raise Exception(f"组件日志查询 HTTP 错误：{exc}")
        except Exception as exc:
            raise Exception(f"组件日志查询时其他错误：{exc}")

    def call(self, node_no: str) -> None:
        """
        一体化：先上传文件，再保存记录
        """
        return self.execute(node_no)
