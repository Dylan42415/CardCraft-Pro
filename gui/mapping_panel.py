import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QGroupBox, QPushButton, 
                             QListWidget, QAbstractItemView, QListWidgetItem, QInputDialog, QFileDialog, QScrollArea, QFrame, QCheckBox, QSlider)
from typing import List, Dict, Any, Optional

class NonScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        # Ignore mouse wheel events to prevent scrolling the panel from changing drop-down settings
        event.ignore()

class MappingPanel(QWidget):
    # Signals to notify parent window of changes
    layout_changed = Signal(str)          # Layout ID
    print_passes_reordered = Signal(list) # List of print pass names in new order
    mapping_updated = Signal(str, str)     # Source channel, Target print pass
    import_single_tiff = Signal()
    import_folder = Signal()
    save_profile_clicked = Signal()
    load_profile_clicked = Signal()
    channel_enable_toggled = Signal(str, bool) # Source channel name, Enabled status (True=enabled)
    print_pass_toggled = Signal(str, bool)     # Pass name, Enabled status (True=enabled)
    preserve_names_toggled = Signal(bool)      # True = preserve original names on export
    dither_mode_changed = Signal(str)
    dither_coverage_changed = Signal(int)
    dither_angle_changed = Signal(float)
    dither_lpi_changed = Signal(float)
    dither_dot_shape_changed = Signal(str)
    dither_preserve_opaque_toggled = Signal(bool)
    dither_texture_changed = Signal(str)
    dither_duplicate_emboss_toggled = Signal(bool)
    binary_debug_toggled = Signal(bool)
    printer_profile_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(15)

        # Make panel scrollable in case there are many channels/passes
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(15)
        
        self.scroll_area.setWidget(self.container)
        self.layout.addWidget(self.scroll_area)

        # 1. Layout Selection Group
        self.init_layout_group()

        # 2. Layer Mapping Group (Populated dynamically)
        self.init_mapping_group()

        # 3. Print Pass Ordering Group
        self.init_ordering_group()
        
        # 4. Export Settings Group
        self.init_export_settings_group()
        
        # 5. Print Info & Calibration Group
        self.init_print_info_group()

        # 6. Batch Operations Group
        self.init_batch_group()

    def init_layout_group(self):
        group = QGroupBox("Print Layout")
        layout = QVBoxLayout(group)
        
        layout.addWidget(QLabel("Select Sheet Layout:"))
        self.layout_combo = NonScrollComboBox()
        self.layout_combo.currentIndexChanged.connect(self.on_layout_combo_changed)
        layout.addWidget(self.layout_combo)
        
        self.container_layout.addWidget(group)

    def on_layout_combo_changed(self, index):
        layout_id = self.layout_combo.currentData()
        if layout_id:
            self.layout_changed.emit(layout_id)

    def init_mapping_group(self):
        self.mapping_group = QGroupBox("TIFF Layer Mapping")
        self.mapping_layout = QVBoxLayout(self.mapping_group)
        
        self.card_info_label = QLabel("No card selected. Click a slot in the canvas to select a card.")
        self.card_info_label.setWordWrap(True)
        self.mapping_layout.addWidget(self.card_info_label)
        
        self.mapping_widgets_layout = QVBoxLayout()
        self.mapping_layout.addLayout(self.mapping_widgets_layout)

        # Profile actions
        btn_layout = QHBoxLayout()
        self.btn_load_profile = QPushButton("Load Profile")
        self.btn_load_profile.clicked.connect(self.load_profile_clicked.emit)
        self.btn_save_profile = QPushButton("Save Profile")
        self.btn_save_profile.clicked.connect(self.save_profile_clicked.emit)
        btn_layout.addWidget(self.btn_load_profile)
        btn_layout.addWidget(self.btn_save_profile)
        self.mapping_layout.addLayout(btn_layout)
        
        self.container_layout.addWidget(self.mapping_group)

    def init_ordering_group(self):
        group = QGroupBox("Print Pass Order")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        layout.addWidget(QLabel("Drag and drop to reorder print sequence:"))
        
        # Drag and drop list widget
        self.pass_list = QListWidget()
        self.pass_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.pass_list.model().rowsMoved.connect(self.on_rows_moved)
        self.pass_list.itemChanged.connect(self.on_pass_item_changed)
        layout.addWidget(self.pass_list)
        
        # Add print pass button
        self.add_pass_btn = QPushButton("+ Add Print Pass")
        self.add_pass_btn.clicked.connect(self.add_custom_print_pass)
        layout.addWidget(self.add_pass_btn)
        
        self.container_layout.addWidget(group)

    def init_export_settings_group(self):
        group = QGroupBox("Export Settings")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        self.cb_preserve_names = QCheckBox("Preserve original channel names")
        self.cb_preserve_names.setChecked(True)
        self.cb_preserve_names.toggled.connect(self.on_preserve_names_toggled)
        layout.addWidget(self.cb_preserve_names)
        
        self.cb_binary_debug = QCheckBox("Binary Spot Channel Debug")
        self.cb_binary_debug.setChecked(False)
        self.cb_binary_debug.setToolTip(
            "Analyzes every exported spot channel (White Ink, Emboss, etc.) for binary compliance. "
            "Shows a detailed validation report upon export completion."
        )
        self.cb_binary_debug.toggled.connect(self.binary_debug_toggled.emit)
        layout.addWidget(self.cb_binary_debug)
        
        # White Ink Processing GroupBox
        dither_group = QGroupBox("White Ink Processing")
        dither_layout = QVBoxLayout(dither_group)
        dither_layout.setSpacing(8)
        
        dither_layout.addWidget(QLabel("Processing Mode:"))
        self.combo_dither_mode = NonScrollComboBox()
        self.combo_dither_mode.addItems([
            "None", "Ordered Bayer", "Floyd–Steinberg", "Atkinson", 
            "AM Halftone", "FM Blue Noise", "Hybrid Screen", "Custom Texture"
        ])
        self.combo_dither_mode.currentTextChanged.connect(self.on_mode_changed)
        dither_layout.addWidget(self.combo_dither_mode)
        
        # Custom Texture file chooser layout
        self.texture_container = QWidget()
        tex_layout = QHBoxLayout(self.texture_container)
        tex_layout.setContentsMargins(0, 0, 0, 0)
        tex_layout.setSpacing(6)
        self.lbl_texture_path = QLabel("No texture selected")
        self.lbl_texture_path.setStyleSheet("font-size: 11px; color: #94a3b8;")
        btn_browse_tex = QPushButton("Browse...")
        btn_browse_tex.clicked.connect(self.on_browse_texture)
        tex_layout.addWidget(self.lbl_texture_path)
        tex_layout.addWidget(btn_browse_tex)
        dither_layout.addWidget(self.texture_container)
        self.texture_container.hide()
        
        # Coverage Slider
        coverage_header = QHBoxLayout()
        coverage_header.addWidget(QLabel("Coverage:"))
        self.lbl_dither_coverage_val = QLabel("100%")
        coverage_header.addStretch()
        coverage_header.addWidget(self.lbl_dither_coverage_val)
        dither_layout.addLayout(coverage_header)
        
        self.slider_dither_coverage = QSlider(Qt.Orientation.Horizontal)
        self.slider_dither_coverage.setRange(0, 100)
        self.slider_dither_coverage.setValue(100)
        self.slider_dither_coverage.valueChanged.connect(self.on_slider_coverage_changed)
        dither_layout.addWidget(self.slider_dither_coverage)
        
        # Preserve fully opaque checkbox (for dithering algorithms)
        self.cb_preserve_opaque = QCheckBox("Preserve Fully Opaque Areas")
        self.cb_preserve_opaque.setChecked(True)
        self.cb_preserve_opaque.toggled.connect(self.dither_preserve_opaque_toggled.emit)
        dither_layout.addWidget(self.cb_preserve_opaque)
        
        # Duplicate Emboss Into White checkbox
        self.cb_duplicate_emboss = QCheckBox("Duplicate Emboss Into White")
        self.cb_duplicate_emboss.setChecked(False)
        self.cb_duplicate_emboss.setToolTip(
            "Copies the Emboss mask into the White Ink channel after White processing. "
            "Emboss regions remain solid while the original White artwork retains the selected dithering or halftone pattern."
        )
        self.cb_duplicate_emboss.toggled.connect(self.dither_duplicate_emboss_toggled.emit)
        dither_layout.addWidget(self.cb_duplicate_emboss)
        
        self.lbl_duplicate_emboss_desc = QLabel(
            "Useful for UV printing workflows that benefit from a solid white foundation beneath embossed regions."
        )
        self.lbl_duplicate_emboss_desc.setWordWrap(True)
        self.lbl_duplicate_emboss_desc.setStyleSheet("font-size: 10px; color: #94a3b8; margin-left: 20px;")
        dither_layout.addWidget(self.lbl_duplicate_emboss_desc)
        
        # Halftone parameters sub-container
        self.halftone_container = QWidget()
        ht_layout = QVBoxLayout(self.halftone_container)
        ht_layout.setContentsMargins(0, 0, 0, 0)
        ht_layout.setSpacing(6)
        
        # Angle
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("Screen Angle:"))
        from PySide6.QtWidgets import QDoubleSpinBox
        self.spin_dither_angle = QDoubleSpinBox()
        self.spin_dither_angle.setRange(0.0, 360.0)
        self.spin_dither_angle.setValue(45.0)
        self.spin_dither_angle.setSuffix("°")
        self.spin_dither_angle.valueChanged.connect(self.dither_angle_changed.emit)
        angle_layout.addStretch()
        angle_layout.addWidget(self.spin_dither_angle)
        ht_layout.addLayout(angle_layout)
        
        # LPI
        lpi_layout = QHBoxLayout()
        lpi_layout.addWidget(QLabel("Screen Frequency:"))
        self.spin_dither_lpi = QDoubleSpinBox()
        self.spin_dither_lpi.setRange(1.0, 300.0)
        self.spin_dither_lpi.setValue(45.0)
        self.spin_dither_lpi.setSuffix(" LPI")
        self.spin_dither_lpi.valueChanged.connect(self.dither_lpi_changed.emit)
        lpi_layout.addStretch()
        lpi_layout.addWidget(self.spin_dither_lpi)
        ht_layout.addLayout(lpi_layout)
        
        # Dot Shape
        shape_layout = QHBoxLayout()
        shape_layout.addWidget(QLabel("Dot Shape:"))
        self.combo_dither_dot_shape = NonScrollComboBox()
        self.combo_dither_dot_shape.addItems(["Round", "Elliptical", "Diamond", "Square", "Line"])
        self.combo_dither_dot_shape.currentTextChanged.connect(self.dither_dot_shape_changed.emit)
        shape_layout.addStretch()
        shape_layout.addWidget(self.combo_dither_dot_shape)
        ht_layout.addLayout(shape_layout)
        
        dither_layout.addWidget(self.halftone_container)
        self.halftone_container.hide() # Hidden by default
        
        # Coverage readout
        self.lbl_dither_coverage = QLabel("Coverage: 100.0%")
        self.lbl_dither_coverage.setStyleSheet("font-weight: bold; color: #a5b4fc;")
        dither_layout.addWidget(self.lbl_dither_coverage)
        
        # Warning label
        self.lbl_dither_warning = QLabel("⚠️ Preview is an approximation. Exported TIFF is authoritative.")
        self.lbl_dither_warning.setWordWrap(True)
        self.lbl_dither_warning.setStyleSheet("font-size: 10px; color: #fbbf24;")
        dither_layout.addWidget(self.lbl_dither_warning)
        
        layout.addWidget(dither_group)
        self.container_layout.addWidget(group)
        
    def on_mode_changed(self, mode: str):
        # Show halftone options container if AM Halftone or Hybrid Screen is selected
        self.halftone_container.setVisible(mode in ("AM Halftone", "Hybrid Screen"))
        # Show custom texture file chooser only for Custom Texture mode
        self.texture_container.setVisible(mode == "Custom Texture")
        # Opaque preservation checkbox only shown for legacy dithering algorithms
        self.cb_preserve_opaque.setVisible(mode in ("Ordered Bayer", "Floyd–Steinberg", "Atkinson"))
        self.dither_mode_changed.emit(mode)
        
    def on_browse_texture(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Custom Texture",
            "",
            "Images (*.png *.jpg *.jpeg *.tiff *.tif *.bmp);;All Files (*)"
        )
        if filepath:
            self.lbl_texture_path.setText(os.path.basename(filepath))
            self.lbl_texture_path.setToolTip(filepath)
            self.dither_texture_changed.emit(filepath)
        
    def on_slider_coverage_changed(self, val):
        self.lbl_dither_coverage_val.setText(f"{val}%")
        self.dither_coverage_changed.emit(val)
        
    def on_preserve_names_toggled(self, checked):
        self.preserve_names_toggled.emit(checked)

    def init_batch_group(self):
        group = QGroupBox("Batch Operations")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        self.btn_import_tiff = QPushButton("Import TIFF File(s)")
        self.btn_import_tiff.setObjectName("successButton")
        self.btn_import_tiff.clicked.connect(self.import_single_tiff.emit)
        layout.addWidget(self.btn_import_tiff)
        
        self.btn_import_folder = QPushButton("Import Folder")
        self.btn_import_folder.clicked.connect(self.import_folder.emit)
        layout.addWidget(self.btn_import_folder)
        
        self.container_layout.addWidget(group)

    # Setters and UI modifiers
    def update_layouts_list(self, layouts: List[Any], current_id: str):
        """Populates the layout dropdown list."""
        self.layout_combo.blockSignals(True)
        self.layout_combo.clear()
        for lay in layouts:
            self.layout_combo.addItem(lay.name, lay.id)
            if lay.id == current_id:
                self.layout_combo.setCurrentText(lay.name)
        self.layout_combo.blockSignals(False)

    def update_print_passes(self, print_passes: List[str], disabled_passes: List[str]):
        """Populates the print pass list widget with user checkbox states and drag-drop options."""
        self.pass_list.blockSignals(True)
        self.pass_list.clear()
        for p in print_passes:
            item = QListWidgetItem(p)
            # Add user checkable flag
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            is_enabled = p not in disabled_passes
            item.setCheckState(Qt.CheckState.Checked if is_enabled else Qt.CheckState.Unchecked)
            self.pass_list.addItem(item)
        self.pass_list.blockSignals(False)

    def update_layer_mappings(self, card_name: str, detected_channels: List[Any], current_mappings: Dict[str, str], disabled_channels: List[str], print_passes: List[str]):
        """
        Populates the mappings dropdowns dynamically for the selected card.
        """
        # Clear existing dynamic widgets
        while self.mapping_widgets_layout.count():
            item = self.mapping_widgets_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
 
        self.card_info_label.setText(f"Active Card: {card_name}")
 
        # Filter and group channels for clean display
        ui_channels = []
        has_rgb = False
        seen_spot_names = set()
        
        # Determine if the file is PSD-structured (contains document-level spot channels)
        is_psd_structured = any(ch.page_index == -1 for ch in detected_channels)
        
        for ch in detected_channels:
            name_lower = ch.name.lower()
            is_rgb_component = "red" in name_lower or "green" in name_lower or "blue" in name_lower or (ch.page_index == 0 and ch.channel_in_page in (0, 1, 2))
            
            if is_rgb_component:
                has_rgb = True
                continue
                
            # Filter: only expose actual spot channels
            if is_psd_structured:
                if ch.page_index != -1:
                    continue
            else:
                if ch.page_index <= 0:
                    continue
                if "alpha" in name_lower or "transparency" in name_lower:
                    continue
                
            if name_lower in seen_spot_names:
                continue
            seen_spot_names.add(name_lower)
            ui_channels.append(ch)
            
        class VirtualChannel:
            def __init__(self, name, shape, dtype):
                self.name = name
                self.shape = shape
                self.dtype = dtype
                
        display_channels = []
        if has_rgb:
            h_w = detected_channels[0].shape if detected_channels else (0, 0)
            display_channels.append(VirtualChannel("Base Artwork (RGB)", h_w, "uint8"))
            
        display_channels.extend(ui_channels)
 
        for ch in display_channels:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)
            
            # Add enable/disable checkbox for this channel
            cb = QCheckBox()
            is_enabled = ch.name not in disabled_channels
            cb.setChecked(is_enabled)
            cb.toggled.connect(lambda checked, src_ch=ch.name: self.channel_enable_toggled.emit(src_ch, checked))
            row_layout.addWidget(cb)
            
            lbl = QLabel(ch.name)
            lbl.setToolTip(f"Shape: {ch.shape} | Type: {ch.dtype}")
            # Dim the label if disabled
            if not is_enabled:
                lbl.setStyleSheet("color: #888888; text-decoration: line-through;")
            row_layout.addWidget(lbl, 1)
            
            combo = NonScrollComboBox()
            combo.addItem("[Unmapped / Ignore]", "")
            for p in print_passes:
                combo.addItem(p, p)
                
            # Select current mapping if exists
            mapped_val = current_mappings.get(ch.name, "")
            if ch.name == "Base Artwork (RGB)" and not mapped_val:
                mapped_val = "Base Artwork"
                
            idx = combo.findData(mapped_val)
            if idx != -1:
                combo.setCurrentIndex(idx)
                
            # Connect change event
            combo.currentTextChanged.connect(lambda val, src_ch=ch.name: self.mapping_updated.emit(src_ch, val))
            combo.setEnabled(is_enabled) # Disable dropdown if channel is unchecked
            
            row_layout.addWidget(combo, 1)
            self.mapping_widgets_layout.addWidget(row_widget)
            row_widget.show()

    def show_no_card_selected(self):
        """Resets the layer mapping panel when no card is selected."""
        while self.mapping_widgets_layout.count():
            item = self.mapping_widgets_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.card_info_label.setText("No card selected. Click a slot in the canvas to select a card.")

    # Event handlers
    def on_rows_moved(self, parent, start, end, destination, row):
        """Emits the new list order when print passes are dragged and dropped."""
        passes = []
        for i in range(self.pass_list.count()):
            passes.append(self.pass_list.item(i).text())
        self.print_passes_reordered.emit(passes)
        
    def on_pass_item_changed(self, item):
        """Triggered when print pass checkboxes are toggled."""
        pass_name = item.text()
        is_enabled = item.checkState() == Qt.CheckState.Checked
        self.print_pass_toggled.emit(pass_name, is_enabled)

    def add_custom_print_pass(self):
        """Shows input dialog to add a custom print pass."""
        text, ok = QInputDialog.getText(self, "Add Print Pass", "Enter new print pass/spot channel name:")
        if ok and text.strip():
            pass_name = text.strip()
            # Append item to list
            item = QListWidgetItem(pass_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
            self.pass_list.addItem(item)
            
            # Emit full reordered list
            self.on_rows_moved(None, 0, 0, None, 0)

    def init_print_info_group(self):
        group = QGroupBox("Print Information & Calibration")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        # Profile selector
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Printer Profile:"))
        self.combo_printer_profile = NonScrollComboBox()
        self.combo_printer_profile.currentTextChanged.connect(self.printer_profile_changed.emit)
        profile_layout.addWidget(self.combo_printer_profile)
        
        self.btn_calibrate = QPushButton("Calibrate...")
        self.btn_calibrate.setStyleSheet("padding: 4px 8px; font-weight: bold;")
        profile_layout.addWidget(self.btn_calibrate)
        layout.addLayout(profile_layout)
        
        # Grid layout for sizing stats
        from PySide6.QtWidgets import QGridLayout
        info_layout = QGridLayout()
        info_layout.setSpacing(6)
        
        self.lbl_info_card_size = QLabel("-")
        self.lbl_info_bleed = QLabel("-")
        self.lbl_info_ppi = QLabel("-")
        self.lbl_info_pixels = QLabel("-")
        self.lbl_info_print_size = QLabel("-")
        self.lbl_info_aspect_ratio = QLabel("-")
        self.lbl_info_compensation = QLabel("-")
        self.lbl_info_calib_status = QLabel("-")
        
        info_layout.addWidget(QLabel("Card size:"), 0, 0)
        info_layout.addWidget(self.lbl_info_card_size, 0, 1)
        
        info_layout.addWidget(QLabel("Bleed:"), 1, 0)
        info_layout.addWidget(self.lbl_info_bleed, 1, 1)
        
        info_layout.addWidget(QLabel("Resolution:"), 2, 0)
        info_layout.addWidget(self.lbl_info_ppi, 2, 1)
        
        info_layout.addWidget(QLabel("Pixels:"), 3, 0)
        info_layout.addWidget(self.lbl_info_pixels, 3, 1)
        
        info_layout.addWidget(QLabel("Print Size:"), 4, 0)
        info_layout.addWidget(self.lbl_info_print_size, 4, 1)
        
        info_layout.addWidget(QLabel("Aspect Ratio:"), 5, 0)
        info_layout.addWidget(self.lbl_info_aspect_ratio, 5, 1)
        
        info_layout.addWidget(QLabel("Compensation:"), 6, 0)
        info_layout.addWidget(self.lbl_info_compensation, 6, 1)
        
        info_layout.addWidget(QLabel("Calib Status:"), 7, 0)
        info_layout.addWidget(self.lbl_info_calib_status, 7, 1)
        
        layout.addLayout(info_layout)
        self.container_layout.addWidget(group)
        
        # Initial load of profiles
        self.reload_printer_profiles()

    def reload_printer_profiles(self, selected_profile: str = "Default"):
        from core import print_validation
        profiles = print_validation.load_printer_profiles()
        self.combo_printer_profile.blockSignals(True)
        self.combo_printer_profile.clear()
        for name in sorted(profiles.keys()):
            self.combo_printer_profile.addItem(name)
        
        if selected_profile in profiles:
            self.combo_printer_profile.setCurrentText(selected_profile)
        else:
            self.combo_printer_profile.setCurrentText("Default")
        self.combo_printer_profile.blockSignals(False)

