from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox,
    QSpinBox,
)


class TouchConfigTab(QWidget):
    """触控配置页：方式选择 + 点击/滑动/按键测试。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        method_group = QGroupBox("触控设置")
        method_layout = QGridLayout(method_group)
        method_layout.setSpacing(8)

        method_layout.addWidget(QLabel("触控方式:"), 0, 0)
        self._touch_method = QComboBox()
        self._touch_method.addItems(["ADBTOUCH", "MINITOUCH", "MAXTOUCH"])
        self._touch_method.setToolTip(
            "ADBTOUCH — 兼容性最好，无需额外配置，延迟较高（50-100ms/次）\n"
            "MINITOUCH — 延迟最低（10-30ms/次），支持多点触控，推荐优先尝试\n"
            "MAXTOUCH — MINITOUCH 的增强版，兼容 Android 10+，性能与 MINITOUCH 相当"
        )
        method_layout.addWidget(self._touch_method, 0, 1)

        method_layout.addWidget(QLabel("操作延迟:"), 1, 0)
        self._action_delay = QSpinBox()
        self._action_delay.setRange(0, 5000)
        self._action_delay.setValue(100)
        self._action_delay.setSingleStep(50)
        self._action_delay.setSuffix(" ms")
        self._action_delay.setToolTip("每次触控操作后的等待时间，防止操作过快导致游戏未响应")
        method_layout.addWidget(self._action_delay, 1, 1)

        layout.addWidget(method_group)

        tap_group = QGroupBox("点击测试")
        tap_layout = QGridLayout(tap_group)
        tap_layout.setSpacing(8)

        tap_layout.addWidget(QLabel("X 坐标:"), 0, 0)
        self._tap_x = QSpinBox()
        self._tap_x.setRange(0, 9999)
        self._tap_x.setValue(512)
        tap_layout.addWidget(self._tap_x, 0, 1)

        tap_layout.addWidget(QLabel("Y 坐标:"), 0, 2)
        self._tap_y = QSpinBox()
        self._tap_y.setRange(0, 9999)
        self._tap_y.setValue(384)
        tap_layout.addWidget(self._tap_y, 0, 3)

        self._tap_btn = QPushButton("执行点击")
        self._tap_btn.setProperty("role", "primary")
        tap_layout.addWidget(self._tap_btn, 0, 4)

        layout.addWidget(tap_group)

        swipe_group = QGroupBox("滑动测试")
        swipe_layout = QGridLayout(swipe_group)
        swipe_layout.setSpacing(8)

        swipe_layout.addWidget(QLabel("起点 X:"), 0, 0)
        self._swipe_x1 = QSpinBox()
        self._swipe_x1.setRange(0, 9999)
        self._swipe_x1.setValue(768)
        swipe_layout.addWidget(self._swipe_x1, 0, 1)

        swipe_layout.addWidget(QLabel("起点 Y:"), 0, 2)
        self._swipe_y1 = QSpinBox()
        self._swipe_y1.setRange(0, 9999)
        self._swipe_y1.setValue(384)
        swipe_layout.addWidget(self._swipe_y1, 0, 3)

        swipe_layout.addWidget(QLabel("终点 X:"), 1, 0)
        self._swipe_x2 = QSpinBox()
        self._swipe_x2.setRange(0, 9999)
        self._swipe_x2.setValue(256)
        swipe_layout.addWidget(self._swipe_x2, 1, 1)

        swipe_layout.addWidget(QLabel("终点 Y:"), 1, 2)
        self._swipe_y2 = QSpinBox()
        self._swipe_y2.setRange(0, 9999)
        self._swipe_y2.setValue(384)
        swipe_layout.addWidget(self._swipe_y2, 1, 3)

        swipe_layout.addWidget(QLabel("持续时间:"), 2, 0)
        self._swipe_duration = QSpinBox()
        self._swipe_duration.setRange(100, 5000)
        self._swipe_duration.setValue(500)
        self._swipe_duration.setSuffix(" ms")
        swipe_layout.addWidget(self._swipe_duration, 2, 1)

        self._swipe_btn = QPushButton("执行滑动")
        self._swipe_btn.setProperty("role", "primary")
        swipe_layout.addWidget(self._swipe_btn, 2, 3, 1, 2)

        layout.addWidget(swipe_group)

        key_group = QGroupBox("按键测试")
        key_layout = QHBoxLayout(key_group)
        key_layout.setSpacing(8)

        key_layout.addWidget(QLabel("按键:"))
        self._key_combo = QComboBox()
        self._key_combo.addItems([
            "HOME", "BACK", "MENU", "POWER",
            "VOLUME_UP", "VOLUME_DOWN",
            "ENTER", "TAB", "ESCAPE",
        ])
        key_layout.addWidget(self._key_combo, stretch=1)

        self._key_btn = QPushButton("执行按键")
        self._key_btn.setProperty("role", "primary")
        key_layout.addWidget(self._key_btn)

        layout.addWidget(key_group)

        result_group = QGroupBox("测试结果")
        result_layout = QVBoxLayout(result_group)
        self._result_label = QLabel("点击上方按钮执行测试操作")
        self._result_label.setStyleSheet("color: #a6adc8; padding: 4px;")
        self._result_label.setWordWrap(True)
        result_layout.addWidget(self._result_label)
        layout.addWidget(result_group)

        layout.addStretch()

    def get_config(self) -> dict:
        return {
            "touch_method": self._touch_method.currentText(),
            "action_delay": self._action_delay.value(),
        }

    def set_config(self, config: dict) -> None:
        if "touch_method" in config:
            idx = self._touch_method.findText(config["touch_method"])
            if idx >= 0:
                self._touch_method.setCurrentIndex(idx)
        if "action_delay" in config:
            self._action_delay.setValue(config["action_delay"])

    def set_result(self, text: str) -> None:
        self._result_label.setText(text)

    def get_tap_params(self) -> tuple[int, int]:
        return self._tap_x.value(), self._tap_y.value()

    def get_swipe_params(self) -> tuple[int, int, int, int, int]:
        return (
            self._swipe_x1.value(), self._swipe_y1.value(),
            self._swipe_x2.value(), self._swipe_y2.value(),
            self._swipe_duration.value(),
        )

    def get_key_param(self) -> str:
        return self._key_combo.currentText()
