# BibAI Filter - AI-Powered Academic Publication Analyzer

<div align="center">
  <img src="docs/images/logo.webp" alt="BibAI Filter Logo" width="200">
  
  *Advanced AI analysis for academic publications*
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
</div>

## 📖 Overview

BibAI Filter is a sophisticated desktop application designed for researchers and academics who need to efficiently filter large volumes of scholarly publications. Using state-of-the-art AI models, this tool analyzes titles, abstracts, and keywords from your Excel-based publication lists to identify the most relevant papers for your research topics.

## ✨ Key Features

- **Seamless Data Import**: Easily load Excel files (`.xlsx` or `.xls`) containing your publication databases
- **Flexible Column Selection**: Define which columns contain titles, abstracts, and keywords
- **AI-Powered Analysis**: Score publications based on relevance to your specified research topic using advanced AI models
  - **Supported AI Providers**: OpenAI, Anthropic, Google AI, DeepSeek, Mistral AI, Cohere, Azure OpenAI (with appropriate API keys)
- **Smart Filtering**: Filter publications based on a customizable relevance threshold
- **Comprehensive Results**: Export filtered publications to a new Excel file with original data and AI relevance scores
- **Real-Time Progress Tracking**: Monitor the filtering process with an intuitive progress indicator
- **User-Friendly Interface**: Clean and intuitive PyQt5-based interface for a smooth user experience

## 🚀 Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/bcankara/BibAIFilter.git
   ```
    ```bash
    cd BibAIFilter
    ```
2. **Create a Virtual Environment (Recommended)**
   ```bash
   python -m venv .venv
   
   # On Linux/macOS
   source .venv/bin/activate
   
   # On Windows
   .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the Application**
   ```bash
   python main.py
   ```

## 🔍 Usage Guide

1. **Start the application**

2. **Configure AI Settings**
   - Navigate to the **"Settings"** tab
   - Select your preferred **AI Provider** (e.g., OpenAI, Anthropic)
   - Enter your **API Key** for the selected provider
   - Choose an appropriate **AI Model**

3. **Load and Filter Publications**
   - Switch to the **"Input & Filtering"** tab
   - Click **"Select Excel File"** to load your publication database
   - Specify which columns contain **Titles**, **Abstracts**, and **Keywords**
   - Enter your **Research Topic** in the text field (e.g., "Quantum Computing in Cryptography")
   - Adjust the **"Relevance Threshold"** slider to set filtering sensitivity (value between 0 and 1)
   - Select an output location using **"Choose Output File"**
   - Start the process by clicking **"Begin Filtering"**

4. **Review Results**
   - When processing completes, the filtered results will be saved to your specified output file
   - The log area will show a summary of the operation

## 📋 Requirements

All dependencies are listed in the `requirements.txt` file. Key requirements include:

- Python 3.8+
- PyQt5
- pandas
- openpyxl
- xlrd
- openai
- anthropic
- google-generativeai
- requests

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please adhere to coding standards and clearly describe your changes.

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## 🔒 Security Note

API keys are sensitive information and should be handled securely. The application stores keys locally in the `config/API_Settings.json` file, which is excluded from version control. 
