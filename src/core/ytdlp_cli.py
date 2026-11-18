"""Runs the standalone yt-dlp.exe as a separate process: this is how a compiled Dynamic talks to yt-dlp.

  extract_info()   `yt-dlp -J`: the same info dictionary yt-dlp's Python API returns, as JSON
  run_download()   one download, reporting progress through the same events the Python-API path uses
  stop()           kills the process (and anything it started, e.g. ffmpeg) - used by cancel/pause
"""
import glob
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys

from src.core.binaries import ffmpeg_location, get_binary_path

MISSING_MSG = "yt-dlp isn't installed. Install from settings."
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_YOUTUBE = ["--extractor-args", "youtube:player_client=tv,web_safari", "--add-headers", "Accept-Language:en-US,en;q=0.9"]


def exe():
    return get_binary_path("yt-dlp")


def warm_up():
    """Start yt-dlp.exe once, shortly after launch, so antivirus scanning and its first unpack don't land on the first link."""
    p = exe()
    if p:
        subprocess.run([str(p), "--version"], capture_output=True, timeout=120, creationflags=_NO_WINDOW, stdin=subprocess.DEVNULL)


def _error_text(text):
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    errors = [ln for ln in lines if ln.upper().startswith("ERROR:")]
    pick = errors[-1] if errors else (lines[-1] if lines else "")
    return re.sub(r"^ERROR:\s*", "", pick, flags=re.I)


def extract_info(url, user_agent, youtube=False, timeout=90):
    """Media info for one video (no playlist), exactly what yt-dlp's Python `extract_info` returns."""
    path = exe()
    if not path:
        raise RuntimeError(MISSING_MSG)
    cmd = [str(path), "-J", "--no-playlist", "--no-warnings", "--ignore-config", "--no-color", "--encoding", "utf-8",
           "--socket-timeout", "30", "--user-agent", user_agent]
    if youtube:
        cmd += _YOUTUBE
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Fetch operation timed out")
    out = r.stdout.decode("utf-8", "replace").strip()
    if r.returncode != 0 or not out:
        raise RuntimeError(_error_text(r.stderr.decode("utf-8", "replace")) or "yt-dlp returned no data")
    try:
        return json.loads(out[out.find("{"):])
    except ValueError:
        raise RuntimeError("Could not read yt-dlp's answer")


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _size_text(b):
    if not b:
        return "0 MB"
    if b >= 1024 ** 3:
        return f"{b / (1024 ** 3):.2f} GB"
    if b >= 1024 ** 2:
        return f"{b / (1024 ** 2):.1f} MB"
    return f"{b / 1024:.1f} KB"


def _speed_text(s):
    if s > 1024 * 1024:
        return f"{s / (1024 * 1024):.1f} MB/s"
    if s > 1024:
        return f"{s / 1024:.1f} KB/s"
    return f"{s:.0f} B/s" if s else "0 MB/s"


def _eta_text(eta):
    if eta is None:
        return "--:--"
    m, s = divmod(int(eta), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _unique_destination(out_dir, name):
    """'Title.mp4' -> 'Title (1).mp4' ... if anything called 'Title.*' is already there (same rule as before)."""
    stem, ext = os.path.splitext(name)
    candidate, n = stem, 0
    while glob.glob(os.path.join(glob.escape(out_dir), glob.escape(candidate) + ".*")):
        n += 1
        candidate = "%s (%d)" % (stem, n)
    return os.path.join(out_dir, candidate + ext)


def _kill_tree(pid):
    if sys.platform == "win32":      # yt-dlp.exe starts a second process of itself, and that one starts ffmpeg: kill the whole tree
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=_NO_WINDOW)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def stop(state):
    """Cancel/pause: the download folder is kept, so Resume continues from the partial files."""
    state["stop"] = True
    proc = state.get("proc")
    if proc is not None and proc.poll() is None:
        _kill_tree(proc.pid)
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


