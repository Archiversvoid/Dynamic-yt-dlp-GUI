"""Toast notifications."""
from PySide6.QtCore import (
    QEasingCurve, QObject, QParallelAnimationGroup, QPoint, QPropertyAnimation, Qt, QTimer,
    Signal)
from PySide6.QtGui import QColor, QCursor, QIcon
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton
from theme import ss as _ss
from src.paths import ICON_PATH


class ToastWidget(QFrame):
    dismissed = Signal(object)
    def __init__(self, message, parent=None, icon_pixmap=None, rich_text=False):
        super().__init__(parent)
        self.setWindowIcon(QIcon(ICON_PATH))
        self.setFixedSize(290, 48)
        _ss(self, "QFrame { background-color: #242424; border: 1px solid #333333; border-radius: 12px; }")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(10)
        if icon_pixmap is not None and not icon_pixmap.isNull():
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(22, 22)
            icon_lbl.setPixmap(icon_pixmap)
            _ss(icon_lbl, "background: transparent; border: none;")
        else:
            icon_lbl = QLabel("✕")
            _ss(icon_lbl, "color: #EF4444; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(icon_lbl)
        msg_lbl = QLabel(message)
        if rich_text:
            msg_lbl.setTextFormat(Qt.TextFormat.RichText)
        _ss(msg_lbl, "color: #FFFFFF; font-size: 13px; font-weight: 500; border: none; background: transparent;")
        layout.addWidget(msg_lbl, 1)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(close_btn, "QPushButton { color: #888888; font-size: 13px; font-weight: bold; border: none; background: transparent; } QPushButton:hover { color: #FFFFFF; }")
        close_btn.clicked.connect(self.close_toast)
        layout.addWidget(close_btn)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close_toast)
        self.timer.start(4000)
        self._is_closing = False
    def close_toast(self):
        if self._is_closing: return
        self._is_closing = True
        self.timer.stop()
        self.dismissed.emit(self)


class ToastManager(QObject):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.win = parent_window
        self.toasts = []
    def show_toast(self, message, icon_pixmap=None, rich_text=False):
        toast = ToastWidget(message, parent=self.win, icon_pixmap=icon_pixmap, rich_text=rich_text)
        toast.dismissed.connect(self._remove_toast)
        self.toasts.append(toast)
        toast.show()
        toast.raise_()
        self._reposition_toasts(animate_last=True)
    def _reposition_toasts(self, animate_last=False):
        if not self.win: return
        w_width, w_height = self.win.width(), self.win.height()
        for i, toast in enumerate(self.toasts):
            target_x = w_width - 24 - 290
            target_y = w_height - 24 - (i + 1) * 48 - i * 10
            if animate_last and i == len(self.toasts) - 1:
                toast.move(target_x, w_height + 20)
                anim = QPropertyAnimation(toast, b"pos", toast)
                anim.setDuration(250)
                anim.setStartValue(QPoint(target_x, w_height + 20))
                anim.setEndValue(QPoint(target_x, target_y))
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.start()
                toast._pos_anim = anim
            else:
                anim = QPropertyAnimation(toast, b"pos", toast)
                anim.setDuration(200)
                anim.setStartValue(toast.pos())
                anim.setEndValue(QPoint(target_x, target_y))
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.start()
                toast._pos_anim = anim
    def _remove_toast(self, toast):
        if toast in self.toasts:
            self.toasts.remove(toast)
            anim_group = QParallelAnimationGroup(toast)
            slide_anim = QPropertyAnimation(toast, b"pos", toast)
            slide_anim.setDuration(200)
            slide_anim.setStartValue(toast.pos())
            slide_anim.setEndValue(toast.pos() + QPoint(40, 0))
            slide_anim.setEasingCurve(QEasingCurve.Type.InCubic)
            anim_group.addAnimation(slide_anim)
            def _on_finish():
                toast.deleteLater()
                self._reposition_toasts(animate_last=False)
            anim_group.finished.connect(_on_finish)
            anim_group.start()
            toast._close_anim = anim_group
    def update_positions(self):
        self._reposition_toasts(animate_last=False)
