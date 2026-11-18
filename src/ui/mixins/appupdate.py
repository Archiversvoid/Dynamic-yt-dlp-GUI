"""Dynamic's own updates: the 'update available' toast, the Update button on Settings > Update, and the restart."""
import threading
import time
import traceback
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication
from src.core import app_updater
from src.core.app_info import APP_VERSION
from src.paths import logs_dir
from src.ui.mixins.binaries import _short_reason

CHECK_EVERY_MS = 6 * 3600 * 1000          # while the app is running (it lives in the tray, so that can be days)
SNOOZE_SECONDS = 24 * 3600                # what "Remind me later" silences the toast for


class AppUpdateMixin:
    def _init_app_updates(self):
        if getattr(self, "_app_update_ready_init", False):
            return
        self._app_update_ready_init = True
        self._app_update = None               # the newer release, when there is one
        self._app_update_state = "idle"       # idle | checking | available | downloading | ready
        self._app_update_kind = "package"     # what was downloaded: "package" (already applied) | "installer" (runs on Restart)
        self._app_update_file = None
        self.signals.app_update_checked.connect(self._on_app_update_checked)
        self.signals.app_update_progress.connect(self._on_app_update_progress)
        self.signals.app_update_done.connect(self._on_app_update_done)
        threading.Thread(target=app_updater.cleanup_old_files, daemon=True).start()      # leftovers of the last update
        self._check_app_update(manual=False)
        self._app_update_timer = QTimer(self)
        self._app_update_timer.setInterval(CHECK_EVERY_MS)
        self._app_update_timer.timeout.connect(lambda: self._check_app_update(manual=False))
        self._app_update_timer.start()

    def _emit_app(self, name, *args):
        try:
            getattr(self.signals, name).emit(*args)
        except RuntimeError:                  # the window is already gone
            pass

    def _app_toast(self, text):
        self.toast_mgr.show_toast(text, icon_pixmap=self._icons.get("info", QIcon()).pixmap(22, 22))

    def _set_app_button(self, text, enabled=True):
        btn = getattr(self, "_upd_app_btn", None)
        if btn is not None:
            btn.setText(text)
            btn.setEnabled(enabled)

    def _refresh_app_update_row(self):
        """The Dynamic row on Settings > Update: its version, or what is happening."""
        sub = getattr(self, "_upd_app_sub", None)
        state = getattr(self, "_app_update_state", None)
        if sub is None or state is None:
            return
        info = self._app_update
        if state == "ready":
            sub.setText(("%s is ready - restart to install" if self._app_update_kind == "installer" else "Updated to %s - restart to finish") % info["version"])
            self._set_app_button("Restart", True)
            return
        sub.setText("%s (%s available)" % (APP_VERSION, info["version"]) if info else APP_VERSION)
        if state not in ("checking", "downloading"):
            self._set_app_button("Update", True)

    # ---- looking for a release
    def _check_app_update(self, manual=False):
        if self._app_update_state in ("checking", "downloading", "ready"):
            return
        if manual:
            self._app_update_state = "checking"
            self._set_app_button("Checking...", False)

        def work():
            try:
                result = {"manual": manual, "info": app_updater.fetch_latest(), "error": ""}
            except Exception as e:
                result = {"manual": manual, "info": None, "error": str(e)[:120] or type(e).__name__}
            self._emit_app("app_update_checked", result)
        threading.Thread(target=work, daemon=True).start()

    def _on_app_update_checked(self, result):
        if self._app_update_state in ("downloading", "ready"):
            return
        info, manual, error = result["info"], result["manual"], result.get("error")
        if error:                                          # offline / GitHub unreachable: quiet unless the user asked
            self._app_update_state = "available" if self._app_update else "idle"
            self._refresh_app_update_row()
            if manual:
                self._app_toast("Couldn't check for updates")
            return
        if info is not None and app_updater.is_newer(info["version"], APP_VERSION):
            self._app_update, self._app_update_state = info, "available"
            self._refresh_app_update_row()
            if manual:
                self._start_app_update()
            elif not self._app_update_snoozed() and hasattr(self, "binary_toasts"):
                self.binary_toasts.set_update("An update is available (%s)" % info["version"])
        else:                                              # already the newest - or no release has been published yet
            self._app_update, self._app_update_state = None, "idle"
            self._refresh_app_update_row()
            if hasattr(self, "binary_toasts"):
                self.binary_toasts.set_update(None)
            if manual:
                self._app_toast("You're up to date")

    # ---- the buttons
    def _on_app_update_button(self):
        """Settings > Update > Dynamic > Update."""
        self._init_app_updates()
        state = self._app_update_state
        if state == "ready":
            self._restart_for_update()
        elif state in ("checking", "downloading"):
            return
        elif state == "available" and self._app_update:
            self._start_app_update()                       # already known - no need to ask GitHub again
        else:
            self._check_app_update(manual=True)

    def _app_update_primary(self):
        """The toast's Update / Restart button."""
        if self._app_update_state == "ready":
            self._restart_for_update()
        elif self._app_update_state == "available":
            self._start_app_update()

    def _app_update_snoozed(self):
        """True while "Remind me later" is in effect (kept in settings, so it survives closing the app)."""
        try:
            until = float(self.settings.get("app_update_snooze_until") or 0)
        except (TypeError, ValueError):
            return False
        now = time.time()
        return now < until <= now + SNOOZE_SECONDS + 3600          # a clock set back doesn't silence it for years

    def _app_update_secondary(self):
        """The toast's Remind me later / Later button (and its X).
        Before an update: no toast for 24 hours - for this release or a newer one - even if the app is restarted;
        then it comes back. After an update has been installed: just hides the restart prompt (nothing to remind about)."""
        if self._app_update_state != "ready":
            self.settings["app_update_snooze_until"] = time.time() + SNOOZE_SECONDS
            self._save_settings()
            QTimer.singleShot(SNOOZE_SECONDS * 1000 + 5000, lambda: self._check_app_update(manual=False))
        if hasattr(self, "binary_toasts"):
            self.binary_toasts.set_update(None)

    # ---- downloading and installing
    def _start_app_update(self):
        info = self._app_update
        if not info:
            return
        ok, reason = app_updater.can_apply()
        if not info.get("asset") or not ok:                # nothing to install in place: say why instead of guessing
            self._app_update_state = "available"
            self._set_app_button("Update", True)
            if not info.get("asset"):
                self._app_toast("No update file in this release")
            elif reason == app_updater.NOT_INSTALLED:
                self._app_toast("Updates install only in the installed app")
            else:                                          # a protected folder (e.g. Program Files): the installer is the way
                QDesktopServices.openUrl(QUrl(info.get("page") or app_updater.RELEASES_URL))
                self._app_toast("Install folder is protected - opening the release page")
            return
        self._app_update_state = "downloading"
        self._set_app_button("Downloading...", False)
        if hasattr(self, "binary_toasts"):
            self.binary_toasts.set_busy("update", True, "Downloading...")
        last = [-1]

        def progress(done, total):
            pct = int(done * 100 / total) if total else 0
            if pct != last[0]:
                last[0] = pct
                self._emit_app("app_update_progress", pct)

        def work():
            try:
                package = app_updater.download_package(info, progress)
                self._emit_app("app_update_progress", 100)
                kind, target = app_updater.prepare_download(package)
                if kind == "package":                      # the files are swapped in now; Restart just starts the new copy
                    app_updater.apply_update(target, version_hint=info["version"])
                self._app_update_kind, self._app_update_file = kind, target      # "installer": Restart runs it
                self._emit_app("app_update_done", True, info["version"])
            except Exception as e:
                try:
                    with open(logs_dir / "app_update.log", "a", encoding="utf-8") as f:
                        f.write("[update to %s] %s\n" % (info["version"], traceback.format_exc()))
                except OSError:
                    pass
                self._emit_app("app_update_done", False, str(e)[:200])
        threading.Thread(target=work, daemon=True).start()

    def _on_app_update_progress(self, pct):
        text = "Downloading %d%%" % pct if pct < 100 else "Installing..."
        self._set_app_button(text, False)
        if hasattr(self, "binary_toasts"):
            self.binary_toasts.set_busy("update", True, text)

    def _on_app_update_done(self, ok, message):
        if hasattr(self, "binary_toasts"):
            self.binary_toasts.set_busy("update", False)
        if ok:
            self._app_update_state = "ready"
            self._refresh_app_update_row()
            if hasattr(self, "binary_toasts"):
                text = ("Version %s is ready to install" if self._app_update_kind == "installer" else "Updated to %s - restart to finish") % message
                self.binary_toasts.set_update(text, "Restart", "Later")
        else:
            self._app_update_state = "available"
            self._set_app_button("Update", True)
            self._app_toast("Update failed (%s)" % _short_reason(message))

    def _restart_for_update(self):
        if self._has_active_downloads():
            self._app_toast("A download is running - restart when it finishes")
            return
        self._persist_state()
        if self._app_update_kind == "installer":
            started = app_updater.run_installer(self._app_update_file)
        else:
            started = app_updater.restart_app()
        if started:
            QApplication.instance().quit()
        else:
            self._app_toast("Close and reopen Dynamic to finish")
