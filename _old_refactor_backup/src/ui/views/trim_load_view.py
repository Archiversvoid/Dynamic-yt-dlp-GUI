"""
TrimLoad view module for Dynamic 2.
"""
import sys
import os
import sys
import math
import threading
import urllib.request
import webbrowser
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QLineEdit, QComboBox, 
                             QProgressBar, QFrame, QGraphicsDropShadowEffect,
                             QGridLayout, QSpacerItem, QSizePolicy,
                             QGraphicsOpacityEffect, QPlainTextEdit, QProxyStyle, QStyle, QScrollBar)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import (Qt, QUrl, Signal, QPointF, QRectF, QLineF, QObject, QTimer, 
                          QPropertyAnimation, QSequentialAnimationGroup, QParallelAnimationGroup, 
                          QPoint, QEasingCurve, QEvent, QRect, QElapsedTimer, QVariantAnimation)
from PySide6.QtGui import (QFont, QPainter, QColor, QPen, QCursor, QPixmap, QIcon, QDesktopServices,
                         QPainterPath, QBrush, QLinearGradient, QRadialGradient, QFontMetrics, QPalette, QFontDatabase)

# Safe theme import for both runtime and editor linters
try:
    import theme  # type: ignore[import-not-found]
    from theme import ss as _ss, qc as _qc  # type: ignore[import-not-found]
except ImportError:
    _root = Path(__file__).resolve().parent.parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    import theme  # type: ignore[import-not-found]
    from theme import ss as _ss, qc as _qc  # type: ignore[import-not-found]

from src.core.settings_store import get_repo_root
from src.ui.components.overlay import ProcessingOverlay

try:
    from PySide6.QtSvgWidgets import QSvgWidget
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

repo_root = get_repo_root()
cache_dir = repo_root / "cache"
favicon_dir = cache_dir / "favicons"
thumb_dir = cache_dir / "thumbnails"
favicon_dir.mkdir(parents=True, exist_ok=True)
thumb_dir.mkdir(parents=True, exist_ok=True)

TEAL_ACCENT   = "#00BFA5"
BG_DARK       = "#121212"
CARD_BG       = "#1E1E1E"
INPUT_BG      = "#333333"
TEXT_MAIN     = "#FFFFFF"
TEXT_MUTED    = "#8A8A8A"
ERROR_RED     = "#FF5555"

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

_AUDIO_ONLY_DOMAINS = (
    "music.youtube.com", "soundcloud.com", "spotify.com",
    "tidal.com", "deezer.com", "music.apple.com", "apple.com",
    "bandcamp.com", "audiomack.com", "reverbnation.com",
    "mixcloud.com",
)

yt_dlp = None

def _get_yt_dlp():
    global yt_dlp
    if yt_dlp is None:
        try:
            import yt_dlp as _yt_dlp
            yt_dlp = _yt_dlp
        except Exception:
            yt_dlp = False
    return yt_dlp or None


def _mono_family():
    from PySide6.QtGui import QFontDatabase
    for fam in ("Consolas", "Cascadia Mono", "Courier New"):
        if QFontDatabase.hasFamily(fam): return fam
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def _is_audio_only_url(url):
    return any(domain in url.lower() for domain in _AUDIO_ONLY_DOMAINS)


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
        if not popup: return
        if self._anim_group and self._anim_group.state() == QParallelAnimationGroup.State.Running:
            self._anim_group.stop()
        self._anim_group = QParallelAnimationGroup(self)
        fade_anim = QPropertyAnimation(popup, b"windowOpacity")
        fade_anim.setDuration(200); fade_anim.setStartValue(0.0); fade_anim.setEndValue(1.0)
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


def _site_name(url):
    try:
        host = urlparse(url).netloc.lower()
        if "music.youtube.com" in host: return "YouTube Music"
        if "music.apple.com" in host or "apple.com" in host: return "Apple Music"
        if "spotify.com" in host: return "Spotify"
        if "soundcloud.com" in host: return "SoundCloud"
        if "deezer.com" in host: return "Deezer"
        if "tidal.com" in host: return "Tidal"
        if "bandcamp.com" in host: return "Bandcamp"
        if "audiomack.com" in host: return "Audiomack"
        if "youtu.be" in host or "youtube.com" in host: return "YouTube"
        host = host.replace("www.", "").replace("m.", "").replace("music.", "")
        return host.split(".")[0].title()
    except Exception:
        return "YouTube"


