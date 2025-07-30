from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QSlider, QDoubleSpinBox, QHBoxLayout, QPushButton
)

from application.utils.utils import get_icon


class NoWheelQSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class SliderEditor(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, minimum=0.0, maximum=100.0, decimal_point=1, initial=0.0, parent=None):
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._decimal_point = decimal_point
        self._factor = 10 ** decimal_point

        # Style sheet remains unchanged
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: white;
                height: 10px;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #66e, stop: 1 #bbf);
                background: qlineargradient(x1: 0, y1: 0.2, x2: 1, y2: 1,
                    stop: 0 #1890ff, stop: 1 #73d13d);
                border: 1px solid #777;
                height: 10px;
                border-radius: 4px;
            }
            QSlider::add-page:horizontal {
                background: #fff;
                border: 1px solid #777;
                height: 10px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #eee, stop:1 #ccc);
                border: 1px solid #777;
                width: 16px;
                margin-top: -3px;
                margin-bottom: -3px;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fff, stop:1 #ddd);
                border: 1px solid #444;
                border-radius: 8px;
            }
        """)

        # Layout setup
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 使用自定义的 NoWheelDoubleSpinBox 替代 QDoubleSpinBox
        self.spin = QDoubleSpinBox(self)
        self.spin.wheelEvent = lambda e: None
        self.spin.setRange(self._min, self._max)
        self.spin.setDecimals(self._decimal_point)
        self.spin.setSingleStep(1.0 / self._factor)
        self.spin.setFixedWidth(80)
        # 设置字体大小（关键修改）
        self.spin.setFont(QFont("微软雅黑", 14))  # 字体类型 + 大小
        self.spin.setStyleSheet("font-size: 14pt; padding: 0px 6px; ")  # 更精确的样式控制

        self.slider = NoWheelQSlider(Qt.Horizontal, self)
        self.slider.setRange(int(self._min * self._factor), int(self._max * self._factor))
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(max(1, (int(self._max * self._factor) - int(self._min * self._factor)) // 10))
        self.slider.setTracking(True)

        self.setValue(initial)

        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spin.valueChanged.connect(self._on_spin_changed)

        # Confirm button (勾号)
        layout.addWidget(self.spin)
        layout.addWidget(self.slider, stretch=1)

    def _on_slider_changed(self, value):
        float_value = value / self._factor
        if self.spin.value() != float_value:
            self.spin.setValue(float_value)
        self.valueChanged.emit(float_value)

    def _on_spin_changed(self, value):
        int_value = round(value * self._factor)
        if self.slider.value() != int_value:
            self.slider.setValue(int_value)
        self.valueChanged.emit(value)

    def _on_confirm_clicked(self):
        self.confirmStateChanged.emit(self.spin.value())

    def value(self):
        return self.spin.value()

    def setValue(self, value):
        value = max(self._min, min(self._max, float(value)))
        int_value = round(value * self._factor)
        self.slider.setValue(int_value)
        self.spin.setValue(value)

    def setRange(self, minimum, maximum):
        self._min = minimum
        self._max = maximum
        self.slider.setRange(int(minimum * self._factor), int(maximum * self._factor))
        self.spin.setRange(minimum, maximum)