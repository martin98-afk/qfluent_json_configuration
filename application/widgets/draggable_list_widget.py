"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: draggable_list_widget.py
@time: 2025/7/2 17:39
@desc: 
"""
from PyQt5.QtWidgets import QListWidget, QAbstractItemView, QStyle, QProxyStyle
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from PyQt5.QtCore import Qt

class CustomDropIndicatorStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget):
        if element == QStyle.PE_IndicatorItemViewItemDrop and option:
            painter.save()
            rect = option.rect
            is_insert_between = rect.height() <= 2
            if is_insert_between:
                pen = QPen(QColor("#0078D7"))
                pen.setWidth(4)
                painter.setPen(pen)
                painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            else:
                pen = QPen(QColor("#00AAFF"))
                pen.setStyle(Qt.DashLine)
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
            painter.restore()
        else:
            super().drawPrimitive(element, option, painter, widget)


class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(True)
        self.setStyle(CustomDropIndicatorStyle())

        # 设置字体大小
        font = QFont()
        font.setPointSize(18)
        self.setFont(font)

        # 设置样式，避免悬浮时字体颜色变白
        self.setStyleSheet("""
            QListWidget {
                background-color: white;
                color: #212529;
            }
            QListWidget::item:hover {
                background-color: #e9ecef;
                color: #212529;
            }
            QListWidget::item:selected {
                background-color: #339af0;
                color: white;
            }
        """)