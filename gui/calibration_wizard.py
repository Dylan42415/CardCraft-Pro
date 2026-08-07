import os
import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QWidget, QDoubleSpinBox, QLineEdit, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from core import print_validation

class CalibrationWizard(QDialog):
    profile_saved = Signal(str, dict)  # Emitted when profile is successfully saved (name, data)

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Print Calibration Wizard")
        self.resize(460, 360)
        self.setModal(True)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header Label
        self.header_label = QLabel("Step 1: Generate & Print Calibration Sheet")
        self.header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e1e2d;")
        self.main_layout.addWidget(self.header_label)
        
        # Stacked widget for step navigation
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        
        # Initialize steps
        self.step1_widget = self.init_step1()
        self.step2_widget = self.init_step2()
        self.step3_widget = self.init_step3()
        
        self.stacked_widget.addWidget(self.step1_widget)
        self.stacked_widget.addWidget(self.step2_widget)
        self.stacked_widget.addWidget(self.step3_widget)
        
        # Bottom Navigation buttons
        self.nav_layout = QHBoxLayout()
        self.btn_back = QPushButton("< Back")
        self.btn_back.clicked.connect(self.go_back)
        self.btn_back.setEnabled(False)
        self.nav_layout.addWidget(self.btn_back)
        
        self.nav_layout.addStretch()
        
        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self.go_next)
        self.nav_layout.addWidget(self.btn_next)
        
        self.main_layout.addLayout(self.nav_layout)
        
        # Calibration output values
        self.calculated_scale_x = 100.0
        self.calculated_scale_y = 100.0

    def init_step1(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        desc = QLabel(
            "To calibrate your printer, you must first print a test calibration sheet "
            "at exactly 100% scale (no scaling, no 'fit to page').\n\n"
            "This sheet contains measurements, crop marks, and a reference 10 mm calibration square."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #4a4a5a; line-height: 1.4;")
        layout.addWidget(desc)
        
        layout.addStretch()
        
        self.btn_print = QPushButton("Generate & Save Calibration PDF...")
        self.btn_print.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; padding: 10px; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        self.btn_print.clicked.connect(self.generate_sheet)
        layout.addWidget(self.btn_print)
        
        layout.addStretch()
        return widget

    def init_step2(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        desc = QLabel(
            "Once printed, measure the 10x10 mm calibration square in the bottom-left "
            "using a physical ruler or a digital caliper.\n\n"
            "Enter the actual measured sizes below:"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #4a4a5a;")
        layout.addWidget(desc)
        
        # Input Form
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)
        
        w_layout = QHBoxLayout()
        w_lbl = QLabel("Measured Width (mm):")
        w_lbl.setMinimumWidth(150)
        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(5.0, 15.0)
        self.spin_width.setValue(10.0)
        self.spin_width.setDecimals(2)
        self.spin_width.setSuffix(" mm")
        w_layout.addWidget(w_lbl)
        w_layout.addWidget(self.spin_width)
        form_layout.addLayout(w_layout)
        
        h_layout = QHBoxLayout()
        h_lbl = QLabel("Measured Height (mm):")
        h_lbl.setMinimumWidth(150)
        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(5.0, 15.0)
        self.spin_height.setValue(10.0)
        self.spin_height.setDecimals(2)
        self.spin_height.setSuffix(" mm")
        h_layout.addWidget(h_lbl)
        h_layout.addWidget(self.spin_height)
        form_layout.addLayout(h_layout)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        return widget

    def init_step3(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        
        self.lbl_results = QLabel("")
        self.lbl_results.setStyleSheet("color: #2d2d39; line-height: 1.4;")
        self.lbl_results.setWordWrap(True)
        layout.addWidget(self.lbl_results)
        
        # Profile Details
        name_layout = QHBoxLayout()
        name_lbl = QLabel("Profile Name:")
        name_lbl.setMinimumWidth(100)
        self.txt_profile_name = QLineEdit()
        self.txt_profile_name.setPlaceholderText("e.g. Epson L1800 Matte")
        name_layout.addWidget(name_lbl)
        name_layout.addWidget(self.txt_profile_name)
        layout.addWidget(name_layout)
        
        notes_layout = QHBoxLayout()
        notes_lbl = QLabel("Notes:")
        notes_lbl.setMinimumWidth(100)
        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("Optional details (paper type, profile revision, etc.)")
        notes_layout.addWidget(notes_lbl)
        notes_layout.addWidget(self.txt_notes)
        layout.addWidget(notes_layout)
        
        layout.addStretch()
        return widget

    def generate_sheet(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Calibration Sheet PDF", "", "PDF Files (*.pdf)")
        if filepath:
            try:
                print_validation.generate_calibration_sheet(self.project, filepath, 300)
                QMessageBox.information(
                    self, 
                    "Calibration Sheet Saved", 
                    f"Successfully generated calibration sheet PDF at:\n{filepath}\n\n"
                    "Please print this file at 100% scale (no scaling) and click Next."
                )
            except Exception as e:
                QMessageBox.critical(self, "Generation Failed", f"Failed to render calibration sheet:\n{e}")

    def calculate_scale(self):
        measured_w = self.spin_width.value()
        measured_h = self.spin_height.value()
        
        if measured_w <= 0 or measured_h <= 0:
            self.calculated_scale_x = 100.0
            self.calculated_scale_y = 100.0
        else:
            # Scale ratio = Expected (10mm) / Measured (mm) * 100
            self.calculated_scale_x = (10.0 / measured_w) * 100.0
            self.calculated_scale_y = (10.0 / measured_h) * 100.0
            
        res_text = (
            f"<b>Calculated Compensation Factors:</b><br>"
            f"• Printer X Compensation: <b>{self.calculated_scale_x:.2f}%</b><br>"
            f"• Printer Y Compensation: <b>{self.calculated_scale_y:.2f}%</b><br><br>"
            f"<i>These scale adjustments will compensate for physical print inaccuracies "
            f"during final layout placement, keeping original artwork pixels untouched.</i>"
        )
        self.lbl_results.setText(res_text)

    def go_back(self):
        curr = self.stacked_widget.currentIndex()
        if curr > 0:
            self.stacked_widget.setCurrentIndex(curr - 1)
            self.update_buttons()

    def go_next(self):
        curr = self.stacked_widget.currentIndex()
        if curr == 0:
            self.stacked_widget.setCurrentIndex(1)
            self.update_buttons()
        elif curr == 1:
            self.calculate_scale()
            self.stacked_widget.setCurrentIndex(2)
            self.update_buttons()
        elif curr == 2:
            self.save_profile()

    def save_profile(self):
        name = self.txt_profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a profile name before saving.")
            return
            
        profiles = print_validation.load_printer_profiles()
        
        profile_data = {
            "scale_x": round(self.calculated_scale_x, 4),
            "scale_y": round(self.calculated_scale_y, 4),
            "date_calibrated": datetime.date.today().isoformat(),
            "notes": self.txt_notes.text().strip()
        }
        
        profiles[name] = profile_data
        print_validation.save_printer_profiles(profiles)
        
        self.profile_saved.emit(name, profile_data)
        QMessageBox.information(self, "Calibration Saved", f"Successfully saved printer calibration profile: '{name}'")
        self.accept()

    def update_buttons(self):
        curr = self.stacked_widget.currentIndex()
        self.btn_back.setEnabled(curr > 0)
        
        if curr == 0:
            self.header_label.setText("Step 1: Generate & Print Calibration Sheet")
            self.btn_next.setText("Next >")
        elif curr == 1:
            self.header_label.setText("Step 2: Input Physical Measurements")
            self.btn_next.setText("Calculate Scale >")
        elif curr == 2:
            self.header_label.setText("Step 3: Save Calibration Profile")
            self.btn_next.setText("Save Profile & Finish")
