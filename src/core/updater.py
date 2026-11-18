"""yt-dlp / ffmpeg version lookup and updating. No UI in here."""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from src.core.binaries import get_binary_path, run_version, set_binary_path
from src.paths import bin_dir, FROZEN, logs_dir, repo_root


def _pkg_version(name):
    if FROZEN and name in ("yt-dlp", "yt_dlp"):          # compiled build: the version of the file in bin\\
        p = get_binary_path("yt-dlp")
        try:
            return run_version(p) if p else None
        except Exception:
            return None
    try:
        from importlib.metadata import version   # reads metadata only; does not import the package
        return version(name)
    except Exception:
        return None


def _ffmpeg_version_text():
    try:
        exe = get_binary_path("ffmpeg")
        if not exe:
            return "Not found"
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        out = subprocess.run([str(exe), "-version"], capture_output=True, text=True, timeout=5, creationflags=flags).stdout
        first = out.splitlines()[0] if out else ""
        parts = first.split()
        return parts[2] if len(parts) >= 3 and parts[1] == "version" else (first or "Unknown")
    except Exception:
        return "Unknown"


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
        d = logs_dir; d.mkdir(parents=True, exist_ok=True)
        with open(d / "update_errors.log", "a", encoding="utf-8") as f:
            f.write("[%s] %s: %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, str(err).replace("\n", " ")))
    except Exception:
        pass


UPDATE_SCHEDULES = ["Manual only", "On startup", "Every 2 days", "Every week", "Every 15 days"]
_SCHEDULE_DAYS = {"Every 2 days": 2, "Every week": 7, "Every 15 days": 15}
YTDLP_EXE_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
YTDLP_LATEST_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_LATEST_URL = "https://www.gyan.dev/ffmpeg/builds/release-version"


def _install_ytdlp_exe():
    """Download the latest standalone yt-dlp.exe into bin\\ and register it."""
    part = bin_dir / "yt-dlp.exe.part"
    dest = bin_dir / "yt-dlp.exe"
    try:
        req = urllib.request.Request(YTDLP_EXE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
            shutil.copyfileobj(r, f, 1024 * 1024)
        if part.stat().st_size < 5 * 1024 * 1024:
            raise RuntimeError("The downloaded yt-dlp file is too small - try again")
        with open(part, "rb") as f:
            if f.read(2) != b"MZ":
                raise RuntimeError("The downloaded file isn't a Windows program")
        try:
            os.replace(part, dest)
        except PermissionError:
            raise RuntimeError("yt-dlp.exe is in use - wait for downloads to finish and try again")
    finally:
        if part.exists():
            try:
                os.remove(part)
            except OSError:
                pass
    set_binary_path("yt-dlp", dest)


def _latest_ytdlp_tag():
    try:
        req = urllib.request.Request(YTDLP_LATEST_API, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8")).get("tag_name") or None
    except Exception:
        return None


def _update_ytdlp():
    """-> ('updated' | 'current', ''). Raises RuntimeError with a short reason.

    From source with the pip package installed: updates the package. Otherwise (and always in the compiled app):
    keeps the standalone yt-dlp.exe in bin\\ current - no download when it already is the latest release."""
    import importlib
    if not FROZEN and _pkg_version("yt-dlp"):
        before = _pkg_version("yt-dlp")
        cmd = [sys.executable, "-m", "pip", "install", "-U", "--disable-pip-version-check", "--no-input",
               "--no-warn-script-location", "--progress-bar", "off", "--timeout", "30", "--retries", "2", "yt-dlp"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=_no_window(), stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            err = (r.stderr or r.stdout).strip()
            raise RuntimeError(err.splitlines()[-1][:200] if err else "pip failed")
        importlib.invalidate_caches()
        return ("updated" if _pkg_version("yt-dlp") != before else "current"), ""
    current = get_binary_path("yt-dlp")
    latest = _latest_ytdlp_tag()
    if current is not None and latest:
        try:
            installed = run_version(current)
        except Exception:
            installed = ""
        if installed and installed == latest:
            return "current", ""
    _install_ytdlp_exe()
    return "updated", ""


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
                part = bin_dir / (base + ".part")
                with z.open(member) as src, open(part, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                try:
                    os.replace(part, bin_dir / base)
                except PermissionError:
                    try: os.remove(part)
                    except OSError: pass
                    raise RuntimeError("%s is in use - try again when nothing is downloading" % base)
    finally:
        if tmp_zip:
            try: os.remove(tmp_zip)
            except OSError: pass
    for base in ("ffmpeg.exe", "ffprobe.exe"):                 # remember where they went (binary_dir.json)
        if (bin_dir / base).is_file():
            set_binary_path(base[:-4], bin_dir / base)
    # Don't run the exe we just wrote to read its version: antivirus (Avast CyberCapture) holds a
    # never-seen-before .exe for analysis, which would stall this for no benefit.
    if latest:
        return "updated", latest
    after = _ffmpeg_version_text()
    return ("current" if after == before else "updated"), after
