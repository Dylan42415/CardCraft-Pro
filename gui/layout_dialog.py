from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox, 
                             QSpinBox, QComboBox, QPushButton, QFormLayout, QDialogButtonBox)
from core.models import Layout, PaperSize, CardSize, MarginSettings, RegistrationSettings, RegistrationPattern

class LayoutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Custom Print Layout")
        self.resize(400, 500)

        self.layout = QVBoxLayout(self)

        # Form layout for inputs
        self.form_layout = QFormLayout()
        self.layout.addLayout(self.form_layout)

        # 1. ID and Name
        self.txt_id = QLineEdit()
        self.txt_id.setPlaceholderText("e.g. custom_a4_cards")
        self.form_layout.addRow("Layout ID (lowercase/underscores):", self.txt_id)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. Custom A4 9 Cards")
        self.form_layout.addRow("Display Name:", self.txt_name)

        # 2. Paper Size
        self.spin_paper_w = QDoubleSpinBox()
        self.spin_paper_w.setRange(50.0, 1000.0)
        self.spin_paper_w.setValue(210.0)
        self.form_layout.addRow("Paper Width (mm):", self.spin_paper_w)

        self.spin_paper_h = QDoubleSpinBox()
        self.spin_paper_h.setRange(50.0, 1000.0)
        self.spin_paper_h.setValue(297.0)
        self.form_layout.addRow("Paper Height (mm):", self.spin_paper_h)

        # 3. Card Size
        self.spin_card_w = QDoubleSpinBox()
        self.spin_card_w.setRange(10.0, 500.0)
        self.spin_card_w.setValue(63.0)
        self.form_layout.addRow("Card Width (mm):", self.spin_card_w)

        self.spin_card_h = QDoubleSpinBox()
        self.spin_card_h.setRange(10.0, 500.0)
        self.spin_card_h.setValue(88.0)
        self.form_layout.addRow("Card Height (mm):", self.spin_card_h)

        self.spin_card_r = QDoubleSpinBox()
        self.spin_card_r.setRange(0.0, 50.0)
        self.spin_card_r.setValue(3.0)
        self.form_layout.addRow("Card Corner Radius (mm):", self.spin_card_r)

        # 4. Grid
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 20)
        self.spin_rows.setValue(3)
        self.form_layout.addRow("Number of Rows:", self.spin_rows)

        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 20)
        self.spin_cols.setValue(3)
        self.form_layout.addRow("Number of Columns:", self.spin_cols)

        # 5. Spacing and Bleed
        self.spin_spacing = QDoubleSpinBox()
        self.spin_spacing.setRange(0.0, 100.0)
        self.spin_spacing.setValue(1.25)
        self.form_layout.addRow("Card Spacing / Gap (mm):", self.spin_spacing)

        self.spin_bleed = QDoubleSpinBox()
        self.spin_bleed.setRange(0.0, 50.0)
        self.spin_bleed.setValue(1.5)
        self.form_layout.addRow("Bleed (mm):", self.spin_bleed)

        # 6. Margins (Simplify by setting uniform margin)
        self.spin_margin = QDoubleSpinBox()
        self.spin_margin.setRange(0.0, 100.0)
        self.spin_margin.setValue(10.0)
        self.form_layout.addRow("Margins (Uniform - mm):", self.spin_margin)

        # 7. Registration
        self.combo_reg_pattern = QComboBox()
        self.combo_reg_pattern.addItems(["THREE", "FOUR"])
        self.form_layout.addRow("Reg Marks Pattern:", self.combo_reg_pattern)

        self.spin_reg_inset = QDoubleSpinBox()
        self.spin_reg_inset.setRange(1.0, 50.0)
        self.spin_reg_inset.setValue(10.0)
        self.form_layout.addRow("Reg Marks Inset (mm):", self.spin_reg_inset)

        self.spin_reg_len = QDoubleSpinBox()
        self.spin_reg_len.setRange(1.0, 50.0)
        self.spin_reg_len.setValue(12.28)
        self.form_layout.addRow("Reg Marks Length (mm):", self.spin_reg_len)

        # OK and Cancel buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_layout_definition(self) -> Layout:
        """Constructs and returns the Layout configuration object from the input form values."""
        m_val = self.spin_margin.value()
        margin = MarginSettings(top_mm=m_val, bottom_mm=m_val, left_mm=m_val, right_mm=m_val)
        
        reg_pattern = RegistrationPattern.THREE if self.combo_reg_pattern.currentText() == "THREE" else RegistrationPattern.FOUR
        reg = RegistrationSettings(
            pattern=reg_pattern,
            inset_mm=self.spin_reg_inset.value(),
            length_mm=self.spin_reg_len.value(),
            thickness_mm=1.0
        )

        return Layout(
            id=self.txt_id.text().strip().lower().replace(" ", "_"),
            name=self.txt_name.text().strip(),
            paper_size=PaperSize(width_mm=self.spin_paper_w.value(), height_mm=self.spin_paper_h.value()),
            card_size=CardSize(width_mm=self.spin_card_w.value(), height_mm=self.spin_card_h.value(), radius_mm=self.spin_card_r.value()),
            rows=self.spin_rows.value(),
            columns=self.spin_cols.value(),
            card_spacing_mm=self.spin_spacing.value(),
            bleed_mm=self.spin_bleed.value(),
            margins=margin,
            registration=reg
        )
