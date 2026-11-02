"""TrimLoad tab: building the tab and its view states (initial / processing / loaded), toasts, theme refresh."""
import os
import theme
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCursor, QDesktopServices
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)
from theme import ss as _ss
from src.paths import cache_dir, repo_root
from src.ui.components.combo import AnimatedComboBox
from src.ui.components.toast import ToastManager
from src.ui.styles import (
    _mono_family, BG_DARK, ERROR_RED, INPUT_BG, TEAL_ACCENT, TEXT_MAIN, TEXT_MUTED)
from src.ui.trim.helpers import jiggle_widget
from src.ui.trim.widgets import AspectRatioLabel, LoadingOverlay, TrimRangeSlider


class TrimUiMixin:
    """Building the tab and its view states (initial / processing / loaded), toasts, theme refresh."""

    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        _ss(self, f"background-color: {BG_DARK};")

        self.search_container = QWidget()
        sc_layout = QVBoxLayout(self.search_container)
        sc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_lbl = QLabel("TRIMLOAD")
        _ss(self.title_lbl, f"color: {TEXT_MAIN}; font-size: 68px; font-weight: 300;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sc_layout.addWidget(self.title_lbl)
        sc_layout.addSpacing(20)

        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Enter link to trim...")
        self.url_entry.setFixedSize(600, 54)
        _ss(self.url_entry, f"QLineEdit {{ background-color: {INPUT_BG}; color: {TEXT_MAIN}; border-radius: 27px; padding: 0 20px; font-size: 18px; border: none; }}")
        self.url_entry.returnPressed.connect(self._process_link)
        sc_layout.addWidget(self.url_entry, alignment=Qt.AlignmentFlag.AlignCenter)

        self.processing_slot = QWidget()
        self.proc_layout = QVBoxLayout(self.processing_slot)
        sc_layout.addWidget(self.processing_slot)

        self.layout.addWidget(self.search_container)

        self.editor_container = QWidget()
        ed_layout = QVBoxLayout(self.editor_container)
        ed_layout.setContentsMargins(20, 16, 20, 20)
        ed_layout.setSpacing(10)

        self.video_frame = QFrame()
        _ss(self.video_frame, "background-color: #000000;")
        vf_layout = QVBoxLayout(self.video_frame)
        vf_layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)
        vf_layout.addWidget(self.video_widget)

        self.thumbnail_label = AspectRatioLabel(self.video_frame)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vf_layout.addWidget(self.thumbnail_label)
        self.thumbnail_label.hide()
        
        self.preview_error_lbl = QLabel("Couldn't load preview", self.video_frame)
        _ss(self.preview_error_lbl, "color: #FFFFFF; font-size: 16px; font-weight: bold; background-color: rgba(0, 0, 0, 180); padding: 12px 24px;")
        self.preview_error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_error_lbl.hide()

        self.loading_overlay = LoadingOverlay(self.video_frame)

        ed_layout.addWidget(self.video_frame, 1)

        self.meta_container = QWidget()
        meta_layout = QVBoxLayout(self.meta_container)
        meta_layout.setContentsMargins(4, 2, 4, 4)
        meta_layout.setSpacing(4)

        self.meta_title_lbl = QLabel("Media Title")
        _ss(self.meta_title_lbl, "color: #FFFFFF; font-size: 20px; font-weight: bold; border: none;")
        self.meta_title_lbl.setWordWrap(True)

        sub_layout = QHBoxLayout()
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(8)

        self.meta_channel_lbl = QLabel("Channel")
        _ss(self.meta_channel_lbl, "color: #DDDDDD; font-size: 14px; border: none;")

        self.meta_dot1_lbl = QLabel("•")
        _ss(self.meta_dot1_lbl, "color: #8A8A8A; font-size: 14px; border: none;")

        self.meta_dur_lbl = QLabel("0:00 mins")
        _ss(self.meta_dur_lbl, f"color: {TEXT_MAIN}; font-size: 14px; border: none;")

        self.meta_dot2_lbl = QLabel("•")
        _ss(self.meta_dot2_lbl, "color: #8A8A8A; font-size: 14px; border: none;")

        self.meta_site_icon = QLabel("▶")
        _ss(self.meta_site_icon, "color: #FF0000; font-size: 14px; border: none;")
        self.meta_site_icon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.meta_site_icon.mousePressEvent = lambda event: self._open_site_url()

        self.meta_site_lbl = QLabel("YouTube")
        _ss(self.meta_site_lbl, "color: #FFFFFF; font-size: 14px; font-weight: bold; border: none;")
        self.meta_site_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.meta_site_lbl.mousePressEvent = lambda event: self._open_site_url()

        sub_layout.addWidget(self.meta_channel_lbl)
        sub_layout.addWidget(self.meta_dot1_lbl)
        sub_layout.addWidget(self.meta_dur_lbl)
        sub_layout.addWidget(self.meta_dot2_lbl)
        sub_layout.addWidget(self.meta_site_icon)
        sub_layout.addWidget(self.meta_site_lbl)
        sub_layout.addStretch()

        meta_layout.addWidget(self.meta_title_lbl)
        meta_layout.addLayout(sub_layout)

        ed_layout.addWidget(self.meta_container)

        timeline_frame = QFrame()
        timeline_frame.setFixedHeight(54)
        _ss(timeline_frame, "background-color: #1A1A1A;")
        tl_layout = QHBoxLayout(timeline_frame)
        tl_layout.setContentsMargins(8, 0, 12, 0)
        tl_layout.setSpacing(6)

        self.btn_play = QPushButton()
        self.btn_play.setFixedSize(32, 32)
        self.btn_play.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self.btn_play, f"QPushButton {{ background: transparent; border: none; }}")
        
        icon_dir = os.path.join(str(repo_root), "icons")
        self.icon_play = theme.icon("play", Path(icon_dir), cache_dir)
        self.icon_pause = theme.icon("pause", Path(icon_dir), cache_dir)
        
        self.btn_play.setIcon(self.icon_play)
        self.btn_play.clicked.connect(self._toggle_play)
        tl_layout.addWidget(self.btn_play)

        self.time_lbl = QLabel("00:00:00 / 00:00:00")
        _ss(self.time_lbl, f"color: {TEXT_MAIN}; font-size: 13px; font-family: '{_mono_family()}'; border: none;")
        tl_layout.addWidget(self.time_lbl)

        self.range_slider = TrimRangeSlider()
        self.range_slider.positionChanged.connect(self._on_slider_position_changed)
        self.range_slider.seekRequested.connect(self._seek_player)
        self.range_slider.trimRangeChanged.connect(self._on_trim_range_changed)
        tl_layout.addWidget(self.range_slider, 1)

        ed_layout.addWidget(timeline_frame)

        dock_frame = QFrame()
        dock_frame.setFixedHeight(96) # Raised from 76 to fit two clean rows
        _ss(dock_frame, "QFrame { background-color: #1A1A1A; }")
        
        grid = QGridLayout(dock_frame)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8) # Raised slightly for row separation

        # --- ROW 0 & 1: TIME CONTROLS (Left Side) ---
        lbl_start = QLabel("Start")
        _ss(lbl_start, "color: #FFFFFF; font-size: 13px;")
        grid.addWidget(lbl_start, 0, 0)

        lbl_end = QLabel("End")
        _ss(lbl_end, "color: #FFFFFF; font-size: 13px;")
        grid.addWidget(lbl_end, 0, 1)

        self.start_input = QLineEdit("00:00:00")
        self.start_input.setFixedSize(80, 28)
        self.start_input.editingFinished.connect(self._on_inputs_edited)
        grid.addWidget(self.start_input, 1, 0)

        self.end_input = QLineEdit("00:00:00")
        self.end_input.setFixedSize(80, 28)
        self.end_input.editingFinished.connect(self._on_inputs_edited)
        grid.addWidget(self.end_input, 1, 1)

        grid.setColumnMinimumWidth(2, 24)

        # --- ROW 0: SETTINGS CONTROLS (Shifted Higher) ---
        mode_frame = QFrame()
        mode_frame.setFixedSize(130, 28)
        _ss(mode_frame, "QFrame { background-color: #252525; border: 1px solid #333333; border-radius: 6px; }")
        m_layout = QHBoxLayout(mode_frame)
        m_layout.setContentsMargins(2, 2, 2, 2)
        m_layout.setSpacing(0)

        self.btn_mode_vid = QPushButton("Video")
        self.btn_mode_aud = QPushButton("Audio")
        for b in (self.btn_mode_vid, self.btn_mode_aud):
            b.setFixedHeight(24)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            
        self.btn_mode_vid.clicked.connect(lambda: self._set_mode(False))
        self.btn_mode_aud.clicked.connect(lambda: self._set_mode(True))
        m_layout.addWidget(self.btn_mode_vid)
        m_layout.addWidget(self.btn_mode_aud)
        
        # MOVED TO ROW 0
        grid.addWidget(mode_frame, 0, 3)

        self.qual_combo = AnimatedComboBox()
        self.qual_combo.setFixedSize(90, 28)
        _ss(self.qual_combo, """
            QComboBox { 
                background-color: #1A1A1A; 
                color: #FFFFFF; 
                font-size: 12px; 
                border-radius: 6px; 
                padding: 0 10px; 
                border: 1px solid #2A2A2A; 
            }
            QComboBox::drop-down { border: none; width: 0px; }
            QComboBox::down-arrow { image: none; border: none; }
            QComboBox QAbstractItemView { 
                background-color: #181818; color: #FFFFFF; 
                selection-background-color: #B5B5B5; selection-color: #000000; 
                border: 1px solid #FFFFFF; border-radius: 4px; outline: none; padding: 2px 0px;
            }
            QComboBox QAbstractItemView::item { min-height: 26px; padding-left: 10px; color: #FFFFFF; }
            QComboBox QAbstractItemView::item:selected { background-color: #B5B5B5; color: #000000; }
        """)
        self.qual_combo.currentIndexChanged.connect(self._update_est_size)
        
        # MOVED TO ROW 0
        grid.addWidget(self.qual_combo, 0, 4)

        self.est_size_lbl = QLabel("Est. size ~0 MB")
        _ss(self.est_size_lbl, "color: #EEEEEE; font-size: 13px;")
        
        # MOVED TO ROW 0
        grid.addWidget(self.est_size_lbl, 0, 5)

        # --- ROW 1: ACTION BUTTONS (Shifted Lower Right) ---
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        grid.addItem(spacer, 1, 3)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedSize(90, 32)
        self.btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self.btn_cancel, f"QPushButton {{ background: transparent; border: 1px solid {TEAL_ACCENT}; color: #FFFFFF; border-radius: 16px; font-size: 14px; font-weight: 400; }} QPushButton:hover {{ background: #222; }}")
        self.btn_cancel.clicked.connect(self._show_initial_view)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_download = QPushButton("Download")
        self.btn_download.setFixedSize(100, 32)
        self.btn_download.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _ss(self.btn_download, f"QPushButton {{ background-color: {TEAL_ACCENT}; color: #000000; border-radius: 16px; font-size: 14px; border: none; font-weight: 500; }} QPushButton:hover {{ background-color: #00A892; }}")
        self.btn_download.clicked.connect(self._on_download)
        btn_layout.addWidget(self.btn_download)

        # MOVED TO ROW 1, SPANNING THE LOWER RIGHT COLUMNS
        grid.addLayout(btn_layout, 1, 4, 1, 3)


        ed_layout.addWidget(dock_frame)
        self.layout.addWidget(self.editor_container)

    def _show_initial_view(self):
        # Safely release the network stream immediately to prevent Qt from freezing the main thread during reset
        if hasattr(self, 'player'):
            self.player.pause()
            self.player.setSource(QUrl())
            self.player.stop()
            
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.stop()
        
        self.preview_failed = False
        if hasattr(self, 'preview_error_lbl'):
            self.preview_error_lbl.hide()
            
        if hasattr(self, 'btn_play') and hasattr(self, 'icon_play'):
            self.btn_play.setIcon(self.icon_play)
            
        if hasattr(self, 'editor_container'):
            self.editor_container.hide()
            self.search_container.show()
            self.title_lbl.show()
            self.url_entry.show()
            self.url_entry.clear()
            self._reset_inputs_style()
            self._clear_processing_slot()

    def _show_initial_view_keep_text(self):
        """Same as _show_initial_view but leaves the pasted link in place -
        used for Cancel (while processing) and Try Again (after a
        failure), where the user almost certainly wants to retry the same
        link rather than retype it. The plain _show_initial_view above
        stays untouched since its other callers (the trim editor's own
        Cancel button, and the post-download reset) are genuine "start
        completely over" actions where clearing makes sense."""
        if hasattr(self, 'player'):
            self.player.pause()
            self.player.setSource(QUrl())
            self.player.stop()

        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.stop()

        self.preview_failed = False
        if hasattr(self, 'preview_error_lbl'):
            self.preview_error_lbl.hide()

        if hasattr(self, 'btn_play') and hasattr(self, 'icon_play'):
            self.btn_play.setIcon(self.icon_play)

        if hasattr(self, 'editor_container'):
            self.editor_container.hide()
            self.search_container.show()
            self.title_lbl.show()
            self.url_entry.show()
            self._reset_inputs_style()
            self._clear_processing_slot()

    def _clear_processing_slot(self):
        while self.proc_layout.count():
            item = self.proc_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_processing_cancel(self):
        if self._proc_cancel_flag is not None: self._proc_cancel_flag[0] = True
        self._proc_run_id += 1
        self._show_initial_view_keep_text()
        self.proc_overlay.dismiss()

    def _on_trim_phase(self, run_id, key):
        if run_id == self._proc_run_id:
            self.proc_overlay.set_phase(key)

    def _mark_inputs_invalid(self):
        err_style = f"background-color: #2A1515; color: {TEXT_MAIN}; border: 1.5px solid {ERROR_RED}; border-radius: 4px; padding: 0 8px; font-size: 13px;"
        _ss(self.start_input, err_style)
        _ss(self.end_input, err_style)
        jiggle_widget(self.start_input)
        jiggle_widget(self.end_input)
        jiggle_widget(self.btn_download)

    def _reset_inputs_style(self):
        norm_style = f"background-color: {INPUT_BG}; color: {TEXT_MAIN}; border: none; border-radius: 4px; padding: 0 8px; font-size: 13px;"
        _ss(self.start_input, norm_style)
        _ss(self.end_input, norm_style)

    def _open_site_url(self):
        url = self.current_info.get('_url')
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _show_toast_error(self, msg):
        self._show_toast(msg)

    def _show_toast(self, msg, icon_pixmap=None, rich_text=False):
        if self.main_win and hasattr(self.main_win, "toast_mgr"):
            self.main_win.toast_mgr.show_toast(msg, icon_pixmap=icon_pixmap, rich_text=rich_text)
        else:
            if not hasattr(self, "local_toast_mgr"):
                self.local_toast_mgr = ToastManager(self)
            self.local_toast_mgr.show_toast(msg, icon_pixmap=icon_pixmap, rich_text=rich_text)

    def apply_theme(self):
        """Called by the main window after a live theme switch (stylesheets are
        re-applied app-wide there; this refreshes what is not a stylesheet)."""
        try:
            icon_dir = repo_root / "icons"
            self.icon_play = theme.icon("play", icon_dir, cache_dir)
            self.icon_pause = theme.icon("pause", icon_dir, cache_dir)
            playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            self.btn_play.setIcon(self.icon_pause if playing else self.icon_play)
        except Exception:
            pass
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "loading_overlay"):
            self.loading_overlay.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
            
        if hasattr(self, "preview_error_lbl") and self.preview_error_lbl.isVisible():
            self.preview_error_lbl.adjustSize()
            self.preview_error_lbl.move(
                (self.video_frame.width() - self.preview_error_lbl.width()) // 2,
                (self.video_frame.height() - self.preview_error_lbl.height()) // 2
            )

    # defaults until a link has loaded (the real lists are set in _reveal_trim_result)
    _video_items = ()
    _audio_items = ()
    _qual_memory = None
    _qual_mode = None

    def _fill_quality_combo(self, is_audio):
        """Video mode lists resolutions; Audio mode lists MP3 bitrates instead. Each mode remembers
        what was last picked, so flipping Video -> Audio -> Video returns to the same resolution."""
        items = self._audio_items if is_audio else self._video_items
        if not items or self._qual_memory is None:
            return
        mode = "audio" if is_audio else "video"
        if self._qual_mode is not None and self._qual_mode != mode:
            self._qual_memory[self._qual_mode] = max(0, self.qual_combo.currentIndex())
        self.qual_combo.blockSignals(True)               # the caller refreshes the size estimate once, afterwards
        try:
            self.qual_combo.clear()
            for text, data in items:
                self.qual_combo.addItem(text, data)
            self.qual_combo.setCurrentIndex(min(self._qual_memory.get(mode, 0), len(items) - 1))
        finally:
            self.qual_combo.blockSignals(False)
        self._qual_mode = mode
        self.qual_combo.setToolTip("Bitrate" if is_audio else "Quality")

    def _set_mode(self, is_audio):
        self.is_audio_mode = is_audio
        self._fill_quality_combo(is_audio)
        
        act = f"QPushButton {{ background-color: #383838; color: {TEAL_ACCENT}; font-size: 13px; font-weight: 500; border-radius: 4px; border: none; }}"
        inact = f"QPushButton {{ background-color: transparent; color: {TEXT_MUTED}; font-size: 13px; font-weight: 500; border-radius: 4px; border: none; }}"
        
        if is_audio:
            _ss(self.btn_mode_aud, act)
            _ss(self.btn_mode_vid, inact)
            self.video_widget.hide()
            self.thumbnail_label.show()
            
            if self.preview_failed:
                self.preview_error_lbl.show()
                self.preview_error_lbl.raise_()
            else:
                self.preview_error_lbl.hide()
        else:
            _ss(self.btn_mode_vid, act)
            _ss(self.btn_mode_aud, inact)
            
            if self.preview_failed:
                self.video_widget.hide()
                self.thumbnail_label.show()
                self.preview_error_lbl.show()
                self.preview_error_lbl.raise_()
            else:
                self.video_widget.show()
                self.thumbnail_label.hide()
                self.preview_error_lbl.hide()
                
        self._update_est_size()
