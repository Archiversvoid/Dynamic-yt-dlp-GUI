"""Cross-thread signals for the TrimLoad tab."""
from PySide6.QtCore import QObject, Signal


class TrimSignals(QObject):
    loaded = Signal(dict)
    error = Signal(int, str)
    phase = Signal(int, str)
