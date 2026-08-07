import sys
import os

# Ensure the root folder is on the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.style import DARK_THEME_QSS

def main():
    app = QApplication(sys.argv)
    
    # Apply our custom premium dark theme
    app.setStyleSheet(DARK_THEME_QSS)
    
    # Initialize the main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
