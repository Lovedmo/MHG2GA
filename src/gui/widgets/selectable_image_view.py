"""可框选图像查看器：支持在截图上拖拽矩形选区、设置点击点标记、缩放平移。"""

from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap, QPen, QColor, QBrush, QWheelEvent
from PyQt6.QtWidgets import QWidget


class SelectableImageView(QWidget):
    """显示截图并支持拖拽矩形框选和点击点标记。

    支持三种交互模式 (通过 set_mode 切换):
        "select"  — 左键拖拽框选矩形区域 (默认)
        "click"   — 左键点击设置点击点标记
        "view"    — 仅查看，左键无操作

    所有模式下: 中键拖拽平移, 滚轮缩放
    """

    selection_changed = pyqtSignal(QRect)
    click_point_changed = pyqtSignal(int, int)
    coordinate_hover = pyqtSignal(int, int)

    _SEL_COLOR = QColor(137, 180, 250, 100)
    _SEL_BORDER = QColor(137, 180, 250, 220)
    _MASK_COLOR = QColor(0, 0, 0, 120)
    _CLICK_COLOR = QColor(243, 139, 168)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._original_size: tuple[int, int] = (0, 0)

        self._selection: QRect | None = None
        self._dragging = False
        self._drag_start = QPoint()

        self._click_point: QPoint | None = None
        self._mode = "select"

        self._scale = 1.0
        self._offset = QPoint(0, 0)
        self._panning = False
        self._pan_start = QPoint()
        self._pan_offset_start = QPoint()

        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setStyleSheet("background-color: #11111b;")

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def set_image(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._original_size = (pixmap.width(), pixmap.height())
        self._selection = None
        self._click_point = None
        self._fit_to_view()
        self.update()

    def get_selection(self) -> QRect | None:
        return QRect(self._selection) if self._selection else None

    def clear_selection(self) -> None:
        self._selection = None
        self.update()

    def get_click_point(self) -> QPoint | None:
        return QPoint(self._click_point) if self._click_point else None

    def set_click_point(self, x: int, y: int) -> None:
        self._click_point = QPoint(x, y)
        self.update()

    def clear_click_point(self) -> None:
        self._click_point = None
        self.update()

    def get_original_size(self) -> tuple[int, int]:
        return self._original_size

    def _fit_to_view(self) -> None:
        if not self._pixmap:
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        vw, vh = self.width(), self.height()
        sx = vw / pw
        sy = vh / ph
        self._scale = min(sx, sy) * 0.95
        self._offset = QPoint(
            int((vw - pw * self._scale) / 2),
            int((vh - ph * self._scale) / 2),
        )

    def _img_to_view(self, x: float, y: float) -> QPoint:
        return QPoint(
            int(x * self._scale + self._offset.x()),
            int(y * self._scale + self._offset.y()),
        )

    def _view_to_img(self, pos: QPoint) -> QPoint:
        ix = (pos.x() - self._offset.x()) / self._scale
        iy = (pos.y() - self._offset.y()) / self._scale
        return QPoint(int(ix), int(iy))

    def _clamp_to_image(self, p: QPoint) -> QPoint:
        if not self._pixmap:
            return p
        x = max(0, min(p.x(), self._pixmap.width()))
        y = max(0, min(p.y(), self._pixmap.height()))
        return QPoint(x, y)

    # ---- Paint ----

    def paintEvent(self, event) -> None:
        if not self._pixmap:
            painter = QPainter(self)
            painter.setPen(QColor("#585b70"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "载入截图后可在此框选模板区域")
            painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        pw, ph = self._pixmap.width(), self._pixmap.height()
        dst = QRectF(
            self._offset.x(), self._offset.y(),
            pw * self._scale, ph * self._scale,
        )
        painter.drawPixmap(dst.toRect(), self._pixmap)

        if self._selection and self._selection.width() > 0 and self._selection.height() > 0:
            sel = self._selection
            tl = self._img_to_view(sel.x(), sel.y())
            br = self._img_to_view(sel.x() + sel.width(), sel.y() + sel.height())
            sel_view = QRect(tl, br)

            painter.setBrush(QBrush(self._MASK_COLOR))
            painter.setPen(Qt.PenStyle.NoPen)
            img_rect = dst.toRect()
            painter.drawRect(QRect(img_rect.x(), img_rect.y(), img_rect.width(), sel_view.y() - img_rect.y()))
            painter.drawRect(QRect(img_rect.x(), sel_view.y(), sel_view.x() - img_rect.x(), sel_view.height()))
            painter.drawRect(QRect(sel_view.right(), sel_view.y(), img_rect.right() - sel_view.right(), sel_view.height()))
            painter.drawRect(QRect(img_rect.x(), sel_view.bottom(), img_rect.width(), img_rect.bottom() - sel_view.bottom()))

            painter.setBrush(QBrush(self._SEL_COLOR))
            painter.setPen(QPen(self._SEL_BORDER, 2, Qt.PenStyle.DashLine))
            painter.drawRect(sel_view)

            painter.setPen(QPen(QColor("#cdd6f4"), 1))
            painter.setFont(self.font())
            label = f"{sel.width()}×{sel.height()}"
            label_pos = QPoint(sel_view.x() + 4, sel_view.y() - 6)
            if label_pos.y() < img_rect.y() + 14:
                label_pos = QPoint(sel_view.x() + 4, sel_view.y() + 16)
            painter.drawText(label_pos, label)

        if self._click_point:
            cp = self._click_point
            vp = self._img_to_view(cp.x(), cp.y())

            painter.setPen(QPen(self._CLICK_COLOR, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(vp, 10, 10)

            painter.setPen(QPen(self._CLICK_COLOR, 2))
            painter.drawLine(vp.x() - 14, vp.y(), vp.x() + 14, vp.y())
            painter.drawLine(vp.x(), vp.y() - 14, vp.x(), vp.y() + 14)

            painter.setPen(QPen(QColor("#cdd6f4"), 1))
            painter.drawText(vp.x() + 16, vp.y() - 4,
                             f"点击点 ({cp.x()}, {cp.y()})")

        painter.end()

    # ---- Mouse events ----

    def mousePressEvent(self, event) -> None:
        if not self._pixmap:
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self._pan_offset_start = QPoint(self._offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            img_pos = self._clamp_to_image(self._view_to_img(event.pos()))

            if self._mode == "click":
                self._click_point = img_pos
                self.click_point_changed.emit(img_pos.x(), img_pos.y())
                self.update()
                return

            if self._mode == "select":
                self._drag_start = img_pos
                self._dragging = True
                self._selection = QRect(img_pos, img_pos)
                self.update()

    def mouseMoveEvent(self, event) -> None:
        if not self._pixmap:
            return

        if self._panning:
            delta = event.pos() - self._pan_start
            self._offset = self._pan_offset_start + delta
            self.update()
            return

        img_pos = self._clamp_to_image(self._view_to_img(event.pos()))
        self.coordinate_hover.emit(img_pos.x(), img_pos.y())

        if self._dragging:
            x1 = min(self._drag_start.x(), img_pos.x())
            y1 = min(self._drag_start.y(), img_pos.y())
            x2 = max(self._drag_start.x(), img_pos.x())
            y2 = max(self._drag_start.y(), img_pos.y())
            self._selection = QRect(x1, y1, x2 - x1, y2 - y1)
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.CrossCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            if self._selection and self._selection.width() > 2 and self._selection.height() > 2:
                self.selection_changed.emit(QRect(self._selection))
            else:
                self._selection = None
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._pixmap:
            return
        mouse_pos = event.position().toPoint()
        img_before = self._view_to_img(mouse_pos)

        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_scale = self._scale * factor
        new_scale = max(0.1, min(new_scale, 10.0))
        self._scale = new_scale

        new_view = self._img_to_view(img_before.x(), img_before.y())
        self._offset += mouse_pos - new_view
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._pixmap and not self._selection:
            self._fit_to_view()
