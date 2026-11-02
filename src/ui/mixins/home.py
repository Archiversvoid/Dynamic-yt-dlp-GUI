"""The Home tab: link box, processing flow, media card."""
import hashlib
import os
import theme
import threading
import urllib.request
from urllib.parse import urlparse
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)
from theme import ss as _ss
from src.core.downloader import _fetch_favicon_sync, _get_yt_dlp, _is_audio_only_url, _site_name, fetch_formats, parse_kbps, strip_ansi
from src.core.models import DownloadItem
from src.paths import default_download_dir, repo_root, thumb_dir
from src.ui.components.combo import AnimatedComboBox
from src.ui.components.overlay import ProcessingOverlay
from src.ui.components.skeleton import ShimmerBox
from src.ui.helpers import get_rounded_pixmap, jiggle_widget
from src.ui.styles import CARD_INNER_BG, ERROR_RED, INPUT_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED


class HomeMixin:
    """The Home tab: link box, processing flow, media card."""

    def _build_home_tab(self):
        layout = QVBoxLayout(self.tab_home)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.home_center = QWidget()
        hc_layout = QVBoxLayout(self.home_center)
        hc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_lbl = QLabel("DYNAMIC")
        _ss(self.title_lbl, f"color: {TEXT_MAIN}; font-size: 68px; font-weight: 300;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hc_layout.addWidget(self.title_lbl)
        hc_layout.addSpacing(20)
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Enter link...")
        self.url_entry.setFixedSize(600, 54)
        _ss(self.url_entry, f"QLineEdit {{ background-color: {INPUT_BG}; color: {TEXT_MAIN}; border-radius: 27px; padding: 0 20px; font-size: 18px; border: none; }}")
        self.url_entry.returnPressed.connect(lambda: self._process_link(self.url_entry.text().strip()))
        hc_layout.addWidget(self.url_entry, alignment=Qt.AlignmentFlag.AlignCenter)
        self.home_slot = QWidget()
        self.home_slot_layout = QVBoxLayout(self.home_slot)
        hc_layout.addWidget(self.home_slot)
        layout.addWidget(self.home_center)

        self._proc_run_id, self._proc_cancel_flag = 0, None
        self.proc_overlay = ProcessingOverlay(self.tab_home)
        self.proc_overlay.cancel_requested.connect(self._on_processing_cancel)
        self.proc_overlay.retry_requested.connect(self._on_processing_cancel)

    def _clear_home_slot(self):
        while self.home_slot_layout.count():
            item = self.home_slot_layout.takeAt(0)
            w = item.widget()
            if w:
                for sb in w.findChildren(ShimmerBox):
                    ShimmerBox.unregister(sb)
                w.deleteLater()

    def _warm_up_ytdlp(self):
        """Import yt-dlp (about 1,700 extractor modules - several seconds on a cold start) in the
        background shortly after launch, so the first link you paste doesn't pay for it."""
        threading.Thread(target=_get_yt_dlp, daemon=True).start()

    def _process_link(self, url, start_time=None, end_time=None):
        if not url: return
        self._last_url = url

        # Supersede whatever run may still be in flight.
        if self._proc_cancel_flag is not None: self._proc_cancel_flag[0] = True
        self._proc_run_id += 1
        run_id = self._proc_run_id
        cancelled = [False]
        self._proc_cancel_flag = cancelled

        host = (urlparse(url if "://" in url else "//" + url).netloc or url).lower()
        if host.startswith("www."): host = host[4:]
        self.proc_overlay.begin(host)

        # Once the overlay has faded in and fully covers the home screen,
        # tuck the title/input away underneath it (same end state as before).
        def _cover():
            if cancelled[0] or run_id != self._proc_run_id: return
            self._clear_home_slot(); self.title_lbl.hide(); self.url_entry.hide()
        QTimer.singleShot(300, _cover)

        def phase(key):
            if not cancelled[0]: self.signals.home_phase.emit(run_id, key)

        def _worker():
            phase("fetch")
            res = fetch_formats(url)
            if cancelled[0]: return
            if not res.get("ok"):
                self.signals.home_error.emit(res.get("error", "Unknown error"))
                return

            phase("process")
            force_audio = _is_audio_only_url(url) or res.get("audio_only", False)
            raw_dur = res.get("duration")
            if isinstance(raw_dur, str) and ":" in raw_dur:
                parts = raw_dur.split(":")
                try:
                    if len(parts) == 3: raw_dur = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
                    elif len(parts) == 2: raw_dur = int(parts[0])*60 + int(parts[1])
                except Exception: pass
            try: final_dur = float(raw_dur) if raw_dur else 0
            except (ValueError, TypeError): final_dur = 0
            
            info = {
                "title": res.get("title", "Unknown Title"), "uploader": res.get("channel") or res.get("uploader", "Unknown"), 
                "duration": final_dur, "_video_formats": [] if force_audio else res.get("video_formats",[]),
                "_audio_formats": res.get("audio_formats",[]), "_audio_only": force_audio,
                "thumbnail": res.get("thumbnail"), "is_live": res.get("is_live", False),
                "_run_id": run_id
            }
            
            phase("preview")
            thumb_path = None
            if info.get("thumbnail"):
                thumb_url = info["thumbnail"]
                if thumb_url.startswith("//"): thumb_url = "https:" + thumb_url
                try:
                    req = urllib.request.Request(thumb_url, headers={"User-Agent":"Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=8) as r: data = r.read()
                    t_hash = hashlib.md5(thumb_url.encode()).hexdigest()
                    thumb_path = str(thumb_dir / f"{t_hash}.png")
                    with open(thumb_path, 'wb') as f: f.write(data)
                except Exception: pass
            
            fav_path = _fetch_favicon_sync(url)
            if not cancelled[0]: self.signals.home_result.emit(info, url, thumb_path, fav_path, start_time, end_time)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_home_phase(self, run_id, key):
        if run_id == self._proc_run_id: self.proc_overlay.set_phase(key)

    def _on_home_result(self, info, url, thumb_path, fav_path, start_time, end_time):
        if info.get("_run_id") != self._proc_run_id: return
        if self._proc_cancel_flag is not None and self._proc_cancel_flag[0]: return
        run_id = self._proc_run_id
        def _reveal():
            if run_id != self._proc_run_id: return
            self.title_lbl.hide(); self.url_entry.hide()
            # Show the skeleton first and let it actually paint (the
            # profile card's thumbnail decode/scale + widget build is
            # real work, not free) before doing that work, so there's a
            # visible loading state instead of a dead pause.
            self._clear_home_slot()
            self.home_slot_layout.addWidget(self._build_home_skeleton_card(), alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            self.proc_overlay.dismiss()
            # 30ms was long enough to dodge the "frozen" case, but for a
            # fast fetch it meant the skeleton was on screen for less
            # than a couple of paint frames - technically shown, but not
            # actually perceivable. Give it a real minimum dwell so it
            # always reads as an intentional loading state.
            QTimer.singleShot(400, lambda: self._finish_home_reveal(run_id, info, url, thumb_path, fav_path, start_time, end_time))
        self.proc_overlay.finish(_reveal)

    def _finish_home_reveal(self, run_id, info, url, thumb_path, fav_path, start_time, end_time):
        if run_id != self._proc_run_id: return
        self._render_media_card_ui(info, url, thumb_path, fav_path, start_time, end_time)
        dur_s = round(self.proc_overlay._clock.elapsed() / 1000.0)
        color = theme.map_hex(ERROR_RED if dur_s >= 60 else TEXT_MAIN, "text")
        check_pix = self._icons.get("check", QIcon()).pixmap(22, 22)
        self.toast_mgr.show_toast(
            f'Finished in <span style="color: {color};">{dur_s}s</span>',
            icon_pixmap=check_pix, rich_text=True
        )

    def _on_home_error(self, msg):
        if self._proc_cancel_flag is not None and self._proc_cancel_flag[0]: return
        # The overlay's own failed state is now the complete error UI (it
        # has its own Try Again / Error Log buttons) - it just stays on
        # screen until the user acts, instead of auto-dismissing to a
        # separate fallback screen underneath.
        self.proc_overlay.fail(strip_ansi(msg))

    def _on_processing_cancel(self):
        if self._proc_cancel_flag is not None: self._proc_cancel_flag[0] = True
        self._proc_run_id += 1
        self.title_lbl.show(); self.url_entry.show(); self._clear_home_slot()
        self.proc_overlay.dismiss()

    def _build_home_skeleton_card(self):
        """Mirrors _render_media_card_ui's real layout exactly (same
        widths/heights/radii/spacing pulled straight from that method) so
        the skeleton never has to guess at the card's shape."""
        outer = QFrame()
        _ss(outer, "QFrame { border: none; }")
        outer.setMaximumWidth(720)
        o_layout = QVBoxLayout(outer)
        o_layout.setContentsMargins(0, 0, 0, 0)
        o_layout.setSpacing(18)

        o_layout.addWidget(ShimmerBox(720, 405, radius=14), alignment=Qt.AlignmentFlag.AlignCenter)
        o_layout.addWidget(ShimmerBox(460, 30, radius=6))

        meta_row = QHBoxLayout(); meta_row.setSpacing(15)
        meta_row.addWidget(ShimmerBox(90, 18, radius=4))
        meta_row.addWidget(ShimmerBox(60, 18, radius=4))
        meta_row.addWidget(ShimmerBox(110, 18, radius=4))
        meta_row.addStretch()
        o_layout.addLayout(meta_row)
        o_layout.addSpacing(5)

        btn_row = QHBoxLayout(); btn_row.setSpacing(15)
        btn_row.addWidget(ShimmerBox(148, 38, radius=8))   # seg_frame (Video/Audio)
        btn_row.addWidget(ShimmerBox(160, 38, radius=6))   # quality combo (matches its real min-width)
        btn_row.addStretch()
        btn_row.addWidget(ShimmerBox(100, 38, radius=19))  # cancel (matches its real min-width)
        btn_row.addWidget(ShimmerBox(120, 38, radius=19))  # download (matches its real min-width)
        o_layout.addLayout(btn_row)

        return outer

    def _render_media_card_ui(self, info, url, thumb_path, fav_path, start_time=None, end_time=None):
        self._clear_home_slot()
        title_text = info.get("title", "Unknown Title")
        channel_text = info.get("uploader") or info.get("channel", "Unknown")
        dur_sec, audio_only, thumb_url, is_live = info.get("duration", 0), info.get("_audio_only", False), info.get("thumbnail"), info.get("is_live", False)

        if is_live: dur_str = "LIVE"
        elif dur_sec and float(dur_sec) > 0:
            t = int(float(dur_sec)); m, s = divmod(t, 60); h, m = divmod(m, 60)
            dur_str = f"{h}:{m:02d}:{s:02d} mins" if h else f"{m}:{s:02d} mins"
        else: dur_str = "0:00 mins"

        format_map, vf, af, video_q, audio_q = {}, info.get("_video_formats", []), info.get("_audio_formats", []), [], []
        
        for f in vf:
            label = f.get("label", "Unknown")
            if label == "Best": label = "Best quality"
            elif label.startswith("Best "): label = label.replace("Best ", "Best quality ", 1)
            
            if not any(x in label for x in ["MB", "KB", "GB"]):
                fs = f.get("filesize") or f.get("filesize_approx")
                if not fs and dur_sec and float(dur_sec) > 0:
                    kbps = 1800
                    if "4K" in label or "2160" in label: kbps = 8000
                    elif "1440" in label: kbps = 4000
                    elif "1080" in label: kbps = 1800
                    elif "720" in label: kbps = 900
                    elif "480" in label: kbps = 500
                    elif "360" in label: kbps = 300
                    elif "Best quality" in label: kbps = 2000
                    fs = ((kbps + 128) * 1000 * float(dur_sec)) / 8
                if fs:
                    size_str = f"~{max(1, round(fs / 1024))} KB" if fs < 1024 * 1024 else f"~{round(fs / (1024 * 1024), 1)} MB"
                    label = f"{label.split('—')[0].strip()} — {size_str}" if "—" in label else f"{label} — {size_str}"
            video_q.append(label); format_map[label] = f.get("format_id")
            
        for f in af:
            label = f.get("label", "Unknown")
            if not any(x in label for x in ["MB", "KB", "GB"]):
                fs = f.get("filesize") or f.get("filesize_approx")
                if not fs and dur_sec and float(dur_sec) > 0:
                    abr = 128
                    if "320" in label: abr = 320
                    elif "256" in label: abr = 256
                    elif "192" in label: abr = 192
                    elif "128" in label: abr = 128
                    elif "96" in label: abr = 96
                    elif "64" in label: abr = 64
                    fs = (abr * 1000 * float(dur_sec)) / 8
                if fs:
                    size_str = f"~{max(1, round(fs / 1024))} KB" if fs < 1024 * 1024 else f"~{round(fs / (1024 * 1024), 1)} MB"
                    label = f"{label.split('—')[0].strip()} — {size_str}" if "—" in label else f"{label} — {size_str}"
            audio_q.append(label); format_map[label] = f.get("format_id")
            
        if not audio_q: audio_q = [f"MP3 {br}kbps" for br in (320, 256, 192, 128, 96, 64)]
        site = _site_name(url)

        outer = QFrame()
        _ss(outer, "QFrame { border: none; }")
        outer.setMaximumWidth(720)
        
        o_layout = QVBoxLayout(outer)
        o_layout.setContentsMargins(0, 0, 0, 0)
        o_layout.setSpacing(18)

        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(720, 405) 
        _ss(thumb_lbl, f"background-color: {CARD_INNER_BG}; border-radius: 8px;")
        if thumb_path and os.path.exists(thumb_path):
            pix = QPixmap(thumb_path).scaled(720, 405, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            thumb_lbl.setPixmap(get_rounded_pixmap(pix, 14))
        o_layout.addWidget(thumb_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        t_lbl = QLabel(title_text)
        _ss(t_lbl, f"color: {TEXT_MAIN}; font-size: 34px; font-weight: normal; border: none;")
        t_lbl.setWordWrap(True)
        o_layout.addWidget(t_lbl)

        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(15)
        
        c_lbl = QLabel(channel_text)
        _ss(c_lbl, f"color: {TEXT_MAIN}; font-size: 16px; border: none;")
        meta_layout.addWidget(c_lbl)

        d_lbl = QLabel(dur_str)
        _ss(d_lbl, f"color: {'#FF5555' if is_live else TEXT_MAIN}; font-size: 16px; font-weight: {'bold' if is_live else 'normal'}; border: none;")
        meta_layout.addWidget(d_lbl)
        
        site_layout = QHBoxLayout()
        site_layout.setSpacing(6)
        if fav_path and os.path.exists(fav_path):
            fav_lbl = QLabel()
            _ss(fav_lbl, "border: none; background: transparent;")
            fav_lbl.setPixmap(QPixmap(fav_path).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            site_layout.addWidget(fav_lbl)
        else:
            site_icon = QLabel("▶" if "Youtube" in site else "🌐")
            _ss(site_icon, f"color: {'#FF0000' if 'Youtube' in site else TEAL_ACCENT}; font-size: 18px; border: none;")
            site_layout.addWidget(site_icon)
            
        site_lbl = QLabel(site)
        site_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(site_lbl, f"color: {TEXT_MAIN}; font-size: 16px; border: none;")
        site_lbl.mousePressEvent = lambda e: self._open_qurl(QUrl(url))
        
        site_layout.addWidget(site_lbl)
        meta_layout.addLayout(site_layout)
        meta_layout.addStretch()
        
        o_layout.addLayout(meta_layout)
        o_layout.addSpacing(5)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        seg_frame = QFrame()
        _ss(seg_frame, "QFrame { background-color: #222222; border-radius: 8px; }")
        seg_frame.setFixedHeight(38)
        seg_layout = QHBoxLayout(seg_frame)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(2)
        
        bv = QPushButton("Video")
        bv.setFixedHeight(30)
        bv.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        ba = QPushButton("Audio")
        ba.setFixedHeight(30)
        ba.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        def update_btn_styles(mode):
            act = f"QPushButton {{ background-color: #333333; color: {TEAL_ACCENT}; font-size: 14px; border-radius: 6px; border: none; padding: 0 15px; }}"
            inact = f"QPushButton {{ background-color: transparent; color: {TEXT_MUTED}; font-size: 14px; border-radius: 6px; border: none; padding: 0 15px; }} QPushButton:hover {{ background-color: #2A2A2A; }}"
            if mode == "Video": _ss(bv, act); _ss(ba, inact)
            else: _ss(bv, inact); _ss(ba, act)
        
        if audio_only:
            bv.setDisabled(True)
            _ss(bv, "QPushButton { background-color: transparent; color: #444; font-size: 14px; border-radius: 6px; border: none; padding: 0 15px; }")
            _ss(ba, f"QPushButton {{ background-color: #333333; color: {TEAL_ACCENT}; font-size: 14px; border-radius: 6px; border: none; padding: 0 15px; }}")
        else: update_btn_styles("Video")
        
        seg_layout.addWidget(bv)
        seg_layout.addWidget(ba)
        btn_layout.addWidget(seg_frame)

        qm = AnimatedComboBox()
        qm.setFixedHeight(38)
        qm.setMinimumWidth(160)
        _ss(qm, f"""
            QComboBox {{ 
                background-color: #1A1A1A; 
                color: #FFFFFF; 
                font-size: 14px; 
                border-radius: 6px; 
                padding: 5px 12px; 
                border: 1px solid #2A2A2A; 
            }}
            QComboBox::drop-down {{ 
                border: none; 
                width: 0px; 
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QComboBox QAbstractItemView {{ 
                background-color: #181818; 
                color: #FFFFFF; 
                selection-background-color: #B5B5B5; 
                selection-color: #000000; 
                border: 1px solid #FFFFFF; 
                border-radius: 4px; 
                outline: none; 
                padding: 2px 0px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 26px;
                padding-left: 10px;
                color: #FFFFFF;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #B5B5B5;
                color: #000000;
            }}
        """)
        qm.addItems(audio_q if audio_only else (video_q or ["Best quality"]))
        btn_layout.addWidget(qm)

        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setMinimumWidth(100)
        btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(btn_cancel, f"QPushButton {{ background-color: transparent; border: 1px solid #777777; color: {TEXT_MAIN}; font-size: 14px; border-radius: 19px; }} QPushButton:hover {{ background-color: #222222; }}")
        btn_layout.addWidget(btn_cancel)

        btn_dl = QPushButton("Download")
        btn_dl.setFixedHeight(38)
        btn_dl.setMinimumWidth(120)
        btn_dl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if is_live: 
            _ss(btn_dl, "QPushButton { background-color: #222222; color: #666666; font-size: 14px; font-weight: bold; border-radius: 19px; border: 1px solid #333333; } QPushButton:hover { background-color: #262626; }")
        else: 
            _ss(btn_dl, f"QPushButton {{ background-color: {TEAL_ACCENT}; color: #000000; font-size: 14px; font-weight: bold; border-radius: 19px; border: none; }} QPushButton:hover {{ background-color: #00A892; }}")
        btn_layout.addWidget(btn_dl)

        o_layout.addLayout(btn_layout)

        current_mode = ["Audio" if audio_only else "Video"]
        def set_mode(mode):
            if audio_only and mode == "Video": return
            current_mode[0] = mode; qm.clear()
            if mode == "Video": update_btn_styles("Video"); qm.addItems(video_q or ["Best quality"])
            else: update_btn_styles("Audio"); qm.addItems(audio_q or ["Best Audio"])
            
        bv.clicked.connect(lambda: set_mode("Video"))
        ba.clicked.connect(lambda: set_mode("Audio"))

        def _cancel(): self.title_lbl.show(); self.url_entry.show(); self.url_entry.clear(); self._clear_home_slot()
        btn_cancel.clicked.connect(_cancel)
        
        def _on_download():
            if is_live: jiggle_widget(btn_dl); self.toast_mgr.show_toast("Can't download live streams"); return
            item = DownloadItem(
                url=url, title=title_text, channel=channel_text, thumb_path=thumb_path, 
                out_dir=self.settings.get("download_dir") or default_download_dir(), is_audio=(current_mode[0] == "Audio"), 
                selected_fid=format_map.get(qm.currentText()), duration_str=dur_str, 
                site_name=site, thumb_url=thumb_url, fav_path=fav_path,
                start_time=start_time, end_time=end_time,
                audio_bitrate=(parse_kbps(qm.currentText()) if current_mode[0] == "Audio" else None)
            )
            self._dl_items.append(item)
            self._dl_item_added(item)
            self._start_download(item); self._show_tab(2); _cancel()
            
        btn_dl.clicked.connect(_on_download)
        
        self.home_slot_layout.addWidget(outer, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
