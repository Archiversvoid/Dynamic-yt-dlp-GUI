"""Small shared UI helpers (rounded pixmaps, thumbnail cache, jiggle)."""
import hashlib
import os
from PySide6.QtCore import QPoint, QPropertyAnimation, QSequentialAnimationGroup, QSize, Qt
from PySide6.QtGui import QImageReader, QPainter, QPainterPath, QPixmap
from src.paths import cache_dir


def _decode_for_card(path):
    """Decode a thumbnail at about 2x the card size instead of full size. JPEG - what
    thumbnails nearly always are, whatever the file extension says - can be decoded at
    reduced size directly, several times faster than decoding every pixel and scaling
    afterwards. Falls back to a plain load for anything unusual."""
    try:
        r = QImageReader(path)
        sz = r.size()
        if sz.isValid() and sz.width() > 0 and sz.height() > 0:
            k = max(240 / sz.width(), 135 / sz.height()) * 2
            if k < 1:
                r.setScaledSize(QSize(max(1, round(sz.width() * k)), max(1, round(sz.height() * k))))
            img = r.read()
            if not img.isNull():
                return QPixmap.fromImage(img)
    except Exception:
        pass
    return QPixmap(path)


def _card_thumb_pixmap(path):
    """The 240x135 rounded thumbnail for a download card. Decoding + smooth-scaling a
    full-size thumbnail costs tens of ms per card; with a few dozen downloads that
    stalled the Downloads tab on first open. The finished result is cached on disk
    (keyed by file path + mtime + size), so it is only ever computed once."""
    cached = None
    try:
        st = os.stat(path)
        key = hashlib.md5(("%s|%d|%d" % (path, st.st_mtime_ns, st.st_size)).encode("utf-8")).hexdigest()
        cached = cache_dir / "dl_thumbs" / (key + ".png")
        if cached.exists():
            pm = QPixmap(str(cached))
            if not pm.isNull():
                return pm
    except OSError:
        pass
    pix = _decode_for_card(path).scaled(240, 135, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    pm = get_rounded_pixmap(pix, 14)
    if cached is not None and not pm.isNull():
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            pm.save(str(cached), "PNG")
        except Exception:
            pass
    return pm


def get_rounded_pixmap(pixmap, radius):
    if pixmap.isNull(): return pixmap
    rounded = QPixmap(pixmap.size())
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded


def jiggle_widget(widget, offsets=(-12, 12, -8, 8, -4, 4, -2, 2, 0)):
    if hasattr(widget, "_jiggle_anim") and widget._jiggle_anim.state() == QSequentialAnimationGroup.State.Running: return
    orig_pos = widget.pos()
    group = QSequentialAnimationGroup(widget)
    for offset in offsets:
        anim = QPropertyAnimation(widget, b"pos", widget)
        anim.setDuration(35)
        anim.setStartValue(widget.pos())
        anim.setEndValue(orig_pos + QPoint(offset, 0))
        group.addAnimation(anim)
    widget._jiggle_anim = group
    group.start()
