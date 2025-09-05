import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QMessageBox,
    QTreeWidgetItem,
    QMenu,
    QInputDialog,
    QShortcut,
    QFileDialog, QLabel,
)
from loguru import logger
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SegmentedWidget, CommandBar, Action, ComboBox

from application.utils.config_handler import yaml
from application.utils.utils import get_icon
from application.widgets.custom_input_messagebox import CustomMessageBox
from application.widgets.draggable_tree_widget import DraggableTreeWidget


class ConfigSettingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("设置修改")
        self.parent = parent
        self.setWindowTitle("配置文件编辑器")
        self.resize(900, 650)
        px6 = int(6 * self.parent.scale)
        pt12 = round(12 * self.parent.scale)
        self.setStyleSheet(f"""
            QTreeWidget {{ font-size: {pt12}pt; background-color: #ffffff; border: none; }}
            QTreeWidget::item {{ padding: {px6}px; }}
            QLabel{{
                font: 20px 'Segoe UI';
                background: rgb(242,242,242);
                border-radius: 8px;
            }}
        """)
        self.tree = DraggableTreeWidget()
        self.tree.setHeaderLabels(["字段", "值"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 300)
        self.tree.setFont(QFont("Microsoft YaHei", 14))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_context_menu)
        self.tree.itemDoubleClicked.connect(self.toggle_expand_collapse)
        self.tree.setHeaders()
        self.clipboard_data = None

        # === 创建 CommandBar（顶部工具栏）===
        self.commandBar = CommandBar(self)
        self.commandBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)  # 图标+文字
        self.commandBar.setFixedHeight(40)  # 可选：固定高度

        # ✅ 新增：配置文件切换 ComboBox
        self.config_combo = ComboBox(self)
        self.config_combo.setFixedWidth(200)
        self.config_combo.setPlaceholderText("选择配置...")
        # ✅ 使用 CommandBar.addWidget() 插入控件到 CommandBar 最前面
        self.commandBar.addWidget(
            QLabel("切换配置: "),
        )
        self.commandBar.addWidget(
            self.config_combo,  # 控件
        )
        self.commandBar.addSeparator()
        # 创建按钮 Action
        self.restore_action = Action(get_icon("初始化配置数据"), '恢复默认', parent=self)
        self.import_action = Action(get_icon("打开文件"), '打开配置', parent=self)
        self.export_action = Action(FIF.SAVE_COPY, '导出配置', parent=self)
        self.save_action = Action(FIF.SAVE, '保存并应用', parent=self)

        # 设置图标（也可以保留 get_icon，但推荐使用 FIF）
        # 如果你坚持用 get_icon，可以这样：
        # self.restore_action.setIcon(get_icon("初始化配置数据"))

        # 添加到 CommandBar
        self.commandBar.addAction(self.restore_action)
        self.commandBar.addAction(self.import_action)
        self.commandBar.addAction(self.export_action)
        self.commandBar.addAction(self.save_action)

        # 连接信号
        self.config_combo.currentTextChanged.connect(self.on_config_switched)
        self.restore_action.triggered.connect(self.restore_config)
        self.import_action.triggered.connect(self.import_config)
        self.export_action.triggered.connect(self.export_config)
        self.save_action.triggered.connect(self.save_config)

        # 设置按钮样式（可选）
        # 由于 CommandBar 默认样式已符合 Fluent 风格，无需手动设置 bg_color

        # === 主布局 ===
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 添加顶部组件
        main_layout.addWidget(self.commandBar)  # 新增：顶部命令栏
        self.pivot = SegmentedWidget(self)
        main_layout.addWidget(self.pivot)
        main_layout.addWidget(self.tree)

        # === 加载配置列表 ===
        self.load_config_list()
        self.load_config()

        # 快捷键保持不变
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_node)
        QShortcut(QKeySequence("Ctrl+V"), self, self.paste_node)
        QShortcut(QKeySequence("Delete"), self, self.delete_parameter)

    def create_top_buttons(self):
        """Create buttons for each top-level node with mutual-exclusive selection."""
        self.pivot.clear()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            tab_name = (
                list(self.parent.config.tab_names.values())[i]
                if self.parent.config.tab_names
                else root.child(i).text(0)
            )
            ori_name = (
                list(self.parent.config.tab_names.keys())[i]
                if self.parent.config.tab_names
                else root.child(i).text(0)
            )
            self.pivot.addItem(
                ori_name, tab_name,
                onClick=lambda _, key=ori_name: self.show_subtree(key)
            )

        self.pivot.setCurrentItem(list(self.parent.config.tab_names.keys())[0])
        self.show_subtree(list(self.parent.config.tab_names.keys())[0])

    def switch_to(self, route_key: str, item_name=None):
        self.pivot.setCurrentItem(route_key)
        self.show_subtree(route_key, item_name)

    def show_subtree(self, key, item_name=None):
        """Display subtree under selected top-level node with precise visibility control.

        Behavior:
        - When item_name is None:
            * Only show top-level node expanded (displaying second-level nodes)
            * Second-level nodes remain collapsed (do not show third-level+ nodes)
        - When item_name is provided:
            * Only show the specified second-level node
            * Fully expand the specified second-level node and all its descendants
        """
        root = self.tree.invisibleRootItem()
        self.tree.blockSignals(True)

        # Hide all top-level nodes except the selected one
        for i in range(root.childCount()):
            item = root.child(i)
            item.setHidden(item.text(0) != key)

        # Reset tree state
        self.tree.collapseAll()

        # Find the visible top-level node
        top_item = None
        for i in range(root.childCount()):
            item = root.child(i)
            if not item.isHidden():
                top_item = item
                break

        if top_item is None:
            self.tree.blockSignals(False)
            return

        # Always expand the top-level node to show second-level nodes
        self.tree.expandItem(top_item)

        # Handle second-level filtering
        if item_name is not None:
            found = False
            for i in range(top_item.childCount()):
                child = top_item.child(i)
                if child.text(0) == item_name:
                    # Only show and expand the specified second-level node
                    child.setHidden(False)

                    # Recursively expand all descendants
                    stack = [child]
                    while stack:
                        current = stack.pop()
                        self.tree.expandItem(current)
                        # Add children in reverse order for proper DFS
                        for j in range(current.childCount() - 1, -1, -1):
                            stack.append(current.child(j))

                    found = True
                else:
                    # Hide other second-level nodes
                    child.setHidden(True)

            # Fallback if specified node not found
            if not found:
                for i in range(top_item.childCount()):
                    top_item.child(i).setHidden(False)
        else:
            # When no item_name provided, ensure all second-level nodes are visible
            # but remain collapsed (no need to expand them)
            for i in range(top_item.childCount()):
                top_item.child(i).setHidden(False)

        self.tree.blockSignals(False)

    def get_item_by_path(self, path):
        """
        根据路径字符串查找对应的 ConfigurableTreeWidgetItem
        :param path: 路径字符串，如 "根节点/子节点/目标节点"
        :return: 匹配的 ConfigurableTreeWidgetItem 或 None
        """
        if not path or not self.tree:
            return None

        # 分割路径
        target_parts = path.split('/')

        # 从顶层节点开始查找
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            result = self._find_child_by_path(top_item, target_parts)
            if result:
                return result

        return None

    def restore_config(self):
        self.config_combo.setCurrentText(0)
        self.parent.config.restore_default_params()
        self.parent.config.params_loaded.connect(self.on_config_loaded)
        self.parent.config.load_async()


    def on_config_loaded(self):
        with open(self.parent.config.param_definitions_path, 'r', encoding='utf-8') as f:
            data = yaml.load(f) or {}
        self.tree.clear()
        self.build_tree(data)
        self.create_top_buttons()  # Update buttons after restore

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入配置文件", "", "YAML 文件 (*.yaml *.yml);;所有文件 (*)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.load(f) or {}
                self.tree.clear()
                self.build_tree(data)
                self.parent.load_config(path)
                self.parent.reload_tree()
                QMessageBox.information(self, "导入成功", f"成功导入配置文件：{os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"导入配置失败：{e}")
        self.create_top_buttons()  # Update buttons after restore

    def toggle_expand_collapse(self, item, col):
        item.setExpanded(not item.isExpanded())

    def on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        menu.addAction("新增参数", self.add_parameter)
        submenu = menu.addMenu("新增预制参数类型")
        default_templates = self.parent.config.param_templates
        for template_name, template in default_templates.items():
            submenu.addAction(
                template.get("name", template_name),
                lambda template_name=template_name, template=template: self.add_default_param(
                    item, template_name, template
                ),
            )
        menu.addAction("复制节点", self.copy_node)
        menu.addAction("粘贴为子节点", self.paste_node)
        menu.addAction("删除节点", self.delete_parameter)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def add_default_param(self, parent, type, template):
        if parent.data(0, Qt.UserRole) not in ("dict", "list"):
            QMessageBox.warning(self, "操作错误", "只能在字典或列表下新增")
            return
        default_data = {"type": type} | {
            param: param_default
            for param, param_default in zip(
                template.get("params", []), template.get("params_default", [""] * len(template.get("params", [])))
            )
        }
        message_box = CustomMessageBox("输入键名", f"请输入 {template.get('name')} 参数名称", parent=self)
        if message_box.exec():
            key = message_box.get_text()
            new_item = self.create_item(parent, key, default_data)
            self.build_tree(default_data, new_item)
            parent.setExpanded(True)
        else:
            return

    def copy_node(self):
        item = self.tree.currentItem()
        if item:
            self.clipboard_data = self._serialize_item(item)

    def paste_node(self):
        parent = self.tree.currentItem()
        if parent and self.clipboard_data:
            if parent.data(0, Qt.UserRole) not in ("dict", "list"):
                QMessageBox.warning(self, "操作错误", "只能粘贴到字典或列表类型下！")
                return
            self._paste_data(parent, self.clipboard_data)

    def _serialize_item(self, item):
        data = {
            'key': item.text(0),
            'value': item.text(1),
            'type': item.data(0, Qt.UserRole),
            'children': [self._serialize_item(item.child(i)) for i in range(item.childCount())]
        }
        return data

    def _paste_data(self, parent, data):
        key = data['key']
        val_type = data['type']
        val = {} if val_type == 'dict' else [] if val_type == 'list' else data['value']
        new_item = self.create_item(parent, key, val)
        if val_type not in ('dict', 'list'):
            new_item.setText(1, str(val))
        for child_data in data['children']:
            self._paste_data(new_item, child_data)
        parent.setExpanded(True)

    def load_config(self):
        self.tree.clear()
        if os.path.exists(self.parent.config.param_definitions_path):
            with open(self.parent.config.param_definitions_path, "r", encoding="utf-8") as f:
                data = yaml.load(f) or {}
            self.build_tree(data)
        self.create_top_buttons()  # Create buttons after loading

    def build_tree(self, data, parent=None):
        parent = parent or self.tree.invisibleRootItem()
        if isinstance(data, dict):
            for k, v in data.items():
                item = self.create_item(parent, str(k), v)
                self.build_tree(v, item)
        elif isinstance(data, list):
            for i, v in enumerate(data):
                item = self.create_item(parent, f"[{i}]", v)
                self.build_tree(v, item)

    def create_item(self, parent, key, value):
        item = QTreeWidgetItem(parent, [key, "" if isinstance(value, (dict, list)) else str(value)])
        item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable)
        if isinstance(value, dict):
            item.setData(0, Qt.UserRole, "dict")
        elif isinstance(value, list):
            item.setData(0, Qt.UserRole, "list")
        else:
            item.setData(0, Qt.UserRole, type(value).__name__)
        return item

    def save_config(self):
        def item_to_data(item):
            t = item.data(0, Qt.UserRole)
            if t == "dict":
                return {item.child(i).text(0): item_to_data(item.child(i)) for i in range(item.childCount())}
            elif t == "list":
                return [item_to_data(item.child(i)) for i in range(item.childCount())]
            else:
                return item.text(1)

        root = self.tree.invisibleRootItem()
        result = {root.child(i).text(0): item_to_data(root.child(i)) for i in range(root.childCount())}
        with open(self.parent.config.param_definitions_path, "w", encoding="utf-8") as f:
            yaml.dump(result, f)
        QMessageBox.information(self, "保存成功", "配置文件已更新！")
        if self.parent:
            self.parent.load_config(self.parent.config.param_definitions_path)
            self.parent.reload_tree()

    def delete_parameter(self):
        cur = self.tree.currentItem()
        if not cur:
            QMessageBox.warning(self, "操作错误", "请先选中要删除的项！")
            return
        parent = cur.parent() or self.tree.invisibleRootItem()
        rep = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除 '{cur.text(0)}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if rep == QMessageBox.Yes:
            parent.removeChild(cur)
            # 新增逻辑：若从根节点删除，更新顶部按钮
            if parent is self.tree.invisibleRootItem():
                self.create_top_buttons()

    def filter_tree(self, text):
        text = text.lower()

        def recurse(item):
            visible = text in item.text(0).lower() or text in item.text(1).lower()
            for i in range(item.childCount()):
                child = item.child(i)
                if recurse(child):
                    visible = True
            item.setHidden(not visible)
            return visible

        recurse(self.tree.invisibleRootItem())

    def add_parameter(self):
        cur = self.tree.currentItem() or self.tree.invisibleRootItem()
        t = cur.data(0, Qt.UserRole)
        if t not in ("dict", "list"):
            QMessageBox.warning(self, "操作错误", "只能在字典或列表下添加！")
            return
        key = None
        if t == "dict":
            message_box = CustomMessageBox("参数键名", "请输入参数名称：", parent=self)
            if message_box.exec():
                key = message_box.get_text()
            else:
                return
        types = {
            "字符串": "",
            "整数": 0,
            "浮点数": 0.0,
            "布尔值": False,
            "字典": {},
            "列表": [],
        }
        ptype, ok = QInputDialog.getItem(
            self, "选择类型", "请选择类型：", list(types.keys()), 0, False
        )
        if not ok:
            return
        val = types[ptype]
        item = self.create_item(cur, key or f"[{cur.childCount()}]", val)
        if not isinstance(val, (dict, list)):
            item.setText(1, str(val))
        cur.setExpanded(True)
        # 新增逻辑：若添加到根节点，更新顶部按钮
        if cur is self.tree.invisibleRootItem():
            self.create_top_buttons()

    def load_config_list(self):
        """
        扫描 config 目录下的所有 .yaml 和 .yml 文件，填充到 ComboBox
        """
        config_dir = os.path.dirname(self.parent.config.param_definitions_path)  # 假设 parent.config 存在
        search_dirs = [config_dir] if os.path.isdir(config_dir) else []

        # 也可以扩展其他路径，比如当前目录
        if not search_dirs:
            search_dirs = ['.']

        files = []
        for d in search_dirs:
            try:
                for f in os.listdir(d):
                    if f.lower().endswith(('.yaml', '.yml')) and f != "default.yaml":
                        files.append(os.path.abspath(os.path.join(d, f)))
            except:
                pass

        yml_files = ["default.yaml"] + [os.path.basename(f) for f in files]
        self.config_combo.clear()
        self.config_files_map = {}  # ✅ 确保初始化
        self.config_combo.addItems(yml_files)
        self.config_files_map = {os.path.basename(f): f for f in files} | {"default.yaml": os.path.join(config_dir, "default.yaml")}

        self.config_combo.setCurrentText(0)

    def on_config_switched(self, filename):
        if not filename:
            return
        file_path = self.config_files_map.get(filename)
        if not file_path:
            return

        # 询问是否保存当前更改（可选）
        # 这里简化：直接加载
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.load(f) or {}

            # 更新 parent 的配置路径
            self.parent.config.param_definitions_path = file_path

            # 清空并重建树
            self.tree.clear()
            self.build_tree(data)
            self.create_top_buttons()

            # 更新 ComboBox 当前项（确保同步）
            self.config_combo.setCurrentText(filename)

            # 可选：通知主界面刷新
            if hasattr(self.parent, 'load_config'):
                self.parent.load_config(file_path)
                self.parent.reload_tree()

        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "加载失败", f"无法加载配置文件：{str(e)}")

    def export_config(self):
        # 弹出文件保存对话框，设置默认后缀为.yaml
        path, _ = QFileDialog.getSaveFileName(
                self,
                "导出配置文件",
                "",
                "YAML 文件 (*.yaml *.yml);;所有文件 (*)",
                options=QFileDialog.Options()
            )
        if not path:
            return  # 用户取消操作

        try:
            # 序列化树形数据（复用save_config中的逻辑）
            def item_to_data(item):
                t = item.data(0, Qt.UserRole)
                if t == "dict":
                    return {item.child(i).text(0): item_to_data(item.child(i)) for i in range(item.childCount())}
                elif t == "list":
                    return [item_to_data(item.child(i)) for i in range(item.childCount())]
                else:
                    return item.text(1)

            root = self.tree.invisibleRootItem()
            result = {root.child(i).text(0): item_to_data(root.child(i)) for i in range(root.childCount())}

            # 写入到指定路径
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(result, f)

            QMessageBox.information(self, "导出成功", f"配置已保存到：{os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"保存配置时发生错误：{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = ConfigSettingDialog("../../dist/config.yaml")
    dlg.show()
    sys.exit(app.exec_())
