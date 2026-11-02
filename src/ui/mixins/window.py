"""The main window: settings file, tray icon, titlebar, theme switching, sidebar, tab switching."""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import theme
from urllib.parse import urlparse
from PySide6.QtCore import QEasingCurve, QSize, Qt, QTimer, QUrl, QVariantAnimation
from PySide6.QtGui import QAction, QColor, QCursor, QDesktopServices, QIcon, QPalette, QTransform
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QStackedWidget, QStyle,
    QSystemTrayIcon, QVBoxLayout, QWidget)
from theme import qc as _qc, ss as _ss
from src.core.downloader import _site_name
from src.core.models import DownloadItem
from src.core.prewarm import FilePrewarm, collect_multimedia_files
from src.paths import cache_dir, default_download_dir, favicon_dir, ICON_PATH, repo_root
from src.ui.components.navigation import FilterTab, SidebarNavButton
from src.ui.styles import (
    BG_DARK, CARD_BG, CARD_INNER_BG, SIDEBAR_DARK, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED)


class WindowMixin:
    """The main window: settings file, tray icon, titlebar, theme switching, sidebar, tab switching."""

    def _load_settings(self):
        default_settings = {
            "download_dir": default_download_dir(),
            "sidebar_collapsed": False,  # Added default state
            "theme": "Default",
        }
        settings_path = repo_root / "settings.json"
        if settings_path.exists():
            try:
                with open(settings_path, "r") as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
            except Exception:
                pass
        # The old default was <app>/downloads. If that is what is saved and the user never picked it
        # themselves, move to the system Downloads folder (a folder the user chose is left alone).
        norm = lambda q: os.path.normcase(os.path.normpath(str(q or "")))
        if not default_settings.get("download_dir_user_set") and norm(default_settings.get("download_dir")) == norm(repo_root / "downloads"):
            default_settings["download_dir"] = default_download_dir()
        return default_settings

    def _save_settings(self):
        try:
            with open(repo_root / "settings.json", "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception: pass

    def _restore_and_show_tab(self, idx):
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self._show_tab(idx)

    def _setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        app_icon = QIcon(ICON_PATH)
        self.tray_icon = QSystemTrayIcon(app_icon, self)
        if not app_icon.isNull(): self.tray_icon.setIcon(app_icon)
        else: self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        
        self.tray_menu = QMenu(self)

        action_dynamic = QAction("Dynamic", self)
        action_dynamic.triggered.connect(lambda: self._restore_and_show_tab(0))
        self.tray_menu.addAction(action_dynamic)
        
        action_trimload = QAction("TrimLoad", self)
        action_trimload.triggered.connect(lambda: self._restore_and_show_tab(1))
        self.tray_menu.addAction(action_trimload)
        
        action_downloads = QAction("Downloads", self)
        action_downloads.triggered.connect(lambda: self._restore_and_show_tab(2))
        self.tray_menu.addAction(action_downloads)
        
        self.tray_menu.addSeparator()
        
        action_quit = QAction("Quit", self)
        action_quit.triggered.connect(QApplication.instance().quit)
        self.tray_menu.addAction(action_quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        self.tray_icon.messageClicked.connect(self._on_tray_message_clicked)

    def _on_tray_message_clicked(self):
        self._restore_and_show_tab(2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast_mgr"): self.toast_mgr.update_positions()

    def _open_qurl(self, qurl): QDesktopServices.openUrl(qurl)

    def _reveal_in_explorer(self, item):
        path = getattr(item, "final_path", None)
        if path and os.path.isfile(path):
            self._reveal_file(path)
            return
        if os.path.isdir(item.out_dir):
            self._open_qurl(QUrl.fromLocalFile(item.out_dir))
        else:
            self.toast_mgr.show_toast("That folder no longer exists")

    def _reveal_file(self, path):
        path = os.path.normpath(path)
        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", path])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", path])
            else:
                folder = os.path.dirname(path)
                for fm, args in (
                    ("nautilus", ["--select", path]),
                    ("dolphin", ["--select", path]),
                    ("nemo", [path]),
                    ("pcmanfm", [folder]),
                    ("thunar", [folder]),
                ):
                    if shutil.which(fm):
                        subprocess.Popen([fm] + args)
                        return
                self._open_qurl(QUrl.fromLocalFile(folder))
        except Exception:
            folder = os.path.dirname(path)
            if os.path.isdir(folder):
                self._open_qurl(QUrl.fromLocalFile(folder))

    def _load_icons(self):
        self._icons = {}
        for name in ["home", "scissors", "downloads", "settings", "pause", "play", "trash", "trash red", "retry", "check", "collapse", "expand", "arrow-right", "info", "github", "reddit", "discord"]:
            self._icons[name] = theme.icon(name, repo_root / "icons", cache_dir)

    def _load_downloads(self):
        file_path = repo_root / "downloads.json"
        if file_path.exists():
            try:
                with open(file_path, "r") as f:
                    for d in json.load(f):
                        fav_p = d.get("fav_path")
                        if not fav_p or not os.path.exists(fav_p):
                            parsed = urlparse(d["url"])
                            possible_path = favicon_dir / f"{parsed.netloc or 'unknown'}.png"
                            fav_p = str(possible_path) if possible_path.exists() else None
                        it = DownloadItem(
                            url=d["url"], title=d["title"], channel=d["channel"], thumb_path=d.get("thumb_path"), 
                            out_dir=d["out_dir"], is_audio=d["is_audio"], selected_fid=d["selected_fid"], 
                            duration_str=d["duration_str"], site_name=_site_name(d["url"]), 
                            thumb_url=d.get("thumb_url"), fav_path=fav_p, 
                            start_time=d.get("start_time"), end_time=d.get("end_time"),
                            audio_bitrate=d.get("audio_bitrate")
                        )
                        it.status, it.percent, it.total_size, it.downloaded = d["status"], d.get("percent", 0.0), d.get("total_size", ""), d.get("downloaded", "")
                        it.error_msg = d.get("error_msg", "")
                        it.final_path = d.get("final_path")
                        if it.status == "done": it._notified = True
                        self._dl_items.append(it)
            except Exception: pass

    def closeEvent(self, event):
        # Save current sidebar state to settings dictionary
        self.settings["sidebar_collapsed"] = self._sidebar_collapsed
        self._save_settings()

        data = []
        for item in self._dl_items:
            # ... (keep your existing download serialization code here)
            data.append({
                "url": item.url, "title": item.title, "channel": item.channel, "out_dir": item.out_dir, "is_audio": item.is_audio,
                "selected_fid": item.selected_fid, "duration_str": item.duration_str, "status": "paused" if item.status == "active" else item.status,
                "percent": item.percent, "total_size": item.total_size, "downloaded": item.downloaded, "thumb_path": item.thumb_path,
                "thumb_url": item.thumb_url, "fav_path": getattr(item, 'fav_path', None), "start_time": item.start_time, "end_time": item.end_time,
                "audio_bitrate": getattr(item, "audio_bitrate", None),
                "error_msg": item.error_msg,
                "final_path": item.final_path
            })
        try:
            with open(repo_root / "downloads.json", "w") as f: json.dump(data, f)
        except Exception:
            pass
        event.accept()

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QFrame()
        self._sidebar_expanded_w = 210
        self._sidebar_collapsed_w = 68

        # Load the saved state from settings
        self._sidebar_collapsed = self.settings.get("sidebar_collapsed", False)

        # Set initial layout widths matching the saved state
        initial_width = self._sidebar_collapsed_w if self._sidebar_collapsed else self._sidebar_expanded_w
        self.sidebar.setFixedWidth(initial_width)
        _ss(self.sidebar, f"QFrame {{ background-color: {SIDEBAR_DARK}; border: none; }}")

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 28, 12, 20)
        sidebar_layout.setSpacing(12)
        self._sidebar_layout = sidebar_layout

        self.menu_btn = QPushButton()
        # Set icon matching the saved state
        initial_icon = "expand" if self._sidebar_collapsed else "collapse"
        self.menu_btn.setIcon(self._icons.get(initial_icon, QIcon()))
        self.menu_btn.setIconSize(QSize(22, 22))
        self.menu_btn.setFixedSize(44, 32)
        self.menu_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self.menu_btn, "QPushButton { background: transparent; border: none; border-radius: 8px; } QPushButton:hover { background-color: #222222; }")
        self.menu_btn.clicked.connect(self._toggle_sidebar)
        sidebar_layout.addWidget(self.menu_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        sidebar_layout.addSpacing(20)

        self._sidebar_anim = QVariantAnimation(self)
        self._sidebar_anim.setDuration(220)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._sidebar_anim.valueChanged.connect(lambda v: self.sidebar.setFixedWidth(int(v)))

        self.nav_btns = []
        nav_items = [("Home", "home", 0), ("TrimLoad", "scissors", 1), ("Downloads", "downloads", 2), ("Settings", "settings", 3)]
        for name, icon_name, idx in nav_items:
            btn = SidebarNavButton(name, self._icons.get(icon_name, QIcon()), idx, is_active=(idx == 0))
            btn._icon_name = icon_name
            
            # Apply initial collapse status to each button without animation on launch
            btn.set_collapsed(self._sidebar_collapsed, animate=False)
            
            btn.clicked.connect(self._show_tab)
            sidebar_layout.addWidget(btn)
            self.nav_btns.append(btn)
            
        sidebar_layout.addStretch()
        main_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        _ss(self.stack, f"background-color: {BG_DARK};")
        
        self.tab_home = QWidget()
        self._build_home_tab()
        self.stack.addWidget(self.tab_home)

        self.tab_trim = QWidget()
        self.trim_layout = QVBoxLayout(self.tab_trim)
        self.trim_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.tab_trim)
        self._trim_loaded = False
        self._trim_building = False        # TrimLoad build in progress (waiting for the pre-warm, or constructing)
        self._constructing_trim = False    # True only during the short, blocking construction itself
        self._trim_placeholder = None      # the "Loading TrimLoad…" label shown while waiting
        self._prewarm = None               # background reader that caches the multimedia DLLs
        
        self.tab_dl = QWidget()
        self._build_downloads_tab()
        self.stack.addWidget(self.tab_dl)

        self.tab_settings = QWidget()
        self._settings_built = False   # built on first visit (see _show_tab) so it costs nothing at startup
        self.stack.addWidget(self.tab_settings)

        main_layout.addWidget(self.stack)

    def _on_theme_changed(self, text):
        self.settings["theme"] = text
        self._save_settings()
        # deferred: the combo that fired this is itself about to be restyled
        QTimer.singleShot(0, lambda: self._apply_theme(text))

    # ------------------------------------------------------------------
    # Theme engine (see theme.py for how colors are mapped)
    # ------------------------------------------------------------------
    def _apply_palette(self):
        P = QPalette.ColorRole
        pal = QPalette(QApplication.instance().palette())
        for role, color in ((P.Window, _qc(BG_DARK, "bg")), (P.WindowText, _qc(TEXT_MAIN, "text")),
                            (P.Base, _qc(CARD_BG, "bg")), (P.AlternateBase, _qc(CARD_INNER_BG, "bg")),
                            (P.Text, _qc(TEXT_MAIN, "text")), (P.Button, _qc(CARD_BG, "bg")),
                            (P.ButtonText, _qc(TEXT_MAIN, "text")), (P.ToolTipBase, _qc("#242424", "bg")),
                            (P.ToolTipText, _qc(TEXT_MAIN, "text")), (P.PlaceholderText, _qc(TEXT_MUTED, "text")),
                            (P.Highlight, _qc(TEAL_ACCENT)), (P.HighlightedText, _qc("#000000")),
                            (P.Link, QColor(theme.accent_text()))):
            pal.setColor(role, color)
        QApplication.instance().setPalette(pal)

    def _apply_theme(self, setting=None):
        """Switch theme live. Every widget styled through _ss re-applies its
        stored source stylesheet in the new mode; icons, painted widgets and
        the title bar are refreshed explicitly."""
        setting = setting or self.settings.get("theme", "Default")
        changed = theme.set_mode(theme.resolve(setting))
        self._follow_system_theme(str(setting) == "Default")
        if not changed:
            return
        self._apply_palette()
        self._load_icons()
        self.setUpdatesEnabled(False)
        try:
            widgets = QApplication.instance().allWidgets()
            for w in widgets:
                theme.restyle(w)
            arrow = self._icons.get("arrow-right", QIcon()).pixmap(20, 20)
            if getattr(self, "_settings_built", False):
                self._settings_arrow = arrow
            for w in widgets:
                if isinstance(w, (FilterTab, SidebarNavButton)):
                    w.apply_theme()
                if isinstance(w, SidebarNavButton) and getattr(w, "_icon_name", None):
                    w.set_icon(self._icons.get(w._icon_name, QIcon()))
                elif isinstance(w, QPushButton):
                    n = w.property("_icon_name")
                    if isinstance(n, str):
                        w.setIcon(self._icons.get(n, QIcon()))
                    elif w.property("_arrow_back") and not arrow.isNull():
                        w.setIcon(QIcon(arrow.transformed(QTransform().scale(-1, 1))))
                elif isinstance(w, QLabel) and w.property("_arrow") and not arrow.isNull():
                    w.setPixmap(arrow)
            self.menu_btn.setIcon(self._icons.get("expand" if self._sidebar_collapsed else "collapse", QIcon()))
            tw = getattr(self, "trim_widget", None)
            if tw is not None and hasattr(tw, "apply_theme"):
                tw.apply_theme()
            for w in widgets:
                w.update()
        finally:
            self.setUpdatesEnabled(True)
        self._apply_titlebar_theme()

    def _follow_system_theme(self, enable):
        """With Theme = Default the app follows Windows' own light/dark setting live."""
        if not enable or getattr(self, "_sys_theme_hooked", False):
            return
        try:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.styleHints().colorSchemeChanged.connect(lambda *_: self._on_system_scheme_changed())
            self._sys_theme_hooked = True
        except Exception:
            pass

    def _on_system_scheme_changed(self):
        if str(self.settings.get("theme", "Default")) == "Default":
            QTimer.singleShot(150, lambda: self._apply_theme("Default"))

    def _apply_titlebar_theme(self):
        """The native title bar is always the light (white) one, whichever app theme is selected.
        (It used to follow the theme, which made it black in dark mode.) Applied before the window is
        first shown, and the frame is repainted at once - Windows otherwise only refreshes the caption
        colour the next time the window is activated."""
        if sys.platform != "win32":
            return
        try:
            val = ctypes.c_int(0)                                   # DWMWA_USE_IMMERSIVE_DARK_MODE = off
            hwnd = int(self.winId())
            for attr in (20, 19):                                   # 20 on current Windows 10/11, 19 on older builds
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                    break
            user32 = ctypes.windll.user32
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0037)        # NOMOVE | NOSIZE | NOZORDER | NOACTIVATE | FRAMECHANGED
            user32.RedrawWindow(hwnd, None, None, 0x0501)           # RDW_FRAME | RDW_INVALIDATE | RDW_UPDATENOW
        except Exception:
            pass

    def showEvent(self, e):
        super().showEvent(e)
        self._apply_titlebar_theme()
        if not getattr(self, "_sched_started", False):
            self._sched_started = True
            QTimer.singleShot(6000, lambda: self._check_scheduled_updates(startup=True))
            QTimer.singleShot(1500, self._start_prewarm)
            try:                                                    # Windows switching its own light/dark mode must not turn the title bar dark again
                from PySide6.QtGui import QGuiApplication
                QGuiApplication.styleHints().colorSchemeChanged.connect(lambda *_: QTimer.singleShot(200, self._apply_titlebar_theme))
            except Exception:
                pass
            QTimer.singleShot(2500, self._warm_up_ytdlp)
            self._sched_timer = QTimer(self)
            self._sched_timer.setInterval(3600 * 1000)
            self._sched_timer.timeout.connect(self._check_scheduled_updates)
            self._sched_timer.start()

    def _toggle_sidebar(self):
        if getattr(self, "_constructing_trim", False):
            return        # ignore clicks in the middle of the TrimLoad build
        self._sidebar_collapsed = not self._sidebar_collapsed
        collapsed = self._sidebar_collapsed

        self._sidebar_anim.stop()
        self._sidebar_anim.setStartValue(self.sidebar.width())
        self._sidebar_anim.setEndValue(self._sidebar_collapsed_w if collapsed else self._sidebar_expanded_w)

        self.menu_btn.setIcon(self._icons.get("expand" if collapsed else "collapse", QIcon()))

        if collapsed:
            for btn in self.nav_btns:
                btn.begin_collapse_fade()
        else:
            for btn in self.nav_btns:
                btn.begin_expand_layout()

        self._sidebar_anim.start()

    def _show_tab(self, idx):
        if getattr(self, "_constructing_trim", False):
            return        # a click that arrived in the middle of the TrimLoad build (see the notes below)
        if self.stack.currentIndex() == idx:
            return

        if idx == 1 and not getattr(self, "_trim_loaded", False):
            self._begin_trim_build(show_placeholder=True)      # asynchronous: the window stays responsive meanwhile

        if idx == 3 and not getattr(self, "_settings_built", False):
            self._build_settings_tab()

        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_btns):
            btn.set_active(i == idx)
        if idx == 2: self._ensure_dl_list_loaded()

    # ------------------------------------------------------------------
    # Building the TrimLoad tab.
    #
    # It loads the Qt multimedia stack (an FFmpeg backend, ~100 MB of DLLs) and opens the audio
    # device. Right after a boot nothing is in the OS file cache, so doing that inside the click
    # froze the window ("Not Responding"). Worse, Windows' audio/COM code pumps messages during
    # the build, so clicks that arrived meanwhile were handled IN THE MIDDLE of it: a second click
    # on TrimLoad started a second build inside the first (_trim_loaded was only set afterwards),
    # and the sidebar button ran its animation against a half-built tab - a total freeze.
    #
    # Now: (1) shortly after launch the multimedia files are read into the file cache from a
    # background thread; (2) a click on TrimLoad shows a "Loading" page at once and WAITS (by timer,
    # window responsive) for that to finish, then builds - which is quick with warm files;
    # (3) clicks during the short build itself are ignored; (4) once everything is cached and the
    # user is idle on Home, the tab is built in advance so the first click is instant.
    # ------------------------------------------------------------------
    def _start_prewarm(self, prebuild=True):
        if getattr(self, "_prewarm", None) is None:
            self._prewarm = FilePrewarm(collect_multimedia_files())
            self._prewarm.start()
        if prebuild:
            self._prebuild_polls = 0
            QTimer.singleShot(500, self._poll_prewarm_for_prebuild)

    def _poll_prewarm_for_prebuild(self):
        pw = self._prewarm
        if pw.running():
            self._prebuild_polls += 1
            if self._prebuild_polls < 240:                      # stop polling after about two minutes
                QTimer.singleShot(500, self._poll_prewarm_for_prebuild)
            return
        if pw.bytes_read > 0:                                   # the files really are cached now
            QTimer.singleShot(1500, self._maybe_prebuild_trim)

    def _maybe_prebuild_trim(self, tries=0):
        if getattr(self, "_trim_loaded", False) or getattr(self, "_trim_building", False):
            return
        busy = self.stack.currentIndex() != 0 or any(getattr(d, "status", "") == "active" for d in self._dl_items)
        if busy:                                                # don't build while the user is doing something else
            if tries < 12:
                QTimer.singleShot(5000, lambda: self._maybe_prebuild_trim(tries + 1))
            return
        self._begin_trim_build(show_placeholder=False)

    def _ensure_trim_placeholder(self):
        if getattr(self, "_trim_loaded", False):
            return
        ph = getattr(self, "_trim_placeholder", None)
        if ph is None:
            ph = QLabel("Loading TrimLoad…")
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _ss(ph, f"color: {TEXT_MUTED}; font-size: 16px; background: transparent;")
            self.trim_layout.addWidget(ph)
            self._trim_placeholder = ph
        else:
            ph.setText("Loading TrimLoad…")

    def _begin_trim_build(self, show_placeholder=True):
        if show_placeholder:
            self._ensure_trim_placeholder()
        if getattr(self, "_trim_building", False):
            return                                              # already on its way: extra clicks must not start another build
        self._trim_building = True
        if getattr(self, "_prewarm", None) is None:
            self._start_prewarm(prebuild=False)                 # clicked before the idle pre-warm began
        self._wait_then_build_trim(time.monotonic())

    def _wait_then_build_trim(self, started):
        pw = getattr(self, "_prewarm", None)
        if pw is not None and pw.running() and time.monotonic() - started < 40:
            QTimer.singleShot(80, lambda: self._wait_then_build_trim(started))
            return
        QTimer.singleShot(0, self._construct_trim_tab)          # let the "Loading" page paint first

    def _construct_trim_tab(self):
        self._constructing_trim = True                          # _show_tab and _toggle_sidebar ignore clicks until this ends
        QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        try:
            from src.ui.trim import TrimLoadTab
            tab = TrimLoadTab(self)
            if hasattr(tab, "request_trim"):
                tab.request_trim.connect(self._handle_trim_request)
            ph = getattr(self, "_trim_placeholder", None)
            if ph is not None:
                self.trim_layout.removeWidget(ph)
                ph.deleteLater()
                self._trim_placeholder = None
            self.trim_widget = tab
            self.trim_layout.addWidget(tab)
            self._trim_loaded = True
        except Exception as e:
            ph = getattr(self, "_trim_placeholder", None)       # a readable message instead of a blank page; leaving and re-opening the tab retries
            if ph is not None:
                ph.setText("Couldn't load TrimLoad: %s" % str(e)[:160])
            try:
                import traceback
                d = repo_root / "logs"; d.mkdir(parents=True, exist_ok=True)
                with open(d / "ui_timing.log", "a", encoding="utf-8") as f:
                    f.write(traceback.format_exc() + "\n")
            except Exception:
                pass
        finally:
            QApplication.restoreOverrideCursor()
            self._constructing_trim = False
            self._trim_building = False

    def _handle_trim_request(self, url, start, end):
        self._show_tab(0)
        self.url_entry.setText(url)
        self._process_link(url, start_time=start, end_time=end)
