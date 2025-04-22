#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QWidget, QPlainTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QColor, QTextCharFormat, QTextCursor, QSyntaxHighlighter

class PromptHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for the prompt text"""
    
    def __init__(self, document, topic):
        super().__init__(document)
        self.topic = topic
        
        # Define formats for light theme 
        self.topic_format = QTextCharFormat()
        self.topic_format.setForeground(QColor("#0078D4"))  # Primary blue for topic
        self.topic_format.setFontWeight(QFont.Bold)
        
        self.header_format = QTextCharFormat()
        self.header_format.setForeground(QColor("#005A9E"))  # Darker blue for section headers
        self.header_format.setFontWeight(QFont.Bold)
        
        self.placeholder_format = QTextCharFormat()
        self.placeholder_format.setForeground(QColor("#107C10"))  # Success green for placeholders
        self.placeholder_format.setFontWeight(QFont.Bold)
        
        self.numeric_format = QTextCharFormat()
        self.numeric_format.setForeground(QColor("#D83B01"))  # Error red/orange for numbers
    
    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text"""
        # Highlight topic
        if self.topic:
            index = text.find(self.topic)
            while index >= 0:
                length = len(self.topic)
                self.setFormat(index, length, self.topic_format)
                index = text.find(self.topic, index + length)
        
        # Highlight headers (all caps words followed by colon)
        for header in ["TOPIC TO ANALYZE:", "PAPER INFORMATION:", "TITLE:", "ABSTRACT:", 
                      "KEYWORDS:", "CATEGORIES:", "ANALYSIS STEPS:", "SCORING GUIDE:", 
                      "IMPORTANT CONSIDERATIONS:", "RESPONSE FORMAT:"]:
            index = text.find(header)
            if index >= 0:
                self.setFormat(index, len(header), self.header_format)
        
        # Highlight placeholders {xxx}
        if "{" in text and "}" in text:
            start = text.find("{")
            while start >= 0:
                end = text.find("}", start)
                if end >= 0:
                    length = end - start + 1
                    self.setFormat(start, length, self.placeholder_format)
                    start = text.find("{", end)
                else:
                    break
        
        # Highlight numbers
        for i in range(len(text)):
            if text[i].isdigit() or text[i] == '.':
                # Check if it's part of a number
                if (i == 0 or not text[i-1].isalnum()) and (i+1 < len(text) and (text[i+1].isdigit() or text[i+1] == '.')):
                    j = i
                    while j < len(text) and (text[j].isdigit() or text[j] == '.'):
                        j += 1
                    self.setFormat(i, j-i, self.numeric_format)


class ConfirmAnalysisDialog(QDialog):
    """Dialog for confirming and editing the analysis prompt"""
    
    # Signal to emit the updated prompt
    prompt_confirmed = pyqtSignal(str)
    
    def __init__(self, topic, template_prompt, parent=None):
        super().__init__(parent)
        
        self.topic = topic
        self.template_prompt = template_prompt
        
        self.setWindowTitle("Confirm Analysis Prompt")
        self.setWindowIcon(QIcon("resources/icon_windows.png"))
        self.setMinimumSize(800, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        
        # Açık tema UI için
        self.setStyleSheet("""
            QDialog {
                background-color: #F9F9F9;
                color: #202020;
            }
            QLabel {
                color: #202020;
                font-size: 11pt;
            }
            QTextEdit {
                background-color: #FFFFFF;
                color: #202020;
                border: 1px solid #E1E1E1;
                border-radius: 6px;
                font-family: Consolas, "Courier New", monospace;
                font-size: 10pt;
                selection-background-color: #0078D4;
                selection-color: white;
            }
            QPushButton {
                background-color: #0078D4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: 600;
                min-width: 120px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #50ABF1;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
            QPlainTextEdit {
                background-color: #FFFFFF;
                color: #202020;
                border: 1px solid #E1E1E1;
                border-radius: 6px;
                font-family: Consolas, "Courier New", monospace;
                font-size: 10pt;
                selection-background-color: #0078D4;
                selection-color: white;
                padding: 8px;
            }
        """)
        
        # Initialize UI
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Instructions
        instruction_label = QLabel("Please review and edit the analysis prompt if necessary. The highlighted topic will be used for relevance scoring.")
        instruction_label.setWordWrap(True)
        layout.addWidget(instruction_label)
        
        # Topic section
        topic_layout = QHBoxLayout()
        topic_label = QLabel("Analysis Topic:")
        topic_label.setStyleSheet("font-weight: bold; color: #0078D4;")  # Ana temada kullanılan mavi
        topic_layout.addWidget(topic_label)
        
        topic_value = QLabel(self.topic)
        topic_value.setStyleSheet("color: #0078D4; font-weight: bold;")  # Ana temada kullanılan mavi
        topic_layout.addWidget(topic_value)
        topic_layout.addStretch()
        
        layout.addLayout(topic_layout)
        
        # Analysis Steps label
        steps_label = QLabel("Analysis Steps:")
        steps_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(steps_label)
        
        # Prompt editor
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlainText(self.template_prompt.replace("{TOPIC}", self.topic))
        
        # Set highlighter
        self.highlighter = PromptHighlighter(self.prompt_edit.document(), self.topic)
        
        # Açık tema için metin stili
        self.prompt_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #FFFFFF;
                color: #202020;
                border: 1px solid #E1E1E1;
                padding: 8px;
                border-radius: 6px;
                font-family: Consolas, "Courier New", monospace;
                font-size: 10pt;
                line-height: 1.5;
            }
        """)
        
        layout.addWidget(self.prompt_edit)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)
        
        buttons_layout.addStretch()
        
        self.start_button = QPushButton("Start Analysis")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #50ABF1;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        self.start_button.clicked.connect(self.confirm_prompt)
        buttons_layout.addWidget(self.start_button)
        
        layout.addLayout(buttons_layout)
    
    def confirm_prompt(self):
        """Confirm the prompt and emit signal with the updated text"""
        updated_prompt = self.prompt_edit.toPlainText()
        self.prompt_confirmed.emit(updated_prompt)
        self.accept() 