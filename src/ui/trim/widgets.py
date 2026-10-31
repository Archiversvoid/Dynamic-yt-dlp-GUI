"""Widgets that only the TrimLoad tab uses: loading spinner/overlay, aspect-ratio label, the trim range slider."""
import os
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from theme import qc as _qc, ss as _ss
from src.paths import repo_root
from src.ui.styles import TEAL_ACCENT


try:
    from PySide6.QtSvgWidgets import QSvgWidget
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False


class SvgSpinnerWidget(QWidget):
    def __init__(self, svg_path, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self.renderer = QSvgRenderer(svg_path) if HAS_SVG and os.path.exists(svg_path) else None
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(16)

    def rotate(self):
        self.angle = (self.angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        if not self.renderer:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        painter.translate(-self.width() / 2, -self.height() / 2)
        self.renderer.render(painter, QRectF(0, 0, self.width(), self.height()))


class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        _ss(self, "background-color: rgba(0, 0, 0, 160); border-radius: 12px")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_dir = os.path.join(str(repo_root), "icons")
        svg_path = os.path.join(icon_dir, "line-md--loading-loop.svg")
        if not os.path.exists(svg_path):
            svg_path = os.path.join(icon_dir, "line-md--loading-loop")

        if HAS_SVG and os.path.exists(svg_path):
            self.spinner = SvgSpinnerWidget(svg_path, self)
            layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            self.spinner = None
            lbl = QLabel("Loading...")
            _ss(lbl, f"color: {TEAL_ACCENT}; font-size: 16px; font-weight: bold;")
            layout.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        self.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())

    def start(self):
        if self.parent():
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        self.show()
        self.raise_()

    def stop(self):
        self.hide()


class AspectRatioLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pix = None
        _ss(self, "background-color: #000000;")
        
    def setPixmap(self, p):
        self.pix = p
        super().setPixmap(self.scaled_pixmap())
        
    def resizeEvent(self, event):
        if self.pix:
            super().setPixmap(self.scaled_pixmap())
        super().resizeEvent(event)
        
    def scaled_pixmap(self):
        if not self.pix: 
            return QPixmap()
        return self.pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class TrimRangeSlider(QWidget):
    positionChanged = Signal(float)
    seekRequested = Signal(float)
    trimRangeChanged = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.duration = 1.0
        self.start_time = 0.0
        self.end_time = 1.0
        self.current_time = 0.0
        self._dragging = None
        self.setMouseTracking(True)

    def set_duration(self, dur):
        self.duration = max(dur, 1.0)
        self.start_time = 0.0
        self.end_time = self.duration
        self.current_time = 0.0
        self.update()

    def set_position(self, pos):
        self.current_time = max(0.0, min(pos, self.duration))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cy = h - 12
        margin = 14
        usable_w = w - (margin * 2)
        if usable_w <= 0 or self.duration <= 0:
            return

        painter.setPen(QPen(_qc("#3A3A3A"), 4))
        painter.drawLine(QLineF(margin, cy, w - margin, cy))

        start_x = margin + (self.start_time / self.duration) * usable_w
        end_x = margin + (self.end_time / self.duration) * usable_w

        painter.setPen(QPen(_qc(TEAL_ACCENT), 4))
        painter.drawLine(QLineF(start_x, cy, end_x, cy))

        handle_w = 12
        handle_h = 22

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_qc(TEAL_ACCENT))
        start_rect = QRectF(start_x - handle_w / 2, cy - handle_h / 2, handle_w, handle_h)
        painter.drawRoundedRect(start_rect, handle_w / 2, handle_w / 2)
        
        painter.setPen(QPen(_qc("#121212"), 2))
        painter.drawLine(QLineF(start_x, cy - 4, start_x, cy + 4))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_qc(TEAL_ACCENT))
        end_rect = QRectF(end_x - handle_w / 2, cy - handle_h / 2, handle_w, handle_h)
        painter.drawRoundedRect(end_rect, handle_w / 2, handle_w / 2)
        
        painter.setPen(QPen(_qc("#121212"), 2))
        painter.drawLine(QLineF(end_x, cy - 4, end_x, cy + 4))

        pos_x = margin + (self.current_time / self.duration) * usable_w
        top_y = cy - 22

        painter.setPen(QPen(_qc(TEAL_ACCENT), 2))
        painter.drawLine(QLineF(pos_x, cy, pos_x, top_y))

        glow_color = _qc(TEAL_ACCENT)
        glow_color.setAlpha(70)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow_color)
        painter.drawEllipse(QPointF(pos_x, top_y), 8, 8)

        painter.setBrush(_qc(TEAL_ACCENT))
        painter.drawEllipse(QPointF(pos_x, top_y), 4.5, 4.5)

    def mousePressEvent(self, event):
        x = event.position().x()
        margin = 14
        usable_w = self.width() - (margin * 2)
        if usable_w <= 0: return

        click_time = max(0.0, min(((x - margin) / usable_w) * self.duration, self.duration))
        start_x = margin + (self.start_time / self.duration) * usable_w
        end_x = margin + (self.end_time / self.duration) * usable_w
        pos_x = margin + (self.current_time / self.duration) * usable_w

        if abs(x - start_x) <= 12:
            self._dragging = 'start'
        elif abs(x - end_x) <= 12:
            self._dragging = 'end'
        elif abs(x - pos_x) <= 12:
            self._dragging = 'position'
        else:
            self._dragging = 'position'
            self.current_time = click_time
            self.positionChanged.emit(self.current_time)
        self.update()

    def mouseMoveEvent(self, event):
        margin = 14
        usable_w = self.width() - (margin * 2)
        if usable_w <= 0: return

        x = event.position().x()
        start_x = margin + (self.start_time / self.duration) * usable_w
        end_x = margin + (self.end_time / self.duration) * usable_w
        pos_x = margin + (self.current_time / self.duration) * usable_w

        if self._dragging:
            t = max(0.0, min(((x - margin) / usable_w) * self.duration, self.duration))
            if self._dragging == 'start':
                self.start_time = min(t, self.end_time - 0.5)
                self.current_time = self.start_time
                self.positionChanged.emit(self.current_time)
                self.trimRangeChanged.emit(self.start_time, self.end_time)
            elif self._dragging == 'end':
                self.end_time = max(t, self.start_time + 0.5)
                self.current_time = self.end_time
                self.positionChanged.emit(self.current_time)
                self.trimRangeChanged.emit(self.start_time, self.end_time)
            elif self._dragging == 'position':
                self.current_time = t
                self.positionChanged.emit(self.current_time)
            self.update()
        else:
            if abs(x - start_x) <= 12 or abs(x - end_x) <= 12 or abs(x - pos_x) <= 12:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self.seekRequested.emit(self.current_time)
        self._dragging = None
