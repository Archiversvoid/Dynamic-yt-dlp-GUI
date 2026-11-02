"""Fetching media info and downloading (yt-dlp). No UI in here."""
import re
import shutil
import sys
import urllib.request
from urllib.parse import urlparse
from src.paths import favicon_dir, repo_root


yt_dlp = None  # imported lazily - see _get_yt_dlp(). Importing it eagerly at
               # startup costs real, measurable time (it pulls in every
               # extractor module it ships with) for something nothing
               # needs until a download actually starts.


def _get_yt_dlp():
    global yt_dlp
    if yt_dlp is None:
        try:
            import yt_dlp as _yt_dlp
            yt_dlp = _yt_dlp
        except Exception:
            yt_dlp = False
    return yt_dlp or None


_AUDIO_ONLY_DOMAINS = (
    "music.youtube.com", "soundcloud.com", "spotify.com",
    "tidal.com", "deezer.com", "music.apple.com", "apple.com",
    "bandcamp.com", "audiomack.com", "reverbnation.com",
    "mixcloud.com",
)


def _is_audio_only_url(url):
    return any(d in url.lower() for d in _AUDIO_ONLY_DOMAINS)


def _is_youtube_url(url):
    return any(d in url.lower() for d in
               ("youtube.com","youtu.be","youtube-nocookie.com","music.youtube.com","m.youtube.com"))


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
        host = host.replace("www.","").replace("m.","").replace("music.","")
        return host.split(".")[0].title()
    except Exception: return "Web"


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


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_ANSI_BARE_RE = re.compile(r"\[(?:\d{1,3};)*\d{1,3}m")      # the same colour codes once the ESC byte has been lost
FFMPEG_MISSING_MSG = "ffmpeg wasn't found. Open Settings > Update, click Update next to ffmpeg, then press Retry."


def strip_ansi(text):
    """yt-dlp colours its errors; the escape codes show up as '[0;31m' junk in the UI."""
    return _ANSI_BARE_RE.sub("", _ANSI_RE.sub("", str(text)))


def friendly_error(err):
    """Plain-language version of a download error (ANSI stripped, whitespace collapsed)."""
    text = " ".join(strip_ansi(err).split())
    if text.upper().startswith("ERROR:"):
        text = text[6:].strip()
    low = text.lower()
    if ("ffmpeg" in low or "ffprobe" in low) and ("not found" in low or "not installed" in low or "no such file" in low):
        return FFMPEG_MISSING_MSG
    return text or "Unknown error"


def ffmpeg_available():
    """ffmpeg next to the app (where Settings > Update puts it) or anywhere on PATH."""
    local = repo_root / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    return local.exists() or shutil.which("ffmpeg") is not None


def _fetch_formats_subprocess(url):
    """Old path (runs the yt-dlp program via universal_scraper/Fetcher). Only used if the yt-dlp library can't be imported."""
    try:
        import importlib
        # YouTube goes through Fetcher, a thin wrapper around universal_scraper. Fetcher.py still imports
        # PyQt6 at the top, so if that cannot load we use universal_scraper directly - same function.
        candidates = ["Fetcher", "universal_scraper"] if _is_youtube_url(url) else ["universal_scraper"]
        module, last_err = None, None
        for module_name in candidates:
            for qualified in ("src.core." + module_name, module_name):
                try:
                    module = importlib.import_module(qualified)
                    break
                except ImportError as e:
                    last_err = e
            if module is not None:
                break
        if module is None:
            raise last_err
        for fn in ("fetch_formats","scrape_formats"):
            if hasattr(module, fn): return getattr(module, fn)(url)
        return {"ok": False, "error": f"{module_name} has no fetch function"}
    except Exception as e:
        return {"ok": False, "error": strip_ansi(str(e))}


DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def fetch_formats(url):
    """Media info + format lists for the Home tab.

    Uses the yt-dlp LIBRARY in-process, exactly like TrimLoad does. The Home tab used to start the
    yt-dlp program for every link and kill it after 25 s; on a first launch that program has to
    unpack itself, get scanned by antivirus and build its caches, so it often hit the limit
    ("Fetch operation timed out") and only worked after several retries. It also lacked the
    player_client=tv,web_safari option TrimLoad passes, which skips YouTube's slow challenge solving."""
    yt = _get_yt_dlp()
    if yt is None:
        return _fetch_formats_subprocess(url)
    import importlib
    try:
        try:
            scraper = importlib.import_module("src.core.universal_scraper")
        except ImportError:
            scraper = importlib.import_module("universal_scraper")
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
                "user_agent": DEFAULT_UA, "socket_timeout": 30, "no_color": True, "color": "no_color"}
        if _is_youtube_url(url):
            opts["extractor_args"] = {"youtube": ["player_client=tv,web_safari"]}
            opts["http_headers"] = {"Accept-Language": "en-US,en;q=0.9"}
        with yt.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            return {"ok": False, "error": "Could not fetch media info."}
        return scraper.result_from_info(info)
    except Exception as e:
        return {"ok": False, "error": friendly_error(e)[:200]}


MP3_BITRATES = (32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)      # the steps MP3 actually offers


def snap_mp3_bitrate(value, default=192):
    """Nearest real MP3 bitrate: a stream that reports 129.5 kbps becomes 128; above 320 becomes 320."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    if n <= 0:
        return default
    return min(MP3_BITRATES, key=lambda b: abs(b - n))


def parse_kbps(text):
    """'MP3 160kbps - 3.4 MB' or '160 kbps' -> 160 (None if there is no bitrate in the text)."""
    m = re.search(r"(\d{2,3})\s*kbps", str(text or ""), re.I)
    return int(m.group(1)) if m else None


def fetcher_download(url, selected_fid=None, out_dir=None, is_audio=False, start_time=None, end_time=None, audio_bitrate=None):
    # Every path below needs ffmpeg (merging video+audio, audio conversion, trimming). Say so up front
    # instead of downloading everything and failing at the very last step.
    if not ffmpeg_available():
        yield {"type": "error", "message": FFMPEG_MISSING_MSG, "raw": "ffmpeg not found in the app folder or on PATH"}
        return
    import queue
    import threading
    import os
    
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
            ydl_opts['no_color'] = True; ydl_opts['color'] = 'no_color'   # plain-text errors (no ANSI codes in the card)
            if (repo_root / ('ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')).exists():
                ydl_opts['ffmpeg_location'] = str(repo_root)   # use the copy Settings > Update maintains

            if is_audio:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['writethumbnail'] = True
                ydl_opts['postprocessors'] = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': str(snap_mp3_bitrate(audio_bitrate))},
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
                # force_keyframes_at_cuts already gets accurate cuts cheaply:
                # yt-dlp re-encodes only the small slice right at each cut
                # point and stream-copies everything else. Forcing a full
                # '-c:v libx264' re-encode of the whole segment on top of
                # that (as this used to) throws that efficiency away and
                # makes ffmpeg software-encode the entire clip - that was
                # the actual source of the high CPU usage during trimming.
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
            q.put({"type": "error", "message": friendly_error(e), "raw": strip_ansi(str(e))})

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
