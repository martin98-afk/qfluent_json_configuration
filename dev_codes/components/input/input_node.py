"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: logistic_regression.py
@time: 2025/9/26 14:41
@desc: 
"""

from dev_codes.components.base import BaseComponent


class UserInputComponent(BaseComponent):
    name = "User Input"
    category = "Input"
    description = "Simulate user input"

    @classmethod
    def get_outputs(cls):
        return [("value", "Value")]

    @classmethod
    def get_properties(cls):
        return {
            "label": {"type": "text", "default": "Enter name", "label": "Prompt Label"}
        }

    def run(self, params, inputs=None):
        # 实际项目可弹窗，这里模拟
        return {"value": "Alice"}