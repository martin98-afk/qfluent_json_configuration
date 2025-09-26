"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: create_dynamic_node.py
@time: 2025/9/26 15:06
@desc: 
"""
from NodeGraphQt import BaseNode

def create_node_class(component_class):
    """直接返回一个完整的节点类"""
    class DynamicNode(BaseNode):
        __identifier__ = 'dynamic'
        NODE_NAME = component_class.name

        def __init__(self):
            super().__init__()
            self.component_class = component_class

            # 添加属性
            for prop_name, prop_def in component_class.get_properties().items():
                default = prop_def.get("default", "")
                label = prop_def.get("label", prop_name)
                if prop_def.get("type") == "bool":
                    self.add_checkbox(prop_name, label, default)
                else:
                    self.add_text_input(prop_name, label, text=str(default))

            # 添加输入端口
            for port_name, label in component_class.get_inputs():
                self.add_input(port_name, label)

            # 添加输出端口
            for port_name, label in component_class.get_outputs():
                self.add_output(port_name, label)

    return DynamicNode