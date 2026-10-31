"""The Downloads tab: cards, skeleton, filters, starting/progress of downloads."""
import os
import threading
import time
from datetime import datetime
from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget)
from theme import ss as _ss
from src.core.downloader import fetcher_download, friendly_error, strip_ansi
from src.core.models import DownloadItem
from src.paths import ICON_PATH, repo_root
from src.ui.components.controls import ElidedLabel, ModernScrollArea
from src.ui.components.navigation import FilterTabBar
from src.ui.components.skeleton import ShimmerBox, SkeletonBox
from src.ui.helpers import _card_thumb_pixmap
from src.ui.styles import CARD_BG, CARD_INNER_BG, ERROR_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED


class DownloadsMixin:
    """The Downloads tab: cards, skeleton, filters, starting/progress of downloads."""

    def _ensure_dl_list_loaded(self):
        if not self._dl_list_dirty:
            return
        if not self._dl_first_build_done:
            self._dl_first_build_done = True
            self._show_dl_skeleton()
            QTimer.singleShot(30, self._full_rebuild_dl_cards)
        else:
            self._full_rebuild_dl_cards()

    def _discard_layout_widgets(self, layout):
        """Remove + delete everything in a layout. ShimmerBoxes are unregistered from
        their shared timer immediately (not whenever Qt gets round to deleting them)."""
        while layout.count():
            it = layout.takeAt(0)
            w = it.widget()
            if w is None:
                continue
            for sb in w.findChildren(ShimmerBox):
                ShimmerBox.unregister(sb)
            if isinstance(w, ShimmerBox):
                ShimmerBox.unregister(w)
            w.deleteLater()

    def _show_dl_skeleton(self):
        self._discard_layout_widgets(self.scroll_layout)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        skeleton_count = min(max(len(self._dl_items), 1), 5)
        for _ in range(skeleton_count):
            self.scroll_layout.addWidget(self._build_skeleton_card())
        self.scroll_layout.addStretch()
        self.scroll_layout.activate()

    def _build_skeleton_card(self):
        """Skeleton card, measured from the design mock-up: a thumbnail block on the left; on the
        right a title bar with the trash button block beside it, a shorter bar under the title, and
        two bars along the bottom (status on the left, folder path on the right). One flat 180px
        frame - no wrapper and no shadow effect (a shadow re-renders its whole card every time a
        child box pulses, which is far heavier than the boxes themselves)."""
        card = QFrame(); card.setObjectName("dlSkelCard"); card.setFixedHeight(180)
        _ss(card, f"QFrame#dlSkelCard {{ background-color: {CARD_BG}; border: 1px solid #2A2A2A; border-radius: 14px; }}")
        top, bottom, left = Qt.AlignmentFlag.AlignTop, Qt.AlignmentFlag.AlignBottom, Qt.AlignmentFlag.AlignLeft
        main_h = QHBoxLayout(card); main_h.setContentsMargins(16, 10, 15, 16); main_h.setSpacing(14)
        main_h.addWidget(SkeletonBox(240, 142, radius=14), 0, Qt.AlignmentFlag.AlignVCenter)

        right_v = QVBoxLayout(); right_v.setContentsMargins(0, 0, 0, 0); right_v.setSpacing(7)
        title_row = QHBoxLayout(); title_row.setContentsMargins(0, 0, 0, 0); title_row.setSpacing(12)
        title_row.addWidget(SkeletonBox(372, 22, radius=6), 0, bottom)      # title
        title_row.addStretch()
        title_row.addWidget(SkeletonBox(35, 35, radius=10), 0, top)         # trash button
        right_v.addLayout(title_row)
        right_v.addWidget(SkeletonBox(255, 22, radius=6), 0, left)          # channel / duration / site line
        right_v.addStretch()
        bottom_row = QHBoxLayout(); bottom_row.setContentsMargins(0, 0, 0, 0); bottom_row.setSpacing(12)
        bottom_row.addWidget(SkeletonBox(166, 22, radius=6))                # status
        bottom_row.addStretch()
        bottom_row.addWidget(SkeletonBox(263, 22, radius=6))                # folder path
        right_v.addLayout(bottom_row)
        main_h.addLayout(right_v, 1)
        return card

    def _build_downloads_tab(self):
        main_layout = QVBoxLayout(self.tab_dl); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        top_container = QWidget(); top_layout = QVBoxLayout(top_container); top_layout.setContentsMargins(32, 28, 32, 12); top_layout.setSpacing(16)
        lbl = QLabel("Downloads"); _ss(lbl, f"color: {TEXT_MAIN}; font-size: 32px; font-weight: bold;"); top_layout.addWidget(lbl)
        filters = ["All", "Active", "Paused", "Done", "Failed"]
        self.filter_tab_bar = FilterTabBar(filters); self.filter_tab_bar.filter_changed.connect(self._on_filter_changed)
        top_layout.addWidget(self.filter_tab_bar, alignment=Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(top_container)
        self.scroll = ModernScrollArea(); self.scroll_content = QWidget(); _ss(self.scroll_content, "background-color: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_content); self.scroll_layout.setContentsMargins(32, 10, 32, 16); self.scroll_layout.setSpacing(16); self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.scroll_content); main_layout.addWidget(self.scroll, 1)
        self._dl_empty_label = None

    def _on_filter_changed(self, f_name):
        if self._dl_tab_filter == f_name: return
        self._dl_tab_filter = f_name
        self._sync_dl_filter_view()

    def _full_rebuild_dl_cards(self):
        """Builds the card list in small time-boxed batches instead of one blocking
        loop. Each card decodes a thumbnail and builds ~20 styled widgets; doing every
        card in a single pass froze the window ("Not Responding") when the Downloads
        tab was first opened with a few dozen downloads. Between batches the event
        loop runs, so the window keeps painting and responding while cards appear."""
        self._dl_build_gen = getattr(self, "_dl_build_gen", 0) + 1
        gen = self._dl_build_gen
        self._discard_layout_widgets(self.scroll_layout)
        self._dl_cards = {}
        self._dl_empty_label = None
        self._dl_slow = []
        self._dl_build_queue = list(reversed(self._dl_items))
        self._dl_list_dirty = False
        self._dl_build_batch(gen)

    def _dl_build_batch(self, gen):
        if gen != getattr(self, "_dl_build_gen", 0):
            return                                   # a newer rebuild took over
        queue = self._dl_build_queue
        t0 = time.perf_counter()
        try:
            built_any = False
            while queue:
                # always build at least one card per batch (guarantees progress),
                # then keep going only while this batch is inside its time budget
                if built_any and (time.perf_counter() - t0) >= 0.008:
                    break
                item = queue.pop(0)
                # skip anything removed, or already built (e.g. refreshed), since we queued it
                if item not in self._dl_items or item.id in self._dl_cards:
                    continue
                t_card = time.perf_counter()
                self.scroll_layout.addWidget(self._build_dl_card_widget(item))
                built_any = True
                if time.perf_counter() - t_card > 0.25:
                    self._dl_slow.append((item.title, time.perf_counter() - t_card))
        finally:
            # Position the new cards NOW, before anything can paint. Painting first used stale geometry,
            # which is what made cards look glued together until the freeze ended.
            self.scroll_layout.activate()
        if queue:
            self._sync_dl_filter_view()
            QTimer.singleShot(0, lambda: self._dl_build_batch(gen))
            return
        self._dl_empty_label = QLabel("No downloads here")
        _ss(self._dl_empty_label, f"color: {TEXT_MUTED}; font-size: 15px;")
        self._dl_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_layout.addWidget(self._dl_empty_label)
        self.scroll_layout.addStretch()
        self.scroll_layout.activate()
        self._sync_dl_filter_view()
        if self._dl_slow:                                   # something took >250 ms to build: leave a trace for diagnosis
            try:
                d = repo_root / "logs"; d.mkdir(parents=True, exist_ok=True)
                with open(d / "ui_timing.log", "a", encoding="utf-8") as f:
                    for title, dt in self._dl_slow:
                        f.write("[%s] slow download card (%.0f ms): %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), dt * 1000, title))
            except Exception:
                pass
            self._dl_slow = []

    def _sync_dl_filter_view(self):
        counts = {"All": len(self._dl_items), "Active": sum(1 for d in self._dl_items if d.status=="active"), "Paused": sum(1 for d in self._dl_items if d.status=="paused"), "Done": sum(1 for d in self._dl_items if d.status=="done"), "Failed": sum(1 for d in self._dl_items if d.status=="failed")}
        self.filter_tab_bar.update_counts(counts)
        visible = 0
        for item in self._dl_items:
            card = self._dl_cards.get(item.id)
            if not card: continue
            match = self._dl_tab_filter == "All" or item.status == self._dl_tab_filter.lower()
            if card.isVisible() != match: card.setVisible(match)
            if match: visible += 1
        if self._dl_empty_label is not None:
            self._dl_empty_label.setVisible(visible == 0)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if visible >= 3 else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _dl_item_added(self, item):
        if not self._dl_first_build_done: return
        self.scroll_layout.insertWidget(0, self._build_dl_card_widget(item))
        self._sync_dl_filter_view()

    def _dl_item_removed(self, item):
        if not self._dl_first_build_done: return
        card = self._dl_cards.pop(item.id, None)
        if card:
            self.scroll_layout.removeWidget(card)
            card.deleteLater()
        self._sync_dl_filter_view()

    def _build_dl_card_widget(self, item: DownloadItem):
        card = QFrame(); card.setFixedHeight(180)
        _ss(card, f"QFrame {{ background-color: {CARD_BG}; border: 1px solid #2A2A2A; border-radius: 14px; }}")
        main_h = QHBoxLayout(card); main_h.setContentsMargins(16, 16, 16, 16); main_h.setSpacing(20)
        thumb_lbl = QLabel(); thumb_lbl.setFixedSize(240, 135)
        _ss(thumb_lbl, f"background-color: {CARD_INNER_BG}; border-radius: 14px; border: none;")
        if item.thumb_path and os.path.exists(item.thumb_path):
            thumb_lbl.setPixmap(_card_thumb_pixmap(item.thumb_path))
        main_h.addWidget(thumb_lbl)
        right_v = QVBoxLayout(); right_v.setContentsMargins(0, 0, 0, 0); right_v.setSpacing(4)
        title_h = QHBoxLayout()
        title_lbl = ElidedLabel(item.title); _ss(title_lbl, f"color: {TEXT_MAIN}; font-size: 20px; font-weight: bold; border: none;")
        title_h.addWidget(title_lbl, 1)
        trash_btn = QPushButton(); trash_btn.setIcon(self._icons.get("trash", QIcon())); trash_btn.setProperty("_icon_name", "trash"); trash_btn.setIconSize(QSize(22, 22)); trash_btn.setFixedSize(32, 32); trash_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(trash_btn, f"QPushButton {{ background: transparent; border: none; }} QPushButton:hover {{ background: #2A1A1A; border-radius: 8px; }}")
        
        def _trash_click():
            if item._trash_ready:
                if item in self._dl_items: self._dl_items.remove(item)
                item._cancelled = True; self._dl_item_removed(item)
            else:
                item._trash_ready = True; trash_btn.setIcon(self._icons.get("trash red", QIcon())); trash_btn.setProperty("_icon_name", "trash red")
                QTimer.singleShot(3000, lambda: _reset_trash())
        def _reset_trash():
            item._trash_ready = False
            try: trash_btn.setIcon(self._icons.get("trash", QIcon())); trash_btn.setProperty("_icon_name", "trash")
            except RuntimeError: pass
        trash_btn.clicked.connect(_trash_click); title_h.addWidget(trash_btn); right_v.addLayout(title_h)
        meta_h = QHBoxLayout()
        ch_lbl = ElidedLabel(item.channel, fit_text=True); ch_lbl.setMaximumWidth(260); _ss(ch_lbl, f"color: {TEXT_MAIN}; font-size: 14px; border: none;"); meta_h.addWidget(ch_lbl)
        dur_lbl = QLabel(f" •  {item.duration_str}"); _ss(dur_lbl, f"color: {TEXT_MAIN}; font-size: 14px; border: none;"); meta_h.addWidget(dur_lbl)
        dot_lbl = QLabel(" • "); _ss(dot_lbl, f"color: #DDDDDD; font-size: 14px; border: none;"); meta_h.addWidget(dot_lbl)
        if item.fav_path and os.path.exists(item.fav_path):
            fav_lbl = QLabel(); _ss(fav_lbl, "border: none; background: transparent;")
            fav_lbl.setPixmap(QPixmap(item.fav_path).scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            meta_h.addWidget(fav_lbl)
        site_lbl = QLabel(item.site_name); site_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); _ss(site_lbl, f"color: {TEXT_MUTED}; font-size: 14px; border: none;"); site_lbl.mousePressEvent = lambda e, u=item.url: self._open_qurl(QUrl(u)); meta_h.addWidget(site_lbl)
        meta_h.addStretch(); right_v.addLayout(meta_h); right_v.addStretch()

        if item.status == "failed":
            err_frame = QFrame(); _ss(err_frame, f"background-color: {ERROR_BG}; border: 1px solid #4A2020; border-radius: 8px;")
            err_frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            err_layout = QVBoxLayout(err_frame); err_layout.setContentsMargins(10, 6, 10, 6)
            full_err = friendly_error(item.error_msg or "Unknown error")     # also cleans errors saved by older versions
            err_w = 440                                                       # fits beside the thumbnail even at the minimum window width
            err_font = QFont(); err_font.setPixelSize(11)                     # same size as the stylesheet below
            fm = QFontMetrics(err_font)
            clean_err = fm.elidedText(full_err, Qt.TextElideMode.ElideRight, err_w * 2 - 80)   # at most two lines
            err_lbl = QLabel(clean_err); err_lbl.setWordWrap(True); err_lbl.setToolTip(full_err)
            _ss(err_lbl, "color: #FF8888; font-size: 11px; border: none;")
            # Size the label to its wrapped text explicitly: a word-wrapped QLabel inside a Fixed-size frame
            # reports too small a height and ends up clipped (the box showed only half the message).
            err_lbl.setFixedSize(err_w, fm.boundingRect(0, 0, err_w, 1000, Qt.TextFlag.TextWordWrap.value, clean_err).height() + 2)
            err_layout.addWidget(err_lbl)
            right_v.addWidget(err_frame, alignment=Qt.AlignmentFlag.AlignLeft)
            retry_h = QHBoxLayout(); retry_h.setContentsMargins(0, 4, 0, 0)
            retry_btn = QPushButton(" Retry"); retry_btn.setIcon(self._icons.get("retry", QIcon())); retry_btn.setProperty("_icon_name", "retry"); retry_btn.setIconSize(QSize(18, 18)); retry_btn.setFixedSize(90, 32); retry_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); _ss(retry_btn, f"QPushButton {{ background-color: #2A2A2A; color: {TEXT_MAIN}; font-weight: bold; border-radius: 16px; border: none; }} QPushButton:hover {{ background-color: #333333; }}")
            def _retry(): item.status, item.error_msg, item.percent = "active", "", 0.0; self._start_download(item); self._refresh_single_card(item)
            retry_btn.clicked.connect(_retry); retry_h.addWidget(retry_btn); retry_h.addStretch(); right_v.addLayout(retry_h)
        else:
            prog_h = QHBoxLayout(); prog_h.setSpacing(12)
            if item.status != "done":
                ctrl_btn = QPushButton(); ctrl_btn.setFixedSize(36, 36); ctrl_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); _ss(ctrl_btn, f"QPushButton {{ background: transparent; border: none; }} QPushButton:hover {{ background: #252525; border-radius: 8px; }}")
                if item.status == "active":
                    ctrl_btn.setIcon(self._icons.get("pause", QIcon())); ctrl_btn.setProperty("_icon_name", "pause"); ctrl_btn.setIconSize(QSize(24, 24))
                    def _pause():
                        if item.duration_str == "LIVE": self.toast_mgr.show_toast("Download cannot be paused"); return
                        item.status = "paused"; item._cancelled = True; item.speed, item.eta = "--", "--"; self._refresh_single_card(item)
                    ctrl_btn.clicked.connect(_pause)
                elif item.status == "paused":
                    ctrl_btn.setIcon(self._icons.get("play", QIcon())); ctrl_btn.setProperty("_icon_name", "play"); ctrl_btn.setIconSize(QSize(24, 24))
                    def _resume(): item.status = "active"; item._cancelled = False; item.speed, item.eta = "Resuming...", "--"; self._start_download(item); self._refresh_single_card(item)
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
            path_lbl = QLabel(item.out_dir); path_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); _ss(path_lbl, f"color: {TEXT_MUTED}; font-size: 12px; border: none;"); path_lbl.mousePressEvent = lambda e, it=item: self._reveal_in_explorer(it); stats_h.addWidget(path_lbl, alignment=Qt.AlignmentFlag.AlignRight)
            bar_v.addLayout(stats_h); prog_h.addLayout(bar_v); right_v.addLayout(prog_h)

        main_h.addLayout(right_v)
        self._dl_cards[item.id] = card
        return card

    def _start_download(self, item: DownloadItem):
        def _worker():
            evts = fetcher_download(item.url, item.selected_fid, item.out_dir, item.is_audio, item.start_time, item.end_time)
            for evt in evts:
                if item._cancelled: break
                t = evt.get("type")
                if t == "progress":
                    item.percent, item.speed, item.eta = evt.get("percent", 0), evt.get("speed", ""), evt.get("eta", "")
                    item.downloaded, item.total_size = evt.get("downloaded", ""), evt.get("size", "")
                    self.signals.update_progress.emit(item)
                elif t == "done":
                    item.status, item.percent = "done", 1.0
                    item.final_path = evt.get("filepath")
                    self.signals.refresh_card.emit(item)
                elif t == "error":
                    item.status, item.error_msg = "failed", evt.get("message", "Unknown error")
                    item.error_raw = evt.get("raw", "")
                    self._log_download_error(item)
                    self.signals.refresh_card.emit(item)
        item._thread = threading.Thread(target=_worker, daemon=True); item._thread.start()

    def _log_download_error(self, item):
        try:
            log_dir = repo_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            clean_err = strip_ansi(item.error_msg or "Unknown error").strip().replace("\n", " ")
            raw = " ".join(strip_ansi(getattr(item, "error_raw", "") or "").split())
            line = f'[{ts}] FAILED  title="{item.title}"  url={item.url}  error={clean_err}' + (f'  raw={raw}' if raw and raw != clean_err else '') + '\n'
            with open(log_dir / "download_errors.log", "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _update_card_progress(self, item):
        if item.id not in self._dl_cards: return
        card = self._dl_cards[item.id]
        if hasattr(card, "prog_bar"): card.prog_bar.setValue(int(item.percent * 1000))
        if hasattr(card, "stat_lbl"):
            dl_str, tot_str, pct_val, spd, eta = item.downloaded or "0MB", item.total_size or "Unknown", item.percent * 100, item.speed or "0Mb/s", item.eta or "--:--"
            txt = "Download complete" if item.status == "done" else (f"Paused - {int(item.percent*100)}%" if item.status == "paused" else f"{dl_str} / {tot_str} ({pct_val:.1f}%)   {spd}   ETA: {eta}")
            card.stat_lbl.setText(txt)

    def _show_download_notification(self, item):
        raw_title = item.title or "File"
        if hasattr(self, "tray_icon") and self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage("Download complete", raw_title, QIcon(ICON_PATH), 5000)

    def _refresh_single_card(self, item):
        if not self._dl_first_build_done:
            return
        old = self._dl_cards.pop(item.id, None)
        idx = -1
        if old is not None:
            try:
                idx = self.scroll_layout.indexOf(old)
                self.scroll_layout.removeWidget(old)
                old.deleteLater()
            except RuntimeError:
                idx = -1
        new_card = self._build_dl_card_widget(item)
        self.scroll_layout.insertWidget(idx if idx >= 0 else 0, new_card)
        self._sync_dl_filter_view()
        if item.status == "done" and not getattr(item, "_notified", False):
            item._notified = True; self._show_download_notification(item)
