import os
import sys
import time
import shutil
import urllib.request
import threading
from pathlib import Path

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QStackedWidget, QFrame, QLineEdit, 
                             QFileDialog, QTextBrowser, QApplication)
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QIcon, QCursor, QTransform, QPixmap, QPainter, QPainterPath, QDesktopServices

import theme
from theme import ss as _ss
from src.ui.styles import (CARD_BG, INPUT_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED, 
                           COMBO_QSS, SettingsRow, AnimatedComboBox)

APP_VERSION = "1.1.0"
FEEDBACK_BUG_URL = "https://github.com/Archiversvoid/Project-Dynamic/issues"
FEEDBACK_FEATURE_URL = "https://github.com/Archiversvoid/Project-Dynamic/issues"
ABOUT_GITHUB_URL = "https://github.com/Archiversvoid/Project-Dynamic/"
ABOUT_REDDIT_URL = "https://www.reddit.com/user/Archivers_void/"
ABOUT_DISCORD_URL = "https://discord.gg/D2x2MVmre"

UPDATE_SCHEDULES = ["Manual only", "On startup", "Every 2 days", "Every week", "Every 15 days"]

class SettingsTab(QWidget):
    def __init__(self, main_win):
        super().__init__(main_win)
        self.win = main_win
        self.repo_root = main_win.repo_root
        self.cache_dir = main_win.cache_dir
        
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.settings_stack = QStackedWidget()
        root.addWidget(self.settings_stack)

        self._settings_arrow = self.win._icons.get("arrow-right", QIcon()).pixmap(20, 20)
        
        self.settings_stack.addWidget(self._build_main_page())
        self.settings_stack.addWidget(self._build_downloads_page())
        self.settings_stack.addWidget(self._build_update_page())
        self.settings_stack.addWidget(self._build_feedback_page())
        self.settings_stack.addWidget(self._build_about_page())
        self.settings_stack.addWidget(self._build_text_page())

    def open_page(self, idx):
        if idx == 2: self.win._refresh_update_info()
        self.settings_stack.setCurrentIndex(idx)

    def _settings_card(self):
        card = QFrame(); card.setObjectName("settingsCard")
        _ss(card, f"QFrame#settingsCard {{ background-color: {CARD_BG}; border: 1px solid #2A2A2A; border-radius: 14px; }}")
        lay = QVBoxLayout(card); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        return card, lay

    def _settings_divider(self):
        d = QFrame(); d.setFixedHeight(1)
        _ss(d, "background-color: #2A2A2A; border: none;")
        return d

    def _settings_fill_card(self, lay, rows):
        for n, row in enumerate(rows):
            lay.addWidget(row)
            if n < len(rows) - 1: lay.addWidget(self._settings_divider())

    def _settings_button(self, text, primary=False):
        b = QPushButton(text); b.setFixedHeight(40); b.setMinimumWidth(104)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if primary:
            _ss(b, f"QPushButton {{ background-color: {TEAL_ACCENT}; color: #0B0B0B; border: none; border-radius: 20px; padding: 0 20px; font-size: 14px; font-weight: bold; }} QPushButton:hover {{ background-color: #1ED6B8; }} QPushButton:disabled {{ background-color: #2E4F4A; color: #7FA9A2; }}")
        else:
            _ss(b, f"QPushButton {{ background: transparent; color: {TEXT_MUTED}; border: 1.2px solid #3A3A3A; border-radius: 20px; padding: 0 20px; font-size: 14px; }} QPushButton:hover {{ border-color: {TEAL_ACCENT}; color: {TEXT_MAIN}; }}")
        return b

    def _settings_subpage(self, title, body, expand=False):
        page = QWidget()
        lay = QVBoxLayout(page); lay.setContentsMargins(32, 28, 32, 16); lay.setSpacing(20)
        head = QHBoxLayout(); head.setSpacing(12)
        back = QPushButton(); back.setFixedSize(40, 40)
        back.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(back, f"QPushButton {{ background: transparent; border: none; border-radius: 10px; color: {TEXT_MUTED}; font-size: 22px; }} QPushButton:hover {{ background-color: #222222; }}")
        if not self._settings_arrow.isNull():
            back.setIcon(QIcon(self._settings_arrow.transformed(QTransform().scale(-1, 1))))
            back.setIconSize(QSize(20, 20)); back.setProperty("_arrow_back", True)
        else:
            back.setText("←")
        back.clicked.connect(lambda: self.settings_stack.setCurrentIndex(0))
        lbl = QLabel(title)
        _ss(lbl, f"color: {TEXT_MAIN}; font-size: 32px; font-weight: bold; background: transparent;")
        head.addWidget(back); head.addWidget(lbl); head.addStretch()
        lay.addLayout(head)
        if expand:
            lay.addWidget(body, 1)
        else:
            lay.addWidget(body); lay.addStretch()
        return page, lbl

    def _build_main_page(self):
        page = QWidget()
        lay = QVBoxLayout(page); lay.setContentsMargins(32, 28, 32, 12); lay.setSpacing(20)
        title = QLabel("Settings")
        _ss(title, f"color: {TEXT_MAIN}; font-size: 32px; font-weight: bold; background: transparent;")
        lay.addWidget(title)

        theme_combo = AnimatedComboBox(); theme_combo.setFixedSize(150, 38)
        theme_combo.addItems(["Default", "Dark", "Light"]); _ss(theme_combo, COMBO_QSS)
        i = theme_combo.findText(str(self.win.settings.get("theme", "Default")))
        theme_combo.setCurrentIndex(i if i >= 0 else 0)
        theme_combo.currentTextChanged.connect(self.win._on_theme_changed)

        arrow = self._settings_arrow
        spec = [("Interface", "Theme", "top", None, theme_combo, None),
                ("Downloads", "Change where downloads and trims appear", "middle", arrow, None, 1),
                ("Update", "yt-dlp  ·  ffmpeg  ·  App", "middle", arrow, None, 2),
                ("Feedback", "Report a bug  ·  Suggest a feature", "middle", arrow, None, 3),
                ("About", "Terms and conditions  ·  Change log", "bottom", arrow, None, 4)]
        rows = []
        for t, s, pos, arr, ctl, target in spec:
            row = SettingsRow(t, s, pos, arrow_pixmap=arr, control=ctl)
            if target is not None:
                row.clicked.connect(lambda idx=target: self.open_page(idx))
            rows.append(row)
        card, cl = self._settings_card()
        self._settings_fill_card(cl, rows)
        lay.addWidget(card)
        lay.addStretch()
        return page

    def _build_downloads_page(self):
        card, cl = self._settings_card()
        inner = QVBoxLayout(); inner.setContentsMargins(26, 20, 22, 22); inner.setSpacing(6)
        h = QLabel("Download folder")
        _ss(h, f"color: {TEXT_MAIN}; font-size: 19px; background: transparent; border: none;")
        sub = QLabel("Downloads and trims are saved here. Applies to new downloads.")
        _ss(sub, f"color: {TEXT_MUTED}; font-size: 14px; background: transparent; border: none;")
        row = QHBoxLayout(); row.setSpacing(10)
        self.dir_input = QLineEdit(self.win.settings.get("download_dir", str(self.repo_root / "downloads")))
        self.dir_input.setReadOnly(True); self.dir_input.setFixedHeight(40)
        _ss(self.dir_input, f"QLineEdit {{ background-color: {INPUT_BG}; color: {TEXT_MAIN}; border-radius: 10px; padding: 0 14px; border: none; font-size: 14px; }}")
        browse = self._settings_button("Browse", primary=True); browse.clicked.connect(self._choose_dir)
        reset = self._settings_button("Reset");                 reset.clicked.connect(self._reset_dir)
        row.addWidget(self.dir_input, 1); row.addWidget(browse); row.addWidget(reset)
        inner.addWidget(h); inner.addWidget(sub); inner.addSpacing(10); inner.addLayout(row)
        cl.addLayout(inner)
        return self._settings_subpage("Downloads", card)[0]

    def _choose_dir(self):
        start = self.win.settings.get("download_dir", str(self.repo_root / "downloads"))
        d = QFileDialog.getExistingDirectory(self, "Select download folder", start)
        if d: self._apply_download_dir(os.path.normpath(d))

    def _reset_dir(self):
        self._apply_download_dir(str(self.repo_root / "downloads"))

    def _apply_download_dir(self, d):
        try:
            os.makedirs(d, exist_ok=True)
            ok = os.access(d, os.W_OK)
        except OSError:
            ok = False
        if not ok:
            self.win.toast_mgr.show_toast("Can't write to that folder")
            return
        self.win.settings["download_dir"] = d
        self.win._save_settings()
        self.dir_input.setText(d)
        self.win.toast_mgr.show_toast("Download folder updated", icon_pixmap=self.win._icons.get("check", QIcon()).pixmap(22, 22))

    def _build_update_page(self):
        self.win._upd_labels = {"yt-dlp": [], "ffmpeg": []}
        self.win._upd_buttons = {}
        self.win._upd_loaded = False

        def make_row(name, pos, control):
            row = SettingsRow(name, "Checking…", pos, control=control)
            self.win._upd_labels[name].append(row.subtitle_lbl)
            return row

        rows = []
        for n, name in enumerate(("yt-dlp", "ffmpeg")):
            btn = self._settings_button("Update", primary=True)
            btn.clicked.connect(lambda checked=False, nm=name: self.win._start_binary_update(nm))
            self.win._upd_buttons[name] = btn
            rows.append(make_row(name, ("top", "bottom")[n], btn))
        card, cl = self._settings_card()
        self._settings_fill_card(cl, rows)

        self.win._upd_note = QLabel("")
        _ss(self.win._upd_note, f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;")

        sched_title = QLabel("Schedule update")
        _ss(sched_title, f"color: {TEXT_MAIN}; font-size: 22px; font-weight: bold; background: transparent;")
        sched_sub = QLabel("Choose when each one updates itself. Skipped while a download is running.")
        _ss(sched_sub, f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;")
        saved = self.win.settings.get("update_schedule", {})
        srows = []
        for n, name in enumerate(("yt-dlp", "ffmpeg")):
            combo = AnimatedComboBox(); combo.setFixedSize(170, 38)
            combo.addItems(UPDATE_SCHEDULES); _ss(combo, COMBO_QSS)
            i = combo.findText(str(saved.get(name, UPDATE_SCHEDULES[0])))
            combo.setCurrentIndex(i if i >= 0 else 0)
            combo.currentTextChanged.connect(lambda text, nm=name: self.win._on_schedule_changed(nm, text))
            srows.append(make_row(name, ("top", "bottom")[n], combo))
        card2, cl2 = self._settings_card()
        self._settings_fill_card(cl2, srows)

        body = QWidget(); bl = QVBoxLayout(body); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(12)
        bl.addWidget(card); bl.addWidget(self.win._upd_note); bl.addSpacing(8)
        bl.addWidget(sched_title); bl.addWidget(sched_sub); bl.addWidget(card2)
        return self._settings_subpage("Update", body)[0]

    def _build_feedback_page(self):
        arrow = self._settings_arrow
        bug = SettingsRow("Report a bug", "", "top", arrow_pixmap=arrow)
        bug.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_BUG_URL)))
        feat = SettingsRow("Suggest a feature", "", "bottom", arrow_pixmap=arrow)
        feat.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_FEATURE_URL)))
        card, cl = self._settings_card()
        self._settings_fill_card(cl, [bug, feat])
        return self._settings_subpage("Feedback", card)[0]

    def _link_button(self, text, callback):
        b = QPushButton(text); b.setFlat(True)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(b, f"QPushButton {{ background: transparent; border: none; color: {TEAL_ACCENT}; font-size: 16px; padding: 4px 6px; }} QPushButton:hover {{ text-decoration: underline; }}")
        b.clicked.connect(callback)
        return b

    def _social_button(self, icon_name, url, tip):
        b = QPushButton(); b.setFixedSize(38, 38); b.setToolTip(tip)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        icon = self.win._icons.get(icon_name, QIcon())
        if icon.isNull():
            b.setText(tip)
        else:
            b.setIcon(icon); b.setIconSize(QSize(26, 26))
        b.setProperty("_icon_name", icon_name)
        _ss(b, "QPushButton { background: transparent; border: none; border-radius: 10px; color: #8A8A8A; } QPushButton:hover { background-color: #222222; }")
        b.clicked.connect(lambda checked=False, u=url: QDesktopServices.openUrl(QUrl(u)))
        return b

    def _about_logo_pixmap(self, px):
        pm = theme.image_pixmap("promo", self.repo_root / "icons", self.cache_dir, px * 2)
        if pm.isNull():
            return pm
        pm = pm.scaled(px * 2, px * 2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        out = QPixmap(pm.size()); out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath(); path.addRoundedRect(0, 0, pm.width(), pm.height(), 44, 44)
        p.setClipPath(path); p.drawPixmap(0, 0, pm); p.end()
        out.setDevicePixelRatio(2.0)
        return out

    def _build_about_page(self):
        body = QWidget()
        bl = QVBoxLayout(body); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(0)

        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(10)
        center = Qt.AlignmentFlag.AlignHCenter
        logo = QLabel(); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = self._about_logo_pixmap(148)
        if pm.isNull():
            logo.hide()
        else:
            logo.setPixmap(pm); logo.setFixedSize(148, 148)
        title = QLabel("Dynamic")
        _ss(title, f"color: {TEXT_MAIN}; font-size: 44px; background: transparent;")
        tag = QLabel("A simple cutting-edge yt-dlp GUI")
        _ss(tag, f"color: {TEXT_MUTED}; font-size: 16px; background: transparent;")
        ver = QLabel("version " + APP_VERSION)
        _ss(ver, f"color: {TEXT_MAIN}; font-size: 15px; background-color: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 16px; padding: 6px 22px;")

        links = QHBoxLayout(); links.setSpacing(6); links.setContentsMargins(0, 0, 0, 0)
        dot = QLabel("·"); _ss(dot, f"color: {TEXT_MUTED}; font-size: 16px; background: transparent;")
        links.addWidget(self._link_button("Terms and conditions", lambda: self._open_text_page(
            "Terms and conditions", ("TERMS.txt", "TERMS.md", "terms.txt", "terms.md"))))
        links.addWidget(dot)
        links.addWidget(self._link_button("Change log", lambda: self._open_text_page(
            "Change log", ("CHANGELOG.md", "CHANGELOG.txt", "changelog.md", "changelog.txt"), "Currently no changes")))
        links_row = QWidget(); links_row.setLayout(links)

        for w in (logo, title, tag, ver):
            col.addWidget(w, alignment=center)
        col.addSpacing(8)
        col.addWidget(links_row, alignment=center)
        bl.addStretch(1); bl.addLayout(col); bl.addStretch(2)

        foot = QHBoxLayout(); foot.setContentsMargins(4, 0, 0, 0); foot.setSpacing(8)
        copy = QLabel("©2026 Archivers_void")
        _ss(copy, f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;")
        foot.addWidget(copy); foot.addStretch()
        for name, url, tip in (("github", ABOUT_GITHUB_URL, "GitHub"), ("reddit", ABOUT_REDDIT_URL, "Reddit"),
                               ("discord", ABOUT_DISCORD_URL, "Discord")):
            foot.addWidget(self._social_button(name, url, tip))
        bl.addLayout(foot)
        return self._settings_subpage("About", body, expand=True)[0]

    def _build_text_page(self):
        self._text_view = QTextBrowser()
        self._text_view.setOpenExternalLinks(True)
        _ss(self._text_view, f"QTextBrowser {{ background-color: {CARD_BG}; color: {TEXT_MAIN}; border: 1px solid #2A2A2A; border-radius: 14px; padding: 16px; font-size: 15px; }}")
        page, self._text_title = self._settings_subpage("", self._text_view, expand=True)
        back = page.findChild(QPushButton)
        if back is not None:
            back.clicked.disconnect()
            back.clicked.connect(lambda: self.settings_stack.setCurrentIndex(4))
        return page

    def _open_text_page(self, title, candidates, empty_text=None):
        text = None
        for name in candidates:
            p = self.repo_root / name
            if p.exists():
                try:
                    text = p.read_text(encoding="utf-8", errors="replace"); break
                except OSError:
                    pass
        if text is None or not text.strip():
            text = empty_text or ("Nothing here yet.\n\nAdd a file named %s next to main.py and its contents will show up here." % candidates[0])
        self._text_view.document().setDefaultStyleSheet("a { color: %s; }" % theme.accent_text())
        self._text_view.setMarkdown(text)
        self._text_view.verticalScrollBar().setValue(0)
        self._text_title.setText(title)
        self.settings_stack.setCurrentIndex(5)