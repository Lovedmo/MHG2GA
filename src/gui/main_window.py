from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QPixmap, QImage
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QToolBar, QStatusBar,
    QLabel, QApplication, QMessageBox, QStackedWidget,
    QSystemTrayIcon,
)
import numpy as np

from src.config.settings import AppConfig
from src.core.database import Database
from src.core.device_manager import DeviceManager
from src.core.template_manager import TemplateManager
from src.core.task_model import TaskManager
from src.core.logger import get_logger, set_gui_callback
from src.core.workers import (
    ScanWorker, ConnectWorker, DisconnectWorker,
    ScreenshotWorker, BenchmarkWorker,
    TapWorker, SwipeWorker, KeyEventWorker, DeviceInfoWorker,
    ListPackagesWorker, CheckAppAliveWorker, StartAppWorker,
    StartEmulatorAndConnectWorker, ConnectionHealthWorker,
)

from src.core.path_helper import get_resource_path, get_data_path

logger = get_logger("main_window")
from src.gui.device_list_panel import DeviceListPanel
from src.gui.device_overview_tab import DeviceOverviewTab
from src.gui.screenshot_config_tab import ScreenshotConfigTab
from src.gui.touch_config_tab import TouchConfigTab
from src.gui.task_config_tab import TaskConfigTab
from src.gui.template_workspace import TemplateWorkspace
from src.gui.log_console import LogConsole
from src.gui.settings_dialog import SettingsDialog
from src.gui.system_tray import SystemTray


class DeviceTabWidget(QTabWidget):
    """单个设备的标签页容器。"""

    config_changed = pyqtSignal(str)

    def __init__(self, device_info: dict, task_manager: TaskManager | None = None,
                 template_manager: TemplateManager | None = None, parent=None):
        super().__init__(parent)
        self.device_info = device_info
        self._address = device_info.get("address", "")

        self.overview_tab = DeviceOverviewTab()
        self.screenshot_tab = ScreenshotConfigTab()
        self.touch_tab = TouchConfigTab()
        self.task_tab = TaskConfigTab(task_manager=task_manager,
                                      template_manager=template_manager)

        self.addTab(self.overview_tab, "设备概览")
        self.addTab(self.screenshot_tab, "截图与识别")
        self.addTab(self.touch_tab, "触控配置")
        self.addTab(self.task_tab, "任务配置")

        self.overview_tab.set_device_info(device_info)
        self._connect_change_signals()

    def _connect_change_signals(self) -> None:
        ss = self.screenshot_tab
        ss._cap_method.currentTextChanged.connect(lambda _: self.config_changed.emit(self._address))
        ss._cap_interval.valueChanged.connect(lambda _: self.config_changed.emit(self._address))
        ss._threshold_slider.valueChanged.connect(lambda _: self.config_changed.emit(self._address))

        tt = self.touch_tab
        tt._touch_method.currentTextChanged.connect(lambda _: self.config_changed.emit(self._address))
        tt._action_delay.valueChanged.connect(lambda _: self.config_changed.emit(self._address))

    def load_config(self, config: dict) -> None:
        widgets = [
            self.screenshot_tab._cap_method,
            self.screenshot_tab._cap_interval,
            self.screenshot_tab._threshold_slider,
            self.touch_tab._touch_method,
            self.touch_tab._action_delay,
        ]
        for w in widgets:
            w.blockSignals(True)

        self.screenshot_tab.set_config({
            "cap_method": config.get("cap_method", "ADBCAP"),
            "cap_interval": config.get("cap_interval", 0.5),
            "threshold": config.get("threshold", 0.80),
        })
        self.touch_tab.set_config({
            "touch_method": config.get("touch_method", "ADBTOUCH"),
            "action_delay": config.get("action_delay", 100),
        })

        for w in widgets:
            w.blockSignals(False)

        locked_app = config.get("locked_app", "")
        self.overview_tab.set_locked_app(locked_app)
        self.overview_tab.set_auto_launch_config(
            config.get("auto_launch", False),
            config.get("auto_launch_delay", 3),
        )
        self.overview_tab.set_keepalive_config(
            config.get("keepalive_enabled", False),
            config.get("keepalive_interval", 30),
        )

    def collect_config(self) -> dict:
        ss_cfg = self.screenshot_tab.get_config()
        tt_cfg = self.touch_tab.get_config()
        al_cfg = self.overview_tab.get_auto_launch_config()
        return {
            "cap_method": ss_cfg["cap_method"],
            "cap_interval": ss_cfg["cap_interval"],
            "threshold": ss_cfg["threshold"],
            "touch_method": tt_cfg["touch_method"],
            "action_delay": tt_cfg["action_delay"],
            "auto_launch": al_cfg["auto_launch"],
            "auto_launch_delay": al_cfg["auto_launch_delay"],
            "keepalive_enabled": self.overview_tab._keepalive_cb.isChecked(),
            "keepalive_interval": self.overview_tab.get_keepalive_interval(),
        }


