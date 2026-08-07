import os
from typing import List, Dict, Optional, Any
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QImage, QColor, QPen, QBrush, QAction, QKeySequence, QTransform
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSplitter, 
                             QGroupBox, QPushButton, QComboBox, QFileDialog, QMessageBox, QListWidget, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsLineItem, QDialog, QApplication)

from core.models import Project, Layout, CardSlot, PrinterProfile
from core import layout_engine
from core import project_manager
from core import tiff_parser
from core import export_engine
from gui.canvas_view import InteractiveCanvasView
from gui.mapping_panel import MappingPanel
from gui.layout_dialog import LayoutDialog
from gui.export_worker import ExportSheetWorker, ExportCardsWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UV Printing Proxy Card Prepress Application")
        self.resize(1200, 800)

        # Application state
        self.layouts = project_manager.load_layouts()
        self.profiles = project_manager.load_printer_profiles()
        self.project_manager = project_manager.ProjectManager()
        self.project_modified = False
        
        # Initialize default project
        default_layout = self.get_default_layout()
        self.project = Project(
            project_name="Untitled Project",
            layout=default_layout
        )
        self.project.export_settings.setdefault("dither_enabled", "false")
        self.project.export_settings.setdefault("dither_algo", "Ordered Bayer")
        self.project.export_settings.setdefault("dither_strength", "15")
        self.project.export_settings.setdefault("dither_preserve_opaque", "true")
        self.project.export_settings.setdefault("preserve_channel_names", "true")
        self.project_path = None
        self.active_slot_index = -1
        self.view_mode = "Combined" # Combined, Artwork, White, Gloss, Emboss
        self.ppi = 150 # Preview resolution (fast and crisp enough)
        self._preview_cache = {}
        self._reg_pixmap_cache = None

        # Setup main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Create splitters for resizable layout
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self.central_widget)
        self.main_layout.addWidget(self.splitter)

        # Left Settings Panel
        self.mapping_panel = MappingPanel(self)
        self.mapping_panel.setMinimumWidth(300) # Minimum readable width
        self.splitter.addWidget(self.mapping_panel)
        self.splitter.setCollapsible(0, False)  # Prevent sidebar from collapsing to 0

        # Right Area (Canvas + Bottom bar)
        self.right_container = QWidget()
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(10, 10, 10, 10)
        self.right_layout.setSpacing(10)

        # The interactive preview canvas
        self.canvas_view = InteractiveCanvasView(self)
        self.right_layout.addWidget(self.canvas_view, 1)

        # Bottom control panel
        self.init_bottom_panel()
        self.splitter.addWidget(self.right_container)
        self.splitter.setStretchFactor(1, 4)
        
        # Set initial layout widths
        self.splitter.setSizes([350, 850])

        # Initialize Menus
        self.init_menus()

        # Connect signals
        self.connect_signals()
        
        # Sync dithering UI from export settings
        self.sync_dither_ui_from_settings()
 
        # Load initial layout list and setup canvas
        self.mapping_panel.update_layouts_list(self.layouts, self.project.layout.id)
        self.mapping_panel.update_print_passes(self.project.print_passes, self.project.disabled_passes)
        self.sync_project_slots()
        self.render_canvas()
        
        # Setup session persistence and autosave paths
        self.config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.SESSION_FILE = os.path.join(self.config_dir, "session.json")
        self.AUTOSAVE_FILE = os.path.join(self.config_dir, "autosave.json")
        self.EXIT_FLAG_FILE = os.path.join(self.config_dir, ".exit_flag")

        # Start autosave timer (every 30 seconds)
        from PySide6.QtCore import QTimer
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30000) # 30 seconds
        self.autosave_timer.timeout.connect(self.auto_save_session)
        self.autosave_timer.start()

        # Start project autosave timer (every 60 seconds)
        self.project_autosave_timer = QTimer(self)
        self.project_autosave_timer.setInterval(60000) # 60 seconds
        self.project_autosave_timer.timeout.connect(self.auto_save_project)
        self.project_autosave_timer.start()

        # Check and perform session and project recovery
        self.check_session_restore()
        self.check_project_restore()

    def init_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")
        
        new_act = QAction("&New Project", self)
        new_act.setShortcut(QKeySequence.StandardKey.New)
        new_act.triggered.connect(self.new_project_action)
        file_menu.addAction(new_act)

        open_act = QAction("&Open Project...", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self.open_project)
        file_menu.addAction(open_act)

        save_act = QAction("&Save Project", self)
        save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(self.save_project)
        file_menu.addAction(save_act)

        save_as_act = QAction("Save Project &As...", self)
        save_as_act.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_act)

        # Recent Projects Submenu
        self.recent_menu = file_menu.addMenu("Recent Projects")
        
        close_project_act = QAction("&Close Project", self)
        close_project_act.triggered.connect(self.close_project)
        file_menu.addAction(close_project_act)

        file_menu.addSeparator()

        batch_load_files_act = QAction("Batch Load 9 Cards (Select &TIFFs)...", self)
        batch_load_files_act.triggered.connect(self.batch_load_cards_files)
        file_menu.addAction(batch_load_files_act)

        batch_load_folder_act = QAction("Batch Load Cards from &Folder...", self)
        batch_load_folder_act.triggered.connect(self.batch_load_cards_folder)
        file_menu.addAction(batch_load_folder_act)

        file_menu.addSeparator()

        export_layered_act = QAction("Export Layered &TIFF Sheet...", self)
        export_layered_act.triggered.connect(self.export_layered_tiff)
        file_menu.addAction(export_layered_act)

        export_individual_act = QAction("Export Cards as &Individual TIFFs...", self)
        export_individual_act.triggered.connect(self.export_individual_cards_dialog)
        file_menu.addAction(export_individual_act)

        export_flat_act = QAction("Export &Flattened TIFF...", self)
        export_flat_act.triggered.connect(self.export_flat_tiff)
        file_menu.addAction(export_flat_act)

        export_pdf_act = QAction("Export PDF &Preview...", self)
        export_pdf_act.triggered.connect(self.export_pdf_preview)
        file_menu.addAction(export_pdf_act)

        calib_sheet_act = QAction("Generate Print Calibration Sheet...", self)
        calib_sheet_act.triggered.connect(self.generate_print_calibration_sheet)
        file_menu.addAction(calib_sheet_act)

        file_menu.addSeparator()

        save_session_act = QAction("&Save Session...", self)
        save_session_act.triggered.connect(self.manual_save_session)
        file_menu.addAction(save_session_act)

        load_session_act = QAction("&Load Session...", self)
        load_session_act.triggered.connect(self.manual_load_session)
        file_menu.addAction(load_session_act)

        restart_act = QAction("&Restart Application", self)
        restart_act.triggered.connect(self.restart_application)
        file_menu.addAction(restart_act)

        clear_session_act = QAction("Clear Saved Session", self)
        clear_session_act.triggered.connect(self.clear_saved_session)
        file_menu.addAction(clear_session_act)

        file_menu.addSeparator()
        
        exit_act = QAction("E&xit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Layouts Menu
        layouts_menu = menubar.addMenu("&Layouts")
        
        create_layout_act = QAction("&Create Custom Layout...", self)
        create_layout_act.triggered.connect(self.create_layout_dialog)
        layouts_menu.addAction(create_layout_act)
        
        import_layout_act = QAction("&Import Layout JSON...", self)
        import_layout_act.triggered.connect(self.import_layout_json)
        layouts_menu.addAction(import_layout_act)
        
        export_layout_act = QAction("&Export Active Layout JSON...", self)
        export_layout_act.triggered.connect(self.export_active_layout)
        layouts_menu.addAction(export_layout_act)

        layouts_menu.addSeparator()

        import_studio3_act = QAction("Import Layout from Silhouette .&studio3 File...", self)
        import_studio3_act.triggered.connect(self.import_layout_from_studio3)
        layouts_menu.addAction(import_studio3_act)

        # View Menu
        view_menu = menubar.addMenu("&View")
        self.show_measurements_act = QAction("Show Print Measurements", self)
        self.show_measurements_act.setCheckable(True)
        self.show_measurements_act.setChecked(False)
        self.show_measurements_act.triggered.connect(self.on_show_measurements_toggled)
        view_menu.addAction(self.show_measurements_act)

    def init_bottom_panel(self):
        self.bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(self.bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # View Mode selector
        bottom_layout.addWidget(QLabel("View Mode:"))
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["Combined", "Artwork Only", "White Ink Only", "Gloss Only", "Emboss Only"])
        self.view_mode_combo.currentTextChanged.connect(self.change_view_mode)
        bottom_layout.addWidget(self.view_mode_combo)

        bottom_layout.addStretch()

        # Canvas actions: Rotate selected slot
        self.btn_rotate = QPushButton("Rotate Selected Slot ↻")
        self.btn_rotate.clicked.connect(self.rotate_selected_slot)
        bottom_layout.addWidget(self.btn_rotate)
        
        self.btn_delete_card = QPushButton("Clear Card")
        self.btn_delete_card.clicked.connect(self.clear_selected_card)
        bottom_layout.addWidget(self.btn_delete_card)

        bottom_layout.addStretch()

        # Zoom controls
        self.btn_zoom_fit = QPushButton("Fit to Screen")
        self.btn_zoom_fit.clicked.connect(self.canvas_view.reset_view)
        bottom_layout.addWidget(self.btn_zoom_fit)

        bottom_layout.addStretch()

        # Prepress Export Actions
        self.btn_export_tiff = QPushButton("Export Layered TIFF")
        self.btn_export_tiff.setObjectName("primaryButton")
        self.btn_export_tiff.clicked.connect(self.export_layered_tiff)
        bottom_layout.addWidget(self.btn_export_tiff)

        self.btn_export_pdf = QPushButton("Export PDF Preview")
        self.btn_export_pdf.clicked.connect(self.export_pdf_preview)
        bottom_layout.addWidget(self.btn_export_pdf)

        self.right_layout.addWidget(self.bottom_widget)

    def connect_signals(self):
        # Sidebar changes
        self.mapping_panel.layout_changed.connect(self.on_layout_changed)
        self.mapping_panel.print_passes_reordered.connect(self.on_print_passes_reordered)
        self.mapping_panel.mapping_updated.connect(self.on_mapping_updated)
        self.mapping_panel.import_single_tiff.connect(self.import_tiff_files)
        self.mapping_panel.import_folder.connect(self.import_folder)
        self.mapping_panel.save_profile_clicked.connect(self.save_printer_profile)
        self.mapping_panel.load_profile_clicked.connect(self.load_printer_profile)
        self.mapping_panel.channel_enable_toggled.connect(self.on_channel_enable_toggled)
        self.mapping_panel.print_pass_toggled.connect(self.on_print_pass_toggled)
        self.mapping_panel.dither_mode_changed.connect(self.on_dither_mode_changed)
        self.mapping_panel.dither_coverage_changed.connect(self.on_dither_coverage_changed)
        self.mapping_panel.dither_angle_changed.connect(self.on_dither_angle_changed)
        self.mapping_panel.dither_lpi_changed.connect(self.on_dither_lpi_changed)
        self.mapping_panel.dither_dot_shape_changed.connect(self.on_dither_dot_shape_changed)
        self.mapping_panel.dither_preserve_opaque_toggled.connect(self.on_dither_preserve_opaque_toggled)
        self.mapping_panel.dither_texture_changed.connect(self.on_dither_texture_changed)
        self.mapping_panel.dither_duplicate_emboss_toggled.connect(self.on_dither_duplicate_emboss_toggled)
        self.mapping_panel.binary_debug_toggled.connect(self.on_binary_debug_toggled)
        self.mapping_panel.preserve_names_toggled.connect(self.on_preserve_names_toggled)
        self.mapping_panel.printer_profile_changed.connect(self.on_printer_profile_changed)
        self.mapping_panel.btn_calibrate.clicked.connect(self.on_calibrate_clicked)

        # Canvas triggers
        self.canvas_view.slot_clicked.connect(self.on_slot_selected)
        self.canvas_view.file_dropped_on_slot.connect(self.load_card_into_slot)

    # State syncing helper
    def sync_project_slots(self):
        """Ensures the number of card slots in the project matches the active layout grid size."""
        grid = layout_engine.calculate_layout_positions(self.project.layout, self.ppi)
        num_slots = len(grid["slots"])
        
        # Grow/shrink list as needed
        current_slots = {s.slot_index: s for s in self.project.card_slots}
        new_slots = []
        for i in range(num_slots):
            if i in current_slots:
                new_slots.append(current_slots[i])
            else:
                new_slots.append(CardSlot(slot_index=i))
        self.project.card_slots = new_slots

    # Actions: File Handling
    def get_default_layout(self):
        for lay in self.layouts:
            if lay.id == "a4_9_cards_borderless":
                return lay
        return self.layouts[0] if self.layouts else None

    def new_project_action(self):
        if self.check_unsaved_changes():
            self.new_project()

    def new_project(self):
        default_layout = self.get_default_layout()
        self.project = Project(
            project_name="Untitled Project",
            layout=default_layout
        )
        self.project.export_settings["preserve_channel_names"] = "true"
        self.project.export_settings["dither_enabled"] = "false"
        self.project.export_settings["dither_algo"] = "Ordered Bayer"
        self.project.export_settings["dither_strength"] = "15"
        self.project.export_settings["dither_preserve_opaque"] = "true"
        self.project_path = None
        self.active_slot_index = -1
        self.project_modified = False
        self.project_manager.clear_autosave()
        self._preview_cache.clear()
        
        self.mapping_panel.update_print_passes(self.project.print_passes, self.project.disabled_passes)
        self.sync_dither_ui_from_settings()
        self.mapping_panel.show_no_card_selected()
        self.sync_project_slots()
        self.render_canvas()

    def open_project(self):
        if not self.check_unsaved_changes():
            return
        filepath, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Project", 
            "", 
            "OPTCG Project Files (*.optcgproj *.optcgproject);;All Files (*)"
        )
        if filepath:
            try:
                loaded = self.project_manager.load_project(filepath)
                if not self.handle_missing_files(loaded):
                    return # Cancelled
                
                self.project = loaded
                self.project_path = filepath
                self.active_slot_index = -1
                self.project_modified = False
                self.project_manager.clear_autosave()
                self._preview_cache.clear()
                
                # Sync GUI
                self.mapping_panel.update_layouts_list(self.layouts, self.project.layout.id)
                self.mapping_panel.update_print_passes(self.project.print_passes, self.project.disabled_passes)
                self.sync_dither_ui_from_settings()
                self.mapping_panel.show_no_card_selected()
                self.sync_project_slots()
                self.render_canvas()
                self.statusBar().showMessage(f"Project loaded: {filepath}", 4000)
                
                # Add to recent list
                self.project_manager.add_recent_project(filepath)
                self.update_recent_projects_menu()
            except Exception as e:
                QMessageBox.critical(self, "Error Loading Project", f"Failed to parse project file:\n{e}")

    def save_project(self):
        if not self.project_path:
            self.save_project_as()
        else:
            try:
                self.project_manager.save_project(self.project, self.project_path)
                self.project_modified = False
                self.project_manager.clear_autosave()
                self.statusBar().showMessage(f"Project saved: {self.project_path}", 3000)
                self.update_recent_projects_menu()
            except Exception as e:
                QMessageBox.critical(self, "Error Saving Project", f"Failed to save project:\n{e}")

    def save_project_as(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Project As", 
            "", 
            "OPTCG Project Files (*.optcgproj *.optcgproject);;All Files (*)"
        )
        if filepath:
            if not filepath.lower().endswith(('.optcgproj', '.optcgproject')):
                filepath += ".optcgproj"
            self.project_path = filepath
            
            # Set project name to match the file name
            base = os.path.splitext(os.path.basename(filepath))[0]
            self.project.project_name = base
            
            self.save_project()

    def close_project(self):
        if self.check_unsaved_changes():
            self.new_project()

    def check_unsaved_changes(self) -> bool:
        if not self.project_modified:
            return True
            
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "The current project has unsaved changes.\nWould you like to save them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.save_project()
            return not self.project_modified
        elif reply == QMessageBox.StandardButton.No:
            return True
        else:
            return False

    def handle_missing_files(self, project: Project) -> bool:
        missing_slots = []
        for slot in project.card_slots:
            if slot.filepath and not os.path.exists(slot.filepath):
                missing_slots.append(slot)
                
        if not missing_slots:
            return True
            
        files_str = "\n".join(f"- Slot {s.slot_index + 1}: {s.filepath}" for s in missing_slots)
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Missing Files")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(f"The following files could not be found:\n\n{files_str}")
        
        btn_locate = msg.addButton("Locate Files", QMessageBox.ButtonRole.AcceptRole)
        btn_skip = msg.addButton("Skip Missing", QMessageBox.ButtonRole.RejectRole)
        btn_cancel = msg.addButton(QMessageBox.StandardButton.Cancel)
        
        msg.exec()
        
        if msg.clickedButton() == btn_locate:
            # Let the user select replacements for each missing file
            for slot in missing_slots:
                filename = os.path.basename(slot.filepath)
                filepath, _ = QFileDialog.getOpenFileName(
                    self,
                    f"Locate File for Slot {slot.slot_index + 1} ({filename})",
                    "",
                    "TIFF Images (*.tiff *.tif)"
                )
                if filepath:
                    slot.filepath = filepath
                else:
                    # Skip this specific file if cancelled
                    slot.filepath = None
            return True
        elif msg.clickedButton() == btn_skip:
            # Clear missing file paths
            for slot in missing_slots:
                slot.filepath = None
            return True
        else:
            # Cancel the open project operation entirely
            return False

    def update_recent_projects_menu(self):
        self.recent_menu.clear()
        recent = self.project_manager.load_recent_projects()
        
        if not recent:
            no_act = QAction("No Recent Projects", self)
            no_act.setEnabled(False)
            self.recent_menu.addAction(no_act)
            return
            
        for path in recent:
            act = QAction(path, self)
            act.triggered.connect(lambda checked=False, p=path: self.open_recent_project(p))
            self.recent_menu.addAction(act)
            
        self.recent_menu.addSeparator()
        clear_act = QAction("Clear Recent List", self)
        clear_act.triggered.connect(self.clear_recent_list)
        self.recent_menu.addAction(clear_act)

    def open_recent_project(self, filepath: str):
        if not self.check_unsaved_changes():
            return
        try:
            loaded = self.project_manager.load_project(filepath)
            if not self.handle_missing_files(loaded):
                return
            
            self.project = loaded
            self.project_path = filepath
            self.active_slot_index = -1
            self.project_modified = False
            self.project_manager.clear_autosave()
            
            # Sync GUI
            self.mapping_panel.update_layouts_list(self.layouts, self.project.layout.id)
            self.mapping_panel.update_print_passes(self.project.print_passes, self.project.disabled_passes)
            self.sync_dither_ui_from_settings()
            self.mapping_panel.show_no_card_selected()
            self.sync_project_slots()
            self.render_canvas()
            
            self.statusBar().showMessage(f"Project loaded: {filepath}", 4000)
            self.project_manager.add_recent_project(filepath)
            self.update_recent_projects_menu()
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Project", f"Failed to parse project file:\n{e}")

    def clear_recent_list(self):
        self.project_manager.clear_recent_projects()
        self.update_recent_projects_menu()

    def auto_save_project(self):
        if self.project_modified:
            self.project_manager.save_autosave(self.project)

    def check_project_restore(self):
        autosaved_project = self.project_manager.load_autosave()
        if autosaved_project:
            reply = QMessageBox.question(
                self,
                "Project Recovery",
                "An unsaved project autosave was found from a previous session.\nWould you like to restore it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.project = autosaved_project
                self.project_modified = True
                
                # Sync GUI
                self.mapping_panel.update_layouts_list(self.layouts, self.project.layout.id)
                self.mapping_panel.update_print_passes(self.project.print_passes, self.project.disabled_passes)
                self.sync_dither_ui_from_settings()
                self.mapping_panel.show_no_card_selected()
                self.sync_project_slots()
                self.render_canvas()
                self.statusBar().showMessage("Restored unsaved project from autosave.", 4000)
            else:
                self.project_manager.clear_autosave()

    # Layout changes
    def on_layout_changed(self, layout_id: str):
        selected_layout = next((lay for lay in self.layouts if lay.id == layout_id), None)
        if selected_layout:
            self.project.layout = selected_layout
            self.sync_project_slots()
            self.render_canvas()
            self.trigger_autosave()

    def on_print_passes_reordered(self, print_passes: list):
        self.project.print_passes = print_passes
        # Re-render active selected card mapping combo choices
        if self.active_slot_index != -1:
            self.on_slot_selected(self.active_slot_index)
        self.trigger_autosave()

    # Dynamic mapping updates
    def on_mapping_updated(self, source_ch: str, target_pass: str):
        # Apply mapping to all slots in the project containing this channel
        for slot in self.project.card_slots:
            if slot.filepath:
                try:
                    channels = tiff_parser.parse_tiff_channels(slot.filepath)
                    has_ch = source_ch == "Base Artwork (RGB)" or any(ch.name == source_ch for ch in channels)
                    if has_ch:
                        slot.mappings[source_ch] = target_pass
                except Exception:
                    pass
                    
        # Apply to the active slot state directly
        if self.active_slot_index != -1:
            slot = self.project.card_slots[self.active_slot_index]
            slot.mappings[source_ch] = target_pass
            
        # Re-render canvas & update mappings sidebar to show status
        self.render_canvas()
        if self.active_slot_index != -1:
            self.on_slot_selected(self.active_slot_index)
        self.trigger_autosave()

    def on_channel_enable_toggled(self, src_ch: str, enabled: bool):
        # Apply to all slots in the project as a global convenience
        for slot in self.project.card_slots:
            if slot.filepath:
                try:
                    channels = tiff_parser.parse_tiff_channels(slot.filepath)
                    has_ch = src_ch == "Base Artwork (RGB)" or any(ch.name == src_ch for ch in channels)
                    if has_ch:
                        if not enabled:
                            if src_ch not in slot.disabled_channels:
                                slot.disabled_channels.append(src_ch)
                        else:
                            if src_ch in slot.disabled_channels:
                                slot.disabled_channels.remove(src_ch)
                except Exception:
                    pass
                    
        # Apply to the active slot state directly
        if self.active_slot_index != -1:
            slot = self.project.card_slots[self.active_slot_index]
            if not enabled:
                if src_ch not in slot.disabled_channels:
                    slot.disabled_channels.append(src_ch)
            else:
                if src_ch in slot.disabled_channels:
                    slot.disabled_channels.remove(src_ch)
                    
        # Re-render canvas & update mappings sidebar to show status
        self.render_canvas()
        if self.active_slot_index != -1:
            self.on_slot_selected(self.active_slot_index)
        self.trigger_autosave()

    def on_print_pass_toggled(self, pass_name: str, enabled: bool):
        if not enabled:
            if pass_name not in self.project.disabled_passes:
                self.project.disabled_passes.append(pass_name)
        else:
            if pass_name in self.project.disabled_passes:
                self.project.disabled_passes.remove(pass_name)
        # Re-render canvas & mappings sidebar
        self.render_canvas()
        if self.active_slot_index != -1:
            self.on_slot_selected(self.active_slot_index)
        self.trigger_autosave()

    def on_preserve_names_toggled(self, checked: bool):
        self.project.export_settings["preserve_channel_names"] = "true" if checked else "false"
        self.trigger_autosave()

    # Slot Selection and File Drop Loading
    def on_slot_selected(self, slot_index: int):
        self.active_slot_index = slot_index
        slot = self.project.card_slots[slot_index]
        
        if slot.filepath:
            card_name = os.path.basename(slot.filepath)
            try:
                channels = tiff_parser.parse_tiff_channels(slot.filepath)
                # Map default if empty
                if not slot.mappings:
                    if self.project.printer_profile:
                        slot.mappings = self.apply_profile_mappings(channels, self.project.printer_profile)
                    else:
                        slot.mappings = self.auto_map_channels(channels)
                
                self.mapping_panel.update_layer_mappings(card_name, channels, slot.mappings, slot.disabled_channels, self.project.print_passes)
                self.sync_dither_ui_from_settings()
            except Exception as e:
                self.statusBar().showMessage(f"Failed to inspect card: {e}")
        else:
            self.mapping_panel.show_no_card_selected()
            self.sync_dither_ui_from_settings()
            
        self.update_print_info_readout()
        self.render_canvas()

    def load_card_into_slot(self, slot_index: int, filepath: str, block_render: bool = False):
        slot = self.project.card_slots[slot_index]
        slot.filepath = filepath
        slot.mappings = {} # Clear mappings to re-detect
        slot.disabled_channels = []
        
        # Apply profile or auto map
        try:
            channels = tiff_parser.parse_tiff_channels(filepath)
            if self.project.printer_profile:
                slot.mappings = self.apply_profile_mappings(channels, self.project.printer_profile)
            else:
                slot.mappings = self.auto_map_channels(channels)
                
            # Smart propagation: inherit mappings and disabled states from any other configured slots in the project
            for existing_slot in self.project.card_slots:
                if existing_slot.filepath and existing_slot.slot_index != slot_index:
                    # Propagate mappings for matching channel names
                    for ch_name, target in existing_slot.mappings.items():
                        has_ch = ch_name == "Base Artwork (RGB)" or any(c.name == ch_name for c in channels)
                        if has_ch:
                            slot.mappings[ch_name] = target
                    # Propagate disabled states for matching channel names
                    for dis_ch in existing_slot.disabled_channels:
                        has_ch = dis_ch == "Base Artwork (RGB)" or any(c.name == dis_ch for c in channels)
                        if has_ch:
                            if dis_ch not in slot.disabled_channels:
                                slot.disabled_channels.append(dis_ch)
        except Exception as e:
            slot.filepath = None # Reset
            if not block_render:
                QMessageBox.critical(self, "Error Loading Card", f"Failed to load card assets:\n{e}")
            else:
                print(f"Error loading {filepath}: {e}")
            return
                
        if not block_render:
            self.on_slot_selected(slot_index)

    def auto_map_channels(self, channels: list) -> dict:
        """Automatically detects standard RGB color and mask channels and maps them to UV passes."""
        mappings = {}
        
        # Sort channels so that global spot channels (page_index == -1) are processed first
        sorted_channels = sorted(channels, key=lambda c: 0 if c.page_index == -1 else 1)
        
        # Keep track of which print passes have been assigned
        assigned_passes = set()
        
        for ch in sorted_channels:
            name = ch.name.lower()
            
            # Map RGB components
            if any(k in name for k in ("red", "green", "blue", "cyan", "magenta", "yellow", "black", "alpha", "transparency")):
                mappings[ch.name] = "Base Artwork"
                continue
                
            # Map spot channels
            target_pass = None
            if name == "1" or "white" in name or "spot1" in name or "spot_1" in name:
                target_pass = "White Ink"
            elif name == "3" or "emboss" in name or "height" in name or "bump" in name or "spot2" in name or "spot_2" in name:
                target_pass = "Emboss"
            elif "gloss" in name or "varnish" in name or "spot3" in name or "spot_3" in name:
                target_pass = "Gloss"
                
            if target_pass:
                # Only map if this print pass has not been assigned to a higher-precedence channel yet
                if target_pass not in assigned_passes:
                    mappings[ch.name] = target_pass
                    assigned_passes.add(target_pass)
                    
        # If still unmapped (like a simple 3-channel RGB image with default page-channel names),
        # map first 3 channels to Base Artwork
        mapped_targets = [v for v in mappings.values() if v == "Base Artwork"]
        if not mapped_targets and len(channels) >= 3:
            for i in range(min(3, len(channels))):
                mappings[channels[i].name] = "Base Artwork"
            if len(channels) >= 4:
                mappings[channels[3].name] = "Base Artwork" # map alpha/transparency too
                
        return mappings

    def apply_profile_mappings(self, channels, profile: PrinterProfile) -> dict:
        import re
        mappings = {}
        for ch in channels:
            # 1. Exact match
            if isinstance(profile.mappings, dict) and ch.name in profile.mappings:
                mappings[ch.name] = profile.mappings[ch.name]
                continue
            # 2. Pattern matching (supporting dict rules or legacy MappingEntry lists)
            matched = False
            if isinstance(profile.mappings, dict):
                for pattern, target in profile.mappings.items():
                    try:
                        if re.match(pattern, ch.name, re.IGNORECASE):
                            mappings[ch.name] = target
                            matched = True
                            break
                    except Exception:
                        pass
            else:
                # Fallback for old list-based MappingEntry profiles
                for rule in profile.mappings:
                    try:
                        pattern = getattr(rule, 'source_pattern', str(rule.get('source_pattern', '')))
                        target = getattr(rule, 'target_layer', str(rule.get('target_layer', '')))
                        if re.match(pattern, ch.name, re.IGNORECASE):
                            mappings[ch.name] = target
                            matched = True
                            break
                    except Exception:
                        pass
            if matched:
                continue
        return mappings

    # Layout Creation, Import and Export Handlers
    def create_layout_dialog(self):
        dialog = LayoutDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                new_layout = dialog.get_layout_definition()
                self.layouts.append(new_layout)
                
                # Save to disk
                project_manager.save_custom_layouts(self.layouts)
                
                # Update combobox
                self.mapping_panel.update_layouts_list(self.layouts, new_layout.id)
                self.on_layout_changed(new_layout.id)
                QMessageBox.information(self, "Success", f"Custom layout '{new_layout.name}' created and saved!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to define custom layout:\n{e}")

    def import_layout_json(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Layout JSON", "", "JSON Files (*.json)")
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    import json
                    data = json.load(f)
                    new_layout = Layout(**data)
                
                # Append and save
                self.layouts.append(new_layout)
                project_manager.save_custom_layouts(self.layouts)
                
                # Refresh combobox
                self.mapping_panel.update_layouts_list(self.layouts, new_layout.id)
                self.on_layout_changed(new_layout.id)
                QMessageBox.information(self, "Success", f"Layout '{new_layout.name}' imported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import layout:\n{e}")

    def export_active_layout(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Layout JSON", f"{self.project.layout.id}.json", "JSON Files (*.json)")
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.project.layout.model_dump_json(indent=4))
                QMessageBox.information(self, "Success", f"Active layout exported to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export layout:\n{e}")

    def rotate_selected_slot(self):
        if self.active_slot_index == -1:
            QMessageBox.warning(self, "No Selection", "Please click on a card slot to rotate it first.")
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.rotation = (slot.rotation + 90) % 360
        self.render_canvas()

    def clear_selected_card(self):
        if self.active_slot_index == -1:
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.filepath = None
        slot.mappings = {}
        slot.disabled_channels = set()
        if self.active_slot_index in self._preview_cache:
            del self._preview_cache[self.active_slot_index]
        self.mapping_panel.show_no_card_selected()
        self.render_canvas()

    def change_view_mode(self, mode: str):
        self.view_mode = mode
        self.render_canvas()

    # Import actions
    def import_tiff_files(self):
        filepaths, _ = QFileDialog.getOpenFileNames(self, "Import Layered TIFF", "", "TIFF Images (*.tiff *.tif)")
        if filepaths:
            # Auto-fill starting from the first empty slot or active slot
            start_idx = max(0, self.active_slot_index)
            filled = 0
            last_loaded_idx = -1
            for fp in filepaths:
                # Find next empty slot
                found = False
                for idx in range(start_idx, len(self.project.card_slots)):
                    if not self.project.card_slots[idx].filepath:
                        self.load_card_into_slot(idx, fp, block_render=True)
                        start_idx = idx + 1
                        last_loaded_idx = idx
                        found = True
                        filled += 1
                        break
                if not found:
                    # Append or override the active slot if full
                    if self.active_slot_index != -1:
                        self.load_card_into_slot(self.active_slot_index, fp, block_render=True)
                        last_loaded_idx = self.active_slot_index
                        filled += 1
                    break
            if filled > 0:
                if last_loaded_idx != -1:
                    self.on_slot_selected(last_loaded_idx)
                else:
                    self.render_canvas()
            self.statusBar().showMessage(f"Imported {filled} cards onto layout.", 3000)

    def import_folder(self):
        dirpath = QFileDialog.getExistingDirectory(self, "Select Folder to Import")
        if dirpath:
            # List all TIFFs
            files = [os.path.join(dirpath, f) for f in os.listdir(dirpath) if f.lower().endswith(('.tiff', '.tif'))]
            if files:
                start_idx = 0
                filled = 0
                last_loaded_idx = -1
                for fp in files:
                    # Find next empty slot
                    while start_idx < len(self.project.card_slots) and self.project.card_slots[start_idx].filepath:
                        start_idx += 1
                        
                    if start_idx >= len(self.project.card_slots):
                        break
                        
                    self.load_card_into_slot(start_idx, fp, block_render=True)
                    last_loaded_idx = start_idx
                    filled += 1
                    start_idx += 1
                    
                if filled > 0:
                    if last_loaded_idx != -1:
                        self.on_slot_selected(last_loaded_idx)
                    else:
                        self.render_canvas()
                self.statusBar().showMessage(f"Imported {filled} cards from folder.", 3000)
            else:
                QMessageBox.information(self, "Empty Directory", "No TIFF/PSD files found in the selected folder.")

    # Profile actions
    def save_printer_profile(self):
        # Create mapping from current selection or input rules
        if self.active_slot_index == -1:
            QMessageBox.warning(self, "No Active Mapping", "Please select a card slot first to save its configuration as a profile.")
            return
            
        text, ok = QInputDialog.getText(self, "Save Profile", "Enter printer profile name:")
        if ok and text.strip():
            profile_name = text.strip()
            slot = self.project.card_slots[self.active_slot_index]
            
            profile = PrinterProfile(
                profile_name=profile_name,
                layout_id=self.project.layout.id,
                print_passes=list(self.project.print_passes),
                disabled_passes=list(self.project.disabled_passes),
                mappings=dict(slot.mappings),
                disabled_channels=list(slot.disabled_channels)
            )
            
            try:
                # Save standalone file and database
                filepath = project_manager.save_printer_profile(profile)
                self.profiles = project_manager.load_printer_profiles()
                self.project.printer_profile = profile
                QMessageBox.information(self, "Success", f"Profile '{profile_name}' saved successfully to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Failed to save profile:\n{e}")

    def load_printer_profile(self):
        # Let user select from dialog box or open a standalone profile JSON file
        self.profiles = project_manager.load_printer_profiles()
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Load Profile")
        msg.setText("Select how you want to load the printer profile:")
        btn_list = msg.addButton("Choose from Saved List", QMessageBox.ButtonRole.AcceptRole)
        btn_file = msg.addButton("Open standalone JSON File...", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg.addButton(QMessageBox.StandardButton.Cancel)
        msg.exec()
        
        selected_profile = None
        if msg.clickedButton() == btn_list:
            if not self.profiles:
                QMessageBox.information(self, "No Profiles", "No saved printer profiles available.")
                return
            profile_names = [p.profile_name for p in self.profiles]
            name, ok = QInputDialog.getItem(self, "Load Profile", "Select a profile to load:", profile_names, 0, False)
            if ok and name:
                selected_profile = next((p for p in self.profiles if p.profile_name == name), None)
        elif msg.clickedButton() == btn_file:
            filepath, _ = QFileDialog.getOpenFileName(self, "Load Standalone Profile JSON", "profiles", "JSON Profiles (*.json)")
            if filepath:
                try:
                    selected_profile = project_manager.load_printer_profile(filepath)
                except Exception as e:
                    QMessageBox.critical(self, "Load Failed", f"Failed to load standalone profile:\n{e}")
                    return
        else:
            return # Cancelled
            
        if selected_profile:
            profile = selected_profile
            try:
                self.project.printer_profile = profile
                
                # 1. Apply layout
                found_layout = None
                for lay in self.layouts:
                    if lay.id == profile.layout_id:
                        found_layout = lay
                        break
                if found_layout:
                    self.project.layout = found_layout
                    self.mapping_panel.update_layouts_list(self.layouts, found_layout.id)
                    self.sync_project_slots()
                    
                # 2. Apply print passes & disabled state
                if profile.print_passes:
                    self.project.print_passes = list(profile.print_passes)
                if profile.disabled_passes is not None:
                    self.project.disabled_passes = list(profile.disabled_passes)
                self.mapping_panel.update_print_passes(self.project.print_passes, self.project.disabled_passes)
                
                # 3. Apply mappings & disabled channels to all slots containing files
                for slot in self.project.card_slots:
                    if slot.filepath:
                        slot.mappings = dict(profile.mappings)
                        slot.disabled_channels = list(profile.disabled_channels)
                        
                # 4. Sync preserve channel names checkbox if present in settings
                preserve = self.project.export_settings.get("preserve_channel_names", "true") == "true"
                self.mapping_panel.cb_preserve_names.setChecked(preserve)
                
                # Refresh active slot selection and canvas
                if self.active_slot_index != -1:
                    self.on_slot_selected(self.active_slot_index)
                else:
                    self.render_canvas()
                    
                QMessageBox.information(self, "Profile Loaded", f"Applied profile configuration '{profile.profile_name}' to layout and loaded cards.")
            except Exception as e:
                QMessageBox.critical(self, "Load Failed", f"Failed to apply printer profile:\n{e}")

    def _get_slot_cache_key(self, p_slot, view_mode):
        # Create a stable, hashable tuple of mappings, disabled channels, and dither settings
        mappings_tuple = tuple(sorted(p_slot.mappings.items())) if p_slot.mappings else ()
        disabled_tuple = tuple(sorted(p_slot.disabled_channels)) if p_slot.disabled_channels else ()
        dither_tuple = tuple(sorted(p_slot.dither_settings.items())) if p_slot.dither_settings else ()
        rotation_val = p_slot.rotation
        return (p_slot.filepath, view_mode, mappings_tuple, disabled_tuple, dither_tuple, rotation_val)

    # High-performance Canvas Rendering
    def render_canvas(self):
        # 1. Compute pixel sizes based on PPI
        grid = layout_engine.calculate_layout_positions(self.project.layout, self.ppi)
        scene = self.canvas_view.scene
        scene.clear()

        page_w = grid["page_width"]
        page_h = grid["page_height"]
        
        # Set scene boundary size
        self.canvas_view.set_scene_rect(page_w, page_h)

        # 2. Draw sheet paper background
        sheet_rect = QGraphicsRectItem(0, 0, page_w, page_h)
        sheet_rect.setBrush(QBrush(QColor("#ffffff")))
        sheet_rect.setPen(QPen(QColor("#2d2d39"), 1))
        scene.addItem(sheet_rect)

        # 3. Render and draw registration marks (cached to prevent allocation lags)
        reg_cache_key = (self.project.layout.id, page_w, page_h, self.ppi)
        if getattr(self, "_reg_pixmap_cache", None) and self._reg_pixmap_cache[0] == reg_cache_key:
            pixmap_reg = self._reg_pixmap_cache[1]
        else:
            reg_img = layout_engine.draw_registration_marks(self.project.layout, self.ppi)
            reg_data = reg_img.convert("RGBA").tobytes("raw", "RGBA")
            q_img = QImage(reg_data, page_w, page_h, QImage.Format.Format_RGBA8888)
            pixmap_reg = QPixmap.fromImage(q_img)
            self._reg_pixmap_cache = (reg_cache_key, pixmap_reg)
        
        reg_item = QGraphicsPixmapItem(pixmap_reg)
        scene.addItem(reg_item)

        # 4. Map View Mode options to active visible layers
        # Visibility: Base Artwork, White Ink, Gloss, Emboss
        visible_layers = []
        if self.view_mode == "Combined":
            visible_layers = ["Base Artwork", "White Ink", "Gloss", "Emboss"]
        elif self.view_mode == "Artwork Only":
            visible_layers = ["Base Artwork"]
        elif self.view_mode == "White Ink Only":
            visible_layers = ["White Ink"]
        elif self.view_mode == "Gloss Only":
            visible_layers = ["Gloss"]
        elif self.view_mode == "Emboss Only":
            visible_layers = ["Emboss"]

        # 5. Render card slots and their content
        for slot in grid["slots"]:
            s_idx = slot["index"]
            sx = slot["x"]
            sy = slot["y"]
            sw = slot["width"]
            sh = slot["height"]

            # Load actual card state
            p_slot = self.project.card_slots[s_idx]

            # If card is loaded, render its preview
            card_item = None
            if p_slot.filepath and os.path.exists(p_slot.filepath):
                try:
                    cache_key = self._get_slot_cache_key(p_slot, self.view_mode)
                    cached_entry = self._preview_cache.get(s_idx)
                    
                    if cached_entry and cached_entry[0] == cache_key:
                        pixmap_card = cached_entry[1]
                    else:
                        channels = tiff_parser.parse_tiff_channels(p_slot.filepath)
                        # Set background depending on view mode (combined=white, single-mask=black for contrast)
                        bg = (255, 255, 255) if self.view_mode in ("Combined", "Artwork Only") else (0, 0, 0)
                        
                        card_preview = tiff_parser.render_preview_rgb(
                            p_slot.filepath, channels, p_slot.mappings, visible_layers, bg,
                            dither_settings=p_slot.dither_settings
                        )
                        
                        # Convert to QPixmap
                        card_data = card_preview.convert("RGBA").tobytes("raw", "RGBA")
                        c_h, c_w = card_preview.height, card_preview.width
                        q_c_img = QImage(card_data, c_w, c_h, QImage.Format.Format_RGBA8888).copy()
                        pixmap_card = QPixmap.fromImage(q_c_img)
                        self._preview_cache[s_idx] = (cache_key, pixmap_card)

                    # Scale the pixmap directly to the slot dimensions
                    scaled_pixmap = pixmap_card.scaled(int(sw), int(sh), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    
                    card_item = QGraphicsPixmapItem(scaled_pixmap)
                    card_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
                    
                    # Set rotation pivot center to the center of the slot
                    card_item.setTransformOriginPoint(sw / 2, sh / 2)
                    card_item.setRotation(p_slot.rotation)
                    
                    # Position slot
                    card_item.setPos(sx, sy)
                    card_item.setData(0, s_idx) # Store slot index
                    scene.addItem(card_item)
                except Exception as e:
                    print(f"Error rendering card slot {s_idx}: {e}")

            # Draw slot boundary and interaction rectangles
            slot_rect_item = QGraphicsRectItem(sx, sy, sw, sh)
            slot_rect_item.setData(0, s_idx) # Store slot index
            
            # Highlight border if selected
            if s_idx == self.active_slot_index:
                pen = QPen(QColor("#8b5cf6"), 3, Qt.PenStyle.SolidLine)
                slot_rect_item.setPen(pen)
                # Soft purple fill overlay for active selection
                slot_rect_item.setBrush(QBrush(QColor(139, 92, 246, 30)))
                
                # Check if measurements toggle is enabled
                if hasattr(self, "show_measurements_act") and self.show_measurements_act.isChecked():
                    # Horizontal measurement line
                    h_line = QGraphicsLineItem(sx, sy - 15, sx + sw, sy - 15)
                    h_line.setPen(QPen(QColor("#8b5cf6"), 1.5))
                    scene.addItem(h_line)
                    
                    # Ticks
                    t1 = QGraphicsLineItem(sx, sy - 20, sx, sy - 10)
                    t1.setPen(QPen(QColor("#8b5cf6"), 1.5))
                    scene.addItem(t1)
                    t2 = QGraphicsLineItem(sx + sw, sy - 20, sx + sw, sy - 10)
                    t2.setPen(QPen(QColor("#8b5cf6"), 1.5))
                    scene.addItem(t2)
                    
                    # Text
                    w_mm = self.project.layout.card_size.width_mm
                    w_text = scene.addText(f"{w_mm:.1f} mm")
                    w_text.setDefaultTextColor(QColor("#8b5cf6"))
                    w_text_font = w_text.font()
                    w_text_font.setPointSize(9)
                    w_text_font.setBold(True)
                    w_text.setFont(w_text_font)
                    w_text.setPos(sx + sw/2 - w_text.boundingRect().width()/2, sy - 32)
                    
                    # Vertical line
                    v_line = QGraphicsLineItem(sx - 15, sy, sx - 15, sy + sh)
                    v_line.setPen(QPen(QColor("#8b5cf6"), 1.5))
                    scene.addItem(v_line)
                    
                    # Ticks
                    t3 = QGraphicsLineItem(sx - 20, sy, sx - 10, sy)
                    t3.setPen(QPen(QColor("#8b5cf6"), 1.5))
                    scene.addItem(t3)
                    t4 = QGraphicsLineItem(sx - 20, sy + sh, sx - 10, sy + sh)
                    t4.setPen(QPen(QColor("#8b5cf6"), 1.5))
                    scene.addItem(t4)
                    
                    # Text
                    h_mm = self.project.layout.card_size.height_mm
                    h_text = scene.addText(f"{h_mm:.1f} mm")
                    h_text.setDefaultTextColor(QColor("#8b5cf6"))
                    h_text_font = h_text.font()
                    h_text_font.setPointSize(9)
                    h_text_font.setBold(True)
                    h_text.setFont(h_text_font)
                    # Rotate vertical text by -90 deg
                    h_text.setTransformOriginPoint(h_text.boundingRect().width()/2, h_text.boundingRect().height()/2)
                    h_text.setRotation(-90)
                    h_text.setPos(sx - 35 - h_text.boundingRect().width()/2, sy + sh/2 - h_text.boundingRect().height()/2)
            else:
                pen = QPen(QColor("#2d2d39"), 1, Qt.PenStyle.DashLine)
                slot_rect_item.setPen(pen)
                slot_rect_item.setBrush(QBrush(QColor(0, 0, 0, 0))) # Transparent

            scene.addItem(slot_rect_item)

            # Draw labels on empty slots
            if card_item is None:
                txt = QGraphicsSimpleTextItem(f"Slot {s_idx + 1}\n(Drop TIFF Here)")
                txt.setBrush(QBrush(QColor("#94a3b8")))
                # Center text inside slot
                txt_w = txt.boundingRect().width()
                txt_h = txt.boundingRect().height()
                txt.setPos(sx + (sw - txt_w)/2, sy + (sh - txt_h)/2)
                txt.setData(0, s_idx)
                scene.addItem(txt)

    def validate_project_before_export(self) -> bool:
        """Validates project mappings and states before export, showing warnings if issues exist."""
        # 1. Check if any cards are loaded
        has_cards = any(slot.filepath for slot in self.project.card_slots)
        if not has_cards:
            QMessageBox.warning(self, "Export Validation", "No card files are loaded in any slots. Please load at least one card.")
            return False

        # 2. Check if all enabled print passes have at least one mapped source channel
        enabled_passes = [p for p in self.project.print_passes if p not in self.project.disabled_passes]
        if not enabled_passes:
            QMessageBox.warning(self, "Export Validation", "All print passes are disabled. Please enable at least one print pass (e.g. Base Artwork or White Ink).")
            return False

        warnings = []
        for pass_name in enabled_passes:
            # Check if mapped and enabled in any slot
            mapped_count = 0
            for slot in self.project.card_slots:
                if slot.filepath:
                    for ch_name, target in slot.mappings.items():
                        if target == pass_name and ch_name not in slot.disabled_channels:
                            mapped_count += 1
            if mapped_count == 0:
                warnings.append(f"Print pass '{pass_name}' is enabled but has no card channels mapped to it.")

        if warnings:
            warning_text = "The following issues were detected:\n\n" + "\n".join(f"- {w}" for w in warnings) + "\n\nDo you want to continue with the export anyway?"
            reply = QMessageBox.question(self, "Export Warning", warning_text, 
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return False

        return True

    # Prepress Export Engine Methods
    def export_layered_tiff(self):
        if not self.validate_project_before_export():
            return
        # 1. Ask save location
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Layered TIFF", "", "TIFF Images (*.tiff *.tif)")
        if filepath:
            self.statusBar().showMessage("Rendering layered TIFF passes...")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                # Compile at 600 DPI/PPI for premium high-fidelity print quality
                filepath, validation_reports = export_engine.export_project(self.project, filepath, "layered_tiff", 600)
                QApplication.restoreOverrideCursor()
                
                # Show debug validation popup dialog if enabled
                binary_debug = self.project.export_settings.get("binary_debug", False)
                if isinstance(binary_debug, str):
                    binary_debug = binary_debug.lower() == "true"
                    
                if binary_debug and validation_reports:
                    total_checked = 0
                    total_passed = 0
                    total_repaired = 0
                    total_failed = 0
                    
                    details = ""
                    for r in validation_reports:
                        if r["stage_name"] == "Final TIFF Assembly (Before Repair)":
                            total_checked += 1
                            if r["pass"]:
                                total_passed += 1
                            elif r["repaired"]:
                                total_repaired += 1
                            else:
                                total_failed += 1
                                
                            status_str = "PASSED" if r["pass"] else ("AUTO-REPAIRED" if r["repaired"] else "FAILED")
                            color = "#22c55e" if r["pass"] else ("#fbbf24" if r["repaired"] else "#ef4444")
                            
                            details += f"<b>Pass Name</b>: {r['pass_name']}<br>"
                            details += f"<b>Stage</b>: {r['stage_name']}<br>"
                            details += f"<b>Status</b>: <span style='color:{color}'>{status_str}</span><br>"
                            details += f"<b>Shape</b>: {r['shape']} | <b>Type</b>: {r['dtype']}<br>"
                            details += f"<b>Unique Values</b>: {r['unique_values']}<br>"
                            if r["invalid_values"]:
                                details += f"<b>Unexpected Values</b>: <span style='color:#ef4444'>{r['invalid_values']}</span><br>"
                            details += f"<b>Active Ink (0)</b>: {r['black_pixels']:,} ({r['coverage_percentage']:.1f}%)<br>"
                            details += f"<b>No Ink (255)</b>: {r['white_pixels']:,}<br>"
                            details += "<hr>"
                            
                        if total_failed > 0:
                            status_summary = "<span style='color:#ef4444; font-weight:bold;'>FAILED</span>"
                        elif total_repaired > 0:
                            status_summary = "<span style='color:#fbbf24; font-weight:bold;'>SUCCESS (Auto-Repaired)</span>"
                        else:
                            status_summary = "<span style='color:#22c55e; font-weight:bold;'>SUCCESS</span>"
                            
                        summary_html = (
                            f"<h3>Validation Summary</h3>"
                            f"<b>Spot Channels Checked</b>: {total_checked}<br>"
                            f"<b>Passed</b>: {total_passed}<br>"
                            f"<b>Auto-Repaired</b>: {total_repaired}<br>"
                            f"<b>Failed</b>: {total_failed}<br><br>"
                            f"<b>Export Status</b>: {status_summary}<br><br>"
                            f"<h3>Detailed Stage Logs</h3>"
                            f"{details}"
                        )
                        
                        msg_box = QMessageBox(self)
                        msg_box.setWindowTitle("Binary Spot Channel Debug Report")
                        msg_box.setTextFormat(Qt.TextFormat.RichText)
                        msg_box.setText(summary_html)
                        msg_box.exec()
                    else:
                        QMessageBox.information(self, "Export Successful", f"Layered TIFF exported to:\n{filepath}")
                        
                    self.statusBar().showMessage("Layered TIFF exported successfully.", 4000)
            except Exception as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(self, "Export Failed", f"Failed to export layered TIFF:\n{e}")
                self.statusBar().showMessage("Layered TIFF export failed.", 4000)

    def export_pdf_preview(self):
        if not self.validate_project_before_export():
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Export PDF Preview", "", "PDF Files (*.pdf)")
        if filepath:
            self.statusBar().showMessage("Rendering PDF layout sheet...")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                export_engine.export_project(self.project, filepath, "pdf_preview", 600)
                QApplication.restoreOverrideCursor()
                QMessageBox.information(self, "Export Successful", f"PDF sheet layout exported to:\n{filepath}")
                self.statusBar().showMessage("PDF exported successfully.", 4000)
            except Exception as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(self, "Export Failed", f"Failed to export PDF:\n{e}")
                self.statusBar().showMessage("PDF export failed.", 4000)

    def export_flat_tiff(self):
        if not self.validate_project_before_export():
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Flattened TIFF", "", "TIFF Images (*.tiff *.tif)")
        if filepath:
            self.statusBar().showMessage("Rendering flattened sheet...")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                export_engine.export_project(self.project, filepath, "flat_tiff", 600)
                QApplication.restoreOverrideCursor()
                QMessageBox.information(self, "Export Successful", f"Flattened TIFF exported to:\n{filepath}")
                self.statusBar().showMessage("Flattened TIFF exported successfully.", 4000)
            except Exception as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(self, "Export Failed", f"Failed to export flattened TIFF:\n{e}")
                self.statusBar().showMessage("Flattened TIFF export failed.", 4000)

    def export_individual_cards_dialog(self):
        if not self.validate_project_before_export():
            return
        output_dir = QFileDialog.getExistingDirectory(self, "Select Directory to Save Individual Card TIFFs")
        if output_dir:
            self.statusBar().showMessage("Rendering individual 600 PPI card TIFF files in background...")
            
            self.card_export_worker = ExportCardsWorker(self.project, output_dir, parent=self)
            self.card_export_worker.progress_updated.connect(
                lambda current, total, msg: self.statusBar().showMessage(f"[{current}/{total}] {msg}")
            )
            def on_finished(paths):
                if paths:
                    QMessageBox.information(
                        self, 
                        "Export Successful", 
                        f"Successfully exported {len(paths)} individual 600 PPI card TIFF files to:\n{output_dir}"
                    )
                    self.statusBar().showMessage(f"Exported {len(paths)} card TIFF files successfully.", 4000)
                else:
                    QMessageBox.warning(self, "No Cards Exported", "No card files were assigned to slots.")
            def on_failed(err_msg):
                QMessageBox.critical(self, "Export Failed", f"Failed to export individual cards:\n{err_msg}")
                self.statusBar().showMessage("Individual cards export failed.", 4000)

            self.card_export_worker.export_finished.connect(on_finished)
            self.card_export_worker.export_failed.connect(on_failed)
            self.card_export_worker.start()

    def batch_load_cards_files(self):
        filepaths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Card TIFF Files (Up to 9)",
            "",
            "TIFF Images (*.tiff *.tif)"
        )
        if filepaths:
            num_slots = len(self.project.card_slots)
            for i, fp in enumerate(filepaths[:num_slots]):
                self.load_card_into_slot(i, fp, block_render=True)
            self.render_canvas()
            if self.active_slot_index < 0:
                self.on_slot_selected(0)
            else:
                self.on_slot_selected(self.active_slot_index)
            self.statusBar().showMessage(f"Batch loaded {len(filepaths[:num_slots])} card TIFFs into slots.", 4000)

    def batch_load_cards_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Folder Containing Card TIFF Files")
        if dir_path:
            valid_exts = ('.tif', '.tiff')
            found_files = [
                os.path.join(dir_path, f) for f in sorted(os.listdir(dir_path))
                if f.lower().endswith(valid_exts)
            ]
            if not found_files:
                QMessageBox.warning(self, "No TIFF Files Found", f"No .tif or .tiff files were found in:\n{dir_path}")
                return
            num_slots = len(self.project.card_slots)
            for i, fp in enumerate(found_files[:num_slots]):
                self.load_card_into_slot(i, fp, block_render=True)
            self.render_canvas()
            if self.active_slot_index < 0:
                self.on_slot_selected(0)
            else:
                self.on_slot_selected(self.active_slot_index)
            self.statusBar().showMessage(f"Batch loaded {len(found_files[:num_slots])} card TIFFs from folder.", 4000)

    # Import Layout from .studio3 File Name Parsing
    def import_layout_from_studio3(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Layout from Silhouette .studio3 File", "", "Silhouette Studio Files (*.studio3)")
        if filepath:
            filename = os.path.basename(filepath)
            info = self.parse_studio3_filename(filename)
            
            if not info:
                QMessageBox.warning(
                    self, 
                    "Custom Template Detected", 
                    "Since .studio3 is a proprietary, closed binary format, we cannot parse its coordinates directly.\n\n"
                    "Please select or create a custom layout manually that matches your template coordinates."
                )
                return
                
            # Try to find a matching preset in layouts
            paper = info["paper"].lower()
            card = info["card"].lower()
            variant = info["variant"].lower()
            
            # Map standard SCM names to our layout IDs
            matched_id = None
            if paper == "a4" and card == "standard":
                if variant == "borderless":
                    matched_id = "a4_9_cards_borderless"
                else:
                    matched_id = "a4_8_cards_standard"
            elif paper == "letter" and card == "standard":
                if variant == "borderless":
                    matched_id = "letter_9_cards_borderless"
                else:
                    matched_id = "letter_8_cards_standard"
            
            # General fallback check: search by name
            if not matched_id:
                for lay in self.layouts:
                    lay_id = lay.id.lower()
                    if paper in lay_id and card in lay_id:
                        if ("borderless" in variant and "borderless" in lay_id) or ("borderless" not in variant and "borderless" not in lay_id):
                            matched_id = lay.id
                            break
                            
            if matched_id:
                self.mapping_panel.update_layouts_list(self.layouts, matched_id)
                self.on_layout_changed(matched_id)
                QMessageBox.information(
                    self, 
                    "Layout Loaded", 
                    f"Successfully loaded preset layout matching SCM template:\n{filename}"
                )
            else:
                QMessageBox.warning(
                    self, 
                    "Preset Match Not Found", 
                    f"Parsed template details:\nPaper: {paper}\nCard: {card}\nVariant: {variant}\n\n"
                    "No exact preset matches. Please create a custom layout manually."
                )

    def parse_studio3_filename(self, filename: str) -> Optional[dict]:
        if not filename.lower().endswith(".studio3"):
            return None
            
        name = filename[:-8] # Strip ".studio3"
        parts = name.split("-")
        if len(parts) < 3:
            return None
            
        paper = parts[0]
        card = parts[1]
        
        # Check version suffix, e.g. "v5"
        version_str = parts[-1]
        if version_str.startswith("v") and version_str[1:].isdigit():
            version = int(version_str[1:])
        else:
            return None
            
        # Variant is middle parts if any
        if len(parts) == 3:
            variant = "default"
        else:
            variant = "-".join(parts[2:-1])
            
        return {
            "paper": paper,
            "card": card,
            "variant": variant,
            "version": version
        }

    # Dithering GUI slots and helpers
    def sync_dither_ui_from_settings(self):
        preserve_names = self.project.export_settings.get("preserve_channel_names", "true") == "true"
        self.mapping_panel.cb_preserve_names.blockSignals(True)
        self.mapping_panel.cb_preserve_names.setChecked(preserve_names)
        self.mapping_panel.cb_preserve_names.blockSignals(False)

        binary_debug = self.project.export_settings.get("binary_debug", False)
        if isinstance(binary_debug, str):
            binary_debug = binary_debug.lower() == "true"
        self.mapping_panel.cb_binary_debug.blockSignals(True)
        self.mapping_panel.cb_binary_debug.setChecked(binary_debug)
        self.mapping_panel.cb_binary_debug.blockSignals(False)

        if self.active_slot_index < 0:
            self.mapping_panel.combo_dither_mode.setEnabled(False)
            self.mapping_panel.slider_dither_coverage.setEnabled(False)
            self.mapping_panel.cb_preserve_opaque.setEnabled(False)
            self.mapping_panel.cb_duplicate_emboss.setEnabled(False)
            self.mapping_panel.spin_dither_angle.setEnabled(False)
            self.mapping_panel.spin_dither_lpi.setEnabled(False)
            self.mapping_panel.combo_dither_dot_shape.setEnabled(False)
            
            self.mapping_panel.combo_dither_mode.blockSignals(True)
            self.mapping_panel.combo_dither_mode.setCurrentText("None")
            self.mapping_panel.combo_dither_mode.blockSignals(False)
            self.mapping_panel.halftone_container.hide()
            self.update_dither_coverage_readout()
            return
            
        slot = self.project.card_slots[self.active_slot_index]
        
        if not slot.filepath:
            self.mapping_panel.combo_dither_mode.setEnabled(False)
            self.mapping_panel.slider_dither_coverage.setEnabled(False)
            self.mapping_panel.cb_preserve_opaque.setEnabled(False)
            self.mapping_panel.cb_duplicate_emboss.setEnabled(False)
            self.mapping_panel.spin_dither_angle.setEnabled(False)
            self.mapping_panel.spin_dither_lpi.setEnabled(False)
            self.mapping_panel.combo_dither_dot_shape.setEnabled(False)
            
            self.mapping_panel.combo_dither_mode.blockSignals(True)
            self.mapping_panel.combo_dither_mode.setCurrentText("None")
            self.mapping_panel.combo_dither_mode.blockSignals(False)
            self.mapping_panel.halftone_container.hide()
            self.update_dither_coverage_readout()
            return
            
        self.mapping_panel.combo_dither_mode.setEnabled(True)
        self.mapping_panel.slider_dither_coverage.setEnabled(True)
        self.mapping_panel.cb_preserve_opaque.setEnabled(True)
        self.mapping_panel.cb_duplicate_emboss.setEnabled(True)
        self.mapping_panel.spin_dither_angle.setEnabled(True)
        self.mapping_panel.spin_dither_lpi.setEnabled(True)
        self.mapping_panel.combo_dither_dot_shape.setEnabled(True)
        
        dither_settings = slot.dither_settings
        
        dither_mode = dither_settings.get("dither_mode")
        if dither_mode is None:
            enabled = dither_settings.get("dither_enabled", "false") == "true"
            dither_mode = dither_settings.setdefault("dither_mode", dither_settings.get("dither_algo", "Ordered Bayer") if enabled else "None")
            
        coverage_str = dither_settings.get("dither_coverage")
        if coverage_str is None:
            strength = int(dither_settings.get("dither_strength", "15"))
            dither_coverage = dither_settings.setdefault("dither_coverage", str(100 - strength))
        else:
            dither_coverage = coverage_str
            
        dither_angle = dither_settings.setdefault("dither_angle", "45.0")
        dither_lpi = dither_settings.setdefault("dither_lpi", "45.0")
        dither_dot_shape = dither_settings.setdefault("dither_dot_shape", "Round")
        preserve_opaque = dither_settings.setdefault("dither_preserve_opaque", "true") == "true"
        duplicate_emboss = dither_settings.setdefault("dither_duplicate_emboss", "false") == "true"
        dither_texture_path = dither_settings.setdefault("dither_texture_path", "")
        
        self.mapping_panel.combo_dither_mode.blockSignals(True)
        self.mapping_panel.combo_dither_mode.setCurrentText(dither_mode)
        self.mapping_panel.combo_dither_mode.blockSignals(False)
        
        self.mapping_panel.on_mode_changed(dither_mode)
        
        if dither_texture_path:
            self.mapping_panel.lbl_texture_path.setText(os.path.basename(dither_texture_path))
            self.mapping_panel.lbl_texture_path.setToolTip(dither_texture_path)
        else:
            self.mapping_panel.lbl_texture_path.setText("No texture selected")
            self.mapping_panel.lbl_texture_path.setToolTip("")
            
        cov_val = int(float(dither_coverage))
        self.mapping_panel.slider_dither_coverage.blockSignals(True)
        self.mapping_panel.slider_dither_coverage.setValue(cov_val)
        self.mapping_panel.lbl_dither_coverage_val.setText(f"{cov_val}%")
        self.mapping_panel.slider_dither_coverage.blockSignals(False)
        
        self.mapping_panel.spin_dither_angle.blockSignals(True)
        self.mapping_panel.spin_dither_angle.setValue(float(dither_angle))
        self.mapping_panel.spin_dither_angle.blockSignals(False)
        
        self.mapping_panel.spin_dither_lpi.blockSignals(True)
        self.mapping_panel.spin_dither_lpi.setValue(float(dither_lpi))
        self.mapping_panel.spin_dither_lpi.blockSignals(False)
        
        self.mapping_panel.combo_dither_dot_shape.blockSignals(True)
        self.mapping_panel.combo_dither_dot_shape.setCurrentText(dither_dot_shape)
        self.mapping_panel.combo_dither_dot_shape.blockSignals(False)
        
        self.mapping_panel.cb_preserve_opaque.blockSignals(True)
        self.mapping_panel.cb_preserve_opaque.setChecked(preserve_opaque)
        self.mapping_panel.cb_preserve_opaque.blockSignals(False)
        
        self.mapping_panel.cb_duplicate_emboss.blockSignals(True)
        self.mapping_panel.cb_duplicate_emboss.setChecked(duplicate_emboss)
        self.mapping_panel.cb_duplicate_emboss.blockSignals(False)
        
        self.update_dither_coverage_readout()
        self.update_print_info_readout()

    def on_dither_mode_changed(self, mode: str):
        if self.active_slot_index < 0:
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.dither_settings["dither_mode"] = mode
        slot.dither_settings["dither_enabled"] = "true" if mode != "None" else "false"
        if mode != "None":
            slot.dither_settings["dither_algo"] = mode
        self.update_dither_coverage_readout()
        self.render_canvas()
        self.trigger_autosave()

    def on_dither_coverage_changed(self, val: int):
        if self.active_slot_index < 0:
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.dither_settings["dither_coverage"] = str(val)
        slot.dither_settings["dither_strength"] = str(100 - val)
        self.update_dither_coverage_readout()
        self.render_canvas()
        self.trigger_autosave()

    def on_dither_angle_changed(self, val: float):
        if self.active_slot_index < 0:
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.dither_settings["dither_angle"] = f"{val:.1f}"
        self.update_dither_coverage_readout()
        self.render_canvas()
        self.trigger_autosave()

    def on_dither_lpi_changed(self, val: float):
        if self.active_slot_index < 0:
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.dither_settings["dither_lpi"] = f"{val:.1f}"
        self.update_dither_coverage_readout()
        self.render_canvas()
        self.trigger_autosave()

    def on_dither_dot_shape_changed(self, shape: str):
        if self.active_slot_index < 0:
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.dither_settings["dither_dot_shape"] = shape
        self.update_dither_coverage_readout()
        self.render_canvas()
        self.trigger_autosave()

    def on_dither_texture_changed(self, filepath: str):
        if self.active_slot_index < 0:
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.dither_settings["dither_texture_path"] = filepath
        self.update_dither_coverage_readout()
        self.render_canvas()
        self.trigger_autosave()

    def on_dither_preserve_opaque_toggled(self, checked: bool):
        if self.active_slot_index < 0:
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.dither_settings["dither_preserve_opaque"] = "true" if checked else "false"
        self.update_dither_coverage_readout()
        self.render_canvas()
        self.trigger_autosave()

    def on_dither_duplicate_emboss_toggled(self, checked: bool):
        if self.active_slot_index < 0:
            return
        slot = self.project.card_slots[self.active_slot_index]
        slot.dither_settings["dither_duplicate_emboss"] = "true" if checked else "false"
        self.update_dither_coverage_readout()
        self.render_canvas()
        self.trigger_autosave()

    def on_binary_debug_toggled(self, checked: bool):
        self.project.export_settings["binary_debug"] = checked
        self.trigger_autosave()

    def on_printer_profile_changed(self, profile_name: str):
        self.project.export_settings["active_printer_profile"] = profile_name
        
        from core import print_validation
        profiles = print_validation.load_printer_profiles()
        p_data = profiles.get(profile_name, {"scale_x": 100.0, "scale_y": 100.0})
        
        self.project.export_settings["printer_compensation_x"] = str(p_data.get("scale_x", 100.0))
        self.project.export_settings["printer_compensation_y"] = str(p_data.get("scale_y", 100.0))
        
        self.update_print_info_readout()
        self.render_canvas()
        self.trigger_autosave()

    def on_calibrate_clicked(self):
        from gui.calibration_wizard import CalibrationWizard
        wiz = CalibrationWizard(self.project, self)
        if wiz.exec():
            new_name = wiz.txt_profile_name.text().strip()
            self.mapping_panel.reload_printer_profiles(new_name)
            self.on_printer_profile_changed(new_name)

    def on_show_measurements_toggled(self, checked: bool):
        self.render_canvas()

    def generate_print_calibration_sheet(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Calibration Sheet PDF", "", "PDF Files (*.pdf)")
        if filepath:
            try:
                from core import print_validation
                print_validation.generate_calibration_sheet(self.project, filepath, 300)
                QMessageBox.information(self, "Export Successful", f"Print Calibration Sheet saved to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to generate calibration sheet:\n{e}")

    def update_print_info_readout(self):
        layout = self.project.layout
        self.mapping_panel.lbl_info_card_size.setText(f"{layout.card_size.width_mm:.2f} × {layout.card_size.height_mm:.2f} mm")
        self.mapping_panel.lbl_info_bleed.setText(f"{layout.bleed_mm:.2f} mm")
        self.mapping_panel.lbl_info_ppi.setText(f"{self.ppi} PPI")
        
        active_profile = self.project.export_settings.get("active_printer_profile", "Default")
        from core import print_validation
        profiles = print_validation.load_printer_profiles()
        p_data = profiles.get(active_profile, {"scale_x": 100.0, "scale_y": 100.0})
        scale_x = p_data.get("scale_x", 100.0)
        scale_y = p_data.get("scale_y", 100.0)
        self.mapping_panel.lbl_info_compensation.setText(f"X: {scale_x:.2f}% | Y: {scale_y:.2f}%")
        
        if self.active_slot_index >= 0:
            slot = self.project.card_slots[self.active_slot_index]
            if slot.filepath and os.path.exists(slot.filepath):
                try:
                    channels = tiff_parser.parse_tiff_channels(slot.filepath)
                    h, w = channels[0].shape
                    file_ppi = tiff_parser.get_tiff_ppi(slot.filepath)
                    self.mapping_panel.lbl_info_pixels.setText(f"{w} × {h} px")
                    
                    actual_size = print_validation.calculate_physical_size(w, h, file_ppi)
                    self.mapping_panel.lbl_info_print_size.setText(
                        f"{actual_size.width_mm:.2f} × {actual_size.height_mm:.2f} mm\n"
                        f"({actual_size.width_inches:.2f} × {actual_size.height_inches:.2f} in)"
                    )
                    
                    expected_w = layout.card_size.width_mm + 2 * layout.bleed_mm
                    expected_h = layout.card_size.height_mm + 2 * layout.bleed_mm
                    expected_ratio = expected_w / expected_h
                    actual_ratio = actual_size.width_mm / actual_size.height_mm
                    ratio_match = "Match" if abs(expected_ratio - actual_ratio) <= 0.01 else "Mismatch"
                    self.mapping_panel.lbl_info_aspect_ratio.setText(f"{actual_ratio:.3f} ({ratio_match})")
                    
                    val_res = print_validation.validate_print_dimensions(self.project, self.active_slot_index)
                    if val_res.get("pass", True):
                        self.mapping_panel.lbl_info_calib_status.setText("✓ PASS")
                        self.mapping_panel.lbl_info_calib_status.setStyleSheet("color: #22c55e; font-weight: bold;")
                    else:
                        self.mapping_panel.lbl_info_calib_status.setText("⚠ WARNING")
                        self.mapping_panel.lbl_info_calib_status.setStyleSheet("color: #ef4444; font-weight: bold;")
                    return
                except Exception:
                    pass
                    
        self.mapping_panel.lbl_info_pixels.setText("-")
        self.mapping_panel.lbl_info_print_size.setText("-")
        self.mapping_panel.lbl_info_aspect_ratio.setText("-")
        self.mapping_panel.lbl_info_calib_status.setText("-")
        self.mapping_panel.lbl_info_calib_status.setStyleSheet("")

    def update_dither_coverage_readout(self):
        if self.active_slot_index < 0:
            self.mapping_panel.lbl_dither_coverage.setText("Coverage: 100.0%")
            return
            
        slot = self.project.card_slots[self.active_slot_index]
        if not slot.filepath or not os.path.exists(slot.filepath):
            self.mapping_panel.lbl_dither_coverage.setText("Coverage: 100.0%")
            return
            
        try:
            channels = tiff_parser.parse_tiff_channels(slot.filepath)
            white_ch = None
            for ch in channels:
                if slot.disabled_channels and ch.name in slot.disabled_channels:
                    continue
                mapped = slot.mappings.get(ch.name)
                if mapped == "White Ink":
                    white_ch = ch
                    break
                    
            if not white_ch:
                self.mapping_panel.lbl_dither_coverage.setText("Coverage: 100.0%")
                return
                
            raw_w = tiff_parser.load_channel_array(slot.filepath, white_ch)
            
            dither_settings = slot.dither_settings
            dither_mode = dither_settings.get("dither_mode")
            if dither_mode is None:
                enabled = dither_settings.get("dither_enabled", "false") == "true"
                dither_mode = dither_settings.get("dither_algo", "Ordered Bayer") if enabled else "None"
                
            is_duplicate_emboss = dither_settings.get("dither_duplicate_emboss") == "true"
            if dither_mode == "None" and not is_duplicate_emboss:
                self.mapping_panel.lbl_dither_coverage.setText("Coverage: 100.0%")
                return
                
            coverage_str = dither_settings.get("dither_coverage")
            if coverage_str is None:
                strength = int(dither_settings.get("dither_strength", "15"))
                dither_coverage = str(100 - strength)
            else:
                dither_coverage = coverage_str
                
            settings = {
                "dither_coverage": dither_coverage,
                "dither_angle": dither_settings.get("dither_angle", "45.0"),
                "dither_lpi": dither_settings.get("dither_lpi", "45.0"),
                "dither_dot_shape": dither_settings.get("dither_dot_shape", "Round"),
            }
            
            from core import dithering
            from core.tiff_parser import get_tiff_ppi
            ppi_val = get_tiff_ppi(slot.filepath)
            dithered_w = dithering.process_white_channel(raw_w.copy(), dither_mode, ppi_val, settings)
            
            # Compose stage
            if is_duplicate_emboss:
                emboss_ch = None
                for ch in channels:
                    if slot.disabled_channels and ch.name in slot.disabled_channels:
                        continue
                    mapped = slot.mappings.get(ch.name)
                    if mapped == "Emboss":
                        emboss_ch = ch
                        break
                if emboss_ch:
                    raw_emboss = tiff_parser.load_channel_array(slot.filepath, emboss_ch)
                    # Prepare settings for composition
                    comp_settings = {"dither_duplicate_emboss": "true"}
                    dithered_w = dithering.compose_white_channel(dithered_w, raw_emboss, comp_settings)
            
            cov = dithering.calculate_coverage(raw_w, dithered_w)
            self.mapping_panel.lbl_dither_coverage.setText(f"Coverage: {cov:.1f}%")
        except Exception as e:
            print(f"Error calculating coverage readout: {e}")
            self.mapping_panel.lbl_dither_coverage.setText("Coverage: 100.0%")

    # --- Session Persistence, Auto Recovery, and In-App Restart ---
    def closeEvent(self, event):
        """Save session automatically on normal close after checking unsaved project changes."""
        if not self.check_unsaved_changes():
            event.ignore()
            return
            
        try:
            self.save_session(self.SESSION_FILE)
            self.remove_exit_flag()
            self.project_manager.clear_autosave()
        except Exception as e:
            print(f"Error during clean close session save: {e}")
        event.accept()

    def serialize_session(self) -> dict:
        center = self.canvas_view.mapToScene(self.canvas_view.viewport().rect().center())
        return {
            "project_dict": self.project.model_dump(),
            "project_path": self.project_path,
            "active_slot_index": self.active_slot_index,
            "view_mode": self.view_mode,
            "zoom_level": self.canvas_view._zoom_level,
            "center_x": center.x(),
            "center_y": center.y(),
            "splitter_sizes": self.splitter.sizes(),
            "window_geometry": self.saveGeometry().toHex().data().decode("utf-8")
        }

    def deserialize_session(self, data: dict):
        try:
            self._preview_cache.clear()
            # 1. Restore Project model
            project_dict = data.get("project_dict")
            if project_dict:
                restored_project = Project(**project_dict)
                
                # Check if all files exist
                missing_files = []
                for slot in restored_project.card_slots:
                    if slot.filepath:
                        if not os.path.exists(slot.filepath):
                            missing_files.append(slot.filepath)
                
                if missing_files:
                    files_str = "\n".join(f"- {f}" for f in missing_files)
                    QMessageBox.warning(
                        self,
                        "Missing Files",
                        f"The following files from the saved session could not be found:\n\n{files_str}\n\n"
                        "The session will be restored without these files."
                    )
                    for slot in restored_project.card_slots:
                        if slot.filepath and not os.path.exists(slot.filepath):
                            slot.filepath = None
                            
                self.project = restored_project
            
            # 2. Restore other states
            self.project_path = data.get("project_path")
            self.active_slot_index = data.get("active_slot_index", -1)
            self.view_mode = data.get("view_mode", "Combined")
            
            # Sync UI elements
            self.view_mode_combo.setCurrentText(self.view_mode)
            self.mapping_panel.update_layouts_list(self.layouts, self.project.layout.id)
            self.mapping_panel.update_print_passes(self.project.print_passes, self.project.disabled_passes)
            self.sync_project_slots()
            self.render_canvas()
            
            # Restore active slot selection in UI
            if self.active_slot_index >= 0:
                self.on_slot_selected(self.active_slot_index)
            else:
                self.mapping_panel.show_no_card_selected()
                self.sync_dither_ui_from_settings()
                
            # Restore splitter sizes
            splitter_sizes = data.get("splitter_sizes")
            if splitter_sizes:
                self.splitter.setSizes(splitter_sizes)
                
            # Restore window geometry
            window_geometry = data.get("window_geometry")
            if window_geometry:
                from PySide6.QtCore import QByteArray
                self.restoreGeometry(QByteArray.fromHex(window_geometry.encode("utf-8")))
                
            # Restore Zoom & Pan
            zoom_level = data.get("zoom_level")
            center_x = data.get("center_x")
            center_y = data.get("center_y")
            if zoom_level is not None and center_x is not None and center_y is not None:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, lambda: self.restore_zoom_pan(zoom_level, center_x, center_y))
                
        except Exception as e:
            print(f"Error during session restore: {e}")
            QMessageBox.warning(self, "Session Restore Failed", f"Could not restore the saved session: {e}\n\nStarting with a clean workspace.")
            self.new_project()

    def restore_zoom_pan(self, zoom_level: float, center_x: float, center_y: float):
        try:
            self.canvas_view.resetTransform()
            self.canvas_view._zoom_level = zoom_level
            self.canvas_view.scale(zoom_level, zoom_level)
            self.canvas_view.centerOn(QPointF(center_x, center_y))
        except Exception as e:
            print(f"Error restoring zoom/pan: {e}")

    def create_exit_flag(self):
        try:
            with open(self.EXIT_FLAG_FILE, "w") as f:
                f.write("running")
        except Exception as e:
            print(f"Error creating exit flag: {e}")

    def remove_exit_flag(self):
        try:
            if os.path.exists(self.EXIT_FLAG_FILE):
                os.remove(self.EXIT_FLAG_FILE)
        except Exception as e:
            print(f"Error removing exit flag: {e}")

    def save_session(self, filepath: str):
        try:
            import json
            session_data = self.serialize_session()
            with open(filepath, "w") as f:
                json.dump(session_data, f, indent=4)
        except Exception as e:
            print(f"Error saving session to {filepath}: {e}")

    def load_session(self, filepath: str):
        try:
            import json
            if not os.path.exists(filepath):
                return
            with open(filepath, "r") as f:
                session_data = json.load(f)
            self.deserialize_session(session_data)
        except Exception as e:
            print(f"Error loading session from {filepath}: {e}")
            QMessageBox.warning(self, "Session Load Error", f"Could not load session from {filepath}:\n{e}")

    def auto_save_session(self):
        """Auto-save session periodically to autosave.json."""
        self.save_session(self.AUTOSAVE_FILE)

    def trigger_autosave(self):
        """Trigger an immediate autosave of session and project state, and set modified flag."""
        self.project_modified = True
        self.auto_save_session()
        self.project_manager.save_autosave(self.project)

    def manual_save_session(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Session", "", "Session Files (*.json)")
        if filepath:
            self.save_session(filepath)
            self.statusBar().showMessage(f"Session saved to {filepath}", 3000)

    def manual_load_session(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Session", "", "Session Files (*.json)")
        if filepath:
            self.load_session(filepath)
            self.statusBar().showMessage(f"Session loaded from {filepath}", 3000)

    def clear_saved_session(self):
        try:
            if os.path.exists(self.SESSION_FILE):
                os.remove(self.SESSION_FILE)
            if os.path.exists(self.AUTOSAVE_FILE):
                os.remove(self.AUTOSAVE_FILE)
            self.remove_exit_flag()
            self.new_project()
            self.statusBar().showMessage("Saved session cleared. Starting clean workspace.", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Clear Session Error", f"Could not clear saved sessions: {e}")

    def clear_session_file(self, filepath: str):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Error clearing session file {filepath}: {e}")

    def restart_application(self):
        try:
            # Save current session to session.json before exit
            self.save_session(self.SESSION_FILE)
            self.remove_exit_flag()
            
            # Restart using the current executable
            import sys
            import subprocess
            subprocess.Popen([sys.executable, sys.argv[0]] + sys.argv[1:])
            QApplication.quit()
        except Exception as e:
            QMessageBox.critical(self, "Restart Failed", f"Could not restart application: {e}")

    def check_session_restore(self):
        is_dirty_shutdown = os.path.exists(self.EXIT_FLAG_FILE)
        
        # Write active/dirty exit flag for the current session
        self.create_exit_flag()
        
        if is_dirty_shutdown and os.path.exists(self.AUTOSAVE_FILE):
            # Prompt the user for crash recovery
            reply = QMessageBox.question(
                self,
                "Auto Recovery",
                "The previous session was not closed properly.\nWould you like to restore it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.load_session(self.AUTOSAVE_FILE)
            else:
                self.clear_session_file(self.AUTOSAVE_FILE)
                if os.path.exists(self.SESSION_FILE):
                    self.load_session(self.SESSION_FILE)
        else:
            if os.path.exists(self.SESSION_FILE):
                self.load_session(self.SESSION_FILE)
