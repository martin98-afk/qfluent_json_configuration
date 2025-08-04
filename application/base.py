# 生成base parameter类，主要方法有编辑参数、保存参数、加载参数三个抽象方法
from abc import ABC

import httpx
import tenacity
from tenacity import stop_after_attempt, wait_fixed, retry_if_exception_type


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