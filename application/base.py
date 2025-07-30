# 生成base parameter类，主要方法有编辑参数、保存参数、加载参数三个抽象方法
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from PyQt5.QtWidgets import QTreeWidgetItem


class BaseTool(ABC):
    base_url: str
    api_key: str
    headers: dict
    timeout: float = 5.0

    def __init__(self, parent=None):
        self.parent = parent

    def call(self, **kwargs) -> dict:
        raise NotImplementedError

    def batch_call(self, **kwargs) -> list[dict]:
        raise NotImplementedError