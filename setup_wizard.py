"""First-run setup, shown once after installing: welcome -> terms -> yt-dlp and ffmpeg.

Lives next to main.py (so  python setup_wizard.py  previews it). The installer starts  Dynamic.exe --setup  when you press Finish. launcher.py calls run_setup_wizard() before the main
window is built: True = carry on and open the app, False = the window was closed, quit. It is shown once (setup_done is
kept in settings.json); start the app with --setup-force to see it again.

Everything visual comes from the app itself: theme.py (dark/light, following Windows or the saved choice), the style
colours, the pill-shaped scroll area, and the same downloads Settings > Update uses.
"""
import json
import os
import threading

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QCursor, QIcon, QPainter, QPainterPath, QPen, QTextOption
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLayout, QProgressBar, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from theme import qc as _qc, ss as _ss
from src.core.app_info import APP_VERSION
from src.core.binaries import get_binary_path, ytdlp_installed
from src.core.updater import _update_ffmpeg, _update_ytdlp
from src.paths import ICON_PATH, repo_root, settings_file
from src.ui.components.controls import ModernScrollArea
from src.ui.styles import BG_DARK, CARD_BG, CARD_INNER_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED

FEATURES = (
    ("Format and quality control", "Pick the resolution, audio bitrate and container you want - nothing extra."),
    ("Precision clip trimming", "Cut exact segments from online videos without downloading hours of footage."),
    ("Open source and free", "Dynamic is a free open source software licensed under GPL-3.0."),
)
TOOLS = (("yt-dlp", "Finds and downloads the videos"), ("ffmpeg", "Merges, trims and converts them"))
FALLBACK_TERMS = ("**Terms of Use**\n\nDynamic is provided as is, without warranty. You are responsible for following the terms "
                  "of service of every site you download from, and for the copyright of what you download.")


# ---------------------------------------------------------------- settings.json (shared with the app)
def _load_settings():
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_settings(**values):
    data = _load_settings()
    data.update(values)
    try:
        tmp = str(settings_file) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, settings_file)
    except OSError:
        pass


def _terms_text():
    for name in ("TERMS.txt", "TERMS.md", "terms.txt", "terms.md"):         # the same files Settings > About shows
        p = repo_root / name
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    return FALLBACK_TERMS


def _installed(name):
    return get_binary_path("ffmpeg") is not None if name == "ffmpeg" else ytdlp_installed()


