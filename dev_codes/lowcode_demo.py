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

from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QTreeWidgetItem, QLabel
from PyQt5.QtCore import Qt, QMimeData, QTimer, QRectF
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QColor, QPen
from qfluentwidgets import (
    FluentWindow, TreeWidget,
    PrimaryPushButton, setTheme, Theme, FluentIcon as FIF, ToolButton, MessageBox, InfoBar, InfoBarPosition
)
from NodeGraphQt import NodeGraph, BaseNode
from NodeGraphQt.constants import NodePropWidgetEnum

# ----------------------------
# 节点运行状态枚举
# ----------------------------
NODE_STATUS_UNRUN = "unrun"      # 未运行
NODE_STATUS_RUNNING = "running"  # 运行中
NODE_STATUS_SUCCESS = "success"  # 运行成功
NODE_STATUS_FAILED = "failed"    # 运行失败

# 状态颜色映射
STATUS_COLORS = {
    NODE_STATUS_UNRUN: "#888888",
    NODE_STATUS_RUNNING: "#4A90E2",
    NODE_STATUS_SUCCESS: "#2ECC71",
    NODE_STATUS_FAILED: "#E74C3C"
}

# ----------------------------
# 属性面板（右侧）
# ----------------------------
from qfluentwidgets import CardWidget, BodyLabel, LineEdit, TextEdit


def get_port_node(port):
    """安全获取端口所属节点，兼容 property 和 method"""
    node = port.node
    return node() if callable(node) else node


from dev_codes.utils.json_serializer import json_serializable
from dev_codes.utils.create_dynamic_node import create_node_class
from dev_codes.scan_components import scan_components


