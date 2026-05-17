"""可复用的模板树形列表控件。

功能:
    - 按分类（文件夹）分组展示模板
    - 可选搜索过滤
    - 可选拖拽支持（用于任务配置页拖拽添加步骤）
    - 统一 MIME 类型 application/x-mhg2ga-template

被 TemplateWorkspace 和 TaskConfigTab 复用。
"""

from PyQt6.QtCore import Qt, QMimeData, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView,
)

TPL_MIME_TYPE = "application/x-mhg2ga-template"


class TemplateTreeWidget(QTreeWidget):
    """分类树形模板列表，支持可选拖拽。"""

    template_selected = pyqtSignal(dict)

    def __init__(self, drag_enabled: bool = False, parent=None):
        super().__init__(parent)
        self._drag_enabled = drag_enabled

        self.setHeaderLabels(["名称", "尺寸", "阈值"])
        self.setRootIsDecorated(True)
        h = self.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        if drag_enabled:
            self.setDragEnabled(True)
            self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
            self.setDefaultDropAction(Qt.DropAction.CopyAction)

        self.currentItemChanged.connect(self._emit_template_signal)

    # ----------------------------------------------------------------
    # 数据填充
    # ----------------------------------------------------------------

    def populate(self, templates: list[dict], categories: list[str]) -> None:
        """填充树。categories 为所有要显示的分类名（含空分类）。"""
        self.clear()
        cat_nodes: dict[str, QTreeWidgetItem] = {}

        for cat in categories:
            node = self._make_category_node(cat)
            self.addTopLevelItem(node)
            node.setExpanded(True)
            cat_nodes[cat] = node

        for t in templates:
            cat = t.get("category", "common")
            if cat not in cat_nodes:
                node = self._make_category_node(cat)
                self.addTopLevelItem(node)
                node.setExpanded(True)
                cat_nodes[cat] = node

            size = f'{t.get("width", "?")}×{t.get("height", "?")}'
            threshold = f'{t.get("threshold", 0.80):.2f}'
            display = t.get("description") or t["name"]
            item = QTreeWidgetItem([display, size, threshold])
            item.setData(0, Qt.ItemDataRole.UserRole, t)
            item.setToolTip(0, t["name"])
            cat_nodes[cat].addChild(item)

    # ----------------------------------------------------------------
    # 查询 / 选中
    # ----------------------------------------------------------------

    def current_template(self) -> dict | None:
        item = self.currentItem()
        if not item:
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    def select_template(self, name: str) -> bool:
        for i in range(self.topLevelItemCount()):
            cat_item = self.topLevelItem(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                data = child.data(0, Qt.ItemDataRole.UserRole)
                if data and data.get("name") == name:
                    self.setCurrentItem(child)
                    return True
        return False

    def template_count(self) -> int:
        total = 0
        for i in range(self.topLevelItemCount()):
            total += self.topLevelItem(i).childCount()
        return total

    # ----------------------------------------------------------------
    # 拖拽
    # ----------------------------------------------------------------

    def startDrag(self, _supported_actions):
        if not self._drag_enabled:
            super().startDrag(_supported_actions)
            return
        item = self.currentItem()
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        name = data.get("name", "")
        if not name:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(TPL_MIME_TYPE, name.encode("utf-8"))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    # ----------------------------------------------------------------
    # 内部
    # ----------------------------------------------------------------

    @staticmethod
    def _make_category_node(cat: str) -> QTreeWidgetItem:
        node = QTreeWidgetItem([f"📁 {cat}", "", ""])
        node.setData(0, Qt.ItemDataRole.UserRole + 1, cat)
        node.setFlags(
            node.flags() & ~Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        )
        return node

    def _emit_template_signal(self, current, _prev):
        if not current:
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if data:
            self.template_selected.emit(data)
