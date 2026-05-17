from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QIcon, QTextCharFormat
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QComboBox, QCheckBox, QFileDialog, QLabel,
)


LEVEL_COLORS = {
    "DEBUG": QColor("#585b70"),
    "INFO": QColor("#cdd6f4"),
    "WARNING": QColor("#f9e2af"),
    "ERROR": QColor("#f38ba8"),
}


class LogConsole(QWidget):
    """独立的日志控制台窗口，支持级别筛选、设备过滤、导出。"""

    visibility_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("MHG2GA - 日志控制台")
        self.setMinimumSize(700, 350)
        self.resize(900, 400)
        self._load_stylesheet()
        self._auto_scroll = True
        self._current_level_filter = "ALL"
        self._current_device_filter = "全部设备"
        self._log_entries: list[dict] = []
        self._setup_ui()

    def _load_stylesheet(self) -> None:
        from src.core.path_helper import get_resource_path
        res_dir = get_resource_path("src", "gui", "resources")
        qss_path = res_dir / "styles.qss"
        base_style = "LogConsole { background-color: #1e1e2e; color: #cdd6f4; }\n"
        if qss_path.exists():
            with open(qss_path, "r", encoding="utf-8") as f:
                base_style += f.read()
        self.setStyleSheet(base_style)
        icon_path = res_dir / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        toolbar.addWidget(QLabel("级别:"))
        self._level_combo = QComboBox()
        self._level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
        self._level_combo.setCurrentText("ALL")
        self._level_combo.currentTextChanged.connect(self._on_filter_changed)
        self._level_combo.setFixedWidth(100)
        toolbar.addWidget(self._level_combo)

        toolbar.addWidget(QLabel("设备:"))
        self._device_combo = QComboBox()
        self._device_combo.addItem("全部设备")
        self._device_combo.currentTextChanged.connect(self._on_filter_changed)
        self._device_combo.setFixedWidth(140)
        toolbar.addWidget(self._device_combo)

        self._auto_scroll_cb = QCheckBox("自动滚动")
        self._auto_scroll_cb.setChecked(True)
        self._auto_scroll_cb.toggled.connect(self._on_auto_scroll_toggled)
        toolbar.addWidget(self._auto_scroll_cb)

        self._pin_btn = QPushButton("置顶")
        self._pin_btn.setFixedWidth(60)
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(False)
        self._pin_btn.toggled.connect(self._on_pin_toggled)
        toolbar.addWidget(self._pin_btn)

        toolbar.addStretch()

        clear_btn = QPushButton("清空")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self._clear_logs)
        toolbar.addWidget(clear_btn)

        export_btn = QPushButton("导出")
        export_btn.setFixedWidth(60)
        export_btn.clicked.connect(self._export_logs)
        toolbar.addWidget(export_btn)

        layout.addLayout(toolbar)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        layout.addWidget(self._text_edit, stretch=1)

    @pyqtSlot(str, str, str)
    def append_log(self, level: str, device: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "level": level.upper(),
            "device": device,
            "message": message,
        }
        self._log_entries.append(entry)

        if len(self._log_entries) > 5000:
            self._log_entries = self._log_entries[-4000:]

        self._update_device_list(device)

        if self._should_show(entry):
            self._append_formatted(entry)

    def _should_show(self, entry: dict) -> bool:
        if self._current_level_filter != "ALL":
            levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
            entry_idx = levels.index(entry["level"]) if entry["level"] in levels else 0
            filter_idx = levels.index(self._current_level_filter)
            if entry_idx < filter_idx:
                return False

        if self._current_device_filter != "全部设备":
            if entry["device"] != self._current_device_filter:
                return False

        return True

    def _append_formatted(self, entry: dict) -> None:
        color = LEVEL_COLORS.get(entry["level"], LEVEL_COLORS["INFO"])
        fmt = QTextCharFormat()
        fmt.setForeground(color)

        cursor = self._text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(
            f"[{entry['timestamp']}] [{entry['level']:7s}] [{entry['device']}] {entry['message']}\n",
            fmt,
        )

        if self._auto_scroll:
            scrollbar = self._text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _update_device_list(self, device: str) -> None:
        existing = [self._device_combo.itemText(i) for i in range(self._device_combo.count())]
        if device and device not in existing:
            self._device_combo.addItem(device)

    def _on_filter_changed(self) -> None:
        self._current_level_filter = self._level_combo.currentText()
        self._current_device_filter = self._device_combo.currentText()
        self._refresh_display()

    def _refresh_display(self) -> None:
        self._text_edit.clear()
        for entry in self._log_entries:
            if self._should_show(entry):
                self._append_formatted(entry)

    def _on_auto_scroll_toggled(self, checked: bool) -> None:
        self._auto_scroll = checked

    def _clear_logs(self) -> None:
        self._log_entries.clear()
        self._text_edit.clear()

    def _export_logs(self) -> None:
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出日志", f"mhg2ga_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if not filepath:
            return
        with open(filepath, "w", encoding="utf-8") as f:
            for entry in self._log_entries:
                f.write(f"[{entry['timestamp']}] [{entry['level']:7s}] [{entry['device']}] {entry['message']}\n")

    def _on_pin_toggled(self, checked: bool) -> None:
        was_visible = self.isVisible()
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self._pin_btn.setText("取消置顶")
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
            self._pin_btn.setText("置顶")
        if was_visible:
            self.show()

    def closeEvent(self, event) -> None:
        self.hide()
        self.visibility_changed.emit(False)
        event.ignore()
