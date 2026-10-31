import theme
from theme import ss as _ss, qc as _qc
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QSize, Signal, QPoint, QVariantAnimation, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QCursor, QPainter, QPainterPath, QColor, QGraphicsOpacityEffect, QIcon

from src.ui.styles import SIDEBAR_DARK, TEAL_ACCENT, TEXT_MUTED, crisp_font, _hover_overlay

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
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(icon.pixmap(22, 22))
        self.icon_lbl.setFixedSize(22, 22)
        _ss(self.icon_lbl, "background: transparent; border: none;")
        
        self.text_lbl = QLabel(name)
        self.text_lbl.setFont(crisp_font("Roboto", 11, QFont.Weight.Medium))
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
        return QColor(theme.accent_text()) if active else _qc(TEXT_MUTED)

    def _bg_for(self, active):
        return _qc("#142C28", "bg") if active else QColor(0, 0, 0, 0)

    def apply_theme(self):
        self._color_anim.stop()
        self._current_text = self._text_for(self._is_active)
        self._current_bg = self._bg_for(self._is_active)
        self._update_text_color()
        self.update()

    def set_icon(self, icon):
        self.icon_lbl.setPixmap(icon.pixmap(22, 22))

    def _update_text_color(self):
        text = self._current_text.name()
        self.text_lbl.setStyleSheet(f"color: {text}; border: none; background: transparent;")

    def _on_color_step(self, progress):
        self._current_text = self._lerp(self._start_text, self._target_text, progress)
        self._current_bg = self._lerp(self._start_bg, self._target_bg, progress)
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
            self._update_text_color()

    def _animate_to(self, target_text, target_bg, duration):
        self._color_anim.stop()
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

class Sidebar(QFrame):
    tab_requested = Signal(int)

    def __init__(self, initial_collapsed=False, icons=None, parent=None):
        super().__init__(parent)
        self.icons = icons or {}
        self.expanded_w = 210
        self.collapsed_w = 68
        self.is_collapsed = initial_collapsed

        initial_width = self.collapsed_w if self.is_collapsed else self.expanded_w
        self.setFixedWidth(initial_width)
        _ss(self, f"QFrame {{ background-color: {SIDEBAR_DARK}; border: none; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 28, 12, 20)
        layout.setSpacing(12)

        self.menu_btn = QPushButton()
        initial_icon = "expand" if self.is_collapsed else "collapse"
        self.menu_btn.setIcon(self.icons.get(initial_icon, QIcon()))
        self.menu_btn.setIconSize(QSize(22, 22))
        self.menu_btn.setFixedSize(44, 32)
        self.menu_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self.menu_btn, "QPushButton { background: transparent; border: none; border-radius: 8px; } QPushButton:hover { background-color: #222222; }")
        self.menu_btn.clicked.connect(self.toggle_sidebar)
        layout.addWidget(self.menu_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(20)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(lambda v: self.setFixedWidth(int(v)))

        self.nav_btns = []
        nav_items = [("Home", "home", 0), ("TrimLoad", "scissors", 1), ("Downloads", "downloads", 2), ("Settings", "settings", 3)]
        for name, icon_name, idx in nav_items:
            btn = SidebarNavButton(name, self.icons.get(icon_name, QIcon()), idx, is_active=(idx == 0))
            btn._icon_name = icon_name
            btn.set_collapsed(self.is_collapsed, animate=False)
            btn.clicked.connect(self.tab_requested.emit)
            layout.addWidget(btn)
            self.nav_btns.append(btn)

        layout.addStretch()

    def toggle_sidebar(self):
        self.is_collapsed = not self.is_collapsed
        collapsed = self.is_collapsed

        self._anim.stop()
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(self.collapsed_w if collapsed else self.expanded_w)

        self.menu_btn.setIcon(self.icons.get("expand" if collapsed else "collapse", QIcon()))

        if collapsed:
            for btn in self.nav_btns:
                btn.begin_collapse_fade()
        else:
            for btn in self.nav_btns:
                btn.begin_expand_layout()

        self._anim.start()

    def set_active_tab(self, idx):
        for i, btn in enumerate(self.nav_btns):
            btn.set_active(i == idx)