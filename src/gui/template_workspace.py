"""模板工作台：集成模板列表浏览、截图框选截取、预览与管理。

布局:
    ┌──────────────────────────────────────────────────────────────┐
    │ 工具栏: [截取新模板] [删除] [刷新列表]                        │
    ├──────────┬───────────────────────────────────────────────────┤
    │ 模板列表  │  截图预览 / 框选截取区域                           │
    │ (tree)   │  (SelectableImageView)                            │
    │          ├───────────────────────────────────────────────────┤
    │          │  模板设置面板 / 模板详情                            │
    ├──────────┴───────────────────────────────────────────────────┤
    │ 状态栏: 坐标 | 模板数量                                      │
    └──────────────────────────────────────────────────────────────┘
"""

import re
from pathlib import Path

import cv2
import numpy as np

from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox,
    QLineEdit, QSlider, QCheckBox, QMessageBox,
    QSplitter, QTreeWidgetItem,
    QStackedWidget, QInputDialog, QMenu,
)

from src.core.template_manager import TemplateManager, CATEGORIES
from src.gui.widgets.selectable_image_view import SelectableImageView
from src.gui.widgets.mask_editor import MaskEditor
from src.gui.widgets.template_tree import TemplateTreeWidget


class TemplateWorkspace(QWidget):
    """模板管理与截取一体化工作台。"""

    capture_screenshot_requested = pyqtSignal()

    def __init__(self, template_manager: TemplateManager, parent=None):
        super().__init__(parent)
        self._tm = template_manager
        self._screenshot: np.ndarray | None = None
        self._selection: QRect | None = None
        self._mode = "template"

        self.setWindowTitle("模板工作台")
        self.setWindowFlag(Qt.WindowType.Window)
        self.setMinimumSize(1050, 650)
        self.resize(1200, 720)
        self._setup_ui()
        self.refresh_list()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 6)
        toolbar.setSpacing(6)

        self._capture_btn = QPushButton("截取新模板")
        self._capture_btn.setProperty("role", "primary")
        self._capture_btn.setToolTip("从当前连接的设备截图，然后在图上框选模板区域")
        self._capture_btn.clicked.connect(self._on_request_capture)
        toolbar.addWidget(self._capture_btn)

        self._edit_btn = QPushButton("编辑模板")
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit)
        toolbar.addWidget(self._edit_btn)

        self._mask_btn = QPushButton("编辑蒙版")
        self._mask_btn.setEnabled(False)
        self._mask_btn.setToolTip(
            "编辑模板蒙版：标记哪些区域参与匹配\n"
            "白色=匹配  红色覆盖=忽略（背景）\n"
            "用于不规则形状按钮，排除背景干扰"
        )
        self._mask_btn.clicked.connect(self._on_edit_mask)
        toolbar.addWidget(self._mask_btn)

        self._delete_btn = QPushButton("删除模板")
        self._delete_btn.setProperty("role", "danger")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(self._delete_btn)

        self._refresh_btn = QPushButton("刷新列表")
        self._refresh_btn.clicked.connect(self.refresh_list)
        toolbar.addWidget(self._refresh_btn)

        self._new_folder_btn = QPushButton("新建文件夹")
        self._new_folder_btn.setToolTip("在模板目录下创建新的分类文件夹")
        self._new_folder_btn.clicked.connect(self._on_new_folder)
        toolbar.addWidget(self._new_folder_btn)

        toolbar.addStretch()

        self._match_toggle = QPushButton("匹配测试")
        self._match_toggle.setCheckable(True)
        self._match_toggle.setToolTip(
            "开启后选择模板时自动执行匹配测试\n"
            "关闭后清除截图上的标注"
        )
        self._match_toggle.setEnabled(False)
        self._match_toggle.toggled.connect(self._on_match_toggle)
        toolbar.addWidget(self._match_toggle)

        self._match_all_btn = QPushButton("匹配全部")
        self._match_all_btn.setToolTip("在当前截图上查找所有匹配位置")
        self._match_all_btn.setEnabled(False)
        self._match_all_btn.clicked.connect(lambda: self._run_match(find_all=True))
        toolbar.addWidget(self._match_all_btn)

        self._mode_label = QLabel("")
        self._mode_label.setStyleSheet("font-weight: bold; padding: 0 8px;")
        toolbar.addWidget(self._mode_label)

        root.addLayout(toolbar)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #313244;")
        root.addWidget(sep)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(4, 4, 4, 0)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索模板...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_search)
        search_row.addWidget(self._search_edit)
        left_layout.addLayout(search_row)

        sort_row = QHBoxLayout()
        sort_row.setContentsMargins(4, 0, 4, 0)
        sort_row.addWidget(QLabel("排序:"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("默认", "default")
        self._sort_combo.addItem("名称 A→Z", "name_asc")
        self._sort_combo.addItem("名称 Z→A", "name_desc")
        self._sort_combo.addItem("阈值 高→低", "threshold_desc")
        self._sort_combo.addItem("阈值 低→高", "threshold_asc")
        self._sort_combo.currentIndexChanged.connect(lambda _: self._apply_filter())
        sort_row.addWidget(self._sort_combo, stretch=1)
        left_layout.addLayout(sort_row)

        self._tree = TemplateTreeWidget(drag_enabled=False)
        self._tree.currentItemChanged.connect(self._on_item_selected)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        left_layout.addWidget(self._tree, stretch=1)

        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(350)
        main_splitter.addWidget(left_panel)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(4)

        self._image_view = SelectableImageView()
        self._image_view.selection_changed.connect(self._on_selection_changed)
        self._image_view.click_point_changed.connect(self._on_click_point_set)
        self._image_view.coordinate_hover.connect(self._on_coord_hover)
        right_layout.addWidget(self._image_view, stretch=3)

        self._bottom_stack = QStackedWidget()

        # ---- Page 0: 模板详情（浏览模式） ----
        self._detail_page = QWidget()
        detail_layout = QHBoxLayout(self._detail_page)
        detail_layout.setContentsMargins(4, 4, 4, 4)
        detail_layout.setSpacing(12)

        self._detail_preview = QLabel("选择模板查看预览")
        self._detail_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_preview.setMinimumSize(150, 100)
        self._detail_preview.setStyleSheet(
            "background-color: #11111b; border: 1px solid #313244; border-radius: 4px;"
        )
        detail_layout.addWidget(self._detail_preview)

        detail_info_layout = QVBoxLayout()
        self._detail_text = QLabel("--")
        self._detail_text.setWordWrap(True)
        self._detail_text.setStyleSheet("color: #a6adc8;")
        self._detail_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_info_layout.addWidget(self._detail_text)
        detail_info_layout.addStretch()
        detail_layout.addLayout(detail_info_layout, stretch=1)

        self._bottom_stack.addWidget(self._detail_page)

        # ---- Page 1: 截取设置面板（截取模式） ----
        self._capture_page = QWidget()
        cap_layout = QHBoxLayout(self._capture_page)
        cap_layout.setContentsMargins(4, 4, 4, 4)
        cap_layout.setSpacing(12)

        self._sel_preview = QLabel("在上方截图中拖拽框选")
        self._sel_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sel_preview.setMinimumSize(150, 100)
        self._sel_preview.setMaximumWidth(250)
        self._sel_preview.setStyleSheet(
            "background-color: #11111b; border: 1px solid #313244; border-radius: 4px;"
        )
        cap_layout.addWidget(self._sel_preview)

        form = QGridLayout()
        form.setSpacing(6)

        form.addWidget(QLabel("名称:"), 0, 0)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("英文标识名 (如 confirm_button)")
        form.addWidget(self._name_edit, 0, 1)

        form.addWidget(QLabel("分类:"), 0, 2)
        self._category_combo = QComboBox()
        self._category_combo.addItems(self._tm.get_all_categories_on_disk())
        self._category_combo.setEditable(False)
        self._category_combo.setToolTip("选择已有分类文件夹，如需新建请使用工具栏「新建文件夹」按钮")
        form.addWidget(self._category_combo, 0, 3)

        form.addWidget(QLabel("描述:"), 1, 0)
        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("中文描述")
        form.addWidget(self._desc_edit, 1, 1)

        form.addWidget(QLabel("阈值:"), 1, 2)
        thr_row = QHBoxLayout()
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(50, 100)
        self._threshold_slider.setValue(80)
        self._threshold_label = QLabel("0.80")
        self._threshold_label.setFixedWidth(36)
        self._threshold_slider.valueChanged.connect(
            lambda v: self._threshold_label.setText(f"{v / 100:.2f}")
        )
        thr_row.addWidget(self._threshold_slider)
        thr_row.addWidget(self._threshold_label)
        form.addLayout(thr_row, 1, 3)

        form.addWidget(QLabel("匹配方式:"), 2, 0)
        self._match_mode_combo = QComboBox()
        self._match_mode_combo.addItem("普通匹配", "normal")
        self._match_mode_combo.addItem("蒙版匹配", "mask")
        self._match_mode_combo.addItem("边缘匹配", "edge")
        self._match_mode_combo.setToolTip(
            "普通匹配 — 灰度+HSV颜色校验，适合背景固定的按钮\n"
            "蒙版匹配 — 只比对蒙版标记的区域，适合不规则形状/变化背景\n"
            "边缘匹配 — 比对轮廓边缘，自动忽略背景颜色变化"
        )
        form.addWidget(self._match_mode_combo, 2, 1)

        self._rgb_check = QCheckBox("颜色校验")
        self._rgb_check.setChecked(True)
        self._rgb_check.setToolTip("仅普通匹配模式有效：额外比较 HSV 颜色，更好区分同框体不同背景的元素")
        form.addWidget(self._rgb_check, 2, 2, 1, 2)

        self._click_btn = QPushButton("设置点击点")
        self._click_btn.setCheckable(True)
        self._click_btn.setToolTip(
            "在截图上点击设置实际触控位置\n"
            "框选大区域确保匹配唯一性，点击点控制触发位置\n"
            "不设置则默认为模板区域中心"
        )
        self._click_btn.toggled.connect(self._on_click_mode)
        form.addWidget(self._click_btn, 3, 0)

        self._click_label = QLabel("默认中心")
        self._click_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        form.addWidget(self._click_label, 3, 1)

        self._roi_btn = QPushButton("设置 ROI")
        self._roi_btn.setCheckable(True)
        self._roi_btn.toggled.connect(self._on_roi_mode)
        form.addWidget(self._roi_btn, 3, 2)

        self._roi_label = QLabel("全屏搜索")
        self._roi_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        form.addWidget(self._roi_label, 3, 3)

        cap_layout.addLayout(form, stretch=1)

        save_col = QVBoxLayout()
        save_col.addStretch()

        self._recrop_btn = QPushButton("重新截取")
        self._recrop_btn.setToolTip("加载新截图并重新裁剪模板图片")
        self._recrop_btn.setVisible(False)
        self._recrop_btn.clicked.connect(self._on_recrop)
        save_col.addWidget(self._recrop_btn)

        self._save_btn = QPushButton("保存模板")
        self._save_btn.setProperty("role", "primary")
        self._save_btn.setEnabled(False)
        self._save_btn.setMinimumHeight(36)
        self._save_btn.clicked.connect(self._on_save)
        save_col.addWidget(self._save_btn)

        self._cancel_btn = QPushButton("取消截取")
        self._cancel_btn.clicked.connect(self._on_cancel)
        save_col.addWidget(self._cancel_btn)
        save_col.addStretch()
        cap_layout.addLayout(save_col)

        self._bottom_stack.addWidget(self._capture_page)

        right_layout.addWidget(self._bottom_stack, stretch=1)
        main_splitter.addWidget(right_widget)

        main_splitter.setSizes([250, 800])
        root.addWidget(main_splitter, stretch=1)

        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(8, 4, 8, 4)
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        status_bar.addWidget(self._status_label)
        status_bar.addStretch()
        self._count_label = QLabel("模板: 0")
        self._count_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        status_bar.addWidget(self._count_label)
        root.addLayout(status_bar)

        self._roi_rect: QRect | None = None
        self._click_offset: tuple[int, int] | None = None
        self._editing_name: str | None = None
        self._set_mode_browse()

    # ---- 模式切换 ----

    def _set_mode_browse(self) -> None:
        self._mode_label.setText("")
        self._mode_label.setStyleSheet("color: #a6adc8; font-weight: bold; padding: 0 8px;")
        self._bottom_stack.setCurrentWidget(self._detail_page)
        self._mode = "browse"

    def _set_mode_capture(self) -> None:
        self._mode_label.setText("截取模式 — 在截图上拖拽框选模板区域")
        self._mode_label.setStyleSheet("color: #a6e3a1; font-weight: bold; padding: 0 8px;")
        self._bottom_stack.setCurrentWidget(self._capture_page)
        self._mode = "template"
        self._image_view.set_mode("select")
        self._selection = None
        self._roi_rect = None
        self._click_offset = None
        self._roi_label.setText("全屏搜索")
        self._click_label.setText("默认中心")
        self._roi_btn.setChecked(False)
        self._click_btn.setChecked(False)
        self._save_btn.setEnabled(False)
        self._sel_preview.setText("在上方截图中拖拽框选")
        self._sel_preview.setPixmap(QPixmap())
        self._image_view.clear_click_point()
        self._name_edit.clear()
        self._desc_edit.clear()

    def _exit_capture_mode(self) -> None:
        self._image_view.clear_selection()
        self._set_mode_browse()
        current = self._tree.currentItem()
        if current:
            self._on_item_selected(current, None)

    # ---- 列表管理 ----

    def refresh_list(self) -> None:
        self._tm.reload()
        self._apply_filter()

    def _on_search(self, text: str) -> None:
        self._apply_filter()

    def _apply_filter(self) -> None:
        templates = self._tm.templates
        keyword = self._search_edit.text().strip().lower()

        if keyword:
            templates = [
                t for t in templates
                if keyword in t.get("name", "").lower()
                or keyword in t.get("description", "").lower()
                or keyword in t.get("category", "").lower()
            ]

        sort_key = self._sort_combo.currentData() or "default"
        if sort_key == "name_asc":
            templates = sorted(templates, key=lambda t: (t.get("description") or t["name"]).lower())
        elif sort_key == "name_desc":
            templates = sorted(templates, key=lambda t: (t.get("description") or t["name"]).lower(), reverse=True)
        elif sort_key == "threshold_desc":
            templates = sorted(templates, key=lambda t: t.get("threshold", 0.80), reverse=True)
        elif sort_key == "threshold_asc":
            templates = sorted(templates, key=lambda t: t.get("threshold", 0.80))

        cats = self._tm.get_all_categories_on_disk() if not keyword else []
        self._tree.populate(templates, cats)

        total = len(self._tm.templates)
        shown = len(templates)
        if keyword:
            self._count_label.setText(f"模板: {shown}/{total}")
        else:
            self._count_label.setText(f"模板: {total}")

    def _on_item_selected(self, current: QTreeWidgetItem | None, _previous) -> None:
        if not current:
            self._delete_btn.setEnabled(False)
            self._edit_btn.setEnabled(False)
            self._mask_btn.setEnabled(False)
            self._update_match_btn_state()
            return

        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            self._delete_btn.setEnabled(False)
            self._edit_btn.setEnabled(False)
            self._mask_btn.setEnabled(False)
            self._update_match_btn_state()
            self._detail_preview.setText("选择模板查看预览")
            self._detail_preview.setPixmap(QPixmap())
            self._detail_text.setText("--")
            return

        self._delete_btn.setEnabled(True)
        self._edit_btn.setEnabled(True)
        self._mask_btn.setEnabled(True)
        self._update_match_btn_state()

        if self._match_toggle.isChecked() and self._screenshot is not None:
            self._run_match(find_all=False)

        if self._mode != "browse":
            return

        path = self._tm.get_template_path(data["name"])
        if path and path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self._image_view.set_image(pixmap)
                scaled = pixmap.scaled(
                    self._detail_preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._detail_preview.setPixmap(scaled)

        roi_text = f'{data.get("roi")}' if data.get("roi") else "全屏搜索"
        co = data.get("click_offset")
        click_text = f"({co[0]}, {co[1]})" if co else "中心 (默认)"
        mask_text = "有" if data.get("mask_file") else "无"
        mode_map = {"normal": "普通", "mask": "蒙版", "edge": "边缘"}
        mm = mode_map.get(data.get("match_mode", "normal"), "普通")
        detail_lines = [
            f"名称: {data['name']}",
            f"分类: {data.get('category', '--')}",
            f"尺寸: {data.get('width', '?')}×{data.get('height', '?')}",
            f"匹配: {mm}  |  阈值: {data.get('threshold', 0.80):.2f}  |  RGB: {'是' if data.get('rgb', True) else '否'}",
            f"ROI: {roi_text}  |  点击点: {click_text}  |  蒙版: {mask_text}",
            f"描述: {data.get('description') or '--'}",
            f"文件: {data.get('file', '--')}",
        ]
        self._detail_text.setText("\n".join(detail_lines))
        self._status_label.setText(f"预览: {data['name']}")

    def _on_delete(self) -> None:
        current = self._tree.currentItem()
        if not current:
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f'确定删除模板 "{data["name"]}" 吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._tm.remove_template(data["name"])
            self.refresh_list()
            self._detail_preview.setText("已删除")
            self._detail_preview.setPixmap(QPixmap())
            self._detail_text.setText("--")

    # ---- 文件夹管理 ----

    def _on_new_folder(self) -> None:
        """新建分类文件夹。"""
        name, ok = QInputDialog.getText(
            self, "新建文件夹", "输入文件夹名称（英文小写，如 daily_task）:",
        )
        if not ok or not name:
            return
        name = name.strip().lower().replace(" ", "_")
        if not re.match(r'^[a-z][a-z0-9_]*$', name):
            QMessageBox.warning(
                self, "名称格式错误",
                "文件夹名称须为英文小写字母开头的 snake_case\n例如: daily_task",
            )
            return
        if self._tm.create_category(name):
            self.refresh_list()
            self._category_combo.clear()
            self._category_combo.addItems(self._tm.get_all_categories_on_disk())
            self._status_label.setText(f"已创建文件夹: {name}")
        else:
            QMessageBox.warning(self, "创建失败", f"无法创建文件夹: {name}")

    def _on_tree_context_menu(self, pos) -> None:
        """模板树右键菜单。"""
        item = self._tree.itemAt(pos)
        if not item:
            menu = QMenu(self)
            menu.addAction("新建文件夹", self._on_new_folder)
            menu.exec(self._tree.viewport().mapToGlobal(pos))
            return

        cat_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
        tpl_data = item.data(0, Qt.ItemDataRole.UserRole)

        menu = QMenu(self)
        if cat_name and not tpl_data:
            menu.addAction("重命名文件夹", lambda: self._on_rename_folder(cat_name))
            menu.addAction("删除文件夹", lambda: self._on_delete_folder(cat_name))
            menu.addSeparator()
            menu.addAction("新建文件夹", self._on_new_folder)
        elif tpl_data:
            menu.addAction("编辑模板", self._on_edit)
            menu.addAction("编辑蒙版", self._on_edit_mask)
            menu.addAction("删除模板", self._on_delete)
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _on_rename_folder(self, old_name: str) -> None:
        new_name, ok = QInputDialog.getText(
            self, "重命名文件夹", f"将 \"{old_name}\" 重命名为:",
            text=old_name,
        )
        if not ok or not new_name:
            return
        new_name = new_name.strip().lower().replace(" ", "_")
        if not re.match(r'^[a-z][a-z0-9_]*$', new_name):
            QMessageBox.warning(self, "名称格式错误",
                                "文件夹名称须为英文小写字母开头的 snake_case")
            return
        if self._tm.rename_category(old_name, new_name):
            self.refresh_list()
            self._category_combo.clear()
            self._category_combo.addItems(self._tm.get_all_categories_on_disk())
            self._status_label.setText(f"文件夹已重命名: {old_name} → {new_name}")
        else:
            QMessageBox.warning(self, "重命名失败",
                                f"无法重命名 \"{old_name}\"。\n可能原因：目标名已存在或源文件夹不存在。")

    def _on_delete_folder(self, name: str) -> None:
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除文件夹 \"{name}\" 吗？\n注意：只有空文件夹可以被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self._tm.delete_category(name):
            self.refresh_list()
            self._category_combo.clear()
            self._category_combo.addItems(self._tm.get_all_categories_on_disk())
            self._status_label.setText(f"文件夹已删除: {name}")
        else:
            QMessageBox.warning(self, "删除失败",
                                f"无法删除 \"{name}\"。\n该文件夹可能不为空或其中仍有模板。")

    # ---- 编辑功能 ----

    def _on_edit(self) -> None:
        current = self._tree.currentItem()
        if not current:
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        self._set_mode_edit(data)

    def _set_mode_edit(self, meta: dict) -> None:
        """进入编辑模式，复用截取面板但预填现有值。"""
        self._editing_name = meta["name"]
        self._mode = "edit"
        self._mode_label.setText(f"编辑模式 — 修改 \"{meta['name']}\" 的属性")
        self._mode_label.setStyleSheet("color: #74c7ec; font-weight: bold; padding: 0 8px;")
        self._bottom_stack.setCurrentWidget(self._capture_page)

        self._name_edit.setText(meta["name"])
        self._name_edit.setReadOnly(True)
        self._name_edit.setStyleSheet("color: #585b70;")

        self._desc_edit.setText(meta.get("description", ""))

        cat = meta.get("category", "common")
        idx = self._category_combo.findText(cat)
        if idx >= 0:
            self._category_combo.setCurrentIndex(idx)
        else:
            self._category_combo.addItem(cat)
            self._category_combo.setCurrentText(cat)

        thr = int(meta.get("threshold", 0.80) * 100)
        self._threshold_slider.setValue(thr)
        self._rgb_check.setChecked(meta.get("rgb", True))

        mm = meta.get("match_mode", "normal")
        mm_idx = self._match_mode_combo.findData(mm)
        if mm_idx >= 0:
            self._match_mode_combo.setCurrentIndex(mm_idx)

        roi = meta.get("roi")
        if roi and len(roi) == 4:
            self._roi_rect = QRect(roi[0], roi[1], roi[2], roi[3])
            self._roi_label.setText(
                f"({roi[0]}, {roi[1]}) {roi[2]}×{roi[3]}"
            )
        else:
            self._roi_rect = None
            self._roi_label.setText("全屏搜索")

        co = meta.get("click_offset")
        if co and len(co) == 2:
            self._click_offset = (co[0], co[1])
            self._click_label.setText(f"偏移 ({co[0]}, {co[1]})")
        else:
            self._click_offset = None
            self._click_label.setText("默认中心")

        path = self._tm.get_template_path(meta["name"])
        if path and path.exists():
            tpl_img = cv2.imread(str(path))
            if tpl_img is not None:
                self._screenshot = tpl_img
                h, w = tpl_img.shape[:2]
                rgb = cv2.cvtColor(tpl_img, cv2.COLOR_BGR2RGB)
                qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                self._image_view.set_image(pixmap)
                self._image_view.set_mode("click")

                if co and len(co) == 2:
                    self._image_view.set_click_point(co[0], co[1])

                scaled = pixmap.scaled(
                    self._sel_preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._sel_preview.setPixmap(scaled)

        self._selection = None
        self._save_btn.setEnabled(True)
        self._save_btn.setText("更新模板")
        self._cancel_btn.setText("取消编辑")
        self._recrop_btn.setVisible(True)
        self._roi_btn.setChecked(False)
        self._click_btn.setChecked(False)

    def _on_recrop(self) -> None:
        """编辑模式下重新截取：发出截图请求，加载新截图后进入框选模式。"""
        if not self._editing_name:
            return
        self._mode_label.setText(f"重新截取 — 请截图后在截图上框选新区域")
        self._mode_label.setStyleSheet("color: #fab387; font-weight: bold; padding: 0 8px;")
        self._selection = None
        self._sel_preview.setText("等待截图...")
        self._sel_preview.setPixmap(QPixmap())
        self._save_btn.setEnabled(False)
        self.capture_screenshot_requested.emit()

    def _on_edit_screenshot_loaded(self, screenshot: np.ndarray) -> None:
        """编辑模式下收到新截图后，切换到框选模式。"""
        self._screenshot = screenshot
        h, w = screenshot.shape[:2]
        rgb = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self._image_view.set_image(pixmap)
        self._image_view.set_mode("select")
        self._image_view.clear_click_point()
        self._mode = "template"
        self._mode_label.setText(f"重新截取 — 在截图上框选新模板区域")
        self._mode_label.setStyleSheet("color: #fab387; font-weight: bold; padding: 0 8px;")
        self._sel_preview.setText("在上方截图中拖拽框选")
        self._status_label.setText(f"截图已加载: {w}×{h} — 请框选模板区域")

    def _exit_edit_mode(self) -> None:
        self._name_edit.setReadOnly(False)
        self._name_edit.setStyleSheet("")
        self._save_btn.setText("保存模板")
        self._cancel_btn.setText("取消截取")
        self._recrop_btn.setVisible(False)
        self._editing_name = None
        self._screenshot = None
        self._image_view.clear_click_point()
        self._set_mode_browse()
        current = self._tree.currentItem()
        if current:
            self._on_item_selected(current, None)

    # ---- 截取功能 ----

    def load_screenshot(self, screenshot: np.ndarray) -> None:
        """加载截图并进入截取模式。编辑模式下加载新截图用于重新裁剪。"""
        if self._editing_name:
            self._on_edit_screenshot_loaded(screenshot)
            self._update_match_btn_state()
            return
        self._screenshot = screenshot
        h, w = screenshot.shape[:2]
        rgb = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self._image_view.set_image(pixmap)
        self._set_mode_capture()
        self._update_match_btn_state()
        self._status_label.setText(f"截图已加载: {w}×{h}")

    def _on_request_capture(self) -> None:
        self.capture_screenshot_requested.emit()

    def _on_selection_changed(self, rect: QRect) -> None:
        if self._mode == "browse":
            return

        if self._mode == "roi":
            self._roi_rect = rect
            self._roi_label.setText(
                f"({rect.x()}, {rect.y()}) {rect.width()}×{rect.height()}"
            )
            self._roi_btn.setChecked(False)
            return

        self._selection = rect
        self._save_btn.setEnabled(rect.width() > 2 and rect.height() > 2)
        self._update_sel_preview()

    def _update_sel_preview(self) -> None:
        if not self._selection or self._screenshot is None:
            return
        r = self._selection
        crop = self._screenshot[r.y():r.y() + r.height(), r.x():r.x() + r.width()]
        if crop.size == 0:
            return
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        max_w = self._sel_preview.width() - 4
        max_h = self._sel_preview.height() - 4
        if pixmap.width() > max_w or pixmap.height() > max_h:
            pixmap = pixmap.scaled(
                max_w, max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._sel_preview.setPixmap(pixmap)

    def _on_click_mode(self, checked: bool) -> None:
        if checked:
            self._roi_btn.setChecked(False)
            self._mode = "click"
            self._image_view.set_mode("click")
            self._mode_label.setText("点击点模式 — 在截图上点击设置触控位置")
            self._mode_label.setStyleSheet("color: #f38ba8; font-weight: bold; padding: 0 8px;")
        else:
            self._mode = "template"
            self._image_view.set_mode("select")
            self._mode_label.setText("截取模式 — 在截图上拖拽框选模板区域")
            self._mode_label.setStyleSheet("color: #a6e3a1; font-weight: bold; padding: 0 8px;")

    def _on_click_point_set(self, x: int, y: int) -> None:
        self._click_offset = (x, y)
        if self._editing_name:
            self._click_label.setText(f"偏移 ({x}, {y})")
        elif self._selection:
            ox = x - self._selection.x()
            oy = y - self._selection.y()
            self._click_label.setText(f"偏移 ({ox}, {oy})")
        else:
            self._click_label.setText(f"绝对 ({x}, {y})")
        self._click_btn.setChecked(False)

    def _on_roi_mode(self, checked: bool) -> None:
        if checked:
            self._click_btn.setChecked(False)
            self._mode = "roi"
            self._image_view.set_mode("select")
            self._mode_label.setText("ROI 模式 — 框选限定搜索区域")
            self._mode_label.setStyleSheet("color: #f9e2af; font-weight: bold; padding: 0 8px;")
        else:
            self._mode = "template"
            self._image_view.set_mode("select")
            self._mode_label.setText("截取模式 — 在截图上拖拽框选模板区域")
            self._mode_label.setStyleSheet("color: #a6e3a1; font-weight: bold; padding: 0 8px;")

    def _on_coord_hover(self, x: int, y: int) -> None:
        ow, oh = self._image_view.get_original_size()
        self._status_label.setText(f"坐标: ({x}, {y})  |  图像: {ow}×{oh}")

    def _on_cancel(self) -> None:
        if self._editing_name:
            self._exit_edit_mode()
        else:
            self._exit_capture_mode()

    def _on_save(self) -> None:
        if self._editing_name:
            self._on_save_edit()
            return

        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少名称", "请输入模板标识名")
            return
        if not re.match(r'^[a-z][a-z0-9_]*$', name):
            QMessageBox.warning(self, "名称格式错误",
                                "模板名称须为英文小写字母开头的 snake_case\n例如: confirm_button")
            return

        if self._screenshot is None or self._selection is None:
            QMessageBox.warning(self, "无选区", "请先在截图上框选模板区域")
            return

        existing = self._tm.get_template(name)
        if existing:
            reply = QMessageBox.question(
                self, "模板已存在", f'"{name}" 已存在，是否覆盖？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        r = self._selection
        crop = self._screenshot[r.y():r.y() + r.height(), r.x():r.x() + r.width()].copy()
        category = self._category_combo.currentText().strip() or "common"
        threshold = self._threshold_slider.value() / 100.0
        rgb = self._rgb_check.isChecked()
        match_mode = self._match_mode_combo.currentData() or "normal"
        roi = None
        if self._roi_rect:
            roi = [self._roi_rect.x(), self._roi_rect.y(),
                   self._roi_rect.width(), self._roi_rect.height()]
        click_offset = None
        if self._click_offset:
            click_offset = [
                self._click_offset[0] - r.x(),
                self._click_offset[1] - r.y(),
            ]
        description = self._desc_edit.text().strip()

        self._tm.add_template(
            name=name, category=category, image=crop,
            threshold=threshold, rgb=rgb, roi=roi,
            click_offset=click_offset, match_mode=match_mode,
            description=description,
        )

        self._status_label.setText(f"已保存: {category}/{name}.png ({crop.shape[1]}×{crop.shape[0]}) — 可继续框选下一个模板")
        self.refresh_list()
        self._select_template_in_tree(name)

        self._selection = None
        self._roi_rect = None
        self._click_offset = None
        self._roi_label.setText("全屏搜索")
        self._click_label.setText("默认中心")
        self._roi_btn.setChecked(False)
        self._click_btn.setChecked(False)
        self._save_btn.setEnabled(False)
        self._sel_preview.setText("在上方截图中拖拽框选")
        self._sel_preview.setPixmap(QPixmap())
        self._image_view.clear_selection()
        self._image_view.clear_click_point()
        self._image_view.set_mode("select")
        self._name_edit.clear()
        self._desc_edit.clear()

    def _on_save_edit(self) -> None:
        """保存编辑模式的修改。如果有新选区则同时更新模板图片。"""
        name = self._editing_name
        category = self._category_combo.currentText().strip() or "common"
        threshold = self._threshold_slider.value() / 100.0
        rgb = self._rgb_check.isChecked()
        match_mode = self._match_mode_combo.currentData() or "normal"
        roi = None
        if self._roi_rect:
            roi = [self._roi_rect.x(), self._roi_rect.y(),
                   self._roi_rect.width(), self._roi_rect.height()]
        click_offset = None
        if self._click_offset:
            click_offset = list(self._click_offset)
        description = self._desc_edit.text().strip()

        if self._selection and self._screenshot is not None:
            r = self._selection
            crop = self._screenshot[r.y():r.y() + r.height(), r.x():r.x() + r.width()].copy()
            if crop.size == 0:
                QMessageBox.warning(self, "选区无效", "裁剪区域为空，请重新框选")
                return
            if click_offset is None and self._click_offset:
                click_offset = [
                    self._click_offset[0] - r.x(),
                    self._click_offset[1] - r.y(),
                ]

            self._tm.add_template(
                name=name, category=category, image=crop,
                threshold=threshold, rgb=rgb, roi=roi,
                click_offset=click_offset, match_mode=match_mode,
                description=description,
            )
            self._status_label.setText(
                f"已更新: {name} (重新裁剪 {crop.shape[1]}×{crop.shape[0]})"
            )
        else:
            self._tm.update_template(
                name,
                category=category,
                threshold=threshold,
                rgb=rgb,
                match_mode=match_mode,
                roi=roi,
                click_offset=click_offset,
                description=description,
            )
            self._status_label.setText(f"已更新: {name}")

        self.refresh_list()
        self._exit_edit_mode()
        self._select_template_in_tree(name)

    def _update_match_btn_state(self) -> None:
        has_screenshot = self._screenshot is not None
        current = self._tree.currentItem()
        has_template = bool(current and current.data(0, Qt.ItemDataRole.UserRole))
        self._match_toggle.setEnabled(has_screenshot)
        self._match_all_btn.setEnabled(has_screenshot and has_template)

    def _on_match_toggle(self, checked: bool) -> None:
        if checked:
            self._match_toggle.setStyleSheet("background-color: #a6e3a1; color: #1e1e2e;")
            current = self._tree.currentItem()
            if current and current.data(0, Qt.ItemDataRole.UserRole) and self._screenshot is not None:
                self._run_match(find_all=False)
        else:
            self._match_toggle.setStyleSheet("")
            self._restore_screenshot()

    def _restore_screenshot(self) -> None:
        """恢复原始截图，清除所有标注。"""
        if self._screenshot is not None:
            h, w = self._screenshot.shape[:2]
            rgb = cv2.cvtColor(self._screenshot, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            self._image_view.set_image(pixmap)
            self._status_label.setText(f"截图: {w}×{h}")

    def _run_match(self, find_all: bool = False) -> None:
        import time
        if self._screenshot is None:
            self._status_label.setText("无截图，请先截取")
            return

        current = self._tree.currentItem()
        if not current:
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        from src.core.device_manager import DeviceManager

        name = data["name"]
        tpl_img = self._tm.load_template_image(name)
        if tpl_img is None:
            self._status_label.setText(f"模板图片加载失败: {name}")
            return

        threshold = data.get("threshold", 0.80)
        rgb = data.get("rgb", True)
        roi = data.get("roi")
        click_offset = data.get("click_offset")
        match_mode = data.get("match_mode", "normal")
        mask = self._tm.load_mask(name) if match_mode == "mask" else None

        rounds = 5
        elapsed_list: list[float] = []
        results: list[dict] = []

        for i in range(rounds):
            t0 = time.perf_counter()
            if find_all:
                r = DeviceManager.match_template_all(
                    self._screenshot, tpl_img,
                    threshold=threshold, rgb=rgb,
                    roi=roi, click_offset=click_offset,
                    mask=mask, match_mode=match_mode,
                )
            else:
                single = DeviceManager.match_template(
                    self._screenshot, tpl_img,
                    threshold=threshold, rgb=rgb,
                    roi=roi, click_offset=click_offset,
                    mask=mask, match_mode=match_mode,
                )
                r = [single] if single else []
            elapsed_list.append((time.perf_counter() - t0) * 1000)
            if i == 0:
                results = r

        avg_ms = sum(elapsed_list) / len(elapsed_list)
        min_ms = min(elapsed_list)
        max_ms = max(elapsed_list)

        annotated = self._screenshot.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1

        timing_text = f"avg={avg_ms:.1f}ms min={min_ms:.1f}ms max={max_ms:.1f}ms ({rounds}R)"

        img_h, img_w = annotated.shape[:2]

        def _draw_label(img, text, x, y, color):
            """在图上绘制带黑色背景的标签，自动限制在图像边界内。"""
            (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
            lx = max(0, min(x, img_w - tw - 4))
            ly = max(th + 4, min(y, img_h - 4))
            cv2.rectangle(img, (lx, ly - th - 2), (lx + tw + 4, ly + 4),
                          (0, 0, 0), -1)
            cv2.putText(img, text, (lx + 2, ly),
                        font, font_scale, color, thickness, cv2.LINE_AA)
            return th

        if results:
            for i, r in enumerate(results):
                rx, ry, rw, rh = r["rect"]
                cv2.rectangle(annotated, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)

                cx, cy = r["center"]
                cp = r.get("click_point", (cx, cy))
                cv2.drawMarker(annotated, (cx, cy), (0, 255, 0),
                               cv2.MARKER_CROSS, 16, 1)
                if cp != (cx, cy):
                    cv2.drawMarker(annotated, (cp[0], cp[1]), (0, 0, 255),
                                   cv2.MARKER_CROSS, 20, 2)
                    cv2.circle(annotated, (cp[0], cp[1]), 8, (0, 0, 255), 1)

                line1 = f"#{i+1} ({cp[0]},{cp[1]}) {r['confidence']:.3f}"
                place_above = ry > 40
                label_y = ry - 8 if place_above else ry + rh + 16
                th1 = _draw_label(annotated, line1, rx, label_y, (0, 255, 0))

                if i == 0:
                    line2_y = label_y - th1 - 6 if place_above else label_y + th1 + 8
                    _draw_label(annotated, timing_text, rx, line2_y, (0, 200, 200))
        else:
            no_match_text = f"NOT FOUND (threshold={threshold:.2f}) | {timing_text}"
            _draw_label(annotated, no_match_text, 8, 20, (0, 100, 255))

        h, w = annotated.shape[:2]
        rgb_img = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb_img.data, w, h, w * 3, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self._image_view.set_image(pixmap)

        if results:
            self._status_label.setText(
                f"匹配: {name} → {len(results)} 个  |  "
                f"耗时: {avg_ms:.1f}ms ({rounds}轮)"
            )
        else:
            self._status_label.setText(
                f"匹配: {name} → 未找到  |  耗时: {avg_ms:.1f}ms ({rounds}轮)"
            )

    def _select_template_in_tree(self, name: str) -> None:
        self._tree.select_template(name)

    # ---- 蒙版编辑 ----

    def _on_edit_mask(self) -> None:
        current = self._tree.currentItem()
        if not current:
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        name = data["name"]
        tpl_img = self._tm.load_template_image(name)
        if tpl_img is None:
            QMessageBox.warning(self, "错误", f"模板图片加载失败: {name}")
            return

        existing_mask = self._tm.load_mask(name)

        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QSpinBox

        dialog = QDialog(self)
        dialog.setWindowTitle(f"编辑蒙版 — {data.get('description') or name}")
        dialog.setMinimumSize(700, 500)
        dialog.resize(900, 600)

        layout = QVBoxLayout(dialog)

        info = QLabel(
            "左键拖拽 = 橡皮擦（涂红，标记为忽略）  |  "
            "右键拖拽 = 画笔（恢复为参与匹配）  |  "
            "滚轮 = 调整笔刷  |  Ctrl+滚轮 = 缩放"
        )
        info.setStyleSheet("color: #a6adc8; font-size: 11px; padding: 4px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        editor = MaskEditor()
        editor.set_image_and_mask(tpl_img, existing_mask)
        layout.addWidget(editor, stretch=1)

        tool_row = QHBoxLayout()
        tool_row.addWidget(QLabel("笔刷大小:"))
        brush_spin = QSpinBox()
        brush_spin.setRange(2, 100)
        brush_spin.setValue(12)
        brush_spin.valueChanged.connect(editor.set_brush_size)
        tool_row.addWidget(brush_spin)

        fill_btn = QPushButton("全部参与匹配")
        fill_btn.clicked.connect(editor.fill_all)
        tool_row.addWidget(fill_btn)

        clear_btn = QPushButton("全部忽略")
        clear_btn.clicked.connect(editor.clear_all)
        tool_row.addWidget(clear_btn)

        invert_btn = QPushButton("反转蒙版")
        invert_btn.clicked.connect(editor.invert)
        tool_row.addWidget(invert_btn)

        tool_row.addStretch()
        layout.addLayout(tool_row)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            mask = editor.get_mask()
            if mask is not None:
                self._tm.save_mask(name, mask)
                self._status_label.setText(f"蒙版已保存: {name}")
                current_item = self._tree.currentItem()
                if current_item:
                    self._on_item_selected(current_item, None)
