"""yt-dlp / ffmpeg: the sticky 'not installed' notifications (Home and TrimLoad) and what their buttons do."""
import threading
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileDialog
from src.core.binaries import get_binary_path, register_validated, validate_binary, ytdlp_installed
from src.core.updater import _log_update_error, _update_ffmpeg, _update_ytdlp
from src.paths import bin_dir, logs_dir
from src.ui.components.binary_toast import BinaryToastManager


def _short_reason(message):
    """A few words for the toast; the full text is in logs\\update_errors.log."""
    m = (message or "").lower()
    if any(k in m for k in ("urlopen", "timed out", "getaddrinfo", "connection", "network")):
        return "no internet"
    if any(k in m for k in ("in use", "permission", "access is denied")):
        return "file in use"
    if any(k in m for k in ("too small", "isn't a windows", "isn't valid")):
        return "bad download"
    return (message or "").strip()[:24]


class BinariesMixin:
    def _init_binary_toasts(self):
        pix = self._icons.get("warning", QIcon()).pixmap(30, 30)
        info = self._icons.get("info", QIcon()).pixmap(30, 30)
        self.binary_toasts = BinaryToastManager(self, pix, info)
        self.binary_toasts.download_requested.connect(self._on_binary_download)
        self.binary_toasts.disk_requested.connect(self._on_binary_from_disk)
        self.signals.binary_installed.connect(self._on_binary_installed)
        self._refresh_binary_toasts()

    def _binary_installed(self, name):
        return get_binary_path("ffmpeg") is not None if name == "ffmpeg" else ytdlp_installed()

    def _missing_binaries(self):
        return [n for n in ("ffmpeg", "yt-dlp") if not self._binary_installed(n)]

    def _refresh_binary_toasts(self):
        if hasattr(self, "binary_toasts"):
            self.binary_toasts.set_missing(self._missing_binaries())
            self.binary_toasts.set_page_visible(self.stack.currentIndex() in (0, 1))      # Home and TrimLoad

    def _emit_binary(self, name, ok, message):
        try:
            self.signals.binary_installed.emit(name, ok, message)
        except RuntimeError:                      # the window is already gone
            pass

    def _on_binary_download(self, name):
        if name == "update":                      # the update toast shares these two buttons
            self._app_update_primary()
            return
        self.binary_toasts.set_busy(name, True, "Downloading...")

        def work():
            try:
                (_update_ffmpeg if name == "ffmpeg" else _update_ytdlp)()
                self._emit_binary(name, True, "")
            except Exception as e:
                _log_update_error(name, e)
                self._emit_binary(name, False, str(e)[:200])
        threading.Thread(target=work, daemon=True).start()

    def _on_binary_from_disk(self, name):
        if name == "update":
            self._app_update_secondary()
            return
        if name == "ffmpeg":
            title, filt = "Select ffmpeg.exe", "ffmpeg (ffmpeg.exe);;All files (*)"
        else:
            title, filt = "Select yt-dlp.exe", "yt-dlp (yt-dlp*.exe);;All files (*)"
        path, _ = QFileDialog.getOpenFileName(self, title, str(bin_dir), filt)
        if not path:
            return
        self.binary_toasts.set_busy(name, True, "Checking...")

        def work():
            ok, reason = validate_binary(name, Path(path))
            if ok:
                register_validated(name, path)
            else:
                try:
                    with open(logs_dir / "binaries.log", "a", encoding="utf-8") as f:
                        f.write("[invalid %s] %s -> %s\n" % (name, path, reason))
                except OSError:
                    pass
            self._emit_binary(name, ok, "" if ok else "invalid:" + reason)
        threading.Thread(target=work, daemon=True).start()

    def _on_binary_installed(self, name, ok, message):
        self.binary_toasts.set_busy(name, False)
        if ok:
            self.toast_mgr.show_toast("%s installed" % name, icon_pixmap=self._icons.get("check", QIcon()).pixmap(22, 22))
            self._refresh_binary_toasts()
            if hasattr(self, "_refresh_update_rows"):
                self._refresh_update_rows()
                self._fetch_version_async(name)
        elif message.startswith("invalid:"):
            self.toast_mgr.show_toast("Invalid binary")
        else:
            reason = _short_reason(message)
            self.toast_mgr.show_toast("Couldn't install %s%s" % (name, " (%s)" % reason if reason else ""))
