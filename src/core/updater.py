"""yt-dlp / ffmpeg version lookup and updating. No UI in here."""
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from src.paths import repo_root


def _pkg_version(name):
    try:
        from importlib.metadata import version   # reads metadata only; does not import the package
        return version(name)
    except Exception:
        return None


def _ffmpeg_version_text():
    try:
        exe = None
        for n in ("ffmpeg.exe", "ffmpeg"):
            p = repo_root / n
            if p.exists():
                exe = str(p); break
        exe = exe or shutil.which("ffmpeg")
        if not exe: return "Not found"
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=5, creationflags=flags).stdout
        first = out.splitlines()[0] if out else ""
        parts = first.split()
        return parts[2] if len(parts) >= 3 and parts[1] == "version" else (first or "Unknown")
    except Exception:
        return "Unknown"


UPDATE_SCHEDULES = ["Manual only", "On startup", "Every 2 days", "Every week", "Every 15 days"]


_SCHEDULE_DAYS = {"Every 2 days": 2, "Every week": 7, "Every 15 days": 15}


FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


FFMPEG_LATEST_URL = "https://www.gyan.dev/ffmpeg/builds/release-version"


def _no_window():
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _ytdlp_version_text():
    v = _pkg_version("yt-dlp")
    if not v:
        for n in ("yt-dlp.exe", "yt-dlp"):
            p = repo_root / n
            if p.exists():
                try:
                    v = subprocess.run([str(p), "--version"], capture_output=True, text=True,
                                       timeout=8, creationflags=_no_window()).stdout.strip() or None
                except Exception:
                    pass
                break
    return "Version " + v if v else "Not installed"


def _ffmpeg_display_text():
    t = _ffmpeg_version_text()
    return t if t in ("Not found", "Unknown") else "Version " + t


def _log_update_error(name, err):
    try:
        d = repo_root / "logs"; d.mkdir(parents=True, exist_ok=True)
        with open(d / "update_errors.log", "a", encoding="utf-8") as f:
            f.write("[%s] %s: %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, str(err).replace("\n", " ")))
    except Exception:
        pass


def _update_ytdlp():
    """-> ('updated' | 'current', ''). Updates whatever the app actually uses:
    the pip package (what downloads import) and/or a standalone yt-dlp binary
    sitting next to the app. Raises RuntimeError with a short reason."""
    import importlib
    changed = did_something = False
    exe = next((str(repo_root / n) for n in ("yt-dlp.exe", "yt-dlp") if (repo_root / n).exists()), None)
    if exe:
        r = subprocess.run([exe, "-U"], capture_output=True, text=True, timeout=300, creationflags=_no_window())
        out = (r.stdout + r.stderr).strip()
        if r.returncode != 0 and "pip" not in out.lower():
            raise RuntimeError(out.splitlines()[-1][:200] if out else "yt-dlp -U failed")
        if r.returncode == 0:
            did_something = True
            changed = changed or ("up to date" not in out.lower())
    if not getattr(sys, "frozen", False) and _pkg_version("yt-dlp"):
        before = _pkg_version("yt-dlp")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "--disable-pip-version-check", "yt-dlp"],
                           capture_output=True, text=True, timeout=600, creationflags=_no_window())
        if r.returncode != 0:
            err = (r.stderr or r.stdout).strip()
            raise RuntimeError(err.splitlines()[-1][:200] if err else "pip failed")
        importlib.invalidate_caches()
        did_something = True
        changed = changed or (_pkg_version("yt-dlp") != before)
    if not did_something:
        raise RuntimeError("No updatable yt-dlp found")
    return ("updated" if changed else "current"), ""


def _update_ffmpeg():
    """-> ('updated' | 'current', version). Windows release build from gyan.dev,
    placed next to the app (the app already looks there first). Checks the
    tiny release-version file first so an up-to-date install costs nothing."""
    if sys.platform != "win32":
        raise RuntimeError("Automatic ffmpeg update is Windows-only")
    import zipfile, tempfile
    ua = {"User-Agent": "Mozilla/5.0"}
    before = _ffmpeg_version_text()
    try:
        with urllib.request.urlopen(urllib.request.Request(FFMPEG_LATEST_URL, headers=ua), timeout=15) as r:
            latest = r.read().decode("utf-8", "ignore").strip()
    except Exception:
        latest = ""
    if latest and before.startswith(latest):
        return "current", before
    tmp_zip = None
    try:
        fd, tmp_zip = tempfile.mkstemp(suffix=".zip"); os.close(fd)
        with urllib.request.urlopen(urllib.request.Request(FFMPEG_ZIP_URL, headers=ua), timeout=30) as r, open(tmp_zip, "wb") as f:
            shutil.copyfileobj(r, f, 1024 * 1024)
        with zipfile.ZipFile(tmp_zip) as z:
            wanted = {"ffmpeg.exe": None, "ffprobe.exe": None}
            for member in z.namelist():
                base = member.rsplit("/", 1)[-1].lower()
                if base in wanted and "/bin/" in member:
                    wanted[base] = member
            if not wanted["ffmpeg.exe"]:
                raise RuntimeError("ffmpeg.exe not found in the download")
            for base, member in wanted.items():
                if not member:
                    continue
                part = repo_root / (base + ".part")
                with z.open(member) as src, open(part, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                try:
                    os.replace(part, repo_root / base)
                except PermissionError:
                    try: os.remove(part)
                    except OSError: pass
                    raise RuntimeError("%s is in use - try again when nothing is downloading" % base)
    finally:
        if tmp_zip:
            try: os.remove(tmp_zip)
            except OSError: pass
    after = _ffmpeg_version_text()
    return ("current" if after == before else "updated"), after
