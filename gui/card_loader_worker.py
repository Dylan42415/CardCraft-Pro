import os
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QRunnable, QThreadPool, QObject, Signal
from PIL import Image

from core import tiff_parser


class CardPreviewWorkerSignals(QObject):
    finished = Signal(int, object, object)  # (slot_index, cache_key, qpixmap)
    failed = Signal(int, str)                # (slot_index, error_message)


class CardPreviewTask(QRunnable):
    """Background task for parsing TIFF/PSD channels and rendering preview RGB pixmaps asynchronously."""

    def __init__(
        self,
        slot_index: int,
        filepath: str,
        mappings: dict,
        visible_layers: list,
        view_mode: str,
        bg_color: tuple,
        dither_settings: dict,
        cache_key: tuple
    ):
        super().__init__()
        self.slot_index = slot_index
        self.filepath = filepath
        self.mappings = mappings
        self.visible_layers = visible_layers
        self.view_mode = view_mode
        self.bg_color = bg_color
        self.dither_settings = dither_settings
        self.cache_key = cache_key
        self.signals = CardPreviewWorkerSignals()

    def run(self):
        try:
            if not self.filepath or not os.path.exists(self.filepath):
                self.signals.failed.emit(self.slot_index, "File not found")
                return

            channels = tiff_parser.parse_tiff_channels(self.filepath)
            card_preview = tiff_parser.render_preview_rgb(
                self.filepath,
                channels,
                self.mappings,
                self.visible_layers,
                self.bg_color,
                dither_settings=self.dither_settings
            )
            
            # Emit PIL image data back to main thread safely
            self.signals.finished.emit(self.slot_index, self.cache_key, card_preview)
        except Exception as e:
            self.signals.failed.emit(self.slot_index, str(e))
