"""模板管理器：负责模板图片的存储、元数据管理和检索。

模板目录结构:
    assets/templates/
    ├── templates.json     # 所有模板元数据
    ├── common/            # 通用 UI 元素
    ├── battle/            # 战斗场景
    ├── navigation/        # 导航菜单
    └── event/             # 活动场景

每个模板的元数据:
    name        — 唯一标识名（英文 snake_case）
    category    — 所属分类目录名
    file        — 相对于 templates 根目录的图片路径
    threshold   — 匹配阈值 (0.0-1.0)
    rgb         — 是否启用 RGB 颜色校验
    roi         — 搜索区域 [x, y, w, h] 或 null 表示全屏搜索
    description — 中文描述
"""

import json
import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.core.logger import get_logger

logger = get_logger("template_manager")

from src.core.path_helper import get_assets_path
TEMPLATES_DIR = get_assets_path("templates")
TEMPLATES_META = TEMPLATES_DIR / "templates.json"

CATEGORIES = ["common", "battle", "navigation", "event", "sign_in", "story"]

MATCH_MODES = ["normal", "mask", "edge"]

DEFAULT_TEMPLATE_META: dict[str, Any] = {
    "name": "",
    "category": "common",
    "file": "",
    "threshold": 0.80,
    "rgb": True,
    "roi": None,
    "click_offset": None,
    "mask_file": None,
    "match_mode": "normal",
    "description": "",
}


