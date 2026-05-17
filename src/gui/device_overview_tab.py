from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QSpinBox, QCheckBox,
    QListWidget, QListWidgetItem, QLineEdit, QAbstractItemView,
    QScrollArea, QFrame,
)

from src.gui.widgets.image_preview import ImagePreview


class DeviceOverviewTab(QWidget):
    """设备概览页：设备信息 + 实时截图预览 + 快捷操作。"""

    preview_requested = pyqtSignal()
    refresh_packages_requested = pyqtSignal(bool)
    lock_app_requested = pyqtSignal(str)
    launch_app_requested = pyqtSignal(str)
    check_alive_requested = pyqtSignal()
    keepalive_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device_info: dict = {}
        self._all_packages: list[str] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(280)
        scroll.setMaximumWidth(420)

        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.setSpacing(8)
        left.setContentsMargins(0, 0, 4, 0)

        # ---- 设备信息 ----
        info_group = QGroupBox("设备信息")
        info_grid = QGridLayout(info_group)
        info_grid.setSpacing(4)
        info_grid.setContentsMargins(8, 12, 8, 8)

        self._info_labels: dict[str, QLabel] = {}
        fields = [
            ("地址", "address"),
            ("型号", "model"),
            ("别名", "alias"),
            ("分辨率", "resolution"),
            ("屏幕方向", "orientation"),
            ("DPI", "dpi"),
            ("Android 版本", "android_version"),
            ("SDK 版本", "sdk_version"),
            ("CPU 架构", "cpu_abi"),
            ("前台应用", "foreground_app"),
        ]
        for row, (label_text, key) in enumerate(fields):
            key_label = QLabel(f"{label_text}:")
            key_label.setProperty("role", "info-key")
            key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label = QLabel("--")
            value_label.setProperty("role", "info-value")
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            info_grid.addWidget(key_label, row, 0)
            info_grid.addWidget(value_label, row, 1)
            self._info_labels[key] = value_label

        left.addWidget(info_group)

        # ---- 快捷操作 ----
        action_group = QGroupBox("快捷操作")
        action_layout = QGridLayout(action_group)
        action_layout.setSpacing(4)
        action_layout.setContentsMargins(8, 12, 8, 8)

        self._connect_btn = QPushButton("连接")
        self._connect_btn.setProperty("role", "primary")
        action_layout.addWidget(self._connect_btn, 0, 0)

        self._disconnect_btn = QPushButton("断开")
        self._disconnect_btn.setProperty("role", "danger")
        action_layout.addWidget(self._disconnect_btn, 0, 1)

        self._home_btn = QPushButton("HOME")
        action_layout.addWidget(self._home_btn, 1, 0)

        self._back_btn = QPushButton("BACK")
        action_layout.addWidget(self._back_btn, 1, 1)

        self._save_screenshot_btn = QPushButton("保存截图")
        action_layout.addWidget(self._save_screenshot_btn, 2, 0, 1, 2)

        left.addWidget(action_group)

        # ---- 运行状态 ----
        status_group = QGroupBox("运行状态")
        status_layout = QGridLayout(status_group)
        status_layout.setSpacing(4)
        status_layout.setContentsMargins(8, 12, 8, 8)
        self._status_label = QLabel("空闲")
        self._status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        status_layout.addWidget(QLabel("当前状态:"), 0, 0)
        status_layout.addWidget(self._status_label, 0, 1)
        self._duration_label = QLabel("--")
        status_layout.addWidget(QLabel("运行时长:"), 1, 0)
        status_layout.addWidget(self._duration_label, 1, 1)
        left.addWidget(status_group)

        # ---- 应用列表 ----
        app_group = QGroupBox("应用列表")
        app_layout = QVBoxLayout(app_group)
        app_layout.setSpacing(4)
        app_layout.setContentsMargins(8, 12, 8, 8)

        app_top = QHBoxLayout()
        app_top.setSpacing(4)
        self._refresh_packages_btn = QPushButton("获取列表")
        self._refresh_packages_btn.setProperty("role", "primary")
        self._refresh_packages_btn.clicked.connect(
            lambda: self.refresh_packages_requested.emit(self._third_party_cb.isChecked())
        )
        app_top.addWidget(self._refresh_packages_btn)
        self._third_party_cb = QCheckBox("仅第三方")
        self._third_party_cb.setChecked(True)
        app_top.addWidget(self._third_party_cb)
        app_layout.addLayout(app_top)

        self._pkg_search = QLineEdit()
        self._pkg_search.setPlaceholderText("搜索包名...")
        self._pkg_search.textChanged.connect(self._filter_packages)
        app_layout.addWidget(self._pkg_search)

        self._pkg_list = QListWidget()
        self._pkg_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._pkg_list.setMinimumHeight(60)
        self._pkg_list.setMaximumHeight(120)
        app_layout.addWidget(self._pkg_list)

        app_btns = QHBoxLayout()
        app_btns.setSpacing(4)
        self._lock_app_btn = QPushButton("锁定")
        self._lock_app_btn.setToolTip("将选中的应用设为锁定应用，连接设备后自动启动")
        self._lock_app_btn.clicked.connect(self._on_lock_clicked)
        app_btns.addWidget(self._lock_app_btn)

        self._launch_app_btn = QPushButton("启动")
        self._launch_app_btn.clicked.connect(self._on_launch_clicked)
        app_btns.addWidget(self._launch_app_btn)

        self._unlock_btn = QPushButton("取消锁定")
        self._unlock_btn.setProperty("role", "danger")
        self._unlock_btn.clicked.connect(lambda: self.lock_app_requested.emit(""))
        app_btns.addWidget(self._unlock_btn)
        app_layout.addLayout(app_btns)

        left.addWidget(app_group)

        # ---- 应用守护 ----
        guard_group = QGroupBox("应用守护")
        guard_layout = QVBoxLayout(guard_group)
        guard_layout.setSpacing(6)
        guard_layout.setContentsMargins(8, 12, 8, 8)

        locked_row = QHBoxLayout()
        locked_row.setSpacing(4)
        locked_lbl = QLabel("锁定:")
        locked_lbl.setFixedWidth(36)
        locked_row.addWidget(locked_lbl)
        self._locked_app_label = QLabel("未设置")
        self._locked_app_label.setStyleSheet("color: #a6adc8;")
        self._locked_app_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._locked_app_label.setWordWrap(True)
        locked_row.addWidget(self._locked_app_label, stretch=1)
        guard_layout.addLayout(locked_row)

        auto_row = QHBoxLayout()
        auto_row.setSpacing(4)
        self._auto_launch_cb = QCheckBox("连接后自动启动")
        self._auto_launch_cb.setChecked(False)
        auto_row.addWidget(self._auto_launch_cb)
        auto_row.addStretch()
        auto_row.addWidget(QLabel("延迟"))
        self._auto_launch_delay = QSpinBox()
        self._auto_launch_delay.setRange(0, 30)
        self._auto_launch_delay.setValue(3)
        self._auto_launch_delay.setSuffix("s")
        self._auto_launch_delay.setFixedWidth(60)
        self._auto_launch_delay.setToolTip("连接设备后延迟多少秒自动启动锁定应用")
        auto_row.addWidget(self._auto_launch_delay)
        guard_layout.addLayout(auto_row)

        keepalive_row = QHBoxLayout()
        keepalive_row.setSpacing(4)
        self._keepalive_cb = QCheckBox("定时探活")
        self._keepalive_cb.setToolTip("定时检测锁定应用是否在运行，未运行则自动拉起")
        self._keepalive_cb.toggled.connect(self.keepalive_toggled.emit)
        keepalive_row.addWidget(self._keepalive_cb)
        keepalive_row.addStretch()
        keepalive_row.addWidget(QLabel("间隔"))
        self._keepalive_interval = QSpinBox()
        self._keepalive_interval.setRange(10, 300)
        self._keepalive_interval.setValue(30)
        self._keepalive_interval.setSuffix("s")
        self._keepalive_interval.setFixedWidth(65)
        self._keepalive_interval.setToolTip("探活检测间隔")
        keepalive_row.addWidget(self._keepalive_interval)
        guard_layout.addLayout(keepalive_row)

        alive_row = QHBoxLayout()
        alive_row.setSpacing(4)
        self._check_alive_btn = QPushButton("立即探活")
        self._check_alive_btn.setFixedWidth(75)
        self._check_alive_btn.clicked.connect(self.check_alive_requested.emit)
        alive_row.addWidget(self._check_alive_btn)
        self._alive_status = QLabel("--")
        self._alive_status.setStyleSheet("color: #a6adc8; font-size: 11px;")
        alive_row.addWidget(self._alive_status, stretch=1)
        guard_layout.addLayout(alive_row)

        left.addWidget(guard_group)

        left.addStretch()
        scroll.setWidget(left_widget)
        layout.addWidget(scroll)

        # ---- 右侧预览 ----
        right = QVBoxLayout()
        right.setSpacing(8)

        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("实时预览"))
        preview_header.addStretch()

        self._refresh_once_btn = QPushButton("刷新")
        self._refresh_once_btn.setFixedWidth(60)
        self._refresh_once_btn.clicked.connect(self.preview_requested.emit)
        preview_header.addWidget(self._refresh_once_btn)

        self._auto_refresh_cb = QCheckBox("自动")
        self._auto_refresh_cb.setChecked(False)
        preview_header.addWidget(self._auto_refresh_cb)

        preview_header.addWidget(QLabel("间隔:"))
        self._refresh_interval = QSpinBox()
        self._refresh_interval.setRange(1, 30)
        self._refresh_interval.setValue(2)
        self._refresh_interval.setSuffix(" 秒")
        self._refresh_interval.setFixedWidth(80)
        preview_header.addWidget(self._refresh_interval)
        right.addLayout(preview_header)

        self._preview = ImagePreview()
        right.addWidget(self._preview, stretch=1)

        coord_layout = QHBoxLayout()
        self._coord_label = QLabel("坐标: --")
        self._coord_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        coord_layout.addWidget(self._coord_label)
        coord_layout.addStretch()
        right.addLayout(coord_layout)

        self._preview.coordinate_clicked.connect(
            lambda x, y: self._coord_label.setText(f"坐标: ({x}, {y})")
        )

        layout.addLayout(right, stretch=3)

    def set_device_info(self, info: dict) -> None:
        """更新设备信息展示。"""
        self._device_info = info
        for key, label in self._info_labels.items():
            value = info.get(key, "--")
            label.setText(str(value) if value else "--")

    def update_preview(self, image) -> None:
        """更新实时预览截图。"""
        self._preview.update_image(image)

    def update_preview_from_file(self, filepath: str) -> None:
        self._preview.update_from_file(filepath)

    def set_status(self, status: str, duration: str = "--") -> None:
        color_map = {"空闲": "#a6e3a1", "运行中": "#89b4fa", "暂停": "#f9e2af", "错误": "#f38ba8"}
        self._status_label.setText(status)
        self._status_label.setStyleSheet(f"color: {color_map.get(status, '#cdd6f4')}; font-weight: bold;")
        self._duration_label.setText(duration)

    # ---- 应用管理 ----

    def set_packages(self, packages: list[str]) -> None:
        """更新应用列表。"""
        self._all_packages = packages
        self._filter_packages(self._pkg_search.text())
        self._refresh_packages_btn.setText(f"获取应用列表 ({len(packages)})")

    def _filter_packages(self, text: str) -> None:
        self._pkg_list.clear()
        keyword = text.strip().lower()
        for pkg in self._all_packages:
            if keyword and keyword not in pkg.lower():
                continue
            self._pkg_list.addItem(pkg)

    def _on_lock_clicked(self) -> None:
        item = self._pkg_list.currentItem()
        if item:
            self.lock_app_requested.emit(item.text())

    def _on_launch_clicked(self) -> None:
        item = self._pkg_list.currentItem()
        if item:
            self.launch_app_requested.emit(item.text())

    def set_locked_app(self, package_name: str) -> None:
        """更新锁定应用的显示。"""
        if package_name:
            self._locked_app_label.setText(package_name)
            self._locked_app_label.setStyleSheet("color: #89b4fa; font-weight: bold;")
        else:
            self._locked_app_label.setText("未设置")
            self._locked_app_label.setStyleSheet("color: #a6adc8;")

    def get_auto_launch_config(self) -> dict:
        """获取自动启动配置。"""
        return {
            "auto_launch": self._auto_launch_cb.isChecked(),
            "auto_launch_delay": self._auto_launch_delay.value(),
        }

    def set_auto_launch_config(self, auto_launch: bool, delay: int) -> None:
        """设置自动启动配置（加载配置时调用）。"""
        self._auto_launch_cb.blockSignals(True)
        self._auto_launch_delay.blockSignals(True)
        self._auto_launch_cb.setChecked(auto_launch)
        self._auto_launch_delay.setValue(delay)
        self._auto_launch_cb.blockSignals(False)
        self._auto_launch_delay.blockSignals(False)

    # ---- 探活 ----

    def set_alive_status(self, running: bool, foreground: bool) -> None:
        """更新探活状态显示。"""
        if foreground:
            self._alive_status.setText("前台运行中")
            self._alive_status.setStyleSheet("color: #a6e3a1; font-size: 11px; font-weight: bold;")
        elif running:
            self._alive_status.setText("后台运行中")
            self._alive_status.setStyleSheet("color: #f9e2af; font-size: 11px; font-weight: bold;")
        else:
            self._alive_status.setText("未运行")
            self._alive_status.setStyleSheet("color: #f38ba8; font-size: 11px; font-weight: bold;")

    def set_keepalive_config(self, enabled: bool, interval: int) -> None:
        """设置探活配置（加载配置时调用）。"""
        self._keepalive_cb.blockSignals(True)
        self._keepalive_interval.blockSignals(True)
        self._keepalive_cb.setChecked(enabled)
        self._keepalive_interval.setValue(interval)
        self._keepalive_cb.blockSignals(False)
        self._keepalive_interval.blockSignals(False)

    def get_keepalive_interval(self) -> int:
        return self._keepalive_interval.value()
