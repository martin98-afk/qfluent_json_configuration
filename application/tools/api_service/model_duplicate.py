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


class ModelDuplicate(BaseTool):
    """
    DatasetUploader 用于：
      1. 上传本地文件或文件夹到 dataset/upload 接口（自动压缩为 ZIP），获取返回的 data.filePath 和 data.fileName。
      2. 调用 dataset/add 接口，保存一条记录（表单 form-data 方式）。
    """

    def __init__(self, base_url: str, api_key: str, copy_path: str, model_info: str, env_path:str, **kwargs):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.copy_path = copy_path
        self.model_info = model_info
        self.env_path = env_path
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def _get_model_env_id(self, model_id):
        url = f"{self.base_url}{self.model_info}"
        params = {
            "flowNo": model_id
        }
        try:
            with httpx.Client(timeout=self.timeout, verify=False) as client:
                resp = client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            result = resp.json()
            # 假设返回字段 code == 0 表示成功
            if result.get("code") == 0:
                logger.info(f"获取模型环境成功！")
                return result.get("data").get("envId")
            else:
                raise Exception(f"获取模型环境失败, 错误信息: {result}")
        except httpx.RequestError as exc:
            raise Exception(f"获取模型环境请求错误：{exc}")
        except httpx.HTTPStatusError as exc:
            raise Exception(f"获取模型环境 HTTP 错误：{exc}")
        except Exception as exc:
            raise Exception()

    def _link_new_model_env(self, new_model_id, env_id):
        url = f"{self.base_url}{self.env_path}"
        params = {
            "envId": env_id,
            "flowNo": new_model_id
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            result = resp.json()
            # 假设返回字段 code == 0 表示成功
            if result.get("code") == 0:
                logger.info(f"关联模型环境成功！")
            else:
                raise Exception(f"关联模型环境失败, 错误信息: {result}")
        except httpx.RequestError as exc:
            raise Exception(f"关联模型环境请求错误：{exc}")

    def call(
            self,
            model_id: str,
            new_model_name: str
    ) -> None:
        """
        保存记录（表单请求），返回 True/False
        """
        env_id = self._get_model_env_id(model_id)
        url = f"{self.base_url}{self.copy_path}"
        data = {
            "flowNo": model_id,
            "templateNam": new_model_name,
            "templateDesc": ""
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self.headers, json=data)
            resp.raise_for_status()
            result = resp.json()
            new_model_id = result.get("data")
            # 假设返回字段 code == 0 表示成功
            if result.get("code") == 0:
                logger.info(f"复制模型成功！")
                self._link_new_model_env(new_model_id, env_id)
            else:
                raise Exception(f"复制模型失败, 返回信息: {result}")
        except httpx.RequestError as exc:
            raise Exception(f"复制模型请求错误：{exc}")
        except httpx.HTTPStatusError as exc:
            raise Exception(f"复制模型 HTTP 错误：{exc}")
        except Exception as exc:
            raise Exception(f"复制模型时其他错误：{exc}")

