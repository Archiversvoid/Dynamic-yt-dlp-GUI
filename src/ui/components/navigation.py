"""Sidebar navigation buttons and the Downloads filter tabs."""
import theme
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget
from theme import qc as _qc, ss as _ss
from src.ui.styles import _crisp_font, _hover_overlay, TEAL_ACCENT, TEXT_MUTED


class FilterTab(QFrame):
    clicked = Signal(str)
    def __init__(self, name, count, is_active=False, parent=None):
        super().__init__(parent)
        self.name, self._is_active, self._count = name, is_active, count
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(32)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 0, 16, 0)
        self.layout.setSpacing(8)
        self.text_lbl = QLabel(name)
        self.text_lbl.setFont(_crisp_font("Roboto", 10, QFont.Weight.Medium))
        self.badge_lbl = QLabel(str(count if count < 100 else "99+"))
        self.badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_lbl.setFixedHeight(20)
        self.badge_lbl.setMinimumWidth(16)
        self.layout.addWidget(self.text_lbl)
        self.layout.addWidget(self.badge_lbl)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(250)
        self._anim.valueChanged.connect(self._on_anim_step)
        self._current_text, self._current_badge_bg, self._current_bg = self._colors(is_active)
        self._update_stylesheet()
    def update_count(self, count):
        if self._count != count:
            self._count = count
            self.badge_lbl.setText(str(count if count < 100 else "99+"))
    def set_active(self, active):
        if self._is_active == active: return
        self._is_active = active
        self._animate_colors(*self._colors(active), 250)
    def _animate_colors(self, t_text, t_badge, t_bg, duration):
        self._anim.stop()
        self._anim.setDuration(duration)
        self._start_text, self._start_badge_bg, self._start_bg = self._current_text, self._current_badge_bg, self._current_bg
        self._target_text, self._target_badge_bg, self._target_bg = t_text, t_badge, t_bg
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
    def _on_anim_step(self, progress):
        self._current_text = self._interpolate_color(self._start_text, self._target_text, progress)
        self._current_badge_bg = self._interpolate_color(self._start_badge_bg, self._target_badge_bg, progress)
        self._current_bg = self._interpolate_color(self._start_bg, self._target_bg, progress)
        self._update_stylesheet()
    def _interpolate_color(self, c1, c2, factor):
        return QColor(int(c1.red() + (c2.red() - c1.red()) * factor), 
                      int(c1.green() + (c2.green() - c1.green()) * factor), 
                      int(c1.blue() + (c2.blue() - c1.blue()) * factor))
    def _colors(self, active, hover=False):
        """(text, badge bg, tab bg) for the current theme. These are already
        themed QColors, which is why _update_stylesheet below applies its
        stylesheets raw instead of through _ss (it would map them twice)."""
        if active:
            return QColor(theme.accent_text()), _qc("#1B3D37", "bg"), _qc("#142C28", "bg")
        if hover:
            return _qc("#FFFFFF", "text"), _qc("#555555", "bg"), _qc("#333333", "bg")
        return _qc("#E0E0E0", "text"), _qc("#3D3D3D", "bg"), _qc("#2A2A2A", "bg")

    def apply_theme(self):
        self._anim.stop()
        self._current_text, self._current_badge_bg, self._current_bg = self._colors(self._is_active)
        self._update_stylesheet()

    def _update_stylesheet(self):
        text, badge_bg, bg = self._current_text.name(), self._current_badge_bg.name(), self._current_bg.name()
        self.setStyleSheet(f"FilterTab {{ background-color: {bg}; border-radius: 16px; border: none; }}")  # theme: raw
        self.text_lbl.setStyleSheet(f"color: {text}; border: none; background: transparent;")  # theme: raw
        self.badge_lbl.setStyleSheet(f'background-color: {badge_bg}; color: {text}; border-radius: 10px; min-width: 14px; font-size: 11px; font-weight: bold; padding: 0px 8px; border: none;')  # theme: raw
    def enterEvent(self, event):
        if not self._is_active: self._animate_colors(*self._colors(False, hover=True), 150)
        super().enterEvent(event)
    def leaveEvent(self, event):
        if not self._is_active: self._animate_colors(*self._colors(False), 150)
        super().leaveEvent(event)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.clicked.emit(self.name)


