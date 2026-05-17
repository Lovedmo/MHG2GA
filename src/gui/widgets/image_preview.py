from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel


class ImagePreview(QLabel):
    """截图预览组件，支持等比缩放显示和鼠标坐标拾取。"""

    coordinate_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._original_size: tuple[int, int] = (0, 0)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 150)
        self.setStyleSheet("background-color: #11111b; border: 1px solid #313244; border-radius: 4px;")
        self.setText("暂无截图")

    def update_image(self, image) -> None:
        """更新预览图。接受 QPixmap 或文件路径 str。"""
        if image is None:
            self._pixmap = None
            self.setText("暂无截图")
            return

        if isinstance(image, QPixmap):
            self._pixmap = image
            self._original_size = (image.width(), image.height())
        elif isinstance(image, str):
            pixmap = QPixmap(image)
            if pixmap.isNull():
                self._pixmap = None
                self.setText("加载失败")
                return
            self._pixmap = pixmap
            self._original_size = (pixmap.width(), pixmap.height())
        else:
            self._pixmap = None
            self.setText("不支持的图像格式")
            return

        self._rescale()

    def update_from_file(self, filepath: str) -> None:
        """从文件加载预览图。"""
        pixmap = QPixmap(filepath)
        if pixmap.isNull():
            self._pixmap = None
            self.setText("加载失败")
            return
        self._pixmap = pixmap
        self._original_size = (pixmap.width(), pixmap.height())
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def mousePressEvent(self, event) -> None:
        if self._pixmap is None or self.pixmap() is None:
            return

        displayed = self.pixmap()
        if displayed is None:
            return

        offset_x = (self.width() - displayed.width()) // 2
        offset_y = (self.height() - displayed.height()) // 2

        click_x = event.position().x() - offset_x
        click_y = event.position().y() - offset_y

        if 0 <= click_x < displayed.width() and 0 <= click_y < displayed.height():
            orig_w, orig_h = self._original_size
            real_x = int(click_x * orig_w / displayed.width())
            real_y = int(click_y * orig_h / displayed.height())
            self.coordinate_clicked.emit(real_x, real_y)