class MainWindow(QMainWindow):
    """MHG2GA 主窗口。"""

    APP_TITLE = "MHG2GA - Make Houkai Gakuen 2 Great Again"

    def __init__(self):
        super().__init__()
        self._app_config = AppConfig()
        self._db = Database()
        self._dm = DeviceManager(
            adb_path=self._app_config.global_settings.get("adb_path", ""),
            mumu_manager_path=self._app_config.global_settings.get("mumu_manager_path", ""),
        )
        self._tm = TemplateManager()
        self._task_mgr = TaskManager()
        self._device_tabs: dict[str, DeviceTabWidget] = {}
        self._workers: list = []
        self._current_address: str = ""
        self._minimize_to_tray = self._app_config.global_settings.get("minimize_to_tray", True)
        self._setup_ui()
        self._setup_tray()
        self._load_stylesheet()
        self._register_log_callbacks()
        self._load_devices_from_config()
        self._setup_health_check()

    def _setup_ui(self) -> None:
        self.setWindowTitle(self.APP_TITLE)
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        icon_path = get_resource_path("src", "gui", "resources", "icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._setup_toolbar()
        self._setup_statusbar()

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(0)

        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)

        self._device_panel = DeviceListPanel()
        self._device_panel.device_selected.connect(self._on_device_selected)
        self._device_panel.device_refresh_requested.connect(self._on_refresh_devices)
        self._device_panel.device_added.connect(self._on_add_device)
        self._device_panel.device_connect_requested.connect(self._on_connect_device)
        self._device_panel.device_disconnect_requested.connect(self._on_disconnect_device)
        self._device_panel.device_removed.connect(self._on_remove_device)
        self._content_splitter.addWidget(self._device_panel)

        self._content_stack = QStackedWidget()
        self._placeholder = QWidget()
        ph_layout = QVBoxLayout(self._placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_label = QLabel("请在左侧选择一个设备")
        ph_label.setStyleSheet("font-size: 16px; color: #585b70;")
        ph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(ph_label)
        self._content_stack.addWidget(self._placeholder)

        self._content_splitter.addWidget(self._content_stack)
        self._content_splitter.setStretchFactor(0, 0)
        self._content_splitter.setStretchFactor(1, 1)
        self._content_splitter.setSizes([160, 980])

        root_layout.addWidget(self._content_splitter, stretch=1)

        self._log_console = LogConsole()
        self._toggle_log_action.toggled.connect(self._toggle_log_window)
        self._log_console.visibility_changed.connect(self._toggle_log_action.setChecked)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        self._start_all_action = QAction("全部启动", self)
        self._start_all_action.setToolTip("启动所有设备的任务")
        self._start_all_action.triggered.connect(
            lambda: self._log("INFO", "系统", "全部启动（功能待实现）")
        )
        toolbar.addAction(self._start_all_action)

        self._stop_all_action = QAction("全部停止", self)
        self._stop_all_action.setToolTip("停止所有设备的任务")
        self._stop_all_action.triggered.connect(
            lambda: self._log("INFO", "系统", "全部停止（功能待实现）")
        )
        toolbar.addAction(self._stop_all_action)

        toolbar.addSeparator()

        settings_action = QAction("全局设置", self)
        settings_action.setToolTip("打开全局设置对话框")
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

        toolbar.addSeparator()

        template_action = QAction("模板管理", self)
        template_action.setToolTip("打开模板管理窗口")
        template_action.triggered.connect(self._open_template_manager)
        toolbar.addAction(template_action)

        toolbar.addSeparator()

        self._toggle_log_action = QAction("日志控制台", self)
        self._toggle_log_action.setCheckable(True)
        self._toggle_log_action.setChecked(False)
        self._toggle_log_action.setToolTip("显示/隐藏日志控制台")
        toolbar.addAction(self._toggle_log_action)

        toolbar.addSeparator()

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        toolbar.addAction(about_action)

    def _setup_statusbar(self) -> None:
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)

        self._status_device_count = QLabel("设备: 0")
        statusbar.addWidget(self._status_device_count)

        self._status_adb = QLabel("ADB: 就绪")
        self._status_adb.setStyleSheet("color: #a6e3a1;")
        statusbar.addWidget(self._status_adb)

        statusbar.addPermanentWidget(QLabel("MHG2GA v0.1.0"))

    def _setup_tray(self) -> None:
        self._tray = SystemTray(self, parent=self)
        self._tray.show()

    def _load_stylesheet(self) -> None:
        qss_path = get_resource_path("src", "gui", "resources", "styles.qss")
        if qss_path.exists():
            with open(qss_path, "r", encoding="utf-8") as f:
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(f.read())

    def _register_log_callbacks(self) -> None:
        """将 GUI 控制台注册为日志处理器。"""
        set_gui_callback(self._log_console.append_log)

    def _log(self, level: str, device: str, message: str) -> None:
        """兼容方法：通过统一日志层记录。"""
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(message, extra={"device": device})

    # ---- 设备列表管理 ----

    def _load_devices_from_config(self) -> None:
        saved_devices = self._app_config.devices
        if saved_devices:
            for dev in saved_devices:
                dev.setdefault("status", "disconnected")
                for key in ("resolution", "dpi", "android_version", "sdk_version", "cpu_abi", "foreground_app"):
                    dev.setdefault(key, "--")
                dev.setdefault("alias", dev.get("address", ""))
                dev.setdefault("model", "--")
            self._device_panel.set_devices(saved_devices)
            self._status_device_count.setText(f"设备: {len(saved_devices)}")
            self._log("INFO", "系统", f"从配置文件加载了 {len(saved_devices)} 个设备")
        else:
            self._log("INFO", "系统", "无已保存设备，点击「刷新列表」扫描模拟器")

    def _on_refresh_devices(self) -> None:
        self._log("INFO", "系统", "正在扫描设备...")
        self._device_panel.setEnabled(False)
        worker = ScanWorker(self._dm)
        worker.finished.connect(self._on_scan_finished)
        worker.error.connect(lambda e: self._log("ERROR", "系统", f"扫描失败: {e}"))
        worker.finished.connect(lambda _: self._device_panel.setEnabled(True))
        worker.error.connect(lambda _: self._device_panel.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _on_scan_finished(self, devices: list[dict]) -> None:
        if not devices:
            self._log("WARNING", "系统", "未发现任何设备")
            return

        for dev in devices:
            dev.setdefault("alias", dev.get("address", ""))
            dev.setdefault("model", "--")
            for key in ("resolution", "dpi", "android_version", "sdk_version", "cpu_abi", "foreground_app"):
                dev.setdefault(key, "--")
            self._app_config.upsert_device({
                "alias": dev.get("alias", ""),
                "address": dev.get("address", ""),
            })

        self._device_panel.set_devices(devices)
        self._status_device_count.setText(f"设备: {len(devices)}")
        self._app_config.save()
        self._log("INFO", "系统", f"扫描完成，发现 {len(devices)} 个设备")

    def _on_connect_device(self, address: str) -> None:
        """右键菜单 → 连接设备。检测模拟器状态，未运行则自动启动后连接。"""
        self._log("INFO", address, "正在检测模拟器状态...")
        dev_cfg = self._app_config.get_device_config(address)
        cap = dev_cfg.get("cap_method", "ADBCAP")
        touch = dev_cfg.get("touch_method", "ADBTOUCH")

        emu_state = self._dm.get_emulator_state(address)
        if emu_state == "running":
            self._log("INFO", address, "模拟器运行中，正在连接...")
            worker = ConnectWorker(self._dm, address, cap_method=cap, touch_method=touch)
            worker.finished.connect(self._on_connect_finished)
            worker.error.connect(
                lambda addr, e, c=cap, t=touch: self._on_connect_failed_fallback(addr, e, c, t)
            )
            self._workers.append(worker)
            worker.start()
        else:
            self._log("INFO", address, f"模拟器状态: {emu_state}，将自动启动并连接...")
            self._start_emulator_and_connect(address, cap, touch)

    def _on_connect_failed_fallback(self, address: str, error: str,
                                     cap: str, touch: str) -> None:
        """连接失败后回退：尝试启动模拟器再连接。"""
        self._log("WARNING", address, f"直接连接失败: {error}")
        if self._dm._mumu_manager:
            self._log("INFO", address, "回退：尝试启动模拟器后重新连接...")
            self._start_emulator_and_connect(address, cap, touch)
        else:
            self._log("ERROR", address,
                       "连接失败且未配置 MuMu Manager 路径，无法自动启动模拟器。"
                       "请在「全局设置」中配置 MuMuManager.exe 路径。")

    def _start_emulator_and_connect(self, address: str, cap: str, touch: str) -> None:
        """启动模拟器并等待就绪后连接。"""
        worker = StartEmulatorAndConnectWorker(
            self._dm, address, cap_method=cap, touch_method=touch,
        )
        worker.stage.connect(lambda msg, a=address: self._log("INFO", a, msg))
        worker.finished.connect(self._on_connect_finished)
        worker.error.connect(lambda addr, e: self._log("ERROR", addr, f"启动/连接失败: {e}"))
        self._workers.append(worker)
        worker.start()

    def _on_disconnect_device(self, address: str) -> None:
        """右键菜单 → 断开连接。"""
        worker = DisconnectWorker(self._dm, address)
        worker.finished.connect(lambda addr: self._log("INFO", addr, "设备已断开"))
        self._workers.append(worker)
        worker.start()

    def _on_remove_device(self, address: str) -> None:
        """右键菜单 → 移除设备。"""
        self._dm.disconnect(address)
        self._app_config.remove_device(address)
        self._save_config()
        self._log("INFO", "系统", f"已移除设备: {address}")

    def _on_add_device(self, address: str) -> None:
        self._log("INFO", "系统", f"正在连接设备 {address}...")
        self._app_config.upsert_device({"alias": address, "address": address})
        self._app_config.save()

        dev_cfg = self._app_config.get_device_config(address)
        cap = dev_cfg.get("cap_method", "ADBCAP")
        touch = dev_cfg.get("touch_method", "ADBTOUCH")
        worker = ConnectWorker(self._dm, address, cap_method=cap, touch_method=touch)
        worker.finished.connect(self._on_connect_finished)
        worker.error.connect(lambda addr, e: self._log("ERROR", addr, f"连接失败: {e}"))
        self._workers.append(worker)
        worker.start()

    def _on_connect_finished(self, device_info: dict) -> None:
        address = device_info.get("address", "")
        self._device_panel.update_device_status(address, "connected")

        orientation = self._dm.get_orientation(address)
        ori_names = {0: "竖屏", 1: "横屏(左)", 2: "倒置", 3: "横屏(右)"}
        device_info["orientation"] = ori_names.get(orientation, f"未知({orientation})")

        self._log("INFO", address,
                   f"设备已连接: {device_info.get('model', '--')} | "
                   f"分辨率: {device_info.get('resolution', '--')} | "
                   f"方向: {device_info['orientation']}")

        if address in self._device_tabs:
            self._device_tabs[address].overview_tab.set_device_info(device_info)
            res = device_info.get("resolution", "")
            if "x" in res:
                w, h = res.split("x")
                self._device_tabs[address].screenshot_tab.set_device_resolution(int(w), int(h))

        dev_cfg = self._app_config.get_device_config(address)
        locked_app = dev_cfg.get("locked_app", "")
        auto_launch = dev_cfg.get("auto_launch", False)
        delay = dev_cfg.get("auto_launch_delay", 3)
        if locked_app and auto_launch:
            self._log("INFO", address, f"将在 {delay} 秒后自动启动: {locked_app}")
            QTimer.singleShot(delay * 1000, lambda a=address, p=locked_app: self._do_start_app(a, p))

    # ---- 设备选择与配置 ----

    def _on_device_selected(self, device_info: dict) -> None:
        address = device_info.get("address", "")
        self._current_address = address

        if address not in self._device_tabs:
            tab_widget = DeviceTabWidget(
                device_info,
                task_manager=self._task_mgr,
                template_manager=self._tm,
            )
            tab_widget.task_tab.set_device_manager(self._dm)
            tab_widget.task_tab.set_active_device(address)
            tab_widget.config_changed.connect(self._on_device_config_changed)

            tab_widget.screenshot_tab._test_btn.clicked.connect(
                lambda: self._do_screenshot_test(address)
            )
            tab_widget.screenshot_tab._perf_btn.clicked.connect(
                lambda: self._do_benchmark(address)
            )

            tab_widget.touch_tab._tap_btn.clicked.connect(
                lambda: self._do_tap_test(address)
            )
            tab_widget.touch_tab._swipe_btn.clicked.connect(
                lambda: self._do_swipe_test(address)
            )
            tab_widget.touch_tab._key_btn.clicked.connect(
                lambda: self._do_key_test(address)
            )

            ov = tab_widget.overview_tab
            ov._connect_btn.clicked.connect(lambda _, a=address: self._on_connect_device(a))
            ov._disconnect_btn.clicked.connect(lambda _, a=address: self._on_disconnect_device(a))
            ov._home_btn.clicked.connect(lambda _, a=address: self._do_key_action(a, "HOME"))
            ov._back_btn.clicked.connect(lambda _, a=address: self._do_key_action(a, "BACK"))
            ov._save_screenshot_btn.clicked.connect(lambda _, a=address: self._do_save_screenshot(a))
            ov.preview_requested.connect(lambda a=address: self._do_preview_refresh(a))
            ov.refresh_packages_requested.connect(
                lambda third_party, a=address: self._do_list_packages(a, third_party)
            )
            ov.lock_app_requested.connect(lambda pkg, a=address: self._do_lock_app(a, pkg))
            ov.launch_app_requested.connect(lambda pkg, a=address: self._do_start_app(a, pkg))
            ov._auto_launch_cb.toggled.connect(lambda _: self._on_device_config_changed(address))
            ov._auto_launch_delay.valueChanged.connect(lambda _: self._on_device_config_changed(address))
            ov.check_alive_requested.connect(lambda a=address: self._do_check_alive(a))
            ov.keepalive_toggled.connect(lambda enabled, a=address: self._on_keepalive_toggled(a, enabled))
            ov._keepalive_interval.valueChanged.connect(lambda _: self._on_device_config_changed(address))

            keepalive_timer = QTimer(self)
            keepalive_timer.timeout.connect(lambda a=address: self._do_keepalive_tick(a))
            tab_widget._keepalive_timer = keepalive_timer

            preview_timer = QTimer(self)
            preview_timer.timeout.connect(lambda a=address: self._on_preview_timer(a))
            tab_widget._preview_timer = preview_timer
            ov._auto_refresh_cb.toggled.connect(lambda checked, t=preview_timer, o=ov: (
                t.start(o._refresh_interval.value() * 1000) if checked else t.stop()
            ))
            ov._refresh_interval.valueChanged.connect(lambda val, t=preview_timer, o=ov: (
                t.setInterval(val * 1000) if o._auto_refresh_cb.isChecked() else None
            ))

            self._device_tabs[address] = tab_widget
            self._content_stack.addWidget(tab_widget)

            device_config = self._app_config.get_device_config(address)
            tab_widget.load_config(device_config)

        self._content_stack.setCurrentWidget(self._device_tabs[address])
        self._log("DEBUG", "系统", f"切换到设备: {device_info.get('alias', address)}")

    def _on_device_config_changed(self, address: str) -> None:
        tab_widget = self._device_tabs.get(address)
        if not tab_widget:
            return

        old_cfg = self._app_config.get_device_config(address)
        new_cfg = tab_widget.collect_config()

        if new_cfg.get("cap_method") != old_cfg.get("cap_method"):
            cap = new_cfg["cap_method"]
            self._log("INFO", address, f"截图方式切换为: {cap}")
            if self._dm.is_connected(address):
                self._dm.set_cap_method(address, cap)

        if new_cfg.get("touch_method") != old_cfg.get("touch_method"):
            touch = new_cfg["touch_method"]
            self._log("INFO", address, f"触控方式切换为: {touch}")
            if self._dm.is_connected(address):
                self._dm.set_touch_method(address, touch)

        self._app_config.update_device_field(address, **new_cfg)
        self._save_config()

    # ---- 截图操作 ----

    def _do_screenshot_test(self, address: str) -> None:
        if not self._dm.is_connected(address):
            self._log("WARNING", address, "设备未连接，正在尝试连接...")
            self._connect_then(address, lambda: self._do_screenshot_test(address))
            return

        tab = self._device_tabs.get(address)
        if tab:
            tab.screenshot_tab.set_test_result("正在截图...")

        temp_dir = get_data_path("data", "temp")
        temp_path = str(temp_dir / f"ss_test_{address.replace(':', '_')}.png")
        worker = ScreenshotWorker(self._dm, address, save_path=temp_path)
        worker.finished.connect(lambda img, elapsed: self._on_screenshot_done(address, temp_path, elapsed))
        worker.error.connect(lambda e: self._on_screenshot_error(address, e))
        self._workers.append(worker)
        worker.start()

    def _on_screenshot_done(self, address: str, filepath: str, elapsed: float) -> None:
        tab = self._device_tabs.get(address)
        if not tab:
            return

        pixmap = QPixmap(filepath)
        if not pixmap.isNull():
            w, h = pixmap.width(), pixmap.height()
            tab.screenshot_tab.set_test_result(f"截图成功: {w}x{h}, 耗时 {elapsed:.0f}ms")
            tab.screenshot_tab.set_preview_info(f"尺寸: {w}x{h} | 耗时: {elapsed:.0f}ms")
            tab.screenshot_tab.set_device_resolution(w, h)
            tab.screenshot_tab.update_preview(pixmap)
            self._log("INFO", address, f"截图成功: {w}x{h}, {elapsed:.0f}ms")
        else:
            tab.screenshot_tab.set_test_result("截图失败：无法加载图像文件")
            self._log("WARNING", address, "截图失败：无法加载图像文件")

    def _on_screenshot_error(self, address: str, error: str) -> None:
        tab = self._device_tabs.get(address)
        if tab:
            tab.screenshot_tab.set_test_result(f"截图失败: {error}")
        self._log("ERROR", address, f"截图失败: {error}")

    def _do_benchmark(self, address: str) -> None:
        if not self._dm.is_connected(address):
            self._log("WARNING", address, "设备未连接，正在尝试连接...")
            self._connect_then(address, lambda: self._do_benchmark(address))
            return

        tab = self._device_tabs.get(address)
        if tab:
            tab.screenshot_tab.set_test_result("性能基准测试中...")

        worker = BenchmarkWorker(self._dm, address, rounds=5)
        worker.progress.connect(lambda i, t: self._on_benchmark_progress(address, i, t))
        worker.finished.connect(lambda results: self._on_benchmark_done(address, results))
        worker.error.connect(lambda e: self._on_screenshot_error(address, e))
        self._workers.append(worker)
        worker.start()

    def _on_benchmark_progress(self, address: str, round_num: int, elapsed: float) -> None:
        tab = self._device_tabs.get(address)
        if tab:
            tab.screenshot_tab.set_test_result(f"第 {round_num}/5 轮: {elapsed:.0f}ms")

    def _on_benchmark_done(self, address: str, results: list[float]) -> None:
        tab = self._device_tabs.get(address)
        if not tab:
            return
        avg = sum(results) / len(results)
        min_t = min(results)
        max_t = max(results)
        detail = " / ".join(f"{t:.0f}" for t in results)
        tab.screenshot_tab.set_test_result(
            f"基准测试完成: 平均 {avg:.0f}ms (最小 {min_t:.0f}, 最大 {max_t:.0f})\n"
            f"各轮: {detail} ms"
        )
        self._log("INFO", address, f"截图基准: 平均 {avg:.0f}ms, 5轮: [{detail}]")

    # ---- 触控操作 ----

    def _do_tap_test(self, address: str) -> None:
        if not self._dm.is_connected(address):
            self._log("WARNING", address, "设备未连接，正在尝试连接...")
            self._connect_then(address, lambda: self._do_tap_test(address))
            return

        tab = self._device_tabs.get(address)
        if not tab:
            return
        x, y = tab.touch_tab.get_tap_params()
        tab.touch_tab.set_result(f"正在点击 ({x}, {y})...")

        worker = TapWorker(self._dm, address, x, y)
        worker.finished.connect(lambda: self._on_tap_done(address, x, y))
        worker.error.connect(lambda e: self._on_touch_error(address, e))
        self._workers.append(worker)
        worker.start()

    def _on_tap_done(self, address: str, x: int, y: int) -> None:
        tab = self._device_tabs.get(address)
        if tab:
            tab.touch_tab.set_result(f"点击 ({x}, {y}) 成功")
        self._log("INFO", address, f"点击 ({x}, {y}) 成功")

    def _do_swipe_test(self, address: str) -> None:
        if not self._dm.is_connected(address):
            self._connect_then(address, lambda: self._do_swipe_test(address))
            return

        tab = self._device_tabs.get(address)
        if not tab:
            return
        x1, y1, x2, y2, duration = tab.touch_tab.get_swipe_params()
        tab.touch_tab.set_result(f"正在滑动 ({x1},{y1})->({x2},{y2})...")

        worker = SwipeWorker(self._dm, address, x1, y1, x2, y2, duration)
        worker.finished.connect(lambda: self._on_swipe_done(address, x1, y1, x2, y2))
        worker.error.connect(lambda e: self._on_touch_error(address, e))
        self._workers.append(worker)
        worker.start()

    def _on_swipe_done(self, address: str, x1: int, y1: int, x2: int, y2: int) -> None:
        tab = self._device_tabs.get(address)
        if tab:
            tab.touch_tab.set_result(f"滑动 ({x1},{y1})->({x2},{y2}) 成功")
        self._log("INFO", address, f"滑动 ({x1},{y1})->({x2},{y2}) 成功")

    def _do_key_test(self, address: str) -> None:
        if not self._dm.is_connected(address):
            self._connect_then(address, lambda: self._do_key_test(address))
            return

        tab = self._device_tabs.get(address)
        if not tab:
            return
        key = tab.touch_tab.get_key_param()
        tab.touch_tab.set_result(f"正在发送按键 {key}...")

        worker = KeyEventWorker(self._dm, address, key)
        worker.finished.connect(lambda: self._on_key_done(address, key))
        worker.error.connect(lambda e: self._on_touch_error(address, e))
        self._workers.append(worker)
        worker.start()

    def _on_key_done(self, address: str, key: str) -> None:
        tab = self._device_tabs.get(address)
        if tab:
            tab.touch_tab.set_result(f"按键 {key} 发送成功")
        self._log("INFO", address, f"按键 {key} 发送成功")

    def _do_key_action(self, address: str, key: str) -> None:
        """设备概览页快捷按键（HOME/BACK 等）。"""
        if not self._dm.is_connected(address):
            self._connect_then(address, lambda: self._do_key_action(address, key))
            return

        worker = KeyEventWorker(self._dm, address, key)
        worker.finished.connect(lambda: self._log("INFO", address, f"{key} 按键已发送"))
        worker.error.connect(lambda e: self._log("ERROR", address, f"{key} 失败: {e}"))
        self._workers.append(worker)
        worker.start()

    def _do_preview_refresh(self, address: str) -> None:
        """手动/自动刷新设备概览的实时预览。"""
        if not self._dm.is_connected(address):
            return
        temp_dir = get_data_path("data", "temp")
        temp_path = str(temp_dir / f"preview_{address.replace(':', '_')}.png")
        worker = ScreenshotWorker(self._dm, address, save_path=temp_path)
        worker.finished.connect(lambda img, elapsed: self._on_preview_done(address, temp_path))
        worker.error.connect(lambda e: logger.warning("预览刷新失败: %s", e, extra={"device": address}))
        self._workers.append(worker)
        worker.start()

    def _on_preview_timer(self, address: str) -> None:
        self._do_preview_refresh(address)

    def _on_preview_done(self, address: str, filepath: str) -> None:
        tab = self._device_tabs.get(address)
        if not tab:
            return
        pixmap = QPixmap(filepath)
        if not pixmap.isNull():
            tab.overview_tab.update_preview(pixmap)
            orientation = self._dm.get_orientation(address)
            ori_names = {0: "竖屏", 1: "横屏(左)", 2: "倒置", 3: "横屏(右)"}
            ori_text = ori_names.get(orientation, f"未知({orientation})")
            if "orientation" in tab.overview_tab._info_labels:
                tab.overview_tab._info_labels["orientation"].setText(ori_text)

    def _do_save_screenshot(self, address: str) -> None:
        """保存截图到文件。"""
        if not self._dm.is_connected(address):
            self._connect_then(address, lambda: self._do_save_screenshot(address))
            return

        from PyQt6.QtWidgets import QFileDialog
        from datetime import datetime
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存截图",
            f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "Images (*.png *.jpg)",
        )
        if not filepath:
            return

        worker = ScreenshotWorker(self._dm, address, save_path=filepath)
        worker.finished.connect(lambda img, elapsed: self._log("INFO", address, f"截图已保存: {filepath}"))
        worker.error.connect(lambda e: self._log("ERROR", address, f"保存截图失败: {e}"))
        self._workers.append(worker)
        worker.start()

    def _on_touch_error(self, address: str, error: str) -> None:
        tab = self._device_tabs.get(address)
        if tab:
            tab.touch_tab.set_result(f"操作失败: {error}")
        self._log("ERROR", address, f"触控操作失败: {error}")

    # ---- 应用管理 ----

    def _do_list_packages(self, address: str, third_party_only: bool = True) -> None:
        """获取设备已安装应用列表。"""
        if not self._dm.is_connected(address):
            self._log("WARNING", address, "设备未连接，正在尝试连接...")
            self._connect_then(address, lambda: self._do_list_packages(address, third_party_only))
            return

        tab = self._device_tabs.get(address)
        if tab:
            tab.overview_tab._refresh_packages_btn.setEnabled(False)
            tab.overview_tab._refresh_packages_btn.setText("正在获取...")

        worker = ListPackagesWorker(self._dm, address, third_party_only)
        worker.finished.connect(lambda pkgs: self._on_packages_listed(address, pkgs))
        worker.error.connect(lambda e: self._on_packages_error(address, e))
        self._workers.append(worker)
        worker.start()

    def _on_packages_listed(self, address: str, packages: list[str]) -> None:
        tab = self._device_tabs.get(address)
        if tab:
            tab.overview_tab.set_packages(packages)
            tab.overview_tab._refresh_packages_btn.setEnabled(True)
        self._log("INFO", address, f"获取到 {len(packages)} 个应用")

    def _on_packages_error(self, address: str, error: str) -> None:
        tab = self._device_tabs.get(address)
        if tab:
            tab.overview_tab._refresh_packages_btn.setEnabled(True)
            tab.overview_tab._refresh_packages_btn.setText("获取应用列表")
        self._log("ERROR", address, f"获取应用列表失败: {error}")

    def _do_lock_app(self, address: str, package_name: str) -> None:
        """锁定/取消锁定应用。"""
        tab = self._device_tabs.get(address)
        if tab:
            tab.overview_tab.set_locked_app(package_name)

        self._app_config.update_device_field(address, locked_app=package_name)
        self._save_config()

        if package_name:
            self._log("INFO", address, f"已锁定应用: {package_name}")
        else:
            self._log("INFO", address, "已取消应用锁定")

    def _do_start_app(self, address: str, package_name: str) -> None:
        """启动指定应用。"""
        if not package_name:
            return
        if not self._dm.is_connected(address):
            self._log("WARNING", address, "设备未连接，无法启动应用")
            return

        self._log("INFO", address, f"正在启动: {package_name}")
        worker = StartAppWorker(self._dm, address, package_name)
        worker.finished.connect(lambda pkg: self._log("INFO", address, f"应用已启动: {pkg}"))
        worker.error.connect(lambda e: self._log("ERROR", address, f"启动应用失败: {e}"))
        self._workers.append(worker)
        worker.start()

    # ---- 探活 ----

    def _do_check_alive(self, address: str) -> None:
        """立即探活：检测锁定应用是否在运行。"""
        dev_cfg = self._app_config.get_device_config(address)
        locked_app = dev_cfg.get("locked_app", "")
        if not locked_app:
            self._log("WARNING", address, "未设置锁定应用，无法探活")
            tab = self._device_tabs.get(address)
            if tab:
                tab.overview_tab._alive_status.setText("未设置锁定应用")
                tab.overview_tab._alive_status.setStyleSheet("color: #a6adc8; font-size: 11px;")
            return
        if not self._dm.is_connected(address):
            self._log("WARNING", address, "设备未连接，无法探活")
            return

        worker = CheckAppAliveWorker(self._dm, address, locked_app)
        worker.finished.connect(lambda result: self._on_check_alive_done(result, auto_restart=False))
        worker.error.connect(lambda e: self._log("ERROR", address, f"探活失败: {e}"))
        self._workers.append(worker)
        worker.start()

    def _do_keepalive_tick(self, address: str) -> None:
        """定时探活：检测并自动拉起。"""
        dev_cfg = self._app_config.get_device_config(address)
        locked_app = dev_cfg.get("locked_app", "")
        if not locked_app or not self._dm.is_connected(address):
            return

        worker = CheckAppAliveWorker(self._dm, address, locked_app)
        worker.finished.connect(lambda result: self._on_check_alive_done(result, auto_restart=True))
        worker.error.connect(lambda e: logger.debug("定时探活异常: %s", e, extra={"device": address}))
        self._workers.append(worker)
        worker.start()

    def _on_check_alive_done(self, result: dict, auto_restart: bool = False) -> None:
        address = result.get("address", "")
        package = result.get("package", "")
        running = result.get("running", False)
        foreground = result.get("foreground", False)

        tab = self._device_tabs.get(address)
        if tab:
            tab.overview_tab.set_alive_status(running, foreground)

        if foreground:
            self._log("DEBUG", address, f"探活: {package} 前台运行中")
        elif running:
            self._log("DEBUG", address, f"探活: {package} 后台运行中")
        else:
            self._log("WARNING", address, f"探活: {package} 未运行")
            if auto_restart:
                self._log("INFO", address, f"自动拉起: {package}")
                self._do_start_app(address, package)

    def _on_keepalive_toggled(self, address: str, enabled: bool) -> None:
        """开启/关闭定时探活。"""
        tab = self._device_tabs.get(address)
        if not tab:
            return

        timer = getattr(tab, '_keepalive_timer', None)
        if not timer:
            return

        if enabled:
            interval = tab.overview_tab.get_keepalive_interval()
            timer.start(interval * 1000)
            self._log("INFO", address, f"定时探活已开启 (间隔 {interval}s)")
            self._do_keepalive_tick(address)
        else:
            timer.stop()
            self._log("INFO", address, "定时探活已关闭")

        self._on_device_config_changed(address)

    # ---- 模板管理 ----

    def _do_capture_template(self, address: str) -> None:
        """从当前设备截图并加载到模板工作台。"""
        if not self._dm.is_connected(address):
            self._log("WARNING", address, "设备未连接，正在尝试连接...")
            self._connect_then(address, lambda: self._do_capture_template(address))
            return

        self._log("INFO", address, "正在截图用于模板截取...")
        try:
            img, elapsed = self._dm.take_screenshot(address)
            self._log("INFO", address, f"截图完成 ({elapsed:.0f}ms)")
            ws = self._get_template_workspace()
            ws.load_screenshot(img)
            ws.show()
            ws.raise_()
            ws.activateWindow()
        except Exception as e:
            self._log("ERROR", address, f"模板截取失败: {e}")

    def _get_template_workspace(self) -> TemplateWorkspace:
        """获取或创建模板工作台窗口（单例）。"""
        if not hasattr(self, '_template_ws') or not self._template_ws:
            self._template_ws = TemplateWorkspace(self._tm)
            self._template_ws.capture_screenshot_requested.connect(
                self._on_workspace_capture_request
            )
        return self._template_ws

    def _open_template_manager(self) -> None:
        """打开模板工作台。"""
        ws = self._get_template_workspace()
        ws.refresh_list()
        ws.show()
        ws.raise_()
        ws.activateWindow()

    def _on_workspace_capture_request(self) -> None:
        """模板工作台请求截图。"""
        address = self._current_address
        if not address:
            QMessageBox.warning(self, "无设备", "请先在主窗口左侧选择一个设备")
            return
        self._do_capture_template(address)

    # ---- 连接健康检测 ----

    def _setup_health_check(self) -> None:
        """每 30 秒检测所有已连接设备的连接状态。"""
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._do_health_check)
        self._health_timer.start(30_000)

    def _do_health_check(self) -> None:
        for address in list(self._device_tabs.keys()):
            if self._dm.is_connected(address):
                worker = ConnectionHealthWorker(self._dm, address)
                worker.finished.connect(self._on_health_check_done)
                self._workers.append(worker)
                worker.start()

    def _on_health_check_done(self, address: str, alive: bool) -> None:
        if alive:
            return
        if not self._dm.is_connected(address):
            return
        self._log("WARNING", address, "检测到模拟器已断开，自动清理连接...")
        self._dm.disconnect(address)
        self._device_panel.update_device_status(address, "disconnected")
        tab = self._device_tabs.get(address)
        if tab:
            timer = getattr(tab, '_preview_timer', None)
            if timer:
                timer.stop()
            ka_timer = getattr(tab, '_keepalive_timer', None)
            if ka_timer:
                ka_timer.stop()
        self._log("INFO", address, "连接已自动断开")

    # ---- 辅助方法 ----

    @staticmethod
    def _ndarray_to_pixmap(img: np.ndarray) -> QPixmap:
        """安全地将 numpy 图像数组 (BGR) 转为 QPixmap。"""
        import cv2
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)
        bytes_per_line = 3 * w
        qimg = QImage(bytes(rgb.data), w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def _connect_then(self, address: str, callback) -> None:
        """连接设备后执行回调。"""
        dev_cfg = self._app_config.get_device_config(address)
        cap = dev_cfg.get("cap_method", "ADBCAP")
        touch = dev_cfg.get("touch_method", "ADBTOUCH")
        worker = ConnectWorker(self._dm, address, cap_method=cap, touch_method=touch)
        worker.finished.connect(lambda info: (self._on_connect_finished(info), callback()))
        worker.error.connect(lambda addr, e: self._log("ERROR", addr, f"连接失败: {e}"))
        self._workers.append(worker)
        worker.start()

    def _toggle_log_window(self, checked: bool) -> None:
        if checked:
            self._log_console.show()
            self._log_console.raise_()
            self._log_console.activateWindow()
        else:
            self._log_console.hide()

    def _save_config(self) -> None:
        try:
            self._app_config.save()
        except Exception as e:
            self._log("ERROR", "系统", f"配置保存失败: {e}")

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._app_config.global_settings, parent=self)
        if dialog.exec():
            new_settings = dialog.get_settings()
            self._app_config.global_settings = new_settings
            self._minimize_to_tray = new_settings.get("minimize_to_tray", True)
            adb_path = new_settings.get("adb_path", "")
            if adb_path:
                self._dm._adb_path = adb_path
            mumu_path = new_settings.get("mumu_manager_path", "")
            self._dm.set_mumu_manager_path(mumu_path)
            self._save_config()
            self._log("INFO", "系统", "全局设置已更新并保存")

    def _show_about(self) -> None:
        from src.config.settings import get_config_path
        config_path = get_config_path()
        QMessageBox.about(
            self,
            "关于 MHG2GA",
            "<h2>MHG2GA</h2>"
            "<p><b>Make Houkai Gakuen 2 Great Again</b></p>"
            "<p>崩坏学园2模拟器全自动流程辅助工具</p>"
            "<p>版本: 0.1.0</p>"
            f"<p>配置文件: {config_path}</p>"
            "<p>许可证: MIT</p>",
        )

    def closeEvent(self, event) -> None:
        if self._minimize_to_tray and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            self._log_console.hide()
            if hasattr(self, '_template_ws') and self._template_ws:
                self._template_ws.hide()
            self._tray.show_message("MHG2GA", "程序已最小化到系统托盘")
        else:
            self._stop_all_task_executors()
            self._dm.disconnect_all()
            self._log_console.close()
            if hasattr(self, '_template_ws') and self._template_ws:
                self._template_ws.close()
            self._db.close()
            self._tray.hide()
            event.accept()

    def _stop_all_task_executors(self) -> None:
        """关闭所有设备 tab 中正在运行的任务执行器。"""
        for tab_widget in self._device_tabs.values():
            if hasattr(tab_widget, 'task_tab'):
                tab_widget.task_tab.stop_all_tasks()
