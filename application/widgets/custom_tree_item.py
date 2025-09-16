"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: custom_tree_item.py
@time: 2025/7/4 16:05
@desc: 
"""
import re
from typing import Union, List, Any, Optional

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QTreeWidgetItem, QCheckBox, QComboBox, QLineEdit, QLabel, QWidget
)
from qfluentwidgets import SwitchButton, TransparentToolButton, FluentIcon, TeachingTip, TeachingTipTailPosition

from application.widgets.multi_select_combobox import FancyMultiSelectComboBox
from application.widgets.tree_edit_command import TreeEditCommand
from application.widgets.value_slider import SliderEditor


class ConfigControlType:
    CHECKBOX = "checkbox"
    SLIDER = "slider"
    DROPDOWN = "dropdown"
    TEXT = "text"  # 新增文本类型 [[1]]
    MULTISELECT_DROPDOWN = "multiselect_dropdown"  # 新增多选下拉类型


class ConfigurableTreeWidgetItem(QTreeWidgetItem):
    """统一配置树控件项基类"""

    def __init__(
            self,
            key: str,
            value: Any,
            full_path: str = "",
            control_type: Optional[str] = None,  # 默认不指定类型 [[9]]
            editor = None,
            required: bool = False,
            desc: str = None
    ):
        super().__init__()
        self.editor = editor
        # 构造带红色星号的 key
        self.key = key
        self.setText(0, key)
        self.required = required
        self.desc = desc

        self.full_path = full_path
        self.control_type = control_type
        # 兼容模式：仅提供 key 和 value 时创建普通文本项 [[2]]
        if control_type is None:
            self.setText(1, str(value))
            return

        self._init_control(value)

    def _init_control(self, value: Any):
        """根据控件类型初始化对应控件"""
        if self.control_type == ConfigControlType.CHECKBOX:
            self._init_checkbox(value)
        elif self.control_type == ConfigControlType.SLIDER:
            self._init_slider(value)
        elif self.control_type == ConfigControlType.DROPDOWN:
            self._init_dropdown(value)
        elif self.control_type == ConfigControlType.TEXT:
            self._init_text(value)  # 新增文本类型支持 [[1]]
        elif self.control_type == ConfigControlType.MULTISELECT_DROPDOWN:
            self._init_multiselect_dropdown(value)  # 新增处理

        self.setText(1, str(value))  # 默认文本显示

    def _init_text(self, value: Any):
        """初始化文本编辑控件"""
        self.setForeground(1, QColor("transparent"))  # 和背景色一样
        self.setBackground(1, QColor("transparent"))  # 确保背景也是白的
        self.text_editor = QLineEdit()
        self.text_editor.setText(str(value))

        # 样式设置
        self.text_editor.setStyleSheet(self._get_text_style())

        # 信号连接
        self.text_editor.textEdited.connect(
            lambda: self._handle_text_change()
        )

    def _init_checkbox(self, value: Any):
        """初始化复选框控件"""
        self.setForeground(1, QColor("transparent"))  # 和背景色一样
        self.setBackground(1, QColor("transparent"))  # 确保背景也
        self.checkbox = SwitchButton()
        options = self.editor.config.params_options[self.full_path]
        # 设置选项状态
        self.checkbox.setChecked(value == options[1])
        self.checkbox.setOffText(options[0])
        self.checkbox.setOnText(options[1])
        self.checkbox.checkedChanged.connect(
            lambda: self._handle_checkbox_change(options)
        )

    def _init_slider(self, value: Union[int, float]):
        """初始化滑动条控件"""
        self.setForeground(1, QColor("transparent"))  # 和背景色一样
        self.setBackground(1, QColor("transparent"))  # 确保背景也
        bound = self.editor.config.params_options.get(self.full_path, [0, 100, 1])
        # 设置滑动条参数
        decimal_num = int(bound[2]) if len(bound) >= 3 else 1
        self.slider = SliderEditor(
            minimum=round(float(bound[0]), decimal_num),
            maximum=round(float(bound[1]), decimal_num),
            initial=round(float(value), decimal_num) if value else round(float(bound[0]), decimal_num),
            decimal_point=decimal_num,
        )

        # 绑定事件
        self.slider.valueChanged.connect(
            lambda val: self._handle_slider_change(val)
        )

    def _init_dropdown(self, value: Any):
        """初始化下拉框控件"""
        self.setForeground(1, QColor("transparent"))  # 和背景色一样
        self.setBackground(1, QColor("transparent"))  # 确保背景也
        self.dropdown = QComboBox()
        self.dropdown.setStyleSheet(self._get_dropdown_style())
        self.dropdown.wheelEvent = lambda e: None
        options = self.editor.config.params_options[self.full_path]
        self.dropdown.addItems(options)

        # 设置初始值
        current_index = self.dropdown.findText(str(value))
        if current_index >= 0:
            self.dropdown.setCurrentIndex(current_index)

        # 绑定事件
        self.dropdown.activated.connect(
            lambda: self._handle_dropdown_change()
        )

    def _init_multiselect_dropdown(self, value: Any):
        self.setForeground(1, QColor("transparent"))
        self.setBackground(1, QColor("transparent"))
        options = self.editor.config.params_options[self.full_path]

        self.multiselect_dropdown = FancyMultiSelectComboBox(options, self.editor)

        # 设置初始值
        if isinstance(value, list):
            self.multiselect_dropdown.set_selected_items(value)
        elif isinstance(value, str):
            self.multiselect_dropdown.set_selected_items([item.strip() for item in value.split(',')])
        else:
            self.multiselect_dropdown.set_selected_items([])

        self.multiselect_dropdown.selectionChanged.connect(
            lambda: self._handle_multiselect_dropdown_change()
        )

    def _get_text_style(self):
        return """
            QLineEdit {
                padding: 0px;
                border: 0px solid #1890ff;
                border-radius: 4px;
                font-size: 11pt;
                background-color: transparent;
            }
        """

    def _get_dropdown_style(self):
        return (f"""
            QComboBox {{
                background-color: transparent;
                color: #333333;
                font-size: {13 * self.editor.scale}pt;
                padding: 2px 8px;
                border: 1px solid #ccc;
                border-radius: 10px;
                padding-right: 20px; /* 留出箭头空间 */
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
                background-color: transparent;
            }}
            QComboBox:hover {{
                border-color: #1890ff;
            }}
            QComboBox:focus {{
                border-color: #1890ff;
                outline: 0px;
            }}
            QComboBox QAbstractItemView {{
                background-color: white;
                color: #333333;
                border: 1px solid #1890ff;
                border-radius: 4px;
                font-size: {13 * self.editor.scale}pt;
                selection-background-color: #e6f7ff;
                selection-color: #1890ff;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #e6f7ff;
                color: #1890ff;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #f0f0f0;
            }}
        """)

    def _handle_text_change(self):
        """处理文本编辑完成事件"""
        old_state = self.editor.capture_tree_data()
        new_value = self.text_editor.text()
        self.setText(1, new_value)

        # 模型绑定更新 [[5]]
        if self.editor.config.api_tools.get("di_flow_params_modify") and re.search(
                self.editor.model_binding_prefix, self.full_path
        ):
            param_no = self.editor.config.get_model_binding_param_no(self.full_path)
            self.editor.config.api_tools.get("di_flow_params_modify").call(
                param_no=param_no, param_val=new_value
            )

        self.editor.undo_stack.push(TreeEditCommand(self.editor, old_state, f"编辑 {self.text(0)}"))

    def _handle_checkbox_change(self, options: List):
        """处理复选框状态变化"""
        old_state = self.editor.capture_tree_data()
        new_val = options[1] if self.checkbox.isChecked() else options[0]
        self.setText(1, str(new_val))
        self.checkbox.setText(options[1] if new_val == options[1] else options[0])
        # 数据持久化逻辑（示例）
        if hasattr(self.editor.config, 'api_tools'):
            self._update_model_binding(new_val)

        self.editor.undo_stack.push(TreeEditCommand(self.editor, old_state, f"编辑 {self.text(0)}"))

    def _handle_slider_change(self, value: int):
        """处理滑动条值变化"""
        old_state = self.editor.capture_tree_data()
        self.setText(1, str(value))
        self.editor.undo_stack.push(TreeEditCommand(self.editor, old_state, f"编辑 {self.text(0)}"))

    def _handle_dropdown_change(self):
        """处理下拉框选择变化"""
        old_state = self.editor.capture_tree_data()
        new_value = self.dropdown.currentText()
        self.setText(1, new_value)

        if hasattr(self.editor.config, 'api_tools'):
            self._update_model_binding(new_value)

        self.editor.undo_stack.push(TreeEditCommand(self.editor, old_state, f"编辑 {self.text(0)}"))

    def _handle_multiselect_dropdown_change(self):
        old_state = self.editor.capture_tree_data()
        new_value = self.multiselect_dropdown.get_selected_items()
        self.setText(1, ", ".join(new_value) if new_value else "")

        if hasattr(self.editor.config, 'api_tools'):
            self._update_model_binding(new_value)

        self.editor.undo_stack.push(TreeEditCommand(self.editor, old_state, f"编辑 {self.text(0)}"))

    def _update_model_binding(self, new_value: Any):
        """更新模型绑定数据"""
        if (self.editor.config.api_tools.get("di_flow_params_modify") and
                re.search(self.editor.model_binding_prefix, self.full_path)):
            param_no = self.editor.config.get_model_binding_param_no(self.full_path)
            if isinstance(new_value, list):
                option_value = ",".join([self.editor.option2val.get(param_no).get(str(item)) for item in new_value])
            else:
                option_value = self.editor.option2val.get(param_no).get(str(new_value))
            self.editor.config.api_tools.get("di_flow_params_modify").call(
                param_no=param_no,
                param_val=option_value
            )

    def set_item_widget(self):
        # ========== 第 0 列：用 setText 设置 key + 星号（保留原始样式） ==========
        display_text = self.key
        # if self.required:
        #     display_text += " (必填)"
        # if self.desc:
        #     display_text += " (带说明)"
        self.setText(0, display_text)  # ← 你原来的逻辑，完全保留！

        # ========== 第 1 列：设置编辑控件 ==========
        if self.control_type == ConfigControlType.CHECKBOX:
            self.editor.tree.setItemWidget(self, 1, self.checkbox)
        elif self.control_type == ConfigControlType.SLIDER:
            self.editor.tree.setItemWidget(self, 1, self.slider)
        elif self.control_type == ConfigControlType.DROPDOWN:
            self.editor.tree.setItemWidget(self, 1, self.dropdown)
        elif self.control_type == ConfigControlType.TEXT:
            self.editor.tree.setItemWidget(self, 1, self.text_editor)
        elif self.control_type == ConfigControlType.MULTISELECT_DROPDOWN:
            self.editor.tree.setItemWidget(self, 1, self.multiselect_dropdown)

        # # ========== 第 3 列：如果有说明，放置问号按钮 ==========
        # if self.desc:
        #     help_button = TransparentToolButton(FluentIcon.QUESTION)
        #     help_button.setFixedSize(24, 24)
        #     help_button.setCursor(Qt.PointingHandCursor)
        #     help_button.setToolTip("点击查看说明")
        #
        #     # 绑定点击事件 → 显示 TeachingTip
        #     def show_teaching_tip():
        #         TeachingTip.create(
        #             target=help_button,
        #             title="使用说明",
        #             content=self.desc,
        #             tailPosition=TeachingTipTailPosition.LEFT,  # 从左侧弹出，避免被树挡住
        #             duration=-1,  # 永不自动关闭
        #             parent=self.editor
        #         )
        #
        #     help_button.clicked.connect(show_teaching_tip)
        #     self.editor.tree.setItemWidget(self, 2, help_button)  # 👈 关键：放在第3列！

    def get_target_widget(self) -> Optional[QWidget]:
        """获取用于显示 TeachingTip 的目标控件（通常是第1列的编辑控件）"""
        if self.control_type == ConfigControlType.CHECKBOX:
            return self.checkbox
        elif self.control_type == ConfigControlType.SLIDER:
            return self.slider
        elif self.control_type == ConfigControlType.DROPDOWN:
            return self.dropdown
        elif self.control_type == ConfigControlType.TEXT:
            return self.text_editor
        elif self.control_type == ConfigControlType.MULTISELECT_DROPDOWN:
            return self.multiselect_dropdown
        else:
            # 普通文本项，返回 None 或 tree 本身（根据需求）
            return None