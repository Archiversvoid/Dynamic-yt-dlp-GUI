"""Settings > About: the about page and the Markdown text viewer."""
import theme
from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QCursor, QDesktopServices, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget
from theme import ss as _ss
from src.core.app_info import ABOUT_DISCORD_URL, ABOUT_GITHUB_URL, ABOUT_REDDIT_URL, APP_VERSION
from src.paths import cache_dir, repo_root
from src.ui.styles import CARD_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED


class AboutMixin:
    """Settings > About: the about page and the Markdown text viewer."""

    # ---- page 4: about / page 5: text viewer ----
    def _link_button(self, text, callback):
        b = QPushButton(text); b.setFlat(True)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(b, f"QPushButton {{ background: transparent; border: none; color: {TEAL_ACCENT}; font-size: 16px; padding: 4px 6px; }} QPushButton:hover {{ text-decoration: underline; }}")
        b.clicked.connect(callback)
        return b

    def _social_button(self, icon_name, url, tip):
        b = QPushButton(); b.setFixedSize(38, 38); b.setToolTip(tip)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        icon = self._icons.get(icon_name, QIcon())
        if icon.isNull():
            b.setText(tip)
        else:
            b.setIcon(icon); b.setIconSize(QSize(26, 26))
        b.setProperty("_icon_name", icon_name)
        _ss(b, "QPushButton { background: transparent; border: none; border-radius: 10px; color: #8A8A8A; } QPushButton:hover { background-color: #222222; }")
        b.clicked.connect(lambda checked=False, u=url: QDesktopServices.openUrl(QUrl(u)))
        return b

    def _about_logo_pixmap(self, px):
        """icons/promo.png, rounded, drawn at px x px (decoded at 2x for HiDPI and cached on disk)."""
        pm = theme.image_pixmap("promo", repo_root / "icons", cache_dir, px * 2)
        if pm.isNull():
            return pm
        pm = pm.scaled(px * 2, px * 2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        out = QPixmap(pm.size()); out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath(); path.addRoundedRect(0, 0, pm.width(), pm.height(), 44, 44)
        p.setClipPath(path); p.drawPixmap(0, 0, pm); p.end()
        out.setDevicePixelRatio(2.0)
        return out

    def _build_settings_about_page(self):
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

    def _build_settings_text_page(self):
        self._text_view = QTextBrowser()
        self._text_view.setOpenExternalLinks(True)
        _ss(self._text_view, f"QTextBrowser {{ background-color: {CARD_BG}; color: {TEXT_MAIN}; border: 1px solid #2A2A2A; border-radius: 14px; padding: 16px; font-size: 15px; }}")
        page, self._text_title = self._settings_subpage("", self._text_view, expand=True)
        # the viewer goes back to About, not to the top-level list
        back = page.findChild(QPushButton)
        if back is not None:
            back.clicked.disconnect()
            back.clicked.connect(lambda: self.settings_stack.setCurrentIndex(4))
        return page

    def _open_text_page(self, title, candidates, empty_text=None):
        """Shows the first file that exists, rendered as Markdown."""
        text = None
        for name in candidates:
            p = repo_root / name
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