def _fetch_favicon_sync(url):
    try:
        parsed = urlparse(url)
        host = parsed.netloc or "unknown"
        filepath = favicon_dir / f"{host}.png"
        if filepath.exists(): return str(filepath)
        furl = f"https://icons.duckduckgo.com/ip3/{parsed.netloc}.ico"
        req = urllib.request.Request(furl, headers={"User-Agent": DEFAULT_UA})
        with urllib.request.urlopen(req, timeout=3) as r: data = r.read()
        with open(filepath, 'wb') as f: f.write(data)
        return str(filepath)
    except Exception:
        return None


def format_time_str(seconds):
    seconds = max(0, float(seconds))
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_time_str(time_str):
    try:
        parts = [float(p) for p in time_str.split(":")]
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2: return parts[0] * 60 + parts[1]
        elif len(parts) == 1: return parts[0]
    except Exception:
        pass
    return -1.0


def jiggle_widget(widget):
    if hasattr(widget, "_jiggle_anim") and widget._jiggle_anim.state() == QSequentialAnimationGroup.State.Running:
        return
    orig_pos = widget.pos()
    group = QSequentialAnimationGroup(widget)
    for offset in [-10, 10, -7, 7, -4, 4, -2, 2, 0]:
        anim = QPropertyAnimation(widget, b"pos", widget)
        anim.setDuration(35); anim.setStartValue(widget.pos()); anim.setEndValue(orig_pos + QPoint(offset, 0))
        group.addAnimation(anim)
    widget._jiggle_anim = group
    group.start()


