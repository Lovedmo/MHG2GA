"""统一路径解析，兼容开发环境和 PyInstaller 打包环境。

PyInstaller 打包后 __file__ 指向临时解压目录 (_MEIPASS)，
而用户数据（config、logs、templates）需要持久化到 exe 同级目录。

规则:
  - 只读资源 (QSS/icon)      → 跟随 _MEIPASS 或源码目录
  - 可写数据 (data/assets)    → 始终在 exe 同级（或开发时项目根目录）
"""

import sys
from pathlib import Path

_frozen = getattr(sys, "frozen", False)

if _frozen:
    _BUNDLE_DIR = Path(sys._MEIPASS)
    _APP_DIR = Path(sys.executable).resolve().parent
else:
    _BUNDLE_DIR = Path(__file__).resolve().parent.parent.parent
    _APP_DIR = _BUNDLE_DIR


def get_project_root() -> Path:
    """可写的项目/应用根目录（exe 所在目录 或 开发时项目根）。"""
    return _APP_DIR


def get_bundle_root() -> Path:
    """只读资源根目录（_MEIPASS 或 开发时项目根）。"""
    return _BUNDLE_DIR


def get_resource_path(*parts: str) -> Path:
    """获取只读资源路径（QSS、icon 等）。"""
    return _BUNDLE_DIR.joinpath(*parts)


def get_data_path(*parts: str) -> Path:
    """获取可写数据路径（config、logs、db 等），自动创建父目录。"""
    p = _APP_DIR.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_assets_path(*parts: str) -> Path:
    """获取 assets 路径（模板等，可写）。"""
    return _APP_DIR.joinpath("assets", *parts)
