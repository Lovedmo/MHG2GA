from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QWidget


class StatusIndicator(QWidget):
    """圆形状态指示灯组件。"""

    COLOR_MAP = {
        "connected": QColor("#a6e3a1"),
        "disconnected": QColor("#585b70"),
        "detected": QColor("#585b70"),
        "stopped": QColor("#45475a"),
        "connecting": QColor("#f9e2af"),
        "error": QColor("#f38ba8"),
    }

    def __init__(self, status: str = "disconnected", size: int = 12, parent=None):
        super().__init__(parent)
        self._status = status
        self._size = size
        self.setFixedSize(size, size)

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        self._status = value
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.COLOR_MAP.get(self._status, self.COLOR_MAP["disconnected"])
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(1, 1, self._size - 2, self._size - 2)
        painter.end()
