"""Project paths. Everything else imports its folders from here."""
import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]     # src/paths.py -> project root
BASE_DIR = repo_root
ICON_PATH = str(BASE_DIR / "icons/icon.ico")
src_dir = repo_root / "src"
cache_dir = repo_root / "cache"
thumb_dir = cache_dir / "thumbnails"
favicon_dir = cache_dir / "favicons"
thumb_dir.mkdir(parents=True, exist_ok=True)
favicon_dir.mkdir(parents=True, exist_ok=True)
if str(repo_root) not in sys.path: sys.path.insert(0, str(repo_root))
if src_dir.exists() and str(src_dir) not in sys.path: sys.path.insert(0, str(src_dir))
core_dir = src_dir / "core"
if core_dir.exists() and str(core_dir) not in sys.path: sys.path.insert(0, str(core_dir))   # Fetcher / universal_scraper


def default_download_dir():
    """The user's real Downloads folder: Windows' own setting (so a relocated Downloads folder
    is honoured), else ~/Downloads, else <app>/downloads."""
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
    return str(home_downloads) if home_downloads.is_dir() else str(repo_root / "downloads")
