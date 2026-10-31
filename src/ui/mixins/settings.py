"""The Settings tab: main list, download folder, feedback."""
import os
from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QCursor, QDesktopServices, QIcon, QTransform
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget)
from theme import ss as _ss
from src.core.app_info import FEEDBACK_BUG_URL, FEEDBACK_FEATURE_URL
from src.paths import default_download_dir, repo_root
from src.ui.components.combo import AnimatedComboBox
from src.ui.components.controls import SettingsRow
from src.ui.styles import CARD_BG, COMBO_QSS, INPUT_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED


class SettingsMixin:
    """The Settings tab: main list, download folder, feedback."""

    # ------------------------------------------------------------------
    # Settings tab. Built on first visit (see _show_tab).
    # Pages in self.settings_stack: 0 list | 1 downloads | 2 update |
    # 3 feedback | 4 about | 5 text viewer (terms / change log)
    # ------------------------------------------------------------------
    def _build_settings_tab(self):
        self._settings_built = True
        root = QVBoxLayout(self.tab_settings)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.settings_stack = QStackedWidget()
        root.addWidget(self.settings_stack)

        # decoded once and shared by every arrow in the tab
        self._settings_arrow = self._icons.get("arrow-right", QIcon()).pixmap(20, 20)
        for page in (self._build_settings_main_page(), self._build_settings_downloads_page(),
                     self._build_settings_update_page(), self._build_settings_feedback_page(),
                     self._build_settings_about_page(), self._build_settings_text_page()):
            self.settings_stack.addWidget(page)

    def _open_settings_page(self, idx):
        if idx == 2: self._refresh_update_info()
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
        """Standard sub-page: back arrow + title, then the body."""
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

    # ---- page 0: the list ----
    def _build_settings_main_page(self):
        page = QWidget()
        lay = QVBoxLayout(page); lay.setContentsMargins(32, 28, 32, 12); lay.setSpacing(20)
        title = QLabel("Settings")
        _ss(title, f"color: {TEXT_MAIN}; font-size: 32px; font-weight: bold; background: transparent;")
        lay.addWidget(title)

        theme = AnimatedComboBox(); theme.setFixedSize(150, 38)
        theme.addItems(["Default", "Dark", "Light"]); _ss(theme, COMBO_QSS)
        i = theme.findText(str(self.settings.get("theme", "Default")))
        theme.setCurrentIndex(i if i >= 0 else 0)
        theme.currentTextChanged.connect(self._on_theme_changed)
        self.theme_combo = theme

        arrow = self._settings_arrow
        spec = [("Interface", "Theme", "top", None, theme, None),
                ("Downloads", "Change where downloads and trims appear", "middle", arrow, None, 1),
                ("Update", "yt-dlp  ·  ffmpeg  ·  App", "middle", arrow, None, 2),
                ("Feedback", "Report a bug  ·  Suggest a feature", "middle", arrow, None, 3),
                ("About", "Terms and conditions  ·  Change log", "bottom", arrow, None, 4)]
        rows = []
        for t, s, pos, arr, ctl, target in spec:
            row = SettingsRow(t, s, pos, arrow_pixmap=arr, control=ctl)
            if target is not None:
                row.clicked.connect(lambda idx=target: self._open_settings_page(idx))
            rows.append(row)
        card, cl = self._settings_card()
        self._settings_fill_card(cl, rows)
        lay.addWidget(card)
        lay.addStretch()
        return page

    # ---- page 1: downloads ----
    def _build_settings_downloads_page(self):
        card, cl = self._settings_card()
        inner = QVBoxLayout(); inner.setContentsMargins(26, 20, 22, 22); inner.setSpacing(6)
        h = QLabel("Download folder")
        _ss(h, f"color: {TEXT_MAIN}; font-size: 19px; background: transparent; border: none;")
        sub = QLabel("Downloads and trims are saved here. Applies to new downloads.")
        _ss(sub, f"color: {TEXT_MUTED}; font-size: 14px; background: transparent; border: none;")
        row = QHBoxLayout(); row.setSpacing(10)
        self.dir_input = QLineEdit(self.settings.get("download_dir") or default_download_dir())
        self.dir_input.setReadOnly(True); self.dir_input.setFixedHeight(40)
        _ss(self.dir_input, f"QLineEdit {{ background-color: {INPUT_BG}; color: {TEXT_MAIN}; border-radius: 10px; padding: 0 14px; border: none; font-size: 14px; }}")
        browse = self._settings_button("Browse", primary=True); browse.clicked.connect(self._settings_choose_dir)
        reset = self._settings_button("Reset");                 reset.clicked.connect(self._settings_reset_dir)
        row.addWidget(self.dir_input, 1); row.addWidget(browse); row.addWidget(reset)
        inner.addWidget(h); inner.addWidget(sub); inner.addSpacing(10); inner.addLayout(row)
        cl.addLayout(inner)
        return self._settings_subpage("Downloads", card)[0]

    def _settings_choose_dir(self):
        start = self.settings.get("download_dir") or default_download_dir()
        d = QFileDialog.getExistingDirectory(self, "Select download folder", start)
        if d: self._apply_download_dir(os.path.normpath(d))

    def _settings_reset_dir(self):
        self._apply_download_dir(default_download_dir())

    def _apply_download_dir(self, d):
        try:
            os.makedirs(d, exist_ok=True)
            ok = os.access(d, os.W_OK)
        except OSError:
            ok = False
        if not ok:
            self.toast_mgr.show_toast("Can't write to that folder")
            return
        self.settings["download_dir"] = d
        self.settings["download_dir_user_set"] = os.path.normcase(os.path.normpath(d)) != os.path.normcase(os.path.normpath(default_download_dir()))
        self._save_settings()
        self.dir_input.setText(d)
        self.toast_mgr.show_toast("Download folder updated", icon_pixmap=self._icons.get("check", QIcon()).pixmap(22, 22))

    # ---- page 3: feedback ----
    def _build_settings_feedback_page(self):
        arrow = self._settings_arrow
        bug = SettingsRow("Report a bug", "", "top", arrow_pixmap=arrow)
        bug.clicked.connect(lambda: self._open_feedback(FEEDBACK_BUG_URL))
        feat = SettingsRow("Suggest a feature", "", "bottom", arrow_pixmap=arrow)
        feat.clicked.connect(lambda: self._open_feedback(FEEDBACK_FEATURE_URL))
        card, cl = self._settings_card()
        self._settings_fill_card(cl, [bug, feat])
        return self._settings_subpage("Feedback", card)[0]

    def _open_feedback(self, url):
        if url: QDesktopServices.openUrl(QUrl(url))
        else: self.toast_mgr.show_toast("Feedback link isn't set up yet")
