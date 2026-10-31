"""The animated combo box used across the app."""
from PySide6.QtCore import (
    QEasingCurve, QEvent, QParallelAnimationGroup, QPoint, QPropertyAnimation, QTimer)
from PySide6.QtWidgets import QComboBox


class AnimatedComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup = None
        self._anim_group = None

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        if popup and popup is not self._popup:
            self._popup = popup
            popup.installEventFilter(self)
        if popup:
            popup.setWindowOpacity(0.0)
            QTimer.singleShot(0, self._animate_popup)

    def eventFilter(self, obj, event):
        if obj is self._popup and event.type() == QEvent.Type.Show:
            obj.setWindowOpacity(0.0)
        return super().eventFilter(obj, event)

    def _animate_popup(self):
        popup = self._popup
        if not popup:
            return

        if self._anim_group and self._anim_group.state() == QParallelAnimationGroup.State.Running:
            self._anim_group.stop()

        self._anim_group = QParallelAnimationGroup(self)

        fade_anim = QPropertyAnimation(popup, b"windowOpacity")
        fade_anim.setDuration(200)
        fade_anim.setStartValue(0.0)
        fade_anim.setEndValue(1.0)
        fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        slide_anim = QPropertyAnimation(popup, b"pos")
        slide_anim.setDuration(200)

        target_pos = popup.pos()
        global_pos = self.mapToGlobal(QPoint(0, self.height()))

        if target_pos.y() < global_pos.y() - 10:
            slide_anim.setStartValue(target_pos + QPoint(0, 8))
        else:
            slide_anim.setStartValue(target_pos + QPoint(0, -8))

        slide_anim.setEndValue(target_pos)
        slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_group.addAnimation(fade_anim)
        self._anim_group.addAnimation(slide_anim)
        self._anim_group.start()
