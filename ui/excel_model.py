#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor

class ExcelTableModel(QAbstractTableModel):
    """Model for displaying Excel data in a QTableView"""
    
    def __init__(self, data=None, custom_headers=None):
        super().__init__()
        
        # Initialize with custom headers if provided
        if custom_headers:
            self.headers = custom_headers
        else:
            self.headers = []
            
        self.data_values = []
        self.relevant_rows = set()  # İlgili satırları takip etmek için küme
        
        # If data is a DataFrame
        if hasattr(data, 'columns') and hasattr(data, 'values'):
            self.set_data(data)
        # If data is a list of dictionaries
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            self.set_dict_data(data)
        # If data is a list
        elif isinstance(data, list):
            self.data_values = data
    
    def set_data(self, data):
        """Set the data from a pandas DataFrame"""
        # Get headers if not already set
        if not self.headers:
            self.headers = list(data.columns)
        
        # Convert DataFrame to list of lists
        self.data_values = data.values.tolist()
        
        # Notify views that data has changed
        self.layoutChanged.emit()
    
    def set_dict_data(self, dict_list):
        """Set data from a list of dictionaries"""
        if not dict_list:
            return
            
        # Get headers from first dict if not already set
        if not self.headers and dict_list:
            self.headers = list(dict_list[0].keys())
        
        # Convert list of dicts to list of lists
        self.data_values = []
        for item in dict_list:
            row = [item.get(header, "") for header in self.headers]
            self.data_values.append(row)
            
        # Notify views that data has changed
        self.layoutChanged.emit()
    
    def append_row(self, row_dict):
        """Append a new row to the model from a dictionary"""
        # If this is the first row and headers aren't set yet, use the dict keys
        if not self.headers and row_dict:
            self.headers = list(row_dict.keys())
        
        # Convert dict to a list using header order
        new_row = [row_dict.get(header, "") for header in self.headers]
        
        # Insert row
        row_index = len(self.data_values)
        self.beginInsertRows(QModelIndex(), row_index, row_index)
        self.data_values.append(new_row)
        self.endInsertRows()
        
        return True
    
    def rowCount(self, parent=QModelIndex()):
        """Return the number of rows"""
        return len(self.data_values)
    
    def columnCount(self, parent=QModelIndex()):
        """Return the number of columns"""
        return len(self.headers)
    
    def data(self, index, role=Qt.DisplayRole):
        """Return the data at the given index"""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
            
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if 0 <= row < len(self.data_values) and 0 <= col < len(self.headers):
                value = self.data_values[row][col]
                
                # Handle different data types
                if isinstance(value, float) and value != value:
                    # Handle NaN values
                    return ""
                
                # Result sütunu için özel gösterim ekleyelim
                if self.headers[col] == "Result":
                    if value == True or value == "True" or value == "RELEVANT" or value == "✓":
                        return "✓"  # Yeşil tik için metin
                    elif value == False or value == "False" or value == "NOT RELEVANT" or value == "✗":
                        return "✗"  # Kırmızı çarpı için metin
                
                return str(value)
        
        # Renk için
        elif role == Qt.ForegroundRole:
            if 0 <= row < len(self.data_values) and 0 <= col < len(self.headers):
                # Sadece Result sütunu için renk uygula
                if self.headers[col] == "Result":
                    value = self.data_values[row][col]
                    if value == True or value == "True" or value == "RELEVANT" or value == "✓":
                        return QColor("#0F9D58")  # Yeşil renk
                    elif value == False or value == "False" or value == "NOT RELEVANT" or value == "✗":
                        return QColor("#DB4437")  # Kırmızı renk
        
        # Text alignment role
        elif role == Qt.TextAlignmentRole:
            # Score ve Result sütunlarını ortaya hizala
            if 0 <= col < len(self.headers):
                if self.headers[col] in ["Score", "Result"]:
                    return Qt.AlignCenter
        
        # For other roles or invalid indices
        return None
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return the header data"""
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal and section < len(self.headers):
                return self.headers[section]
            elif orientation == Qt.Vertical:
                return str(section + 1)
        
        return None
    
    def flags(self, index):
        """Return the item flags"""
        if not index.isValid():
            return Qt.NoItemFlags
        
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable 
    
    def set_row_relevant(self, row_index, is_relevant):
        """Satırın ilgili (relevant) olup olmadığını ayarlar"""
        if is_relevant:
            self.relevant_rows.add(row_index)
        elif row_index in self.relevant_rows:
            self.relevant_rows.remove(row_index)
        
        # Görsel güncellemeyi tetikle
        self.dataChanged.emit(
            self.index(row_index, 0),
            self.index(row_index, self.columnCount() - 1)
        ) 