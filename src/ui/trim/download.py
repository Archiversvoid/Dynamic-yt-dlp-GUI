"""TrimLoad tab: start/end inputs, size estimate and starting the trimmed download."""
import hashlib
import os
from PySide6.QtCore import QTimer
from src.core.downloader import _site_name
from src.paths import repo_root, thumb_dir
from src.ui.trim.helpers import format_time_str, is_live_info, jiggle_widget, parse_time_str


class TrimDownloadMixin:
    """Start/end inputs, size estimate and starting the trimmed download."""

    def _download_dir(self):
        """Where trims are saved: the folder chosen in Settings > Downloads
        (shared with Home downloads), falling back to ./downloads."""
        try:
            from src.paths import default_download_dir
            default = default_download_dir()
        except Exception:
            default = str(repo_root / "downloads")
        settings = getattr(self.main_win, "settings", None)
        if isinstance(settings, dict):
            return settings.get("download_dir") or default
        return default

    def _on_inputs_edited(self):
        s_text = self.start_input.text().strip()
        e_text = self.end_input.text().strip()
        s = parse_time_str(s_text)
        e = parse_time_str(e_text)
        
        if s < 0 or e < 0:
            self._mark_inputs_invalid()
            self._show_toast_error("Invalid time format")
            return

        if s >= e:
            self._mark_inputs_invalid()
            self._show_toast_error("Start time must be before end time")
            return

        if s >= self.duration or e > self.duration:
            self._mark_inputs_invalid()
            self._show_toast_error("Trim range exceeds media duration")
            return

        self.start_trim = s
        self.end_trim = e

        self.start_input.setText(format_time_str(s))
        self.end_input.setText(format_time_str(e))

        self.range_slider.start_time = s
        self.range_slider.end_time = e
        self.range_slider.update()

        self._reset_inputs_style()
        self._update_est_size()

    def _update_est_size(self):
        if not self.current_info:
            return

        duration_selected = max(0.1, self.end_trim - self.start_trim)
        total_duration = max(1.0, float(self.current_info.get('duration') or self.duration or 1.0))

        fmt = self.qual_combo.currentData()
        est_bytes = 0

        if self.is_audio_mode:
            formats = self.current_info.get('formats') or []
            audio_fmts = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
            best_audio = audio_fmts[0] if audio_fmts else None
            
            if best_audio and (best_audio.get('filesize') or best_audio.get('filesize_approx')):
                full_sz = best_audio.get('filesize') or best_audio.get('filesize_approx')
                est_bytes = (full_sz / total_duration) * duration_selected
            elif best_audio and best_audio.get('abr'):
                abr = best_audio.get('abr')
                est_bytes = (abr * 1000 / 8) * duration_selected
            else:
                est_bytes = (160 * 1000 / 8) * duration_selected
        else:
            if isinstance(fmt, dict):
                full_sz = fmt.get('filesize') or fmt.get('filesize_approx')
                tbr = fmt.get('tbr') or ((fmt.get('vbr') or 0) + (fmt.get('abr') or 0))
                
                if full_sz:
                    est_bytes = (full_sz / total_duration) * duration_selected
                    if fmt.get('acodec') == 'none':
                        est_bytes += (128 * 1000 / 8) * duration_selected
                elif tbr:
                    est_bytes = (tbr * 1000 / 8) * duration_selected
                    if fmt.get('acodec') == 'none':
                        est_bytes += (128 * 1000 / 8) * duration_selected

            if est_bytes <= 0:
                qual_text = self.qual_combo.currentText()
                if "2160" in qual_text or "4k" in qual_text.lower(): bitrate_kbps = 15000
                elif "1440" in qual_text: bitrate_kbps = 9000
                elif "1080" in qual_text: bitrate_kbps = 4500
                elif "720" in qual_text: bitrate_kbps = 2500
                elif "480" in qual_text: bitrate_kbps = 1200
                elif "360" in qual_text: bitrate_kbps = 750
                else: bitrate_kbps = 2500
                
                est_bytes = (bitrate_kbps * 1000 / 8) * duration_selected

        if self.is_audio_mode and isinstance(fmt, dict) and fmt.get('kbps'):
            # the output is an MP3 encoded at the chosen bitrate, so its size is bitrate x duration
            est_bytes = (fmt['kbps'] * 1000 / 8) * duration_selected

        if est_bytes >= 1024 * 1024 * 1024:
            size_gb = est_bytes / (1024 * 1024 * 1024)
            self.est_size_lbl.setText(f"Est. size ~{size_gb:.2f} GB")
        else:
            size_mb = est_bytes / (1024 * 1024)
            self.est_size_lbl.setText(f"Est. size ~{size_mb:.1f} MB")

    def _on_download(self):
        if self.current_info and is_live_info(self.current_info):
            jiggle_widget(self.btn_download)
            self._show_toast_error("Can't download live streams")
            return
        s_text = self.start_input.text().strip()
        e_text = self.end_input.text().strip()
        s = parse_time_str(s_text)
        e = parse_time_str(e_text)

        if s < 0 or e < 0:
            self._mark_inputs_invalid()
            self._show_toast_error("Invalid time format")
            return

        if s >= e:
            self._mark_inputs_invalid()
            self._show_toast_error("Start time must be before end time")
            return

        if s >= self.duration or e > self.duration:
            self._mark_inputs_invalid()
            self._show_toast_error("Trim range exceeds media duration")
            return

        if not self.main_win: return
        
        url = self.current_info.get('_url')
        title = self.current_info.get('title', 'Trimmed Media')
        selected_fmt = self.qual_combo.currentData()
        selected_fid = selected_fmt.get('format_id') if isinstance(selected_fmt, dict) else selected_fmt
        audio_bitrate = selected_fmt.get('kbps') if (self.is_audio_mode and isinstance(selected_fmt, dict)) else None

        thumb_path = None
        thumb_data = self.current_info.get('_thumb_data')
        thumb_url = self.current_info.get('thumbnail')
        if thumb_data and thumb_url:
            try:
                t_hash = hashlib.md5(thumb_url.encode()).hexdigest()
                candidate = str(thumb_dir / f"{t_hash}.png")
                if not os.path.exists(candidate):
                    with open(candidate, 'wb') as f:
                        f.write(thumb_data)
                thumb_path = candidate
            except Exception:
                thumb_path = None
        
        item = self.main_win.DownloadItem(
            url=url,
            title=f"[Trimmed] {title}",
            channel=self.current_info.get('uploader') or self.current_info.get('channel', 'YouTube'),
            thumb_path=thumb_path,
            out_dir=self._download_dir(),
            is_audio=self.is_audio_mode,
            selected_fid=selected_fid,
            duration_str=format_time_str(e - s),
            site_name=_site_name(url),
            thumb_url=thumb_url,
            fav_path=self.current_info.get('_fav_path'),
            start_time=s,
            end_time=e,
            audio_bitrate=audio_bitrate
        )
        
        self.main_win._dl_items.append(item)
        if hasattr(self.main_win, "_dl_item_added"):
            self.main_win._dl_item_added(item)
            
        self.main_win._start_download(item)
        self.main_win._show_tab(2)
        
        # Defer the UI reset logic to safely prevent GUI hangs during the tab switch 
        QTimer.singleShot(50, self._show_initial_view)
