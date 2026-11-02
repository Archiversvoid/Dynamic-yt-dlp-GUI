"""TrimLoad tab: fetching a link's info and showing the result."""
import os
import theme
import threading
import urllib.request
from urllib.parse import urlparse
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCursor, QIcon, QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from theme import ss as _ss
from src.core.downloader import _fetch_favicon_sync, _get_yt_dlp, _site_name, DEFAULT_UA, friendly_error
from src.paths import repo_root
from src.ui.styles import ERROR_RED, TEAL_ACCENT, TEXT_MAIN
from src.ui.trim.helpers import (
    audio_bitrate_items, format_time_str, is_live_info, live_message, select_preview_stream, video_quality_items)


class TrimProcessingMixin:
    """Fetching a link's info and showing the result."""

    def _process_link(self):
        url = self.url_entry.text().strip()
        if not url: return

        if self._proc_cancel_flag is not None: self._proc_cancel_flag[0] = True
        self._proc_run_id += 1
        run_id = self._proc_run_id
        cancelled = [False]
        self._proc_cancel_flag = cancelled

        host = (urlparse(url if "://" in url else "//" + url).netloc or url).lower()
        if host.startswith("www."): host = host[4:]
        self.proc_overlay.begin(host)

        def _cover():
            if cancelled[0] or run_id != self._proc_run_id: return
            self.title_lbl.hide(); self.url_entry.hide(); self._clear_processing_slot()
        QTimer.singleShot(300, _cover)

        threading.Thread(target=self._scrape_and_load, args=(url, run_id, cancelled), daemon=True).start()

    def _scrape_and_load(self, url, run_id, cancelled):
        ydl_mod = _get_yt_dlp()
        if ydl_mod is None:
            self.signals.error.emit(run_id, "yt-dlp library missing")
            return

        try:
            self.signals.phase.emit(run_id, "fetch")
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'noplaylist': True,
                'user_agent': DEFAULT_UA
            }

            if "music.youtube.com" in url:
                ydl_opts['extractor_args'] = {'youtube': ['player_client=tv,web_safari']}
                ydl_opts['http_headers'] = {'Accept-Language': 'en-US,en;q=0.9'}
            elif "youtube.com" in url or "youtu.be" in url:
                ydl_opts['extractor_args'] = {'youtube': ['player_client=tv,web_safari']}
                ydl_opts['http_headers'] = {'Accept-Language': 'en-US,en;q=0.9'}

            with ydl_mod.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if cancelled[0]: return
            if not info:
                self.signals.error.emit(run_id, "Could not fetch media info.")
                return
            if is_live_info(info):
                # A live stream has no fixed length and nothing to trim, and handing its endless stream
                # to the preview player is what can hang or crash it. Stop here, before a stream is
                # chosen or the player is touched.
                self.signals.error.emit(run_id, live_message(info))
                return

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
            if not cancelled[0]: self.signals.error.emit(run_id, friendly_error(e)[:200])

    def _on_scrape_error(self, run_id, msg):
        if run_id != self._proc_run_id: return
        if self._proc_cancel_flag is not None and self._proc_cancel_flag[0]: return
        self.proc_overlay.fail(msg)

    def _on_metadata_loaded(self, info):
        if info.get('_run_id') != self._proc_run_id: return
        if self._proc_cancel_flag is not None and self._proc_cancel_flag[0]: return
        if is_live_info(info):                      # second line of defence; the fetch already refuses live streams
            self._on_scrape_error(info.get('_run_id'), live_message(info))
            return
        run_id = self._proc_run_id
        def _reveal():
            if run_id != self._proc_run_id: return
            self._reveal_trim_result(info)
            self.proc_overlay.dismiss()
        self.proc_overlay.finish(_reveal)

    def _reveal_trim_result(self, info):
        self.current_info = info
        self.preview_failed = False
        self.preview_error_lbl.hide()
        
        self.search_container.hide()
        self.editor_container.show()

        title = info.get('title', 'Media Preview')
        channel = info.get('uploader') or info.get('channel') or info.get('uploader_id') or 'Unknown'
        
        dur_sec = float(info.get('duration') or 1.0)
        if dur_sec > 0:
            t = int(dur_sec)
            m, s = divmod(t, 60)
            h, m = divmod(m, 60)
            dur_str = f"{h}:{m:02d}:{s:02d} mins" if h else f"{m}:{s:02d} mins"
        else:
            dur_str = "0:00 mins"

        url = info.get('_url', '')
        site = _site_name(url)

        self.meta_title_lbl.setText(title)
        self.meta_channel_lbl.setText(channel)
        self.meta_dur_lbl.setText(dur_str)
        self.meta_site_lbl.setText(site)
        self.meta_site_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.meta_site_icon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        fav_path = info.get('_fav_path')
        if fav_path and os.path.exists(fav_path):
            self.meta_site_icon.clear()
            pix = QPixmap(fav_path).scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.meta_site_icon.setPixmap(pix)
            _ss(self.meta_site_icon, "border: none; background: transparent;")
        else:
            if "Youtube" in site or "YouTube" in site:
                self.meta_site_icon.setText("▶")
                _ss(self.meta_site_icon, "color: #FF0000; font-size: 14px; border: none;")
            else:
                self.meta_site_icon.setText("🌐")
                _ss(self.meta_site_icon, f"color: {TEAL_ACCENT}; font-size: 14px; border: none;")

        if '_thumb_data' in info:
            pixmap = QPixmap()
            pixmap.loadFromData(info['_thumb_data'])
            self.thumbnail_label.setPixmap(pixmap)
        else:
            self.thumbnail_label.setPixmap(QPixmap())

        self.duration = dur_sec
        self.start_trim = 0.0
        self.end_trim = self.duration

        self.range_slider.set_duration(self.duration)
        self.start_input.setText(format_time_str(0))
        self.end_input.setText(format_time_str(self.duration))
        self.time_lbl.setText(f"{format_time_str(0)} / {format_time_str(self.duration)}")
        self._reset_inputs_style()

        # One list per mode - video resolutions, and MP3 bitrates for audio. _set_mode fills the
        # combo from the right one (see _fill_quality_combo).
        self._video_items = video_quality_items(info)
        self._audio_items = audio_bitrate_items(info)
        self._qual_memory = {"video": 0, "audio": 0}
        self._qual_mode = None
        self.qual_combo.clear()

        is_pure_audio = info.get('_is_audio_only', False)

        if is_pure_audio:
            self.btn_mode_vid.setEnabled(False)
            self._set_mode(True)
        else:
            self.btn_mode_vid.setEnabled(True)
            self._set_mode(False)

        stream_url = info.get('_preview_stream')
        if stream_url:
            self.loading_overlay.start()
            self.player.setSource(QUrl(stream_url))
            self.player.play()
            self.btn_play.setIcon(self.icon_pause)
        else:
            self._on_player_error(QMediaPlayer.Error.ResourceError, "No stream url available")

        dur_s = round(self.proc_overlay._clock.elapsed() / 1000.0)
        color = theme.map_hex(ERROR_RED if dur_s >= 60 else TEXT_MAIN, "text")
        check_pix = QIcon(str(repo_root / "icons" / "check.png")).pixmap(22, 22)
        self._show_toast(
            f'Finished in <span style="color: {color};">{dur_s}s</span>',
            icon_pixmap=check_pix, rich_text=True
        )
