"""Where yt-dlp and ffmpeg live, and how the app finds them.

  bin\\yt-dlp.exe                     yt-dlp's standalone program (a compiled app runs it as a separate process)
  bin\\ffmpeg.exe, bin\\ffprobe.exe   the ffmpeg programs

Locations are remembered in binary_dir.json (in the data folder), so the app never has to guess.
Running from source with the yt-dlp Python package installed, that package is used instead of yt-dlp.exe.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from src.paths import FROZEN, app_dir, bin_dir, binary_config

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _exe(name):
    return name + ".exe" if sys.platform == "win32" else name


def load_config():
    try:
        with open(binary_config, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    tmp = Path(str(binary_config) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, binary_config)


def set_binary_path(name, path):
    cfg = load_config()
    cfg[name] = str(path)
    cfg["bin_dir"] = str(bin_dir)
    save_config(cfg)


def get_binary_path(name):
    """The saved location, else bin\\ (and, running from source, next to the project or on PATH). None if not found."""
    saved = load_config().get(name)
    candidates = [Path(saved)] if saved else []
    candidates.append(bin_dir / _exe(name))
    if not FROZEN:                       # a compiled app only trusts its own bin\\, so "not installed" is accurate
        candidates.append(app_dir / _exe(name))
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for c in candidates:
        if c.is_file():
            return c
    return None


def ffmpeg_location():
    """Folder holding ffmpeg (and ffprobe) for yt-dlp's ffmpeg location, or None."""
    p = get_binary_path("ffmpeg")
    return str(p.parent) if p else None


def ytdlp_exe():
    """The standalone yt-dlp.exe, or None."""
    return get_binary_path("yt-dlp")


def ytdlp_installed():
    if not FROZEN:                       # running from source: a pip-installed yt-dlp counts
        import importlib.util
        if importlib.util.find_spec("yt_dlp") is not None:
            return True
    return ytdlp_exe() is not None


def run_version(path, timeout=30):
    """`<program> --version` -> its first line ('' if it printed nothing)."""
    out = subprocess.run([str(path), "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=timeout, creationflags=_NO_WINDOW, stdin=subprocess.DEVNULL).stdout
    out = (out or "").strip()
    return out.splitlines()[0].strip() if out else ""


def validate_binary(name, path):
    """-> (ok, reason). Checks that `path` really is ffmpeg / ffprobe / yt-dlp - a random .exe is refused."""
    path = Path(path)
    try:
        if not path.is_file():
            return False, "not a file"
        if name == "yt-dlp":
            if path.suffix.lower() != ".exe" or not path.name.lower().startswith("yt-dlp"):
                return False, "expected yt-dlp.exe"
        elif path.name.lower() != _exe(name):
            return False, "expected %s" % _exe(name)
        if sys.platform == "win32":
            with open(path, "rb") as f:
                if f.read(2) != b"MZ":
                    return False, "not a Windows program"
        if name == "yt-dlp":
            version = run_version(path)
            return (True, version) if re.match(r"^\d{4}\.\d{2}\.\d{2}", version) else (False, "not yt-dlp")
        out = subprocess.run([str(path), "-version"], capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW,
                             stdin=subprocess.DEVNULL).stdout
        first = (out or "").strip().splitlines()[0].lower() if (out or "").strip() else ""
        if not first.startswith(name + " version"):
            return False, "not %s" % name
        return True, first.split()[2] if len(first.split()) > 2 else ""
    except Exception as e:
        return False, "could not be checked (%s)" % type(e).__name__


def register_validated(name, path):
    """Remember a validated binary (and, for ffmpeg, the ffprobe sitting next to it)."""
    path = Path(path)
    set_binary_path(name, path)
    if name == "ffmpeg":
        probe = path.with_name(_exe("ffprobe"))
        if probe.is_file():
            set_binary_path("ffprobe", probe)
