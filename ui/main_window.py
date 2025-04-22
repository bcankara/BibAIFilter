#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QGroupBox, QLineEdit, QSpinBox, QDoubleSpinBox,
    QTabWidget, QTableView, QHeaderView, QProgressBar, QMessageBox, QSplitter,
    QApplication, QTextEdit, QScrollArea, QFormLayout, QSlider, QGraphicsDropShadowEffect,
    QFrame, QCheckBox, QDialog, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QSettings, QDir, QTimer
from PyQt5.QtGui import QIcon, QColor, QPixmap, QFont, QPainter
import logging
from pathlib import Path

from ui.excel_model import ExcelTableModel
from utils.excel_processor import ExcelProcessor
from ui.worker_thread import ProcessingThread
from ui.setup_dialog import SetupDialog
from ui.confirm_analysis_dialog import ConfirmAnalysisDialog

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self.settings = QSettings("BibAIFilter", "BibAIFilter")
        self.excel_processor = ExcelProcessor()
        self.worker_thread = None
        self.excel_table_model = None
        
        # Common style variables
        self.groupbox_style = "QGroupBox { font-weight: bold; }"
        
        # Initialize AI processor for settings loading
        from utils.ai_processor import AIProcessor
        
        # Doğrudan dosyadan API yapılandırmasını yükleyen bir AIProcessor oluştur
        try:
            # Config dosya yolunu oluştur
            config_file = str(Path("config") / "API_Settings.json")
            logger.info(f"Looking for API config at: {config_file}")
            
            # Dosya varsa doğrudan yükle
            if os.path.exists(config_file):
                logger.info(f"Config file exists, loading directly")
                try:
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    
                    # Aktif sağlayıcı bilgisini al
                    active_provider = config.get("activeProvider", "openai")
                    logger.info(f"Loaded active provider: {active_provider}")
                    
                    # AIProcessor'u doğrudan yüklenmiş yapılandırma ile oluştur
                    self.ai_processor = AIProcessor(provider=active_provider)
                    
                    # API anahtarının yüklendiğinden emin ol
                    logger.info(f"Initial API key status: {bool(self.ai_processor.api_key)}")
                    
                except Exception as e:
                    logger.error(f"Error loading config directly: {str(e)}")
                    self.ai_processor = AIProcessor()
            else:
                logger.info(f"Config file not found, using default AIProcessor")
                self.ai_processor = AIProcessor()
        except Exception as e:
            logger.error(f"Error during config initialization: {str(e)}")
            self.ai_processor = AIProcessor()
        
        # Setup completed flag
        self.setup_completed = False
        
        self.setup_ui()
        self.load_settings()
        
        # Dosya çıktı kutusunu temizle ama placeholder metni göster
        self.output_file_edit.clear()
        self.generate_default_output_filename()
        
        # Always show setup dialog on startup
        QTimer.singleShot(100, self.show_setup_dialog)
    
    def init_logger(self):
        """Initialize the logger"""
        # Configure the logger
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler())
        logger.addHandler(logging.FileHandler("app.log"))
    
    def setup_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("BibAIFilter - Find Relevant Research, Faster")
        self.setMinimumWidth(1200)
        self.setMinimumHeight(800)
        
        # Set window icon
        self.setWindowIcon(QIcon("resources/icon_windows.png"))
        
        # Windows 11 color palette - modern palette for better visibility
        primary_color = "#0078D4"     # Windows blue (darker tone)
        accent_color = "#50ABF1"      # Light blue (accent - harmonized)
        success_color = "#107C10"     # Green (more lively)
        warning_color = "#F8A800"     # Yellow (harmonized darker tone)
        error_color = "#D83B01"       # Red (harmonized darker tone)
        text_color = "#202020"        # Main text
        secondary_text = "#5F6368"    # Secondary text
        divider_color = "#E1E1E1"     # Dividers
        
        background_color = "#F9F9F9"  # Background
        card_color = "#FFFFFF"        # Card background
        hover_color = "#F2F2F2"       # Hover background
        subtle_hover = "#F5F5F5"      # Subtle hover
        
        border_radius = "8px"         # More consistent rounded corners
        input_radius = "6px"          # More consistent input corners
        
        # Main widget and layout
        central_widget = QWidget()
        central_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {background_color};
                color: {text_color};
                font-family: 'Segoe UI', sans-serif;
                font-size: 9.5pt;
            }}
            QGroupBox {{
                border: 1px solid {divider_color};
                border-radius: {border_radius};
                margin-top: 1.5ex;
                padding: 10px;
                background-color: {card_color};
                font-weight: normal;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {primary_color};
                font-weight: 600;
                font-size: 10pt;
            }}
            QLineEdit {{
                border: 1px solid {divider_color};
                border-radius: {input_radius};
                padding: 8px;
                background-color: {card_color};
                selection-background-color: {primary_color};
                min-height: 16px;
                font-size: 9pt;
            }}
            QLineEdit:focus {{
                border-color: {primary_color};
                background-color: {card_color};
            }}
            QPushButton {{
                border-radius: {input_radius};
                padding: 8px 14px;
                background-color: {primary_color};
                color: white;
                border: none;
                font-weight: 600;
                min-height: 16px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: #006CBE;
            }}
            QPushButton:pressed {{
                background-color: #005AA0;
            }}
            QPushButton:disabled {{
                background-color: {divider_color};
                color: {secondary_text};
            }}
            QCheckBox {{
                spacing: 8px;
                font-size: 9pt;
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 3px;
            }}
            QTabWidget::pane {{
                border: 1px solid {divider_color};
                border-radius: {border_radius};
                background-color: {background_color};
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 20px;
                margin-right: 6px;
                font-weight: normal;
                color: {secondary_text};
                font-size: 9.5pt;
                font-family: "Segoe UI", Verdana, sans-serif;
                min-width: 100px;
            }}
            QTabBar::tab:selected {{
                background-color: transparent;
                border-bottom: 2px solid {primary_color};
                color: {primary_color};
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: transparent;
                font-weight: bold;
                font-size: 10pt;
            }}
            QScrollBar:vertical {{
                border: none;
                background-color: {hover_color};
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #C0C0C0;
                min-height: 28px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #A0A0A0;
            }}
            QScrollBar:horizontal {{
                border: none;
                background-color: {hover_color};
                height: 12px;
                margin: 0px;
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: #C0C0C0;
                min-width: 28px;
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: #A0A0A0;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                width: 0px;
                background: none;
            }}
            QProgressBar {{
                border: none;
                border-radius: 6px;
                text-align: center;
                background-color: {divider_color};
                height: 12px;
                font-size: 8pt;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {primary_color};
                border-radius: 6px;
            }}
            QLabel {{
                font-size: 9.5pt;
            }}
            QTextEdit {{
                border: 1px solid {divider_color};
                border-radius: {input_radius};
                padding: 4px;
                background-color: {card_color};
                selection-background-color: {primary_color};
                font-size: 9pt;
            }}
        """)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)
        
        # Add header with logo and title
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 20)  # Add some space at the bottom
        
        # BibAIFilter Logo (Tek resim olarak)
        logo_label = QLabel()
        logo_pixmap = QPixmap("resources/logo_bibaifilter.webp")
        if not logo_pixmap.isNull():
            logo_pixmap = logo_pixmap.scaled(350, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
        else:
            # Fallback if logo doesn't exist
            logo_label.setText("BibAIFilter")
            logo_label.setFont(QFont("Segoe UI", 32, QFont.Bold))
            logo_label.setStyleSheet(f"color: {primary_color};")
        
        logo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(logo_label)
        
        # Right logo (BIBEXPY)
        header_layout.addStretch(1)
        
        # BibexPy logo and text on the right (for branding)
        bibexpy_layout = QVBoxLayout()
        
        # BibexPy icon
        bibexpy_icon_label = QLabel()
        bibexpy_icon = QPixmap("resources/logo_bibewxpy.webp")
        if not bibexpy_icon.isNull():
            bibexpy_icon = bibexpy_icon.scaled(140, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            bibexpy_icon_label.setPixmap(bibexpy_icon)
            bibexpy_icon_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # BibexPy slogan
        bibexpy_slogan = QLabel("Bibliometrics Experience with Python")
        bibexpy_slogan.setFont(QFont("Segoe UI", 10))
        bibexpy_slogan.setStyleSheet(f"color: {primary_color};")
        bibexpy_slogan.setAlignment(Qt.AlignRight)
        
        bibexpy_website = QLabel("bibexpy.com")
        bibexpy_website.setFont(QFont("Segoe UI", 9))
        bibexpy_website.setStyleSheet(f"color: {secondary_text};")
        bibexpy_website.setAlignment(Qt.AlignRight)

        bibexpy_layout.addWidget(bibexpy_icon_label)
        bibexpy_layout.addWidget(bibexpy_slogan)
        bibexpy_layout.addWidget(bibexpy_website)
        bibexpy_layout.setSpacing(2)
        
        header_layout.addLayout(bibexpy_layout)
        
        main_layout.addLayout(header_layout)
        
        # Main tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)  # More modern tab view
        self.tabs.setElideMode(Qt.ElideRight)  # Clip mode for long tab names
        self.tabs.setMinimumHeight(600)
        
        # Input tab (renamed to Main - combines Main and Results)
        self.input_tab = QWidget()
        self.setup_combined_main_tab()
        self.tabs.addTab(self.input_tab, "Main")
        
        # Add API Settings tab
        self.api_settings_tab = QWidget()
        self.setup_api_settings_tab()
        self.tabs.addTab(self.api_settings_tab, "API Settings")
        
        main_layout.addWidget(self.tabs)
        
        # Status bar'ı tamamen kaldır
        self.status_label = QLabel("")  # Gizli bir label ekleyelim - kodun diğer kısımlarındaki referanslar için
        self.status_label.setVisible(False)
        
        self.setCentralWidget(central_widget)
    
    def setup_combined_main_tab(self):
        """Set up the combined main tab with input and results sections"""
        layout = QVBoxLayout(self.input_tab)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(15)
        
        # Top section - Configuration and Input
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Setup input configuration section
        self.setup_input_section(top_layout)
        
        # Bottom section - Results and Log
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # Setup results section
        self.setup_results_section(bottom_layout)
        
        # Add widgets to main splitter
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(top_widget)
        main_splitter.addWidget(bottom_widget)
        main_splitter.setSizes([350, 650])  # Give more space to results
        
        layout.addWidget(main_splitter)
    
    def setup_input_section(self, parent_layout):
        """Set up the input configuration section (formerly part of input tab)"""
        # Column Mapping Info and File Settings
        input_group = self.create_group_box("Input/Output Configuration")
        input_layout = QHBoxLayout()
        input_layout.setSpacing(15)  # İki bölüm arasında eşit boşluk
        
        # İki bölüm için iki eşit yükseklikte container widget oluştur
        # Column Mappings section
        mapping_section = QWidget()
        mapping_layout = QVBoxLayout(mapping_section)
        mapping_layout.setContentsMargins(0, 0, 0, 0)
        mapping_layout.setSpacing(8)
        
        # Files section
        files_section = QWidget()
        files_layout = QVBoxLayout(files_section)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(8)
        
        # Column mappings content - groups and titles adjusted
        mappings_group = QGroupBox()
        mappings_group.setStyleSheet("QGroupBox { border: 1px solid #E1E1E1; border-radius: 6px; background-color: white; }")
        mappings_layout = QVBoxLayout(mappings_group)
        mappings_layout.setSpacing(15)
        mappings_layout.setContentsMargins(15, 15, 15, 15)
        
        # Title layout with settings icon inside group box
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)
        header_layout.setSpacing(10)
        
        # Title label
        mapping_title = QLabel("Column Mappings")
        mapping_title.setStyleSheet("font-weight: bold; font-size: 11pt; background-color: white; padding: 4px;")
        header_layout.addWidget(mapping_title)
        
        # Settings icon button
        settings_button = QPushButton()
        settings_button.setIcon(QIcon("resources/gear.png"))
        settings_button.setIconSize(QSize(28, 28))
        settings_button.setFixedSize(32, 32)
        settings_button.setToolTip("Open Setup Dialog")
        settings_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #F0F0F0;
                border-radius: 16px;
            }
            QPushButton:pressed {
                background-color: #E0E0E0;
            }
        """)
        settings_button.clicked.connect(self.show_setup_dialog)
        header_layout.addWidget(settings_button)
        header_layout.addStretch()
        
        mappings_layout.addLayout(header_layout)
        
        # Fields layout
        fields_layout = QFormLayout()
        fields_layout.setSpacing(10)
        
        # Add read-only displays for selected columns with white background
        self.title_display = QLineEdit()
        self.title_display.setReadOnly(True)
        self.title_display.setPlaceholderText("Not selected")
        self.title_display.setStyleSheet("background-color: white;")
        fields_layout.addRow("Title Column:", self.title_display)
        
        self.abstract_display = QLineEdit()
        self.abstract_display.setReadOnly(True)
        self.abstract_display.setPlaceholderText("Not selected")
        self.abstract_display.setStyleSheet("background-color: white;")
        fields_layout.addRow("Abstract Column:", self.abstract_display)
        
        self.keywords_display = QLineEdit()
        self.keywords_display.setReadOnly(True)
        self.keywords_display.setPlaceholderText("Not selected (optional)")
        self.keywords_display.setStyleSheet("background-color: white;")
        fields_layout.addRow("Keywords Column:", self.keywords_display)
        
        self.categories_display = QLineEdit()
        self.categories_display.setReadOnly(True)
        self.categories_display.setPlaceholderText("Not selected (optional)")
        self.categories_display.setStyleSheet("background-color: white;")
        fields_layout.addRow("Categories Column:", self.categories_display)
        
        mappings_layout.addLayout(fields_layout)
        
        mapping_layout.addWidget(mappings_group)
        mapping_layout.addStretch()
        
        # Files group - title inside the group
        files_group = QGroupBox()
        files_group.setStyleSheet("QGroupBox { border: 1px solid #E1E1E1; border-radius: 6px; background-color: white; }")
        files_group_layout = QVBoxLayout(files_group)
        files_group_layout.setSpacing(15)
        files_group_layout.setContentsMargins(15, 15, 15, 15)
        
        # Title for Files inside the group
        files_header = QHBoxLayout()
        files_header.setContentsMargins(0, 0, 0, 10)
        
        files_title = QLabel("Files")
        files_title.setStyleSheet("font-weight: bold; font-size: 11pt; background-color: white; padding: 4px;")
        files_header.addWidget(files_title)
        files_header.addStretch()
        
        files_group_layout.addLayout(files_header)
        
        # File input fields with white background
        self.files_layout = QFormLayout()
        self.files_layout.setSpacing(10)
        
        # Input file selection
        input_file_layout = QHBoxLayout()
        self.input_file_edit = QLineEdit()
        self.input_file_edit.setReadOnly(True)
        self.input_file_edit.setPlaceholderText("Select input Excel file")
        self.input_file_edit.setStyleSheet("background-color: white;")
        
        browse_input_button = QPushButton("Browse")
        browse_input_button.clicked.connect(self.browse_input_file)
        
        input_file_layout.addWidget(self.input_file_edit)
        input_file_layout.addWidget(browse_input_button)
        self.files_layout.addRow("Input Excel:", input_file_layout)
        
        # Output file selection - without placeholder
        output_file_layout = QHBoxLayout()
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setReadOnly(True)
        self.output_file_edit.setStyleSheet("""
            QLineEdit {
                color: #202020;
                background-color: white;
            }
        """)
        
        browse_output_button = QPushButton("Browse")
        browse_output_button.clicked.connect(self.browse_output_file)
        
        output_file_layout.addWidget(self.output_file_edit)
        output_file_layout.addWidget(browse_output_button)
        self.files_layout.addRow("Output Excel:", output_file_layout)
        
        # Output file info text
        self.output_info_label = QLabel("Output file will be automatically generated in the same directory as the input file if not specified.")
        self.output_info_label.setStyleSheet("color: #0078D4; font-style: italic; font-size: 9pt;")
        self.output_info_label.setWordWrap(True)
        self.files_layout.addRow("", self.output_info_label)
        
        files_group_layout.addLayout(self.files_layout)
        
        files_layout.addWidget(files_group)
        files_layout.addStretch()
        
        # Her iki bölümü ana layout'a ekle
        input_layout.addWidget(mapping_section, 1)  # 1:1 oranında genişlik
        input_layout.addWidget(files_section, 1)    # 1:1 oranında genişlik
        
        # Add input layout to the group
        input_group.layout().addLayout(input_layout)
        
        # Add input group to parent layout
        parent_layout.addWidget(input_group)
        
        # Topic and Threshold (AI Configuration)
        ai_group = self.create_group_box("AI Analysis Configuration")
        ai_layout = QHBoxLayout()
        
        # Topic input
        topic_group = QGroupBox("Topic")
        topic_group.setStyleSheet(self.groupbox_style)
        topic_layout = QVBoxLayout(topic_group)
        
        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("Enter your topic (e.g., 'Machine Learning in Healthcare')")
        self.topic_edit.setMinimumHeight(32)  # Yüksekliği artırıyoruz
        self.topic_edit.setStyleSheet("QLineEdit { padding: 2px 8px; font-size: 10pt; background-color: white; }")
        topic_layout.addWidget(self.topic_edit)
        
        # Add to AI layout
        ai_layout.addWidget(topic_group)
        
        # Threshold setting
        threshold_group = QGroupBox("Relevance Threshold")
        threshold_group.setStyleSheet(self.groupbox_style)
        threshold_layout = QVBoxLayout(threshold_group)
        
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(1.0, 7.0)
        self.threshold_spin.setSingleStep(1.0)
        self.threshold_spin.setValue(4.0)
        self.threshold_spin.setDecimals(0)
        threshold_layout.addWidget(self.threshold_spin)
        
        # Add to AI layout
        ai_layout.addWidget(threshold_group)
        
        # Max Records setting
        max_records_group = QGroupBox("Max Records to Process")
        max_records_group.setStyleSheet(self.groupbox_style)
        max_records_layout = QVBoxLayout(max_records_group)
        
        self.max_records_spin = QSpinBox()
        self.max_records_spin.setRange(0, 10000)  # 0 means process all
        self.max_records_spin.setSingleStep(10)
        self.max_records_spin.setValue(0)
        self.max_records_spin.setSpecialValueText("All")  # "All" text when value is 0
        self.max_records_spin.setToolTip("Maximum number of records to process (0 means process all records)")
        max_records_layout.addWidget(self.max_records_spin)
        
        # Add to AI layout
        ai_layout.addWidget(max_records_group)
        
        # Iterations setting
        iterations_group = QGroupBox("Iterations")
        iterations_group.setStyleSheet(self.groupbox_style)
        iterations_layout = QVBoxLayout(iterations_group)
        
        self.iterations_spin = QSpinBox()
        self.iterations_spin.setRange(1, 10)  # 1 to 10 iterations
        self.iterations_spin.setSingleStep(1)
        self.iterations_spin.setValue(1)
        self.iterations_spin.setToolTip("Number of iterations for each record (multiple results will be saved)")
        iterations_layout.addWidget(self.iterations_spin)
        
        # Add to AI layout
        ai_layout.addWidget(iterations_group)
        
        # Add to parent layout
        ai_group.layout().addLayout(ai_layout)
        parent_layout.addWidget(ai_group)
        
        # Start Button (always at the bottom of input section)
        # Button ve progress barı içerecek bir container widget oluştur
        start_container = QWidget()
        start_container_layout = QHBoxLayout(start_container)
        start_container_layout.setContentsMargins(0, 0, 0, 0)
        start_container_layout.setSpacing(10)  # Butonlar arasında boşluk
        
        # Start button - solda ve daha geniş
        self.start_button = QPushButton("Start Publication Filtering")
        self.start_button.setMinimumHeight(50)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #107C10;  /* Yeşil renk - success */
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                padding: 14px 30px;
            }
            QPushButton:hover {
                background-color: #0B6111;
            }
            QPushButton:pressed {
                background-color: #094509;
            }
            QPushButton:disabled {
                background-color: #E1E1E1;
                color: #5F6368;
            }
        """)
        self.start_button.clicked.connect(self.start_filtering)
        
        # Progress barı butona entegre et
        self.progress_bar = QProgressBar(self.start_button)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: rgba(16, 124, 16, 0.5);
                text-align: center;
                color: white;
                font-weight: 600;
                font-size: 14px;
                border-radius: 8px;
            }
            QProgressBar::chunk {
                background-color: rgba(255, 255, 255, 0.4);
                border-radius: 8px;
            }
        """)
        # Progress barı buton boyutlarına göre ayarla ve gizle
        self.progress_bar.setGeometry(0, 0, self.start_button.width(), self.start_button.height())
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        
        # Butonun tekrar boyutlandırma olayını izle ve progress barı uygun boyuta getir
        self.start_button.resizeEvent = lambda event: self.progress_bar.setGeometry(0, 0, self.start_button.width(), self.start_button.height())
        
        # Stop button - sağda ve daha küçük
        self.stop_button = QPushButton("Stop")
        self.stop_button.setMinimumHeight(50)
        self.stop_button.setMaximumWidth(120)  # Sabit genişlik
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #D83B01;  /* Kırmızı renk - error */
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #C23001;
            }
            QPushButton:pressed {
                background-color: #A62901;
            }
        """)
        self.stop_button.clicked.connect(self.stop_filtering)
        self.stop_button.setVisible(False)
        
        # Butonları yerleştir
        start_container_layout.addWidget(self.start_button, 1)  # Stretch faktörü 1
        start_container_layout.addWidget(self.stop_button, 0)   # Stretch faktörü 0
        
        parent_layout.addWidget(start_container)
    
    def setup_results_section(self, parent_layout):
        """Set up the results section (formerly results tab)"""
        # Results group
        results_group = self.create_group_box("Filtered Publications")
        results_layout = QVBoxLayout()
        
        # Setup table view for results - simplified to only show Title - Score - Result
        self.results_table = QTableView()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setStyleSheet("""
            QTableView {
                border: 1px solid #E1E1E1;
                border-radius: 8px;
                background-color: #FFFFFF;
                gridline-color: #F2F2F2;
                selection-background-color: #E5F1FB;
                selection-color: #202020;
            }
            QTableView::item {
                padding: 5px;
            }
            QTableView::item:alternate {
                background-color: #F9F9F9;
            }
            QHeaderView::section {
                background-color: #F2F2F2;
                color: #202020;
                padding: 5px;
                border: none;
                border-right: 1px solid #E1E1E1;
                border-bottom: 1px solid #E1E1E1;
                font-weight: bold;
            }
        """)
        
        results_layout.addWidget(self.results_table)
        results_group.layout().addLayout(results_layout)
        
        # Artık progress bar kullanmıyoruz, direkt sonuç grubunu ekle
        parent_layout.addWidget(results_group)
        
        # Create a hidden log text widget for compatibility with existing code
        self.log_text = QTextEdit()
        self.log_text.setVisible(False)
        parent_layout.addWidget(self.log_text)
    
    def create_group_box(self, title):
        """Create a styled group box"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #E1E1E1;
                border-radius: 8px;
                margin-top: 1.5ex;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 12px;
                background-color: white;
                border: 2px solid white;
            }
        """)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(20, 20, 20, 20)
        return group
    
    def add_shadow_effect(self, widget, blur_radius=4, color=QColor(0, 0, 0, 15), x_offset=0, y_offset=1):
        """Add shadow effect to a widget"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur_radius)
        shadow.setColor(color)
        shadow.setOffset(x_offset, y_offset)
        widget.setGraphicsEffect(shadow)
    
    def update_threshold_label(self):
        """Update the threshold label when slider value changes"""
        value = self.threshold_spin.value()
        self.threshold_spin.setText(f"{value:.2f}")
    
    def browse_input_file(self):
        """Open file dialog to select Excel file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if file_path:
            self.input_file_edit.setText(file_path)
            
            # Çıktı dosya adını otomatik güncelle
            self.generate_default_output_filename()
            
            # Input dosya bilgisini güncelle
            input_path = Path(file_path)
            input_dir = input_path.parent
            input_name = input_path.stem  # Dosya adı (uzantısız)
            
            # Output dosya adını oluştur - her zaman .xlsx uzantısı kullan
            output_name = f"{input_name}_BibAIFiltered.xlsx"
            output_path = str(input_dir / output_name)
            
            # Output info metnini doğrudan güncelle
            self.output_info_label.setText(f"Output will be automatically saved as: {output_path}")
            
            self.load_excel_file(file_path)
            self.update_start_button_state()
    
    def browse_output_file(self):
        """Open file dialog to select output Excel file"""
        # Varsayılan dosya adını oluştur
        default_filename = self.generate_default_output_filename()
        default_directory = ""
        
        # Eğer giriş dosyası seçilmişse, onun konumunu kullan
        input_file = self.input_file_edit.text()
        if input_file:
            input_path = Path(input_file)
            default_directory = str(input_path.parent)
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Filtered Results", os.path.join(default_directory, default_filename), 
            "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if file_path:
            # .xlsx uzantısı yoksa ekle
            if not file_path.lower().endswith('.xlsx'):
                file_path += '.xlsx'
            
            self.output_file_edit.setText(file_path)
            self.output_info_label.setText(f"Output will be manually saved to: {file_path}")
            self.update_start_button_state()
    
    def generate_default_output_filename(self):
        """AI modeline göre varsayılan çıktı dosyası adı oluştur"""
        # Modelin kısaltmasını al
        model_abbr = self.get_model_abbreviation()
        
        # Giriş dosyasına dayalı ad oluştur
        input_file = self.input_file_edit.text()
        if input_file:
            input_path = Path(input_file)
            filename = f"{input_path.stem}_BibAI_{model_abbr}.xlsx"
            
            # Placeholder'ı ayarla
            self.output_file_edit.setPlaceholderText(filename)
            
            # Eğer output dosya adı boşsa, doğrudan dosya adını ayarla (placeholder değil)
            if not self.output_file_edit.text() and input_file:
                output_file = str(input_path.parent / filename)
                # Metin kutusunu güncelle
                self.output_file_edit.setText(output_file)
                self.output_info_label.setText(f"Output will be saved as: {output_file}")
                logger.info(f"Output filename automatically set to: {output_file}")
            
            return filename
        else:
            # Sadece model kısaltmasını içeren varsayılan ad
            filename = f"filtered_results_BibAI_{model_abbr}.xlsx"
            self.output_file_edit.setPlaceholderText(filename)
            return filename
    
    def get_model_abbreviation(self):
        """Mevcut AI modelinin okunabilir kısaltmasını döndür"""
        model = self.ai_processor.model.lower()
        
        # OpenAI modelleri için kısaltmalar
        if "gpt-4o" in model:
            return "gpt4o"
        elif "gpt-4-turbo" in model:
            return "gpt4turbo"
        elif "gpt-4" in model:
            return "gpt4"
        elif "gpt-3.5-turbo-instruct" in model:
            return "gpt35turboinstruct"
        elif "gpt-3.5-turbo" in model:
            return "gpt35turbo"
        elif "gpt-3.5" in model:
            return "gpt35"
            
        # Claude modelleri için kısaltmalar
        elif "claude-3-7-sonnet" in model:
            return "claude37sonnet"
        elif "claude-3-5-sonnet" in model:
            return "claude35sonnet"
        elif "claude-3-5-haiku" in model:
            return "claude35haiku"
        elif "claude-3" in model:
            if "opus" in model:
                return "claude3opus"
            elif "sonnet" in model:
                return "claude3sonnet"
            elif "haiku" in model:
                return "claude3haiku"
            else:
                return "claude3"
                
        # Gemini modelleri için kısaltmalar
        elif "gemini" in model:
            if "flash" in model:
                return "geminiflash"
            elif "pro" in model:
                return "geminipro"
            elif "ultra" in model:
                return "geminiultra"
            else:
                return "gemini"
                
        # DeepSeek modelleri için kısaltmalar
        elif "deepseek" in model:
            if "coder" in model:
                return "deepseekcoder"
            else:
                return "deepseek"
                
        # Bilinmeyen modeller için
        else:
            # Modelin ilk harflerini al
            model_cleaned = model.replace('-', '').replace('.', '')
            return model_cleaned[:12]  # İlk 12 karakter
    
    def load_excel_file(self, file_path):
        """Load Excel file and update column combos"""
        try:
            # Load Excel file and get columns
            columns = self.excel_processor.get_columns(file_path)
            
            # QLineEdit nesneleri için sadece tooltip güncelleme yeter
            # Bunlar read-only olduğundan içeriklerini güncellemiyoruz
            column_list = ", ".join(columns)
            self.title_display.setToolTip(f"Mevcut sütunlar: {column_list}")
            self.abstract_display.setToolTip(f"Mevcut sütunlar: {column_list}")
            self.keywords_display.setToolTip(f"Mevcut sütunlar: {column_list}")
            self.categories_display.setToolTip(f"Mevcut sütunlar: {column_list}")
            
            self.log_message(f"Loaded Excel file: {file_path}")
        except Exception as e:
            self.log_message(f"Error loading Excel file: {str(e)}", level=logging.ERROR)
            QMessageBox.critical(self, "Error", f"Failed to load Excel file:\n{str(e)}")
    
    def update_start_button_state(self):
        """Update the state of the start button based on form completeness"""
        file_selected = bool(self.input_file_edit.text())
        topic_entered = bool(self.topic_edit.text())
        
        # Start butonu için sadece input dosyası seçilmiş ve topic girilmiş olması yeterli
        self.start_button.setEnabled(file_selected and topic_entered)
    
    def start_filtering(self):
        """Start the filtering process"""
        # Input validation
        input_file = self.input_file_edit.text()
        if not input_file:
            QMessageBox.warning(self, "Missing Input", "Please select an input file.")
            return
        
        # Clear existing results in the Filtered Publications table
        if self.excel_table_model is not None:
            # Create a new empty model with the same headers
            columns = ["Title", "Score", "Result"]
            self.excel_table_model = ExcelTableModel([], columns)
            self.results_table.setModel(self.excel_table_model)
            
            # Set column widths
            header = self.results_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)  # Title stretches
            header.setSectionResizeMode(1, QHeaderView.Fixed)    # Score fixed
            header.setSectionResizeMode(2, QHeaderView.Fixed)    # Result fixed
            
            # Set fixed widths for score and result columns
            self.results_table.setColumnWidth(1, 80)
            self.results_table.setColumnWidth(2, 80)
        
        # Make sure progress bar is properly sized and positioned
        self.progress_bar.setGeometry(0, 0, self.start_button.width(), self.start_button.height())
        
        # Get other parameters from UI
        output_file = self.output_file_edit.text()
        title_column = self.title_display.text()
        abstract_column = self.abstract_display.text()
        keywords_column = self.keywords_display.text()
        topic = self.topic_edit.text()
        threshold = self.threshold_spin.value()
        max_records = self.max_records_spin.value()  # Get max records value
        iterations = self.iterations_spin.value()    # Get iterations value
        
        # Validate required parameters
        if not title_column or title_column == "Not selected":
            QMessageBox.warning(self, "Missing Column", "Please select a Title column.")
            return
            
        if not abstract_column or abstract_column == "Not selected":
            QMessageBox.warning(self, "Missing Column", "Please select an Abstract column.")
            return
            
        if not topic:
            QMessageBox.warning(self, "Missing Topic", "Please enter a topic.")
            return
        
        # İstekli kontrolü: Şu anki çıktı dosya adını placeholder'da önerilen model ile uyumlu mu?
        current_model_abbr = self.get_model_abbreviation()
        
        # Önerilen varsayılan dosya adını al
        suggested_filename = self.output_file_edit.placeholderText()
        
        # Hem mevcut bir dosya adı girilmiş hem de bu dosya adı önerilen modelden farklıysa uyarı göster
        if output_file and suggested_filename and current_model_abbr not in output_file:
            # Önceki analizden farklı bir model kullanıldığını kontrol et
            if not output_file.endswith(f"_{current_model_abbr}.xlsx"):
                # Kullanıcıya sorma
                answer = QMessageBox.question(
                    self,
                    "Model Değişimi Algılandı",
                    f"Önceki analizden farklı bir model ({current_model_abbr}) kullanılıyor. "
                    f"Çıktı dosyası adını otomatik olarak güncellemek ister misiniz?\n\n"
                    f"Önerilen: {suggested_filename}",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if answer == QMessageBox.Yes:
                    # Evet seçildiyse çıktı dosya adını önerilen ile güncelle
                    output_file = ""  # Aşağıdaki kod otomatik olarak önerilen adı kullanacak
        
        # If output file is not provided, create one based on input file with model info
        if not output_file:
            # Varsayılan dosya adını al - model kısaltmasını içerir
            default_name = self.generate_default_output_filename()
            
            # Giriş dosyasının konumunu kullan
            input_path = Path(input_file)
            output_file = str(input_path.parent / default_name)
            
            # Output bilgisini güncelle
            self.output_file_edit.setText(output_file)
            self.output_info_label.setText(f"Output will be saved as: {output_file}")
            logger.info(f"Auto-generated output filename with model info: {output_file}")
            
        # Get categories column (optional)
        categories_column = self.categories_display.text()
        if categories_column == "Not selected":
            categories_column = ""
            
        # Process keywords column
        if keywords_column == "Not selected":
            keywords_column = ""
            
        # Use the existing AI processor instead of creating a new one
        # Test connection with selected provider
        if not self.ai_processor.test_connection():
            QMessageBox.warning(self, "API Connection Error", 
                               f"Failed to connect to the AI API.\n\n"
                               "Please check your API settings in the API Settings tab.")
            return
            
        # Show prompt template for confirmation
        default_prompt = self.get_default_prompt_template()
        
        # Show the prompt confirmation dialog - doğru parametreleri geçirelim
        confirm_dialog = ConfirmAnalysisDialog(topic, default_prompt, self)
        confirm_dialog.prompt_confirmed.connect(lambda prompt: self.start_analysis_with_prompt(
            input_file, output_file, title_column, abstract_column, 
            keywords_column, topic, threshold, max_records, 
            self.ai_processor, prompt, iterations
        ))
        confirm_dialog.exec_()
    
    def stop_filtering(self):
        """Stop the filtering process"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.log_message("Stopping the process...")
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self.reset_progress_bar()
            self.start_button.setEnabled(True)
            self.stop_button.setVisible(False)
            self.log_message("Process stopped by user.")
    
    def on_processing_complete(self, filtered_count, total_count):
        """Processing is complete"""
        self.reset_progress_bar()
        self.worker_thread = None
        self.stop_button.setVisible(False)
        self.start_button.setEnabled(True)
        
        # Processing results message
        message = f"Processing complete! Found {filtered_count} relevant publications out of {total_count} processed publications."
        self.log_message(message)
        
        # Çıktı dosya adını yenile - model değişimi için hazır olsun
        self.output_file_edit.clear()
        self.generate_default_output_filename()
        
        # Show a success message box
        QMessageBox.information(self, "Processing Complete", message)
    
    def on_error(self, error_message):
        """Handle error from the worker thread"""
        self.reset_progress_bar()
        self.worker_thread = None
        self.stop_button.setVisible(False)
        self.start_button.setEnabled(True)
        
        error_log = f"Error: {error_message}"
        self.log_message(error_log, level=logging.ERROR)
        
        # Show error message box
        QMessageBox.critical(self, "Processing Error", error_log)
    
    def on_file_processed(self, result_data, is_relevant):
        """Update UI with processed file results"""
        # Split the result data into columns
        # Format is: "title|score|result"
        try:
            parts = result_data.split('|', 2)
            title = parts[0]
            score = parts[1] if len(parts) > 1 else "0.0"
            result_text = parts[2] if len(parts) > 2 else ("RELEVANT" if is_relevant else "NOT RELEVANT")
            
            # Create model if not exists
            if self.excel_table_model is None:
                # Create a model with custom headers
                columns = ["Title", "Score", "Result"]
                self.excel_table_model = ExcelTableModel([], columns)
                self.results_table.setModel(self.excel_table_model)
                
                # Set column widths
                header = self.results_table.horizontalHeader()
                header.setSectionResizeMode(0, QHeaderView.Stretch)  # Title stretches
                header.setSectionResizeMode(1, QHeaderView.Fixed)    # Score fixed
                header.setSectionResizeMode(2, QHeaderView.Fixed)    # Result fixed
                
                # Set fixed widths for score and result columns
                self.results_table.setColumnWidth(1, 80)
                self.results_table.setColumnWidth(2, 80)
            
            # Add the data to the model
            self.excel_table_model.append_row({
                "Title": title,
                "Score": score,
                "Result": result_text
            })
            
            # Scroll to the latest row
            self.results_table.scrollToBottom()
        except Exception as e:
            logger.error(f"Error formatting result data: {str(e)}")
            self.log_message(f"Error formatting result: {str(e)}", level=logging.ERROR)
    
    def load_results(self):
        """Load filtered results into the table view"""
        try:
            # Get output file
            output_file = self.output_file_edit.text()
            if not os.path.exists(output_file):
                self.log_message("Results file not found", level=logging.ERROR)
                return
            
            # Load Excel data
            data = self.excel_processor.load_excel_data(output_file)
            
            # Create model and set it on the table view
            self.excel_table_model = ExcelTableModel(data)
            self.results_table.setModel(self.excel_table_model)
            
            # Adjust column widths
            self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.results_table.horizontalHeader().setMinimumSectionSize(100)
            
            self.log_message("Loaded filtered results into table")
        except Exception as e:
            self.log_message(f"Error loading results: {str(e)}", level=logging.ERROR)
    
    def log_message(self, message, level=logging.INFO):
        """Add a message to the log text widget"""
        if level == logging.ERROR:
            message = f"ERROR: {message}"
            self.log_text.append(f"<span style='color: #D83B01;'>{message}</span>")
        elif level == logging.WARNING:
            message = f"WARNING: {message}"
            self.log_text.append(f"<span style='color: #F8A800;'>{message}</span>")
        else:
            self.log_text.append(message)
        
        # Scroll to bottom
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        
        # Log to system logger
        logger.log(level, message)
    
    def update_progress(self, percentage):
        """Update the progress bar"""
        # Show the progress bar if not visible
        if not self.progress_bar.isVisible():
            self.progress_bar.setVisible(True)
        
        # Update the value
        self.progress_bar.setValue(percentage)
        
        # Yüzdeyi metin olarak göster
        self.progress_bar.setFormat(f"Processing... {percentage}%")
        
        # Start butonunun metnini güncelle
        self.start_button.setText(f"Processing... {percentage}%")
        
        # İşlem tamamlandığında progress barı temizle
        if percentage >= 100:
            QTimer.singleShot(1000, self.reset_progress_bar)
    
    def reset_progress_bar(self):
        """Reset progress bar after completion"""
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.start_button.setText("Start Publication Filtering")
    
    def load_settings(self):
        """Load saved settings"""
        # Program her başlangıçta sıfırdan başlaması için 
        # Excel dosyası ve sütun eşleştirmelerini boş bırakıyoruz
        
        # Sadece API ayarları ve gelişmiş seçenekleri yükle
        # API anahtar bilgilerini sıfırlamak istemiyoruz
        
        # Connect signals for auto-saving settings
        self.topic_edit.textChanged.connect(self.update_start_button_state)
        self.output_file_edit.textChanged.connect(self.update_start_button_state)
    
    def save_settings(self):
        """Save settings"""
        # Program her başladığında temiz başlaması için Excel dosyası ve sütun
        # seçim bilgilerini kaydetmiyoruz
        
        # Not: QSettings'e hiçbir şey kaydetmiyoruz, böylece her
        # program başlangıcında temiz bir başlangıç yapılacak
        
        # API settings are saved separately via save_api_settings method
        pass
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop any running processes
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.terminate()
        
        # Save settings
        self.save_settings()
        
        event.accept()

    def setup_api_settings_tab(self):
        """Set up the API Settings tab"""
        layout = QVBoxLayout(self.api_settings_tab)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(15)
        
        # API provider selection group
        provider_group = self.create_group_box("AI Provider Selection")
        provider_layout = QFormLayout()
        provider_layout.setSpacing(10)
        
        # Provider selection
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["OpenAI", "Anthropic", "Google", "DeepSeek"])
        
        # Set provider based on config
        provider_index = {
            "openai": 0,
            "anthropic": 1,
            "google": 2,
            "deepseek": 3
        }.get(self.ai_processor.provider.lower(), 0)
        self.provider_combo.setCurrentIndex(provider_index)
        
        # Connect provider change signal
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        
        provider_layout.addRow("AI Provider:", self.provider_combo)
        
        # Models - This will be populated when provider changes
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        provider_layout.addRow("AI Model:", self.model_combo)
        
        provider_group.layout().addLayout(provider_layout)
        layout.addWidget(provider_group)
        
        # API configuration group
        self.api_config_group = self.create_group_box("API Configuration")
        api_stacked_layout = QVBoxLayout()
        
        # Create API key inputs for each provider
        self.provider_api_keys = {}
        self.provider_base_urls = {}
        
        providers = ["openai", "anthropic", "google", "deepseek"]
        
        for provider in providers:
            provider_widget = QWidget()
            provider_layout = QFormLayout(provider_widget)
            provider_layout.setSpacing(10)
            
            # Get provider config
            prov_config = self.ai_processor.config.get("providers", {}).get(provider, {})
            
            # API key input with show/hide option
            api_key_edit = QLineEdit()
            api_key_edit.setPlaceholderText(f"Enter your {provider.capitalize()} API key")
            api_key_edit.setEchoMode(QLineEdit.Password)
            api_key_edit.setText(prov_config.get("api_key", ""))
            
            # Show key checkbox
            show_key_layout = QHBoxLayout()
            show_key_checkbox = QCheckBox("Show API Key")
            show_key_checkbox.stateChanged.connect(lambda state, edit=api_key_edit: self.toggle_api_key_visibility_for(edit, state))
            show_key_layout.addWidget(api_key_edit)
            show_key_layout.addWidget(show_key_checkbox)
            
            provider_layout.addRow("API Key:", show_key_layout)
            
            # Base URL (optional) - for custom endpoints
            base_url_edit = QLineEdit()
            base_url_edit.setPlaceholderText(f"Optional: Custom {provider.capitalize()} API endpoint URL")
            base_url_edit.setText(prov_config.get("base_url", ""))
            
            provider_layout.addRow("Base URL:", base_url_edit)
            
            # Store references
            self.provider_api_keys[provider] = api_key_edit
            self.provider_base_urls[provider] = base_url_edit
            
            # Add the provider widget to the layout but hide it initially
            provider_widget.setVisible(False)
            api_stacked_layout.addWidget(provider_widget)
            
            # Store reference to the widget
            setattr(self, f"{provider}_widget", provider_widget)
        
        # Test connection button
        test_button = QPushButton("Test Connection")
        test_button.setMinimumSize(150, 40)
        test_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #006CBE;
            }
            QPushButton:pressed {
                background-color: #005AA0;
            }
        """)
        test_button.clicked.connect(self.test_api_connection)
        
        test_layout = QHBoxLayout()
        test_layout.addStretch()
        test_layout.addWidget(test_button)
        api_stacked_layout.addLayout(test_layout)
        
        self.api_config_group.layout().addLayout(api_stacked_layout)
        layout.addWidget(self.api_config_group)
        
        # Show the current provider's settings
        self.show_current_provider_settings()
        
        # Advanced settings
        advanced_group = self.create_group_box("Advanced Settings")
        advanced_layout = QFormLayout()
        advanced_layout.setSpacing(10)
        
        self.temperature_slider = QSlider(Qt.Horizontal)
        self.temperature_slider.setMinimum(0)
        self.temperature_slider.setMaximum(100)
        self.temperature_slider.setValue(int(self.ai_processor.temperature * 100))  # Config from AI processor
        self.temperature_slider.setTickPosition(QSlider.TicksBelow)
        self.temperature_slider.setTickInterval(10)
        self.temperature_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #E1E1E1;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078D4;
                border: none;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::sub-page:horizontal {
                background: #50ABF1;
                border-radius: 4px;
            }
        """)
        
        self.temperature_value_label = QLabel(f"Temperature: {self.temperature_slider.value()/100:.2f}")
        self.temperature_slider.valueChanged.connect(self.update_temperature_label)
        
        temp_slider_layout = QHBoxLayout()
        temp_slider_layout.addWidget(self.temperature_slider)
        temp_slider_layout.addWidget(self.temperature_value_label)
        
        advanced_layout.addRow("AI Temperature:", temp_slider_layout)
        
        # Request timeout
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setMinimum(5)
        self.timeout_spin.setMaximum(120)
        self.timeout_spin.setValue(self.ai_processor.timeout)  # Config from AI processor
        self.timeout_spin.setSuffix(" seconds")
        
        advanced_layout.addRow("Request Timeout:", self.timeout_spin)
        
        advanced_group.layout().addLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        # Help section
        help_group = self.create_group_box("Help & Information")
        help_layout = QVBoxLayout()
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMinimumHeight(300)  # Minimum yükseklik ayarı
        help_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Genişleme politikası
        help_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #E1E1E1;
                border-radius: 8px;
                background-color: #F9F9F9;
                font-size: 9.5pt;
            }
        """)
        help_text.setHtml("""
            <h3>AI API Settings</h3>
            <p>To use the AI filtering functionality, you need to provide your API key for your chosen provider. 
            These keys are used to authenticate your requests to the AI service.</p>
            <br>
            <h3>Supported Providers:</h3>
            <ul>
                <li><strong>OpenAI</strong>: Provider of GPT models (GPT-3.5, GPT-4). These models offer excellent 
                performance for academic paper filtering. <a href='https://platform.openai.com/signup'>Get API key</a></li>
                <li><strong>Anthropic</strong>: Provider of Claude models (Claude 2, Claude Instant). Claude models are 
                particularly good at understanding complex academic texts. <a href='https://console.anthropic.com/'>Get API key</a></li>
                <li><strong>Google</strong>: Provider of Gemini models. These models offer strong performance and are tightly 
                integrated with Google's ecosystem. <a href='https://ai.google.dev/'>Get API key</a></li>
                <li><strong>DeepSeek</strong>: Provider of alternative AI models with competitive pricing. 
                <a href='https://platform.deepseek.com/'>Get API key</a></li>
            </ul>
            <br>
            <h3>Model Selection:</h3>
            <p>Choose the appropriate model based on your needs:</p>
            <ul>
                <li><strong>More powerful models</strong> (like GPT-4, Claude 2, Gemini Pro) provide better accuracy but cost more.</li>
                <li><strong>Faster models</strong> (like GPT-3.5 Turbo, Claude Instant) are more economical and process papers more quickly.</li>
            </ul>
            <br>
            <h3>Temperature Setting:</h3>
            <p>Controls randomness in AI responses:</p>
            <ul>
                <li><strong>Low values (0.0-0.3)</strong>: More consistent scoring, recommended for academic filtering</li>
                <li><strong>Medium values (0.4-0.7)</strong>: Balanced approach</li>
                <li><strong>High values (0.8-1.0)</strong>: More creative responses, not recommended for filtering</li>
            </ul>
            <br>
            <h3>Advanced Settings:</h3>
            <ul>
                <li><strong>Custom Base URL</strong>: For using private deployments or proxies</li>
                <li><strong>Request Timeout</strong>: Maximum time allowed for AI to respond</li>
            </ul>
            <br>
            <h3>Configuration Storage:</h3>
            <p>All settings are saved in <code>config/API_Settings.json</code> file. Your API keys are stored on your local device only.</p>
            <br>
            <h3>Support:</h3>
            <p>For more information on AI providers and pricing, visit their respective websites.</p>
        """)
        
        help_layout.addWidget(help_text)
        help_group.layout().addLayout(help_layout)
        layout.addWidget(help_group)
        
        layout.addStretch()
        
        # Save settings button
        save_button = QPushButton("Save Settings")
        save_button.setMinimumSize(200, 50)
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                padding: 14px 30px;
            }
            QPushButton:hover {
                background-color: #006CBE;
            }
            QPushButton:pressed {
                background-color: #005AA0;
            }
        """)
        save_button.clicked.connect(self.save_api_settings)
        
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        save_layout.addWidget(save_button)
        layout.addLayout(save_layout)
        
        # Initialize models for the current provider
        self.update_model_combo()
        
    def show_current_provider_settings(self):
        """Show the settings for the current provider"""
        current_provider = self.ai_processor.provider
        providers = ["openai", "anthropic", "google", "deepseek"]
        
        for provider in providers:
            widget = getattr(self, f"{provider}_widget")
            widget.setVisible(provider == current_provider)
            
    def toggle_api_key_visibility_for(self, edit, state):
        """Toggle the visibility of the API key for a specific line edit"""
        if state == Qt.Checked:
            edit.setEchoMode(QLineEdit.Normal)
        else:
            edit.setEchoMode(QLineEdit.Password)
    
    def update_temperature_label(self):
        """Update the temperature label when slider value changes"""
        value = self.temperature_slider.value() / 100.0
        self.temperature_value_label.setText(f"Temperature: {value:.2f}")
    
    def save_api_settings(self):
        """Save API settings to config file"""
        # Update processor properties
        current_provider = self.ai_processor.provider
        
        # Save all provider API keys and URLs
        for provider, key_edit in self.provider_api_keys.items():
            provider_config = self.ai_processor.config.get("providers", {}).get(provider, {})
            provider_config["api_key"] = key_edit.text()
            provider_config["base_url"] = self.provider_base_urls[provider].text()
            
            # Make sure providers exist in config
            if "providers" not in self.ai_processor.config:
                self.ai_processor.config["providers"] = {}
            if provider not in self.ai_processor.config["providers"]:
                self.ai_processor.config["providers"][provider] = provider_config
        
        # Set active provider and its current values
        self.ai_processor.api_key = self.provider_api_keys[current_provider].text()
        self.ai_processor.base_url = self.provider_base_urls[current_provider].text()
        
        # Seçili modeli kaydet ve ayarla
        selected_model = self.model_combo.currentText()
        if selected_model:
            # Uygulamaya ayarla
            self.ai_processor.model = selected_model
            
            # Config'e kaydet - active_model olarak
            if "providers" in self.ai_processor.config and current_provider in self.ai_processor.config["providers"]:
                self.ai_processor.config["providers"][current_provider]["active_model"] = selected_model
                
            logger.info(f"Saving selected model: {selected_model} for provider: {current_provider}")
            
        # Diğer ayarları kaydet
        self.ai_processor.temperature = self.temperature_slider.value() / 100.0
        self.ai_processor.timeout = self.timeout_spin.value()
        
        # Doğrudan AIProcessor'un config özelliğini güncelleyelim
        if "providers" not in self.ai_processor.config:
            self.ai_processor.config["providers"] = {}
            
        for provider, key_edit in self.provider_api_keys.items():
            if provider not in self.ai_processor.config["providers"]:
                self.ai_processor.config["providers"][provider] = {}
                
            self.ai_processor.config["providers"][provider]["api_key"] = key_edit.text()
            self.ai_processor.config["providers"][provider]["base_url"] = self.provider_base_urls[provider].text()
            
        # Aktif sağlayıcıyı kaydet
        self.ai_processor.config["activeProvider"] = current_provider
        
        # Log current values before saving
        logger.debug(f"API key for {current_provider}: {self.ai_processor.api_key}")
        logger.debug(f"Selected model: {self.ai_processor.model}")
        logger.debug(f"All config before saving: {self.ai_processor.config}")
        
        # Save to config file via AIProcessor
        result = self.ai_processor.save_config()
        
        # DOĞRUDAN dosyaya yazma denemesi - Yedek çözüm
        try:
            # Ensure config directory exists
            config_dir = os.path.dirname(self.ai_processor.config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            # Write directly to the file
            with open(self.ai_processor.config_file, 'w') as f:
                json.dump(self.ai_processor.config, f, indent=4)
                
            logger.info(f"Direct write to config file: {self.ai_processor.config_file}")
            
            # Read back to verify
            with open(self.ai_processor.config_file, 'r') as f:
                saved_config = json.load(f)
            logger.debug(f"Config after direct write: {saved_config}")
            
            if result:
                QMessageBox.information(self, "Settings Saved", "API settings have been saved successfully.")
                self.status_label.setText("API settings saved")
            else:
                QMessageBox.warning(self, "Save Failed", "AIProcessor.save_config failed but direct write succeeded.")
                self.status_label.setText("API settings saved via direct write")
        except Exception as e:
            logger.error(f"Error during direct write: {str(e)}")
            
            if result:
                QMessageBox.information(self, "Settings Saved", "API settings have been saved successfully.")
                self.status_label.setText("API settings saved")
            else:
                QMessageBox.critical(self, "Save Failed", f"Failed to save API settings: {str(e)}")
                self.status_label.setText("Failed to save API settings")
    
    def test_api_connection(self):
        """Test the connection to the API"""
        # Update processor with current form values
        current_provider = self.ai_processor.provider
        api_key = self.provider_api_keys[current_provider].text()
        base_url = self.provider_base_urls[current_provider].text()
        
        self.ai_processor.api_key = api_key
        self.ai_processor.base_url = base_url
        self.ai_processor.model = self.model_combo.currentText()
        
        if not self.ai_processor.api_key:
            QMessageBox.warning(self, "Missing API Key", "Please enter your API key first.")
            return
            
        # Güncel ayarları önce kaydet
        self.save_api_settings()
        
        # Doğrudan config dosyasına da yazalım
        try:
            # Ensure config directory exists
            config_dir = os.path.dirname(self.ai_processor.config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            # Değişikliği doğrudan config'e uygulayalım
            if "providers" not in self.ai_processor.config:
                self.ai_processor.config["providers"] = {}
                
            if current_provider not in self.ai_processor.config["providers"]:
                self.ai_processor.config["providers"][current_provider] = {}
                
            # API anahtarını doğrudan güncelle
            self.ai_processor.config["providers"][current_provider]["api_key"] = api_key
            self.ai_processor.config["providers"][current_provider]["base_url"] = base_url
            
            # Write directly to the file
            with open(self.ai_processor.config_file, 'w') as f:
                json.dump(self.ai_processor.config, f, indent=4)
                
            logger.info(f"API key updated in config file: {api_key[:5]}... for {current_provider}")
        except Exception as e:
            logger.error(f"Error updating config file directly: {str(e)}")
        
        try:
            self.status_label.setText(f"Testing {self.ai_processor.provider.capitalize()} API connection...")
            QApplication.processEvents()
            
            # Test connection
            result = self.ai_processor.test_connection()
            
            if result:
                QMessageBox.information(self, "Connection Successful", 
                                        f"Successfully connected to {self.ai_processor.provider.capitalize()} API!")
                self.status_label.setText(f"{self.ai_processor.provider.capitalize()} API connection successful")
            else:
                QMessageBox.critical(self, "Connection Failed", 
                                     f"Could not connect to {self.ai_processor.provider.capitalize()} API. Please check your API key and try again.")
                self.status_label.setText(f"{self.ai_processor.provider.capitalize()} API connection failed")
        
        except Exception as e:
            logger.exception("API test failed")
            QMessageBox.critical(self, "Connection Error", f"Error testing API connection:\n{str(e)}")
            self.status_label.setText("API connection error")
    
    def show_setup_dialog(self):
        """Show the setup dialog"""
        setup_dialog = SetupDialog(self)
        setup_dialog.setup_completed.connect(self.apply_setup_config)
        
        # Show the dialog - setup dialog should always be displayed
        result = setup_dialog.exec_()
        
        # Handle dialog result
        if result == QDialog.Accepted:
            self.setup_completed = True
        
        # Note: We're not storing setup_completed in settings anymore
        # as we want setup dialog to appear every time the app starts
    
    def apply_setup_config(self, config):
        """Apply the configuration from the setup dialog"""
        # Get values from config
        excel_file = config.get("excel_file", "")
        column_mapping = config.get("column_mapping", {})
        
        # Apply Excel file path
        if excel_file:
            self.input_file_edit.setText(excel_file)
            # Only load columns from Excel but don't update the dropdowns anymore
            self.load_excel_columns(excel_file)
        
        # Apply column mappings to labels instead of combos
        self.update_column_mapping(column_mapping)
        
        # Update start button state
        self.update_start_button_state()
        
        # Ayarları kaydetmiyoruz, böylece her seferinde sıfırdan başlayacak
        
        # Log the applied configuration
        self.log_message(f"Applied configuration from setup: Excel file '{excel_file}' with columns {column_mapping}")
    
    def load_excel_columns(self, file_path):
        """Load Excel columns without updating the UI"""
        try:
            # Load Excel file and get columns
            columns = self.excel_processor.get_columns(file_path)
            
            # QLineEdit nesneleri için sadece tooltip güncelleme yeter
            column_list = ", ".join(columns)
            self.title_display.setToolTip(f"Mevcut sütunlar: {column_list}")
            self.abstract_display.setToolTip(f"Mevcut sütunlar: {column_list}")
            self.keywords_display.setToolTip(f"Mevcut sütunlar: {column_list}")
            self.categories_display.setToolTip(f"Mevcut sütunlar: {column_list}")
            
            self.log_message(f"Loaded columns from Excel file: {file_path}")
        except Exception as e:
            self.log_message(f"Error loading Excel columns: {str(e)}", level=logging.ERROR)

    def on_provider_changed(self, index):
        """Handle provider selection change"""
        provider_map = {
            0: "openai",
            1: "anthropic",
            2: "google", 
            3: "deepseek"
        }
        
        # Mevcut modeli ve provider'ı sakla
        old_provider = self.ai_processor.provider
        old_model = self.ai_processor.model
        
        # Update the provider in the processor
        self.ai_processor.provider = provider_map.get(index, "openai")
        
        # Anthropic sağlayıcısı seçildiyse ve SDK varsa güncel modelleri çek
        if self.ai_processor.provider == "anthropic":
            try:
                # SDK modellerini çekmeyi AI processor üzerinden dene
                if hasattr(self.ai_processor, 'fetch_anthropic_models'):
                    self.ai_processor.fetch_anthropic_models()
            except Exception as e:
                logger.warning(f"Error fetching Anthropic models after provider change: {str(e)}")
        
        # Show the current provider's settings
        self.show_current_provider_settings()
        
        # Update the models dropdown
        self.update_model_combo()
        
        # Değişiklik sonrası API anahtarını ve model bilgilerini doğrudan yükleme
        current_provider = self.ai_processor.provider
        new_model = None
        
        if "providers" in self.ai_processor.config and current_provider in self.ai_processor.config["providers"]:
            prov_config = self.ai_processor.config["providers"][current_provider]
            self.ai_processor.api_key = prov_config.get("api_key", "")
            self.ai_processor.base_url = prov_config.get("base_url", "")
            
            # Aktif modele göre seç
            active_model = prov_config.get("active_model", "")
            self.ai_processor.model = active_model
            new_model = active_model
            
            # Loglama ekle
            logger.info(f"Provider changed to {current_provider}, active model set to: {active_model}")
            
            # Model kısaltmasını al
            model_abbr = self.get_model_abbreviation()
            logger.info(f"Current model abbreviation: {model_abbr}")
        
        # Dosya yolunu güncellemek için giriş dosyasının var olup olmadığını kontrol et
        input_file = self.input_file_edit.text()
        if not input_file:
            logger.info("Input file not set, skipping output file update")
            return
            
        input_path = Path(input_file)
        
        # Eğer provider değiştiyse ve output dosyası belirlenmişse, dosya adını güncelle
        if old_provider != current_provider and self.output_file_edit.text():
            try:
                # Yeni model kısaltmasını al
                model_abbr = self.get_model_abbreviation()
                
                # Mevcut dosyayı analiz et
                file_path = Path(self.output_file_edit.text())
                file_dir = file_path.parent
                file_name = file_path.stem
                
                # "_BibAI_" ile bölünmüş kısımları al
                parts = file_name.split("_BibAI_")
                
                # Yeni dosya adı oluştur
                if len(parts) > 1:
                    # Eğer daha önce _BibAI_ formatında kaydedilmişse, sadece model kısmını güncelle
                    new_filename = f"{parts[0]}_BibAI_{model_abbr}.xlsx"
                else:
                    # Değilse mevcut dosya adına model ekle
                    new_filename = f"{file_name}_BibAI_{model_abbr}.xlsx"
                
                # Yeni dosya yolunu oluştur
                new_file_path = file_dir / new_filename
                
                # Arayüzü güncelle
                self.output_file_edit.setText(str(new_file_path))
                self.output_info_label.setText(f"Output file updated for provider: {current_provider} and model: {new_model}")
                logger.info(f"Output file path updated to: {new_file_path} for new provider")
            except Exception as e:
                logger.error(f"Error updating output file path after provider change: {str(e)}")
        else:
            # Varsayılan dosya adını oluştur (hem çıktı dosyası boş olduğunda hem de provider değişmediğinde)
            default_name = f"{input_path.stem}_BibAI_{model_abbr}.xlsx"
            output_file = str(input_path.parent / default_name)
            
            # Metin kutusunu güncelle
            self.output_file_edit.setText(output_file)
            self.output_info_label.setText(f"Output file updated for provider: {current_provider} and model: {new_model}")
            logger.info(f"Output filename set to: {output_file} for model {new_model}")

    def on_model_changed(self, model_text):
        """Model combo kutusunda değişiklik olduğunda çağrılır"""
        if not model_text:
            return
            
        # Modeli processor'da güncelle
        self.ai_processor.model = model_text
        
        # Log for debugging
        logger.info(f"Model changed to: {model_text}")
        
        # Mevcut sağlayıcıyı al
        current_provider = self.ai_processor.provider
        
        # Config'de active_model'i güncelle
        if "providers" in self.ai_processor.config and current_provider in self.ai_processor.config["providers"]:
            self.ai_processor.config["providers"][current_provider]["active_model"] = model_text
        
        # Önce model kısaltmasını al
        model_abbr = self.get_model_abbreviation()
        logger.info(f"Current model abbreviation: {model_abbr}")
        
        # Eğer daha önce bir dosya adı girilmişse, model değişikliğine göre güncelle
        current_output_file = self.output_file_edit.text()
        
        # Dosya yolunu güncellemek için giriş dosyasının var olup olmadığını kontrol et
        input_file = self.input_file_edit.text()
        if not input_file:
            logger.info("Input file not set, skipping output file update")
            return
            
        input_path = Path(input_file)
        
        if current_output_file:
            try:
                # Mevcut dosya yolunu analiz et
                file_path = Path(current_output_file)
                file_dir = file_path.parent
                file_name = file_path.stem
                
                # "_BibAI_" ile bölünmüş kısımları al
                parts = file_name.split("_BibAI_")
                
                # Yeni dosya adı oluştur
                if len(parts) > 1:
                    # Eğer daha önce _BibAI_ formatında kaydedilmişse, sadece model kısmını güncelle
                    new_filename = f"{parts[0]}_BibAI_{model_abbr}.xlsx"
                else:
                    # Değilse mevcut dosya adına model ekle
                    new_filename = f"{file_name}_BibAI_{model_abbr}.xlsx"
                
                # Yeni dosya yolunu oluştur
                new_file_path = file_dir / new_filename
                
                # Arayüzü güncelle
                self.output_file_edit.setText(str(new_file_path))
                self.output_info_label.setText(f"Output file updated for model: {model_text}")
                logger.info(f"Output file path updated to: {new_file_path}")
            except Exception as e:
                logger.error(f"Error updating output file path: {str(e)}")
        else:
            # Varsayılan dosya adını oluştur
            default_name = f"{input_path.stem}_BibAI_{model_abbr}.xlsx"
            output_file = str(input_path.parent / default_name)
            
            # Metin kutusunu güncelle
            self.output_file_edit.setText(output_file)
            self.output_info_label.setText(f"Output file updated for model: {model_text}")
            logger.info(f"Output filename set to: {output_file} for model {model_text}")

    def update_model_combo(self):
        """Update the model combo box based on selected provider"""
        # Clear existing items
        self.model_combo.clear()
        
        # Get models for the current provider
        provider_config = self.ai_processor.config.get("providers", {}).get(self.ai_processor.provider, {})
        models = provider_config.get("models", [])
        active_model = provider_config.get("active_model", "")
        
        # Log for debugging
        logger.info(f"Active provider: {self.ai_processor.provider}, available models: {models}")
        logger.info(f"Active model from config: {active_model}")
        
        # Add models to combo box
        self.model_combo.addItems(models)
        
        # Set current model if it exists in the list
        if active_model and active_model in models:
            logger.info(f"Setting current model to: {active_model}")
            self.model_combo.setCurrentText(active_model)
            # Processor'ı da güncelle
            self.ai_processor.model = active_model
    
    def update_column_mapping(self, column_mapping):
        """Update the column mapping from setup dialog"""
        if "title" in column_mapping:
            self.title_display.setText(column_mapping["title"])
            self.title_display.setStyleSheet("color: #202020; font-weight: bold;")
        
        if "abstract" in column_mapping:
            self.abstract_display.setText(column_mapping["abstract"])
            self.abstract_display.setStyleSheet("color: #202020; font-weight: bold;")
        
        if "keywords" in column_mapping:
            self.keywords_display.setText(column_mapping["keywords"])
            self.keywords_display.setStyleSheet("color: #202020; font-weight: bold;")
            
        if "categories" in column_mapping:
            self.categories_display.setText(column_mapping["categories"])
            self.categories_display.setStyleSheet("color: #202020; font-weight: bold;")
        
        # Update settings
        settings = {
            "excel_file": column_mapping.get("excel_file", ""),
            "title_column": self.title_display.text(),
            "abstract_column": self.abstract_display.text(),
            "keywords_column": self.keywords_display.text(),
            "categories_column": self.categories_display.text() if "categories" in column_mapping else ""
        }
        
        # Save settings
        self.settings.setValue("column_mapping", settings)
        
        # Update start button state
        self.update_start_button_state() 

    def get_default_prompt_template(self):
        """Default prompt template for relevance analysis"""
        return """
         You are an advanced AI specialized in evaluating the relevance of scientific papers to a specified topic. Your task is to analyze the provided paper information (title, abstract, keywords) and output a relevance score using a 7-point semantic differential scale.

         INPUTS:
         TOPIC: {TOPIC}
         PAPER TITLE: {TITLE}
         PAPER ABSTRACT: {ABSTRACT}
         KEYWORDS: {KEYWORDS}
         CATEGORIES: {CATEGORIES}

         ANALYSIS INSTRUCTIONS:
         Term Matching:
         - Identify key terms, synonyms, and relevant concepts related to the provided topic.
         - Assess the frequency and contextual usage of these terms within the paper's title, abstract, and keywords.

         Contextual Alignment:
         - Evaluate both direct and indirect connections between the paper content and the provided topic.
         - Even superficial mentions or indirect references should influence the relevance score.

         Depth and Significance:
         - Evaluate the extent to which the paper directly or indirectly focuses on the specified topic.
         - The paper does not need to be centered exclusively around the topic; partial or secondary references also indicate relevance.

         7-POINT SCORING SCALE:
         - 1: Not relevant at all - No meaningful connection to the topic
         - 2: Very slightly relevant - Only tangential or vague connections
         - 3: Slightly relevant - Few or minimal connections to the topic
         - 4: Somewhat relevant - Some indirect but meaningful connections
         - 5: Moderately relevant - Clear connections to the topic
         - 6: Very relevant - Strong relevance with significant topic-related content
         - 7: Extremely relevant - Direct focus on the topic with comprehensive coverage

         IMPORTANT NOTES:
         - Base your evaluation on the frequency and contextual overlap of keywords between the topic and paper information.
         - Surface-level relationships are sufficient for your analysis.
         - Focus on semantic similarity rather than requiring exact keyword matches.

         OUTPUT FORMAT:
         Only return a single integer value between 1 and 7 representing the relevance score.
         DO NOT include any additional text, explanations, or justifications.
         Example output: 6
         """

    def start_analysis_with_prompt(self, input_file, output_file, title_column, abstract_column, 
                               keywords_column, topic, threshold, max_records, 
                                ai_processor, prompt, iterations=1):
        """Start the analysis with the confirmed prompt"""
        self.log_message(f"Starting analysis with topic: {topic}")
        self.log_message(f"Using threshold: {threshold}")
        self.log_message(f"Running {iterations} iterations for each record")
        
        # Initialize the worker thread
        params = {
            'input_file': input_file,
            'output_file': output_file,
            'title_col': title_column,
            'abstract_col': abstract_column,
            'keywords_col': keywords_column,
            'topic': topic,
            'threshold': threshold,
            'max_records': max_records,
            'prompt_template': prompt,
            'provider': ai_processor.provider,
            'api_key': ai_processor.api_key,
            'model': ai_processor.model,
            'base_url': ai_processor.base_url,
            'temperature': ai_processor.temperature,
            'iterations': iterations  # Tekrar sayısını worker thread'e ilet
        }
        
        self.worker_thread = ProcessingThread(params)
        
        # Connect signals
        self.worker_thread.progress_update.connect(self.log_message)
        self.worker_thread.progress_percentage.connect(self.update_progress)
        self.worker_thread.processing_complete.connect(self.on_processing_complete)
        self.worker_thread.error_occurred.connect(self.on_error)
        self.worker_thread.file_processed.connect(self.on_file_processed)
        
        # Update UI state
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.start_button.setEnabled(False)
        self.stop_button.setVisible(True)
        
        # Clear previous results
        self.log_text.clear()
        
        # Start processing
        self.worker_thread.start()