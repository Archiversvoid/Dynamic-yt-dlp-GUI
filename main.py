"""Dynamic - entry point. Composes the window from the mixins in src/ui/mixins."""
import ctypes
import os
import sys
import theme
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow
from theme import qc as _qc, ss as _ss
from src.core.models import AppSignals, DownloadItem
from src.paths import ICON_PATH, repo_root
from src.ui.components.toast import ToastManager
from src.ui.mixins.about import AboutMixin
from src.ui.mixins.downloads import DownloadsMixin
from src.ui.mixins.home import HomeMixin
from src.ui.mixins.settings import SettingsMixin
from src.ui.mixins.updates import UpdatesMixin
from src.ui.mixins.window import WindowMixin
from src.ui.styles import (
    _crisp_font, BG_DARK, GlobalContextMenuBlocker, install_font_safety, NoFocusRectStyle,
    TEAL_ACCENT)


try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('mycompany.myapp.1.0')
except Exception:
    pass


class DynamicPC(WindowMixin, HomeMixin, DownloadsMixin, SettingsMixin, UpdatesMixin, AboutMixin, QMainWindow):
    """The application window. Behaviour lives in the mixins (src/ui/mixins);
    this class only wires them together. Mixins come BEFORE QMainWindow so their
    event overrides (showEvent, closeEvent, ...) win."""
    DownloadItem = DownloadItem

    def __init__(self):
        super().__init__()
        self.settings = self._load_settings()
        theme.set_mode(theme.resolve(self.settings.get("theme", "Default")))
        self._apply_palette()
        self._updating = set()
        self.setWindowTitle("Dynamic")
        self.resize(1100, 720)
        self.setWindowIcon(QIcon(ICON_PATH))
        self.setMinimumSize(1020, 640)
        _ss(self, f"QMainWindow {{ background-color: {BG_DARK}; }}")
        self.toast_mgr = ToastManager(self)
        self.signals = AppSignals()
        self.signals.update_progress.connect(self._update_card_progress)
        self.signals.refresh_card.connect(self._refresh_single_card)
        self.signals.home_result.connect(self._on_home_result)
        self.signals.home_error.connect(self._on_home_error)
        self.signals.home_phase.connect(self._on_home_phase)
        self.signals.binary_version.connect(self._on_binary_version)
        self.signals.update_done.connect(self._on_update_done)
        font_path = str(repo_root / "assets" / "Roboto-Regular.ttf")
        if os.path.exists(font_path): QFontDatabase.addApplicationFont(font_path)
        app_font = _crisp_font("Roboto", 10)
        app_font.setStyleHint(QFont.StyleHint.SansSerif)
        QApplication.setFont(app_font)
        self._dl_items, self._dl_cards, self._dl_tab_filter, self._last_url = [], {}, "All", ""
        self._dl_list_dirty, self._dl_first_build_done = True, False
        # settings are loaded at the top of __init__ (theme must be known before any widget is built)
        self._load_icons()
        self._setup_tray_icon()
        self._load_downloads()
        self._setup_ui()
        self._show_tab(0)


def configure_app(app):
    """App-wide Qt configuration. Split out of the __main__ block so
    launcher.py (the light startup stub that shows a splash screen first)
    can apply exactly the same setup to the QApplication it already
    created, instead of duplicating it."""
    app.setWindowIcon(QIcon(str(repo_root / "icons" / "icon.ico")))
    install_font_safety()    # before any widget asks for a font

    app.setStyle(NoFocusRectStyle(app.style()))

    ctx_menu_blocker = GlobalContextMenuBlocker(app)
    app.installEventFilter(ctx_menu_blocker)
    app._ctx_menu_blocker = ctx_menu_blocker  # keep a Python ref alive

    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Highlight, _qc(TEAL_ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, _qc("#000000"))
    app.setPalette(palette)


def main():
    app = QApplication(sys.argv)
    configure_app(app)
    window = DynamicPC()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
