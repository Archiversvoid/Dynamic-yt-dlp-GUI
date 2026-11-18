"""Where everything lives. Everything else imports its folders from here.

Two kinds of folders:

  app_dir (repo_root)  READ-ONLY program files: icons, Terms/Changelog, bin\\ ...
                       the install folder when compiled, the project folder when run from source.
  data_dir             everything the app WRITES: settings, downloads list, cache, logs, binary_dir.json.
                       %APPDATA%\\Dynamic when compiled, the project folder when run from source.

So the data survives uninstalling/reinstalling, and the install folder can live anywhere the user chose.
"""
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

app_dir = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[1]
repo_root = app_dir                      # the older name: used for icons/ and the Terms/Changelog files
BASE_DIR = app_dir
ICON_PATH = str(app_dir / "icons" / "icon.ico")      # window, taskbar, tray and toast icon
src_dir = app_dir / "src"


def _roaming():
    base = os.environ.get("APPDATA")
    return Path(base) if base else Path.home() / "AppData" / "Roaming"


data_dir = Path(os.environ["DYNAMIC_DATA_DIR"]) if os.environ.get("DYNAMIC_DATA_DIR") else (_roaming() / "Dynamic" if FROZEN else app_dir)
cache_dir = data_dir / "cache"
thumb_dir = cache_dir / "thumbnails"
favicon_dir = cache_dir / "favicons"
logs_dir = data_dir / "logs"
settings_file = data_dir / "settings.json"
downloads_file = data_dir / "downloads.json"
binary_config = data_dir / "binary_dir.json"      # remembers where yt-dlp / ffmpeg / ffprobe are

for _d in (data_dir, cache_dir, thumb_dir, favicon_dir, logs_dir):
    _d.mkdir(parents=True, exist_ok=True)


def _writable(folder):
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write_test"
        probe.write_text("x")
        probe.unlink()
        return True
    except OSError:
        return False


# bin\\ holds yt-dlp and ffmpeg. Next to the app by default; if that folder can't be written to
# (e.g. a Program Files install without admin rights) it lives in the data folder instead.
bin_dir = app_dir / "bin"
if not _writable(bin_dir):
    bin_dir = data_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

if not FROZEN:                           # running from source: make `import src...`, `import theme` and the bare legacy imports work
    if str(repo_root) not in sys.path: sys.path.insert(0, str(repo_root))
    if src_dir.exists() and str(src_dir) not in sys.path: sys.path.insert(0, str(src_dir))
    core_dir = src_dir / "core"
    if core_dir.exists() and str(core_dir) not in sys.path: sys.path.insert(0, str(core_dir))
else:
    core_dir = src_dir / "core"


def default_download_dir():
    """The user's real Downloads folder: Windows' own setting (so a relocated Downloads folder
    is honoured), else ~/Downloads, else <data>/downloads."""
    if sys.platform == "win32":
        try:
            import ctypes

            class _GUID(ctypes.Structure):
                _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                            ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]
            folder_id = _GUID(0x374DE290, 0x123F, 0x4565, (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
            buf = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(buf)) == 0:
                path = buf.value
                ctypes.windll.ole32.CoTaskMemFree(buf)
                if path:
                    return str(Path(path))
        except Exception:
            pass
    home_downloads = Path.home() / "Downloads"
    return str(home_downloads) if home_downloads.is_dir() else str(data_dir / "downloads")
