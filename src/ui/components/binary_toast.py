"""Sticky 'X is not installed' notifications (Home and TrimLoad), with Download / From disk... buttons."""
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from theme import ss as _ss
from src.ui.styles import CARD_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED

TOAST_W, TOAST_H, MARGIN, GAP = 300, 88, 20, 8


def stack_positions(win_w, win_h, count, margin=MARGIN, gap=GAP, w=TOAST_W, h=TOAST_H):
    """Top-left corners for `count` toasts stacked upward from the bottom-right corner (index 0 = topmost)."""
    x = max(0, win_w - w - margin)
    return [(x, max(0, win_h - margin - h - (count - 1 - i) * (h + gap))) for i in range(count)]


class BinaryToast(QFrame):
    """Compact: the message and a close button on top, the two buttons underneath, all inside the rounded frame."""
    download_clicked = Signal()
    disk_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, text, warning_pixmap, parent=None, primary="Download", secondary="From disk..."):
        super().__init__(parent)
        self._primary_text = primary
        self.setObjectName("binToast")
        self.setFixedSize(TOAST_W, TOAST_H)
        _ss(self, f"QFrame#binToast {{ background-color: {CARD_BG}; border: 1px solid #2A2A2A; border-radius: 14px; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 10, 12)
        root.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        icon = QLabel()
        icon.setFixedSize(22, 22)
        _ss(icon, "background: transparent; border: none;")
        if warning_pixmap is not None and not warning_pixmap.isNull():
            icon.setPixmap(warning_pixmap.scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            icon.setText("!")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel(text)
        _ss(self.label, f"color: {TEXT_MAIN}; font-size: 14px; background: transparent; border: none;")
        close = QPushButton("✕")
        close.setFixedSize(22, 22)
        close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(close, f"QPushButton {{ background: transparent; border: none; color: {TEXT_MUTED}; font-size: 14px; }} QPushButton:hover {{ color: {TEXT_MAIN}; }}")
        top.addWidget(icon)
        top.addWidget(self.label, 1)
        top.addWidget(close)
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.download_btn = self._pill(primary, True)
        self.disk_btn = self._pill(secondary, False)
        bottom.addWidget(self.download_btn, 1)
        bottom.addWidget(self.disk_btn, 1)
        root.addLayout(top)
        root.addLayout(bottom)
        self.download_btn.clicked.connect(self.download_clicked.emit)
        self.disk_btn.clicked.connect(self.disk_clicked.emit)
        close.clicked.connect(self.close_clicked.emit)

    def _pill(self, text, primary):
        b = QPushButton(text)
        b.setFixedHeight(28)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if primary:
            _ss(b, f"QPushButton {{ background-color: {TEAL_ACCENT}; color: #0B0B0B; border: none; border-radius: 14px; padding: 0 10px; font-size: 13px; }} QPushButton:hover {{ background-color: #1ED6B8; }} QPushButton:disabled {{ background-color: #2E4F4A; color: #7FA9A2; }}")
        else:
            _ss(b, f"QPushButton {{ background: transparent; color: {TEXT_MAIN}; border: 1.2px solid {TEXT_MAIN}; border-radius: 14px; padding: 0 10px; font-size: 13px; }} QPushButton:hover {{ border-color: {TEAL_ACCENT}; color: {TEAL_ACCENT}; }} QPushButton:disabled {{ color: #666666; border-color: #444444; }}")
        return b

    def set_busy(self, busy, text=None):
        self.download_btn.setEnabled(not busy)
        self.disk_btn.setEnabled(not busy)
        self.download_btn.setText(text if (busy and text) else self._primary_text)

    def set_content(self, text, primary, secondary):
        self.label.setText(text)
        self._primary_text = primary
        self.download_btn.setText(primary)
        self.disk_btn.setText(secondary)


class BinaryToastManager(QObject):
    """Owns the sticky toasts: 'not installed' (Home and TrimLoad only, until installed; the X hides one for this session)
    and 'update available' (every page). For the update toast the two buttons are Update/Restart and Remind me later/Later."""
    download_requested = Signal(str)      # the primary button, with the toast's name
    disk_requested = Signal(str)          # the secondary button (for the update toast also its X)
    ORDER = ("update", "ffmpeg", "yt-dlp")
    BINARY = ("ffmpeg", "yt-dlp")
    ALWAYS = ("update",)
    TEXT = {"ffmpeg": "ffmpeg not installed", "yt-dlp": "yt-dlp not installed"}

    def __init__(self, window, warning_pixmap, info_pixmap=None):
        super().__init__(window)
        self._win = window
        self._pix = warning_pixmap
        self._info_pix = info_pixmap if info_pixmap is not None else warning_pixmap
        self._toasts = {}
        self._dismissed = set()
        self._on_home = True

    def _eligible(self, name):
        return self._on_home or name in self.ALWAYS

    def set_missing(self, names):
        wanted = [n for n in self.BINARY if n in names and n not in self._dismissed]
        for n in list(self._toasts):
            if n in self.BINARY and n not in wanted:
                t = self._toasts.pop(n)
                t.hide()
                t.deleteLater()
        for n in wanted:
            if n not in self._toasts:
                t = BinaryToast(self.TEXT[n], self._pix, self._win)
                t.download_clicked.connect(lambda n=n: self.download_requested.emit(n))
                t.disk_clicked.connect(lambda n=n: self.disk_requested.emit(n))
                t.close_clicked.connect(lambda n=n: self._dismiss(n))
                t.setVisible(self._eligible(n))
                self._toasts[n] = t
        self.relayout()

    def set_update(self, text, primary="Update", secondary="Remind me later"):
        """Show (or change) the update toast; text=None removes it."""
        if text is None:
            t = self._toasts.pop("update", None)
            if t is not None:
                t.hide()
                t.deleteLater()
        else:
            t = self._toasts.get("update")
            if t is None:
                t = BinaryToast(text, self._info_pix, self._win, primary, secondary)
                t.download_clicked.connect(lambda: self.download_requested.emit("update"))
                t.disk_clicked.connect(lambda: self.disk_requested.emit("update"))
                t.close_clicked.connect(lambda: self.disk_requested.emit("update"))
                self._toasts["update"] = t
            else:
                t.set_content(text, primary, secondary)
            t.setVisible(True)
        self.relayout()

    def _dismiss(self, name):
        self._dismissed.add(name)
        t = self._toasts.pop(name, None)
        if t is not None:
            t.hide()
            t.deleteLater()
        self.relayout()

    def set_busy(self, name, busy, text=None):
        t = self._toasts.get(name)
        if t is not None:
            t.set_busy(busy, text)

    def set_page_visible(self, on_home):
        self._on_home = on_home
        for n, t in self._toasts.items():
            t.setVisible(self._eligible(n))
        self.relayout()

    def relayout(self):
        shown = [self._toasts[n] for n in self.ORDER if n in self._toasts and self._eligible(n)]
        for t, (x, y) in zip(shown, stack_positions(self._win.width(), self._win.height(), len(shown))):
            t.move(x, y)
            t.raise_()
