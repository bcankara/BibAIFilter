#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from ui.main_window import MainWindow

# Configure logging - Sadece konsola yazdırma yapacak şekilde değiştirdik
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.StreamHandler()
        # Dosyaya yazma işlemini kaldırdık
        # logging.FileHandler('bibaifilter.log', 'a')
    ]
)
logger = logging.getLogger("BibAIFilter")

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("BibAIFilter")
    app.setStyle("Fusion")
    
    # Set application icon
    app_icon = QIcon("resources/icon_windows.png")
    app.setWindowIcon(app_icon)
    
    # Set application style
    app.setStyleSheet("""
        QWidget {
            font-family: "Segoe UI", sans-serif;
            font-size: 9.5pt;
        }
        QLabel {
            color: #202020;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #E1E1E1;
            border-radius: 8px;
            margin-top: 1.1em;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
    """)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 