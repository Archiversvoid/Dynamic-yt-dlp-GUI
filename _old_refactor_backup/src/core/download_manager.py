"""
Download item state container and threading pipeline hooks.
"""
import sys
import time
import os
import queue
import threading
from datetime import datetime
from urllib.parse import urlparse
from src.core.settings_store import get_repo_root

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


def _is_youtube_url(url):
    return any(d in url.lower() for d in ("youtube.com", "youtu.be", "youtube-nocookie.com", "music.youtube.com", "m.youtube.com"))


class DownloadItem:
    _counter = int(time.time())

    def __init__(self, url, title, channel, thumb_path, out_dir, is_audio, selected_fid, duration_str, site_name, thumb_url=None, fav_path=None, start_time=None, end_time=None):
        DownloadItem._counter += 1
        self.id = DownloadItem._counter
        self.url, self.title, self.channel = url, title, channel
        self.thumb_url, self.thumb_path, self.fav_path = thumb_url, thumb_path, fav_path
        self.out_dir, self.is_audio, self.selected_fid = out_dir, is_audio, selected_fid
        self.duration_str, self.site_name = duration_str, site_name
        self.start_time, self.end_time = start_time, end_time
        self.status, self.percent, self.speed, self.eta, self.downloaded, self.total_size, self.error_msg = "active", 0.0, "", "", "", "", ""
        self.final_path = None
        self.timestamp = datetime.now().strftime("%H:%M")
        self._thread, self._cancelled, self._trash_ready, self._notified = None, False, False, False


def fetcher_download(url, selected_fid=None, out_dir=None, is_audio=False, start_time=None, end_time=None):
    repo_root = get_repo_root()
    q = queue.Queue()

    def format_size(b):
        if not b: return "0 MB"
        if b >= 1024 * 1024 * 1024: return f"{b / (1024**3):.2f} GB"
        if b >= 1024 * 1024: return f"{b / (1024**2):.1f} MB"
        return f"{b / 1024:.1f} KB"

    def progress_hook(d):
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total) if total > 0 else 0.0

            speed_bytes = d.get('speed') or 0
            if speed_bytes > 1024 * 1024:
                speed_str = f"{speed_bytes / (1024*1024):.1f} MB/s"
            elif speed_bytes > 1024:
                speed_str = f"{speed_bytes / 1024:.1f} KB/s"
            else:
                speed_str = f"{speed_bytes:.0f} B/s" if speed_bytes else "0 MB/s"

            eta_sec = d.get('eta')
            if eta_sec is not None:
                m, s = divmod(int(eta_sec), 60)
                h, m = divmod(m, 60)
                eta_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
            else:
                eta_str = "--:--"

            q.put({
                "type": "progress",
                "percent": percent,
                "speed": speed_str,
                "eta": eta_str,
                "downloaded": format_size(downloaded),
                "size": format_size(total)
            })
        elif d.get('status') == 'finished':
            q.put({
                "type": "progress",
                "percent": 1.0,
                "speed": "Processing...",
                "eta": "00:00",
                "downloaded": "",
                "size": ""
            })

    def run_dl():
        try:
            import glob
            ydl_mod = _get_yt_dlp()
            if ydl_mod is None:
                q.put({"type": "error", "message": "yt-dlp library missing"})
                return
            os.makedirs(out_dir, exist_ok=True)
            ydl_opts = {
                'outtmpl': os.path.join(out_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [progress_hook],
                'concurrent_fragment_downloads': 8,
                'merge_output_format': 'mp4',
                'postprocessor_args': {
                    'ffmpeg': ['-avoid_negative_ts', 'make_zero']
                }
            }

            if _is_youtube_url(url):
                ydl_opts['extractor_args'] = {'youtube': ['player_client=tv,web_safari']}
                ydl_opts['http_headers'] = {'Accept-Language': 'en-US,en;q=0.9'}

            final_path_holder = {"path": None}
            def _pp_hook(d):
                if d.get('status') == 'finished':
                    info_d = d.get('info_dict') or {}
                    fp = info_d.get('filepath') or info_d.get('_filename')
                    if fp:
                        final_path_holder['path'] = fp
            ydl_opts['postprocessor_hooks'] = [_pp_hook]
            if (repo_root / ('ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')).exists():
                ydl_opts['ffmpeg_location'] = str(repo_root)

            if is_audio:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['writethumbnail'] = True
                ydl_opts['postprocessors'] = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                    {'key': 'FFmpegMetadata'},
                    {'key': 'EmbedThumbnail'},
                ]
            elif selected_fid:
                ydl_opts['format'] = f"{selected_fid}+bestaudio/best"
            else:
                ydl_opts['format'] = 'bestvideo+bestaudio/best'

            if start_time is not None and end_time is not None:
                def range_func(info_dict, ydl):
                    return [{'start_time': start_time, 'end_time': end_time}]
                ydl_opts['download_ranges'] = range_func
                ydl_opts['force_keyframes_at_cuts'] = True

            with ydl_mod.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise Exception("Could not extract video information")
                if info.get('_type') == 'playlist' and info.get('entries'):
                    info = next((e for e in info['entries'] if e), info)

                try:
                    from yt_dlp.utils import sanitize_filename
                except ImportError:
                    def sanitize_filename(s, **kwargs):
                        import re
                        return re.sub(r'(?u)[^-\w.]', '_', s)

                base_title = info.get('title', 'Download')
                current_title = base_title
                sanitized = sanitize_filename(current_title, restricted=False)

                counter = 1
                while glob.glob(os.path.join(glob.escape(out_dir), f"{glob.escape(sanitized)}.*")):
                    current_title = f"{base_title} ({counter})"
                    sanitized = sanitize_filename(current_title, restricted=False)
                    counter += 1

                info['title'] = current_title
                ydl.process_ie_result(info, download=True)

                resolved_path = final_path_holder["path"]
                if not resolved_path:
                    try:
                        candidate = ydl.prepare_filename(info)
                        if candidate and os.path.exists(candidate):
                            resolved_path = candidate
                    except Exception:
                        pass

            q.put({"type": "done", "filepath": resolved_path})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})

    t = threading.Thread(target=run_dl, daemon=True)
    t.start()

    while True:
        try:
            item = q.get(timeout=0.1)
            yield item
            if item.get("type") in ("done", "error"):
                break
        except queue.Empty:
            if not t.is_alive():
                yield {"type": "error", "message": "Download thread terminated unexpectedly"}
                break