def run_download(q, state, url, selected_fid, out_dir, is_audio, start_time, end_time, kbps, youtube, to_error):
    """Download `url`, putting {"type": "progress" | "done" | "error"} events on `q`."""
    try:
        path = exe()
        if not path:
            q.put({"type": "error", "message": MISSING_MSG})
            return
        os.makedirs(out_dir, exist_ok=True)
        # Work in a folder of our own (stable per download, so a resumed download finds its partial files), then move the
        # finished file into place under a free name - that is how "Title (1).mp4" is chosen.
        key = hashlib.sha1(("%s|%s|%s|%s|%s" % (url, selected_fid, is_audio, start_time, end_time)).encode("utf-8")).hexdigest()[:10]
        tmp = os.path.join(out_dir, ".dynamic_" + key)
        os.makedirs(tmp, exist_ok=True)
        path_file = os.path.join(tmp, "final_path.txt")
        if os.path.exists(path_file):
            os.remove(path_file)
        cmd = [str(path), "--ignore-config", "--no-color", "--no-playlist", "--newline", "--progress", "--encoding", "utf-8",
               "-o", tmp.replace("%", "%%") + os.sep + "%(title)s.%(ext)s",
               "--concurrent-fragments", "8", "--merge-output-format", "mp4",
               "--postprocessor-args", "ffmpeg:-avoid_negative_ts make_zero",
               "--progress-template", "download:DYNP|%(progress.status)s|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s",
               "--progress-template", "postprocess:DYNPP|%(progress.status)s",
               "--print-to-file", "after_move:filepath", path_file]
        ffdir = ffmpeg_location()
        if ffdir:
            cmd += ["--ffmpeg-location", ffdir]
        if youtube:
            cmd += _YOUTUBE
        if is_audio:
            cmd += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "%dK" % kbps,
                    "--embed-metadata", "--embed-thumbnail"]
        elif selected_fid:
            cmd += ["-f", "%s+bestaudio/best" % selected_fid]
        else:
            cmd += ["-f", "bestvideo+bestaudio/best"]
        if start_time is not None and end_time is not None:
            # force_keyframes_at_cuts re-encodes only the small slice at each cut and stream-copies the rest
            cmd += ["--download-sections", "*%.3f-%.3f" % (float(start_time), float(end_time)), "--force-keyframes-at-cuts"]
        cmd.append(url)

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                creationflags=_NO_WINDOW, text=True, encoding="utf-8", errors="replace", bufsize=1)
        state["proc"] = proc
        tail, processing = [], False
        for line in proc.stdout:
            if state["stop"]:
                break
            line = line.strip()
            if line.startswith("DYNP|"):
                parts = line.split("|")
                if len(parts) >= 7:
                    done_b = _num(parts[2]) or 0.0
                    total = _num(parts[3]) or _num(parts[4]) or 0.0
                    if parts[1] == "downloading":
                        q.put({"type": "progress", "percent": min(1.0, done_b / total) if total > 0 else 0.0,
                               "speed": _speed_text(_num(parts[5]) or 0), "eta": _eta_text(_num(parts[6])),
                               "downloaded": _size_text(done_b), "size": _size_text(total)})
                    elif parts[1] == "finished":
                        q.put({"type": "progress", "percent": 1.0, "speed": "Processing...", "eta": "00:00", "downloaded": "", "size": ""})
            elif line.startswith("DYNPP|"):
                if not processing:
                    processing = True
                    q.put({"type": "progress", "percent": 1.0, "speed": "Processing...", "eta": "00:00", "downloaded": "", "size": ""})
            elif line:
                tail = (tail + [line])[-12:]
        if state["stop"]:
            return
        proc.wait()
        if proc.returncode != 0:
            err = _error_text("\n".join(tail)) or "yt-dlp stopped with an error"
            q.put({"type": "error", "message": to_error(RuntimeError(err)), "raw": err})
            return
        final = None
        try:
            with open(path_file, encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            final = lines[-1] if lines else None
        except OSError:
            pass
        if not final or not os.path.isfile(final):           # fall back to the newest finished media file
            skip = (".part", ".ytdl", ".txt", ".webp", ".jpg", ".jpeg", ".png", ".temp")
            found = [os.path.join(tmp, f) for f in os.listdir(tmp) if os.path.isfile(os.path.join(tmp, f)) and not f.lower().endswith(skip)]
            final = max(found, key=os.path.getmtime) if found else None
        if not final:
            q.put({"type": "error", "message": "The download finished but the file wasn't found", "raw": ""})
            return
        dest = _unique_destination(out_dir, os.path.basename(final))
        shutil.move(final, dest)
        shutil.rmtree(tmp, ignore_errors=True)
        q.put({"type": "done", "filepath": dest})
    except Exception as e:
        if not state["stop"]:
            q.put({"type": "error", "message": to_error(e), "raw": str(e)})
