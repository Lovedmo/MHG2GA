"""任务模型：工作流（Task）由多个步骤（Step）组成，支持 YAML 持久化。

步骤类型:
    check   — 条件判断（类似 if），验证模板是否存在于当前画面
    whileif — 循环判断（类似 while），条件成立时循环执行子步骤
    click   — 检测模板并点击匹配位置
    delay   — 步骤间延时等待

存储结构:
    data/tasks.yaml       — 任务索引（name, description, enabled）
    data/tasks/<name>.yaml — 各任务的详细步骤定义
"""

from copy import deepcopy
from pathlib import Path

import yaml

from src.core.logger import get_logger

logger = get_logger("task_model")

from src.core.path_helper import get_data_path
_DATA_DIR = get_data_path("data")

STEP_TYPES = ["check", "whileif", "click", "delay"]

STEP_TYPE_LABELS = {
    "check": "条件",
    "whileif": "循环",
    "click": "点击",
    "delay": "延时",
}

DEFAULT_STEPS: dict[str, dict] = {
    "check": {
        "type": "check",
        "template": "",
        "description": "",
        "retry_enabled": False,
        "retry_interval_ms": 1000,
        "timeout_mode": "time",
        "max_timeout_ms": 30000,
        "max_retries": 10,
        "on_fail": "stop",
        "children": [],
    },
    "whileif": {
        "type": "whileif",
        "template": "",
        "description": "",
        "check_interval_ms": 1000,
        "timeout_mode": "time",
        "max_timeout_ms": 1000,
        "max_loops": 2,
        "children": [],
    },
    "click": {
        "type": "click",
        "template": "",
        "description": "",
        "touch_duration_ms": 50,
        "after_delay_ms": 200,
        "on_fail": "stop",
    },
    "delay": {
        "type": "delay",
        "duration_ms": 1000,
        "description": "",
    },
}

CONTAINER_TYPES = {"check", "whileif"}


def count_steps_recursive(steps: list[dict]) -> int:
    """递归统计步骤总数（含 children）。"""
    total = 0
    for s in steps:
        total += 1
        if s.get("type") in CONTAINER_TYPES:
            total += count_steps_recursive(s.get("children", []))
    return total


class TaskManager:
    """管理工作流任务的加载、保存和增删改查。

    索引文件: data/tasks.yaml — [{name, description, enabled}, ...]
    步骤文件: data/tasks/<name>.yaml — {steps: [...]}
    """

    def __init__(self, data_dir: Path | None = None):
        self._dir = data_dir or _DATA_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._tasks_dir = self._dir / "tasks"
        self._tasks_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._dir / "tasks.yaml"
        self._index: list[dict] = []
        self._load_index()

    # ─── 索引操作 ───

    def _load_index(self) -> None:
        if self._index_file.exists():
            try:
                with open(self._index_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                raw = data.get("tasks", data) if isinstance(data, dict) else data
                if not isinstance(raw, list):
                    raw = []
                self._index = []
                migrated = False
                for t in raw:
                    if not isinstance(t, dict) or "name" not in t:
                        continue
                    self._index.append({
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "enabled": t.get("enabled", False),
                    })
                    if "steps" in t and t["steps"]:
                        task_file = self._task_file(t["name"])
                        if not task_file.exists():
                            self._save_steps(t["name"], t["steps"])
                            migrated = True
                if migrated:
                    self._save_index()
                    logger.info("已自动迁移旧格式任务步骤到独立文件")
                logger.info("加载了 %d 个任务索引", len(self._index))
            except Exception as e:
                logger.warning("加载任务索引失败: %s", e)
                self._index = []
        else:
            self._index = []

    def _save_index(self) -> None:
        with open(self._index_file, "w", encoding="utf-8") as f:
            yaml.dump(
                {"tasks": self._index},
                f, allow_unicode=True, default_flow_style=False, sort_keys=False,
            )

    # ─── 步骤文件操作 ───

    def _task_file(self, name: str) -> Path:
        safe = name.replace("/", "_").replace("\\", "_")
        return self._tasks_dir / f"{safe}.yaml"

    def _load_steps(self, name: str) -> list[dict]:
        f = self._task_file(name)
        if f.exists():
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = yaml.safe_load(fp) or {}
                return data.get("steps", [])
            except Exception as e:
                logger.warning("加载任务步骤失败 [%s]: %s", name, e)
        return []

    def _save_steps(self, name: str, steps: list[dict]) -> None:
        f = self._task_file(name)
        with open(f, "w", encoding="utf-8") as fp:
            yaml.dump(
                {"steps": steps},
                fp, allow_unicode=True, default_flow_style=False, sort_keys=False,
            )

    # ─── 公开接口 ───

    @property
    def tasks(self) -> list[dict]:
        """返回完整的任务列表（含 steps），兼容旧的调用方式。"""
        result = []
        for entry in self._index:
            task = dict(entry)
            task["steps"] = self._load_steps(entry["name"])
            result.append(task)
        return result

    def get_task_names(self) -> list[str]:
        return [t["name"] for t in self._index]

    def get_task(self, name: str) -> dict | None:
        for entry in self._index:
            if entry["name"] == name:
                task = dict(entry)
                task["steps"] = self._load_steps(name)
                return task
        return None

    def add_task(self, task: dict) -> None:
        """添加或替换同名任务。"""
        name = task["name"]
        self._index = [t for t in self._index if t["name"] != name]
        self._index.append({
            "name": name,
            "description": task.get("description", ""),
            "enabled": task.get("enabled", False),
        })
        self._save_index()
        self._save_steps(name, task.get("steps", []))
        logger.debug("任务已保存: %s", name)

    def remove_task(self, name: str) -> bool:
        before = len(self._index)
        self._index = [t for t in self._index if t["name"] != name]
        if len(self._index) < before:
            self._save_index()
            f = self._task_file(name)
            if f.exists():
                f.unlink()
            return True
        return False

    def rename_task(self, old_name: str, new_name: str) -> bool:
        if any(t["name"] == new_name for t in self._index):
            return False
        for entry in self._index:
            if entry["name"] == old_name:
                steps = self._load_steps(old_name)
                old_file = self._task_file(old_name)
                if old_file.exists():
                    old_file.unlink()
                entry["name"] = new_name
                self._save_index()
                self._save_steps(new_name, steps)
                return True
        return False

    def save(self) -> None:
        """兼容旧代码的显式保存。"""
        self._save_index()

    @staticmethod
    def create_step(step_type: str) -> dict:
        if step_type not in DEFAULT_STEPS:
            raise ValueError(f"Unknown step type: {step_type}")
        return deepcopy(DEFAULT_STEPS[step_type])

    @staticmethod
    def new_task(name: str, description: str = "") -> dict:
        return {"name": name, "description": description, "enabled": False, "steps": []}
