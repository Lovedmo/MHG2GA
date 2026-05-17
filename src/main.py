"""MHG2GA 程序入口。"""

import signal
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys.executable).resolve().parent))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from src.core.logger import setup_logging
from src.gui.main_window import MainWindow


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    setup_logging(level="DEBUG")

    app = QApplication(sys.argv)
    app.setApplicationName("MHG2GA")
    app.setApplicationVersion("0.1.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
