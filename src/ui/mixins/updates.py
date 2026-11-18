"""Settings > Update: yt-dlp / ffmpeg updating and the update schedule."""
import threading
import time
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from theme import ss as _ss
from src.core.app_info import APP_VERSION
from src.core.updater import (
    _ffmpeg_display_text, _log_update_error, _SCHEDULE_DAYS, _update_ffmpeg, _update_ytdlp,
    _ytdlp_version_text, UPDATE_SCHEDULES)
from src.ui.components.combo import AnimatedComboBox
from src.ui.components.controls import SettingsRow
from src.ui.styles import COMBO_QSS, TEXT_MAIN, TEXT_MUTED


class UpdatesMixin:
    """Settings > Update: yt-dlp / ffmpeg updating and the update schedule."""

    # ---- page 2: update ----
    def _build_settings_update_page(self):
        self._upd_labels = {"yt-dlp": [], "ffmpeg": []}
        self._upd_buttons = {}
        self._upd_disk = {}
        self._upd_loaded = False

        def make_row(name, pos, control):
            row = SettingsRow(name, "Checking…", pos, control=control)
            self._upd_labels[name].append(row.subtitle_lbl)
            return row

        rows = []
        for n, name in enumerate(("yt-dlp", "ffmpeg")):
            btn = self._settings_button("Update", primary=True)
            btn.clicked.connect(lambda checked=False, nm=name: self._on_update_button(nm))
            disk = self._settings_button("Load from disk...")
            disk.clicked.connect(lambda checked=False, nm=name: self._on_binary_from_disk(nm))
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(10)
            hl.addWidget(disk)
            hl.addWidget(btn)
            _ss(holder, "background: transparent;")
            self._upd_buttons[name] = btn
            self._upd_disk[name] = disk
            rows.append(make_row(name, ("top", "middle")[n], holder))
        # Dynamic itself: its version and an Update button (no schedule for this one)
        self._upd_app_btn = self._settings_button("Update", primary=True)
        self._upd_app_btn.clicked.connect(self._on_app_update_button)
        app_row = SettingsRow("Dynamic", APP_VERSION, "bottom", control=self._upd_app_btn)
        self._upd_app_sub = app_row.subtitle_lbl
        rows.append(app_row)
        card, cl = self._settings_card()
        self._settings_fill_card(cl, rows)

        self._upd_note = QLabel("")
        _ss(self._upd_note, f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;")

        sched_title = QLabel("Schedule update")
        _ss(sched_title, f"color: {TEXT_MAIN}; font-size: 22px; font-weight: bold; background: transparent;")
        sched_sub = QLabel("Choose when each one updates itself. Skipped while a download is running.")
        _ss(sched_sub, f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;")
        saved = self.settings.get("update_schedule", {})
        srows = []
        for n, name in enumerate(("yt-dlp", "ffmpeg")):
            combo = AnimatedComboBox(); combo.setFixedSize(170, 38)
            combo.addItems(UPDATE_SCHEDULES); _ss(combo, COMBO_QSS)
            i = combo.findText(str(saved.get(name, UPDATE_SCHEDULES[0])))
            combo.setCurrentIndex(i if i >= 0 else 0)
            combo.currentTextChanged.connect(lambda text, nm=name: self._on_schedule_changed(nm, text))
            srows.append(make_row(name, ("top", "bottom")[n], combo))
        card2, cl2 = self._settings_card()
        self._settings_fill_card(cl2, srows)

        body = QWidget(); bl = QVBoxLayout(body); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(12)
        bl.addWidget(card); bl.addWidget(self._upd_note); bl.addSpacing(8)
        bl.addWidget(sched_title); bl.addWidget(sched_sub); bl.addWidget(card2)
        return self._settings_subpage("Update", body)[0]

    def _on_update_button(self, name):
        """Installed -> update it. Not installed -> the same install as the notification's Download button."""
        if self._binary_installed(name):
            self._start_binary_update(name)
        else:
            self._on_binary_download(name)

    def _refresh_update_rows(self):
        """Installed: [Update]. Not installed: [Load from disk...] [Download] and 'Not installed' instead of a version."""
        for name, btn in getattr(self, "_upd_buttons", {}).items():
            installed = self._binary_installed(name)
            self._upd_disk[name].setVisible(not installed)
            if name not in self._updating:
                btn.setText("Update" if installed else "Download")
            if not installed:
                for lbl in self._upd_labels.get(name, []):
                    lbl.setText("Not installed")

    def _refresh_update_info(self):
        """Runs every time the page opens, so a binary that was moved/installed meanwhile is reflected.
        Versions come from background threads, so opening the page never blocks."""
        self._refresh_update_rows()
        for name in ("yt-dlp", "ffmpeg"):
            if self._binary_installed(name):
                self._fetch_version_async(name)
        self._refresh_app_update_row()

    def _fetch_version_async(self, name):
        def work():
            text = _ytdlp_version_text() if name == "yt-dlp" else _ffmpeg_display_text()
            self.signals.binary_version.emit(name, text)
        threading.Thread(target=work, daemon=True).start()

    def _on_binary_version(self, name, text):
        for lbl in getattr(self, "_upd_labels", {}).get(name, []):
            lbl.setText(text)

    def _has_active_downloads(self):
        return any(getattr(d, "status", "") == "active" for d in self._dl_items)

    def _start_binary_update(self, name, auto=False):
        """Returns True if an update was started."""
        if name in self._updating:
            return False
        if name == "ffmpeg" and self._has_active_downloads():
            if not auto:
                self.toast_mgr.show_toast("ffmpeg is in use by a download")
            return False
        self._updating.add(name)
        btn = getattr(self, "_upd_buttons", {}).get(name)
        if btn is not None:
            btn.setEnabled(False); btn.setText("Updating…")
        self.toast_mgr.show_toast("Updating %s" % name, icon_pixmap=self._icons.get("info", QIcon()).pixmap(22, 22))

        def work():
            try:
                status, _ = (_update_ytdlp if name == "yt-dlp" else _update_ffmpeg)()
                self.signals.update_done.emit(name, True, status)
            except Exception as e:
                _log_update_error(name, e)
                self.signals.update_done.emit(name, False, str(e)[:200])
        threading.Thread(target=work, daemon=True).start()
        return True

    def _on_update_done(self, name, ok, info):
        self._updating.discard(name)
        btn = getattr(self, "_upd_buttons", {}).get(name)
        if btn is not None:
            btn.setEnabled(True); btn.setText("Update")
        if not ok:
            self.toast_mgr.show_toast("%s update failed" % name)
            return
        self.settings.setdefault("last_update", {})[name] = time.time()
        self._save_settings()
        msg = "%s updated" % name if info == "updated" else "%s is up to date" % name
        self.toast_mgr.show_toast(msg, icon_pixmap=self._icons.get("check", QIcon()).pixmap(22, 22))
        if name == "yt-dlp" and info == "updated" and hasattr(self, "_upd_note"):
            self._upd_note.setText("yt-dlp updated - restart the app to use the new version.")
        self._fetch_version_async(name)

    def _on_schedule_changed(self, name, text):
        self.settings.setdefault("update_schedule", {})[name] = text
        if text == "On startup" or text in _SCHEDULE_DAYS:
            self.settings.setdefault("last_update", {}).setdefault(name, time.time())   # start the clock now
        self._save_settings()

    def _check_scheduled_updates(self, startup=False):
        """Runs shortly after launch (startup=True) and then hourly while the app
        is open (it lives in the tray, so a long session still updates on time)."""
        sched = self.settings.get("update_schedule", {})
        last = self.settings.setdefault("last_update", {})
        now = time.time()
        for name in ("yt-dlp", "ffmpeg"):
            pol = sched.get(name, UPDATE_SCHEDULES[0])
            if name in self._updating or pol == UPDATE_SCHEDULES[0]:
                continue
            if pol == "On startup":
                due = startup
            else:
                days = _SCHEDULE_DAYS.get(pol)
                if days is None:
                    continue
                if name not in last:
                    last[name] = now; self._save_settings()
                    continue
                due = now - float(last[name]) >= days * 86400
            if due:
                self._start_binary_update(name, auto=True)
