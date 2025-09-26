"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: logistic_regression.py
@time: 2025/9/26 14:41
@desc: 
"""
from loguru import logger

from dev_codes.components.base import BaseComponent


class LogisticRegressionComponent(BaseComponent):
    name = "Logistic Regression"
    category = "Algorithm"
    description = "Simulate user input"

    @classmethod
    def get_inputs(cls):
        return [("text", "text"), ("value", "value")]

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
        logger.info(inputs)
        logger.info(params)
        # 生成逻辑回归模型样例
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression()
        model.fit([[0, 0], [0, 1], [1, 0], [1, 1]], [0, 1, 1, 0])

        return {"value": model.predict([[2, 2]])}
