#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class ExcelProcessor:
    """Class for Excel file operations"""
    
    def __init__(self):
        """Initialize the Excel processor"""
        pass
    
    def get_columns(self, file_path):
        """Get column names from Excel file"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Excel file not found: {file_path}")
            
            # Dosya uzantısına göre uygun motoru belirle
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.xls':
                # Eski Excel formatı için engine='xlrd' kullan
                logger.info(f"Reading columns from .xls format with xlrd engine")
                df = pd.read_excel(file_path, nrows=1, engine='xlrd')
            elif file_ext == '.xlsx':
                # Modern Excel formatı için engine='openpyxl' kullan
                logger.info(f"Reading columns from .xlsx format with openpyxl engine")
                df = pd.read_excel(file_path, nrows=1, engine='openpyxl')
            else:
                # Diğer formatlar için varsayılan engine kullan
                logger.info(f"Reading columns with default engine for format: {file_ext}")
                df = pd.read_excel(file_path, nrows=1)
            
            # Return column names as list
            return list(df.columns)
        
        except Exception as e:
            logger.exception(f"Error getting columns from Excel file: {str(e)}")
            raise
    
    def load_excel_data(self, file_path):
        """Load data from Excel file into a list of dictionaries"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Excel file not found: {file_path}")
            
            # Dosya uzantısına göre uygun motoru belirle
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.xls':
                # Eski Excel formatı için engine='xlrd' kullan
                logger.info(f"Loading .xls format with xlrd engine")
                df = pd.read_excel(file_path, engine='xlrd')
            elif file_ext == '.xlsx':
                # Modern Excel formatı için engine='openpyxl' kullan
                logger.info(f"Loading .xlsx format with openpyxl engine")
                df = pd.read_excel(file_path, engine='openpyxl')
            else:
                # Diğer formatlar için varsayılan engine kullan
                logger.info(f"Loading with default engine for format: {file_ext}")
                df = pd.read_excel(file_path)
            
            # Convert DataFrame to a list of dictionaries
            data = df.to_dict('records')
            
            return data
        
        except Exception as e:
            logger.exception(f"Error loading Excel data: {str(e)}")
            raise
            
    def load_excel_dataframe(self, file_path):
        """Load data from Excel file as pandas DataFrame (for UI and preview)"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Excel file not found: {file_path}")
            
            # Dosya uzantısına göre uygun motoru belirle
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.xls':
                # Eski Excel formatı için engine='xlrd' kullan
                logger.info(f"Loading .xls format with xlrd engine")
                df = pd.read_excel(file_path, engine='xlrd')
            elif file_ext == '.xlsx':
                # Modern Excel formatı için engine='openpyxl' kullan
                logger.info(f"Loading .xlsx format with openpyxl engine")
                df = pd.read_excel(file_path, engine='openpyxl')
            else:
                # Diğer formatlar için varsayılan engine kullan
                logger.info(f"Loading with default engine for format: {file_ext}")
                df = pd.read_excel(file_path)
            
            return df
        
        except Exception as e:
            logger.exception(f"Error loading Excel DataFrame: {str(e)}")
            raise
    
    def save_excel_data(self, data, file_path, model_info=None):
        """
        Excel dosyasına veriyi kaydet
        
        Args:
            data (list): Kaydedilecek satırların listesi
            file_path (str): Excel dosyasının yolu
            model_info (dict, optional): AI model bilgileri
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            # Dosya yolunu al ve analiz et
            file_dir, file_name = os.path.split(file_path)
            file_base, file_ext = os.path.splitext(file_name)
            
            # Her zaman xlsx formatında kaydet
            if file_ext.lower() != '.xlsx':
                # Eğer uzantı xlsx değilse, xlsx olarak değiştir
                new_file_path = os.path.join(file_dir, file_base + '.xlsx')
                logger.info(f"Converting output format from {file_ext} to .xlsx")
                logger.info(f"New file path: {new_file_path}")
                file_path = new_file_path
            
            # Verileri DataFrame'e dönüştür (ilk veri sayfası için)
            df = pd.DataFrame(data)
            
            # Timestamp sütununu datetime formatına çevir ve daha iyi görünüm için formatla
            if 'timestamp' in df.columns:
                try:
                    # Eğer timestamp zaten string değilse, formatla
                    if not pd.api.types.is_string_dtype(df['timestamp']):
                        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.warning(f"Timestamp sütunu formatlanırken hata: {str(e)}")
            
            # Excel yazıcı oluştur
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Ana veriyi ilk sayfaya kaydet
                df.to_excel(writer, sheet_name='Filtered Results', index=False)
                
                # Eğer model bilgisi varsa, ikinci sayfaya kaydet
                if model_info:
                    # Model bilgilerini DataFrame'e dönüştür
                    model_rows = []
                    
                    for key, value in model_info.items():
                        model_rows.append({"Parameter": key, "Value": value})
                    
                    model_df = pd.DataFrame(model_rows)
                    
                    # Model bilgilerini ikinci sayfaya kaydet
                    model_df.to_excel(writer, sheet_name='Model Info', index=False)
            
            logger.info(f"Veri başarıyla kaydedildi: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Excel'e kayıt hatası: {str(e)}")
            raise e 