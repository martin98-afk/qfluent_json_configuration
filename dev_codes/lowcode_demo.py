"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: lowcode_demo.py
@time: 2025/9/26 14:21
@desc: 
"""
import sys
import json
import io
from collections import deque, defaultdict
from contextlib import redirect_stdout, redirect_stderr

from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QTreeWidgetItem
from PyQt5.QtCore import Qt
from qfluentwidgets import (
    FluentWindow, TreeWidget,
    PrimaryPushButton, setTheme, Theme, FluentIcon as FIF, ToolButton, MessageBox
)
from NodeGraphQt import NodeGraph

# ----------------------------
# 属性面板（右侧）
# ----------------------------
from qfluentwidgets import CardWidget, BodyLabel, LineEdit, TextEdit


def get_port_node(port):
    """安全获取端口所属节点，兼容 property 和 method"""
    node = port.node
    return node() if callable(node) else node


from dev_codes.utils.create_dynamic_node import create_node_class
from dev_codes.scan_components import scan_components


class PropertyPanel(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(300)
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(20, 20, 20, 20)
        self.current_node = None

    def update_properties(self, node):
        # 清空所有控件
        for i in reversed(range(self.vbox.count())):
            widget = self.vbox.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        self.current_node = node
        if not node:
            label = BodyLabel("Select a node to view details.")
            self.vbox.addWidget(label)
            return

        # 1. 节点标题
        title = BodyLabel(f"📌 {node.name()}")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.vbox.addWidget(title)

        # 2. 运行按钮
        run_btn = PrimaryPushButton("▶ Run This Node", self)
        run_btn.clicked.connect(lambda: self.run_current_node())
        self.vbox.addWidget(run_btn)

        # 3. 查看日志按钮
        log_btn = PrimaryPushButton("📄 View Node Log", self)
        log_btn.clicked.connect(lambda: self.view_node_log())
        self.vbox.addWidget(log_btn)

        # 4. 输入端口
        self.vbox.addWidget(BodyLabel("📥 Input Ports:"))
        for input_port in node.input_ports():
            port_name = input_port.name()
            upstream_data = self.get_upstream_data(node, port_name)
            value_str = json.dumps(upstream_data, indent=2, ensure_ascii=False) if upstream_data is not None else "No input"
            self.vbox.addWidget(BodyLabel(f"  • {port_name}:"))
            text_edit = TextEdit()
            text_edit.setPlainText(value_str)
            text_edit.setReadOnly(True)
            text_edit.setMaximumHeight(80)
            self.vbox.addWidget(text_edit)

        # 5. 输出端口
        self.vbox.addWidget(BodyLabel("📤 Output Ports:"))
        result = self.get_node_result(node)
        if result:
            for port_name, value in result.items():
                value_str = json.dumps(value, indent=2, ensure_ascii=False)
                self.vbox.addWidget(BodyLabel(f"  • {port_name}:"))
                text_edit = TextEdit()
                text_edit.setPlainText(value_str)
                text_edit.setReadOnly(True)
                text_edit.setMaximumHeight(80)
                self.vbox.addWidget(text_edit)
        else:
            self.vbox.addWidget(BodyLabel("  No output yet. Click 'Run This Node'."))

    def get_upstream_data(self, node, port_name):
        """从主窗口获取上游输入数据"""
        if hasattr(self.parent(), 'get_node_input'):
            return self.parent().get_node_input(node, port_name)
        return None

    def get_node_result(self, node):
        """从主窗口获取节点运行结果"""
        if hasattr(self.parent(), 'node_results'):
            return self.parent().node_results.get(node.id, {})
        return {}

    def run_current_node(self):
        """触发主窗口运行当前节点"""
        if self.current_node and hasattr(self.parent(), 'run_single_node'):
            self.parent().run_single_node(self.current_node)
            # 刷新面板
            self.update_properties(self.current_node)

    def view_node_log(self):
        """显示节点日志"""
        if self.current_node and hasattr(self.parent(), 'show_node_log'):
            self.parent().show_node_log(self.current_node)


# ----------------------------
# 主窗口
# ----------------------------
class LowCodeWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)

        # 扫描组件
        self.component_map = scan_components()

        # 初始化日志存储
        self.node_logs = {}
        self.node_results = {}

        # 初始化 NodeGraph
        self.graph = NodeGraph()
        # 动态注册所有组件
        self.node_type_map = {}

        for full_path, comp_cls in self.component_map.items():
            safe_name = full_path.replace("/", "_").replace(" ", "_").replace("-", "_")
            node_class = create_node_class(comp_cls)
            node_class.__name__ = f"DynamicNode_{safe_name}"
            self.graph.register_node(node_class)
            self.node_type_map[full_path] = f"dynamic.{node_class.__name__}"

        self.canvas_widget = self.graph.viewer()

        # 组件面板
        self.nav_view = TreeWidget(self)
        self.nav_view.setHeaderHidden(True)
        self.nav_view.setFixedWidth(200)
        self.build_component_tree(self.component_map)

        # 属性面板
        self.property_panel = PropertyPanel()

        # 布局（移除日志面板）
        central_widget = QWidget()
        central_widget.setObjectName('central_widget')
        main_layout = QVBoxLayout(central_widget)
        canvas_layout = QHBoxLayout()
        canvas_layout.addWidget(self.nav_view)
        canvas_layout.addWidget(self.canvas_widget, 1)
        canvas_layout.addWidget(self.property_panel, 0, Qt.AlignRight)
        main_layout.addLayout(canvas_layout)
        self.addSubInterface(central_widget, FIF.APPLICATION, 'Canvas')

        # 创建悬浮按钮
        self.create_floating_buttons()

        # 信号连接
        scene = self.graph.viewer().scene()
        scene.selectionChanged.connect(self.on_selection_changed)

    def create_floating_buttons(self):
        """创建画布左上角的悬浮按钮"""
        button_container = QWidget(self.canvas_widget)
        button_container.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        button_container.move(10, 10)

        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(5)
        button_layout.setContentsMargins(0, 0, 0, 0)

        # 运行按钮
        self.run_btn = ToolButton(FIF.PLAY, self)
        self.run_btn.setToolTip("Run Workflow")
        self.run_btn.clicked.connect(self.run_workflow)
        button_layout.addWidget(self.run_btn)

        # 导出按钮
        self.export_btn = ToolButton(FIF.SAVE, self)
        self.export_btn.setToolTip("Export Workflow")
        self.export_btn.clicked.connect(self.save_graph)
        button_layout.addWidget(self.export_btn)

        # 导入按钮
        self.import_btn = ToolButton(FIF.FOLDER, self)
        self.import_btn.setToolTip("Import Workflow")
        self.import_btn.clicked.connect(self.load_graph)
        button_layout.addWidget(self.import_btn)

        button_container.setLayout(button_layout)
        button_container.show()

    def execute_node(self, node, upstream_outputs):
        """执行单个节点，返回输出"""
        # 获取组件类
        comp_cls = node.component_class
        comp_instance = comp_cls()

        # 参数
        params = {}
        for name in node.model.properties.keys():
            if name not in ['name', 'color', 'icon', 'pos', 'width', 'height']:
                params[name] = node.get_property(name)

        # 输入
        inputs = {}
        for input_port in node.input_ports():
            port_name = input_port.name()
            connected = input_port.connected_ports()
            if connected:
                upstream_out = connected[0]
                upstream_node = get_port_node(upstream_out)
                upstream_data = upstream_outputs.get(upstream_node.id, {})
                inputs[port_name] = upstream_data.get(upstream_out.name())
            else:
                inputs[port_name] = None

        # 执行（捕获stdout/stderr）
        log_capture = io.StringIO()
        try:
            with redirect_stdout(log_capture), redirect_stderr(log_capture):
                if comp_cls.get_inputs():
                    output = comp_instance.run(params, inputs)
                else:
                    output = comp_instance.run(params)
            # 获取捕获的日志
            captured_log = log_capture.getvalue()
            if captured_log:
                self.log_to_node(node, captured_log)
            return output
        finally:
            log_capture.close()

    def run_single_node(self, node):
        self.clear_node_log(node)
        self.log_to_node(node, f"▶ Running single node: {node.name()}\n")
        try:
            result = self.execute_node(node, self.node_results)
            self.node_results[node.id] = result
            self.log_to_node(node, f"✅ Result: {result}\n")
        except Exception as e:
            import traceback
            error_msg = f"❌ Error: {e}\n{traceback.format_exc()}"
            self.log_to_node(node, error_msg)

    def run_node_list(self, nodes):
        """执行节点列表（按顺序）"""
        node_outputs = {}
        for node in nodes:
            try:
                self.log_to_node(node, f"▶ Executing: {node.name()}\n")
                output = self.execute_node(node, node_outputs)
                node_outputs[node.id] = output
                self.node_results[node.id] = output
                self.log_to_node(node, f"  ✅ {output}\n")
            except Exception as e:
                import traceback
                error_msg = f"  ❌ {e}\n{traceback.format_exc()}"
                self.log_to_node(node, error_msg)
                return
        # 记录完成信息到第一个节点
        if nodes:
            self.log_to_node(nodes[0], "🎉 Batch execution completed.\n")

    # 日志辅助方法
    def clear_node_log(self, node):
        self.node_logs[node.id] = ""

    def log_to_node(self, node, msg):
        current = self.node_logs.get(node.id, "")
        self.node_logs[node.id] = current + msg

    def show_node_log(self, node):
        """显示节点日志在MessageBox中"""
        log = self.node_logs.get(node.id, "No log available.")
        w = MessageBox("Node Log", log, self)
        w.exec()

    def get_node_input(self, node, port_name):
        """获取节点某个输入端口的上游数据"""
        for input_port in node.input_ports():
            if input_port.name() == port_name:
                connected = input_port.connected_ports()
                if connected:
                    upstream_out = connected[0]
                    upstream_node = get_port_node(upstream_out)
                    return self.node_results.get(upstream_node.id, {}).get(upstream_out.name())
        return None

    def on_selection_changed(self):
        selected_nodes = self.graph.selected_nodes()
        if selected_nodes:
            self.on_node_selected(selected_nodes[0])
        else:
            self.property_panel.update_properties(None)

    def on_component_clicked(self, item, column):
        parent = item.parent()
        if parent is None:
            return

        category = parent.text(0)
        name = item.text(column)
        full_path = f"{category}/{name}"

        node_type = self.node_type_map.get(full_path)
        if not node_type:
            return

        try:
            node = self.graph.create_node(node_type)
            node.set_pos(300, 200)
        except Exception as e:
            print(f"❌ Failed to create node {node_type}: {e}")

    def on_node_selected(self, node):
        self.property_panel.update_properties(node)

    def save_graph(self):
        self.graph.save_session('workflow.json')
        print("Graph saved to workflow.json")

    def load_graph(self):
        try:
            self.graph.load_session('workflow.json')
            print("Graph loaded from workflow.json")
        except FileNotFoundError:
            print("workflow.json not found!")

    def build_component_tree(self, component_map):
        self.nav_view.clear()
        categories = {}

        for full_path, comp_cls in component_map.items():
            category, name = full_path.split("/", 1)
            if category not in categories:
                cat_item = QTreeWidgetItem([category])
                self.nav_view.addTopLevelItem(cat_item)
                categories[category] = cat_item
            else:
                cat_item = categories[category]
            cat_item.addChild(QTreeWidgetItem([name]))

        self.nav_view.expandAll()
        self.nav_view.itemClicked.connect(self.on_component_clicked)

    def run_workflow(self):
        nodes = self.graph.all_nodes()
        if not nodes:
            # 显示错误消息
            w = MessageBox("No Nodes", "⚠️ No nodes in workflow.", self)
            w.exec()
            return

        # 构建依赖图
        in_degree = {node: 0 for node in nodes}
        graph = defaultdict(list)

        for node in nodes:
            for input_port in node.input_ports():
                for upstream_out in input_port.connected_ports():
                    upstream = get_port_node(upstream_out)
                    graph[upstream].append(node)
                    in_degree[node] += 1

        # 拓扑排序
        queue = deque([n for n in nodes if in_degree[n] == 0])
        order = []
        while queue:
            n = queue.popleft()
            order.append(n)
            for neighbor in graph[n]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(nodes):
            w = MessageBox("Circular Dependency", "❌ Circular dependency detected!", self)
            w.exec()
            return

        self.run_node_list(order)


# ----------------------------
# 启动应用
# ----------------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LowCodeWindow()
    window.show()
    sys.exit(app.exec_())