class TemplateManager:
    """模板元数据管理。"""

    def __init__(self, templates_dir: Path | None = None):
        self._dir = templates_dir or TEMPLATES_DIR
        self._meta_path = self._dir / "templates.json"
        self._templates: list[dict] = []
        self._ensure_dirs()
        self._load()

    def _ensure_dirs(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        for cat in CATEGORIES:
            (self._dir / cat).mkdir(exist_ok=True)

    def _load(self) -> None:
        if self._meta_path.exists():
            try:
                with open(self._meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._templates = data.get("templates", [])
            except Exception as e:
                logger.warning("加载模板元数据失败: %s", e)
                self._templates = []
        else:
            self._templates = []

    def reload(self) -> None:
        """从磁盘重新加载模板元数据。"""
        self._load()
        logger.info("模板元数据已重新加载，共 %d 个模板", len(self._templates))

    def save(self) -> None:
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump({"templates": self._templates}, f, ensure_ascii=False, indent=2)

    @property
    def templates(self) -> list[dict]:
        return list(self._templates)

    def get_template(self, name: str) -> dict | None:
        for t in self._templates:
            if t["name"] == name:
                return dict(t)
        return None

    def get_template_path(self, name: str) -> Path | None:
        t = self.get_template(name)
        if not t:
            return None
        return self._dir / t["file"]

    def get_templates_by_category(self, category: str) -> list[dict]:
        return [t for t in self._templates if t.get("category") == category]

    def add_template(
        self,
        name: str,
        category: str,
        image: np.ndarray,
        threshold: float = 0.80,
        rgb: bool = True,
        roi: list[int] | None = None,
        click_offset: list[int] | None = None,
        match_mode: str = "normal",
        description: str = "",
    ) -> dict:
        """保存模板图片并记录元数据。

        Args:
            name: 模板唯一标识名 (英文 snake_case)
            category: 分类目录
            image: BGR numpy 数组 (OpenCV 格式)
            threshold: 匹配阈值
            rgb: 是否启用颜色校验
            roi: 搜索区域 [x, y, w, h]
            description: 中文描述

        Returns:
            模板元数据 dict
        """
        if category not in CATEGORIES:
            CATEGORIES.append(category)
            (self._dir / category).mkdir(exist_ok=True)

        filename = f"{name}.png"
        rel_path = f"{category}/{filename}"
        abs_path = self._dir / rel_path

        cv2.imwrite(str(abs_path), image)
        logger.info("模板图片已保存: %s (%dx%d)", rel_path, image.shape[1], image.shape[0])

        meta = {
            "name": name,
            "category": category,
            "file": rel_path,
            "threshold": threshold,
            "rgb": rgb,
            "roi": roi,
            "click_offset": click_offset,
            "mask_file": None,
            "match_mode": match_mode,
            "description": description,
            "width": image.shape[1],
            "height": image.shape[0],
        }

        existing = self.get_template(name)
        if existing:
            self._templates = [t for t in self._templates if t["name"] != name]
        self._templates.append(meta)
        self.save()
        return meta

    def remove_template(self, name: str) -> bool:
        t = self.get_template(name)
        if not t:
            return False
        img_path = self._dir / t["file"]
        if img_path.exists():
            img_path.unlink()
        self._templates = [t for t in self._templates if t["name"] != name]
        self.save()
        logger.info("模板已删除: %s", name)
        return True

    def update_template(self, name: str, **kwargs) -> dict | None:
        for t in self._templates:
            if t["name"] == name:
                t.update(kwargs)
                self.save()
                return dict(t)
        return None

    def load_template_image(self, name: str) -> np.ndarray | None:
        path = self.get_template_path(name)
        if path and path.exists():
            return cv2.imread(str(path))
        return None

    def save_mask(self, name: str, mask: np.ndarray) -> str | None:
        """保存模板蒙版，返回蒙版文件的相对路径。"""
        t = self.get_template(name)
        if not t:
            return None
        category = t.get("category", "common")
        mask_filename = f"{name}_mask.png"
        rel_path = f"{category}/{mask_filename}"
        abs_path = self._dir / rel_path
        cv2.imwrite(str(abs_path), mask)
        self.update_template(name, mask_file=rel_path)
        logger.info("蒙版已保存: %s (%dx%d)", rel_path, mask.shape[1], mask.shape[0])
        return rel_path

    def load_mask(self, name: str) -> np.ndarray | None:
        """加载模板蒙版（灰度图）。"""
        t = self.get_template(name)
        if not t or not t.get("mask_file"):
            return None
        mask_path = self._dir / t["mask_file"]
        if mask_path.exists():
            return cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        return None

    def get_mask_path(self, name: str) -> Path | None:
        t = self.get_template(name)
        if not t or not t.get("mask_file"):
            return None
        return self._dir / t["mask_file"]

    def get_categories(self) -> list[str]:
        """返回所有已使用的分类。"""
        used = {t.get("category", "common") for t in self._templates}
        all_cats = list(CATEGORIES)
        for c in used:
            if c not in all_cats:
                all_cats.append(c)
        return all_cats

    def get_all_categories_on_disk(self) -> list[str]:
        """返回磁盘上实际存在的所有分类目录（含空目录）。"""
        on_disk = set()
        for p in self._dir.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                on_disk.add(p.name)
        all_cats = list(CATEGORIES)
        for c in sorted(on_disk):
            if c not in all_cats:
                all_cats.append(c)
        return all_cats

    def create_category(self, name: str) -> bool:
        """创建新的分类目录。返回是否成功。"""
        if not name or "/" in name or "\\" in name:
            return False
        cat_dir = self._dir / name
        cat_dir.mkdir(exist_ok=True)
        if name not in CATEGORIES:
            CATEGORIES.append(name)
        logger.info("创建分类目录: %s", name)
        return True

    def rename_category(self, old_name: str, new_name: str) -> bool:
        """重命名分类目录，同步更新所有模板的 category 和 file 字段。"""
        if not new_name or old_name == new_name:
            return False
        old_dir = self._dir / old_name
        new_dir = self._dir / new_name
        if not old_dir.exists():
            return False
        if new_dir.exists():
            return False
        try:
            old_dir.rename(new_dir)
        except Exception as e:
            logger.error("重命名分类目录失败: %s → %s: %s", old_name, new_name, e)
            return False
        for t in self._templates:
            if t.get("category") == old_name:
                t["category"] = new_name
                t["file"] = t["file"].replace(f"{old_name}/", f"{new_name}/", 1)
                if t.get("mask_file"):
                    t["mask_file"] = t["mask_file"].replace(f"{old_name}/", f"{new_name}/", 1)
        if old_name in CATEGORIES:
            idx = CATEGORIES.index(old_name)
            CATEGORIES[idx] = new_name
        elif new_name not in CATEGORIES:
            CATEGORIES.append(new_name)
        self.save()
        logger.info("分类目录已重命名: %s → %s", old_name, new_name)
        return True

    def delete_category(self, name: str) -> bool:
        """删除空的分类目录。非空则拒绝删除。"""
        cat_dir = self._dir / name
        if not cat_dir.exists():
            return False
        has_templates = any(t.get("category") == name for t in self._templates)
        if has_templates:
            return False
        files = list(cat_dir.iterdir())
        if files:
            return False
        try:
            cat_dir.rmdir()
        except Exception as e:
            logger.error("删除分类目录失败: %s: %s", name, e)
            return False
        if name in CATEGORIES:
            CATEGORIES.remove(name)
        logger.info("分类目录已删除: %s", name)
        return True

    def import_image(self, src_path: str, name: str, category: str = "common") -> str:
        """从外部路径导入图片作为模板。返回模板文件的相对路径。"""
        dst = self._dir / category / f"{name}.png"
        (self._dir / category).mkdir(exist_ok=True)
        shutil.copy2(src_path, dst)
        return f"{category}/{name}.png"
