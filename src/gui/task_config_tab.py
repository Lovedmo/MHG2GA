"""任务配置页：双层结构 — 任务卡片概览 / 步骤编辑器。

Page 0 — 任务概览:
    ┌──────────────────────────────────────────────────────────────┐
    │ 任务列表                                      [+ 新建任务]   │
    ├──────────────────────────────────────────────────────────────┤
    │ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐   │
    │ │ 每日签到        │ │ 日常任务        │ │ 战斗流程        │   │
    │ │ 自动签到并领取  │ │ 完成每日任务     │ │ 自动战斗        │   │
    │ │ 3 个步骤        │ │ 5 个步骤        │ │ 2 个步骤        │   │
    │ │ [✓开启] [✏编辑] │ │ [✗关闭] [✏编辑] │ │ [✓开启] [✏编辑] │   │
    │ └────────────────┘ └────────────────┘ └────────────────┘   │
    └──────────────────────────────────────────────────────────────┘

Page 1 — 步骤编辑器 (点击卡片进入):
    ┌──────────────────────────────────────────────────────────────┐
    │ [← 返回]  编辑: 每日签到              [保存]  [删除任务]      │
    ├───────────────┬──────────────────────────────────────────────┤
    │ 模板库 (树形)  │ 工作流步骤 (树形)                              │
    │ 🔍 [搜索]     │ [+条件] [+点击] [+延时]  [▲] [▼] [×]        │
    │ 📁 mainwindow │  ▼ 条件: 首页检测                             │
    │               │      点击: 任务按钮                           │
    │               │      延时: 1.0s                              │
    │               │    点击: 返回                                  │
    ├───────────────┴──────────────────────────────────────────────┤
    │ 步骤属性面板                                                  │
    └──────────────────────────────────────────────────────────────┘
"""

from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty, QSize
from PyQt6.QtGui import QColor, QPainter, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QFrame,
    QLineEdit, QSpinBox, QCompleter,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QInputDialog, QDialog,
    QRadioButton, QButtonGroup, QStackedWidget, QSplitter,
    QScrollArea, QDialogButtonBox, QSizePolicy,
)

from src.core.task_model import TaskManager, STEP_TYPE_LABELS, CONTAINER_TYPES, count_steps_recursive
from src.core.task_executor import TaskExecutor

COLS_PER_ROW = 3


# ────────────────────────────────────────────────────────────
# 滑块开关
# ────────────────────────────────────────────────────────────

class _ToggleSwitch(QWidget):
    """iOS 风格滑块开关。"""

    toggled = pyqtSignal(bool)

    _TRACK_ON = QColor("#a6e3a1")
    _TRACK_OFF = QColor("#45475a")
    _KNOB_ON = QColor("#ffffff")
    _KNOB_OFF = QColor("#6c7086")

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._knob_x: float = 0.0
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._knob_x = self._target_x()

        self._anim = QPropertyAnimation(self, b"knob_pos")
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _target_x(self) -> float:
        return float(self.width() - self.height() + 2) if self._checked else 2.0

    def _get_knob_pos(self) -> float:
        return self._knob_x

    def _set_knob_pos(self, v: float) -> None:
        self._knob_x = v
        self.update()

    knob_pos = pyqtProperty(float, _get_knob_pos, _set_knob_pos)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool) -> None:
        if self._checked == v:
            return
        self._checked = v
        self._animate()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._animate()
        self.toggled.emit(self._checked)

    def _animate(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob_x)
        self._anim.setEndValue(self._target_x())
        self._anim.start()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        ratio = (self._knob_x - 2) / max(w - h, 1)
        track = _lerp_color(self._TRACK_OFF, self._TRACK_ON, ratio)
        knob = _lerp_color(self._KNOB_OFF, self._KNOB_ON, ratio)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(0, 0, w, h, r, r)

        p.setBrush(knob)
        p.drawEllipse(int(self._knob_x), 2, h - 4, h - 4)
        p.end()


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
    )


# ────────────────────────────────────────────────────────────
# 任务卡片
# ────────────────────────────────────────────────────────────