class FilterTabBar(QFrame):
    filter_changed = Signal(str)
    def __init__(self, filters, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.tabs = {}
        self.active_tab = filters[0]
        self.indicator = QFrame(self)
        _ss(self.indicator, "background-color: transparent; border: none; border-radius: 16px;")
        self.anim = QPropertyAnimation(self.indicator, b"geometry")
        self.anim.setDuration(350)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 6, 0, 6)
        self.layout.setSpacing(10)
        for f_name in filters:
            tab = FilterTab(f_name, 0, is_active=(f_name == self.active_tab))
            tab.clicked.connect(self._on_tab_clicked)
            self.layout.addWidget(tab)
            self.tabs[f_name] = tab
        self.layout.addStretch()
    def update_counts(self, counts):
        for f_name, tab in self.tabs.items():
            if f_name in counts: tab.update_count(counts[f_name])
        if not self.anim.state() == QPropertyAnimation.State.Running and self.active_tab in self.tabs:
            self.indicator.setGeometry(self.tabs[self.active_tab].geometry())
    def _on_tab_clicked(self, f_name):
        if f_name == self.active_tab: return
        prev_tab = self.active_tab
        self.active_tab = f_name
        self.tabs[prev_tab].set_active(False)
        self.tabs[f_name].set_active(True)
        self.anim.stop()
        self.anim.setStartValue(self.indicator.geometry())
        self.anim.setEndValue(self.tabs[f_name].geometry())
        self.anim.start()
        self.filter_changed.emit(f_name)
    def showEvent(self, event):
        super().showEvent(event)
        if self.active_tab in self.tabs: self.indicator.setGeometry(self.tabs[self.active_tab].geometry())
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.active_tab in self.tabs and self.anim.state() != QPropertyAnimation.State.Running:
            self.indicator.setGeometry(self.tabs[self.active_tab].geometry())


