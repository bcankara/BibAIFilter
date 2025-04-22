#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import logging
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class ProcessingThread(QThread):
    """Thread for processing publications with AI"""
    
    # Signals
    progress_update = pyqtSignal(str)
    progress_percentage = pyqtSignal(int)
    processing_complete = pyqtSignal(int, int)
    error_occurred = pyqtSignal(str)
    file_processed = pyqtSignal(str, bool)
    
    def __init__(self, params):
        """Initialize with processing parameters"""
        super().__init__()
        self.input_file = params.get('input_file', '')
        self.output_file = params.get('output_file', '')
        self.title_col = params.get('title_col', '')
        self.abstract_col = params.get('abstract_col', '')
        self.keywords_col = params.get('keywords_col', '')
        self.categories_col = params.get('categories_col', '')
        self.topic = params.get('topic', '')
        self.prompt_template = params.get('prompt_template', None)
        self.provider = params.get('provider', 'openai')
        self.api_key = params.get('api_key', '')
        self.model = params.get('model', '')
        self.base_url = params.get('base_url', '')
        self.temperature = params.get('temperature', 0.0)
        self.threshold = params.get('threshold', 0.6)
        self.max_records = params.get('max_records', 0)  # 0 means process all
        self.iterations = params.get('iterations', 1)  # Tekrar sayısı, varsayılan 1
        self.terminate_flag = False
        
        # Initialize excel processor
        from utils.excel_processor import ExcelProcessor
        self.excel_processor = ExcelProcessor()
    
    def run(self):
        """Run the processing thread"""
        try:
            # Initialize progress at 0%
            self.progress_percentage.emit(0)
            self.progress_update.emit("Starting...")
            
            # Initialize excel processor
            from utils.excel_processor import ExcelProcessor
            from utils.ai_processor import AIProcessor
            
            # Read data from Excel
            self.progress_update.emit("Reading Excel file...")
            data = self.excel_processor.load_excel_data(self.input_file)
            total_rows = len(data)
            
            if total_rows == 0:
                self.error_occurred.emit("No data found in the Excel file.")
                return
            
            self.progress_update.emit(f"Total {total_rows} articles found. Processing...")
            # Log iterations setting
            self.progress_update.emit(f"Each record will be processed {self.iterations} times.")
            
            # Initialize AI processor
            ai_processor = AIProcessor(
                provider=self.provider,
                api_key=self.api_key,
                model=self.model,
                base_url=self.base_url,
                temperature=self.temperature
            )
            
            # Process data
            processed_data = []
            relevant_count = 0
            
            # Maksimum kayıt sınırını kontrol et
            if self.max_records > 0 and self.max_records < total_rows:
                self.progress_update.emit(f"Maximum {self.max_records} records will be processed (out of {total_rows} records)")
                effective_total = self.max_records
            else:
                effective_total = total_rows
                
            # Her iterasyon ve her kayıt için toplam iş sayısını hesapla
            total_tasks = effective_total * self.iterations
            completed_tasks = 0
            
            # YENİ MANTIK: İterasyon dışarıda, makale için döngü içeride
            for iteration in range(1, self.iterations + 1):
                if self.terminate_flag:
                    self.progress_update.emit("Processing cancelled.")
                    break
                    
                self.progress_update.emit(f"Starting iteration {iteration} of {self.iterations}...")
                
                for i, row in enumerate(data):
                    if self.terminate_flag:
                        self.progress_update.emit("Processing cancelled.")
                        break
                        
                    # Maksimum kayıt sayısına ulaşıldıysa döngüden çık
                    if self.max_records > 0 and i >= self.max_records:
                        self.progress_update.emit(f"Maximum record count ({self.max_records}) reached for iteration {iteration}.")
                        break
                    
                    # Original row data to use for each iteration
                    original_row = row.copy()
                    
                    # İlerleme yüzdesini güncelle - tüm iterations dahil
                    completed_tasks += 1
                    progress = int((completed_tasks / total_tasks) * 100)
                    self.progress_percentage.emit(progress)
                    
                    # Title and abstract bilgisi
                    title = str(original_row.get(self.title_col, ''))
                    abstract = str(original_row.get(self.abstract_col, ''))
                    keywords = str(original_row.get(self.keywords_col, ''))
                    categories = str(original_row.get(self.categories_col, ''))
                    
                    if not title and not abstract:
                        self.progress_update.emit(f"Row {i+1}: Title and abstract missing, skipping for iteration {iteration}.")
                        # İlk iterasyonda boş kayıtları ekleme
                        if iteration == 1:
                            original_row['relevance_score'] = 0.0
                            original_row['is_relevant'] = False
                            original_row['iteration'] = iteration
                            original_row['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
                            processed_data.append(original_row)
                        continue
                    
                    # Bu iterasyon için yeni bir row kopya oluşturup işle
                    current_row = original_row.copy()
                    
                    # Get relevance score from AI
                    self.progress_update.emit(f"Iteration {iteration}/{self.iterations}, Row {i+1}/{total_rows}: Processing '{title}'...")

                    # Log input data for testing (ilk 2 makale için tam log)
                    if i < 2 and iteration == 1:
                        input_log = f"""
===== SENDING TO AI (ITERATION #{iteration}, RECORD #{i+1}) =====
Topic: {self.topic}
Title: {title}
Abstract: {abstract}
Keywords: {keywords}
Categories: {categories}
Provider: {self.provider}
Model: {self.model}
Temperature: {self.temperature}
=========================================
"""
                        self.progress_update.emit(input_log)
                        logger.info(input_log)

                    # Check if we have a custom prompt template
                    if self.prompt_template:
                        # Replace placeholders with actual values
                        custom_prompt = self.prompt_template
                        custom_prompt = custom_prompt.replace("{TITLE}", title)
                        custom_prompt = custom_prompt.replace("{ABSTRACT}", abstract)
                        custom_prompt = custom_prompt.replace("{KEYWORDS}", keywords)
                        custom_prompt = custom_prompt.replace("{TOPIC}", self.topic)
                        custom_prompt = custom_prompt.replace("{CATEGORIES}", categories)
                        
                        # Log the custom prompt for testing (ilk 2 makale için)
                        if i < 2 and iteration == 1:
                            prompt_log = f"""
===== CUSTOM PROMPT TO AI (ITERATION #{iteration}, RECORD #{i+1}) =====
{custom_prompt}
===============================================
"""
                            self.progress_update.emit(prompt_log)
                            logger.info(prompt_log)
                        
                        # Get score using custom prompt
                        relevance_score = ai_processor.get_relevance_score_with_prompt(
                            title, abstract, keywords, self.topic, custom_prompt, categories
                        )
                    else:
                        # Use the original method if no custom prompt
                        relevance_score = ai_processor.get_relevance_score(
                            title, abstract, keywords, self.topic, categories
                        )
                    
                    # Log the response for testing (ilk 2 makale için)
                    if i < 2 and iteration == 1:
                        response_log = f"""
===== AI RESPONSE (ITERATION #{iteration}, RECORD #{i+1}) =====
Score: {relevance_score}
======================================
"""
                        self.progress_update.emit(response_log)
                        logger.info(response_log)
                    
                    # Check if the score meets threshold
                    # Not: 1-7 ölçeğinde 1 en az ilişkili, 7 en ilişkili olduğu için
                    # skorun eşik değerinden büyük ya da eşit olması durumunda ilgili kabul edilir
                    is_relevant = relevance_score >= self.threshold
                    
                    # Add results to the row
                    current_row['relevance_score'] = relevance_score
                    current_row['is_relevant'] = is_relevant
                    
                    # İterasyon bilgisi ekle
                    current_row['iteration'] = iteration
                    
                    # Tam zaman damgası ekle (saniye seviyesine kadar)
                    current_row['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Log the results - hepsini ingilizce yap
                    result_message = f"Iteration {iteration}, Evaluation result: '{title}' - Score: {relevance_score}"
                    if is_relevant:
                        relevant_count += 1
                        logger.info(f"✓ {result_message} - RELEVANT")
                        self.progress_update.emit(f"✓ {result_message} - RELEVANT")
                    else:
                        logger.info(f"✗ {result_message} - NOT RELEVANT")
                        self.progress_update.emit(f"✗ {result_message} - NOT RELEVANT")
                    
                    # Add processed row to the results
                    processed_data.append(current_row)
                    
                    # Format result in English
                    result_status = "RELEVANT" if is_relevant else "NOT RELEVANT"
                    
                    # Emit file processed signal with the formatted text (Title - Score - Result)
                    self.file_processed.emit(f"{title}|{relevance_score}|{result_status} (Iteration #{iteration})", is_relevant)
            
            # Write results to Excel if not terminated
            if not self.terminate_flag:
                self.progress_update.emit("Writing results to Excel...")
                
                # Model bilgilerini hazırla
                model_info = {
                    "Provider": self.provider.capitalize(),
                    "Model": self.model,
                    "Temperature": self.temperature,
                    "Topic": self.topic,
                    "Threshold": self.threshold,
                    "Total Records": total_rows,
                    "Processed Records": len(data[:self.max_records if self.max_records > 0 else len(data)]),
                    "Relevant Records": relevant_count,
                    "Iterations": self.iterations,
                    "Date/Time": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Excel'e model bilgilerini de ekleyerek kaydet
                self.excel_processor.save_excel_data(processed_data, self.output_file, model_info)
                
                # Complete the process
                self.progress_percentage.emit(100)
                processed_count = len(processed_data) // self.iterations  # Gerçekten işlenen kayıt sayısı (her kayıt iterations kez işlendiğinden)
                self.progress_update.emit(f"Processing completed. {relevant_count} relevant articles found out of {processed_count} processed (with {self.iterations} iterations each).")
                self.processing_complete.emit(processed_count, relevant_count)
            
        except Exception as e:
            logger.exception(f"Processing error: {str(e)}")
            self.error_occurred.emit(f"Processing error: {str(e)}")
    
    def terminate(self):
        """Terminate the thread gracefully"""
        self.terminate_flag = True
        self.progress_update.emit("Terminating processing...")
        super().terminate() 