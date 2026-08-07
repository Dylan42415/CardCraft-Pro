DARK_THEME_QSS = """
/* General styles */
QMainWindow {
    background-color: #1e1e24;
}

QWidget {
    background-color: #1e1e24;
    color: #e2e8f0;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

/* Sidebar and containers */
QFrame#sidebar {
    background-color: #121216;
    border-right: 1px solid #2d2d39;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #2d2d39;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    background-color: #15151c;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: #a78bfa; /* Light purple */
}

/* Labels and text inputs */
QLabel {
    background-color: transparent;
    color: #94a3b8;
}

QLabel#titleLabel {
    font-size: 16px;
    font-weight: bold;
    color: #e2e8f0;
}

QLineEdit {
    background-color: #1b1b22;
    border: 1px solid #3b3b4f;
    border-radius: 4px;
    padding: 6px;
    color: #ffffff;
}

QLineEdit:focus {
    border: 1px solid #8b5cf6; /* Purple highlight */
}

/* Comboboxes */
QComboBox {
    background-color: #1b1b22;
    border: 1px solid #3b3b4f;
    border-radius: 4px;
    padding: 5px 8px;
    color: #ffffff;
    min-height: 24px;
}

QComboBox:on {
    border: 1px solid #8b5cf6;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
}

QComboBox QAbstractItemView {
    background-color: #15151c;
    border: 1px solid #3b3b4f;
    selection-background-color: #8b5cf6;
    selection-color: #ffffff;
}

/* Buttons */
QPushButton {
    background-color: #3b3b4f;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    color: #ffffff;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #4c4c65;
    border-color: #8b5cf6;
}

QPushButton:pressed {
    background-color: #2e2e3f;
}

QPushButton#primaryButton {
    background-color: #8b5cf6; /* Electric purple */
}

QPushButton#primaryButton:hover {
    background-color: #a78bfa;
}

QPushButton#successButton {
    background-color: #0d9488; /* Teal */
}

QPushButton#successButton:hover {
    background-color: #14b8a6;
}

/* List Views and Trees */
QListWidget {
    background-color: #121216;
    border: 1px solid #2d2d39;
    border-radius: 6px;
    padding: 5px;
}

QListWidget::item {
    background-color: #1b1b22;
    border: 1px solid #2d2d39;
    border-radius: 4px;
    padding: 8px;
    margin-bottom: 4px;
}

QListWidget::item:hover {
    background-color: #272733;
    border-color: #8b5cf6;
}

QListWidget::item:selected {
    background-color: #8b5cf6;
    color: #ffffff;
    border-color: #a78bfa;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background-color: #121216;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #3b3b4f;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #8b5cf6;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

/* Canvas background */
QGraphicsView {
    background-color: #272730;
    border: 1px solid #1a1a20;
    border-radius: 8px;
}

/* Menu Bar */
QMenuBar {
    background-color: #121216;
    border-bottom: 1px solid #2d2d39;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #8b5cf6;
    border-radius: 4px;
}

QMenu {
    background-color: #15151c;
    border: 1px solid #2d2d39;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #8b5cf6;
}
"""
