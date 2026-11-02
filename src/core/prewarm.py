"""Reading files into the operating system's file cache ahead of time, so the first real load is fast.

Why: right after a boot nothing is cached. Opening the TrimLoad tab loads the Qt multimedia stack
(an FFmpeg backend: about 100 MB of DLLs) and every one of those files has to come off the disk and
be scanned by antivirus first. Doing that inside the click froze the window. Reading the files in a
background thread is harmless to the UI - file reads release the GIL and never touch a widget - and
afterwards loading them is nearly instant.
"""
import sys
import threading
from pathlib import Path

_PATTERNS = (
    "Qt6Multimedia*.dll", "Qt6Svg*.dll", "QtMultimedia*.pyd", "QtSvg*.pyd",     # the Qt modules TrimLoad imports
    "av*.dll", "sw*.dll",                                                       # the FFmpeg libraries Qt's multimedia backend loads
    "plugins/multimedia/*.dll", "plugins/imageformats/qsvg*.dll", "plugins/iconengines/qsvg*.dll",
)


def collect_multimedia_files(base=None):
    """Files that opening the TrimLoad tab will load. `base` is the PySide6 package folder."""
    if base is None:
        try:
            import PySide6
            base = Path(PySide6.__file__).resolve().parent
        except Exception:
            return []
    base = Path(base)
    files, seen = [], set()
    for pattern in _PATTERNS:
        for p in sorted(base.glob(pattern)):
            if p.is_file() and p not in seen:
                seen.add(p)
                files.append(p)
    return files


class FilePrewarm:
    """Reads `files` once, in a background thread, at low priority. Never raises."""
    CAP = 600 * 1024 * 1024          # never read more than this, whatever the files turn out to be

    def __init__(self, files):
        self.files = list(files)
        self.bytes_read = 0
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        self._background_priority(True)
        try:
            for path in self.files:
                try:
                    with open(path, "rb", buffering=0) as fh:
                        while True:
                            chunk = fh.read(1 << 20)
                            if not chunk:
                                break
                            self.bytes_read += len(chunk)
                            if self.bytes_read >= self.CAP:
                                return
                except OSError:
                    continue
        except Exception:
            pass
        finally:
            self._background_priority(False)

    @staticmethod
    def _background_priority(begin):
        """Windows: lower this thread's disk and memory priority so the read never competes with the app."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetThreadPriority(k.GetCurrentThread(), 0x00010000 if begin else 0x00020000)   # THREAD_MODE_BACKGROUND_BEGIN / END
        except Exception:
            pass
