import os
import traceback
from typing import Dict, List, Optional
from PySide6.QtCore import QThread, Signal

from core.models import Project
from core import export_engine, print_validation


class ExportSheetWorker(QThread):
    """Background worker thread for compiling and exporting 600 PPI print sheets."""
    progress_updated = Signal(int, int, str)  # (current_step, total_steps, status_message)
    export_finished = Signal(dict)           # returns dictionary of exported pass filepaths
    export_failed = Signal(str)             # returns error message string

    def __init__(
        self,
        project: Project,
        output_dir: str,
        export_mode: str = "pdf",
        export_dxf: bool = True,
        export_svg_cut: bool = True,
        parent=None
    ):
        super().__init__(parent)
        self.project = project
        self.output_dir = output_dir
        self.export_mode = export_mode
        self.export_dxf = export_dxf
        self.export_svg_cut = export_svg_cut

    def run(self):
        try:
            passes = ["Base Artwork", "White Ink", "Emboss"]
            total_steps = len(passes) + (1 if self.export_dxf or self.export_svg_cut else 0)
            step = 0

            # Run prepress validation
            reports = print_validation.validate_project_prepress(self.project)
            results = {}

            for p_idx, p_name in enumerate(passes):
                step += 1
                self.progress_updated.emit(step, total_steps, f"Compiling 600 PPI {p_name} Pass...")
                
                # Check pass export setting
                if p_name == "White Ink" and not self.project.export_settings.get("export_white_ink", True):
                    continue
                if p_name == "Emboss" and not self.project.export_settings.get("export_emboss", True):
                    continue
                if p_name == "Base Artwork" and not self.project.export_settings.get("export_base_artwork", True):
                    continue

                # Compile pass
                out_files = export_engine.export_print_sheet(
                    self.project,
                    output_dir=self.output_dir,
                    export_mode=self.export_mode,
                    target_pass=p_name,
                    validation_reports=reports
                )
                results[p_name] = out_files

            # Export cut lines if requested
            if self.export_dxf or self.export_svg_cut:
                step += 1
                self.progress_updated.emit(step, total_steps, "Exporting Vector Cut Lines (.dxf / .svg)...")
                cut_files = export_engine.export_cutting_templates(
                    self.project,
                    output_dir=self.output_dir,
                    export_dxf=self.export_dxf,
                    export_svg=self.export_svg_cut
                )
                results["cut_files"] = cut_files

            self.export_finished.emit(results)
        except Exception as e:
            err_msg = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            self.export_failed.emit(err_msg)


class ExportCardsWorker(QThread):
    """Background worker thread for batch exporting individual 600 PPI card files."""
    progress_updated = Signal(int, int, str)
    export_finished = Signal(list)
    export_failed = Signal(str)

    def __init__(self, project: Project, output_dir: str, parent=None):
        super().__init__(parent)
        self.project = project
        self.output_dir = output_dir

    def run(self):
        try:
            slots = [s for s in self.project.card_slots if s.filepath and os.path.exists(s.filepath)]
            total = len(slots)
            exported_paths = []

            for idx, slot in enumerate(slots):
                self.progress_updated.emit(idx + 1, total, f"Exporting Card Slot {slot.index + 1} of {total}...")
                card_paths = export_engine.export_single_card_channels(
                    self.project,
                    slot_index=slot.index,
                    output_dir=self.output_dir
                )
                exported_paths.extend(card_paths)

            self.export_finished.emit(exported_paths)
        except Exception as e:
            err_msg = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            self.export_failed.emit(err_msg)
