"""YAML 配置文件管理，支持读取、保存、合并默认值。"""

from pathlib import Path
from copy import deepcopy

import yaml

from src.core.path_helper import get_resource_path, get_data_path


DEFAULT_CONFIG_PATH = get_resource_path("src", "config", "default.yaml")
USER_CONFIG_DIR = get_data_path("data")
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个字典，override 中的值覆盖 base。"""
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_default_config() -> dict:
    """加载内置默认配置。"""
    with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_user_config() -> dict:
    """加载用户配置，与默认配置合并。用户值覆盖默认值。"""
    default = load_default_config()
    if not USER_CONFIG_PATH.exists():
        return default
    try:
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        return _deep_merge(default, user)
    except Exception:
        return default


def save_user_config(config: dict) -> None:
    """保存用户配置到文件。"""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_config_path() -> Path:
    return USER_CONFIG_PATH


DEFAULT_DEVICE_CONFIG = {
    "alias": "",
    "address": "",
    "model": "",
    "cap_method": "",
    "touch_method": "",
    "threshold": 0.0,
    "cap_interval": 0.0,
    "action_delay": 0,
    "swipe_duration": 0,
    "random_offset": 0,
    "locked_app": "",
    "auto_launch": False,
    "auto_launch_delay": 3,
    "keepalive_enabled": False,
    "keepalive_interval": 30,
    "tasks": [],
}


class AppConfig:
    """应用配置管理器，提供便捷的读写接口。"""

    def __init__(self):
        self._config: dict = load_user_config()

    def reload(self) -> None:
        self._config = load_user_config()

    def save(self) -> None:
        save_user_config(self._config)

    @property
    def raw(self) -> dict:
        return self._config

    @property
    def global_settings(self) -> dict:
        return self._config.get("global", {})

    @global_settings.setter
    def global_settings(self, value: dict) -> None:
        self._config["global"] = value

    @property
    def recognition(self) -> dict:
        return self._config.get("recognition", {})

    @recognition.setter
    def recognition(self, value: dict) -> None:
        self._config["recognition"] = value

    @property
    def devices(self) -> list[dict]:
        return self._config.get("devices", [])

    @devices.setter
    def devices(self, value: list[dict]) -> None:
        self._config["devices"] = value

    def get_device(self, address: str) -> dict | None:
        for dev in self.devices:
            if dev.get("address") == address:
                return dev
        return None

    def upsert_device(self, device_info: dict) -> None:
        """更新或插入设备配置（按 address 匹配），合并已有字段。"""
        address = device_info.get("address")
        if not address:
            return
        for i, dev in enumerate(self.devices):
            if dev.get("address") == address:
                dev.update(device_info)
                return
        self.devices.append(device_info)

    def get_device_config(self, address: str) -> dict:
        """获取设备的完整配置，未单独设置的项使用全局默认值。"""
        device = self.get_device(address) or {}
        gs = self.global_settings
        rec = self.recognition
        return {
            "alias": device.get("alias", address),
            "address": address,
            "model": device.get("model", ""),
            "cap_method": device.get("cap_method") or gs.get("default_cap_method", "ADBCAP"),
            "touch_method": device.get("touch_method") or gs.get("default_touch_method", "ADBTOUCH"),
            "threshold": device.get("threshold") or rec.get("default_threshold", 0.80),
            "cap_interval": device.get("cap_interval") or rec.get("screenshot_interval", 0.5),
            "action_delay": device.get("action_delay", 100),
            "swipe_duration": device.get("swipe_duration", 300),
            "random_offset": device.get("random_offset", 5),
            "locked_app": device.get("locked_app", ""),
            "auto_launch": device.get("auto_launch", False),
            "auto_launch_delay": device.get("auto_launch_delay", 3),
            "keepalive_enabled": device.get("keepalive_enabled", False),
            "keepalive_interval": device.get("keepalive_interval", 30),
            "tasks": device.get("tasks", []),
        }

    def update_device_field(self, address: str, **kwargs) -> None:
        """更新设备的指定字段。"""
        for dev in self.devices:
            if dev.get("address") == address:
                dev.update(kwargs)
                return
        entry = {"address": address}
        entry.update(kwargs)
        self.devices.append(entry)

    def remove_device(self, address: str) -> None:
        self._config["devices"] = [
            d for d in self.devices if d.get("address") != address
        ]
