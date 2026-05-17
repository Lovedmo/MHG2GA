"""设备管理器：封装 ADB 连接、截图、触控操作。

所有操作均通过统一日志层记录。
"""

import json
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from airtest.core.api import connect_device
from airtest.core.android.android import Android

from src.core.logger import get_logger

logger = get_logger("device_manager")

MUMU12_ADB_CANDIDATES = [
    r"D:\MuMu Player 12\shell\adb.exe",
    r"C:\Program Files\MuMu Player 12\shell\adb.exe",
    r"C:\Program Files (x86)\MuMu Player 12\shell\adb.exe",
]

MUMU12_PORTS = [16384 + i * 32 for i in range(32)]


@dataclass
class DeviceInfo:
    address: str
    alias: str = ""
    model: str = ""
    resolution: str = ""
    dpi: str = ""
    android_version: str = ""
    sdk_version: str = ""
    cpu_abi: str = ""
    foreground_app: str = ""
    status: str = "disconnected"

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "alias": self.alias or self.address,
            "model": self.model or "--",
            "resolution": self.resolution or "--",
            "dpi": self.dpi or "--",
            "android_version": self.android_version or "--",
            "sdk_version": self.sdk_version or "--",
            "cpu_abi": self.cpu_abi or "--",
            "foreground_app": self.foreground_app or "--",
            "status": self.status,
        }


