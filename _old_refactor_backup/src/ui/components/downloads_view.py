import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QProgressBar, QSizePolicy, QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, QSize, QTimer, QUrl
from PySide6.QtGui import QIcon, QPixmap, QCursor, QColor

import theme
from theme import ss as _ss
from src.ui.styles import (CARD_BG, CARD_INNER_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED, 
                           ERROR_BG, ModernScrollArea, FilterTabBar, SkeletonBox, get_rounded_pixmap)

class DownloadsTab(QWidget):
    def __init__(self, main_win):
        super().__init__(main_win)
        self.win = main_win
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(32, 28, 32, 12)
        top_layout.setSpacing(16)

        lbl = QLabel("Downloads")
        _ss(lbl, f"color: {TEXT_MAIN}; font-size: 32px; font-weight: bold;")
        top_layout.addWidget(lbl)

        filters = ["All", "Active", "Paused", "Done", "Failed"]
        self.filter_tab_bar = FilterTabBar(filters)
        self.filter_tab_bar.filter_changed.connect(self._on_filter_changed)
        top_layout.addWidget(self.filter_tab_bar, alignment=Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(top_container)

        self.scroll = ModernScrollArea()
        self.scroll_content = QWidget()
        _ss(self.scroll_content, "background-color: transparent;")
        
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(32, 10, 32, 16)
        self.scroll_layout.setSpacing(16)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll, 1)
        self._dl_empty_label = None

    def _on_filter_changed(self, f_name):
        if self.win._dl_tab_filter == f_name: return
        self.win._dl_tab_filter = f_name
        self.sync_dl_filter_view()

    def full_rebuild_dl_cards(self):
        while self.scroll_layout.count():
            it = self.scroll_layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.win._dl_cards = {}
        for item in reversed(self.win._dl_items):
            self.scroll_layout.addWidget(self.build_dl_card_widget(item))
        self._dl_empty_label = QLabel("No downloads here")
        _ss(self._dl_empty_label, f"color: {TEXT_MUTED}; font-size: 15px;")
        self._dl_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_layout.addWidget(self._dl_empty_label)
        self.scroll_layout.addStretch()
        self.win._dl_list_dirty = False
        self.sync_dl_filter_view()

    def sync_dl_filter_view(self):
        counts = {
            "All": len(self.win._dl_items),
            "Active": sum(1 for d in self.win._dl_items if d.status == "active"),
            "Paused": sum(1 for d in self.win._dl_items if d.status == "paused"),
            "Done": sum(1 for d in self.win._dl_items if d.status == "done"),
            "Failed": sum(1 for d in self.win._dl_items if d.status == "failed")
        }
        self.filter_tab_bar.update_counts(counts)
        visible = 0
        for item in self.win._dl_items:
            card = self.win._dl_cards.get(item.id)
            if not card: continue
            match = self.win._dl_tab_filter == "All" or item.status == self.win._dl_tab_filter.lower()
            if card.isVisible() != match: card.setVisible(match)
            if match: visible += 1
        if self._dl_empty_label is not None:
            self._dl_empty_label.setVisible(visible == 0)
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded if visible >= 3 else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

    def show_dl_skeleton(self):
        while self.scroll_layout.count():
            it = self.scroll_layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        skeleton_count = min(max(len(self.win._dl_items), 1), 5)
        for _ in range(skeleton_count):
            self.scroll_layout.addWidget(self._build_skeleton_card())
        self.scroll_layout.addStretch()

    def _build_skeleton_card(self):
        wrapper = QWidget()
        wrap_v = QVBoxLayout(wrapper); wrap_v.setContentsMargins(0, 0, 0, 14); wrap_v.setSpacing(0)

        card = QFrame(); card.setFixedHeight(180)
        _ss(card, f"QFrame {{ background-color: {CARD_BG}; border: 1px solid #333333; border-radius: 14px; }}")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24); shadow.setColor(QColor(0, 0, 0, 130)); shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        main_h = QHBoxLayout(card); main_h.setContentsMargins(16, 16, 16, 16); main_h.setSpacing(20)
        main_h.addWidget(SkeletonBox(240, 135, radius=14))

        right_v = QVBoxLayout(); right_v.setContentsMargins(0, 6, 0, 6); right_v.setSpacing(14)
        right_v.addWidget(SkeletonBox(None, 22, radius=4))
        meta_row = QHBoxLayout(); meta_row.setSpacing(10)
        meta_row.addWidget(SkeletonBox(90, 13, radius=4))
        meta_row.addWidget(SkeletonBox(60, 13, radius=4))
        meta_row.addWidget(SkeletonBox(70, 13, radius=4))
        meta_row.addStretch()
        right_v.addLayout(meta_row)
        right_v.addStretch()

        ctrl_row = QHBoxLayout(); ctrl_row.setSpacing(12)
        ctrl_row.addWidget(SkeletonBox(36, 36, radius=18))
        bar_col = QVBoxLayout(); bar_col.setSpacing(8)
        bar_col.addWidget(SkeletonBox(None, 4, radius=2))
        stats_row = QHBoxLayout()
        stats_row.addWidget(SkeletonBox(160, 12, radius=4))
        stats_row.addStretch()
        stats_row.addWidget(SkeletonBox(90, 12, radius=4))
        bar_col.addLayout(stats_row)
        ctrl_row.addLayout(bar_col)
        right_v.addLayout(ctrl_row)

        main_h.addLayout(right_v)
        wrap_v.addWidget(card)
        return wrapper

    def build_dl_card_widget(self, item):
        card = QFrame(); card.setFixedHeight(180)
        _ss(card, f"QFrame {{ background-color: {CARD_BG}; border: 1px solid #2A2A2A; border-radius: 14px; }}")
        main_h = QHBoxLayout(card); main_h.setContentsMargins(16, 16, 16, 16); main_h.setSpacing(20)
        thumb_lbl = QLabel(); thumb_lbl.setFixedSize(240, 135)
        _ss(thumb_lbl, f"background-color: {CARD_INNER_BG}; border-radius: 14px; border: none;")
        if item.thumb_path and os.path.exists(item.thumb_path):
            pix = QPixmap(item.thumb_path).scaled(240, 135, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            thumb_lbl.setPixmap(get_rounded_pixmap(pix, 14))
        main_h.addWidget(thumb_lbl)
        right_v = QVBoxLayout(); right_v.setContentsMargins(0, 0, 0, 0); right_v.setSpacing(4)
        title_h = QHBoxLayout()
        title_lbl = QLabel(item.title); _ss(title_lbl, f"color: {TEXT_MAIN}; font-size: 20px; font-weight: bold; border: none;"); title_lbl.setWordWrap(True)
        title_h.addWidget(title_lbl, 1)
        trash_btn = QPushButton(); trash_btn.setIcon(self.win._icons.get("trash", QIcon())); trash_btn.setProperty("_icon_name", "trash"); trash_btn.setIconSize(QSize(22, 22)); trash_btn.setFixedSize(32, 32); trash_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(trash_btn, f"QPushButton {{ background: transparent; border: none; }} QPushButton:hover {{ background: #2A1A1A; border-radius: 8px; }}")
        
        def _trash_click():
            if item._trash_ready:
                if item in self.win._dl_items: self.win._dl_items.remove(item)
                item._cancelled = True; self.win._dl_item_removed(item)
            else:
                item._trash_ready = True; trash_btn.setIcon(self.win._icons.get("trash red", QIcon())); trash_btn.setProperty("_icon_name", "trash red")
                QTimer.singleShot(3000, lambda: _reset_trash())
        def _reset_trash():
            item._trash_ready = False
            try: trash_btn.setIcon(self.win._icons.get("trash", QIcon())); trash_btn.setProperty("_icon_name", "trash")
            except RuntimeError: pass
        trash_btn.clicked.connect(_trash_click); title_h.addWidget(trash_btn); right_v.addLayout(title_h)
        meta_h = QHBoxLayout()
        ch_lbl = QLabel(item.channel); _ss(ch_lbl, f"color: {TEXT_MAIN}; font-size: 14px; border: none;"); meta_h.addWidget(ch_lbl)
        dur_lbl = QLabel(f" •  {item.duration_str}"); _ss(dur_lbl, f"color: {TEXT_MAIN}; font-size: 14px; border: none;"); meta_h.addWidget(dur_lbl)
        dot_lbl = QLabel(" • "); _ss(dot_lbl, f"color: #DDDDDD; font-size: 14px; border: none;"); meta_h.addWidget(dot_lbl)
        if item.fav_path and os.path.exists(item.fav_path):
            fav_lbl = QLabel(); _ss(fav_lbl, "border: none; background: transparent;")
            fav_lbl.setPixmap(QPixmap(item.fav_path).scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            meta_h.addWidget(fav_lbl)
        site_lbl = QLabel(item.site_name); site_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); _ss(site_lbl, f"color: {TEXT_MUTED}; font-size: 14px; border: none;"); site_lbl.mousePressEvent = lambda e, u=item.url: self.win._open_qurl(QUrl(u)); meta_h.addWidget(site_lbl)
        meta_h.addStretch(); right_v.addLayout(meta_h); right_v.addStretch()

        if item.status == "failed":
            err_frame = QFrame(); _ss(err_frame, f"background-color: {ERROR_BG}; border: 1px solid #4A2020; border-radius: 8px;")
            err_frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            err_layout = QVBoxLayout(err_frame); err_layout.setContentsMargins(10, 6, 10, 6)
            clean_err = (item.error_msg or "Unknown error").strip().replace("\n", " ")
            if len(clean_err) > 130: clean_err = clean_err[:130] + "..."
            err_lbl = QLabel(clean_err); err_lbl.setWordWrap(True); err_lbl.setMaximumWidth(520); _ss(err_lbl, "color: #FF8888; font-size: 11px; border: none;"); err_layout.addWidget(err_lbl)
            right_v.addWidget(err_frame, alignment=Qt.AlignmentFlag.AlignLeft)
            retry_h = QHBoxLayout(); retry_h.setContentsMargins(0, 4, 0, 0)
            retry_btn = QPushButton(" Retry"); retry_btn.setIcon(self.win._icons.get("retry", QIcon())); retry_btn.setProperty("_icon_name", "retry"); retry_btn.setIconSize(QSize(18, 18)); retry_btn.setFixedSize(90, 32); retry_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); _ss(retry_btn, f"QPushButton {{ background-color: #2A2A2A; color: {TEXT_MAIN}; font-weight: bold; border-radius: 16px; border: none; }} QPushButton:hover {{ background-color: #333333; }}")
            def _retry(): item.status, item.error_msg, item.percent = "active", "", 0.0; self.win._start_download(item); self.win._refresh_single_card(item)
            retry_btn.clicked.connect(_retry); retry_h.addWidget(retry_btn); retry_h.addStretch(); right_v.addLayout(retry_h)
        else:
            prog_h = QHBoxLayout(); prog_h.setSpacing(12)
            if item.status != "done":
                ctrl_btn = QPushButton(); ctrl_btn.setFixedSize(36, 36); ctrl_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); _ss(ctrl_btn, f"QPushButton {{ background: transparent; border: none; }} QPushButton:hover {{ background: #252525; border-radius: 8px; }}")
                if item.status == "active":
                    ctrl_btn.setIcon(self.win._icons.get("pause", QIcon())); ctrl_btn.setProperty("_icon_name", "pause"); ctrl_btn.setIconSize(QSize(24, 24))
                    def _pause():
                        if item.duration_str == "LIVE": self.win.toast_mgr.show_toast("Download cannot be paused"); return
                        item.status = "paused"; item._cancelled = True; item.speed, item.eta = "--", "--"; self.win._refresh_single_card(item)
                    ctrl_btn.clicked.connect(_pause)
                elif item.status == "paused":
                    ctrl_btn.setIcon(self.win._icons.get("play", QIcon())); ctrl_btn.setProperty("_icon_name", "play"); ctrl_btn.setIconSize(QSize(24, 24))
                    def _resume(): item.status = "active"; item._cancelled = False; item.speed, item.eta = "Resuming...", "--"; self.win._start_download(item); self.win._refresh_single_card(item)
                    ctrl_btn.clicked.connect(_resume)
                prog_h.addWidget(ctrl_btn)
            bar_v = QVBoxLayout(); bar_v.setSpacing(6)
            if item.status != "done":
                pb = QProgressBar(); pb.setFixedHeight(4); pb.setTextVisible(False); pb.setMaximum(1000); pb.setValue(int(item.percent * 1000))
                _ss(pb, f"QProgressBar {{ background-color: #333333; border: none; border-radius: 2px; }} QProgressBar::chunk {{ background-color: {TEAL_ACCENT}; border-radius: 2px; }}")
                bar_v.addWidget(pb); card.prog_bar = pb
            stats_h = QHBoxLayout()
            dl_str, tot_str, pct_val, spd, eta = item.downloaded or "0MB", item.total_size or "Unknown", item.percent * 100, item.speed or "0Mb/s", item.eta or "--:--"
            stat_txt = "Download complete" if item.status == "done" else (f"Paused - {int(item.percent*100)}%" if item.status == "paused" else f"{dl_str} / {tot_str} ({pct_val:.1f}%)   {spd}   ETA: {eta}")
            stat_lbl = QLabel(stat_txt); _ss(stat_lbl, f"color: {TEAL_ACCENT if item.status == 'done' else (TEXT_MAIN if item.status == 'active' else TEXT_MUTED)}; font-size: 12px; font-weight: {'bold' if item.status == 'done' else 'normal'}; border: none;"); stats_h.addWidget(stat_lbl); card.stat_lbl = stat_lbl
            path_lbl = QLabel(item.out_dir); path_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); _ss(path_lbl, f"color: {TEXT_MUTED}; font-size: 12px; border: none;"); path_lbl.mousePressEvent = lambda e, it=item: self.win._reveal_in_explorer(it); stats_h.addWidget(path_lbl, alignment=Qt.AlignmentFlag.AlignRight)
            bar_v.addLayout(stats_h); prog_h.addLayout(bar_v); right_v.addLayout(prog_h)

        main_h.addLayout(right_v)
        self.win._dl_cards[item.id] = card
        return card