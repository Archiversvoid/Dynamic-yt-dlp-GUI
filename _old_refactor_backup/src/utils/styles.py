"""
Global Qt style proxies and event filters.
"""
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QProxyStyle, QStyle, QLineEdit, QScrollBar


class NoFocusRectStyle(QProxyStyle):
    """Suppresses the dotted keyboard-focus rectangle Windows draws on
    buttons/widgets after Alt is pressed."""
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_FrameFocusRect:
            return
        super().drawPrimitive(element, option, painter, widget)


class GlobalContextMenuBlocker(QObject):
    """Blocks native right-click/Menu-key flyouts on QLineEdit and QScrollBar."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ContextMenu and isinstance(obj, (QLineEdit, QScrollBar)):
            return True
        return super().eventFilter(obj, event)