class DeviceManager:
    """管理多个 Android 设备/模拟器的连接和操作。"""

    def __init__(self, adb_path: str = "", mumu_manager_path: str = ""):
        self._adb_path = adb_path or self._find_adb()
        self._mumu_manager = self._validate_path(mumu_manager_path)
        self._devices: dict[str, Android] = {}
        self._device_info: dict[str, DeviceInfo] = {}
        logger.info("DeviceManager 初始化完成，ADB 路径: %s", self._adb_path)
        if self._mumu_manager:
            logger.info("MuMu Manager 路径: %s", self._mumu_manager)
        else:
            logger.debug("未配置 MuMu Manager 路径，模拟器自动启动功能不可用")

    def _find_adb(self) -> str:
        import shutil
        path = shutil.which("adb")
        if path:
            logger.debug("在 PATH 中找到 ADB: %s", path)
            return path
        for candidate in MUMU12_ADB_CANDIDATES:
            if Path(candidate).exists():
                logger.debug("在常用路径找到 ADB: %s", candidate)
                return candidate
        logger.warning("未找到 ADB，使用默认 'adb'")
        return "adb"

    @staticmethod
    def _validate_path(path: str) -> str | None:
        if path and Path(path).exists():
            return path
        return None

    def set_mumu_manager_path(self, path: str) -> None:
        """动态更新 MuMu Manager 路径。"""
        self._mumu_manager = self._validate_path(path)
        if self._mumu_manager:
            logger.info("MuMu Manager 路径已更新: %s", self._mumu_manager)
        else:
            logger.debug("MuMu Manager 路径已清除")

    @staticmethod
    def mumu_port_to_index(port: int) -> int | None:
        """MuMu 12 端口号转实例索引。16384 → 0, 16416 → 1, ..."""
        if port < 16384 or (port - 16384) % 32 != 0:
            return None
        idx = (port - 16384) // 32
        return idx if 0 <= idx < 32 else None

    # ---- MuMu Manager 命令调用 ----

    def _run_mumu_cmd(self, args: list[str], timeout: int = 10) -> dict | list | str | None:
        """执行 MuMuManager.exe 命令。

        尝试将输出解析为 JSON；若非 JSON 则返回原始字符串；失败返回 None。
        """
        if not self._mumu_manager:
            return None
        cmd = [self._mumu_manager] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace",
            )
            output = result.stdout.strip()
            if not output:
                return ""
            try:
                return json.loads(output)
            except (json.JSONDecodeError, ValueError):
                return output
        except subprocess.TimeoutExpired:
            logger.warning("MuMu Manager 命令超时: %s", cmd)
            return None
        except Exception as e:
            logger.debug("MuMu Manager 命令失败: %s → %s", cmd, e)
            return None

    def _get_mumu_index(self, address: str) -> int | None:
        """从 ADB 地址获取 MuMu 实例索引。"""
        port = self._parse_port(address)
        if port is None:
            return None
        return self.mumu_port_to_index(port)

    def get_emulator_info(self, address: str) -> dict | None:
        """通过 MuMuManager.exe info 获取模拟器详细信息。

        Returns:
            包含 index, name, pid, is_process_started, is_android_started,
            adb_host_ip, adb_port 等字段的字典，或 None。
        """
        idx = self._get_mumu_index(address)
        if idx is None:
            return None
        result = self._run_mumu_cmd(["info", "-v", str(idx)])
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        if isinstance(result, dict):
            return result
        logger.debug("MuMu info 返回非预期格式: %r", result, extra={"device": address})
        return None

    def get_all_emulator_info(self) -> list[dict]:
        """获取所有 MuMu 模拟器实例信息。"""
        result = self._run_mumu_cmd(["info", "-v", "all"])
        if isinstance(result, list):
            return result
        return []

    def get_emulator_state(self, address: str) -> str:
        """获取模拟器实例状态。

        通过 MuMuManager info 命令的 JSON 返回值判断：
        - is_android_started=true → "running"
        - is_process_started=true 但 android 未就绪 → "starting"
        - 均为 false → "stopped"
        - 无 MuMu Manager 时回退到 TCP 端口探测。

        Returns:
            "running" | "starting" | "stopped" | "unknown"
        """
        if not self._mumu_manager:
            return self._check_port_alive(address)

        info = self.get_emulator_info(address)
        if info is not None:
            logger.debug("MuMu info: %s", info, extra={"device": address})
            if info.get("is_android_started"):
                return "running"
            elif info.get("is_process_started"):
                return "starting"
            else:
                return "stopped"

        return self._check_port_alive(address)

    def start_emulator(self, address: str, with_package: str = "") -> bool:
        """启动 MuMu 模拟器实例。

        使用新版命令: MuMuManager.exe control -v {idx} launch [-pkg ...]

        Args:
            address: 设备 ADB 地址
            with_package: 可选，启动后自动打开指定应用

        Returns:
            True 如果命令已成功发出。
        """
        if not self._mumu_manager:
            logger.warning("未配置 MuMuManager.exe 路径，无法自动启动模拟器")
            return False

        idx = self._get_mumu_index(address)
        if idx is None:
            port = self._parse_port(address)
            logger.warning("无法获取 MuMu 实例索引 (地址=%s, 端口=%s)", address, port)
            return False

        args = ["control", "-v", str(idx), "launch"]
        if with_package:
            args += ["-pkg", with_package]

        logger.info("正在启动 MuMu 实例 %d...", idx, extra={"device": address})
        result = self._run_mumu_cmd(args, timeout=15)
        if result is not None:
            logger.info("启动命令已发出 (实例 %d)", idx, extra={"device": address})
            return True
        logger.error("启动模拟器失败", extra={"device": address})
        return False

    def stop_emulator(self, address: str) -> bool:
        """关闭 MuMu 模拟器实例。

        使用命令: MuMuManager.exe control -v {idx} shutdown
        """
        if not self._mumu_manager:
            logger.warning("未配置 MuMuManager.exe 路径，无法关闭模拟器")
            return False

        idx = self._get_mumu_index(address)
        if idx is None:
            return False

        logger.info("正在关闭 MuMu 实例 %d...", idx, extra={"device": address})
        result = self._run_mumu_cmd(["control", "-v", str(idx), "shutdown"], timeout=15)
        if result is not None:
            logger.info("关闭命令已发出 (实例 %d)", idx, extra={"device": address})
            return True
        logger.error("关闭模拟器失败", extra={"device": address})
        return False

    def check_connection_alive(self, address: str) -> bool:
        """检测设备 ADB 连接是否仍然有效。"""
        dev = self._devices.get(address)
        if not dev:
            return False
        try:
            output = dev.shell("echo alive")
            text = output if isinstance(output, str) else output.decode()
            return "alive" in text
        except Exception:
            return False

    def _check_port_alive(self, address: str) -> str:
        """通过 TCP 套接字直接检测端口是否可达（避免 ADB 缓存误判）。"""
        port = self._parse_port(address)
        host = address.split(":")[0] if ":" in address else "127.0.0.1"
        if port is None:
            return "unknown"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return "running"
        except Exception:
            pass
        return "stopped"

    @staticmethod
    def _parse_port(address: str) -> int | None:
        if ":" in address:
            try:
                return int(address.split(":")[-1])
            except ValueError:
                pass
        return None

    def scan_devices(self) -> list[DeviceInfo]:
        """扫描所有可用设备。

        优先使用 MuMuManager info -v all 获取所有模拟器实例（速度快），
        再补充 adb devices 发现的非 MuMu 设备。
        """
        logger.info("开始扫描设备...")
        found: list[DeviceInfo] = []
        seen: set[str] = set()

        if self._mumu_manager:
            all_info = self.get_all_emulator_info()
            for emu in all_info:
                adb_port = emu.get("adb_port")
                adb_host = emu.get("adb_host_ip", "127.0.0.1")
                idx = emu.get("index", -1)
                name = emu.get("name", "")
                is_running = emu.get("is_android_started", False)

                if adb_port:
                    addr = f"{adb_host}:{adb_port}"
                else:
                    addr = f"127.0.0.1:{16384 + idx * 32}"

                if addr in seen:
                    continue
                seen.add(addr)

                status = "detected" if is_running else "stopped"
                info = DeviceInfo(address=addr, alias=name or addr, status=status)
                found.append(info)
                logger.debug(
                    "通过 MuMu Manager 发现: %s (实例%d, %s, %s)",
                    addr, idx, name, status,
                )
            if found:
                logger.info("MuMu Manager 发现 %d 个实例", len(found))

        try:
            result = subprocess.run(
                [self._adb_path, "devices"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().splitlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == "device":
                    addr = parts[0]
                    if addr not in seen:
                        seen.add(addr)
                        found.append(DeviceInfo(address=addr, status="detected"))
                        logger.debug("通过 adb devices 发现: %s", addr)
        except Exception as e:
            logger.error("执行 adb devices 失败: %s", e)

        if not self._mumu_manager:
            for port in MUMU12_PORTS:
                addr = f"127.0.0.1:{port}"
                if addr in seen:
                    continue
                if self._check_port_alive(addr) == "running":
                    seen.add(addr)
                    found.append(DeviceInfo(address=addr, status="detected"))
                    logger.debug("通过端口扫描发现: %s", addr)

        logger.info("扫描完成，共发现 %d 个设备", len(found))
        return found

    def connect(self, address: str, cap_method: str = "ADBCAP",
                touch_method: str = "ADBTOUCH") -> DeviceInfo:
        """连接到指定设备。"""
        if address in self._devices:
            logger.debug("设备 %s 已连接，跳过", extra={"device": address})
            info = self._device_info[address]
            info.status = "connected"
            return info

        logger.info("正在连接设备 (cap=%s, touch=%s)...",
                    cap_method, touch_method, extra={"device": address})
        uri = f"Android:///{address}?ori_method=ADBORI"
        try:
            dev = connect_device(uri)
            self._devices[address] = dev
            logger.info("ADB 连接成功", extra={"device": address})

            self.set_cap_method(address, cap_method)
            self.set_touch_method(address, touch_method)

            info = self._query_device_info(address, dev)
            info.status = "connected"
            self._device_info[address] = info
            logger.info(
                "设备信息: 型号=%s 分辨率=%s 安卓=%s",
                info.model, info.resolution, info.android_version,
                extra={"device": address},
            )
            return info
        except Exception as e:
            logger.error("连接失败: %s", e, extra={"device": address})
            raise ConnectionError(f"连接设备 {address} 失败: {e}")

    def disconnect(self, address: str) -> None:
        """断开设备连接。"""
        if address in self._devices:
            try:
                self._devices[address].disconnect()
            except Exception:
                pass
            del self._devices[address]
            logger.info("已断开连接", extra={"device": address})
        if address in self._device_info:
            self._device_info[address].status = "disconnected"

    def is_connected(self, address: str) -> bool:
        return address in self._devices

    def get_device(self, address: str) -> Android | None:
        return self._devices.get(address)

    def set_cap_method(self, address: str, method: str) -> None:
        """运行时切换截图方式，绕过 Airtest 有 bug 的 setter。"""
        dev = self._devices.get(address)
        if not dev:
            logger.warning("设备未连接，无法切换截图方式", extra={"device": address})
            return
        try:
            from airtest.core.android.cap_methods.screen_proxy import ScreenProxy
            if dev._screen_proxy:
                try:
                    dev._screen_proxy.teardown_stream()
                except (NotImplementedError, AttributeError):
                    pass
            dev._screen_proxy = ScreenProxy.auto_setup(
                dev.adb,
                default_method=method.upper(),
                rotation_watcher=dev.rotation_watcher,
                display_id=dev.display_id,
                ori_function=lambda: dev.display_info,
            )
            logger.info("截图方式已切换为: %s", method, extra={"device": address})
        except Exception as e:
            logger.warning("截图方式切换失败: %s", e, extra={"device": address})

    def set_touch_method(self, address: str, method: str) -> None:
        """运行时切换触控方式，绕过 Airtest 有 bug 的 setter。"""
        dev = self._devices.get(address)
        if not dev:
            logger.warning("设备未连接，无法切换触控方式", extra={"device": address})
            return
        try:
            from airtest.core.android.touch_methods.touch_proxy import TouchProxy
            if dev._touch_proxy:
                try:
                    dev._touch_proxy.teardown()
                except (NotImplementedError, AttributeError):
                    pass
            dev._touch_proxy = TouchProxy.auto_setup(
                dev.adb,
                default_method=method.upper(),
                ori_transformer=dev._touch_point_by_orientation,
                size_info=dev.display_info,
                input_event=dev.input_event,
            )
            logger.info("触控方式已切换为: %s", method, extra={"device": address})
        except Exception as e:
            logger.warning("触控方式切换失败: %s", e, extra={"device": address})

    def _query_device_info(self, address: str, dev: Android) -> DeviceInfo:
        logger.debug("正在查询设备信息...", extra={"device": address})
        info = DeviceInfo(address=address)

        def _shell(cmd: str) -> str:
            try:
                out = dev.shell(cmd)
                return out.strip() if isinstance(out, str) else out.decode().strip()
            except Exception:
                return ""

        try:
            w, h = dev.get_current_resolution()
            info.resolution = f"{w}x{h}"
        except Exception as e:
            logger.warning("获取分辨率失败: %s", e, extra={"device": address})

        info.model = _shell("getprop ro.product.model")
        info.dpi = _shell("getprop ro.sf.lcd_density") or _shell("wm density").split(":")[-1].strip()
        info.android_version = _shell("getprop ro.build.version.release")
        info.sdk_version = _shell("getprop ro.build.version.sdk")
        info.cpu_abi = _shell("getprop ro.product.cpu.abi")

        try:
            fg = _shell("dumpsys activity activities | grep mResumedActivity")
            if "/" in fg:
                for p in fg.split():
                    if "/" in p:
                        info.foreground_app = p.rstrip("}")
                        break
        except Exception:
            pass

        return info

    def get_device_info(self, address: str) -> DeviceInfo | None:
        return self._device_info.get(address)

    def refresh_device_info(self, address: str) -> DeviceInfo | None:
        dev = self._devices.get(address)
        if not dev:
            logger.warning("设备未连接，无法刷新信息", extra={"device": address})
            return None
        logger.info("正在刷新设备信息...", extra={"device": address})
        info = self._query_device_info(address, dev)
        info.status = "connected"
        self._device_info[address] = info
        return info

    # ---- 截图 ----

    @staticmethod
    def _get_cap_method_name(dev: Android) -> str:
        """获取设备当前实际使用的截图方式名称。"""
        try:
            from airtest.core.android.constant import CAP_METHOD
            cap = dev.cap_method
            for name in ("MINICAP", "JAVACAP", "ADBCAP"):
                if cap == getattr(CAP_METHOD, name, None):
                    return name
            return f"UNKNOWN({cap})"
        except Exception:
            return "UNKNOWN"

    def get_orientation(self, address: str, silent: bool = False) -> int:
        """获取设备屏幕方向 (0=竖屏, 1=横屏左, 2=倒置, 3=横屏右)。"""
        dev = self._devices.get(address)
        if not dev:
            return 0
        try:
            info = dev.display_info
            orientation = info.get("orientation", 0)
            if not silent:
                logger.debug("设备方向: %d", orientation, extra={"device": address})
            return orientation
        except Exception:
            return 0

    def take_screenshot(self, address: str, save_path: str | None = None,
                         silent: bool = False) -> tuple[np.ndarray | None, float]:
        dev = self._devices.get(address)
        if not dev:
            logger.error("截图失败：设备未连接", extra={"device": address})
            raise RuntimeError(f"设备 {address} 未连接")

        if not silent:
            logger.debug("正在截图...", extra={"device": address})
        start = time.perf_counter()
        try:
            screen = dev.snapshot()
            elapsed = (time.perf_counter() - start) * 1000

            if screen is None:
                logger.warning("截图返回空数据", extra={"device": address})
                return None, elapsed

            orientation = self.get_orientation(address, silent=silent)
            if orientation == 1:
                screen = cv2.rotate(screen, cv2.ROTATE_90_CLOCKWISE)

            if not silent:
                h, w = screen.shape[:2]
                cap_name = self._get_cap_method_name(dev)
                logger.info("截图成功: %dx%d, 方式=%s, orientation=%d, %.0fms",
                            w, h, cap_name, orientation, elapsed, extra={"device": address})

            if save_path:
                cv2.imwrite(save_path, screen)
                logger.debug("截图已保存: %s", save_path, extra={"device": address})

            return screen, elapsed
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("截图失败: %s (%.0fms)", e, elapsed, extra={"device": address})
            raise RuntimeError(f"截图失败: {e}")

    def screenshot_benchmark(self, address: str, rounds: int = 5) -> list[float]:
        logger.info("开始截图基准测试 (%d 轮)...", rounds, extra={"device": address})
        results: list[float] = []
        for i in range(rounds):
            _, elapsed = self.take_screenshot(address)
            results.append(elapsed)
            logger.debug("第 %d/%d 轮: %.0fms", i + 1, rounds, elapsed, extra={"device": address})

        avg = sum(results) / len(results)
        logger.info("基准测试完成: 平均 %.0fms (最小 %.0f, 最大 %.0f)",
                     avg, min(results), max(results), extra={"device": address})
        return results

    # ---- 触控 ----

    @staticmethod
    def _get_touch_method_name(dev: Android) -> str:
        """获取设备当前实际使用的触控方式名称。"""
        try:
            from airtest.core.android.constant import TOUCH_METHOD
            touch = dev.touch_method
            for name in ("MINITOUCH", "MAXTOUCH", "ADBTOUCH"):
                if touch == getattr(TOUCH_METHOD, name, None):
                    return name
            return f"UNKNOWN({touch})"
        except Exception:
            return "UNKNOWN"

    def tap(self, address: str, x: int, y: int) -> None:
        dev = self._devices.get(address)
        if not dev:
            logger.error("点击失败：设备未连接", extra={"device": address})
            raise RuntimeError(f"设备 {address} 未连接")
        touch_name = self._get_touch_method_name(dev)
        logger.info("点击 (%d, %d), 方式=%s", x, y, touch_name, extra={"device": address})
        dev.touch((x, y))
        logger.debug("点击完成", extra={"device": address})

    def swipe(self, address: str, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> None:
        dev = self._devices.get(address)
        if not dev:
            logger.error("滑动失败：设备未连接", extra={"device": address})
            raise RuntimeError(f"设备 {address} 未连接")
        touch_name = self._get_touch_method_name(dev)
        logger.info("滑动 (%d,%d)->(%d,%d) duration=%dms, 方式=%s",
                    x1, y1, x2, y2, duration, touch_name, extra={"device": address})
        dev.swipe((x1, y1), (x2, y2), duration=duration / 1000.0)
        logger.debug("滑动完成", extra={"device": address})

    def key_event(self, address: str, key: str) -> None:
        dev = self._devices.get(address)
        if not dev:
            logger.error("按键失败：设备未连接", extra={"device": address})
            raise RuntimeError(f"设备 {address} 未连接")
        logger.info("发送按键: %s", key, extra={"device": address})
        dev.keyevent(key)
        logger.debug("按键完成", extra={"device": address})

    def get_resolution(self, address: str) -> tuple[int, int] | None:
        dev = self._devices.get(address)
        if not dev:
            return None
        try:
            res = dev.get_current_resolution()
            logger.debug("获取分辨率: %s", res, extra={"device": address})
            return res
        except Exception as e:
            logger.warning("获取分辨率失败: %s", e, extra={"device": address})
            return None

    # ---- 模板匹配 ----

    @staticmethod
    def _prepare_source(screenshot, roi):
        """准备搜索源图和 ROI 偏移。"""
        if screenshot is None or screenshot.size == 0:
            return None, (0, 0)
        source = screenshot
        roi_offset = (0, 0)
        if roi and len(roi) == 4:
            rx, ry, rw, rh = roi
            sh, sw = screenshot.shape[:2]
            rx, ry = max(0, rx), max(0, ry)
            rw = min(rw, sw - rx)
            rh = min(rh, sh - ry)
            if rw <= 0 or rh <= 0:
                return None, (0, 0)
            source = screenshot[ry:ry + rh, rx:rx + rw]
            roi_offset = (rx, ry)
        if source.size == 0:
            return None, (0, 0)
        return source, roi_offset

    @staticmethod
    def match_template(
        screenshot: np.ndarray,
        template: np.ndarray,
        threshold: float = 0.80,
        rgb: bool = True,
        roi: list[int] | None = None,
        click_offset: list[int] | None = None,
        mask: np.ndarray | None = None,
        match_mode: str = "normal",
    ) -> dict | None:
        """在截图中查找模板的最佳匹配位置。

        Args:
            screenshot: BGR 截图
            template: BGR 模板图
            threshold: 最低置信度
            rgb: 是否启用颜色校验
            roi: 搜索区域 [x, y, w, h]，None 表示全屏
            click_offset: 点击点偏移 [ox, oy] 相对于模板左上角，None 则用中心
            mask: 模板蒙版（灰度/二值），白色区域参与匹配，黑色忽略
            match_mode: "normal" | "mask" | "edge"

        Returns:
            匹配成功返回 {"center": (x,y), "click_point": (x,y), "rect": (x,y,w,h), "confidence": float}
            匹配失败返回 None
        """
        if template is None or template.size == 0:
            return None

        source, roi_offset = DeviceManager._prepare_source(screenshot, roi)
        if source is None:
            return None

        src_gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        if src_gray.shape[0] < tpl_gray.shape[0] or src_gray.shape[1] < tpl_gray.shape[1]:
            return None

        th, tw = template.shape[:2]

        if match_mode == "edge":
            src_match = cv2.Canny(src_gray, 50, 150)
            tpl_match = cv2.Canny(tpl_gray, 50, 150)
            res = cv2.matchTemplate(src_match, tpl_match, cv2.TM_CCOEFF_NORMED)
        elif match_mode == "mask" and mask is not None and mask.shape[:2] == tpl_gray.shape[:2]:
            res = cv2.matchTemplate(src_gray, tpl_gray, cv2.TM_CCORR_NORMED, mask=mask)
        else:
            res = cv2.matchTemplate(src_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)

        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        confidence = max_val
        if match_mode == "normal" and rgb and confidence >= threshold * 0.8:
            crop = source[max_loc[1]:max_loc[1] + th, max_loc[0]:max_loc[0] + tw]
            if crop.shape[:2] == template.shape[:2]:
                src_hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                tpl_hsv = cv2.cvtColor(template, cv2.COLOR_BGR2HSV)
                channels_conf = []
                for i in range(3):
                    r = cv2.matchTemplate(src_hsv[:, :, i], tpl_hsv[:, :, i], cv2.TM_CCOEFF_NORMED)
                    channels_conf.append(cv2.minMaxLoc(r)[1])
                confidence = min(channels_conf)

        if confidence < threshold:
            return None

        cx = max_loc[0] + tw // 2 + roi_offset[0]
        cy = max_loc[1] + th // 2 + roi_offset[1]
        rect_x = max_loc[0] + roi_offset[0]
        rect_y = max_loc[1] + roi_offset[1]

        if click_offset and len(click_offset) == 2:
            cpx = rect_x + click_offset[0]
            cpy = rect_y + click_offset[1]
        else:
            cpx, cpy = cx, cy

        return {
            "center": (cx, cy),
            "click_point": (cpx, cpy),
            "rect": (rect_x, rect_y, tw, th),
            "confidence": round(confidence, 4),
        }

    @staticmethod
    def match_template_all(
        screenshot: np.ndarray,
        template: np.ndarray,
        threshold: float = 0.80,
        rgb: bool = True,
        roi: list[int] | None = None,
        click_offset: list[int] | None = None,
        mask: np.ndarray | None = None,
        match_mode: str = "normal",
        max_count: int = 20,
    ) -> list[dict]:
        """查找所有匹配位置。"""
        if template is None or template.size == 0:
            return []

        source, roi_offset = DeviceManager._prepare_source(screenshot, roi)
        if source is None:
            return []

        src_gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        if src_gray.shape[0] < tpl_gray.shape[0] or src_gray.shape[1] < tpl_gray.shape[1]:
            return []

        if match_mode == "edge":
            src_match = cv2.Canny(src_gray, 50, 150)
            tpl_match = cv2.Canny(tpl_gray, 50, 150)
            res = cv2.matchTemplate(src_match, tpl_match, cv2.TM_CCOEFF_NORMED)
        elif match_mode == "mask" and mask is not None and mask.shape[:2] == tpl_gray.shape[:2]:
            res = cv2.matchTemplate(src_gray, tpl_gray, cv2.TM_CCORR_NORMED, mask=mask)
        else:
            res = cv2.matchTemplate(src_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
        th, tw = template.shape[:2]
        results = []

        while len(results) < max_count:
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val < threshold:
                break

            confidence = max_val
            if match_mode == "normal" and rgb:
                crop = source[max_loc[1]:max_loc[1] + th, max_loc[0]:max_loc[0] + tw]
                if crop.shape[:2] == template.shape[:2]:
                    src_hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                    tpl_hsv = cv2.cvtColor(template, cv2.COLOR_BGR2HSV)
                    channels_conf = []
                    for i in range(3):
                        r = cv2.matchTemplate(src_hsv[:, :, i], tpl_hsv[:, :, i], cv2.TM_CCOEFF_NORMED)
                        channels_conf.append(cv2.minMaxLoc(r)[1])
                    confidence = min(channels_conf)

            if confidence >= threshold:
                cx = max_loc[0] + tw // 2 + roi_offset[0]
                cy = max_loc[1] + th // 2 + roi_offset[1]
                rect_x = max_loc[0] + roi_offset[0]
                rect_y = max_loc[1] + roi_offset[1]
                if click_offset and len(click_offset) == 2:
                    cpx = rect_x + click_offset[0]
                    cpy = rect_y + click_offset[1]
                else:
                    cpx, cpy = cx, cy
                results.append({
                    "center": (cx, cy),
                    "click_point": (cpx, cpy),
                    "rect": (rect_x, rect_y, tw, th),
                    "confidence": round(confidence, 4),
                })

            cv2.rectangle(res,
                          (max_loc[0] - tw // 2, max_loc[1] - th // 2),
                          (max_loc[0] + tw // 2, max_loc[1] + th // 2),
                          0, -1)

        return results

    @staticmethod
    def draw_match_results(
        screenshot: np.ndarray,
        results: list[dict],
        color: tuple = (0, 255, 0),
        thickness: int = 2,
    ) -> np.ndarray:
        """在截图上绘制匹配结果标注，返回标注后的图像副本。"""
        annotated = screenshot.copy()
        for i, r in enumerate(results):
            rx, ry, rw, rh = r["rect"]
            cv2.rectangle(annotated, (rx, ry), (rx + rw, ry + rh), color, thickness)

            cx, cy = r["center"]
            cv2.drawMarker(annotated, (cx, cy), (0, 255, 0),
                           cv2.MARKER_CROSS, 16, 1)

            cp = r.get("click_point")
            if cp and cp != (cx, cy):
                cpx, cpy = cp
                cv2.drawMarker(annotated, (cpx, cpy), (0, 0, 255),
                               cv2.MARKER_CROSS, 20, 2)
                cv2.circle(annotated, (cpx, cpy), 8, (0, 0, 255), 1)
            else:
                cv2.drawMarker(annotated, (cx, cy), (0, 0, 255),
                               cv2.MARKER_CROSS, 20, 2)

            label = f'#{i + 1} {r["confidence"]:.2f}'
            font_scale = 0.5
            label_y = ry - 8 if ry > 20 else ry + rh + 16
            cv2.putText(annotated, label, (rx, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 1, cv2.LINE_AA)

        return annotated

    # ---- 应用管理 ----

    def list_packages(self, address: str, third_party_only: bool = True) -> list[str]:
        """获取设备上已安装的应用包名列表。"""
        dev = self._devices.get(address)
        if not dev:
            logger.error("获取应用列表失败：设备未连接", extra={"device": address})
            raise RuntimeError(f"设备 {address} 未连接")

        logger.info("正在获取应用列表...", extra={"device": address})
        try:
            flag = "-3" if third_party_only else ""
            output = dev.shell(f"pm list packages {flag}".strip())
            if isinstance(output, bytes):
                output = output.decode()
            packages = sorted(
                line.replace("package:", "").strip()
                for line in output.splitlines()
                if line.strip().startswith("package:")
            )
            logger.info("获取到 %d 个应用", len(packages), extra={"device": address})
            return packages
        except Exception as e:
            logger.error("获取应用列表失败: %s", e, extra={"device": address})
            raise RuntimeError(f"获取应用列表失败: {e}")

    def start_app(self, address: str, package_name: str) -> None:
        """启动指定应用。"""
        dev = self._devices.get(address)
        if not dev:
            logger.error("启动应用失败：设备未连接", extra={"device": address})
            raise RuntimeError(f"设备 {address} 未连接")

        logger.info("正在启动应用: %s", package_name, extra={"device": address})
        try:
            output = dev.shell(
                f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
            )
            if isinstance(output, bytes):
                output = output.decode()
            if "No activities found" in output:
                raise RuntimeError(f"应用 {package_name} 没有可启动的 Activity")
            logger.info("应用已启动: %s", package_name, extra={"device": address})
        except RuntimeError:
            raise
        except Exception as e:
            logger.error("启动应用失败: %s", e, extra={"device": address})
            raise RuntimeError(f"启动应用失败: {e}")

    def is_app_running(self, address: str, package_name: str) -> dict:
        """检测指定应用是否正在运行。

        Returns:
            {"running": bool, "foreground": bool, "pid": str}
        """
        dev = self._devices.get(address)
        if not dev:
            raise RuntimeError(f"设备 {address} 未连接")

        result = {"running": False, "foreground": False, "pid": ""}

        def _shell(cmd: str) -> str:
            out = dev.shell(cmd)
            return out.strip() if isinstance(out, str) else out.decode().strip()

        try:
            ps_out = _shell(f"pidof {package_name}")
            if ps_out and ps_out.strip():
                result["running"] = True
                result["pid"] = ps_out.strip().split()[0]
        except Exception:
            pass

        try:
            fg_out = _shell("dumpsys activity activities | grep mResumedActivity")
            if package_name in fg_out:
                result["foreground"] = True
                result["running"] = True
        except Exception:
            pass

        logger.debug(
            "探活 %s: running=%s foreground=%s pid=%s",
            package_name, result["running"], result["foreground"], result["pid"],
            extra={"device": address},
        )
        return result

    def stop_app(self, address: str, package_name: str) -> None:
        """强制停止指定应用。"""
        dev = self._devices.get(address)
        if not dev:
            raise RuntimeError(f"设备 {address} 未连接")
        logger.info("正在停止应用: %s", package_name, extra={"device": address})
        try:
            dev.shell(f"am force-stop {package_name}")
            logger.info("应用已停止: %s", package_name, extra={"device": address})
        except Exception as e:
            logger.error("停止应用失败: %s", e, extra={"device": address})
            raise RuntimeError(f"停止应用失败: {e}")

    def disconnect_all(self) -> None:
        logger.info("正在断开所有设备...")
        for addr in list(self._devices.keys()):
            self.disconnect(addr)
        logger.info("所有设备已断开")