class _TaskCardWidget(QFrame):
    """任务卡片组件：展示名称、描述、步骤数和开关。"""

    card_clicked = pyqtSignal(str)
    edit_info = pyqtSignal(str)
    toggle_enabled = pyqtSignal(str, bool)

    def __init__(self, task: dict, parent=None):
        super().__init__(parent)
        self._name = task["name"]
        self._enabled = task.get("enabled", False)
        self.setObjectName("taskCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(200, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build(task)
        self._apply_style()

    def _build(self, task: dict) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(12, 10, 12, 10)

        name = QLabel(task["name"])
        name.setStyleSheet("font-size: 14px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(name)

        desc = task.get("description", "") or "无描述"
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color: #a6adc8; font-size: 12px;")
        desc_lbl.setWordWrap(True)
        desc_lbl.setMaximumHeight(36)
        layout.addWidget(desc_lbl)

        steps_n = count_steps_recursive(task.get("steps", []))
        info = QLabel(f"{steps_n} 个步骤")
        info.setStyleSheet("color: #6c7086; font-size: 11px;")
        layout.addWidget(info)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._switch = _ToggleSwitch(checked=self._enabled)
        self._switch.toggled.connect(self._on_toggle)
        btn_row.addWidget(self._switch)

        self._state_label = QLabel()
        self._state_label.setStyleSheet("font-size: 11px;")
        self._update_state_label()
        btn_row.addWidget(self._state_label)

        btn_row.addStretch()

        edit_btn = QPushButton("编辑信息")
        edit_btn.setFixedHeight(26)
        edit_btn.clicked.connect(lambda: self.edit_info.emit(self._name))
        btn_row.addWidget(edit_btn)

        layout.addLayout(btn_row)

    def _apply_style(self) -> None:
        bc = "#a6e3a1" if self._enabled else "#313244"
        self.setStyleSheet(
            f"#taskCard {{ background-color:#1e1e2e; border:1px solid {bc}; border-radius:8px; }}"
            f"#taskCard:hover {{ border-color:#89b4fa; }}"
        )

    def _update_state_label(self) -> None:
        if self._enabled:
            self._state_label.setText("已开启")
            self._state_label.setStyleSheet("color:#a6e3a1; font-size:11px;")
        else:
            self._state_label.setText("已关闭")
            self._state_label.setStyleSheet("color:#6c7086; font-size:11px;")

    def _on_toggle(self, checked: bool) -> None:
        self._enabled = checked
        self._update_state_label()
        self._apply_style()
        self.toggle_enabled.emit(self._name, self._enabled)

    def mousePressEvent(self, event):
        self.card_clicked.emit(self._name)


# ────────────────────────────────────────────────────────────
# 步骤树
# ────────────────────────────────────────────────────────────

class _StepTreeWidget(QTreeWidget):
    """步骤树形控件，支持任意深度嵌套。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIndentation(24)
        self.setRootIsDecorated(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def _item_path(self, item: QTreeWidgetItem) -> tuple:
        """获取 item 的完整路径，支持任意深度。如 (0,), (0, 2), (0, 2, 1) 等。"""
        indices = []
        current = item
        while current:
            parent = current.parent()
            if parent is None:
                indices.append(self.indexOfTopLevelItem(current))
            else:
                indices.append(parent.indexOfChild(current))
            current = parent
        return tuple(reversed(indices))

    def current_path(self) -> tuple | None:
        item = self.currentItem()
        if item is None:
            return None
        return self._item_path(item)


# ────────────────────────────────────────────────────────────
# 主页面
# ────────────────────────────────────────────────────────────

class TaskConfigTab(QWidget):
    """任务配置页：卡片概览 + 步骤编辑器。"""

    _TYPE_COLORS = {
        "check": QColor("#89b4fa"),
        "whileif": QColor("#cba6f7"),
        "click": QColor("#a6e3a1"),
        "delay": QColor("#f9e2af"),
    }

    def __init__(self, task_manager: TaskManager | None = None,
                 template_manager=None, device_manager=None, parent=None):
        super().__init__(parent)
        self._task_mgr = task_manager
        self._tm = template_manager
        self._device_mgr = device_manager
        self._active_device: str | None = None
        self._executors: dict[str, "TaskExecutor"] = {}
        self._current_task: dict | None = None
        self._current_step_path: tuple | None = None
        self._updating = False
        self._setup_ui()

    # ================================================================
    # 顶层布局
    # ================================================================

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        if not self._task_mgr:
            root.addWidget(QLabel("任务管理器未初始化"))
            return

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_overview_page())
        self._stack.addWidget(self._build_editor_page())
        root.addWidget(self._stack)

        self._refresh_overview()

    # ================================================================
    # Page 0 — 任务概览
    # ================================================================

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("任务列表")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cdd6f4;")
        header.addWidget(title)
        header.addStretch()

        new_btn = QPushButton("+ 新建任务")
        new_btn.setProperty("role", "primary")
        new_btn.clicked.connect(self._on_new_task)
        header.addWidget(new_btn)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._card_container = QWidget()
        self._card_grid = QGridLayout(self._card_container)
        self._card_grid.setSpacing(12)
        self._card_grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._card_container)
        layout.addWidget(scroll)

        return page

    def _refresh_overview(self) -> None:
        while self._card_grid.count():
            item = self._card_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        tasks = self._task_mgr.tasks
        for i, task in enumerate(tasks):
            card = _TaskCardWidget(task)
            card.card_clicked.connect(self._on_card_clicked)
            card.edit_info.connect(self._on_edit_task_info)
            card.toggle_enabled.connect(self._on_toggle_task)
            self._card_grid.addWidget(card, i // COLS_PER_ROW, i % COLS_PER_ROW)

        for col in range(COLS_PER_ROW):
            self._card_grid.setColumnStretch(col, 1)
        last_row = (len(tasks) // COLS_PER_ROW) + 1
        spacer = QWidget()
        self._card_grid.addWidget(spacer, last_row, 0, 1, COLS_PER_ROW)
        self._card_grid.setRowStretch(last_row, 1)

    def _on_card_clicked(self, task_name: str) -> None:
        self._current_task = self._task_mgr.get_task(task_name)
        if not self._current_task:
            return
        self._editor_title.setText(f"编辑任务: {task_name}")
        self._current_step_path = None
        self._refresh_step_tree()
        self._stack.setCurrentIndex(1)

    def _on_new_task(self) -> None:
        name, ok = QInputDialog.getText(self, "新建任务", "任务名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if self._task_mgr.get_task(name):
            QMessageBox.warning(self, "名称重复", f"任务 \"{name}\" 已存在")
            return
        task = TaskManager.new_task(name)
        self._task_mgr.add_task(task)
        self._refresh_overview()

    def _on_edit_task_info(self, task_name: str) -> None:
        task = self._task_mgr.get_task(task_name)
        if not task:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("编辑任务信息")
        dlg.setMinimumWidth(340)
        fl = QVBoxLayout(dlg)

        fl.addWidget(QLabel("名称:"))
        name_ed = QLineEdit(task["name"])
        fl.addWidget(name_ed)

        fl.addWidget(QLabel("描述:"))
        desc_ed = QLineEdit(task.get("description", ""))
        fl.addWidget(desc_ed)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        fl.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_name = name_ed.text().strip()
        new_desc = desc_ed.text().strip()
        if not new_name:
            return

        if new_name != task_name:
            if not self._task_mgr.rename_task(task_name, new_name):
                QMessageBox.warning(self, "重命名失败", "名称可能已被占用")
                return

        updated = self._task_mgr.get_task(new_name)
        if updated:
            updated["description"] = new_desc
            self._task_mgr.add_task(updated)
        self._refresh_overview()

    def set_device_manager(self, dm) -> None:
        self._device_mgr = dm

    def set_active_device(self, address: str | None) -> None:
        self._active_device = address

    def stop_all_tasks(self) -> None:
        for name, executor in list(self._executors.items()):
            executor.stop()
            executor.wait(3000)
        self._executors.clear()

    def _on_toggle_task(self, task_name: str, enabled: bool) -> None:
        task = self._task_mgr.get_task(task_name)
        if not task:
            return
        task["enabled"] = enabled
        self._task_mgr.add_task(task)

        if enabled:
            self._start_task(task_name)
        else:
            self._stop_task(task_name)

    def _start_task(self, task_name: str) -> None:
        if task_name in self._executors:
            return
        if not self._active_device:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "无法启动", "请先连接设备后再启动任务")
            return
        if not self._device_mgr:
            return
        task = self._task_mgr.get_task(task_name)
        if not task:
            return
        executor = TaskExecutor(task, self._active_device,
                                self._device_mgr, self._tm, parent=self)
        executor.task_finished.connect(lambda name, ok: self._on_task_finished(name, ok))
        executor.log_message.connect(self._on_executor_log)
        self._executors[task_name] = executor
        executor.start()

    def _stop_task(self, task_name: str) -> None:
        executor = self._executors.pop(task_name, None)
        if executor:
            executor.stop()
            executor.wait(3000)

    def _on_task_finished(self, task_name: str, success: bool) -> None:
        self._executors.pop(task_name, None)
        task = self._task_mgr.get_task(task_name)
        if task:
            task["enabled"] = False
            self._task_mgr.add_task(task)
        self._update_card_switch(task_name, False)

    def _update_card_switch(self, task_name: str, enabled: bool) -> None:
        """更新任务卡片上的开关状态（不触发 toggle 信号）。"""
        for i in range(self._card_grid.count()):
            widget = self._card_grid.itemAt(i).widget()
            if isinstance(widget, _TaskCardWidget) and widget._name == task_name:
                widget._switch.blockSignals(True)
                widget._switch.setChecked(enabled)
                widget._enabled = enabled
                widget._update_state_label()
                widget._apply_style()
                widget._switch.blockSignals(False)
                break

    def _on_executor_log(self, msg: str) -> None:
        from src.core.logger import get_logger
        get_logger("task_executor").info(msg, extra={"device": self._active_device or "系统"})

    # ================================================================
    # Page 1 — 步骤编辑器
    # ================================================================

    def _build_editor_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        back_btn = QPushButton("← 返回任务列表")
        back_btn.clicked.connect(self._on_back)
        header.addWidget(back_btn)

        self._editor_title = QLabel("编辑任务")
        self._editor_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #cdd6f4;")
        header.addWidget(self._editor_title)
        header.addStretch()

        save_btn = QPushButton("保存")
        save_btn.setProperty("role", "primary")
        save_btn.setFixedWidth(70)
        save_btn.clicked.connect(self._on_save)
        header.addWidget(save_btn)

        del_btn = QPushButton("删除任务")
        del_btn.setProperty("role", "danger")
        del_btn.clicked.connect(self._on_delete_task)
        header.addWidget(del_btn)
        layout.addLayout(header)

        mid = QSplitter(Qt.Orientation.Horizontal)
        mid.addWidget(self._build_step_section())
        mid.addWidget(self._build_property_panel())
        mid.setStretchFactor(0, 3)
        mid.setStretchFactor(1, 2)
        mid.setSizes([560, 360])
        layout.addWidget(mid)

        return page

    def _on_back(self) -> None:
        self._commit_current_step()
        self._current_task = None
        self._current_step_path = None
        self._refresh_overview()
        self._stack.setCurrentIndex(0)

    def _on_delete_task(self) -> None:
        if not self._current_task:
            return
        name = self._current_task["name"]
        reply = QMessageBox.question(
            self, "确认删除", f"确定删除任务 \"{name}\" 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._task_mgr.remove_task(name)
            self._current_task = None
            self._on_back()

    # （模板库面板已移除，模板选择由属性面板的下拉框完成）

    # ---- 步骤列表 (树形) ----

    def _build_step_section(self) -> QGroupBox:
        group = QGroupBox("工作流步骤")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        for label, tip, stype in [
            ("+ 条件", "添加条件步骤（if）：验证模板存在则执行子步骤", "check"),
            ("+ 循环", "添加循环步骤（while）：条件成立时循环执行子步骤", "whileif"),
            ("+ 点击", "添加点击步骤：检测并点击模板", "click"),
            ("+ 延时", "添加延时步骤：步骤间等待", "delay"),
        ]:
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _, t=stype: self._on_add_step(t))
            toolbar.addWidget(btn)
        toolbar.addStretch()

        for text, tip, slot in [
            ("上移", "上移步骤", self._on_move_up),
            ("下移", "下移步骤", self._on_move_down),
            ("缩进", "缩进：将步骤移入上方条件步骤的子步骤中", self._on_indent),
            ("移出", "取消缩进：将子步骤移出到父级", self._on_unindent),
        ]:
            b = QPushButton(text)
            b.setStyleSheet("padding: 4px 6px;")
            b.setToolTip(tip)
            b.clicked.connect(slot)
            toolbar.addWidget(b)

        self._convert_btn = QPushButton("if⇄while")
        self._convert_btn.setToolTip("在条件(if)与循环(while)之间切换")
        self._convert_btn.setStyleSheet("padding: 4px 6px;")
        self._convert_btn.clicked.connect(self._on_convert_container)
        toolbar.addWidget(self._convert_btn)

        ds = QPushButton("删除步骤")
        ds.setProperty("role", "danger")
        ds.clicked.connect(self._on_delete_step)
        toolbar.addWidget(ds)
        layout.addLayout(toolbar)

        self._step_tree = _StepTreeWidget()
        self._step_tree.setColumnCount(3)
        self._step_tree.setHeaderLabels(["类型", "目标", "参数"])
        h = self._step_tree.header()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)
        self._step_tree.setColumnWidth(0, 100)
        self._step_tree.setColumnWidth(1, 200)
        self._step_tree.currentItemChanged.connect(self._on_tree_item_changed)
        layout.addWidget(self._step_tree)
        return group

    # ---- 属性面板 ----

    def _build_property_panel(self) -> QWidget:
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)

        self._prop_group = QGroupBox("步骤属性")
        inner_widget = QWidget()
        outer = QVBoxLayout(inner_widget)
        outer.setSpacing(6)
        outer.setContentsMargins(8, 16, 8, 8)

        # ─── 基本信息分组 ───
        basic_box = QGroupBox("基本信息")
        basic_layout = QVBoxLayout(basic_box)
        basic_layout.setSpacing(4)
        basic_layout.setContentsMargins(8, 12, 8, 8)

        self._tpl_label = QLabel("目标模板")
        basic_layout.addWidget(self._tpl_label)
        self._template_combo = QComboBox()
        self._template_combo.setEditable(True)
        self._template_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._template_combo.completer().setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion)
        self._template_combo.completer().setFilterMode(
            Qt.MatchFlag.MatchContains)
        basic_layout.addWidget(self._template_combo)

        self._tpl_preview = QLabel()
        self._tpl_preview.setFixedHeight(64)
        self._tpl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tpl_preview.setStyleSheet("background: #1e1e2e; border-radius: 4px;")
        basic_layout.addWidget(self._tpl_preview)

        basic_layout.addWidget(QLabel("步骤描述"))
        self._step_desc = QLineEdit()
        self._step_desc.setPlaceholderText("可选描述")
        basic_layout.addWidget(self._step_desc)

        outer.addWidget(basic_box)

        self._prop_stack = QStackedWidget()

        # ═══ Page 0: check（条件）— 轮询检测参数 ═══
        check_page = QWidget()
        check_layout = QVBoxLayout(check_page)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.setSpacing(6)

        # 检测行为
        behavior_box = QGroupBox("检测行为")
        behavior_layout = QVBoxLayout(behavior_box)
        behavior_layout.setSpacing(4)
        behavior_layout.setContentsMargins(8, 12, 8, 8)

        retry_row = QHBoxLayout()
        retry_row.addWidget(QLabel("轮询检测"))
        retry_row.addStretch()
        self._retry_switch = _ToggleSwitch(checked=False)
        self._retry_switch.toggled.connect(self._on_retry_toggled)
        retry_row.addWidget(self._retry_switch)
        behavior_layout.addLayout(retry_row)

        fail_row = QHBoxLayout()
        fail_row.addWidget(QLabel("失败处理"))
        fail_row.addStretch()
        self._check_on_fail = QComboBox()
        self._check_on_fail.addItem("跳过此步", "skip")
        self._check_on_fail.addItem("停止任务", "stop")
        self._check_on_fail.setFixedWidth(100)
        fail_row.addWidget(self._check_on_fail)
        behavior_layout.addLayout(fail_row)

        check_layout.addWidget(behavior_box)

        # 轮询参数
        self._poll_box = QGroupBox("轮询参数")
        poll_layout = QVBoxLayout(self._poll_box)
        poll_layout.setSpacing(4)
        poll_layout.setContentsMargins(8, 12, 8, 8)

        poll_layout.addWidget(QLabel("检测间隔"))
        self._retry_interval = QSpinBox()
        self._retry_interval.setRange(100, 600000)
        self._retry_interval.setValue(1000)
        self._retry_interval.setSingleStep(100)
        self._retry_interval.setSuffix(" ms")
        poll_layout.addWidget(self._retry_interval)

        poll_layout.addWidget(QLabel("超时模式"))
        self._mode_group = QButtonGroup(self)
        self._time_radio = QRadioButton("时间限制")
        self._count_radio = QRadioButton("次数限制")
        self._mode_group.addButton(self._time_radio, 0)
        self._mode_group.addButton(self._count_radio, 1)
        self._time_radio.setChecked(True)
        poll_layout.addWidget(self._time_radio)
        poll_layout.addWidget(self._count_radio)

        poll_layout.addWidget(QLabel("最大超时"))
        self._max_timeout = QSpinBox()
        self._max_timeout.setRange(1000, 3600000)
        self._max_timeout.setValue(30000)
        self._max_timeout.setSingleStep(1000)
        self._max_timeout.setSuffix(" ms")
        poll_layout.addWidget(self._max_timeout)

        poll_layout.addWidget(QLabel("最大次数"))
        self._max_retries = QSpinBox()
        self._max_retries.setRange(1, 1000)
        self._max_retries.setValue(10)
        self._max_retries.setSuffix(" 次")
        poll_layout.addWidget(self._max_retries)

        self._mode_group.idToggled.connect(self._on_timeout_mode_changed)
        check_layout.addWidget(self._poll_box)
        check_layout.addStretch()
        self._prop_stack.addWidget(check_page)

        # ═══ Page 1: click（点击）— 触摸参数 ═══
        click_page = QWidget()
        click_layout = QVBoxLayout(click_page)
        click_layout.setContentsMargins(0, 0, 0, 0)
        click_layout.setSpacing(6)

        touch_box = QGroupBox("触摸参数")
        touch_layout = QVBoxLayout(touch_box)
        touch_layout.setSpacing(4)
        touch_layout.setContentsMargins(8, 12, 8, 8)

        touch_layout.addWidget(QLabel("触发延迟"))
        self._trigger_delay = QSpinBox()
        self._trigger_delay.setRange(0, 60000)
        self._trigger_delay.setValue(250)
        self._trigger_delay.setSingleStep(50)
        self._trigger_delay.setSuffix(" ms")
        self._trigger_delay.setToolTip("匹配成功后，等待多久再执行点击")
        touch_layout.addWidget(self._trigger_delay)

        touch_layout.addWidget(QLabel("触摸时长"))
        self._touch_duration = QSpinBox()
        self._touch_duration.setRange(10, 10000)
        self._touch_duration.setValue(50)
        self._touch_duration.setSingleStep(50)
        self._touch_duration.setSuffix(" ms")
        touch_layout.addWidget(self._touch_duration)

        touch_layout.addWidget(QLabel("触摸后延时"))
        self._after_delay = QSpinBox()
        self._after_delay.setRange(0, 3600000)
        self._after_delay.setValue(200)
        self._after_delay.setSingleStep(100)
        self._after_delay.setSuffix(" ms")
        touch_layout.addWidget(self._after_delay)

        click_layout.addWidget(touch_box)

        click_fail_box = QGroupBox("失败处理")
        cfb_layout = QVBoxLayout(click_fail_box)
        cfb_layout.setSpacing(4)
        cfb_layout.setContentsMargins(8, 12, 8, 8)
        cfb_row = QHBoxLayout()
        cfb_row.addWidget(QLabel("未找到模板"))
        cfb_row.addStretch()
        self._click_on_fail = QComboBox()
        self._click_on_fail.addItem("跳过此步", "skip")
        self._click_on_fail.addItem("停止任务", "stop")
        self._click_on_fail.setFixedWidth(100)
        cfb_row.addWidget(self._click_on_fail)
        cfb_layout.addLayout(cfb_row)
        click_layout.addWidget(click_fail_box)

        click_layout.addStretch()
        self._prop_stack.addWidget(click_page)

        # ═══ Page 2: delay（延时） ═══
        delay_page = QWidget()
        delay_layout = QVBoxLayout(delay_page)
        delay_layout.setContentsMargins(0, 0, 0, 0)
        delay_layout.setSpacing(6)

        delay_box = QGroupBox("延时设置")
        dbl = QVBoxLayout(delay_box)
        dbl.setSpacing(4)
        dbl.setContentsMargins(8, 12, 8, 8)
        dbl.addWidget(QLabel("等待时长"))
        self._delay_duration = QSpinBox()
        self._delay_duration.setRange(100, 3600000)
        self._delay_duration.setValue(1000)
        self._delay_duration.setSingleStep(100)
        self._delay_duration.setSuffix(" ms")
        dbl.addWidget(self._delay_duration)
        delay_layout.addWidget(delay_box)
        delay_layout.addStretch()
        self._prop_stack.addWidget(delay_page)

        # ═══ Page 3: whileif（循环） ═══
        while_page = QWidget()
        while_layout = QVBoxLayout(while_page)
        while_layout.setContentsMargins(0, 0, 0, 0)
        while_layout.setSpacing(6)

        while_box = QGroupBox("循环参数")
        wbl = QVBoxLayout(while_box)
        wbl.setSpacing(4)
        wbl.setContentsMargins(8, 12, 8, 8)

        wbl.addWidget(QLabel("每轮检测间隔"))
        self._while_interval = QSpinBox()
        self._while_interval.setRange(100, 3600000)
        self._while_interval.setValue(1000)
        self._while_interval.setSingleStep(100)
        self._while_interval.setSuffix(" ms")
        wbl.addWidget(self._while_interval)

        wbl.addWidget(QLabel("退出模式"))
        self._while_mode_group = QButtonGroup(self)
        self._while_time_radio = QRadioButton("时间限制")
        self._while_count_radio = QRadioButton("次数限制")
        self._while_mode_group.addButton(self._while_time_radio, 0)
        self._while_mode_group.addButton(self._while_count_radio, 1)
        self._while_time_radio.setChecked(True)
        wbl.addWidget(self._while_time_radio)
        wbl.addWidget(self._while_count_radio)

        wbl.addWidget(QLabel("最大执行时间"))
        self._while_max_timeout = QSpinBox()
        self._while_max_timeout.setRange(1000, 3600000)
        self._while_max_timeout.setValue(1000)
        self._while_max_timeout.setSingleStep(1000)
        self._while_max_timeout.setSuffix(" ms")
        wbl.addWidget(self._while_max_timeout)

        wbl.addWidget(QLabel("最大循环次数"))
        self._while_max_loops = QSpinBox()
        self._while_max_loops.setRange(1, 10000)
        self._while_max_loops.setValue(2)
        self._while_max_loops.setSuffix(" 次")
        wbl.addWidget(self._while_max_loops)

        self._while_mode_group.idToggled.connect(self._on_while_mode_changed)

        hint = QLabel("条件不成立或达到上限时退出循环")
        hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        wbl.addWidget(hint)
        while_layout.addWidget(while_box)
        while_layout.addStretch()
        self._prop_stack.addWidget(while_page)

        outer.addWidget(self._prop_stack)

        # 属性变更时同步步骤树显示
        self._template_combo.currentIndexChanged.connect(self._sync_step_tree_item)
        self._template_combo.currentIndexChanged.connect(self._update_tpl_preview)
        self._check_on_fail.currentIndexChanged.connect(self._sync_step_tree_item)
        self._click_on_fail.currentIndexChanged.connect(self._sync_step_tree_item)
        self._retry_interval.valueChanged.connect(self._sync_step_tree_item)
        self._while_interval.valueChanged.connect(self._sync_step_tree_item)
        self._while_max_timeout.valueChanged.connect(self._sync_step_tree_item)
        self._while_max_loops.valueChanged.connect(self._sync_step_tree_item)
        self._max_timeout.valueChanged.connect(self._sync_step_tree_item)
        self._max_retries.valueChanged.connect(self._sync_step_tree_item)
        self._trigger_delay.valueChanged.connect(self._sync_step_tree_item)
        self._touch_duration.valueChanged.connect(self._sync_step_tree_item)
        self._after_delay.valueChanged.connect(self._sync_step_tree_item)
        self._delay_duration.valueChanged.connect(self._sync_step_tree_item)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner_widget)

        prop_layout = QVBoxLayout(self._prop_group)
        prop_layout.setContentsMargins(0, 0, 0, 0)
        prop_layout.addWidget(scroll)

        wrapper_layout.addWidget(self._prop_group)
        self._prop_group.setEnabled(False)
        return wrapper

    # ================================================================
    # 模板下拉框（搜索 + 图片）
    # ================================================================

    def _populate_template_combo(self) -> None:
        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        if not self._tm:
            self._template_combo.blockSignals(False)
            return
        icon_size = QSize(32, 32)
        self._template_combo.setIconSize(icon_size)
        for tpl in self._tm.templates:
            label = tpl.get("description") or tpl["name"]
            display = f"{label} [{tpl.get('category', '')}]"
            icon = self._get_template_icon(tpl)
            if icon:
                self._template_combo.addItem(icon, display, tpl["name"])
            else:
                self._template_combo.addItem(display, tpl["name"])
        self._template_combo.blockSignals(False)

    def _get_template_icon(self, tpl: dict) -> QIcon | None:
        if not self._tm:
            return None
        name = tpl.get("name", "")
        path = self._tm.get_template_path(name)
        if not path or not path.is_file():
            return None
        pm = QPixmap(str(path))
        if pm.isNull():
            return None
        return QIcon(pm.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation))

    def _select_template_in_combo(self, template_name: str) -> None:
        idx = self._template_combo.findData(template_name)
        if idx >= 0:
            self._template_combo.setCurrentIndex(idx)
        elif template_name:
            self._template_combo.addItem(template_name, template_name)
            self._template_combo.setCurrentIndex(self._template_combo.count() - 1)

    def _update_tpl_preview(self) -> None:
        tpl_name = self._template_combo.currentData()
        if not tpl_name or not self._tm:
            self._tpl_preview.clear()
            return
        tpl = self._tm.get_template(tpl_name)
        if not tpl:
            self._tpl_preview.clear()
            return
        icon = self._get_template_icon(tpl)
        if icon:
            pm = icon.pixmap(QSize(120, 60))
            self._tpl_preview.setPixmap(pm)
        else:
            self._tpl_preview.setText("(无预览)")

    # ================================================================
    # 步骤操作
    # ================================================================

    def _insert_template_as_step(self, template_name: str) -> None:
        if not self._current_task:
            return
        self._commit_current_step()
        step = self._make_click_step(template_name)
        new_path = self._insert_step_near(self._current_step_path, step)
        self._refresh_step_tree(preserve_state=True)
        self._select_path(new_path)

    def _make_click_step(self, template_name: str) -> dict:
        step = TaskManager.create_step("click")
        step["template"] = template_name
        if self._tm:
            tpl = self._tm.get_template(template_name)
            if tpl and tpl.get("description"):
                step["description"] = f"点击{tpl['description']}"
        return step

    def _insert_step_near(self, path: tuple | None, step: dict) -> tuple:
        """在 path 附近插入 step，返回插入后的路径。支持任意深度。"""
        steps = self._current_task.setdefault("steps", [])
        if not path:
            steps.append(step)
            return (len(steps) - 1,)

        selected = self._get_step_at(path)
        if selected and selected.get("type") in CONTAINER_TYPES:
            children = selected.setdefault("children", [])
            children.append(step)
            return path + (len(children) - 1,)

        sibling_list = self._get_sibling_list(path)
        if sibling_list is not None:
            idx = path[-1] + 1
            sibling_list.insert(idx, step)
            return path[:-1] + (idx,)

        steps.append(step)
        return (len(steps) - 1,)

    # ================================================================
    # 步骤树操作
    # ================================================================

    def _get_step_at(self, path: tuple) -> dict | None:
        """根据路径获取步骤 dict，支持任意深度。"""
        if not self._current_task or not path:
            return None
        steps = self._current_task.get("steps", [])
        node = None
        for i, idx in enumerate(path):
            target = steps if i == 0 else node.get("children", [])
            if idx >= len(target):
                return None
            node = target[idx]
            if i < len(path) - 1 and node.get("type") not in CONTAINER_TYPES:
                return None
        return node

    def _get_sibling_list(self, path: tuple) -> list | None:
        """获取 path 所在的兄弟列表（即其父级的 children 或根 steps）。"""
        if not self._current_task or not path:
            return None
        if len(path) == 1:
            return self._current_task.get("steps", [])
        parent = self._get_step_at(path[:-1])
        if parent and parent.get("type") in CONTAINER_TYPES:
            return parent.setdefault("children", [])
        return None

    def _refresh_step_tree(self, preserve_state: bool = False) -> None:
        self._updating = True
        expanded_paths: set[tuple] = set()
        selected_path = self._current_step_path

        if preserve_state:
            self._collect_expanded(expanded_paths)

        self._step_tree.clear()
        self._current_step_path = None

        if not self._current_task:
            self._prop_group.setEnabled(False)
            self._updating = False
            return

        steps = self._current_task.get("steps", [])
        for i, step in enumerate(steps):
            item = self._build_tree_item_recursive(step, (i,), expanded_paths if preserve_state else None)
            self._step_tree.addTopLevelItem(item)
            if not preserve_state and step.get("type") in CONTAINER_TYPES:
                item.setExpanded(True)
            elif preserve_state and (i,) in expanded_paths:
                item.setExpanded(True)

        self._updating = False
        if preserve_state and selected_path:
            self._select_path(selected_path)
        elif steps:
            self._step_tree.setCurrentItem(self._step_tree.topLevelItem(0))
        else:
            self._prop_group.setEnabled(False)

    def _collect_expanded(self, result: set, item=None, path: tuple = ()) -> None:
        """递归收集所有展开节点的路径。"""
        if item is None:
            for i in range(self._step_tree.topLevelItemCount()):
                top = self._step_tree.topLevelItem(i)
                p = (i,)
                if top.isExpanded():
                    result.add(p)
                self._collect_expanded(result, top, p)
        else:
            for i in range(item.childCount()):
                child = item.child(i)
                p = path + (i,)
                if child.isExpanded():
                    result.add(p)
                self._collect_expanded(result, child, p)

    def _build_tree_item_recursive(self, step: dict, path: tuple = (),
                                     expanded_set: set | None = None) -> QTreeWidgetItem:
        """递归构建树节点，支持任意深度嵌套。"""
        item = self._make_step_item(step)
        if step.get("type") in CONTAINER_TYPES:
            for i, child_step in enumerate(step.get("children", [])):
                child_path = path + (i,)
                child_item = self._build_tree_item_recursive(child_step, child_path, expanded_set)
                item.addChild(child_item)
                if expanded_set is not None:
                    if child_path in expanded_set:
                        child_item.setExpanded(True)
                elif child_step.get("type") in CONTAINER_TYPES:
                    child_item.setExpanded(True)
        return item

    @staticmethod
    def _fmt_ms(ms: int) -> str:
        if ms >= 60000 and ms % 60000 == 0:
            return f"{ms // 60000}min"
        if ms >= 1000 and ms % 1000 == 0:
            return f"{ms // 1000}s"
        return f"{ms}ms"

    def _make_step_item(self, step: dict) -> QTreeWidgetItem:
        stype = step.get("type", "?")
        label = STEP_TYPE_LABELS.get(stype, stype)
        color = self._TYPE_COLORS.get(stype, QColor("#cdd6f4"))

        if stype == "delay":
            target = self._fmt_ms(step.get("duration_ms", 1000))
        else:
            tpl_name = step.get("template", "")
            tpl_meta = self._tm.get_template(tpl_name) if self._tm and tpl_name else None
            target = tpl_meta.get("description", tpl_name) if tpl_meta else tpl_name

        if stype == "check":
            label_text = f"if ({target})"
        elif stype == "whileif":
            label_text = f"while ({target})"
        else:
            label_text = label

        params = self._build_params_text(step, stype)
        item = QTreeWidgetItem([label_text, target, params])
        item.setForeground(0, color)
        return item

    def _build_params_text(self, step: dict, stype: str) -> str:
        if stype == "check":
            retry = step.get("retry_enabled", False)
            if retry:
                intv = self._fmt_ms(step.get("retry_interval_ms", 1000))
                mode = step.get("timeout_mode", "time")
                if mode == "time":
                    timeout = self._fmt_ms(step.get("max_timeout_ms", 30000))
                    params = f"轮询{intv} / 超时{timeout}"
                else:
                    params = f"轮询{intv} / 最多{step.get('max_retries', 10)}次"
            else:
                params = "单次检测"
            on_fail = step.get("on_fail", "skip")
            params += f" | 失败{'跳过' if on_fail == 'skip' else '停止'}"
            return params
        elif stype == "whileif":
            intv = self._fmt_ms(step.get("check_interval_ms", 1000))
            mode = step.get("timeout_mode", "time")
            if mode == "time":
                limit = self._fmt_ms(step.get("max_timeout_ms", 60000))
                return f"间隔{intv} / 超时{limit}"
            else:
                return f"间隔{intv} / 最多{step.get('max_loops', 20)}轮"
        elif stype == "click":
            trig = step.get("trigger_delay_ms", 250)
            td = step.get("touch_duration_ms", 50)
            ad = step.get("after_delay_ms", 200)
            parts = []
            if trig > 0:
                parts.append(f"延{self._fmt_ms(trig)}")
            parts.append(f"按住{self._fmt_ms(td)}")
            if ad > 0:
                parts.append(f"后延{self._fmt_ms(ad)}")
            on_fail = step.get("on_fail", "skip")
            parts.append(f"失败{'跳过' if on_fail == 'skip' else '停止'}")
            return " | ".join(parts)
        return ""

    def _select_path(self, path: tuple) -> None:
        """选中任意深度的路径对应的树节点。"""
        if not path:
            return
        item = self._step_tree.topLevelItem(path[0])
        for level_idx in path[1:]:
            if item is None:
                return
            item = item.child(level_idx)
        if item:
            self._step_tree.setCurrentItem(item)

    def _on_tree_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem) -> None:
        if self._updating:
            return
        if previous:
            self._commit_current_step()
        path = self._step_tree.current_path()
        self._current_step_path = path
        self._load_step_properties()

    def _on_add_step(self, step_type: str) -> None:
        """添加步骤：如果当前选中的是条件步骤，新步骤作为其子步骤；否则作为兄弟步骤插入到后面。"""
        if not self._current_task:
            return
        self._commit_current_step()
        step = TaskManager.create_step(step_type)
        steps = self._current_task.setdefault("steps", [])
        path = self._current_step_path

        if not path:
            steps.append(step)
            new_path = (len(steps) - 1,)
        else:
            selected = self._get_step_at(path)
            if selected and selected.get("type") in CONTAINER_TYPES:
                children = selected.setdefault("children", [])
                children.append(step)
                new_path = path + (len(children) - 1,)
            else:
                sibling_list = self._get_sibling_list(path)
                if sibling_list is None:
                    steps.append(step)
                    new_path = (len(steps) - 1,)
                else:
                    idx = path[-1] + 1
                    sibling_list.insert(idx, step)
                    new_path = path[:-1] + (idx,)

        self._refresh_step_tree(preserve_state=True)
        self._select_path(new_path)

    def _on_move_up(self) -> None:
        path = self._current_step_path
        if not self._current_task or not path:
            return
        idx = path[-1]
        if idx <= 0:
            return
        self._commit_current_step()
        sibling_list = self._get_sibling_list(path)
        if not sibling_list:
            return
        sibling_list[idx - 1], sibling_list[idx] = sibling_list[idx], sibling_list[idx - 1]
        new_path = path[:-1] + (idx - 1,)
        self._refresh_step_tree(preserve_state=True)
        self._select_path(new_path)

    def _on_move_down(self) -> None:
        path = self._current_step_path
        if not self._current_task or not path:
            return
        self._commit_current_step()
        sibling_list = self._get_sibling_list(path)
        if not sibling_list:
            return
        idx = path[-1]
        if idx >= len(sibling_list) - 1:
            return
        sibling_list[idx], sibling_list[idx + 1] = sibling_list[idx + 1], sibling_list[idx]
        new_path = path[:-1] + (idx + 1,)
        self._refresh_step_tree(preserve_state=True)
        self._select_path(new_path)

    def _on_indent(self) -> None:
        """将步骤缩进到同级上方最近的条件步骤中（任意层级）。"""
        path = self._current_step_path
        if not self._current_task or not path:
            return
        idx = path[-1]
        if idx <= 0:
            return
        sibling_list = self._get_sibling_list(path)
        if not sibling_list:
            return
        prev_step = sibling_list[idx - 1]
        if prev_step.get("type") not in CONTAINER_TYPES:
            return
        self._commit_current_step()
        step = sibling_list.pop(idx)
        children = prev_step.setdefault("children", [])
        children.append(step)
        new_path = path[:-1] + (idx - 1, len(children) - 1)
        self._refresh_step_tree(preserve_state=True)
        self._select_path(new_path)

    def _on_unindent(self) -> None:
        """将子步骤移出到父条件步骤之后（任意层级）。"""
        path = self._current_step_path
        if not self._current_task or not path or len(path) < 2:
            return
        self._commit_current_step()
        parent_path = path[:-1]
        parent_sibling_list = self._get_sibling_list(parent_path)
        if not parent_sibling_list:
            return
        parent_step = self._get_step_at(parent_path)
        if not parent_step or parent_step.get("type") not in CONTAINER_TYPES:
            return
        children = parent_step.get("children", [])
        child_idx = path[-1]
        if child_idx >= len(children):
            return
        step = children.pop(child_idx)
        insert_at = parent_path[-1] + 1
        parent_sibling_list.insert(insert_at, step)
        new_path = parent_path[:-1] + (insert_at,)
        self._refresh_step_tree(preserve_state=True)
        self._select_path(new_path)

    def _on_delete_step(self) -> None:
        path = self._current_step_path
        if not self._current_task or not path:
            return
        sibling_list = self._get_sibling_list(path)
        if not sibling_list:
            return
        idx = path[-1]
        if idx >= len(sibling_list):
            return
        sibling_list.pop(idx)
        self._refresh_step_tree(preserve_state=True)

    def _on_convert_container(self) -> None:
        """在 check(if) 和 whileif(while) 之间互相转换。"""
        if not self._current_task or not self._current_step_path:
            return
        step = self._get_step_at(self._current_step_path)
        if not step:
            return
        stype = step.get("type", "")
        if stype == "check":
            step["type"] = "whileif"
            step.setdefault("check_interval_ms", 1000)
            step.pop("retry_enabled", None)
            step.pop("retry_interval_ms", None)
            step.pop("timeout_mode", None)
            step.pop("max_timeout_ms", None)
            step.pop("max_retries", None)
            step.pop("on_fail", None)
        elif stype == "whileif":
            step["type"] = "check"
            step.setdefault("retry_enabled", False)
            step.setdefault("retry_interval_ms", 1000)
            step.setdefault("timeout_mode", "time")
            step.setdefault("max_timeout_ms", 30000)
            step.setdefault("max_retries", 10)
            step.setdefault("on_fail", "skip")
            step.pop("check_interval_ms", None)
        else:
            return
        self._refresh_step_tree(preserve_state=True)
        self._select_path(self._current_step_path)

    # ================================================================
    # 属性面板
    # ================================================================

    def _load_step_properties(self) -> None:
        step = self._get_step_at(self._current_step_path) if self._current_step_path else None
        if not step:
            self._prop_group.setEnabled(False)
            return

        self._updating = True
        stype = step.get("type", "check")
        self._prop_group.setEnabled(True)

        path_desc = ""
        if self._current_step_path:
            path_str = ".".join(str(i + 1) for i in self._current_step_path)
            path_desc = f" (步骤 {path_str})"
        self._prop_group.setTitle(f"步骤属性{path_desc} — {STEP_TYPE_LABELS.get(stype, stype)}")

        show_tpl = stype in ("check", "click", "whileif")
        self._tpl_label.setVisible(show_tpl)
        self._template_combo.setVisible(show_tpl)
        if show_tpl:
            self._populate_template_combo()
            self._select_template_in_combo(step.get("template", ""))

        self._step_desc.setText(step.get("description", ""))
        self._prop_stack.setCurrentIndex({"check": 0, "click": 1, "delay": 2, "whileif": 3}.get(stype, 0))

        if stype == "check":
            retry_on = step.get("retry_enabled", False)
            self._retry_switch.setChecked(retry_on)
            self._on_retry_toggled(retry_on)
            self._retry_interval.setValue(step.get("retry_interval_ms", 1000))
            mode = step.get("timeout_mode", "time")
            self._time_radio.setChecked(mode == "time")
            self._count_radio.setChecked(mode == "count")
            self._max_timeout.setValue(step.get("max_timeout_ms", 30000))
            self._max_retries.setValue(step.get("max_retries", 10))
            self._on_timeout_mode_changed()
            on_fail = step.get("on_fail", "skip")
            idx = self._check_on_fail.findData(on_fail)
            self._check_on_fail.setCurrentIndex(idx if idx >= 0 else 0)
        elif stype == "click":
            self._trigger_delay.setValue(step.get("trigger_delay_ms", 250))
            self._touch_duration.setValue(step.get("touch_duration_ms", 50))
            self._after_delay.setValue(step.get("after_delay_ms", 200))
            on_fail = step.get("on_fail", "skip")
            idx = self._click_on_fail.findData(on_fail)
            self._click_on_fail.setCurrentIndex(idx if idx >= 0 else 0)
        elif stype == "whileif":
            self._while_interval.setValue(step.get("check_interval_ms", 1000))
            mode = step.get("timeout_mode", "time")
            self._while_time_radio.setChecked(mode == "time")
            self._while_count_radio.setChecked(mode == "count")
            self._while_max_timeout.setValue(step.get("max_timeout_ms", 1000))
            self._while_max_loops.setValue(step.get("max_loops", 2))
            self._on_while_mode_changed()
        elif stype == "delay":
            self._delay_duration.setValue(step.get("duration_ms", 1000))

        self._updating = False

    def _on_retry_toggled(self, enabled: bool) -> None:
        """轮询开关切换时，显示/隐藏轮询参数分组。"""
        self._poll_box.setVisible(enabled)
        self._sync_step_tree_item()

    def _on_timeout_mode_changed(self) -> None:
        is_time = self._time_radio.isChecked()
        self._max_timeout.setEnabled(is_time)
        self._max_retries.setEnabled(not is_time)
        self._sync_step_tree_item()

    def _on_while_mode_changed(self) -> None:
        is_time = self._while_time_radio.isChecked()
        self._while_max_timeout.setEnabled(is_time)
        self._while_max_loops.setEnabled(not is_time)
        self._sync_step_tree_item()

    def _sync_step_tree_item(self) -> None:
        """将当前属性面板的值同步到步骤树对应行的显示列。"""
        if self._updating or not self._current_step_path:
            return
        self._commit_current_step()
        step = self._get_step_at(self._current_step_path)
        if not step:
            return
        item = self._step_tree.currentItem()
        if not item:
            return
        stype = step.get("type", "")
        if stype == "delay":
            item.setText(1, self._fmt_ms(step.get("duration_ms", 1000)))
        else:
            tpl_name = step.get("template", "")
            tpl_meta = self._tm.get_template(tpl_name) if self._tm and tpl_name else None
            target = tpl_meta.get("description", tpl_name) if tpl_meta else tpl_name
            item.setText(1, target)
            if stype == "check":
                item.setText(0, f"if ({target})")
            elif stype == "whileif":
                item.setText(0, f"while ({target})")

        item.setText(2, self._build_params_text(step, stype))

    def _commit_current_step(self) -> None:
        if self._updating or not self._current_task or not self._current_step_path:
            return
        step = self._get_step_at(self._current_step_path)
        if not step:
            return
        stype = step.get("type", "")
        step["description"] = self._step_desc.text().strip()
        if stype in ("check", "click", "whileif"):
            step["template"] = self._template_combo.currentData() or ""
        if stype == "check":
            step["retry_enabled"] = self._retry_switch.isChecked()
            step["on_fail"] = self._check_on_fail.currentData() or "skip"
            if step["retry_enabled"]:
                step["retry_interval_ms"] = self._retry_interval.value()
                step["timeout_mode"] = "time" if self._time_radio.isChecked() else "count"
                step["max_timeout_ms"] = self._max_timeout.value()
                step["max_retries"] = self._max_retries.value()
        elif stype == "whileif":
            step["check_interval_ms"] = self._while_interval.value()
            step["timeout_mode"] = "time" if self._while_time_radio.isChecked() else "count"
            step["max_timeout_ms"] = self._while_max_timeout.value()
            step["max_loops"] = self._while_max_loops.value()
        elif stype == "click":
            step["trigger_delay_ms"] = self._trigger_delay.value()
            step["touch_duration_ms"] = self._touch_duration.value()
            step["after_delay_ms"] = self._after_delay.value()
            step["on_fail"] = self._click_on_fail.currentData() or "skip"
        elif stype == "delay":
            step["duration_ms"] = self._delay_duration.value()

    # ================================================================
    # 保存
    # ================================================================

    def _on_save(self) -> None:
        if not self._current_task or not self._task_mgr:
            return
        self._commit_current_step()
        self._task_mgr.add_task(self._current_task)
        QMessageBox.information(self, "已保存", f"任务 \"{self._current_task['name']}\" 已保存")
