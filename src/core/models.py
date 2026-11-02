"""Plain data: the download record and the cross-thread signals."""
import time
from datetime import datetime
from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    update_progress = Signal(object)
    refresh_card = Signal(object)
    home_result = Signal(dict, str, object, object, object, object)
    home_error = Signal(str)
    home_phase = Signal(int, str)
    binary_version = Signal(str, str)          # name, text
    update_done = Signal(str, bool, str)       # name, ok, 'updated' | 'current' | error text


class DownloadItem:
    _counter = int(time.time())
    def __init__(self, url, title, channel, thumb_path, out_dir, is_audio, selected_fid, duration_str, site_name, thumb_url=None, fav_path=None, start_time=None, end_time=None, audio_bitrate=None):
        DownloadItem._counter += 1
        self.id = DownloadItem._counter
        self.url, self.title, self.channel = url, title, channel
        self.thumb_url, self.thumb_path, self.fav_path = thumb_url, thumb_path, fav_path
        self.out_dir, self.is_audio, self.selected_fid = out_dir, is_audio, selected_fid
        self.duration_str, self.site_name = duration_str, site_name
        self.start_time, self.end_time = start_time, end_time
        self.audio_bitrate = audio_bitrate        # MP3 kbps chosen for an audio download (None = default)
        self.status, self.percent, self.speed, self.eta, self.downloaded, self.total_size, self.error_msg = "active", 0.0, "", "", "", "", ""
        self.final_path = None
        self.timestamp = datetime.now().strftime("%H:%M")
        self._thread, self._cancelled, self._trash_ready, self._notified = None, False, False, False
