from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication

from src.core.path_helper import get_resource_path
_ICON_PATH = get_resource_path("src", "gui", "resources", "icon.png")


class SystemTray:
    """系统托盘管理，支持最小化到托盘和快捷菜单。"""

    def __init__(self, main_window, parent=None):
        self._main_window = main_window
        self._tray = QSystemTrayIcon(parent)
        if _ICON_PATH.exists():
            self._tray.setIcon(QIcon(str(_ICON_PATH)))
        self._tray.setToolTip("MHG2GA - Make Houkai Gakuen 2 Great Again")
        self._setup_menu()
        self._tray.activated.connect(self._on_activated)

    def _setup_menu(self) -> None:
        menu = QMenu()

        show_action = QAction("显示主窗口", menu)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        menu.addSeparator()

        self._start_action = QAction("全部启动", menu)
        menu.addAction(self._start_action)

        self._stop_action = QAction("全部停止", menu)
        menu.addAction(self._stop_action)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def show_message(self, title: str, message: str) -> None:
        self._tray.showMessage(
            title, message,
            QSystemTrayIcon.MessageIcon.Information, 3000,
        )

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self) -> None:
        self._main_window.showNormal()
        self._main_window.activateWindow()

    def _quit_app(self) -> None:
        self._tray.hide()
        QApplication.quit()
