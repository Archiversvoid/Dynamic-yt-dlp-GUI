"""Run the TrimLoad tab by itself:  python -m src.ui.trim"""
import sys
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from theme import qc as _qc
from src.ui.styles import (
    GlobalContextMenuBlocker, install_font_safety, NoFocusRectStyle, TEAL_ACCENT)
from src.ui.trim.tab import TrimLoadTab


def main():
    app = QApplication(sys.argv)

    install_font_safety()
    app.setStyle(NoFocusRectStyle(app.style()))

    ctx_menu_blocker = GlobalContextMenuBlocker(app)
    app.installEventFilter(ctx_menu_blocker)

    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Highlight, _qc(TEAL_ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, _qc("#000000"))
    app.setPalette(palette)

    window = TrimLoadTab()
    window.resize(900, 600)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