class PropertyPanel(CardWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setFixedWidth(320)
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

        # 2. 操作按钮组
        self.vbox.addWidget(BodyLabel("Actions:"))

        # 运行该节点
        run_btn = PrimaryPushButton("▶ Run This Node", self)
        run_btn.clicked.connect(lambda: self.run_current_node())
        self.vbox.addWidget(run_btn)

        # 运行到此处
        run_to_btn = PrimaryPushButton("⏩ Run to This Node", self)
        run_to_btn.clicked.connect(lambda: self.run_to_current_node())
        self.vbox.addWidget(run_to_btn)

        # 从此处运行
        run_from_btn = PrimaryPushButton("⏭️ Run from This Node", self)
        run_from_btn.clicked.connect(lambda: self.run_from_current_node())
        self.vbox.addWidget(run_from_btn)

        # 删除节点
        delete_btn = PrimaryPushButton("🗑️ Delete Node", self)
        delete_btn.clicked.connect(lambda: self.delete_current_node())
        self.vbox.addWidget(delete_btn)

        # 3. 查看日志按钮
        log_btn = PrimaryPushButton("📄 View Node Log", self)
        log_btn.clicked.connect(lambda: self.view_node_log())
        self.vbox.addWidget(log_btn)

        # 4. 输入端口
        self.vbox.addWidget(BodyLabel("📥 Input Ports:"))
        for input_port in node.input_ports():
            port_name = input_port.name()
            upstream_data = self.get_upstream_data(node, port_name)
            value_str = json.dumps(json_serializable(upstream_data), indent=2, ensure_ascii=False) if upstream_data is not None else "No input"
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
                value_str = json.dumps(json_serializable(value), indent=2, ensure_ascii=False)
                self.vbox.addWidget(BodyLabel(f"  • {port_name}:"))
                text_edit = TextEdit()
                text_edit.setPlainText(value_str)
                text_edit.setReadOnly(True)
                text_edit.setMaximumHeight(80)
                self.vbox.addWidget(text_edit)
        else:
            self.vbox.addWidget(BodyLabel("  No output yet."))

    def get_upstream_data(self, node, port_name):
        return self.main_window.get_node_input(node, port_name)

    def get_node_result(self, node):
        return self.main_window.node_results.get(node.id, {})

    def run_current_node(self):
        if self.current_node:
            self.main_window.run_single_node(self.current_node)
            self.update_properties(self.current_node)

    def run_to_current_node(self):
        if self.current_node:
            self.main_window.run_to_node(self.current_node)
            self.update_properties(self.current_node)

    def run_from_current_node(self):
        if self.current_node:
            self.main_window.run_from_node(self.current_node)
            self.update_properties(self.current_node)

    def delete_current_node(self):
        if self.current_node:
            self.main_window.delete_node(self.current_node)
            self.main_window.property_panel.update_properties(None)

    def view_node_log(self):
        if self.current_node:
            self.main_window.show_node_log(self.current_node)


# ----------------------------
# 可拖拽的组件树（带预览）
# ----------------------------
class DraggableTreeWidget(TreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(False)
        self.setDragDropMode(TreeWidget.DragOnly)
        self.component_map = {}

    def set_component_map(self, component_map):
        """设置组件映射，用于拖拽预览"""
        self.component_map = component_map

    def startDrag(self, supportedActions):
        """开始拖拽操作，带预览"""
        item = self.currentItem()
        if item and item.parent():  # 确保是叶子节点（组件，不是分类）
            category = item.parent().text(0)
            name = item.text(0)
            full_path = f"{category}/{name}"

            # 创建拖拽对象
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(full_path)
            drag.setMimeData(mime_data)

            # 创建预览 pixmap
            preview = self.create_drag_preview(full_path)
            drag.setPixmap(preview)
            drag.setHotSpot(preview.rect().center())

            drag.exec_(Qt.CopyAction)

    def create_drag_preview(self, full_path):
        """创建拖拽预览 pixmap"""
        comp_cls = self.component_map.get(full_path)
        if not comp_cls:
            # 默认预览
            pixmap = QPixmap(120, 60)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setPen(QPen(QColor("#4A90E2"), 2))
            painter.drawRect(0, 0, 119, 59)
            painter.setPen(Qt.black)
            painter.drawText(QRectF(10, 20, 100, 20), Qt.AlignLeft, "Component")
            painter.end()
            return pixmap

        # 创建组件预览
        pixmap = QPixmap(150, 80)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)

        # 绘制节点背景
        painter.setPen(QPen(QColor("#4A90E2"), 2))
        painter.setBrush(QColor("#2D2D2D"))
        painter.drawRect(0, 0, 149, 79)

        # 绘制标题
        painter.setPen(Qt.white)
        painter.setFont(painter.font())
        painter.drawText(QRectF(10, 10, 130, 20), Qt.AlignLeft, comp_cls.name)

        # 绘制类别
        painter.setPen(QColor("#888888"))
        painter.drawText(QRectF(10, 35, 130, 15), Qt.AlignLeft, f"Category: {comp_cls.category}")

        # 绘制输入端口
        inputs = comp_cls.get_inputs()
        if inputs:
            painter.setPen(QColor("#2ECC71"))
            painter.drawText(QRectF(10, 55, 130, 15), Qt.AlignLeft, f"Inputs: {len(inputs)}")

        # 绘制输出端口
        outputs = comp_cls.get_outputs()
        if outputs:
            painter.setPen(QColor("#E74C3C"))
            painter.drawText(QRectF(10, 70, 130, 15), Qt.AlignLeft, f"Outputs: {len(outputs)}")

        painter.end()
        return pixmap


# ----------------------------
# 自定义节点类（支持状态显示）
# ----------------------------
class StatusNode(BaseNode):
    """支持状态显示的基节点类"""
    def __init__(self):
        super().__init__()
        self._status = NODE_STATUS_UNRUN
        self._status_pixmap = None
        self._update_status_pixmap()

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if value != self._status:
            self._status = value
            self._update_status_pixmap()
            self.view.update()

    def _update_status_pixmap(self):
        """更新状态 pixmap"""
        if self._status == NODE_STATUS_UNRUN:
            self._status_pixmap = None
            return

        # 创建状态指示器 pixmap
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)

        color = QColor(STATUS_COLORS.get(self._status, "#888888"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(0, 0, 15, 15)

        # 绘制状态图标
        if self._status == NODE_STATUS_RUNNING:
            painter.setPen(Qt.white)
            painter.setFont(painter.font())
            painter.drawText(4, 12, "...")
        elif self._status == NODE_STATUS_SUCCESS:
            painter.setPen(Qt.white)
            painter.drawText(4, 12, "✓")
        elif self._status == NODE_STATUS_FAILED:
            painter.setPen(Qt.white)
            painter.drawText(4, 12, "✗")

        painter.end()
        self._status_pixmap = pixmap

    def paint(self, painter, option, widget):
        """重写绘制方法，添加状态指示器"""
        super().paint(painter, option, widget)

        if self._status_pixmap:
            # 在节点右上角绘制状态指示器
            status_rect = self.boundingRect()
            painter.drawPixmap(
                status_rect.right() - 20,
                status_rect.top() + 5,
                self._status_pixmap
            )


# ----------------------------
# 主窗口
# ----------------------------
class LowCodeWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)
        from PyQt5.QtWidgets import QDesktopWidget
        screen_rect = QDesktopWidget().screenGeometry()
        screen_width, screen_height = screen_rect.width(), screen_rect.height()
        self.window_width = int(screen_width * 0.6)
        self.window_height = int(screen_height * 0.75)
        self.resize(self.window_width, self.window_height)

        # 扫描组件
        self.component_map = scan_components()

        # 初始化日志存储和状态
        self.node_logs = {}
        self.node_results = {}
        self.node_status = {}  # {node_id: status}

        # 初始化 NodeGraph
        self.graph = NodeGraph()
        # 动态注册所有组件
        self.node_type_map = {}

        for full_path, comp_cls in self.component_map.items():
            safe_name = full_path.replace("/", "_").replace(" ", "_").replace("-", "_")
            node_class = create_node_class(comp_cls)
            # 继承 StatusNode 以支持状态显示
            node_class = type(f"Status{node_class.__name__}", (StatusNode, node_class), {})
            node_class.__name__ = f"StatusDynamicNode_{safe_name}"
            self.graph.register_node(node_class)
            self.node_type_map[full_path] = f"dynamic.{node_class.__name__}"

        self.canvas_widget = self.graph.viewer()

        # 组件面板 - 使用可拖拽的树
        self.nav_view = DraggableTreeWidget(self)
        self.nav_view.setHeaderHidden(True)
        self.nav_view.setFixedWidth(200)
        self.nav_view.set_component_map(self.component_map)  # 设置组件映射用于预览
        self.build_component_tree(self.component_map)

        # 属性面板
        self.property_panel = PropertyPanel(self)

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
        self.navigationInterface.hide()  # 隐藏导航栏

        # 创建悬浮按钮
        self.create_floating_buttons()

        # 信号连接
        scene = self.graph.viewer().scene()
        scene.selectionChanged.connect(self.on_selection_changed)

        # 启用画布的拖拽放置
        self.canvas_widget.setAcceptDrops(True)
        self.canvas_widget.dragEnterEvent = self.canvas_drag_enter_event
        self.canvas_widget.dropEvent = self.canvas_drop_event

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

    def canvas_drag_enter_event(self, event):
        """画布拖拽进入事件"""
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def canvas_drop_event(self, event):
        """画布放置事件"""
        if event.mimeData().hasText():
            full_path = event.mimeData().text()
            node_type = self.node_type_map.get(full_path)
            if node_type:
                # 获取放置位置（相对于画布）
                pos = event.pos()
                # 转换为场景坐标
                scene_pos = self.canvas_widget.mapToScene(pos)
                # 创建节点
                node = self.graph.create_node(node_type)
                node.set_pos(scene_pos.x(), scene_pos.y())
                # 初始化状态
                self.node_status[node.id] = NODE_STATUS_UNRUN
                # 设置节点状态（用于视觉显示）
                if hasattr(node, 'status'):
                    node.status = NODE_STATUS_UNRUN
            event.accept()
        else:
            event.ignore()

    def get_node_status(self, node):
        """获取节点状态"""
        return self.node_status.get(node.id, NODE_STATUS_UNRUN)

    def set_node_status(self, node, status):
        """设置节点状态"""
        self.node_status[node.id] = status
        # 更新节点视觉状态
        if hasattr(node, 'status'):
            node.status = status
        # 如果当前选中的是这个节点，更新属性面板
        if (self.property_panel.current_node and
            self.property_panel.current_node.id == node.id):
            self.property_panel.update_properties(self.property_panel.current_node)

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
            return json_serializable(output)
        finally:
            log_capture.close()

    def run_single_node(self, node):
        """运行单个节点"""
        self.set_node_status(node, NODE_STATUS_RUNNING)
        self.clear_node_log(node)
        self.log_to_node(node, f"▶ Running single node: {node.name()}\n")

        try:
            result = self.execute_node(node, self.node_results)
            self.node_results[node.id] = result
            self.log_to_node(node, f"✅ Result: {result}\n")
            self.set_node_status(node, NODE_STATUS_SUCCESS)
            InfoBar.success(
                title='Success',
                content=f'Node "{node.name()}" executed successfully!',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )
        except Exception as e:
            import traceback
            error_msg = f"❌ Error: {e}\n{traceback.format_exc()}"
            self.log_to_node(node, error_msg)
            self.set_node_status(node, NODE_STATUS_FAILED)
            InfoBar.error(
                title='Error',
                content=f'Node "{node.name()}" execution failed!',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def run_node_list(self, nodes):
        """执行节点列表（按顺序）"""
        node_outputs = {}
        for node in nodes:
            self.set_node_status(node, NODE_STATUS_RUNNING)
            self.log_to_node(node, f"▶ Executing: {node.name()}\n")
            try:
                output = self.execute_node(node, node_outputs)
                node_outputs[node.id] = output
                self.node_results[node.id] = output
                self.log_to_node(node, f"  ✅ {output}\n")
                self.set_node_status(node, NODE_STATUS_SUCCESS)
            except Exception as e:
                import traceback
                error_msg = f"  ❌ {e}\n{traceback.format_exc()}"
                self.log_to_node(node, error_msg)
                self.set_node_status(node, NODE_STATUS_FAILED)
                return
        # 记录完成信息到第一个节点
        if nodes:
            self.log_to_node(nodes[0], "🎉 Batch execution completed.\n")

    def run_to_node(self, target_node):
        """运行到目标节点（包含所有上游节点）"""
        nodes_to_run = self.get_ancestors_and_self(target_node)
        self.run_node_list(nodes_to_run)

    def run_from_node(self, start_node):
        """从起始节点开始运行（包含所有下游节点）"""
        nodes_to_run = self.get_descendants_and_self(start_node)
        self.run_node_list(nodes_to_run)

    def get_ancestors_and_self(self, node):
        """获取 node 及其所有上游节点（拓扑顺序）"""
        visited = set()
        result = []

        def dfs(n):
            if n in visited:
                return
            visited.add(n)
            # 先处理上游
            for input_port in n.input_ports():
                for out_port in input_port.connected_ports():
                    upstream = get_port_node(out_port)
                    dfs(upstream)
            result.append(n)

        dfs(node)
        return result

    def get_descendants_and_self(self, node):
        """获取 node 及其所有下游节点（拓扑顺序）"""
        visited = set()
        result = []

        def dfs(n):
            if n in visited:
                return
            visited.add(n)
            result.append(n)
            # 处理下游
            for output_port in n.output_ports():
                for in_port in output_port.connected_ports():
                    downstream = get_port_node(in_port)
                    dfs(downstream)

        dfs(node)
        return result

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

    def on_node_selected(self, node):
        self.property_panel.update_properties(node)

    def delete_node(self, node):
        """删除节点"""
        if node:
            # 清理相关数据
            node_id = node.id
            if node_id in self.node_logs:
                del self.node_logs[node_id]
            if node_id in self.node_results:
                del self.node_results[node_id]
            if node_id in self.node_status:
                del self.node_status[node_id]

            # 删除节点
            self.graph.delete_node(node)

    def save_graph(self):
        self.graph.save_session('workflow.json')
        print("Graph saved to workflow.json")

    def load_graph(self):
        try:
            self.graph.load_session('workflow.json')
            print("Graph loaded from workflow.json")
            # 重新初始化所有节点状态
            self.node_status = {}
            for node in self.graph.all_nodes():
                self.node_status[node.id] = NODE_STATUS_UNRUN
                if hasattr(node, 'status'):
                    node.status = NODE_STATUS_UNRUN
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