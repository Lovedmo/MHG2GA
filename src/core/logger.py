"""统一日志系统。

所有模块通过 get_logger() 获取 logger，日志自动流向：
1. 控制台 (stdout)
2. GUI 日志控制台（运行时可视化）
3. 文本日志文件（每次启动新建一个）

日志记录格式：
    logger.info("消息", extra={"device": "127.0.0.1:16384"})
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable


LOGGER_NAME = "mhg2ga"

from src.core.path_helper import get_data_path
LOG_DIR = get_data_path("data", "logs")

_gui_callback: Callable[[str, str, str], None] | None = None
_current_log_file: Path | None = None


class _GuiHandler(logging.Handler):
    """将日志转发到 GUI 日志控制台。"""

    def emit(self, record: logging.LogRecord) -> None:
        if _gui_callback is None:
            return
        try:
            device = getattr(record, "device", "系统")
            message = self.format(record)
            _gui_callback(record.levelname, device, message)
        except Exception:
            pass


def setup_logging(level: str = "DEBUG") -> None:
    """初始化日志系统。应在应用启动时调用一次。

    每次调用会在 data/logs/ 下新建一个以启动时间命名的日志文件。
    """
    global _current_log_file

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))

    if logger.handlers:
        return

    log_fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [%(device)s] %(message)s",
        datefmt="%H:%M:%S",
        defaults={"device": "系统"},
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(log_fmt)
    logger.addHandler(console_handler)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_filename = f"mhg2ga_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    _current_log_file = LOG_DIR / log_filename
    file_handler = logging.FileHandler(str(_current_log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_fmt)
    logger.addHandler(file_handler)

    gui_handler = _GuiHandler()
    gui_handler.setLevel(logging.DEBUG)
    gui_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(gui_handler)

    # 将 Airtest 内部日志也路由到我们的日志系统
    for airtest_name in ("airtest", "airtest.core"):
        airtest_logger = logging.getLogger(airtest_name)
        airtest_logger.handlers.clear()
        airtest_logger.propagate = False
        airtest_logger.setLevel(logging.INFO)
        airtest_logger.addHandler(console_handler)
        airtest_logger.addHandler(file_handler)
        airtest_logger.addHandler(gui_handler)


def set_gui_callback(callback: Callable[[str, str, str], None] | None) -> None:
    """注册 GUI 日志回调：callback(level, device, message)。"""
    global _gui_callback
    _gui_callback = callback


def get_log_file_path() -> Path | None:
    """获取当前日志文件路径。"""
    return _current_log_file


def get_logger(name: str = "") -> logging.Logger:
    """获取应用日志记录器。

    用法：
        logger = get_logger(__name__)
        logger.info("设备已连接", extra={"device": "127.0.0.1:16384"})
    """
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.getLogger(LOGGER_NAME)
