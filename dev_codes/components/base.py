"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: base.py
@time: 2025/9/26 15:02
@desc: 
"""
# components/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseComponent(ABC):
    """所有组件必须继承此类"""
    name: str = "Unnamed Component"
    category: str = "General"
    description: str = ""

    @abstractmethod
    def run(self, params: Dict[str, Any], inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        params: 节点属性（来自UI）
        inputs: 上游输入（key=输入端口名）
        return: 输出数据（key=输出端口名）
        """
        pass

    @classmethod
    def get_inputs(cls) -> list:
        """返回输入端口定义：[('port_name', 'Port Label')]"""
        return []

    @classmethod
    def get_outputs(cls) -> list:
        """返回输出端口定义：[('port_name', 'Port Label')]"""
        return []

    @classmethod
    def get_properties(cls) -> dict:
        """
        返回属性定义：{'prop_name': {'type': 'text', 'default': '...'}}
        支持类型：'text', 'int', 'bool', 'choice'
        """
        return {}