def select_preview_stream(info, url):
    if not isinstance(info, dict): return None, None, False
    formats = info.get('formats') or []
    is_audio_platform = _is_audio_only_url(url)
    if not formats:
        stream_url = info.get('url')
        if stream_url:
            vcodec = info.get('vcodec')
            is_audio = is_audio_platform or (vcodec == 'none')
            return stream_url, 0, is_audio
        return None, None, False
    valid = [f for f in formats if f.get('url') and str(f.get('url')).startswith('http')]
    vids = [f for f in valid if f.get('vcodec') not in ('none', None)]
    all_audio_only = bool(valid) and all(f.get('vcodec') == 'none' for f in valid)
    is_pure_audio = is_audio_platform or all_audio_only
    if is_pure_audio:
        auds = [f for f in valid if f.get('acodec') not in ('none', None)]
        if auds:
            best_aud = sorted(auds, key=lambda x: x.get('abr') or 0, reverse=True)[0]
            return best_aud.get('url'), 0, True
        fallback = [f for f in valid]
        if fallback: return fallback[0].get('url'), 0, True
        return None, None, True

    def vid_score(f):
        s = 0; h = f.get('height') or 9999
        vcodec = (f.get('vcodec') or '').lower(); ext = (f.get('ext') or '').lower()
        if 'av1' in vcodec or 'av01' in vcodec: s -= 100000
        if 'vp9' in vcodec or 'vp09' in vcodec: s -= 20000
        if 'avc' in vcodec or 'h264' in vcodec: s += 50000
        if ext == 'mp4': s += 20000
        if 0 < h <= 720: s += (10000 - h)
        return s

    if vids: best_vid = max(vids, key=vid_score)
    elif valid: best_vid = valid[0]
    else: return None, None, False
    return best_vid.get('url'), best_vid.get('height') or 0, False


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
        if not self.renderer: return
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
        icon_dir = repo_root / "icons"
        svg_path = icon_dir / "line-md--loading-loop.svg"
        if HAS_SVG and svg_path.exists():
            self.spinner = SvgSpinnerWidget(str(svg_path), self)
            layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            self.spinner = None
            lbl = QLabel("Loading...")
            _ss(lbl, f"color: {TEAL_ACCENT}; font-size: 16px; font-weight: bold;")
            layout.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent(): self.setGeometry(0, 0, self.parent().width(), self.parent().height())

    def start(self):
        if self.parent(): self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        self.show(); self.raise_()

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
        if self.pix: super().setPixmap(self.scaled_pixmap())
        super().resizeEvent(event)
        
    def scaled_pixmap(self):
        if not self.pix: return QPixmap()
        return self.pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class TrimRangeSlider(QWidget):
    positionChanged = Signal(float)
    seekRequested = Signal(float)
    trimRangeChanged = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.duration = 1.0; self.start_time = 0.0; self.end_time = 1.0; self.current_time = 0.0
        self._dragging = None; self.setMouseTracking(True)

    def set_duration(self, dur):
        self.duration = max(dur, 1.0); self.start_time = 0.0; self.end_time = self.duration; self.current_time = 0.0
        self.update()

    def set_position(self, pos):
        self.current_time = max(0.0, min(pos, self.duration))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height(); cy = h - 12; margin = 14; usable_w = w - (margin * 2)
        if usable_w <= 0 or self.duration <= 0: return
        painter.setPen(QPen(_qc("#3A3A3A"), 4)); painter.drawLine(QLineF(margin, cy, w - margin, cy))
        start_x = margin + (self.start_time / self.duration) * usable_w
        end_x = margin + (self.end_time / self.duration) * usable_w
        painter.setPen(QPen(_qc(TEAL_ACCENT), 4)); painter.drawLine(QLineF(start_x, cy, end_x, cy))
        handle_w = 12; handle_h = 22
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(_qc(TEAL_ACCENT))
        painter.drawRoundedRect(QRectF(start_x - handle_w / 2, cy - handle_h / 2, handle_w, handle_h), handle_w / 2, handle_w / 2)
        painter.setPen(QPen(_qc("#121212"), 2)); painter.drawLine(QLineF(start_x, cy - 4, start_x, cy + 4))
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(_qc(TEAL_ACCENT))
        painter.drawRoundedRect(QRectF(end_x - handle_w / 2, cy - handle_h / 2, handle_w, handle_h), handle_w / 2, handle_w / 2)
        painter.setPen(QPen(_qc("#121212"), 2)); painter.drawLine(QLineF(end_x, cy - 4, end_x, cy + 4))
        pos_x = margin + (self.current_time / self.duration) * usable_w; top_y = cy - 22
        painter.setPen(QPen(_qc(TEAL_ACCENT), 2)); painter.drawLine(QLineF(pos_x, cy, pos_x, top_y))
        glow_color = _qc(TEAL_ACCENT); glow_color.setAlpha(70)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(glow_color)
        painter.drawEllipse(QPointF(pos_x, top_y), 8, 8)
        painter.setBrush(_qc(TEAL_ACCENT)); painter.drawEllipse(QPointF(pos_x, top_y), 4.5, 4.5)

    def mousePressEvent(self, event):
        x = event.position().x(); margin = 14; usable_w = self.width() - (margin * 2)
        if usable_w <= 0: return
        click_time = max(0.0, min(((x - margin) / usable_w) * self.duration, self.duration))
        start_x = margin + (self.start_time / self.duration) * usable_w
        end_x = margin + (self.end_time / self.duration) * usable_w
        pos_x = margin + (self.current_time / self.duration) * usable_w
        if abs(x - start_x) <= 12: self._dragging = 'start'
        elif abs(x - end_x) <= 12: self._dragging = 'end'
        else:
            self._dragging = 'position'; self.current_time = click_time
            self.positionChanged.emit(self.current_time)
        self.update()

    def mouseMoveEvent(self, event):
        margin = 14; usable_w = self.width() - (margin * 2)
        if usable_w <= 0: return
        x = event.position().x()
        if self._dragging:
            t = max(0.0, min(((x - margin) / usable_w) * self.duration, self.duration))
            if self._dragging == 'start':
                self.start_time = min(t, self.end_time - 0.5); self.current_time = self.start_time
                self.positionChanged.emit(self.current_time); self.trimRangeChanged.emit(self.start_time, self.end_time)
            elif self._dragging == 'end':
                self.end_time = max(t, self.start_time + 0.5); self.current_time = self.end_time
                self.positionChanged.emit(self.current_time); self.trimRangeChanged.emit(self.start_time, self.end_time)
            elif self._dragging == 'position':
                self.current_time = t; self.positionChanged.emit(self.current_time)
            self.update()

    def mouseReleaseEvent(self, event):
        if self._dragging: self.seekRequested.emit(self.current_time)
        self._dragging = None


