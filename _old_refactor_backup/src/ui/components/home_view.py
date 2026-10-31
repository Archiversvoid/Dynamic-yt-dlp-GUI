import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QLineEdit
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QCursor, QDesktopServices

import theme
from theme import ss as _ss
from src.ui.styles import CARD_INNER_BG, INPUT_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED, COMBO_QSS, AnimatedComboBox, get_rounded_pixmap, jiggle_widget

class HomeTab(QWidget):
    def __init__(self, main_win):
        super().__init__(main_win)
        self.win = main_win
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.home_center = QWidget()
        hc_layout = QVBoxLayout(self.home_center)
        hc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.title_lbl = QLabel("DYNAMIC")
        _ss(self.title_lbl, f"color: {TEXT_MAIN}; font-size: 68px; font-weight: 300;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hc_layout.addWidget(self.title_lbl)
        hc_layout.addSpacing(20)
        
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Enter link...")
        self.url_entry.setFixedSize(600, 54)
        _ss(self.url_entry, f"QLineEdit {{ background-color: {INPUT_BG}; color: {TEXT_MAIN}; border-radius: 27px; padding: 0 20px; font-size: 18px; border: none; }}")
        self.url_entry.returnPressed.connect(lambda: self.win._process_link(self.url_entry.text().strip()))
        hc_layout.addWidget(self.url_entry, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.home_slot = QWidget()
        self.home_slot_layout = QVBoxLayout(self.home_slot)
        hc_layout.addWidget(self.home_slot)
        
        layout.addWidget(self.home_center)

    def clear_slot(self):
        while self.home_slot_layout.count():
            item = self.home_slot_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def render_media_card(self, info, url, thumb_path, fav_path, start_time=None, end_time=None):
        self.clear_slot()
        title_text = info.get("title", "Unknown Title")
        channel_text = info.get("uploader") or info.get("channel", "Unknown")
        dur_sec, audio_only, is_live = info.get("duration", 0), info.get("_audio_only", False), info.get("is_live", False)

        if is_live: dur_str = "LIVE"
        elif dur_sec and float(dur_sec) > 0:
            t = int(float(dur_sec)); m, s = divmod(t, 60); h, m = divmod(m, 60)
            dur_str = f"{h}:{m:02d}:{s:02d} mins" if h else f"{m}:{s:02d} mins"
        else: dur_str = "0:00 mins"

        format_map, vf, af, video_q, audio_q = {}, info.get("_video_formats", []), info.get("_audio_formats", []), [], []
        for f in vf:
            label = f.get("label", "Unknown")
            video_q.append(label); format_map[label] = f.get("format_id")
        for f in af:
            label = f.get("label", "Unknown")
            audio_q.append(label); format_map[label] = f.get("format_id")
            
        if not audio_q: audio_q = [f"MP3 {br}kbps" for br in (320, 256, 192, 128, 96, 64)]
        site = self.win._site_name(url)

        outer = QFrame()
        _ss(outer, "QFrame { border: none; }")
        outer.setMaximumWidth(720)
        
        o_layout = QVBoxLayout(outer)
        o_layout.setContentsMargins(0, 0, 0, 0)
        o_layout.setSpacing(18)

        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(720, 405) 
        _ss(thumb_lbl, f"background-color: {CARD_INNER_BG}; border-radius: 8px;")
        if thumb_path and os.path.exists(thumb_path):
            pix = QPixmap(thumb_path).scaled(720, 405, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            thumb_lbl.setPixmap(get_rounded_pixmap(pix, 14))
        o_layout.addWidget(thumb_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        t_lbl = QLabel(title_text)
        _ss(t_lbl, f"color: {TEXT_MAIN}; font-size: 34px; font-weight: normal; border: none;")
        t_lbl.setWordWrap(True)
        o_layout.addWidget(t_lbl)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        seg_frame = QFrame()
        _ss(seg_frame, "QFrame { background-color: #222222; border-radius: 8px; }")
        seg_frame.setFixedHeight(38)
        seg_layout = QHBoxLayout(seg_frame)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(2)
        
        bv = QPushButton("Video"); bv.setFixedHeight(30); bv.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ba = QPushButton("Audio"); ba.setFixedHeight(30); ba.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        def update_btn_styles(mode):
            act = f"QPushButton {{ background-color: #333333; color: {TEAL_ACCENT}; font-size: 14px; border-radius: 6px; border: none; padding: 0 15px; }}"
            inact = f"QPushButton {{ background-color: transparent; color: {TEXT_MUTED}; font-size: 14px; border-radius: 6px; border: none; padding: 0 15px; }} QPushButton:hover {{ background-color: #2A2A2A; }}"
            if mode == "Video": _ss(bv, act); _ss(ba, inact)
            else: _ss(bv, inact); _ss(ba, act)
        
        if audio_only:
            bv.setDisabled(True)
            _ss(bv, "QPushButton { background-color: transparent; color: #444; font-size: 14px; border-radius: 6px; border: none; padding: 0 15px; }")
            _ss(ba, f"QPushButton {{ background-color: #333333; color: {TEAL_ACCENT}; font-size: 14px; border-radius: 6px; border: none; padding: 0 15px; }}")
        else: update_btn_styles("Video")
        
        seg_layout.addWidget(bv); seg_layout.addWidget(ba)
        btn_layout.addWidget(seg_frame)

        qm = AnimatedComboBox()
        qm.setFixedHeight(38); qm.setMinimumWidth(160)
        _ss(qm, COMBO_QSS)
        qm.addItems(audio_q if audio_only else (video_q or ["Best quality"]))
        btn_layout.addWidget(qm)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(38); btn_cancel.setMinimumWidth(100)
        btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(btn_cancel, f"QPushButton {{ background-color: transparent; border: 1px solid #777777; color: {TEXT_MAIN}; font-size: 14px; border-radius: 19px; }} QPushButton:hover {{ background-color: #222222; }}")
        btn_layout.addWidget(btn_cancel)

        btn_dl = QPushButton("Download")
        btn_dl.setFixedHeight(38); btn_dl.setMinimumWidth(120)
        btn_dl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if is_live: 
            _ss(btn_dl, "QPushButton { background-color: #222222; color: #666666; font-size: 14px; font-weight: bold; border-radius: 19px; border: 1px solid #333333; }")
        else: 
            _ss(btn_dl, f"QPushButton {{ background-color: {TEAL_ACCENT}; color: #000000; font-size: 14px; font-weight: bold; border-radius: 19px; border: none; }}")
        btn_layout.addWidget(btn_dl)

        o_layout.addLayout(btn_layout)

        current_mode = ["Audio" if audio_only else "Video"]
        def set_mode(mode):
            if audio_only and mode == "Video": return
            current_mode[0] = mode; qm.clear()
            if mode == "Video": update_btn_styles("Video"); qm.addItems(video_q or ["Best quality"])
            else: update_btn_styles("Audio"); qm.addItems(audio_q or ["Best Audio"])
            
        bv.clicked.connect(lambda: set_mode("Video"))
        ba.clicked.connect(lambda: set_mode("Audio"))

        def _cancel(): 
            self.title_lbl.show(); self.url_entry.show(); self.url_entry.clear(); self.clear_slot()
        btn_cancel.clicked.connect(_cancel)
        
        def _on_download():
            if is_live: 
                jiggle_widget(btn_dl); self.win.toast_mgr.show_toast("Can't download live streams"); return
            item = self.win.DownloadItem(
                url=url, title=title_text, channel=channel_text, thumb_path=thumb_path, 
                out_dir=self.win.settings.get("download_dir", str(self.win.repo_root / "downloads")), 
                is_audio=(current_mode[0] == "Audio"), selected_fid=format_map.get(qm.currentText()), 
                duration_str=dur_str, site_name=site, start_time=start_time, end_time=end_time
            )
            self.win._dl_items.append(item)
            self.win._dl_item_added(item)
            self.win._start_download(item)
            self.win._show_tab(2)
            self.title_lbl.show(); self.url_entry.show(); self.url_entry.clear(); self.clear_slot()

        btn_dl.clicked.connect(_on_download)
        self.home_slot_layout.addWidget(outer, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)