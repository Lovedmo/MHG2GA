from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QMenu,
)

from src.gui.widgets.status_indicator import StatusIndicator


class DeviceCard(QWidget):
    """单个设备在列表中的卡片组件。"""

    def __init__(self, device_info: dict, parent=None):
        super().__init__(parent)
        self.device_info = device_info
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self._indicator = StatusIndicator(
            status=self.device_info.get("status", "disconnected"),
            size=10,
        )
        layout.addWidget(self._indicator)

        alias = self.device_info.get("alias", "未命名")
        self._alias_label = QLabel(alias)
        self._alias_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self._alias_label, stretch=1)

        address = self.device_info.get("address", "")
        model = self.device_info.get("model", "")
        tooltip_parts = [f"地址: {address}"] if address else []
        if model:
            tooltip_parts.append(f"型号: {model}")
        self.setToolTip("\n".join(tooltip_parts))

    def update_status(self, status: str) -> None:
        self.device_info["status"] = status
        self._indicator.status = status

    def update_alias(self, alias: str) -> None:
        self.device_info["alias"] = alias
        self._alias_label.setText(alias)


class DeviceListPanel(QWidget):
    """左侧设备列表面板。"""

    device_selected = pyqtSignal(dict)
    device_refresh_requested = pyqtSignal()
    device_added = pyqtSignal(str)
    device_connect_requested = pyqtSignal(str)
    device_disconnect_requested = pyqtSignal(str)
    device_removed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(8, 8, 8, 0)
        header_label = QLabel("设备列表")
        header_label.setProperty("role", "heading")
        header_row.addWidget(header_label)
        header_row.addStretch()

        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setToolTip("添加设备")
        add_btn.setStyleSheet(
            "QPushButton { font-size: 16px; font-weight: bold; border-radius: 4px;"
            "  padding: 0; min-height: 0; color: #cdd6f4; background-color: #313244; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        add_btn.clicked.connect(self._on_add_device)
        header_row.addWidget(add_btn)

        layout.addLayout(header_row)

        self._list_widget = QListWidget()
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)
        self._list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list_widget, stretch=1)

        self.setMinimumWidth(120)
        self.setMaximumWidth(240)

    def set_devices(self, devices: list[dict]) -> None:
        """设置设备列表。"""
        self._devices = devices
        self._list_widget.clear()

        for dev in devices:
            card = DeviceCard(dev)
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 36))
            self._list_widget.addItem(item)
            self._list_widget.setItemWidget(item, card)

        if devices:
            self._list_widget.setCurrentRow(0)

    def update_device_status(self, address: str, status: str) -> None:
        """更新指定设备的连接状态。"""
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            card = self._list_widget.itemWidget(item)
            if isinstance(card, DeviceCard) and card.device_info.get("address") == address:
                card.update_status(status)
                break

    def _on_selection_changed(self, row: int) -> None:
        if 0 <= row < len(self._devices):
            self.device_selected.emit(self._devices[row])

    def _on_add_device(self) -> None:
        address, ok = QInputDialog.getText(
            self, "添加设备", "请输入模拟器 ADB 地址:",
            text="127.0.0.1:16384",
        )
        if ok and address.strip():
            self.device_added.emit(address.strip())

    def _show_context_menu(self, pos) -> None:
        item = self._list_widget.itemAt(pos)
        if item is None:
            return
        row = self._list_widget.row(item)
        if row < 0 or row >= len(self._devices):
            return

        card = self._list_widget.itemWidget(item)
        device = self._devices[row]
        address = device.get("address", "")
        is_connected = device.get("status") == "connected"
        menu = QMenu(self)

        if is_connected:
            disconnect_action = menu.addAction("断开连接")
            connect_action = None
        else:
            connect_action = menu.addAction("连接")
            disconnect_action = None

        menu.addSeparator()
        rename_action = menu.addAction("重命名")
        remove_action = menu.addAction("移除")
        menu.addSeparator()
        refresh_action = menu.addAction("刷新列表")

        action = menu.exec(self._list_widget.mapToGlobal(pos))

        if action is None:
            return

        if action == connect_action:
            self.device_connect_requested.emit(address)

        elif action == disconnect_action:
            self.device_disconnect_requested.emit(address)
            if isinstance(card, DeviceCard):
                card.update_status("disconnected")
                device["status"] = "disconnected"

        elif action == rename_action:
            new_alias, ok = QInputDialog.getText(
                self, "重命名设备",
                "请输入新别名:",
                text=device.get("alias", ""),
            )
            if ok and new_alias.strip() and isinstance(card, DeviceCard):
                card.update_alias(new_alias.strip())
                device["alias"] = new_alias.strip()

        elif action == remove_action:
            self.device_removed.emit(address)
            self._devices.pop(row)
            self._list_widget.takeItem(row)

        elif action == refresh_action:
            self.device_refresh_requested.emit()
