"""TrimLoad tab: the preview player: playback, seeking and keeping the trim slider in sync."""
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from src.ui.trim.helpers import format_time_str


class TrimPlayerMixin:
    """The preview player: playback, seeking and keeping the trim slider in sync."""

    def _setup_player(self):
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0) 
        
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        
        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.errorOccurred.connect(self._on_player_error)

    def _on_player_error(self, error, error_string):
        if error != QMediaPlayer.Error.NoError:
            self._show_toast_error("Preview stream unavailable. Thumbnail mode active.")
            self.player.stop()
            self.preview_failed = True
            
            self.video_widget.hide()
            self.thumbnail_label.show()
            self.preview_error_lbl.show()
            self.preview_error_lbl.raise_()
            
            self.preview_error_lbl.adjustSize()
            self.preview_error_lbl.move(
                (self.video_frame.width() - self.preview_error_lbl.width()) // 2,
                (self.video_frame.height() - self.preview_error_lbl.height()) // 2
            )
            self.loading_overlay.stop()

    def _on_media_status_changed(self, status):
        if status in (QMediaPlayer.MediaStatus.BufferingMedia, QMediaPlayer.MediaStatus.LoadingMedia, QMediaPlayer.MediaStatus.StalledMedia):
            self.loading_overlay.start()
        else:
            self.loading_overlay.stop()

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setIcon(self.icon_play)
        else:
            self.player.play()
            self.btn_play.setIcon(self.icon_pause)

    def _seek_player(self, pos_sec):
        self.player.setPosition(int(pos_sec * 1000))

    def _on_slider_position_changed(self, sec):
        if self.range_slider._dragging:
            self.time_lbl.setText(f"{format_time_str(sec)} / {format_time_str(self.duration)}")

    def _on_player_position_changed(self, ms):
        if self.range_slider._dragging:
            return 
        
        sec = ms / 1000.0
        self.range_slider.set_position(sec)
        self.time_lbl.setText(f"{format_time_str(sec)} / {format_time_str(self.duration)}")

        if sec >= self.end_trim:
            self.player.setPosition(int(self.start_trim * 1000))
        elif sec < (self.start_trim - 0.2): 
            self.player.setPosition(int(self.start_trim * 1000))

    def _on_player_duration_changed(self, ms):
        if ms > 0:
            self.duration = ms / 1000.0
            self.range_slider.set_duration(self.duration)

    def _on_trim_range_changed(self, start, end):
        self.start_trim = start
        self.end_trim = end
        self.start_input.setText(format_time_str(start))
        self.end_input.setText(format_time_str(end))
        self._reset_inputs_style()
        self._update_est_size()