class TrimSignals(QObject):
    loaded = Signal(dict)
    error = Signal(int, str)
    phase = Signal(int, str)


class TrimLoadTab(QWidget):
    def __init__(self, main_win=None):
        super().__init__()
        self.main_win = main_win
        self.signals = TrimSignals()
        self.signals.loaded.connect(self._on_metadata_loaded)
        self.signals.error.connect(self._on_scrape_error)
        self.signals.phase.connect(self._on_trim_phase)
        
        self.current_info = {}
        self.duration = 1.0; self.start_trim = 0.0; self.end_trim = 1.0
        self.is_audio_mode = False; self.preview_failed = False

        self._setup_player()
        self._build_ui()

        self._proc_run_id, self._proc_cancel_flag = 0, None
        self.proc_overlay = ProcessingOverlay(self)
        self.proc_overlay.cancel_requested.connect(self._on_processing_cancel)
        self.proc_overlay.retry_requested.connect(self._on_processing_cancel)

        self._show_initial_view()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "loading_overlay"):
            self.loading_overlay.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
        if hasattr(self, "preview_error_lbl") and self.preview_error_lbl.isVisible():
            self.preview_error_lbl.adjustSize()
            self.preview_error_lbl.move(
                (self.video_frame.width() - self.preview_error_lbl.width()) // 2,
                (self.video_frame.height() - self.preview_error_lbl.height()) // 2
            )

    def _setup_player(self):
        self.audio_output = QAudioOutput(); self.audio_output.setVolume(1.0)
        self.player = QMediaPlayer(); self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.errorOccurred.connect(self._on_player_error)

    def _on_player_error(self, error, error_string):
        if error != QMediaPlayer.Error.NoError:
            self._show_toast_error("Preview stream unavailable. Thumbnail mode active.")
            self.player.stop(); self.preview_failed = True
            self.video_widget.hide(); self.thumbnail_label.show()
            self.preview_error_lbl.show(); self.preview_error_lbl.raise_()
            self.loading_overlay.stop()

    def _on_media_status_changed(self, status):
        if status in (QMediaPlayer.MediaStatus.BufferingMedia, QMediaPlayer.MediaStatus.LoadingMedia):
            self.loading_overlay.start()
        else:
            self.loading_overlay.stop()

    def _download_dir(self):
        default = str(repo_root / "downloads")
        settings = getattr(self.main_win, "settings", None)
        if isinstance(settings, dict): return settings.get("download_dir") or default
        return default

    def _show_toast_error(self, msg):
        self._show_toast(msg)

    def _show_toast(self, msg, icon_pixmap=None, rich_text=False):
        if self.main_win and hasattr(self.main_win, "toast_mgr"):
            self.main_win.toast_mgr.show_toast(msg, icon_pixmap=icon_pixmap, rich_text=rich_text)

    def _mark_inputs_invalid(self):
        err_style = f"background-color: #2A1515; color: {TEXT_MAIN}; border: 1.5px solid {ERROR_RED}; border-radius: 4px; padding: 0 8px; font-size: 13px;"
        _ss(self.start_input, err_style); _ss(self.end_input, err_style)
        jiggle_widget(self.start_input); jiggle_widget(self.end_input)

    def _reset_inputs_style(self):
        norm_style = f"background-color: {INPUT_BG}; color: {TEXT_MAIN}; border: none; border-radius: 4px; padding: 0 8px; font-size: 13px;"
        _ss(self.start_input, norm_style); _ss(self.end_input, norm_style)

    def _open_site_url(self):
        url = self.current_info.get('_url')
        if url: QDesktopServices.openUrl(QUrl(url))

    def _build_ui(self):
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0)
        _ss(self, f"background-color: {BG_DARK};")

        self.search_container = QWidget()
        sc_layout = QVBoxLayout(self.search_container)
        sc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_lbl = QLabel("TRIMLOAD")
        _ss(self.title_lbl, f"color: {TEXT_MAIN}; font-size: 68px; font-weight: 300;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sc_layout.addWidget(self.title_lbl); sc_layout.addSpacing(20)

        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Enter link to trim...")
        self.url_entry.setFixedSize(600, 54)
        _ss(self.url_entry, f"QLineEdit {{ background-color: {INPUT_BG}; color: {TEXT_MAIN}; border-radius: 27px; padding: 0 20px; font-size: 18px; border: none; }}")
        self.url_entry.returnPressed.connect(self._process_link)
        sc_layout.addWidget(self.url_entry, alignment=Qt.AlignmentFlag.AlignCenter)

        self.processing_slot = QWidget()
        self.proc_layout = QVBoxLayout(self.processing_slot)
        sc_layout.addWidget(self.processing_slot)
        self.layout.addWidget(self.search_container)

        self.editor_container = QWidget()
        ed_layout = QVBoxLayout(self.editor_container)
        ed_layout.setContentsMargins(20, 16, 20, 20); ed_layout.setSpacing(10)

        self.video_frame = QFrame()
        _ss(self.video_frame, "background-color: #000000;")
        vf_layout = QVBoxLayout(self.video_frame); vf_layout.setContentsMargins(0, 0, 0, 0)
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)
        vf_layout.addWidget(self.video_widget)

        self.thumbnail_label = AspectRatioLabel(self.video_frame)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vf_layout.addWidget(self.thumbnail_label); self.thumbnail_label.hide()
        
        self.preview_error_lbl = QLabel("Couldn't load preview", self.video_frame)
        _ss(self.preview_error_lbl, "color: #FFFFFF; font-size: 16px; font-weight: bold; background-color: rgba(0, 0, 0, 180); padding: 12px 24px;")
        self.preview_error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview_error_lbl.hide()

        self.loading_overlay = LoadingOverlay(self.video_frame)
        ed_layout.addWidget(self.video_frame, 1)

        self.meta_container = QWidget()
        meta_layout = QVBoxLayout(self.meta_container); meta_layout.setContentsMargins(4, 2, 4, 4); meta_layout.setSpacing(4)
        self.meta_title_lbl = QLabel("Media Title")
        _ss(self.meta_title_lbl, "color: #FFFFFF; font-size: 20px; font-weight: bold; border: none;")
        self.meta_title_lbl.setWordWrap(True)

        sub_layout = QHBoxLayout(); sub_layout.setContentsMargins(0, 0, 0, 0); sub_layout.setSpacing(8)
        self.meta_channel_lbl = QLabel("Channel")
        _ss(self.meta_channel_lbl, "color: #DDDDDD; font-size: 14px; border: none;")
        self.meta_dur_lbl = QLabel("0:00 mins")
        _ss(self.meta_dur_lbl, f"color: {TEXT_MAIN}; font-size: 14px; border: none;")
        self.meta_site_lbl = QLabel("YouTube")
        _ss(self.meta_site_lbl, "color: #FFFFFF; font-size: 14px; font-weight: bold; border: none;")
        
        sub_layout.addWidget(self.meta_channel_lbl)
        sub_layout.addWidget(self.meta_dur_lbl)
        sub_layout.addWidget(self.meta_site_lbl)
        sub_layout.addStretch()

        meta_layout.addWidget(self.meta_title_lbl)
        meta_layout.addLayout(sub_layout)
        ed_layout.addWidget(self.meta_container)

        timeline_frame = QFrame(); timeline_frame.setFixedHeight(54)
        _ss(timeline_frame, "background-color: #1A1A1A;")
        tl_layout = QHBoxLayout(timeline_frame); tl_layout.setContentsMargins(8, 0, 12, 0); tl_layout.setSpacing(6)

        self.btn_play = QPushButton()
        self.btn_play.setFixedSize(32, 32); self.btn_play.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self.btn_play, "QPushButton { background: transparent; border: none; }")
        self.icon_play = theme.icon("play", repo_root / "icons", cache_dir)
        self.icon_pause = theme.icon("pause", repo_root / "icons", cache_dir)
        self.btn_play.setIcon(self.icon_play)
        self.btn_play.clicked.connect(self._toggle_play)
        tl_layout.addWidget(self.btn_play)

        self.time_lbl = QLabel("00:00:00 / 00:00:00")
        _ss(self.time_lbl, f"color: {TEXT_MAIN}; font-size: 13px; font-family: '{_mono_family()}'; border: none;")
        tl_layout.addWidget(self.time_lbl)

        self.range_slider = TrimRangeSlider()
        self.range_slider.positionChanged.connect(self._on_slider_position_changed)
        self.range_slider.seekRequested.connect(self._seek_player)
        self.range_slider.trimRangeChanged.connect(self._on_trim_range_changed)
        tl_layout.addWidget(self.range_slider, 1)
        ed_layout.addWidget(timeline_frame)

        dock_frame = QFrame(); dock_frame.setFixedHeight(96)
        _ss(dock_frame, "QFrame { background-color: #1A1A1A; }")
        grid = QGridLayout(dock_frame); grid.setContentsMargins(16, 12, 16, 12); grid.setHorizontalSpacing(16); grid.setVerticalSpacing(8)

        lbl_start = QLabel("Start"); _ss(lbl_start, "color: #FFFFFF; font-size: 13px;"); grid.addWidget(lbl_start, 0, 0)
        lbl_end = QLabel("End"); _ss(lbl_end, "color: #FFFFFF; font-size: 13px;"); grid.addWidget(lbl_end, 0, 1)

        self.start_input = QLineEdit("00:00:00"); self.start_input.setFixedSize(80, 28)
        self.start_input.editingFinished.connect(self._on_inputs_edited); grid.addWidget(self.start_input, 1, 0)

        self.end_input = QLineEdit("00:00:00"); self.end_input.setFixedSize(80, 28)
        self.end_input.editingFinished.connect(self._on_inputs_edited); grid.addWidget(self.end_input, 1, 1)

        mode_frame = QFrame(); mode_frame.setFixedSize(130, 28)
        _ss(mode_frame, "QFrame { background-color: #252525; border: 1px solid #333333; border-radius: 6px; }")
        m_layout = QHBoxLayout(mode_frame); m_layout.setContentsMargins(2, 2, 2, 2); m_layout.setSpacing(0)
        self.btn_mode_vid = QPushButton("Video"); self.btn_mode_aud = QPushButton("Audio")
        for b in (self.btn_mode_vid, self.btn_mode_aud):
            b.setFixedHeight(24); b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_mode_vid.clicked.connect(lambda: self._set_mode(False))
        self.btn_mode_aud.clicked.connect(lambda: self._set_mode(True))
        m_layout.addWidget(self.btn_mode_vid); m_layout.addWidget(self.btn_mode_aud)
        grid.addWidget(mode_frame, 0, 3)

        self.qual_combo = AnimatedComboBox(); self.qual_combo.setFixedSize(90, 28)
        self.qual_combo.currentIndexChanged.connect(self._update_est_size)
        grid.addWidget(self.qual_combo, 0, 4)

        self.est_size_lbl = QLabel("Est. size ~0 MB"); _ss(self.est_size_lbl, "color: #EEEEEE; font-size: 13px;")
        grid.addWidget(self.est_size_lbl, 0, 5)

        btn_layout = QHBoxLayout(); btn_layout.setSpacing(12)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedSize(90, 32); self.btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self.btn_cancel, f"QPushButton {{ background: transparent; border: 1px solid {TEAL_ACCENT}; color: #FFFFFF; border-radius: 16px; font-size: 14px; }}")
        self.btn_cancel.clicked.connect(self._show_initial_view)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_download = QPushButton("Download")
        self.btn_download.setFixedSize(100, 32); self.btn_download.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self.btn_download, f"QPushButton {{ background-color: {TEAL_ACCENT}; color: #000000; border-radius: 16px; font-size: 14px; font-weight: 500; border: none; }}")
        self.btn_download.clicked.connect(self._on_download)
        btn_layout.addWidget(self.btn_download)

        grid.addLayout(btn_layout, 1, 4, 1, 3)
        ed_layout.addWidget(dock_frame)
        self.layout.addWidget(self.editor_container)

    def _show_initial_view(self):
        if hasattr(self, 'player'):
            self.player.pause(); self.player.setSource(QUrl()); self.player.stop()
        if hasattr(self, 'loading_overlay'): self.loading_overlay.stop()
        self.preview_failed = False
        if hasattr(self, 'editor_container'):
            self.editor_container.hide(); self.search_container.show()
            self.title_lbl.show(); self.url_entry.show(); self.url_entry.clear()
            self._reset_inputs_style()

    def _show_initial_view_keep_text(self):
        if hasattr(self, 'player'):
            self.player.pause(); self.player.setSource(QUrl()); self.player.stop()
        if hasattr(self, 'loading_overlay'): self.loading_overlay.stop()
        self.preview_failed = False
        if hasattr(self, 'editor_container'):
            self.editor_container.hide(); self.search_container.show()
            self.title_lbl.show(); self.url_entry.show(); self._reset_inputs_style()

    def _on_processing_cancel(self):
        if self._proc_cancel_flag is not None: self._proc_cancel_flag[0] = True
        self._proc_run_id += 1
        self._show_initial_view_keep_text()
        self.proc_overlay.dismiss()

    def _on_trim_phase(self, run_id, key):
        if run_id == self._proc_run_id: self.proc_overlay.set_phase(key)

    def _process_link(self):
        url = self.url_entry.text().strip()
        if not url: return
        if self._proc_cancel_flag is not None: self._proc_cancel_flag[0] = True
        self._proc_run_id += 1; run_id = self._proc_run_id; cancelled = [False]
        self._proc_cancel_flag = cancelled
        host = (urlparse(url if "://" in url else "//" + url).netloc or url).lower()
        if host.startswith("www."): host = host[4:]
        self.proc_overlay.begin(host)
        def _cover():
            if cancelled[0] or run_id != self._proc_run_id: return
            self.title_lbl.hide(); self.url_entry.hide()
        QTimer.singleShot(300, _cover)
        threading.Thread(target=self._scrape_and_load, args=(url, run_id, cancelled), daemon=True).start()

    def _scrape_and_load(self, url, run_id, cancelled):
        ydl_mod = _get_yt_dlp()
        if ydl_mod is None:
            self.signals.error.emit(run_id, "yt-dlp library missing")
            return
        try:
            self.signals.phase.emit(run_id, "fetch")
            ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True, 'user_agent': DEFAULT_UA}
            with ydl_mod.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if cancelled[0]: return
            self.signals.phase.emit(run_id, "process")
            preview_url, preview_height, is_audio_only = select_preview_stream(info, url)
            info['_preview_stream'] = preview_url
            info['_preview_height'] = preview_height
            info['_is_audio_only'] = is_audio_only
            info['_url'] = url
            info['_run_id'] = run_id
            self.signals.phase.emit(run_id, "preview")
            thumb_url = info.get('thumbnail')
            if thumb_url:
                try:
                    req = urllib.request.Request(thumb_url, headers={'User-Agent': DEFAULT_UA})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        info['_thumb_data'] = response.read()
                except Exception:
                    pass
            info['_fav_path'] = _fetch_favicon_sync(url)
            if not cancelled[0]: self.signals.loaded.emit(info)
        except Exception as e:
            if not cancelled[0]: self.signals.error.emit(run_id, str(e))

    def _on_scrape_error(self, run_id, msg):
        if run_id != self._proc_run_id: return
        if self._proc_cancel_flag is not None and self._proc_cancel_flag[0]: return
        self.proc_overlay.fail(msg)

    def _on_metadata_loaded(self, info):
        if info.get('_run_id') != self._proc_run_id: return
        if self._proc_cancel_flag is not None and self._proc_cancel_flag[0]: return
        run_id = self._proc_run_id
        def _reveal():
            if run_id != self._proc_run_id: return
            self._reveal_trim_result(info)
            self.proc_overlay.dismiss()
        self.proc_overlay.finish(_reveal)

    def _reveal_trim_result(self, info):
        self.current_info = info; self.preview_failed = False; self.preview_error_lbl.hide()
        self.search_container.hide(); self.editor_container.show()
        title = info.get('title', 'Media Preview')
        channel = info.get('uploader') or info.get('channel') or 'Unknown'
        dur_sec = float(info.get('duration') or 1.0)
        self.duration = dur_sec; self.start_trim = 0.0; self.end_trim = self.duration
        self.range_slider.set_duration(self.duration)
        self.start_input.setText(format_time_str(0))
        self.end_input.setText(format_time_str(self.duration))
        self.time_lbl.setText(f"{format_time_str(0)} / {format_time_str(self.duration)}")
        self._reset_inputs_style()

        self.qual_combo.clear()
        formats = info.get('formats', [])
        video_formats = [f for f in formats if f.get('vcodec') not in ('none', None)]
        if video_formats:
            seen = set()
            for f in reversed(video_formats):
                h = f.get('height')
                if h and h not in seen:
                    seen.add(h); self.qual_combo.addItem(f"{h}p", f)
        if self.qual_combo.count() == 0: self.qual_combo.addItem("Best", None)

        if info.get('_is_audio_only', False):
            self.btn_mode_vid.setEnabled(False); self._set_mode(True)
        else:
            self.btn_mode_vid.setEnabled(True); self._set_mode(False)

        stream_url = info.get('_preview_stream')
        if stream_url:
            self.loading_overlay.start()
            self.player.setSource(QUrl(stream_url))
            self.player.play()
            self.btn_play.setIcon(self.icon_pause)
        else:
            self._on_player_error(QMediaPlayer.Error.ResourceError, "No stream url available")

    def _set_mode(self, is_audio):
        self.is_audio_mode = is_audio
        act = f"QPushButton {{ background-color: #383838; color: {TEAL_ACCENT}; font-size: 13px; font-weight: 500; border-radius: 4px; border: none; }}"
        inact = f"QPushButton {{ background-color: transparent; color: {TEXT_MUTED}; font-size: 13px; font-weight: 500; border-radius: 4px; border: none; }}"
        if is_audio:
            _ss(self.btn_mode_aud, act); _ss(self.btn_mode_vid, inact)
            self.video_widget.hide(); self.thumbnail_label.show()
        else:
            _ss(self.btn_mode_vid, act); _ss(self.btn_mode_aud, inact)
            self.video_widget.show(); self.thumbnail_label.hide()
        self._update_est_size()

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause(); self.btn_play.setIcon(self.icon_play)
        else:
            self.player.play(); self.btn_play.setIcon(self.icon_pause)

    def _seek_player(self, pos_sec):
        self.player.setPosition(int(pos_sec * 1000))

    def _on_slider_position_changed(self, sec):
        if self.range_slider._dragging:
            self.time_lbl.setText(f"{format_time_str(sec)} / {format_time_str(self.duration)}")

    def _on_player_position_changed(self, ms):
        if self.range_slider._dragging: return
        sec = ms / 1000.0
        self.range_slider.set_position(sec)
        self.time_lbl.setText(f"{format_time_str(sec)} / {format_time_str(self.duration)}")
        if sec >= self.end_trim:
            self.player.setPosition(int(self.start_trim * 1000))

    def _on_player_duration_changed(self, ms):
        if ms > 0:
            self.duration = ms / 1000.0
            self.range_slider.set_duration(self.duration)

    def _on_trim_range_changed(self, start, end):
        self.start_trim = start; self.end_trim = end
        self.start_input.setText(format_time_str(start))
        self.end_input.setText(format_time_str(end))
        self._reset_inputs_style(); self._update_est_size()

    def _on_inputs_edited(self):
        s = parse_time_str(self.start_input.text().strip())
        e = parse_time_str(self.end_input.text().strip())
        if s < 0 or e < 0 or s >= e or s >= self.duration or e > self.duration:
            self._mark_inputs_invalid(); return
        self.start_trim = s; self.end_trim = e
        self.range_slider.start_time = s; self.range_slider.end_time = e; self.range_slider.update()
        self._reset_inputs_style(); self._update_est_size()

    def _update_est_size(self):
        pass

    def _on_download(self):
        s = parse_time_str(self.start_input.text().strip())
        e = parse_time_str(self.end_input.text().strip())
        if s < 0 or e < 0 or s >= e:
            self._mark_inputs_invalid(); return
        if not self.main_win: return
        url = self.current_info.get('_url')
        title = self.current_info.get('title', 'Trimmed Media')
        selected_fmt = self.qual_combo.currentData()
        selected_fid = selected_fmt.get('format_id') if isinstance(selected_fmt, dict) else selected_fmt
        item = self.main_win.DownloadItem(
            url=url, title=f"[Trimmed] {title}", channel=self.current_info.get('uploader', 'YouTube'),
            thumb_path=None, out_dir=self._download_dir(), is_audio=self.is_audio_mode,
            selected_fid=selected_fid, duration_str=format_time_str(e - s), site_name=_site_name(url),
            start_time=s, end_time=e
        )
        self.main_win._dl_items.append(item)
        self.main_win._start_download(item)
        self.main_win._show_tab(2)
        QTimer.singleShot(50, self._show_initial_view)