from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox,
    QLineEdit, QFileDialog, QCheckBox, QDialogButtonBox,
)


class SettingsDialog(QDialog):
    """全局设置对话框。"""

    def __init__(self, current_settings: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全局设置")
        self.setMinimumWidth(500)
        self._settings = current_settings or {}
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        adb_group = QGroupBox("ADB 配置")
        adb_layout = QGridLayout(adb_group)
        adb_layout.setSpacing(8)

        adb_layout.addWidget(QLabel("ADB 路径:"), 0, 0)
        self._adb_path = QLineEdit()
        self._adb_path.setPlaceholderText("留空则自动检测")
        adb_layout.addWidget(self._adb_path, 0, 1)
        browse_adb_btn = QPushButton("浏览...")
        browse_adb_btn.setFixedWidth(70)
        browse_adb_btn.clicked.connect(self._browse_adb)
        adb_layout.addWidget(browse_adb_btn, 0, 2)

        adb_layout.addWidget(QLabel("MuMu Manager:"), 1, 0)
        self._mumu_path = QLineEdit()
        self._mumu_path.setPlaceholderText("MuMuManager.exe 路径（用于自动启动模拟器）")
        self._mumu_path.setToolTip(
            "通常位于 MuMu Player 12 安装目录下的 shell\\MuMuManager.exe\n"
            "例如: D:\\MuMu Player 12\\shell\\MuMuManager.exe\n"
            "设置后可实现连接时自动启动模拟器"
        )
        adb_layout.addWidget(self._mumu_path, 1, 1)
        browse_mumu_btn = QPushButton("浏览...")
        browse_mumu_btn.setFixedWidth(70)
        browse_mumu_btn.clicked.connect(self._browse_mumu)
        adb_layout.addWidget(browse_mumu_btn, 1, 2)

        layout.addWidget(adb_group)

        default_group = QGroupBox("新设备默认值")
        default_layout = QGridLayout(default_group)
        default_layout.setSpacing(8)

        default_layout.addWidget(QLabel("默认截图方式:"), 0, 0)
        self._default_cap = QComboBox()
        self._default_cap.addItems(["ADBCAP", "MINICAP", "JAVACAP"])
        default_layout.addWidget(self._default_cap, 0, 1)

        default_layout.addWidget(QLabel("默认触控方式:"), 1, 0)
        self._default_touch = QComboBox()
        self._default_touch.addItems(["ADBTOUCH", "MINITOUCH", "MAXTOUCH"])
        default_layout.addWidget(self._default_touch, 1, 1)

        layout.addWidget(default_group)

        ui_group = QGroupBox("界面与日志")
        ui_layout = QGridLayout(ui_group)
        ui_layout.setSpacing(8)

        ui_layout.addWidget(QLabel("界面主题:"), 0, 0)
        self._theme = QComboBox()
        self._theme.addItems(["暗色", "亮色"])
        ui_layout.addWidget(self._theme, 0, 1)

        ui_layout.addWidget(QLabel("日志级别:"), 1, 0)
        self._log_level = QComboBox()
        self._log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._log_level.setCurrentText("INFO")
        ui_layout.addWidget(self._log_level, 1, 1)

        ui_layout.addWidget(QLabel("日志文件:"), 2, 0)
        self._log_path = QLineEdit()
        self._log_path.setPlaceholderText("logs/mhg2ga.log")
        ui_layout.addWidget(self._log_path, 2, 1)

        layout.addWidget(ui_group)

        behavior_group = QGroupBox("行为")
        behavior_layout = QVBoxLayout(behavior_group)

        self._minimize_to_tray = QCheckBox("关闭窗口时最小化到系统托盘")
        self._minimize_to_tray.setChecked(True)
        behavior_layout.addWidget(self._minimize_to_tray)

        self._auto_connect = QCheckBox("启动时自动连接上次的设备")
        self._auto_connect.setChecked(True)
        behavior_layout.addWidget(self._auto_connect)

        layout.addWidget(behavior_group)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse_adb(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 ADB 可执行文件", "",
            "Executable (adb.exe);;All Files (*)",
        )
        if path:
            self._adb_path.setText(path)

    def _browse_mumu(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 MuMuManager.exe", "",
            "Executable (MuMuManager.exe);;All Files (*)",
        )
        if path:
            self._mumu_path.setText(path)

    def _load_settings(self) -> None:
        if "adb_path" in self._settings:
            self._adb_path.setText(self._settings["adb_path"])
        if "mumu_manager_path" in self._settings:
            self._mumu_path.setText(self._settings["mumu_manager_path"])
        if "default_cap_method" in self._settings:
            idx = self._default_cap.findText(self._settings["default_cap_method"])
            if idx >= 0:
                self._default_cap.setCurrentIndex(idx)
        if "default_touch_method" in self._settings:
            idx = self._default_touch.findText(self._settings["default_touch_method"])
            if idx >= 0:
                self._default_touch.setCurrentIndex(idx)
        if "theme" in self._settings:
            idx = self._theme.findText(self._settings["theme"])
            if idx >= 0:
                self._theme.setCurrentIndex(idx)
        if "log_level" in self._settings:
            idx = self._log_level.findText(self._settings["log_level"])
            if idx >= 0:
                self._log_level.setCurrentIndex(idx)
        if "log_path" in self._settings:
            self._log_path.setText(self._settings["log_path"])
        if "minimize_to_tray" in self._settings:
            self._minimize_to_tray.setChecked(self._settings["minimize_to_tray"])
        if "auto_connect" in self._settings:
            self._auto_connect.setChecked(self._settings["auto_connect"])

    def get_settings(self) -> dict:
        return {
            "adb_path": self._adb_path.text().strip(),
            "mumu_manager_path": self._mumu_path.text().strip(),
            "default_cap_method": self._default_cap.currentText(),
            "default_touch_method": self._default_touch.currentText(),
            "theme": self._theme.currentText(),
            "log_level": self._log_level.currentText(),
            "log_path": self._log_path.text().strip() or "logs/mhg2ga.log",
            "minimize_to_tray": self._minimize_to_tray.isChecked(),
            "auto_connect": self._auto_connect.isChecked(),
        }
