from collections import deque
from PyQt5.QtGui import QTextCharFormat, QColor, QTextCursor, QFont
from PyQt5.QtWidgets import QPlainTextEdit
from loguru import logger

from PyQt5.QtCore import QObject, pyqtSignal, QMetaObject, Qt, Q_ARG
from collections import deque
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor
import logging


class QTextEditLogger(QObject):
    """线程安全的日志记录器，专为Qt应用设计"""

    # 信号用于跨线程传递日志
    log_signal = pyqtSignal(str, str)  # (level, message)

    def __init__(self, text_edit, max_lines=1000):
        super().__init__()
        self.text_edit = text_edit
        self.buffer = deque(maxlen=max_lines)

        # 级别对应颜色
        self.colors = {
            "DEBUG": QColor("#00BFFF"),
            "INFO": QColor("#00FF7F"),
            "WARNING": QColor("#FFD700"),
            "ERROR": QColor("#FF4500"),
            "CRITICAL": QColor("#FF1493"),
        }

        # 连接信号到安全处理槽
        self.log_signal.connect(self._safe_append_line, Qt.QueuedConnection)

    def write(self, message):
        """安全写入日志（可被任何线程调用）"""
        text = message.strip()
        if not text:
            return

        # 提取日志级别（兼容标准logging格式）
        level = "INFO"
        for lvl in self.colors:
            if f"| {lvl} |" in text:
                level = lvl
                break

        # 缓存到内存
        self.buffer.append((level, text))

        # 通过信号安全传递到主线程
        self.log_signal.emit(level, text)

    def _safe_append_line(self, level: str, line: str):
        """主线程执行的日志追加（安全防护版）"""
        # 1. 检查UI对象是否有效
        if not self._is_widget_valid():
            return

        # 2. 检查日志级别有效性
        color = self.colors.get(level, QColor("#FFFFFF"))

        # 3. 创建格式化对象
        fmt = QTextCharFormat()
        fmt.setForeground(color)

        # 4. 安全获取游标（双重检查）
        cursor = self._safe_text_cursor()
        if not cursor:
            return

        # 5. 安全插入文本
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(line + "\n", fmt)

        # 6. 安全设置游标
        self._safe_set_cursor(cursor)

    def _is_widget_valid(self) -> bool:
        """检查文本编辑控件是否有效"""
        if not hasattr(self, 'text_edit') or self.text_edit is None:
            return False
        try:
            # 尝试访问基本属性验证
            self.text_edit.isVisible()
            return True
        except RuntimeError as e:
            if "underlying C/C++ object has been deleted" in str(e):
                return False
            logging.error(f"Widget validation error: {e}")
            return False

    def _safe_text_cursor(self) -> QTextCursor:
        """安全获取文本游标"""
        if not self._is_widget_valid():
            return None
        try:
            return self.text_edit.textCursor()
        except RuntimeError:
            return None

    def _safe_set_cursor(self, cursor: QTextCursor):
        """安全设置文本游标"""
        if not self._is_widget_valid() or not cursor:
            return

        try:
            # 1. 确保在主线程执行
            QMetaObject.invokeMethod(
                self.text_edit,
                "setTextCursor",
                Qt.QueuedConnection,
                Q_ARG(QTextCursor, cursor)
            )
            # 2. 确保可见
            QMetaObject.invokeMethod(
                self.text_edit,
                "ensureCursorVisible",
                Qt.QueuedConnection
            )
        except RuntimeError:
            pass  # 安静忽略销毁对象的错误

    def flush(self):
        """标准流接口"""
        pass

    def close(self):
        """安全关闭（清理资源）"""
        self.log_signal.disconnect()
        self.text_edit = None
        self.buffer.clear()

# class QTextEditLogger:
#     def __init__(self, text_edit, max_lines=1000):
#         self.text_edit = text_edit
#         # 缓存最后 max_lines 条日志
#         self.buffer = deque(maxlen=max_lines)
#         # 级别对应颜色
#         self.colors = {
#             "DEBUG": QColor("#00BFFF"),
#             "INFO": QColor("#00FF7F"),
#             "WARNING": QColor("#FFD700"),
#             "ERROR": QColor("#FF4500"),
#             "CRITICAL": QColor("#FF1493"),
#         }
#
#     def write(self, message):
#         text = message.strip()
#         if not text:
#             return
#         # 先缓存
#         self.buffer.append(text)
#
#         # 如果当前视图可见，就立即输出（实时 + 历史都是同一窗口）
#         self._append_line(text)
#
#     def _append_line(self, line):
#         # 找到日志级别
#         lvl = None
#         for k in self.colors:
#             if f"| {k} |" in line:
#                 lvl = k
#                 break
#         fmt = QTextCharFormat()
#         fmt.setForeground(self.colors.get(lvl, QColor("#FFFFFF")))
#
#         cursor = self.text_edit.textCursor()
#         cursor.movePosition(QTextCursor.End)
#         cursor.insertText(line + "\n", fmt)
#         self.text_edit.setTextCursor(cursor)
#         self.text_edit.ensureCursorVisible()
#
#     def flush(self):
#         pass
