"""The processing screen and its animations."""
import math
from PySide6.QtCore import (
    QEasingCurve, QElapsedTimer, QEvent, QPointF, QPropertyAnimation, QRect, QRectF, Qt,
    QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QRadialGradient)
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget)
from theme import qc as _qc, ss as _ss
from src.ui.styles import (
    _mono_family, _tint_overlay, BG_DARK, ERROR_RED, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED)


class ProcessingOverlay(QWidget):
    """The "processing" screen shown while a pasted link is being parsed.

    Everything (background, headline, step tracker, racing line, cancel
    button) is painted by this one widget instead of being built from a
    pile of child widgets + QGraphicsEffects. That keeps it cheap (no
    offscreen buffers, no per-widget effect compositing) and lets the
    whole thing fade/slide as a single unit.

    The screen mirrors what the worker thread is *actually* doing: the
    app calls set_phase() as each real stage begins. Each stage is held
    on screen for at least MIN_DWELL_MS so quick stages stay readable,
    and the queued stages are shown in order."""

    # key, headline, tracker label, detail line
    STEPS = [
        ("start",   "Starting",             "Start",   "Getting things ready"),
        ("fetch",   "Fetching URL streams", "Streams", "Contacting {host} and reading the available streams"),
        ("process", "Processing",           "Process", "Reading the title, duration and available qualities"),
        ("preview", "Loading preview",      "Preview", "Grabbing the thumbnail and site info"),
        ("done",    "Done",                 "Done",    "All set"),
    ]
    MIN_DWELL_MS = 260      # shortest time a stage stays on screen
    DONE_DWELL_MS = 550     # how long "Done" is shown before the card appears
    FAIL_COLOR_MS = 480     # how long the ambient glow/accent takes to turn red
    LINE_PERIOD_MS = 1500   # one lap of the racing line
    FADE_IN_MS = 240
    FADE_OUT_MS = 280
    LOG_PANEL_H = 134

    cancel_requested = Signal()
    retry_requested = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self._keys = [s[0] for s in self.STEPS]
        self._host = ""
        self._active, self._prev = 0, 0
        self._queue = []
        self._done_at = [None] * len(self.STEPS)
        self._change_at, self._active_since = -10000, 0
        self._failed, self._fail_at = False, 0
        self._error_text = ""
        self._log_open = False
        self._finish_cb, self._finish_armed = None, False
        self._alpha, self._opaque = 0.0, False
        self._ease = QEasingCurve(QEasingCurve.Type.OutCubic)
        self._line_ease = QEasingCurve(QEasingCurve.Type.InOutCubic)

        self._clock = QElapsedTimer(); self._clock.start()
        # 30fps rather than 60fps - this is slow ambient motion (gradient
        # sweeps, a pulsing dot), not fast action; halving the repaint
        # rate is not visually distinguishable here but meaningfully cuts
        # sustained CPU/power draw for however long a fetch takes.
        self._tick = QTimer(self); self._tick.setInterval(33)
        self._tick.timeout.connect(self._on_tick)
        self._fade = QVariantAnimation(self)
        self._fade.valueChanged.connect(self._on_fade_step)
        self._fade.finished.connect(self._on_fade_finished)

        # Smoothly carries the ambient glow/accent color from teal to red
        # on failure, instead of snapping instantly.
        self._fail_color_t = 0.0
        self._fail_color_anim = QVariantAnimation(self)
        self._fail_color_anim.valueChanged.connect(self._on_fail_color_step)

        self._build_buttons()
        self._build_log_panel()

        parent.installEventFilter(self)
        self.hide()

    # ---------- buttons / log panel (real child widgets, not painted) ----------
    def _pill_style(self, filled=False):
        if filled:
            return (f"QPushButton {{ background-color: {TEAL_ACCENT}; border: none; border-radius: 17px; "
                     f"color: #0B0B0B; font-size: 13px; font-weight: bold; }} "
                     f"QPushButton:hover {{ background-color: #1ED6B8; }}")
        return (f"QPushButton {{ background: transparent; border: 1.2px solid #3A3A3A; border-radius: 17px; "
                 f"color: {TEXT_MUTED}; font-size: 13px; }} "
                 f"QPushButton:hover {{ border-color: {TEAL_ACCENT}; color: {TEXT_MAIN}; background-color: rgba(0, 191, 165, 22); }}")

    def _fade_with_overlay(self, widget):
        """Gives a child widget its own opacity effect so it fades in/out
        together with the hand-painted content instead of popping in/out
        at full opacity (child widgets aren't touched by this widget's own
        paintEvent-level p.setOpacity() calls)."""
        eff = QGraphicsOpacityEffect(widget)
        eff.setOpacity(0.0)
        widget.setGraphicsEffect(eff)
        return eff

    def _build_buttons(self):
        self._btn_cancel = QPushButton("Cancel", self)
        self._btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self._btn_cancel, self._pill_style(filled=False))
        self._btn_cancel.clicked.connect(self.cancel_requested.emit)
        self._cancel_fx = self._fade_with_overlay(self._btn_cancel)

        self._btn_retry = QPushButton("Try Again", self)
        self._btn_retry.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self._btn_retry, self._pill_style(filled=True))
        self._btn_retry.clicked.connect(self.retry_requested.emit)
        self._retry_fx = self._fade_with_overlay(self._btn_retry)

        self._btn_log = QPushButton("Error Log", self)
        self._btn_log.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self._btn_log, self._pill_style(filled=False))
        self._btn_log.clicked.connect(self._toggle_log)
        self._log_btn_fx = self._fade_with_overlay(self._btn_log)

        for b in (self._btn_cancel, self._btn_retry, self._btn_log):
            b.setFixedSize(120, 34); b.hide()

    def _build_log_panel(self):
        self._log_panel = QFrame(self)
        _ss(self._log_panel, "QFrame { background-color: #161616; border: 1px solid #2E2E2E; border-radius: 10px; }")
        lay = QVBoxLayout(self._log_panel)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel("Error details")
        _ss(title, f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        header.addWidget(title)
        header.addStretch()
        self._btn_copy = QPushButton("Copy")
        self._btn_copy.setFixedSize(64, 24)
        self._btn_copy.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._copy_style_normal = (f"QPushButton {{ background: transparent; border: 1px solid #3A3A3A; border-radius: 12px; "
                                    f"color: {TEXT_MUTED}; font-size: 11px; }} "
                                    f"QPushButton:hover {{ border-color: {TEAL_ACCENT}; color: {TEXT_MAIN}; }}")
        self._copy_style_done = (f"QPushButton {{ background: transparent; border: 1px solid {TEAL_ACCENT}; border-radius: 12px; "
                                  f"color: {TEAL_ACCENT}; font-size: 11px; font-weight: bold; }}")
        _ss(self._btn_copy, self._copy_style_normal)
        self._btn_copy.clicked.connect(self._copy_error_text)
        header.addWidget(self._btn_copy)
        lay.addLayout(header)
        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        _ss(self._log_text, f"QPlainTextEdit {{ background: transparent; border: none; color: {ERROR_RED}; "
                                       f"font-family: '{_mono_family()}'; font-size: 11px; }}")
        lay.addWidget(self._log_text, 1)
        self._log_panel.hide()
        self._log_fx = self._fade_with_overlay(self._log_panel)
        self._log_anim = QPropertyAnimation(self._log_panel, b"geometry", self)
        self._log_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._log_anim.setDuration(240)
        self._log_anim.finished.connect(self._on_log_anim_finished)

    def _copy_error_text(self):
        QApplication.clipboard().setText(self._error_text)
        self._btn_copy.setText("Copied")
        _ss(self._btn_copy, self._copy_style_done)
        QTimer.singleShot(1500, self._reset_copy_button)

    def _reset_copy_button(self):
        self._btn_copy.setText("Copy")
        _ss(self._btn_copy, self._copy_style_normal)

    def _toggle_log(self):
        self._log_open = not self._log_open
        self._btn_log.setText("Hide Log" if self._log_open else "Error Log")
        rect = self._log_panel_geometry()
        collapsed = QRect(rect.x(), rect.y(), rect.width(), 0)
        expanded = QRect(rect.x(), rect.y(), rect.width(), self.LOG_PANEL_H)
        self._log_anim.stop()
        if self._log_open:
            self._log_panel.setGeometry(collapsed)
            self._log_panel.show()
            self._log_fx.setOpacity(1.0)
            self._log_anim.setStartValue(collapsed)
            self._log_anim.setEndValue(expanded)
        else:
            self._log_anim.setStartValue(self._log_panel.geometry())
            self._log_anim.setEndValue(collapsed)
        self._log_anim.start()

    def _on_log_anim_finished(self):
        if not self._log_open:
            self._log_panel.hide()

    # ---------- public API ----------
    def begin(self, host):
        n = len(self.STEPS)
        self._host = host or "the link"
        self._active, self._prev = 0, 0
        self._queue = []
        self._done_at = [None] * n
        self._change_at, self._active_since = -10000, 0
        self._failed = False
        self._error_text = ""
        self._log_open = False
        self._log_panel.hide()
        self._btn_log.setText("Error Log")
        self._reset_copy_button()
        self._finish_cb, self._finish_armed = None, False
        self._fail_color_anim.stop(); self._fail_color_t = 0.0
        self._clock.restart()
        self.setGeometry(self.parentWidget().rect())
        self._reposition_buttons()
        self.raise_()
        self.show()
        self._fade_to(1.0, self.FADE_IN_MS)

    def set_phase(self, key):
        if self._failed or key not in self._keys: return
        idx = self._keys.index(key)
        last = self._queue[-1] if self._queue else self._active
        if idx > last: self._queue.append(idx)

    def finish(self, callback):
        """Queue up "Done"; callback fires once it has been shown."""
        last = self._queue[-1] if self._queue else self._active
        for i in range(last + 1, len(self.STEPS)): self._queue.append(i)
        self._finish_cb, self._finish_armed = callback, True
        self._reposition_buttons()

    def fail(self, message):
        now = self._clock.elapsed()
        self._failed, self._fail_at = True, now
        self._prev, self._change_at = self._active, now
        self._queue = []
        self._error_text = message or "Unknown error"
        self._log_text.setPlainText(self._error_text)
        self._log_open = False
        self._log_panel.hide()
        self._btn_log.setText("Error Log")
        self._finish_cb, self._finish_armed = None, False
        self._fail_color_anim.stop()
        self._fail_color_anim.setStartValue(self._fail_color_t)
        self._fail_color_anim.setEndValue(1.0)
        self._fail_color_anim.setDuration(self.FAIL_COLOR_MS)
        self._fail_color_anim.start()
        self._reposition_buttons()

    def dismiss(self):
        self._finish_cb, self._finish_armed = None, False
        if self._log_open:
            self._log_open = False
            self._log_anim.stop()
            self._log_panel.hide()
        self._fade_to(0.0, self.FADE_OUT_MS)

    # ---------- internals ----------
    def _fade_to(self, target, ms):
        self._fade.stop()
        self._fade.setStartValue(self._alpha)
        self._fade.setEndValue(float(target))
        self._fade.setDuration(ms)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._fade.start()

    def _on_fade_step(self, v):
        self._alpha = float(v)
        opaque = self._alpha >= 0.999
        if opaque != self._opaque:
            self._opaque = opaque
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, opaque)
        # Child widgets (real buttons/panel) don't fade on their own just
        # because the parent's paintEvent sets an opacity - drive each
        # one's own opacity effect off the same alpha so everything fades
        # together as one unit.
        self._cancel_fx.setOpacity(self._alpha if self._btn_cancel.isVisible() else 0.0)
        self._retry_fx.setOpacity(self._alpha if self._btn_retry.isVisible() else 0.0)
        self._log_btn_fx.setOpacity(self._alpha if self._btn_log.isVisible() else 0.0)
        self._log_fx.setOpacity(self._alpha if self._log_panel.isVisible() else 0.0)
        self.update()

    def _on_fade_finished(self):
        if self._alpha <= 0.001: self.hide()

    def _on_fail_color_step(self, v):
        self._fail_color_t = float(v)
        self.update()

    def showEvent(self, e):
        self._tick.start()
        self._refresh_button_effects()
        super().showEvent(e)

    def hideEvent(self, e):
        self._tick.stop(); super().hideEvent(e)

    def _refresh_button_effects(self):
        """Re-creates each button's/the log panel's QGraphicsOpacityEffect
        from scratch instead of reusing the existing instance. This
        guards against a real Qt quirk: when this overlay's ancestor
        chain is hidden and shown again (e.g. switching away from the
        Home tab and back while a failure is still on screen), a widget
        under a QGraphicsOpacityEffect can keep showing its last cached
        render - invisible or faded - even though it's fully visible and
        clickable again as far as Qt's hit-testing is concerned. That's
        exactly "buttons gone but still clickable". A brand new effect
        instance has no stale cache to carry over."""
        self._cancel_fx = self._fade_with_overlay(self._btn_cancel)
        self._retry_fx = self._fade_with_overlay(self._btn_retry)
        self._log_btn_fx = self._fade_with_overlay(self._btn_log)
        self._log_fx = self._fade_with_overlay(self._log_panel)
        self._cancel_fx.setOpacity(self._alpha if self._btn_cancel.isVisible() else 0.0)
        self._retry_fx.setOpacity(self._alpha if self._btn_retry.isVisible() else 0.0)
        self._log_btn_fx.setOpacity(self._alpha if self._btn_log.isVisible() else 0.0)
        self._log_fx.setOpacity(self._alpha if self._log_panel.isVisible() else 0.0)

    def eventFilter(self, obj, event):
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
            self._reposition_buttons()
            if self._log_open:
                self._log_anim.stop()
                self._log_panel.setGeometry(self._log_panel_geometry())
        return False

    def _activate(self, idx, now):
        for i in range(self._active, idx):
            if self._done_at[i] is None: self._done_at[i] = now
        self._prev, self._active = self._active, idx
        self._change_at = self._active_since = now
        if idx == len(self.STEPS) - 1: self._done_at[idx] = now
        self._reposition_buttons()

    def _on_tick(self):
        now = self._clock.elapsed()
        if self._queue and not self._failed and now - self._active_since >= self.MIN_DWELL_MS:
            self._activate(self._queue.pop(0), now)
        if self._finish_armed and not self._failed and self._active == len(self.STEPS) - 1 and not self._queue:
            if now - self._active_since >= self.DONE_DWELL_MS:
                cb, self._finish_cb, self._finish_armed = self._finish_cb, None, False
                if cb: QTimer.singleShot(0, cb)
        # Stage progression/dwell timing above always keeps running (so
        # things don't stall while minimized), but repainting a window
        # nobody can see is wasted power for zero benefit - skip it.
        win = self.window()
        if win is not None and win.isMinimized():
            return
        # Full repaint every tick: the ambient glow is large (a ~380px
        # soft radial gradient) and its color is continuously animating
        # between teal and red, so constraining updates to the small
        # content/line rects (as a pure power optimization) left stale,
        # hard-edged glow outside those rects - exactly the "rectangle"
        # artifact. A plain gradient fill is cheap regardless of area, so
        # the earlier partial-update split wasn't saving much that
        # mattered - correctness wins here.
        self.update()

    def _center(self): return QPointF(self.width() / 2, self.height() * 0.46)
    def _content_rect(self):
        c = self._center(); return QRect(int(c.x()) - 390, int(c.y()) - 150, 780, 350)
    def _line_rect(self): return QRect(0, self.height() - 16, self.width(), 16)

    def _button_row_rect(self):
        c = self._center()
        return QRect(int(c.x() - 56), int(c.y() + 132), 112, 34)

    def _log_panel_geometry(self):
        c = self._center()
        w = 460
        return QRect(int(c.x() - w / 2), int(c.y() + 132 + 34 + 14), w, self.LOG_PANEL_H)

    def _reposition_buttons(self):
        cancel_visible = (not self._failed) and (not self._finish_armed) and self._active < len(self.STEPS) - 1
        c = self._center()
        if self._failed:
            self._btn_retry.setGeometry(int(c.x() - 127), int(c.y() + 132), 120, 34)
            self._btn_log.setGeometry(int(c.x() + 7), int(c.y() + 132), 120, 34)
        # Visibility is purely state-driven (not gated on the current
        # alpha) - the fade itself is handled by each button's own
        # opacity effect in _on_fade_step, which reads this visibility to
        # decide whether to fade to 0 or to the current alpha. Gating
        # setVisible on alpha here would freeze a button hidden forever
        # once _reposition_buttons happened to run at alpha==0 (e.g. the
        # very start of begin()), since nothing re-shows it as alpha
        # rises during the fade-in.
        self._btn_cancel.setVisible(cancel_visible)
        self._btn_retry.setVisible(self._failed)
        self._btn_log.setVisible(self._failed)
        if cancel_visible:
            r = self._button_row_rect()
            self._btn_cancel.setGeometry(r)
        self._cancel_fx.setOpacity(self._alpha if self._btn_cancel.isVisible() else 0.0)
        self._retry_fx.setOpacity(self._alpha if self._btn_retry.isVisible() else 0.0)
        self._log_btn_fx.setOpacity(self._alpha if self._btn_log.isVisible() else 0.0)
        if not self._failed:
            self._log_panel.hide()

    # ---------- painting ----------
    def _lerp_color(self, c1, c2, t):
        t = max(0.0, min(1.0, t))
        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * t),
            int(c1.green() + (c2.green() - c1.green()) * t),
            int(c1.blue() + (c2.blue() - c1.blue()) * t),
        )

    def _font(self, px, weight=None, spacing=None):
        f = QFont(self.font()); f.setPixelSize(px)
        if weight is not None: f.setWeight(weight)
        if spacing: f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
        return f

    def _draw_phase_text(self, p, idx, failed, opacity, dy, now, cx, cy):
        base = p.opacity()
        p.setOpacity(base * opacity)
        headline = "Couldn't process link" if failed else self.STEPS[idx][1]
        detail = "Check the link and try again" if failed else self.STEPS[idx][3].format(host=self._host)
        hf = self._font(38, QFont.Weight.Light)
        p.setFont(hf); p.setPen(_qc(TEXT_MAIN))
        p.drawText(QRectF(cx - 390, cy - 96 + dy, 780, 56), Qt.AlignmentFlag.AlignCenter, headline)
        if not failed and idx < len(self.STEPS) - 1:
            tw = QFontMetrics(hf).horizontalAdvance(headline)
            n = int(now / 380) % 4
            p.setPen(_qc(TEAL_ACCENT))
            p.drawText(QRectF(cx + tw / 2 + 4, cy - 96 + dy, 60, 56), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "." * n)
        p.setFont(self._font(14)); p.setPen(_qc(ERROR_RED if failed else TEXT_MUTED))
        fm = QFontMetrics(p.font())
        p.drawText(QRectF(cx - 390, cy - 34 + dy, 780, 24), Qt.AlignmentFlag.AlignCenter,
                   fm.elidedText(detail, Qt.TextElideMode.ElideRight, 760))
        p.setOpacity(base)

    def paintEvent(self, event):
        p = QPainter(self)
        a = self._alpha
        if a <= 0.001: return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setOpacity(a)
        now = self._clock.elapsed()
        accent = self._lerp_color(_qc(TEAL_ACCENT), _qc(ERROR_RED), self._fail_color_t)

        # background + soft ambient glow
        p.fillRect(event.rect(), _qc(BG_DARK))
        c = self._center()
        glow = QRadialGradient(QPointF(c.x(), c.y() - 30), 380)
        g0 = QColor(accent); g0.setAlpha(24); g1 = QColor(accent); g1.setAlpha(0)
        glow.setColorAt(0.0, g0); glow.setColorAt(1.0, g1)
        p.fillRect(event.rect(), QBrush(glow))

        # content slides up a few px as the screen fades in
        p.save()
        p.translate(0, (1.0 - self._ease.valueForProgress(a)) * 14)
        cx, cy = c.x(), c.y()

        # host chip
        cf = self._font(12, None, 1.2)
        host = QFontMetrics(cf).elidedText(self._host, Qt.TextElideMode.ElideRight, 320)
        tw = QFontMetrics(cf).horizontalAdvance(host)
        chip = QRectF(cx - (tw + 46) / 2, cy - 138, tw + 46, 28)
        p.setPen(QPen(_qc("#2C2C2C"), 1)); p.setBrush(_tint_overlay(7, 6))
        p.drawRoundedRect(chip, 14, 14)
        pulse = 0.5 + 0.5 * math.sin(now / 260.0)
        dot = QColor(accent); dot.setAlpha(int(110 + 145 * pulse))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(dot)
        p.drawEllipse(QPointF(chip.left() + 16, chip.center().y()), 3, 3)
        p.setFont(cf); p.setPen(_qc(TEXT_MUTED))
        p.drawText(QRectF(chip.left() + 27, chip.top(), tw + 12, chip.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, host)

        # headline + detail (cross-fade / slide between stages)
        t = self._ease.valueForProgress(max(0.0, min(1.0, (now - self._change_at) / 360.0)))
        if t < 1.0:
            self._draw_phase_text(p, self._prev, False, 1.0 - t, -12 * t, now, cx, cy)
            self._draw_phase_text(p, self._active, self._failed, t, 12 * (1.0 - t), now, cx, cy)
        else:
            self._draw_phase_text(p, self._active, self._failed, 1.0, 0, now, cx, cy)

        # step tracker
        n, spacing, r = len(self.STEPS), 96.0, 8.0
        ty = cy + 64
        x0 = cx - spacing * (n - 1) / 2
        for i in range(n - 1):
            xa, xb = x0 + i * spacing + r + 7, x0 + (i + 1) * spacing - r - 7
            p.setPen(QPen(_qc("#2A2A2A"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(xa, ty), QPointF(xb, ty))
            if self._done_at[i] is not None:
                fp = self._ease.valueForProgress(max(0.0, min(1.0, (now - self._done_at[i]) / 320.0)))
                p.setPen(QPen(_qc(TEAL_ACCENT), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(xa, ty), QPointF(xa + (xb - xa) * fp, ty))
        lf = self._font(11, None, 0.6)
        for i in range(n):
            x = x0 + i * spacing
            done = self._done_at[i] is not None
            is_active = (i == self._active) and not done
            if self._failed and i == self._active:
                p.setPen(QPen(_qc(ERROR_RED), 2)); p.setBrush(_qc(ERROR_RED))
                p.drawEllipse(QPointF(x, ty), r, r)
                p.setPen(QPen(_qc("#0B0B0B"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(x - 3, ty - 3), QPointF(x + 3, ty + 3)); p.drawLine(QPointF(x + 3, ty - 3), QPointF(x - 3, ty + 3))
                lab = _qc(ERROR_RED)
            elif done:
                e = self._ease.valueForProgress(max(0.0, min(1.0, (now - self._done_at[i]) / 280.0)))
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(_qc(TEAL_ACCENT))
                p.drawEllipse(QPointF(x, ty), r * (0.55 + 0.45 * e), r * (0.55 + 0.45 * e))
                ck = _qc("#0B0B0B"); ck.setAlphaF(e)
                p.setPen(QPen(ck, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)); p.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath(); path.moveTo(x - 3.6, ty + 0.4); path.lineTo(x - 1.0, ty + 3.0); path.lineTo(x + 3.8, ty - 2.8)
                p.drawPath(path)
                lab = _qc("#9A9A9A")
            elif is_active:
                ph = (now % 1300) / 1300.0
                halo = _qc(TEAL_ACCENT); halo.setAlpha(int(95 * (1 - ph)))
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(halo)
                p.drawEllipse(QPointF(x, ty), r + 2 + 9 * ph, r + 2 + 9 * ph)
                p.setPen(QPen(_qc(TEAL_ACCENT), 2)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(x, ty), r, r)
                br = 3.2 + 0.8 * math.sin(now / 200.0)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(_qc(TEAL_ACCENT))
                p.drawEllipse(QPointF(x, ty), br, br)
                lab = _qc(TEXT_MAIN)
            else:
                p.setPen(QPen(_qc("#3A3A3A"), 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(x, ty), r - 1, r - 1)
                lab = _qc("#555555")
            p.setFont(lf); p.setPen(lab)
            p.drawText(QRectF(x - 50, ty + r + 10, 100, 16), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.STEPS[i][2])

        # Cancel / Try Again / Error Log are real child widgets now (see
        # _build_buttons) - they paint themselves on top of this, and
        # _reposition_buttons keeps their geometry/visibility in sync.
        p.restore()

        # racing line along the bottom edge (VS Code style): thin, and the
        # lit segment grows out of a point, then the trailing edge speeds
        # up to close the gap on itself right as it reaches the far edge,
        # collapsing back to a point before instantly looping - rather
        # than a fixed-width comet that just slides back and forth.
        line_h = 2.0
        w, ly = float(self.width()), float(self.height() - line_h)
        track = QColor(accent); track.setAlpha(22)
        p.fillRect(QRectF(0, ly, w, line_h), track)
        done_prog = 0.0
        if self._active == len(self.STEPS) - 1 and not self._failed:
            done_prog = self._ease.valueForProgress(max(0.0, min(1.0, (now - self._active_since) / 320.0)))
        t = (now % self.LINE_PERIOD_MS) / float(self.LINE_PERIOD_MS)
        lead = w * t
        gap = (w * 0.32) * math.sin(math.pi * t)
        trail = max(0.0, lead - gap)
        seg_w = max(1.5, lead - trail)
        p.setOpacity(a * (1.0 - done_prog))
        body = QColor(accent); body.setAlpha(150)
        p.fillRect(QRectF(trail, ly, seg_w, line_h), body)
        head_w = min(seg_w, 18.0)
        p.fillRect(QRectF(lead - head_w, ly, head_w, line_h), QColor(accent).lighter(160))
        if done_prog > 0:
            p.setOpacity(a * done_prog)
            p.fillRect(QRectF(0, ly, w * done_prog, line_h), accent)
        p.end()
