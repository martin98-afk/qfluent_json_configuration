import json
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRectF
from PyQt5.QtGui import QColor, QFont, QCursor
from PyQt5.QtWidgets import QGraphicsItem
from loguru import logger
from qfluentwidgets import CommandBarView, Action, FluentIcon, Flyout, FlyoutAnimationType

from application.interfaces.service_test_dialog import JSONServiceTester
from application.widgets.persistent_tooltip import PersistentToolTip

# 启用 OpenGL 硬件加速与抗锯齿
# pg.setConfigOptions(useOpenGL=True, antialias=True)


class PixelAlignedLinearRegionItem(pg.LinearRegionItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 开启设备坐标缓存
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

    def boundingRect(self):
        r = super().boundingRect()
        # 缩紧到整数像素范围
        return QRectF(round(r.x()), round(r.y()), round(r.width()), round(r.height()))

    def paint(self, p, *args):
        # 使用重载后的 boundingRect 作为裁剪
        p.setClipRect(self.boundingRect())
        super().paint(p, *args)

    def setRegion(self, region):
        self.prepareGeometryChange()
        super().setRegion(region)


class TrendPlotWidget(pg.PlotWidget):
    range_selected = pyqtSignal(datetime, datetime)
    selection_started = pyqtSignal()

    def __init__(self, legend: bool = True, **kwargs):
        super().__init__()
        self.kwargs = kwargs
        # 状态与缓存
        self.tooltip_widget = PersistentToolTip(self)
        self.tooltip_timer = QTimer(self, interval=200)
        self.tooltip_timer.timeout.connect(self._on_tooltip_timer)
        self._last_ts = None
        self._tooltip_active = False
        vb = self.plotItem.vb
        vb.setAutoPan(x=False, y=False)

        # ---- 新增：独立 Y 轴相关 ----
        self.independent_y = False  # False = 共享y轴；True = 每条曲线独立 y 轴
        self.extra_vbs = []  # 存放为每条曲线创建的 ViewBox
        self.right_axes = []  # 对应右侧 AxisItem 列表

        # 基础绘图
        self.setBackground('w')
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setMouseEnabled(x=True, y=False)
        if legend:
            self.addLegend(offset=(1, 1))

        # 时间轴（不变）
        axis = pg.DateAxisItem(orientation='bottom')
        axis.setStyle(tickTextOffset=10, tickFont=QFont("Microsoft YaHei", 9))
        axis.setTickSpacing(major=3600 * 6, minor=3600)
        self.setAxisItems({'bottom': axis})

        # 区域选择（不变）
        self.region = pg.LinearRegionItem(brush=(0, 200, 0, 100), pen=QColor(0, 200, 0))
        self.region.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.region.setZValue(1000)
        self.region.hide()
        self.plotItem.vb.addItem(self.region)

        # 十字光标（主 viewbox 上）
        self.crosshair = pg.InfiniteLine(
            angle=90,
            pen=pg.mkPen(QColor('#999999'), width=1, style=Qt.DashLine)
        )
        self.crosshair.setZValue(1001)
        self.crosshair.hide()
        self.plotItem.vb.addItem(self.crosshair)

        # 曲线存储
        self.curves = []
        # 清除其它项（保持你的原逻辑）
        for item in self.items():
            if not isinstance(item, pg.AxisItem) and not isinstance(item, pg.GridItem):
                self.removeItem(item)

        # 交互绑定
        self.scene().sigMouseMoved.connect(self._on_mouse_move)

        # 初始视野
        self._init_xrange = None
        self._init_yrange = None

        # 区域选择状态
        self._is_selecting = False
        self._select_start = None

        self._right_axis_spacing = 70  # 多个右轴之间的水平间距（像素）
        self._right_axis_width = 58  # 每个右轴的宽度（像素）

        def update_views():
            # 让额外的 viewbox 与主 viewbox 对齐
            vb_rect = self.plotItem.vb.sceneBoundingRect()
            for vb_extra in self.extra_vbs:
                vb_extra.setGeometry(vb_rect)
                vb_extra.linkedViewChanged(self.plotItem.vb, vb_extra.XAxis)

            # 手动布局右侧多个 AxisItem，避免堆叠到右上角
            for j, ax in enumerate(self.right_axes):
                x = vb_rect.right() + j * self._right_axis_spacing
                ax.setGeometry(QRectF(x, vb_rect.top(), self._right_axis_width, vb_rect.height()))

        self._update_views = update_views
        self.plotItem.vb.sigResized.connect(self._update_views)
        self.plotItem.vb.setZValue(100)

    def set_independent_y(self, enable: bool):
        """切换是否为每条曲线独立 Y 轴，并在切换后重绘已有数据（如果有）"""
        enable = bool(enable)
        if enable == bool(self.independent_y):
            return
        self.independent_y = enable

        # 清理已有的额外 viewboxes / axes
        for vb in list(self.extra_vbs):
            try:
                # 移除 viewbox
                self.plotItem.scene().removeItem(vb)
            except Exception:
                pass
        self.extra_vbs.clear()

        for ax in list(self.right_axes):
            try:
                self.plotItem.layout.removeItem(ax)
                self.plotItem.scene().removeItem(ax)
            except Exception:
                pass
        self.right_axes.clear()

        # 如果切回共享 y ，显示主左轴刻度；否则隐藏主左轴刻度
        self.plotItem.getAxis('left').setStyle(showValues=not self.independent_y)

        # 如果之前画过曲线，则重新绘制，使新模式生效
        if getattr(self, "_last_data", None) is not None:
            # 注意：plot_multiple 内部也会读取 self.independent_y 来决定绘制方式
            self.plot_multiple(self._last_data, self._last_mode)

    def wheelEvent(self, ev):
        vb = self.plotItem.vb
        # 平滑的缩放因子
        factor = 0.92 if ev.angleDelta().y() > 0 else 1.08
        mp = vb.mapSceneToView(ev.pos())
        # 应用缩放，仅在x轴方向
        vb.scaleBy((factor, 1.0), center=(mp.x(), mp.y()))
        ev.accept()

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.autoRange()
            ev.accept()
        else:
            super().mouseDoubleClickEvent(ev)

    def plot_multiple(self, data, mode: str = "line"):
        # 保存以便后续切换模式时重绘
        self._last_data = data
        self._last_mode = mode
        # 先清除旧曲线（主 plotItem / 额外 viewboxes 中都清理）
        for c in self.curves:
            try:
                # 可能 curve 在主 plotItem 或者在某个 vb 中
                parent = c.getViewBox() if hasattr(c, 'getViewBox') else None
                if parent is not None:
                    parent.removeItem(c)
                else:
                    self.plotItem.removeItem(c)
            except Exception:
                try:
                    self.plotItem.removeItem(c)
                except Exception:
                    pass
        self.curves.clear()

        # === 清空 legend ===
        if hasattr(self.plotItem, 'legend') and self.plotItem.legend is not None:
            try:
                # 1. 移除 legend 中的所有曲线项
                for sample, label in list(self.plotItem.legend.items):
                    self.plotItem.legend.removeItem(label.text)
                # 2. 移除 legend 控件
                self.plotItem.removeItem(self.plotItem.legend)
            except Exception:
                pass
            self.plotItem.legend = None

        # === 如果需要 legend，重新创建 ===
        if self.kwargs.get("legend", True):
            self.plotItem.addLegend(offset=(1, 1))

        # 如果之前存在额外 viewboxes/axes，需要清理（例如从独立切回共享之前）
        if not self.independent_y and (self.extra_vbs or self.right_axes):
            self.set_independent_y(False)  # 清理所有额外控件

        all_y = []
        x = None

        if not self.independent_y:
            # 共享 y 轴：与原来逻辑一致
            for i, (tag, points) in enumerate(data.items()):
                if not points:
                    continue
                x, y = points
                hue = i / max(1, len(data))
                qcolor = QColor.fromHsvF(hue, 0.7, 0.9)
                color_str = qcolor.name()
                if mode == "fill":
                    curve = pg.PlotDataItem(
                        x=x, y=y,
                        pen=pg.mkPen(color_str, width=2),
                        name=tag,
                        **{
                            "fillLevel": min(y),
                            "fillBrush": pg.mkBrush(QColor(color_str).lighter(180))
                        }
                    )
                elif mode == "line":
                    curve = pg.PlotDataItem(x=x, y=y, pen=pg.mkPen(color_str, width=2), name=tag, symbol=None)
                elif mode == "scatter":
                    curve = pg.ScatterPlotItem(
                        x=x, y=y,
                        pen=pg.mkPen(color_str, width=2),
                        name=tag,
                        **{"symbol": "o", "brush": pg.mkBrush(color_str), "size": 5}
                    )
                else:
                    logger.error(f"Invalid mode: {mode}")
                    raise ValueError

                if mode != "scatter":
                    curve.setDownsampling(auto=True, method='peak')
                    curve.setClipToView(True)
                curve.setZValue(0)
                self.plotItem.addItem(curve)
                self.curves.append(curve)
                all_y.append(np.array(y))

            # X 范围与 Y 范围
            if x is not None:
                self.plotItem.setXRange(x[0] - 2500, x[-1] + 1000, padding=0)

            if all_y:
                arr = np.hstack(all_y)
                mn, mx = arr.min(), arr.max()
                pad = (mx - mn) * 0.1 if mx != mn else 1.0
                self.plotItem.vb.setYRange(mn - pad, mx + pad, padding=0)
        else:
            # 独立 y 轴模式：为每条曲线创建独立 ViewBox + 独立右侧 AxisItem
            self.plotItem.getAxis('left').setStyle(showValues=False)  # 隐藏主左轴刻度

            # 清理旧 viewbox / 右轴
            for vb in self.extra_vbs:
                try:
                    self.plotItem.scene().removeItem(vb)
                except Exception:
                    pass
            self.extra_vbs.clear()
            for ax in self.right_axes:
                try:
                    self.plotItem.scene().removeItem(ax)
                except Exception:
                    pass
            self.right_axes.clear()
            # 获取主 viewbox 几何，用于定位右轴
            vb_rect = self.plotItem.vb.sceneBoundingRect()
            num_curves = len(data)
            right_axis_spacing = 70  # 每条右轴水平间隔像素
            for i, (tag, points) in enumerate(data.items()):
                if not points:
                    continue
                x, y = points
                hue = i / max(1, num_curves)
                qcolor = QColor.fromHsvF(hue, 0.7, 0.9)
                color_str = qcolor.name()

                # 创建独立 ViewBox
                vb_extra = pg.ViewBox(enableMouse=False)  # 这里先禁用
                vb_extra.setXLink(self.plotItem.vb)  # X 轴同步
                vb_extra.setMouseEnabled(x=False, y=False)  # 禁止额外 viewbox 处理拖拽
                vb_extra.setAcceptHoverEvents(False)  # 禁止悬停事件
                vb_extra.setAcceptedMouseButtons(Qt.NoButton)  # 不接收鼠标点击
                vb_extra.setZValue(-10)
                self.plotItem.scene().addItem(vb_extra)
                self.extra_vbs.append(vb_extra)

                # 创建右侧 Y 轴
                axis = pg.AxisItem('right')
                axis.setLabel(tag, color=color_str)  # 这里可以直接用 color
                axis.setStyle(
                    tickFont=QFont("Microsoft YaHei", 9),
                    tickTextOffset=5
                )
                # 颜色不要放在 setStyle 里，用专用 API：
                axis.setPen(pg.mkPen(color_str))  # 刻度线和轴线的颜色
                axis.setTextPen(pg.mkPen(color_str))  # 刻度文字颜色

                axis.linkToView(vb_extra)
                axis.setZValue(1000)
                self.plotItem.scene().addItem(axis)
                self.right_axes.append(axis)

                # 动态设置右轴的位置
                axis.setPos(vb_rect.right() + i * right_axis_spacing, vb_rect.top())

                # 添加曲线到该 viewbox
                if mode == "fill":
                    curve = pg.PlotDataItem(
                        x=x, y=y, pen=pg.mkPen(color_str, width=2), name=tag,
                        fillLevel=min(y),
                        fillBrush=pg.mkBrush(QColor(color_str).lighter(180))
                    )
                elif mode == "line":
                    curve = pg.PlotDataItem(
                        x=x, y=y, pen=pg.mkPen(color_str, width=2), name=tag
                    )
                elif mode == "scatter":
                    curve = pg.ScatterPlotItem(
                        x=x, y=y,
                        pen=pg.mkPen(color_str, width=2),
                        name=tag,
                        symbol="o",
                        brush=pg.mkBrush(color_str),
                        size=5
                    )
                else:
                    logger.error(f"Invalid mode: {mode}")
                    raise ValueError

                if mode != "scatter":
                    curve.setDownsampling(auto=True, method='peak')
                    curve.setClipToView(True)

                if self.plotItem.legend is None:
                    self.plotItem.addLegend(offset=(1, 1))
                self.plotItem.legend.addItem(curve, tag)

                vb_extra.addItem(curve)
                self.curves.append(curve)

                # 设置 y 范围
                mn, mx = np.min(y), np.max(y)
                pad = (mx - mn) * 0.1 if mx != mn else 1.0
                vb_extra.setYRange(mn - pad, mx + pad, padding=0)

            # X 范围由主 plotItem 控制
            if x is not None:
                self.plotItem.setXRange(x[0] - 2500, x[-1] + 1000, padding=0)
            # 同步几何
            self._update_views()

        # 确保 region 与 crosshair 在最上层
        self.region.setZValue(1000)
        self.crosshair.setZValue(1001)

    def _on_mouse_move(self, pos):
        mp = self.plotItem.vb.mapSceneToView(pos)
        if not self.viewRect().contains(mp):
            self.crosshair.hide()
            self._stop_tooltip()
            return
        self.crosshair.setPos(mp.x())
        self.crosshair.show()
        self._start_tooltip(mp.x())

    def _start_tooltip(self, ts):
        if ts < 0:
            return
        if self._last_ts is not None and abs(ts - self._last_ts) < 0.5:
            return
        self._last_ts = ts
        if not self._tooltip_active:
            self._tooltip_active = True
            self.tooltip_timer.start()
        self._update_tooltip()

    def _on_tooltip_timer(self):
        if self._tooltip_active:
            self._update_tooltip()
        else:
            self.tooltip_timer.stop()

    def _update_tooltip(self):
        try:
            ts = self._last_ts
            if ts is None:
                return

            tstr = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            lines = [
                f"<div style='font-size:13px; font-weight:bold; margin-bottom:8px;'>🕒 {tstr}</div>",
                "<div style='height:6px;'></div>",  # 垂直间距
                "<table style='border-collapse:collapse; font-size:12px;'>",
            ]

            for curve in self.curves:
                x, y = curve.getData()
                if x is None or len(x) == 0:
                    continue
                idx = np.searchsorted(x, ts)
                idx = min(max(idx, 0), len(x) - 1)
                if abs(x[idx - 1] - ts) < abs(x[idx] - ts):
                    idx -= 1
                if abs(x[idx] - ts) <= 1200:
                    color = curve.opts["pen"].color().name()
                    value_str = f"{y[idx]:.2f}"
                    # 可在此加单位，如 "°C"
                    lines.append(
                        f"""
                        <tr style="line-height: 1.2;">
                            <td style="padding-right:6px;">
                                <span style="color:{color}; font-size:14px;">&#9679;</span>
                            </td>
                            <td style="padding-right:6px; color:#444;">{curve.name()}</td>
                            <td style="font-weight:bold; color:#222;">{value_str}</td>
                        </tr>
                        """
                    )

            lines.append("</table>")
            self.tooltip_widget.show_tooltip("".join(lines))
        except Exception as e:
            logger.error(f"工具提示更新错误: {e}")

    def _stop_tooltip(self):
        self._tooltip_active = False
        self.tooltip_timer.stop()
        self.tooltip_widget.hide()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton and self.kwargs.get("show_service", True):
            self._show_copy_dialog(ev.pos())
            return

        if not self._is_selecting or ev.button() != Qt.LeftButton:
            return super().mousePressEvent(ev)

        # —— 正确映射 —— #
        # 1) widget -> scene
        scenePos = self.mapToScene(ev.pos())
        # 2) scene -> view/data
        x = self.plotItem.vb.mapSceneToView(scenePos).x()

        if self._select_start is None:
            self._select_start = x
            self.region.setRegion([x, x])
            self.region.show()
            self.selection_started.emit()
        else:
            s, e = sorted([self._select_start, x])
            self._select_start = None
            self.region.setRegion([s, e])
            dt0, dt1 = datetime.fromtimestamp(s), datetime.fromtimestamp(e)
            # 出现menu用来确认是否添加该段区域
            commandBar = CommandBarView()
            # 关键修改：使用鼠标位置作为目标位置
            # 获取当前鼠标位置
            mouse_pos = QCursor.pos()
            flyout = Flyout.make(commandBar, target=mouse_pos, parent=self, aniType=FlyoutAnimationType.FADE_IN)
            commandBar.addAction(
                Action(FluentIcon.ACCEPT, '确认', triggered=lambda: [
                    self.kwargs.get("home")._add_current_region(),
                    flyout.close()
                ]))
            commandBar.addAction(
                Action(FluentIcon.CLOSE, '取消', triggered=lambda: [
                    self.region.hide(),
                    flyout.close()
                ])
            )
            commandBar.resizeToSuitableWidth()
            flyout.show()
            self.range_selected.emit(dt0, dt1)

    def mouseMoveEvent(self, ev):
        if self._is_selecting and self._select_start is not None:
            # 同样的两步映射
            scenePos = self.mapToScene(ev.pos())
            cur = self.plotItem.vb.mapSceneToView(scenePos).x()
            self.region.setRegion([self._select_start, cur])
        super().mouseMoveEvent(ev)

    def enable_selection(self):
        self._is_selecting = True
        self.setCursor(Qt.CrossCursor)

    def disable_selection(self):
        self._is_selecting = False
        self._select_start = None
        self.region.hide()
        self.setCursor(Qt.ArrowCursor)

    def enterEvent(self, ev):
        self._tooltip_active = True
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._stop_tooltip()
        super().leaveEvent(ev)

    def clear_all(self):
        for c in self.curves:
            self.plotItem.removeItem(c)
        self.curves.clear()
        # self._last_indices.clear()

    def showEvent(self, ev):
        super().showEvent(ev)
        # 强制触发重新绘制，激活 GL 上下文
        self.plotItem.vb.update()

    def _show_copy_dialog(self, pos):
        vb = self.plotItem.vb
        mp = vb.mapSceneToView(self.mapToScene(pos))
        ts = mp.x()

        res = {}
        for curve in self.curves:
            x, y = curve.getData()
            if len(x) == 0:
                continue
            idx = int(np.abs(np.array(x) - ts).argmin())
            res[curve.name()] = float(y[idx])

        if res:
            json_str = json.dumps({"data": res}, ensure_ascii=False)
            self.kwargs.get("home").service_test.set_current_text(json_str)
            self.kwargs.get("home").switchTo(self.kwargs.get("home").service_test)

    def autoRangeEnabled(self):
        """补丁：代理到内部的 ViewBox.autoRangeEnabled()"""
        return self.plotItem.vb.autoRangeEnabled()
