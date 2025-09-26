"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: print_node.py
@time: 2025/9/26 14:42
@desc: 
"""
from dev_codes.components.base import BaseComponent


class PrintMessageComponent(BaseComponent):
    name = "Print Message"
    category = "Output"
    description = "Print a message to console and log"

    @classmethod
    def get_outputs(cls):
        return [("out", "Output")]

    @classmethod
    def get_properties(cls):
        return {
            "message": {"type": "text", "default": "Hello World", "label": "Message"}
        }

    def run(self, params, inputs=None):
        msg = params.get("message", "Hello")
        print(f"[Print] {msg}")  # 也会被捕获到日志
        return {"out": msg}