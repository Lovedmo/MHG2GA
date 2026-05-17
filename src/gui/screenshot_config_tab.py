from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QSlider,
)

from src.gui.widgets.image_preview import ImagePreview


class ScreenshotConfigTab(QWidget):
    """截图与识别配置页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(10)

        cap_group = QGroupBox("截图设置")
        cap_layout = QGridLayout(cap_group)
        cap_layout.setSpacing(8)

        cap_layout.addWidget(QLabel("截图方式:"), 0, 0)
        self._cap_method = QComboBox()
        self._cap_method.addItems(["ADBCAP", "MINICAP", "JAVACAP"])
        self._cap_method.setToolTip(
            "ADBCAP — 兼容性最好，无需额外配置，速度较慢（300-800ms/帧）\n"
            "MINICAP — 性能最佳（50-150ms/帧），需要设备支持，推荐优先尝试\n"
            "JAVACAP — 兼容性好，速度中等（200-500ms/帧），部分设备上比 ADBCAP 快"
        )
        cap_layout.addWidget(self._cap_method, 0, 1)

        cap_layout.addWidget(QLabel("截图间隔:"), 1, 0)
        self._cap_interval = QDoubleSpinBox()
        self._cap_interval.setRange(0.3, 5.0)
        self._cap_interval.setValue(0.5)
        self._cap_interval.setSingleStep(0.1)
        self._cap_interval.setSuffix(" 秒")
        self._cap_interval.setToolTip("两次截图之间的最小等待时间，值越小检测越灵敏但 CPU 占用越高")
        cap_layout.addWidget(self._cap_interval, 1, 1)

        left.addWidget(cap_group)

        match_group = QGroupBox("模板匹配")
        match_layout = QGridLayout(match_group)
        match_layout.setSpacing(8)

        threshold_label = QLabel("匹配阈值:")
        threshold_label.setToolTip(
            "模板匹配的相似度阈值，范围 0.50 - 1.00\n"
            "值越高匹配越严格（不容易误识别但可能漏识别）\n"
            "推荐 0.80，动态背景场景可降至 0.70"
        )
        match_layout.addWidget(threshold_label, 0, 0)
        threshold_row = QHBoxLayout()
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(50, 100)
        self._threshold_slider.setValue(80)
        self._threshold_slider.setTickInterval(5)
        self._threshold_label = QLabel("0.80")
        self._threshold_label.setFixedWidth(40)
        self._threshold_slider.valueChanged.connect(
            lambda v: self._threshold_label.setText(f"{v / 100:.2f}")
        )
        threshold_row.addWidget(self._threshold_slider)
        threshold_row.addWidget(self._threshold_label)
        match_layout.addLayout(threshold_row, 0, 1)

        match_layout.addWidget(QLabel("设备分辨率:"), 1, 0)
        self._device_res_label = QLabel("未连接")
        self._device_res_label.setStyleSheet("color: #a6adc8;")
        self._device_res_label.setToolTip(
            "截图和模板匹配均使用模拟器当前实际分辨率\n"
            "模板图片需在相同分辨率下截取才能正确匹配\n"
            "连接设备后自动获取"
        )
        match_layout.addWidget(self._device_res_label, 1, 1)

        left.addWidget(match_group)

        test_group = QGroupBox("截图测试")
        test_layout = QVBoxLayout(test_group)
        test_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("截图测试")
        self._test_btn.setProperty("role", "primary")
        btn_row.addWidget(self._test_btn)

        self._perf_btn = QPushButton("性能基准 (5轮)")
        btn_row.addWidget(self._perf_btn)
        test_layout.addLayout(btn_row)

        self._test_result = QLabel("点击上方按钮开始测试")
        self._test_result.setStyleSheet("color: #a6adc8; padding: 4px;")
        self._test_result.setWordWrap(True)
        test_layout.addWidget(self._test_result)

        left.addWidget(test_group)
        left.addStretch()
        layout.addLayout(left, stretch=2)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(QLabel("截图预览"))

        self._preview = ImagePreview()
        right.addWidget(self._preview, stretch=1)

        self._preview_info = QLabel("尺寸: -- | 耗时: --")
        self._preview_info.setStyleSheet("color: #a6adc8; font-size: 11px;")
        right.addWidget(self._preview_info)

        layout.addLayout(right, stretch=3)

    def get_config(self) -> dict:
        return {
            "cap_method": self._cap_method.currentText(),
            "cap_interval": self._cap_interval.value(),
            "threshold": self._threshold_slider.value() / 100.0,
        }

    def set_config(self, config: dict) -> None:
        if "cap_method" in config:
            idx = self._cap_method.findText(config["cap_method"])
            if idx >= 0:
                self._cap_method.setCurrentIndex(idx)
        if "cap_interval" in config:
            self._cap_interval.setValue(config["cap_interval"])
        if "threshold" in config:
            self._threshold_slider.setValue(int(config["threshold"] * 100))

    def set_test_result(self, text: str) -> None:
        self._test_result.setText(text)

    def set_preview_info(self, text: str) -> None:
        self._preview_info.setText(text)

    def set_device_resolution(self, width: int, height: int) -> None:
        """设置当前设备实际分辨率。"""
        if width > 0 and height > 0:
            self._device_res_label.setText(f"{width} × {height}")
            self._device_res_label.setStyleSheet("color: #a6e3a1;")
        else:
            self._device_res_label.setText("未连接")
            self._device_res_label.setStyleSheet("color: #a6adc8;")

    def update_preview(self, image) -> None:
        self._preview.update_image(image)

