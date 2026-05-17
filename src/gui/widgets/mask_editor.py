"""蒙版编辑器：在模板图片上涂抹蒙版，标记匹配/忽略区域。

白色区域 = 参与匹配
黑色区域 = 忽略（背景）

操作:
    左键拖拽 — 橡皮擦（涂黑，标记为忽略）
    右键拖拽 — 画笔（涂白，恢复为参与匹配）
    滚轮     — 调整笔刷大小
"""

import numpy as np

from PyQt6.QtCore import Qt, QPoint, QRectF
from PyQt6.QtGui import (
    QPainter, QPixmap, QImage, QPen, QColor,
    QBrush, QWheelEvent, QPainterPath,
)
from PyQt6.QtWidgets import QWidget


class MaskEditor(QWidget):
    """在模板图片上编辑蒙版的控件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._mask: np.ndarray | None = None
        self._mask_pixmap: QPixmap | None = None

        self._brush_size = 12
        self._painting = False
        self._erase_mode = True

        self._scale = 1.0
        self._offset = QPoint(0, 0)
        self._panning = False
        self._pan_start = QPoint()
        self._pan_offset_start = QPoint()

        self.setMinimumSize(300, 200)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setStyleSheet("background-color: #11111b;")

    def set_image_and_mask(self, image: np.ndarray, mask: np.ndarray | None = None) -> None:
        """设置模板图片和初始蒙版。image: BGR, mask: 灰度单通道。"""
        h, w = image.shape[:2]
        rgb = image[:, :, ::-1].copy()
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)

        if mask is not None and mask.shape[:2] == (h, w):
            self._mask = mask.copy()
        else:
            self._mask = np.full((h, w), 255, dtype=np.uint8)

        self._update_mask_pixmap()
        self._fit_to_view()
        self.update()

    def get_mask(self) -> np.ndarray | None:
        return self._mask.copy() if self._mask is not None else None

    def fill_all(self) -> None:
        """全部设为参与匹配（白色）。"""
        if self._mask is not None:
            self._mask[:] = 255
            self._update_mask_pixmap()
            self.update()

    def clear_all(self) -> None:
        """全部设为忽略（黑色）。"""
        if self._mask is not None:
            self._mask[:] = 0
            self._update_mask_pixmap()
            self.update()

    def invert(self) -> None:
        """反转蒙版。"""
        if self._mask is not None:
            self._mask = 255 - self._mask
            self._update_mask_pixmap()
            self.update()

    def set_brush_size(self, size: int) -> None:
        self._brush_size = max(2, min(size, 100))

    def _update_mask_pixmap(self) -> None:
        if self._mask is None:
            return
        h, w = self._mask.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        ignored = self._mask < 128
        rgba[ignored] = [255, 50, 50, 140]
        qimg = QImage(rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        self._mask_pixmap = QPixmap.fromImage(qimg)

    def _fit_to_view(self) -> None:
        if not self._pixmap:
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        vw, vh = self.width(), self.height()
        self._scale = min(vw / pw, vh / ph) * 0.95
        self._offset = QPoint(
            int((vw - pw * self._scale) / 2),
            int((vh - ph * self._scale) / 2),
        )

    def _view_to_img(self, pos: QPoint) -> QPoint:
        ix = (pos.x() - self._offset.x()) / self._scale
        iy = (pos.y() - self._offset.y()) / self._scale
        return QPoint(int(ix), int(iy))

    def _img_to_view(self, x: float, y: float) -> QPoint:
        return QPoint(
            int(x * self._scale + self._offset.x()),
            int(y * self._scale + self._offset.y()),
        )

    def _paint_mask(self, img_pos: QPoint, value: int) -> None:
        if self._mask is None:
            return
        h, w = self._mask.shape
        x, y = img_pos.x(), img_pos.y()
        r = self._brush_size // 2
        y1, y2 = max(0, y - r), min(h, y + r + 1)
        x1, x2 = max(0, x - r), min(w, x + r + 1)
        yy, xx = np.ogrid[y1:y2, x1:x2]
        circle = (xx - x) ** 2 + (yy - y) ** 2 <= r ** 2
        self._mask[y1:y2, x1:x2][circle] = value
        self._update_mask_pixmap()

    # ---- Paint ----

    def paintEvent(self, event) -> None:
        if not self._pixmap:
            painter = QPainter(self)
            painter.setPen(QColor("#585b70"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "载入模板图片")
            painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        pw, ph = self._pixmap.width(), self._pixmap.height()
        dst = QRectF(self._offset.x(), self._offset.y(),
                     pw * self._scale, ph * self._scale)

        checker_size = 8
        for cy in range(int(dst.y()), int(dst.y() + dst.height()), checker_size):
            for cx in range(int(dst.x()), int(dst.x() + dst.width()), checker_size):
                row = (cy - int(dst.y())) // checker_size
                col = (cx - int(dst.x())) // checker_size
                color = QColor(40, 40, 50) if (row + col) % 2 == 0 else QColor(50, 50, 60)
                painter.fillRect(cx, cy, checker_size, checker_size, color)

        painter.drawPixmap(dst.toRect(), self._pixmap)

        if self._mask_pixmap:
            painter.drawPixmap(dst.toRect(), self._mask_pixmap)

        mouse_pos = self.mapFromGlobal(self.cursor().pos())
        if self.rect().contains(mouse_pos):
            view_r = self._brush_size * self._scale / 2
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(mouse_pos, int(view_r), int(view_r))

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

        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self._painting = True
            self._erase_mode = event.button() == Qt.MouseButton.LeftButton
            img_pos = self._view_to_img(event.pos())
            value = 0 if self._erase_mode else 255
            self._paint_mask(img_pos, value)
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if not self._pixmap:
            return

        if self._panning:
            delta = event.pos() - self._pan_start
            self._offset = self._pan_offset_start + delta
            self.update()
            return

        if self._painting:
            img_pos = self._view_to_img(event.pos())
            value = 0 if self._erase_mode else 255
            self._paint_mask(img_pos, value)

        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self._painting = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._pixmap:
            return

        mods = event.modifiers()
        delta = event.angleDelta().y()

        if mods & Qt.KeyboardModifier.ControlModifier:
            mouse_pos = event.position().toPoint()
            img_before = self._view_to_img(mouse_pos)
            factor = 1.15 if delta > 0 else 1 / 1.15
            self._scale = max(0.5, min(self._scale * factor, 20.0))
            new_view = self._img_to_view(img_before.x(), img_before.y())
            self._offset += mouse_pos - new_view
        else:
            step = 2 if delta > 0 else -2
            self._brush_size = max(2, min(self._brush_size + step, 100))

        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._pixmap:
            self._fit_to_view()
