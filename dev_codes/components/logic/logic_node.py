"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: logic_node.py
@time: 2025/9/26 14:42
@desc: 
"""
from dev_codes.components.base import BaseComponent


class LogicComponent(BaseComponent):
    name = "Logic Node"
    category = "Logic"
    description = "Simulate user input"

    @classmethod
    def get_outputs(cls):
        return [("value", "Value")]

    @classmethod
    def get_properties(cls):
        return {
            "parameter1": {"type": "text", "default": "Enter name", "label": "Prompt Label"},
            "parameter2": {"type": "text", "default": "Enter ip", "label": "test ip"}
        }

    def run(self, params, inputs=None):
        # 实际项目可弹窗，这里模拟

        return {"value": "Alice"}