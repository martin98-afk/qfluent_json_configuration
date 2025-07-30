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
import tempfile
import zipfile

import httpx
from loguru import logger

from application.base import BaseTool


class ModelUploader(BaseTool):
    """
    DatasetUploader 用于：
      1. 上传本地文件或文件夹到 dataset/upload 接口（自动压缩为 ZIP），获取返回的 data.filePath 和 data.fileName。
      2. 调用 dataset/add 接口，保存一条记录（表单 form-data 方式）。
    """

    def __init__(self, base_url: str, api_key: str, upload_path: str, del_path: str, env_path: str, **kwargs):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.upload_path = upload_path
        self.del_path = del_path
        self.env_path = env_path
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def get_model_id(self, file_path: str):
        """
        解压 ZIP 文件到临时目录，读取 diFlow.json 中的模型 ID。
        解压目录在使用完毕后会自动删除。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # 解压到临时目录
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # 构造 diFlow.json 路径
            json_path = os.path.join(temp_dir, "diFlow.json")

            # 读取模型 ID
            with open(json_path, 'r', encoding="utf-8") as f:
                model_id = json.load(f)["flowNo"]

            return model_id

    def del_duplicate(
            self,
            model_id: str,
    ) -> None:
        """
        保存记录（表单请求），返回 True/False
        """
        url = f"{self.base_url}{self.del_path}"
        data = {
            "flowNo[]": model_id
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self.headers, data=data)
            resp.raise_for_status()
            result = resp.json()
            # 假设返回字段 code == 0 表示成功
            if result.get("code") == 0:
                logger.info(f"删除重复模型成功！")
            else:
                logger.error(f"删除重复模型失败, 返回信息: {result}")
        except httpx.RequestError as exc:
            logger.error(f"删除重复模型请求错误：{exc}")
        except httpx.HTTPStatusError as exc:
            logger.error(f"删除重复模型 HTTP 错误：{exc}")
        except Exception as exc:
            logger.error(f"删除重复模型时其他错误：{exc}")

    def _link_new_model_env(self, model_id, env_id):
        url = f"{self.base_url}{self.env_path}"
        params = {
            "envId": env_id,
            "flowNo": model_id
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
                logger.error(f"关联模型环境失败, 错误信息: {result}")
        except httpx.RequestError as exc:
            logger.error(f"关联模型环境请求错误：{exc}")

    def call(
            self,
            file_path: str,
            env_id: str = None
    ) -> None:
        """
        上传文件/文件夹，自动压缩ZIP后上传，返回 {'filePath': ..., 'fileName': ...} 或 None
        """
        if not os.path.exists(file_path):
            logger.error(f"路径不存在：{file_path}")
            return None

        url = f"{self.base_url}{self.upload_path}"
        try:
            model_id = self.get_model_id(file_path)
            with open(file_path, "rb") as f:
                files = {
                    "file": (os.path.basename(file_path), f)
                }
                data = {
                    "fileName": os.path.basename(file_path),
                    "treeId": 0, "unitType": 0
                }
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=self.headers, files=files, data=data)
                resp.raise_for_status()
                result = resp.json()

            if result.get("state") == "success":
                logger.info(f"模型模板上传成功！")

            elif result.get("state") == "error" and result.get("message") == "请勿导入重复模型！":
                self.del_duplicate(model_id)
                self.call(file_path)

            # 关联模型运行环境
            self._link_new_model_env(model_id, env_id)
        except httpx.RequestError as exc:
            logger.error(f"上传请求错误：{exc}")
        except httpx.HTTPStatusError as exc:
            logger.error(f"上传 HTTP 错误：{exc}")
        except Exception as exc:
            logger.error(f"上传时其他错误：{exc}")
