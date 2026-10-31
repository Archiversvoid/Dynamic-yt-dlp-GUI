"""Skeleton / shimmer loading placeholders."""
from PySide6.QtCore import QEasingCurve, QElapsedTimer, QPropertyAnimation, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QSizePolicy
from theme import qc as _qc, ss as _ss
from src.ui.styles import _white_sheen, CARD_INNER_BG


class SkeletonBox(QFrame):
    def __init__(self, width=None, height=12, radius=6, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        if width is not None:
            self.setFixedWidth(width)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        _ss(self, f"background-color: {CARD_INNER_BG}; border-radius: {radius}px; border: none;")
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(950)
        anim.setStartValue(0.35)
        anim.setKeyValueAt(0.5, 0.9)
        anim.setEndValue(0.35)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.setLoopCount(-1)
        anim.start()
        self._anim = anim


class ShimmerBox(QFrame):
    """A skeleton placeholder with a soft light band continuously sweeping
    across it - the "flowing" shimmer look, rather than SkeletonBox's flat
    pulse. Every instance shares one QTimer/clock (like the processing
    overlay's racing line), so a whole card full of these costs one timer,
    not one per block - and since they all read the same shared clock and
    map it through their own width, the bands all sweep past together as
    if gliding across one continuous surface."""
    _instances = []
    _timer = None
    _clock = None

    def __init__(self, width=None, height=12, radius=6, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        if width is not None:
            self.setFixedWidth(width)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._radius = radius
        _ss(self, "background: transparent; border: none;")
        ShimmerBox._instances.append(self)
        if ShimmerBox._clock is None:
            ShimmerBox._clock = QElapsedTimer()
            ShimmerBox._clock.start()
        if ShimmerBox._timer is None:
            ShimmerBox._timer = QTimer()
            ShimmerBox._timer.setInterval(33)
            ShimmerBox._timer.timeout.connect(ShimmerBox._tick)
        if not ShimmerBox._timer.isActive():
            ShimmerBox._timer.start()

    @classmethod
    def _tick(cls):
        # Belt-and-suspenders pruning for anything that got destroyed
        # without going through unregister() - normal cleanup is
        # deterministic (see unregister/_clear_home_slot), this is just
        # a safety net so a missed case can't silently accumulate.
        alive = []
        for w in cls._instances:
            try:
                win = w.window()
                if w.isVisible() and not (win is not None and win.isMinimized()):
                    w.update()
                alive.append(w)
            except RuntimeError:
                pass
        cls._instances = alive
        if not cls._instances and cls._timer is not None:
            cls._timer.stop()

    @classmethod
    def unregister(cls, box):
        """Explicit, immediate removal - called the moment a skeleton card
        is discarded, rather than waiting on Qt's deferred deleteLater()
        (which only runs once the event loop is idle) or on isVisible()
        happening to already read False by then. Without this, a
        ShimmerBox whose parent widget was queued for deletion but hadn't
        actually been destroyed yet stayed in _instances - still visible,
        still getting update()+repainted every tick - and every fresh
        link pasted in the same session added more of these on top,
        so the paint cost (and CPU/power draw) only ever grew across a
        session instead of being released when a card was replaced."""
        if box in cls._instances:
            cls._instances.remove(box)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self._radius, self._radius)
        p.setClipPath(path)
        p.fillRect(self.rect(), _qc(CARD_INNER_BG))
        now = ShimmerBox._clock.elapsed()
        period = 1400.0
        t = (now % period) / period
        w = float(self.width())
        band_w = max(60.0, w * 0.5)
        x = -band_w + (w + band_w) * t
        g = QLinearGradient(x, 0, x + band_w, 0)
        c0 = QColor(255, 255, 255, 0)
        c1 = _white_sheen(26, 150)
        g.setColorAt(0.0, c0); g.setColorAt(0.5, c1); g.setColorAt(1.0, c0)
        p.fillRect(self.rect(), QBrush(g))
        p.end()
