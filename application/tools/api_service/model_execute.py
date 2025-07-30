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


class ModelExecute(BaseTool):
    """
    DatasetUploader 用于：
      1. 上传本地文件或文件夹到 dataset/upload 接口（自动压缩为 ZIP），获取返回的 data.filePath 和 data.fileName。
      2. 调用 dataset/add 接口，保存一条记录（表单 form-data 方式）。
    """

    def __init__(self, base_url: str, api_key: str = "", run_path: str = "/rest/di/flow/run", **kwargs):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.run_path = run_path
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def execute(
            self,
            flow_no: str,
            flow_json: dict,
            flow_pic: str,
            node_no: str,
            run_type: str
    ) -> None:
        """
        保存记录（表单请求），返回 True/False
        """
        url = f"{self.base_url}{self.run_path}"
        data = {
            "flowNo": flow_no,
            "flowJson": flow_json,
            "flowPic": flow_pic,
            "nodeNo": node_no,
            "runTyp": run_type,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self.headers, json=data)
            resp.raise_for_status()
            result = resp.json()
            # 假设返回字段 code == 0 表示成功
            if result.get("code") == 0:
                logger.info(f"模型执行成功！")
            else:
                logger.error(f"模型执行失败, 返回信息: {result}")
        except httpx.RequestError as exc:
            logger.error(f"模型执行请求错误：{exc}")
        except httpx.HTTPStatusError as exc:
            logger.error(f"模型执行 HTTP 错误：{exc}")
        except Exception as exc:
            logger.error(f"模型执行时其他错误：{exc}")

    def call(
            self,
            flow_no: str,
            flow_json: dict,
            flow_pic: str,
            node_no: str,
            run_type: str = "1"
    ) -> None:
        """
        一体化：先上传文件，再保存记录
        """
        self.execute(flow_no, flow_json, flow_pic, node_no, run_type)
