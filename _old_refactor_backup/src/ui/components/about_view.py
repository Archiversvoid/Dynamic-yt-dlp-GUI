from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPainterPath, QCursor, QDesktopServices

import theme
from theme import ss as _ss
from src.ui.styles import CARD_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED, SettingsRow

APP_VERSION = "1.1.0"
FEEDBACK_BUG_URL = "https://github.com/Archiversvoid/Project-Dynamic/issues"
FEEDBACK_FEATURE_URL = "https://github.com/Archiversvoid/Project-Dynamic/issues"
ABOUT_GITHUB_URL = "https://github.com/Archiversvoid/Project-Dynamic/"
ABOUT_REDDIT_URL = "https://reddit.com/users/Archivers_void"
ABOUT_DISCORD_URL = "https://discord.gg/D2x2MVmre"

class AboutSectionHelper:
    @staticmethod
    def build_feedback_page(settings_tab, arrow_pixmap):
        bug = SettingsRow("Report a bug", "", "top", arrow_pixmap=arrow_pixmap)
        bug.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_BUG_URL)))
        feat = SettingsRow("Suggest a feature", "", "bottom", arrow_pixmap=arrow_pixmap)
        feat.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_FEATURE_URL)))
        card, cl = settings_tab._settings_card()
        settings_tab._settings_fill_card(cl, [bug, feat])
        return settings_tab._settings_subpage("Feedback", card)[0]

    @staticmethod
    def build_about_page(settings_tab, arrow_pixmap):
        body = QWidget()
        bl = QVBoxLayout(body); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(0)

        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(10)
        center = Qt.AlignmentFlag.AlignHCenter
        logo = QLabel(); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        pm = theme.image_pixmap("promo", settings_tab.repo_root / "icons", settings_tab.cache_dir, 296)
        if pm.isNull():
            logo.hide()
        else:
            pm = pm.scaled(296, 296, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            out = QPixmap(pm.size()); out.fill(Qt.GlobalColor.transparent)
            p = QPainter(out); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath(); path.addRoundedRect(0, 0, pm.width(), pm.height(), 44, 44)
            p.setClipPath(path); p.drawPixmap(0, 0, pm); p.end()
            out.setDevicePixelRatio(2.0)
            logo.setPixmap(out); logo.setFixedSize(148, 148)

        title = QLabel("Dynamic")
        _ss(title, f"color: {TEXT_MAIN}; font-size: 44px; background: transparent;")
        tag = QLabel("A simple cutting-edge yt-dlp GUI")
        _ss(tag, f"color: {TEXT_MUTED}; font-size: 16px; background: transparent;")
        ver = QLabel("version " + APP_VERSION)
        _ss(ver, f"color: {TEXT_MAIN}; font-size: 15px; background-color: #1A1A1A; border: 1px solid #2A2A2A; border-radius: 16px; padding: 6px 22px;")

        links = QHBoxLayout(); links.setSpacing(6); links.setContentsMargins(0, 0, 0, 0)
        dot = QLabel("·"); _ss(dot, f"color: {TEXT_MUTED}; font-size: 16px; background: transparent;")
        
        def link_btn(text, cb):
            b = QPushButton(text); b.setFlat(True)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            _ss(b, f"QPushButton {{ background: transparent; border: none; color: {TEAL_ACCENT}; font-size: 16px; padding: 4px 6px; }} QPushButton:hover {{ text-decoration: underline; }}")
            b.clicked.connect(cb)
            return b

        links.addWidget(link_btn("Terms and conditions", lambda: settings_tab._open_text_page(
            "Terms and conditions", ("TERMS.txt", "TERMS.md", "terms.txt", "terms.md"))))
        links.addWidget(dot)
        links.addWidget(link_btn("Change log", lambda: settings_tab._open_text_page(
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

        def social_btn(icon_name, url, tip):
            b = QPushButton(); b.setFixedSize(38, 38); b.setToolTip(tip)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            icon = settings_tab.win._icons.get(icon_name, QIcon())
            if not icon.isNull():
                b.setIcon(icon); b.setIconSize(QSize(26, 26))
            else:
                b.setText(tip)
            _ss(b, "QPushButton { background: transparent; border: none; border-radius: 10px; color: #8A8A8A; } QPushButton:hover { background-color: #222222; }")
            b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
            return b

        for name, url, tip in (("github", ABOUT_GITHUB_URL, "GitHub"), ("reddit", ABOUT_REDDIT_URL, "Reddit"), ("discord", ABOUT_DISCORD_URL, "Discord")):
            foot.addWidget(social_btn(name, url, tip))
        bl.addLayout(foot)
        return settings_tab._settings_subpage("About", body, expand=True)[0]