class _NavIcon(QWidget):
    """The sidebar icon. It holds the icon as drawn plus a copy tinted with the accent colour and
    cross-fades between them (t=0 plain ... t=1 accent). Both pixmaps are rendered once, when the
    icon is set; an animation step only repaints this 22x22 widget, so switching tabs stays cheap."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._base = QPixmap()
        self._active = QPixmap()
        self._t = 0.0

    def set_pixmaps(self, base, active):
        self._base, self._active = base, active
        self.update()

    def set_t(self, t):
        t = max(0.0, min(1.0, float(t)))
        if t != self._t:
            self._t = t
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._t >= 0.999 and not self._active.isNull():
            p.drawPixmap(0, 0, self._active)          # resting active state: the tinted icon only
            return
        if not self._base.isNull():
            p.drawPixmap(0, 0, self._base)
        if self._t > 0.001 and not self._active.isNull():
            p.setOpacity(self._t)                      # fade the tinted copy in over the plain one
            p.drawPixmap(0, 0, self._active)


class SidebarNavButton(QFrame):
    clicked = Signal(int)
    def __init__(self, name, icon, idx, is_active=False, parent=None):
        super().__init__(parent)
        self.idx = idx
        self._is_active = is_active
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(44)
        
        _ss(self, "SidebarNavButton { background: transparent; border: none; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 0, 11, 0)
        layout.setSpacing(12)
        
        self.icon_lbl = _NavIcon()
        self._icon_t = 1.0 if is_active else 0.0          # 0 = icon as drawn, 1 = accent colour
        self._icon_start = self._icon_target = self._icon_t
        self.set_icon(icon)
        
        self.text_lbl = QLabel(name)
        self.text_lbl.setFont(_crisp_font("Roboto", 11, QFont.Weight.Medium))
        self.text_lbl.setMinimumWidth(0)
        
        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.text_lbl, 1)

        self._color_anim = QVariantAnimation(self)
        self._color_anim.setDuration(220)
        self._color_anim.valueChanged.connect(self._on_color_step)

        self._current_text = self._text_for(is_active)
        self._current_bg = self._bg_for(is_active)
        self._update_text_color()

        self._ripple_pos = QPoint(0, 0)
        self._ripple_radius = 0.0
        self._ripple_opacity = 0.0
        
        self._ripple_anim = QVariantAnimation(self)
        self._ripple_anim.setDuration(400)
        self._ripple_anim.valueChanged.connect(self._on_ripple_step)
        self._ripple_anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        self._collapsed = False
        self._text_fade_anim = None

        self._text_opacity = QGraphicsOpacityEffect(self.text_lbl)
        self.text_lbl.setGraphicsEffect(self._text_opacity)
        self._text_opacity.setOpacity(1.0)

    def _text_for(self, active):
        """Already-themed QColors (see FilterTab._colors for why that matters)."""
        return QColor(theme.accent_text()) if active else _qc(TEXT_MUTED)

    def _bg_for(self, active):
        return _qc("#142C28", "bg") if active else QColor(0, 0, 0, 0)

    def apply_theme(self):
        self._color_anim.stop()
        self._icon_t = 1.0 if self._is_active else 0.0
        self.icon_lbl.set_t(self._icon_t)
        self._current_text = self._text_for(self._is_active)
        self._current_bg = self._bg_for(self._is_active)
        self._update_text_color()
        self.update()

    def set_icon(self, icon):
        """Render the icon twice - as drawn, and tinted with the accent colour. Done here, once;
        never per animation frame."""
        base = icon.pixmap(22, 22)
        try:
            active = theme.tint_pixmap(base, theme.accent_text())
        except Exception:
            active = base                                  # never let icon tinting break the sidebar
        self.icon_lbl.set_pixmaps(base, active)
        self.icon_lbl.set_t(self._icon_t)

    def _update_text_color(self):
        text = self._current_text.name()
        self.text_lbl.setStyleSheet(f"color: {text}; border: none; background: transparent;")  # theme: raw
        self.update()

    def _on_color_step(self, progress):
        self._current_text = self._lerp(self._start_text, self._target_text, progress)
        self._current_bg = self._lerp(self._start_bg, self._target_bg, progress)
        self._icon_t = self._icon_start + (self._icon_target - self._icon_start) * progress
        self.icon_lbl.set_t(self._icon_t)
        self._update_text_color()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_path = QPainterPath()
        bg_path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        painter.fillPath(bg_path, self._current_bg)

        if self._ripple_opacity > 0:
            painter.setClipPath(bg_path)
            ripple_color = _qc(TEAL_ACCENT)
            ripple_color.setAlphaF(self._ripple_opacity)
            painter.setBrush(ripple_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self._ripple_pos, self._ripple_radius, self._ripple_radius)

    def set_active(self, active, animate=True):
        if self._is_active == active:
            return
        self._is_active = active
        target_text = self._text_for(active)
        target_bg = self._bg_for(active)
        if animate:
            self._animate_to(target_text, target_bg, 220)
        else:
            self._current_text, self._current_bg = target_text, target_bg
            self._icon_t = 1.0 if active else 0.0
            self.icon_lbl.set_t(self._icon_t)
            self._update_text_color()

    def _animate_to(self, target_text, target_bg, duration):
        self._color_anim.stop()
        # Every animation - including a hover that interrupts a tab switch - ends with the icon in
        # the resting state for this button, so it can never get stuck half-tinted.
        self._icon_start = self._icon_t
        self._icon_target = 1.0 if self._is_active else 0.0
        self._color_anim.setDuration(duration)
        self._start_text, self._start_bg = self._current_text, self._current_bg
        self._target_text, self._target_bg = target_text, target_bg
        self._color_anim.setStartValue(0.0)
        self._color_anim.setEndValue(1.0)
        self._color_anim.start()

    def _lerp(self, c1, c2, t):
        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * t),
            int(c1.green() + (c2.green() - c1.green()) * t),
            int(c1.blue() + (c2.blue() - c1.blue()) * t),
            int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
        )

    def enterEvent(self, event):
        if not self._is_active:
            self._animate_to(self._text_for(False), _hover_overlay(), 150)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._is_active:
            self._animate_to(self._text_for(False), QColor(0, 0, 0, 0), 150)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._ripple_pos = event.position().toPoint()
            self._ripple_radius = 0.0
            self._ripple_opacity = 0.35

            self._ripple_anim.stop()
            self._ripple_anim.setStartValue(0.0)
            self._ripple_anim.setEndValue(1.0)
            self._ripple_anim.start()
            
            self.clicked.emit(self.idx)
        super().mousePressEvent(event)

    def _on_ripple_step(self, progress):
        max_radius = self.width() * 1.5
        self._ripple_radius = max_radius * progress
        self._ripple_opacity = 0.35 * (1.0 - progress)
        self.update()

    def set_collapsed(self, collapsed, animate=True):
        self._collapsed = collapsed
        if collapsed:
            self._text_opacity.setOpacity(0.0)
        else:
            self._text_opacity.setOpacity(1.0)

    def begin_collapse_fade(self):
        self._collapsed = True
        if self._text_fade_anim and self._text_fade_anim.state() == QPropertyAnimation.State.Running:
            self._text_fade_anim.stop()
        
        anim = QPropertyAnimation(self._text_opacity, b"opacity", self)
        anim.setDuration(160)
        anim.setStartValue(self._text_opacity.opacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._text_fade_anim = anim
        anim.start()

    def begin_expand_layout(self):
        self._collapsed = False
        if self._text_fade_anim and self._text_fade_anim.state() == QPropertyAnimation.State.Running:
            self._text_fade_anim.stop()
        
        anim = QPropertyAnimation(self._text_opacity, b"opacity", self)
        anim.setDuration(200)
        anim.setStartValue(self._text_opacity.opacity())
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._text_fade_anim = anim
        anim.start()
