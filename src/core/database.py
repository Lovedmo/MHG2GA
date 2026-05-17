"""SQLite 数据库管理，用于运行日志和任务执行历史的持久化存储。"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


from src.core.path_helper import get_data_path
DEFAULT_DB_DIR = get_data_path("data")
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "mhg2ga.db"

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS run_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    level       TEXT    NOT NULL,
    device      TEXT    NOT NULL DEFAULT '',
    message     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS task_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device      TEXT    NOT NULL,
    task_name   TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    message     TEXT    NOT NULL DEFAULT '',
    duration_s  REAL    NOT NULL DEFAULT 0,
    started_at  TEXT    NOT NULL,
    finished_at TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS screenshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device      TEXT    NOT NULL,
    filepath    TEXT    NOT NULL,
    width       INTEGER NOT NULL DEFAULT 0,
    height      INTEGER NOT NULL DEFAULT 0,
    elapsed_ms  REAL    NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_run_logs_timestamp ON run_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_run_logs_level ON run_logs(level);
CREATE INDEX IF NOT EXISTS idx_run_logs_device ON run_logs(device);
CREATE INDEX IF NOT EXISTS idx_task_history_device ON task_history(device);
CREATE INDEX IF NOT EXISTS idx_task_history_task ON task_history(task_name);
"""


class Database:
    """SQLite 数据库连接管理器。"""

    def __init__(self, db_path: Path | str | None = None):
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_CREATE_TABLES_SQL)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---- 运行日志 ----

    def insert_log(self, timestamp: str, level: str, device: str, message: str) -> None:
        self._conn.execute(
            "INSERT INTO run_logs (timestamp, level, device, message) VALUES (?, ?, ?, ?)",
            (timestamp, level, device, message),
        )
        self._conn.commit()

    def query_logs(
        self,
        level: str | None = None,
        device: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict]:
        sql = "SELECT * FROM run_logs WHERE 1=1"
        params: list[Any] = []
        if level and level != "ALL":
            sql += " AND level = ?"
            params.append(level)
        if device:
            sql += " AND device = ?"
            params.append(device)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def count_logs(self, level: str | None = None, device: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM run_logs WHERE 1=1"
        params: list[Any] = []
        if level and level != "ALL":
            sql += " AND level = ?"
            params.append(level)
        if device:
            sql += " AND device = ?"
            params.append(device)
        return self._conn.execute(sql, params).fetchone()[0]

    def clear_logs(self) -> None:
        self._conn.execute("DELETE FROM run_logs")
        self._conn.commit()

    # ---- 任务历史 ----

    def insert_task(
        self,
        device: str,
        task_name: str,
        status: str,
        message: str = "",
        duration_s: float = 0,
        started_at: str = "",
        finished_at: str = "",
    ) -> int:
        if not started_at:
            started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self._conn.execute(
            "INSERT INTO task_history (device, task_name, status, message, duration_s, started_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (device, task_name, status, message, duration_s, started_at, finished_at),
        )
        self._conn.commit()
        return cursor.lastrowid

    def update_task(self, task_id: int, status: str, message: str = "", duration_s: float = 0) -> None:
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._conn.execute(
            "UPDATE task_history SET status=?, message=?, duration_s=?, finished_at=? WHERE id=?",
            (status, message, duration_s, finished_at, task_id),
        )
        self._conn.commit()

    def query_tasks(
        self,
        device: str | None = None,
        task_name: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        sql = "SELECT * FROM task_history WHERE 1=1"
        params: list[Any] = []
        if device:
            sql += " AND device = ?"
            params.append(device)
        if task_name:
            sql += " AND task_name = ?"
            params.append(task_name)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ---- 截图记录 ----

    def insert_screenshot(
        self,
        device: str,
        filepath: str,
        width: int = 0,
        height: int = 0,
        elapsed_ms: float = 0,
    ) -> None:
        self._conn.execute(
            "INSERT INTO screenshots (device, filepath, width, height, elapsed_ms) VALUES (?, ?, ?, ?, ?)",
            (device, filepath, width, height, elapsed_ms),
        )
        self._conn.commit()

    def query_screenshots(self, device: str | None = None, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM screenshots WHERE 1=1"
        params: list[Any] = []
        if device:
            sql += " AND device = ?"
            params.append(device)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ---- 统计 ----

    def get_stats(self, device: str | None = None) -> dict:
        """获取简要统计数据。"""
        params: list[Any] = []
        device_filter = ""
        if device:
            device_filter = " AND device = ?"
            params.append(device)

        total_tasks = self._conn.execute(
            f"SELECT COUNT(*) FROM task_history WHERE 1=1{device_filter}", params
        ).fetchone()[0]

        success_tasks = self._conn.execute(
            f"SELECT COUNT(*) FROM task_history WHERE status='success'{device_filter}", params
        ).fetchone()[0]

        total_screenshots = self._conn.execute(
            f"SELECT COUNT(*) FROM screenshots WHERE 1=1{device_filter}", params
        ).fetchone()[0]

        error_logs = self._conn.execute(
            f"SELECT COUNT(*) FROM run_logs WHERE level='ERROR'{device_filter}", params
        ).fetchone()[0]

        return {
            "total_tasks": total_tasks,
            "success_tasks": success_tasks,
            "total_screenshots": total_screenshots,
            "error_logs": error_logs,
        }
