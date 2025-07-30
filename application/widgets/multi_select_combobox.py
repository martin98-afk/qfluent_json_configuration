from PyQt5.QtCore import pyqtSignal, Qt, QPoint, QEvent, QPropertyAnimation, QRect
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QApplication, QAbstractItemView, QFrame, QLabel, QPushButton, QSizePolicy, QScrollArea
)


class TagLabel(QFrame):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: 1px solid #1890ff;
                border-radius: 4px;
                max-height: 24px;
            }
            QLabel {
                border: none;
                padding-left: 4px;
                padding-right: 2px;
                font-size: 9pt;
            }
            QPushButton {
                border: none;
                color: black;
                background-color: transparent;
                font-size: 9pt;
                padding-left: 0px;
                padding-right: 2px;
            }
            QPushButton:hover {
                color: red;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)
        label = QLabel(text)
        self.close_btn = QPushButton("×")
        layout.addWidget(label)
        layout.addWidget(self.close_btn)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)


class FancyMultiSelectComboBox(QWidget):
    selectionChanged = pyqtSignal()

    def __init__(self, options, parent=None):
        super().__init__()
        self.editor = parent
        self.options = options
        self.selected = []  # 使用列表保持顺序
        self._init_ui()
        self.dropdown_expanded = False

    def _init_ui(self):
        self.setMinimumHeight(30)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.setAlignment(Qt.AlignVCenter)  # 控件整体居中对齐

        self.display_frame = QFrame()
        self.display_frame.setFixedHeight(30)
        self.display_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ccc;
                border-radius: 10px;
                background-color: transparent;
            }
        """)
        self.display_frame.setCursor(Qt.PointingHandCursor)
        self.display_layout = QHBoxLayout(self.display_frame)
        self.display_layout.setContentsMargins(0, 0, 0, 0)  # 增加左侧和上下边距
        self.display_layout.setSpacing(6)  # 每个tag间距更大
        self.display_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; }")

        self.tag_container = QWidget()
        self.tag_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        self.tag_layout = QHBoxLayout(self.tag_container)
        self.tag_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_layout.setSpacing(6)  # tag 间距加大
        self.tag_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.tag_container.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

        scroll_area.setWidget(self.tag_container)
        self.display_layout.addWidget(scroll_area)
        self.main_layout.addWidget(self.display_frame)

        self.dropdown = QListWidget()
        self.dropdown.setWindowFlags(Qt.Popup)
        self.dropdown.setSelectionMode(QAbstractItemView.MultiSelection)
        self.dropdown.setStyleSheet("""
            QListWidget {
                font-size: 10pt;
                background-color: white;
                border: 1px solid #1890ff;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #e6f7ff;
                color: #1890ff;
            }
        """)
        for opt in self.options:
            item = QListWidgetItem(opt)
            self.dropdown.addItem(item)

        self.dropdown.itemClicked.connect(self.update_selection)

        self.display_frame.mousePressEvent = self.toggle_dropdown
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, source, event):
        if event.type() == QEvent.MouseButtonPress:
            if self.dropdown.isVisible() and not self.dropdown.geometry().contains(event.globalPos()):
                self.dropdown.hide()
        return super().eventFilter(source, event)

    def update_selection(self):
        selected_set = {item.text() for item in self.dropdown.selectedItems()}
        old_selected = set(self.selected)

        # 添加新选项保持原顺序
        for i in range(self.dropdown.count()):
            text = self.dropdown.item(i).text()
            if text in selected_set and text not in old_selected:
                self.selected.append(text)
        # 删除未选中项
        self.selected = [s for s in self.selected if s in selected_set]

        self.update_tags()
        self.selectionChanged.emit()

    def update_tags(self):
        for i in reversed(range(self.tag_layout.count())):
            w = self.tag_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        for item in self.selected:
            tag = TagLabel(item)
            tag.close_btn.clicked.connect(lambda _, t=item: self.remove_item(t))
            self.tag_layout.addWidget(tag)

    def remove_item(self, item_text):
        if item_text in self.selected:
            self.selected.remove(item_text)
        for i in range(self.dropdown.count()):
            item = self.dropdown.item(i)
            if item.text() == item_text:
                item.setSelected(False)
        self.update_tags()
        self.selectionChanged.emit()

    def set_selected_items(self, items):
        self.selected = [i for i in items if i in self.options]
        for i in range(self.dropdown.count()):
            item = self.dropdown.item(i)
            item.setSelected(item.text() in self.selected)
        self.update_tags()

    def get_selected_items(self):
        return list(self.selected)

    def toggle_dropdown(self, event):
        if self.dropdown_expanded:
            # 收起动画
            anim = QPropertyAnimation(self.dropdown, b"geometry")
            anim.setDuration(200)
            start_rect = self.dropdown.geometry()
            end_rect = QRect(start_rect.x(), start_rect.y(), start_rect.width(), 0)
            anim.setStartValue(start_rect)
            anim.setEndValue(end_rect)
            anim.finished.connect(self.dropdown.hide)
            anim.finished.connect(lambda: setattr(self, 'dropdown_expanded', False))
            anim.start()
            self._slide_anim = anim
        else:
            # 展开动画
            target_height = 150
            global_pos = self.mapToGlobal(self.display_frame.pos()) + QPoint(0, self.display_frame.height())
            self.dropdown.setGeometry(global_pos.x(), global_pos.y(), self.width(), 0)
            self.dropdown.show()
            end_rect = QRect(global_pos.x(), global_pos.y(), self.width(), target_height)
            anim = QPropertyAnimation(self.dropdown, b"geometry")
            anim.setDuration(200)
            anim.setStartValue(self.dropdown.geometry())
            anim.setEndValue(end_rect)
            anim.finished.connect(lambda: setattr(self, 'dropdown_expanded', True))
            anim.start()
            self._slide_anim = anim