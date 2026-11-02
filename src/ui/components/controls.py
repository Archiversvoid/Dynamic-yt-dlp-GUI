"""Reusable settings widgets: SettingsRow and the scroll area."""
from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout
from theme import ss as _ss
from src.ui.styles import TEXT_MAIN, TEXT_MUTED


class SettingsRow(QFrame):
    """One row of a settings card: title + optional subtitle on the left, and
    on the right either a custom control (combo box, value label) or a
    navigation arrow. Rows with an arrow are clickable."""
    clicked = Signal()

    def __init__(self, title, subtitle="", position="middle", arrow_pixmap=None, control=None, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsRow")
        self._clickable = control is None and arrow_pixmap is not None
        self.subtitle_lbl = None
        self.setMinimumHeight(78 if subtitle else 68)
        radius = {"top": "border-top-left-radius: 13px; border-top-right-radius: 13px;",
                  "bottom": "border-bottom-left-radius: 13px; border-bottom-right-radius: 13px;",
                  "single": "border-radius: 13px;"}.get(position, "")
        hover = "QFrame#settingsRow:hover { background-color: #242424; }" if self._clickable else ""
        _ss(self, f"QFrame#settingsRow {{ background: transparent; border: none; {radius} }} {hover}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(26, 12, 22, 12)
        lay.setSpacing(16)
        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(4)
        t = QLabel(title)
        _ss(t, f"color: {TEXT_MAIN}; font-size: 19px; background: transparent; border: none;")
        col.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            self.subtitle_lbl = s
            _ss(s, f"color: {TEXT_MUTED}; font-size: 14px; background: transparent; border: none;")
            col.addWidget(s)
        lay.addLayout(col, 1)
        if control is not None:
            lay.addWidget(control)
        elif arrow_pixmap is not None:
            a = QLabel(); a.setFixedSize(22, 22)
            _ss(a, f"color: {TEXT_MUTED}; font-size: 20px; background: transparent; border: none;")
            if not arrow_pixmap.isNull(): a.setPixmap(arrow_pixmap); a.setProperty("_arrow", True)
            else: a.setText("→")
            lay.addWidget(a)
        if self._clickable:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, e):
        if self._clickable and e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class ModernScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _ss(self, """
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical { width: 8px; background: transparent; margin: 0px; }
            QScrollBar::handle:vertical { background-color: #444444; border-radius: 4px; min-height: 40px; }
            QScrollBar::handle:vertical:hover { background-color: #666666; }
            QScrollBar::handle:vertical:pressed { background-color: #00BFA5; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; border: none; background: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        self._scroll_anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim.setDuration(180)
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0:
            vbar = self.verticalScrollBar()
            current = self._scroll_anim.endValue() if self._scroll_anim.state() == QPropertyAnimation.State.Running else vbar.value()
            step = -int(delta * 1.2)
            target = max(vbar.minimum(), min(vbar.maximum(), current + step))
            self._scroll_anim.stop()
            self._scroll_anim.setStartValue(vbar.value())
            self._scroll_anim.setEndValue(target)
            self._scroll_anim.start()
            event.accept()
        else:
            super().wheelEvent(event)


class ElidedLabel(QLabel):
    """A one-line label that shows 'A very long title...' instead of growing.

    A normal QLabel's minimum width is its full text width, so a long title (or one
    long unbroken word) used to stretch the whole download card - and the scroll
    area - past the right edge of the window. This label elides to whatever width
    its layout gives it.

    fit_text=False (default): ignores its text width entirely and takes the space
    the layout offers (use for a title that should fill its row).
    fit_text=True: sizes to its text like a normal label, but pair it with
    setMaximumWidth() so it stops growing and elides instead (use inside a row of
    short items, such as a channel name)."""

    def __init__(self, text="", fit_text=False, parent=None):
        super().__init__(parent)
        self._full = ""
        if fit_text:
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.setMinimumWidth(0)
        self.setFullText(text)

    def setFullText(self, text):
        self._full = str(text or "")
        self._elide()

    def fullText(self):
        return self._full

    def _elide(self):
        w = self.width()
        if w <= 1:
            shown = self._full          # not laid out yet - the first resize elides it
        else:
            shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, w)
        if shown != self.text():
            super().setText(shown)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._elide()
