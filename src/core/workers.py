"""后台工作线程：将耗时的 ADB 操作放到 QThread 中执行，避免阻塞 GUI。"""

from PyQt6.QtCore import QThread, pyqtSignal
import numpy as np

from src.core.device_manager import DeviceManager, DeviceInfo


class ScanWorker(QThread):
    """扫描设备列表。"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, parent=None):
        super().__init__(parent)
        self._dm = device_manager

    def run(self):
        try:
            devices = self._dm.scan_devices()
            self.finished.emit([d.to_dict() for d in devices])
        except Exception as e:
            self.error.emit(str(e))


class ConnectWorker(QThread):
    """连接单个设备。"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str, str)

    def __init__(self, device_manager: DeviceManager, address: str,
                 cap_method: str = "ADBCAP", touch_method: str = "ADBTOUCH",
                 parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._cap_method = cap_method
        self._touch_method = touch_method

    def run(self):
        try:
            info = self._dm.connect(self._address, self._cap_method, self._touch_method)
            self.finished.emit(info.to_dict())
        except Exception as e:
            self.error.emit(self._address, str(e))


class DisconnectWorker(QThread):
    """断开设备连接。"""
    finished = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address

    def run(self):
        self._dm.disconnect(self._address)
        self.finished.emit(self._address)


class ScreenshotWorker(QThread):
    """截图操作。"""
    finished = pyqtSignal(object, float)
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str, save_path: str | None = None, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._save_path = save_path

    def run(self):
        try:
            img, elapsed = self._dm.take_screenshot(self._address, self._save_path)
            self.finished.emit(img, elapsed)
        except Exception as e:
            self.error.emit(str(e))


class BenchmarkWorker(QThread):
    """截图性能基准测试。"""
    finished = pyqtSignal(list)
    progress = pyqtSignal(int, float)
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str, rounds: int = 5, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._rounds = rounds

    def run(self):
        try:
            results: list[float] = []
            for i in range(self._rounds):
                _, elapsed = self._dm.take_screenshot(self._address)
                results.append(elapsed)
                self.progress.emit(i + 1, elapsed)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class TapWorker(QThread):
    """点击操作。"""
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str, x: int, y: int, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._x = x
        self._y = y

    def run(self):
        try:
            self._dm.tap(self._address, self._x, self._y)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class SwipeWorker(QThread):
    """滑动操作。"""
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str,
                 x1: int, y1: int, x2: int, y2: int, duration: int, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._x1, self._y1 = x1, y1
        self._x2, self._y2 = x2, y2
        self._duration = duration

    def run(self):
        try:
            self._dm.swipe(self._address, self._x1, self._y1, self._x2, self._y2, self._duration)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class KeyEventWorker(QThread):
    """按键事件。"""
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str, key: str, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._key = key

    def run(self):
        try:
            self._dm.key_event(self._address, self._key)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class ListPackagesWorker(QThread):
    """获取设备已安装应用列表。"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str,
                 third_party_only: bool = True, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._third_party_only = third_party_only

    def run(self):
        try:
            packages = self._dm.list_packages(self._address, self._third_party_only)
            self.finished.emit(packages)
        except Exception as e:
            self.error.emit(str(e))


class CheckAppAliveWorker(QThread):
    """检测应用是否在运行。"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str,
                 package_name: str, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._package = package_name

    def run(self):
        try:
            result = self._dm.is_app_running(self._address, self._package)
            result["package"] = self._package
            result["address"] = self._address
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class StartAppWorker(QThread):
    """启动指定应用。"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str,
                 package_name: str, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._package = package_name

    def run(self):
        try:
            self._dm.start_app(self._address, self._package)
            self.finished.emit(self._package)
        except Exception as e:
            self.error.emit(str(e))


class StartEmulatorAndConnectWorker(QThread):
    """启动模拟器并等待其就绪后自动连接。"""
    stage = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str, str)

    def __init__(self, device_manager: DeviceManager, address: str,
                 cap_method: str = "ADBCAP", touch_method: str = "ADBTOUCH",
                 max_wait: int = 60, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address
        self._cap_method = cap_method
        self._touch_method = touch_method
        self._max_wait = max_wait

    def run(self):
        import time
        try:
            state = self._dm.get_emulator_state(self._address)
            if state == "running":
                self.stage.emit("模拟器已运行，正在连接...")
            elif state == "starting":
                self.stage.emit("模拟器正在启动中，等待就绪...")
            else:
                self.stage.emit("模拟器未运行，正在启动...")
                ok = self._dm.start_emulator(self._address)
                if not ok:
                    self.error.emit(self._address, "无法启动模拟器（未找到 MuMuManager.exe）")
                    return

            waited = 0
            poll_interval = 3
            while waited < self._max_wait:
                st = self._dm.get_emulator_state(self._address)
                if st == "running":
                    break
                self.stage.emit(f"等待模拟器启动... ({waited}s/{self._max_wait}s)")
                time.sleep(poll_interval)
                waited += poll_interval

            if self._dm.get_emulator_state(self._address) != "running":
                self.error.emit(self._address, f"模拟器在 {self._max_wait}s 内未启动")
                return

            time.sleep(2)
            self.stage.emit("模拟器已就绪，正在连接...")
            info = self._dm.connect(self._address, self._cap_method, self._touch_method)
            self.finished.emit(info.to_dict())
        except Exception as e:
            self.error.emit(self._address, str(e))


class ConnectionHealthWorker(QThread):
    """检测设备 ADB 连接是否仍然有效。"""
    finished = pyqtSignal(str, bool)

    def __init__(self, device_manager: DeviceManager, address: str, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address

    def run(self):
        alive = self._dm.check_connection_alive(self._address)
        self.finished.emit(self._address, alive)


class DeviceInfoWorker(QThread):
    """获取设备详细信息。"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, device_manager: DeviceManager, address: str, parent=None):
        super().__init__(parent)
        self._dm = device_manager
        self._address = address

    def run(self):
        try:
            info = self._dm.refresh_device_info(self._address)
            if info:
                self.finished.emit(info.to_dict())
            else:
                self.error.emit(f"设备 {self._address} 未连接")
        except Exception as e:
            self.error.emit(str(e))
