#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QGridLayout, QTableWidget, 
    QTableWidgetItem, QGroupBox, QLineEdit, QFormLayout,
    QMessageBox, QWidget, QHeaderView, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QColor

import os
import pandas as pd
import logging

from utils.excel_processor import ExcelProcessor

logger = logging.getLogger(__name__)

class SetupDialog(QDialog):
    """Initial setup dialog for Excel file selection and column mapping"""
    
    # Setup completed signal with config parameters
    setup_completed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Initial Setup")
        self.setWindowIcon(QIcon("resources/icon_windows.png"))
        self.setMinimumSize(800, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        
        # Initialize variables
        self.excel_file = ""
        self.excel_processor = ExcelProcessor()
        self.df = None  # Will hold the dataframe for preview
        self.columns = []  # Will hold column names
        self.mapped_columns = {}  # Will hold the column mapping
        
        # Define colors (matching the app's color scheme)
        self.primary_color = "#0078D4"    # Windows blue (darker tone)
        self.background_color = "#F9F9F9" # Background
        self.text_color = "#202020"       # Main text
        self.secondary_text = "#5F6368"   # Secondary text
        self.card_color = "#FFFFFF"       # Card background
        self.divider_color = "#E1E1E1"    # Dividers
        
        # Initialize UI
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Custom checkbox style using resources
        self.setStyleSheet("""
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            QCheckBox::indicator:unchecked {
                image: url(resources/unchecked.png);
            }
            QCheckBox::indicator:checked {
                image: url(resources/check.png);
            }
        """)
        
        # Header
        header_label = QLabel("Initial Setup")
        header_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        header_label.setStyleSheet(f"color: {self.primary_color};")
        layout.addWidget(header_label)
        
        # Instruction text
        instruction_label = QLabel("Please select your Excel file and map the columns.")
        instruction_label.setStyleSheet(f"color: {self.secondary_text}; font-size: 12pt;")
        layout.addWidget(instruction_label)
        
        # Excel file selection
        file_layout = QFormLayout()
        file_layout.setSpacing(10)
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select an Excel file containing academic publication data")
        self.file_path_edit.setReadOnly(True)
        
        browse_button = QPushButton("Browse...")
        browse_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.primary_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #006CBE;
            }}
            QPushButton:pressed {{
                background-color: #005AA0;
            }}
        """)
        browse_button.clicked.connect(self.browse_excel_file)
        
        file_layout_horizontal = QHBoxLayout()
        file_layout_horizontal.addWidget(self.file_path_edit)
        file_layout_horizontal.addWidget(browse_button)
        
        file_layout.addRow("Excel File:", file_layout_horizontal)
        layout.addLayout(file_layout)
        
        # Column mapping
        mapping_group = QGroupBox("Column Mapping")
        mapping_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {self.divider_color};
                border-radius: 8px;
                margin-top: 1.5ex;
                padding: 10px;
                background-color: {self.card_color};
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {self.primary_color};
                font-weight: 600;
                font-size: 10pt;
            }}
        """)
        
        mapping_layout = QFormLayout()
        mapping_layout.setSpacing(10)
        
        # Column combo boxes
        self.title_combo = QComboBox()
        self.title_combo.setMinimumWidth(250)
        self.title_combo.currentIndexChanged.connect(self.update_preview)
        
        self.abstract_combo = QComboBox()
        self.abstract_combo.setMinimumWidth(250)
        self.abstract_combo.currentIndexChanged.connect(self.update_preview)
        
        self.keywords_combo = QComboBox()
        self.keywords_combo.setMinimumWidth(250)
        self.keywords_combo.currentIndexChanged.connect(self.update_preview)
        
        self.categories_combo = QComboBox()
        self.categories_combo.setMinimumWidth(250)
        self.categories_combo.currentIndexChanged.connect(self.update_preview)
        
        # Add to mapping layout
        mapping_layout.addRow("Title:", self.title_combo)
        mapping_layout.addRow("Abstract:", self.abstract_combo)
        mapping_layout.addRow("Keywords:", self.keywords_combo)
        mapping_layout.addRow("Categories:", self.categories_combo)
        
        mapping_group.setLayout(mapping_layout)
        layout.addWidget(mapping_group)
        
        # Data preview
        preview_group = QGroupBox("Data Preview")
        preview_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {self.divider_color};
                border-radius: 8px;
                margin-top: 1.5ex;
                padding: 10px;
                background-color: {self.card_color};
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {self.primary_color};
                font-weight: 600;
                font-size: 10pt;
            }}
        """)
        
        preview_layout = QVBoxLayout()
        
        # Create a header label for preview section
        preview_header = QLabel("Preview")
        preview_header.setStyleSheet(f"""
            font-weight: bold;
            font-size: 14px;
            color: {self.primary_color};
            padding-bottom: 5px;
        """)
        preview_layout.addWidget(preview_header)
        
        # Table widget for preview - improved styling based on app.py
        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Make table read-only
        self.preview_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.preview_table.setSelectionMode(QTableWidget.SingleSelection)
        self.preview_table.setShowGrid(True)
        self.preview_table.setWordWrap(True)
        self.preview_table.verticalHeader().setVisible(False)  # Hide row numbers
        
        # Modern table styling
        self.preview_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {self.divider_color};
                border-radius: 4px;
                background-color: {self.card_color};
                gridline-color: {self.divider_color};
                selection-background-color: #E5F1FB;
                selection-color: {self.text_color};
            }}
            QTableWidget::item {{
                padding: 4px;
                border-bottom: 1px solid #F0F0F0;
            }}
            QTableWidget::item:alternate {{
                background-color: #F9F9F9;
            }}
            QHeaderView::section {{
                background-color: #323c4e;
                color: white;
                padding: 6px;
                border: none;
                font-weight: bold;
                font-size: 11px;
                border-right: 1px solid #3D4A61;
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
            QScrollBar:vertical {{
                border: none;
                background-color: #F2F2F2;
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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                border: none;
                background-color: #F2F2F2;
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
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
        """)
        
        # Create a container widget with border
        table_container = QWidget()
        table_container.setStyleSheet(f"""
            background-color: white;
            border: 1px solid {self.divider_color};
            border-radius: 8px;
        """)
        table_container_layout = QVBoxLayout(table_container)
        table_container_layout.setContentsMargins(1, 1, 1, 1)
        table_container_layout.addWidget(self.preview_table)
        
        preview_layout.addWidget(table_container)
        
        # Add shadow effect to the table container
        self.add_shadow_effect(table_container)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumSize(120, 40)
        self.cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #F2F2F2;
                color: {self.text_color};
                border: 1px solid {self.divider_color};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #E5E5E5;
            }}
            QPushButton:pressed {{
                background-color: #D9D9D9;
            }}
        """)
        self.cancel_button.clicked.connect(self.reject)
        
        self.continue_button = QPushButton("Continue")
        self.continue_button.setMinimumSize(120, 40)
        self.continue_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.primary_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #006CBE;
            }}
            QPushButton:pressed {{
                background-color: #005AA0;
            }}
            QPushButton:disabled {{
                background-color: #E1E1E1;
                color: #5F6368;
            }}
        """)
        self.continue_button.clicked.connect(self.finish_setup)
        self.continue_button.setEnabled(False)
        
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.continue_button)
        
        layout.addLayout(buttons_layout)
    
    def browse_excel_file(self):
        """Open file dialog to select Excel file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if file_path:
            self.excel_file = file_path
            self.file_path_edit.setText(file_path)
            self.load_excel_file(file_path)
    
    def load_excel_file(self, file_path):
        """Load Excel file and update column combos"""
        try:
            # Load Excel file and get columns
            self.columns = self.excel_processor.get_columns(file_path)
            
            # Load dataframe for preview
            self.df = self.excel_processor.load_excel_dataframe(file_path)
            
            # Update column combos
            for combo in [self.title_combo, self.abstract_combo, self.keywords_combo, self.categories_combo]:
                combo.clear()
                combo.addItems(["-- Select Column --"] + self.columns)
            
            # Try to automatically match column names
            self.auto_match_columns()
            
            # Update preview table
            self.update_preview()
            
            # Enable continue button if file is loaded
            self.update_continue_button()
            
        except Exception as e:
            logger.exception(f"Error loading Excel file: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load Excel file:\n{str(e)}")
    
    def auto_match_columns(self):
        """Try to automatically match columns based on common naming patterns"""
        title_patterns = ["title", "ti", "başlık", "name"]
        abstract_patterns = ["abstract", "ab", "özet", "summary", "description"]
        keyword_patterns = ["keyword", "key words", "keywords", "de", "anahtar", "keys"]
        category_patterns = ["category", "categories", "cat", "subject", "topic", "field", "wc", "web of science categories"]
        
        # Helper function to find best match
        def find_match(combo, patterns):
            best_idx = 0  # Default to "-- Select Column --"
            for i, col in enumerate(["-- Select Column --"] + self.columns):
                if any(pattern.lower() in col.lower() for pattern in patterns):
                    best_idx = i
                    break
            combo.setCurrentIndex(best_idx)
        
        # Find matches for each column type
        find_match(self.title_combo, title_patterns)
        find_match(self.abstract_combo, abstract_patterns)
        find_match(self.keywords_combo, keyword_patterns)
        find_match(self.categories_combo, category_patterns)
    
    def update_preview(self):
        """Update the preview table based on selected columns"""
        if self.df is None or len(self.df) == 0:
            return
        
        # Get selected columns
        selected_columns = []
        labels = []
        
        for combo, label in [
            (self.title_combo, "TI"),
            (self.abstract_combo, "AB"),
            (self.keywords_combo, "DE"),
            (self.categories_combo, "WC")
        ]:
            if combo.currentIndex() > 0:  # Skip "-- Select Column --"
                selected_columns.append(combo.currentText())
                labels.append(label)
        
        if not selected_columns:
            return
        
        # Set up table
        self.preview_table.setRowCount(min(10, len(self.df)))  # Show max 10 rows
        self.preview_table.setColumnCount(len(selected_columns))
        self.preview_table.setHorizontalHeaderLabels(labels)
        
        # Set row height
        for row in range(self.preview_table.rowCount()):
            self.preview_table.setRowHeight(row, 40)  # Fixed row height for better appearance
        
        # Configure column widths
        header = self.preview_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)  # All columns stretch by default
        
        # Fill table with data
        for row in range(min(10, len(self.df))):
            for col, column_name in enumerate(selected_columns):
                value = self.df.iloc[row][column_name]
                
                # Convert various data types to string
                if pd.isna(value):
                    value = ""
                else:
                    value = str(value)
                
                # Limit length for display
                if len(value) > 100:
                    value = value[:97] + "..."
                
                item = QTableWidgetItem(value)
                item.setToolTip(value)  # Show full text on hover
                self.preview_table.setItem(row, col, item)
        
        # Store mapping
        self.update_column_mapping()
        
        # Update continue button state
        self.update_continue_button()
    
    def update_column_mapping(self):
        """Update the column mapping dictionary"""
        self.mapped_columns = {}
        
        if self.title_combo.currentIndex() > 0:
            self.mapped_columns["title"] = self.title_combo.currentText()
        
        if self.abstract_combo.currentIndex() > 0:
            self.mapped_columns["abstract"] = self.abstract_combo.currentText()
        
        if self.keywords_combo.currentIndex() > 0:
            self.mapped_columns["keywords"] = self.keywords_combo.currentText()
        
        if self.categories_combo.currentIndex() > 0:
            self.mapped_columns["categories"] = self.categories_combo.currentText()
    
    def update_continue_button(self):
        """Update the state of the continue button"""
        # Enable continue button if Excel file is loaded and any change was made
        # or if at least title and abstract are mapped
        has_file = bool(self.excel_file)
        has_title = self.title_combo.currentIndex() > 0
        has_abstract = self.abstract_combo.currentIndex() > 0
        
        if has_file:
            # Check if any combo has a selection (this means user made a choice)
            has_any_selection = (self.title_combo.currentIndex() > 0 or 
                                self.abstract_combo.currentIndex() > 0 or
                                self.keywords_combo.currentIndex() > 0 or
                                self.categories_combo.currentIndex() > 0)
            
            # Enable button if user made any selection with a valid file
            self.continue_button.setEnabled(has_any_selection)
        else:
            # If no file, disable button
            self.continue_button.setEnabled(False)
    
    def finish_setup(self):
        """Finish setup and emit the completed signal"""
        # Only validate that a file exists - any column mapping is acceptable
        if not self.excel_file:
            QMessageBox.warning(self, "Incomplete Setup", "Please select an Excel file.")
            return
        
        # At least one column should be mapped
        if not self.mapped_columns:
            QMessageBox.information(self, "Column Selection", "You haven't selected any columns to map. It's recommended to map at least Title and Abstract columns.")
            # Continue anyway - we won't block the user
        
        # Prepare config
        config = {
            "excel_file": self.excel_file,
            "column_mapping": self.mapped_columns
        }
        
        # Emit signal with config
        self.setup_completed.emit(config)
        
        # Close dialog
        self.accept()

    # Add shadow effect method if it doesn't exist
    def add_shadow_effect(self, widget, blur_radius=8, color=QColor(0, 0, 0, 25), x_offset=0, y_offset=2):
        """Add shadow effect to a widget"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur_radius)
        shadow.setColor(color)
        shadow.setOffset(x_offset, y_offset)
        widget.setGraphicsEffect(shadow) 