# ---------------------------------------------------------------- small widgets
class TickBox(QCheckBox):
    """A check box that always draws a box with a tick (the native look), in the app's colours, light or dark.
    (Styling QCheckBox::indicator in a stylesheet is what turned it into a flat coloured square.)"""
    SIZE = 20

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(30)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(self.SIZE + 12 + self.fontMetrics().horizontalAdvance(self.text()) + 6)
        hint.setHeight(max(hint.height(), 30))
        return hint

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.SIZE
        box = QRectF(1.0, (self.height() - s) / 2 + 0.5, s - 1, s - 1)
        lit = self.isChecked() or self.underMouse()
        p.setPen(QPen(_qc(TEAL_ACCENT) if lit else _qc(TEXT_MUTED, "text"), 1.5))
        p.setBrush(_qc(CARD_BG, "bg"))
        p.drawRoundedRect(box, 4, 4)
        if self.isChecked():
            pen = QPen(_qc(TEXT_MAIN, "text"), 2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            tick = QPainterPath()
            tick.moveTo(box.left() + 4.5, box.top() + 10.2)
            tick.lineTo(box.left() + 8.2, box.top() + 13.8)
            tick.lineTo(box.left() + 14.8, box.top() + 6.2)
            p.drawPath(tick)
        p.setPen(_qc(TEXT_MAIN, "text"))
        p.drawText(QRectF(s + 12, 0, self.width() - s - 12, self.height()), self.text(),
                   QTextOption(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft))


def _pill(text, primary=False):
    b = QPushButton(text)
    b.setFixedHeight(40)
    b.setMinimumWidth(104)
    b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    if primary:
        _ss(b, f"QPushButton {{ background-color: {TEAL_ACCENT}; color: #0B0B0B; border: none; border-radius: 20px; padding: 0 22px; font-size: 14px; font-weight: bold; }} "
               f"QPushButton:hover {{ background-color: #1ED6B8; }} QPushButton:disabled {{ background-color: #2E4F4A; color: #7FA9A2; }}")
    else:
        _ss(b, f"QPushButton {{ background: transparent; color: {TEXT_MUTED}; border: 1.2px solid #3A3A3A; border-radius: 20px; padding: 0 22px; font-size: 14px; }} "
               f"QPushButton:hover {{ color: {TEXT_MAIN}; border-color: #5A5A5A; }} QPushButton:disabled {{ color: #555555; border-color: #2A2A2A; }}")
    return b


def _text(text, size=14, bold=False, muted=False):
    lbl = QLabel(text)                  # NOT word-wrapped on purpose: a wrapped label reports a very tall minimum height
    _ss(lbl, f"color: {TEXT_MUTED if muted else TEXT_MAIN}; font-size: {size}px; {'font-weight: bold; ' if bold else ''}background: transparent;")
    return lbl


def _card():
    card = QFrame()
    card.setObjectName("wizCard")
    _ss(card, f"QFrame#wizCard {{ background-color: {CARD_BG}; border: 1px solid #2A2A2A; border-radius: 14px; }}")
    return card


class _Signals(QObject):
    row = Signal(str, str)              # tool, "busy" | "done" | "failed"
    finished = Signal(bool)


# ---------------------------------------------------------------- the wizard
class SetupWizard(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dynamic Setup")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.setFixedSize(720, 600)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        _ss(self, f"QDialog {{ background-color: {BG_DARK}; }}")
        self._sig = _Signals()
        self._sig.row.connect(self._on_row)
        self._sig.finished.connect(self._on_install_finished)
        self._failed, self._done, self._total = set(), 0, 0
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 28)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)      # the layout never imposes a minimum size on the window
        self.pages = QStackedWidget()
        root.addWidget(self.pages)
        for build in (self._welcome_page, self._terms_page, self._install_page):
            self.pages.addWidget(build())

    def _page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        return page, lay

    @staticmethod
    def _buttons(*buttons):
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addStretch(1)
        for b in buttons:
            row.addWidget(b)
        return row

    def _welcome_page(self):
        page, lay = self._page()
        logo = QLabel()
        logo.setPixmap(QIcon(ICON_PATH).pixmap(64, 64))
        logo.setStyleSheet("background: transparent;")
        lay.addWidget(logo)
        lay.addWidget(_text("Welcome to Dynamic", 30, bold=True))
        lay.addWidget(_text("A simple, cutting-edge yt-dlp GUI - version %s." % APP_VERSION, 14, muted=True))
        lay.addSpacing(6)
        for title, body in FEATURES:
            card = _card()
            inner = QVBoxLayout(card)
            inner.setContentsMargins(18, 12, 18, 12)
            inner.setSpacing(2)
            inner.addWidget(_text(title, 15, bold=True))
            inner.addWidget(_text(body, 13, muted=True))
            lay.addWidget(card)
        lay.addStretch(1)
        start = _pill("Get Started", True)
        start.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        lay.addLayout(self._buttons(start))
        return page

    def _terms_page(self):
        page, lay = self._page()
        lay.addWidget(_text("Terms of Service", 28, bold=True))
        lay.addWidget(_text("Please read and accept them to continue.", 14, muted=True))
        card = _card()
        inner = QVBoxLayout(card)
        inner.setContentsMargins(14, 14, 6, 14)
        scroll = ModernScrollArea()
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)      # the app hides it; here the pill bar is visible and moves
        body = QLabel()
        body.setTextFormat(Qt.TextFormat.MarkdownText)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.setText(_terms_text())
        _ss(body, f"color: {TEXT_MAIN}; font-size: 13px; background: transparent; padding-right: 12px;")
        scroll.setWidget(body)
        inner.addWidget(scroll)
        lay.addWidget(card, 1)
        self.agree = TickBox("I have read and agree to the Terms of Service")
        lay.addWidget(self.agree)
        back = _pill("Back")
        back.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.cont = _pill("Continue", True)
        self.cont.setEnabled(False)
        self.agree.toggled.connect(self.cont.setEnabled)
        self.cont.clicked.connect(self._accept_terms)
        lay.addLayout(self._buttons(back, self.cont))
        return page

    def _install_page(self):
        page, lay = self._page()
        lay.addWidget(_text("One last thing", 28, bold=True))
        lay.addWidget(_text("Dynamic uses two small programs to download and convert videos.", 14, muted=True))
        lay.addWidget(_text("Download them now, or skip and add them later from the Home page.", 14, muted=True))
        lay.addSpacing(6)
        self.status = {}
        for name, purpose in TOOLS:
            card = _card()
            row = QHBoxLayout(card)
            row.setContentsMargins(18, 14, 18, 14)
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_text(name, 15, bold=True))
            col.addWidget(_text(purpose, 13, muted=True))
            row.addLayout(col, 1)
            self.status[name] = QLabel("")
            row.addWidget(self.status[name])
            lay.addWidget(card)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        _ss(self.bar, f"QProgressBar {{ background-color: {CARD_INNER_BG}; border: none; border-radius: 4px; }} "
                      f"QProgressBar::chunk {{ background-color: {TEAL_ACCENT}; border-radius: 4px; }}")
        lay.addWidget(self.bar)
        lay.addStretch(1)
        self.back2 = _pill("Back")
        self.back2.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.skip = _pill("Skip")
        self.skip.clicked.connect(self._finish)
        self.primary = _pill("Download", True)
        self.primary.clicked.connect(self._on_primary)
        lay.addLayout(self._buttons(self.back2, self.skip, self.primary))
        return page

    # ---- flow
    def _accept_terms(self):
        _save_settings(terms_accepted=True)
        self._refresh_install_page()
        self.pages.setCurrentIndex(2)

    def _missing(self):
        return [name for name, _ in TOOLS if not _installed(name)]

    def _set_status(self, name, text, color):
        _ss(self.status[name], f"color: {color}; font-size: 13px; font-weight: bold; background: transparent;")
        self.status[name].setText(text)

    def _refresh_install_page(self):
        missing = self._missing()
        for name, _ in TOOLS:
            if name in self._failed and name in missing:
                self._set_status(name, "Couldn't download", "#E5534B")
            elif name in missing:
                self._set_status(name, "Not installed", TEXT_MUTED)
            else:
                self._set_status(name, "Installed", TEAL_ACCENT)
        self.bar.setValue(int((len(TOOLS) - len(missing)) * 100 / len(TOOLS)))      # how many of the two are installed
        self.primary.setText("Launch" if not missing else ("Retry" if self._failed else "Download"))

    def _set_busy(self, busy):
        for b in (self.back2, self.skip, self.primary):
            b.setEnabled(not busy)

    def _on_primary(self):
        todo = self._missing()
        if not todo:
            self._finish()
            return
        self._failed.clear()
        self._done, self._total = 0, len(todo)
        self.bar.setValue(0)
        self._set_busy(True)

        def work():
            ok = True
            for name in todo:
                self._sig.row.emit(name, "busy")
                try:
                    (_update_ytdlp if name == "yt-dlp" else _update_ffmpeg)()      # the same downloads Settings > Update uses
                    self._sig.row.emit(name, "done")
                except Exception:
                    ok = False
                    self._sig.row.emit(name, "failed")
            self._sig.finished.emit(ok)
        threading.Thread(target=work, daemon=True).start()

    def _on_row(self, name, state):
        if state == "busy":
            self._set_status(name, "Downloading...", TEXT_MUTED)
        elif state == "done":
            self._done += 1
            self._set_status(name, "Installed", TEAL_ACCENT)
            self.bar.setValue(int(self._done * 100 / max(1, self._total)))
        else:
            self._failed.add(name)
            self._set_status(name, "Couldn't download", "#E5534B")

    def _on_install_finished(self, _ok):
        self._set_busy(False)
        self._refresh_install_page()                       # Launch if everything is there, otherwise Retry

    def _finish(self):
        _save_settings(setup_done=True)
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        try:                                                # the same always-white title bar the app has
            import ctypes
            hwnd = int(self.winId())
            for attr in (20, 19):
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ctypes.c_int(0)), 4) == 0:
                    break
        except Exception:
            pass


def run_setup_wizard(app=None, force=False):
    """True: carry on and open the app. False: the window was closed without finishing - quit."""
    if not force and _load_settings().get("setup_done"):
        return True
    return bool(SetupWizard().exec())


if __name__ == "__main__":              # python setup_wizard.py  ->  preview the wizard (always shown, nothing is saved as "done")
    import sys
    try:
        import launcher                 # the same dark/light choice the app makes at start
        launcher._init_theme()
    except Exception:
        pass
    from PySide6.QtWidgets import QApplication
    _app = QApplication(sys.argv)
    print("Launch / Skip pressed - the app would open now" if run_setup_wizard(_app, force=True) else "Closed without finishing")
