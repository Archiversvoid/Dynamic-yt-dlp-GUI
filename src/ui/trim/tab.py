"""The TrimLoad tab: preview a link, pick a start/end, download just that part."""
from PySide6.QtWidgets import QWidget
from src.ui.components.overlay import ProcessingOverlay
from src.ui.trim.download import TrimDownloadMixin
from src.ui.trim.player import TrimPlayerMixin
from src.ui.trim.processing import TrimProcessingMixin
from src.ui.trim.signals import TrimSignals
from src.ui.trim.ui import TrimUiMixin


class TrimLoadTab(TrimUiMixin, TrimPlayerMixin, TrimProcessingMixin, TrimDownloadMixin, QWidget):
    """The TrimLoad tab. Behaviour lives in the mixins (src/ui/trim/*.py); this class wires them together.
    Mixins come BEFORE QWidget so their event overrides (resizeEvent) win."""

    def __init__(self, main_win=None):
        super().__init__()
        self.main_win = main_win
        self.signals = TrimSignals()
        self.signals.loaded.connect(self._on_metadata_loaded)
        self.signals.error.connect(self._on_scrape_error)
        self.signals.phase.connect(self._on_trim_phase)
        
        self.current_info = {}
        self.duration = 1.0
        self.start_trim = 0.0
        self.end_trim = 1.0
        self.is_audio_mode = False
        self.preview_failed = False 

        self._setup_player()
        self._build_ui()

        self._proc_run_id, self._proc_cancel_flag = 0, None
        self.proc_overlay = ProcessingOverlay(self)
        self.proc_overlay.cancel_requested.connect(self._on_processing_cancel)
        self.proc_overlay.retry_requested.connect(self._on_processing_cancel)

        self._show_initial_view()
