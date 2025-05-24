#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import time
import re  # Regular expression modülünü ekle
import requests
from pathlib import Path
from datetime import datetime
from openai import OpenAI  # Yeni OpenAI import
# Google Güvenlik Ayarları için Enumları import et
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger(__name__)

class AIProcessor:
    """Class for AI processing with various LLM API services"""
    
    def __init__(self, provider="openai", model=None, api_key=None, config_file=None, base_url=None, temperature=None, timeout=None):
        """Initialize AI Processor"""
        # Set config file path
        self.config_file = config_file or os.path.join("config", "API_Settings.json")
        
        # Initialize clients to None
        self.openai_client = None
        self.anthropic_client = None
        self.google_client = None
        
        # Load configuration
        self.config = self._load_config()
        
        # Update provider models to ensure latest are included
        self._update_provider_models()
        
        # Set provider
        self.provider = provider if provider in self.config.get("providers", {}) else self.config.get("activeProvider", "openai")
        
        # Set attributes from config (model, API key, base URL, temperature, timeout)
        self._set_attributes_from_config(model, api_key, base_url, temperature, timeout)
        
        # Initialize models list
        self.models = self.config.get("providers", {}).get(self.provider, {}).get("models", [])
        
        # Get system settings
        self.is_record_requests = self.config.get("settings", {}).get("record_requests", False)
        self.is_verbose_logging = self.config.get("settings", {}).get("verbose_logging", False)
        
        # Initialize API client if needed
        self._initialize_client()
    
    def _load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file not found: {self.config_file}")
                # Return default config
                return {
                    "activeProvider": "openai",
                    "providers": {
                        "openai": {
                            "api_key": "",
                            "base_url": "",
                            "active_model": "gpt-4.1",  # Set new active model
                            "models": [
                                "gpt-4.1",
                                "gpt-4.1-mini",
                                "gpt-4.1-nano",
                                "o1",
                                "o1-mini",
                                "o3-mini",
                                "o1-pro"
                            ]
                        },
                        "anthropic": {
                            "api_key": "",
                            "base_url": "https://api.anthropic.com",
                            "active_model": "claude-3-7-sonnet-20250219",
                            "models": [
                                "claude-3-7-sonnet-20250219",
                                "claude-3-5-sonnet-20241022",
                                "claude-3-5-haiku-20241022",
                                "claude-3-5-sonnet-20240620",
                                "claude-3-haiku-20240307",
                                "claude-3-opus-20240229"
                                # Removed older claude-3-haiku and sonnet without dates
                            ]
                        },
                        "google": {
                            "api_key": "",
                            "base_url": "https://generativelanguage.googleapis.com",
                            "active_model": "gemini-1.5-flash",
                            "models": [
                                # 2.5 Series - Preview/Experimental
                                "gemini-2.5-flash-preview-05-20",
                                "gemini-2.5-flash-preview-native-audio-dialog",
                                "gemini-2.5-flash-exp-native-audio-thinking-dialog",
                                "gemini-2.5-flash-preview-tts",
                                "gemini-2.5-pro-preview-05-06",
                                "gemini-2.5-pro-preview-tts",
                                # 2.0 Series - Stable
                                "gemini-2.0-flash",
                                "gemini-2.0-flash-preview-image-generation",
                                "gemini-2.0-flash-lite",
                                # 1.5 Series - Stable
                                "gemini-1.5-flash",
                                "gemini-1.5-flash-8b",
                                "gemini-1.5-pro",
                                # Embedding Models
                                "gemini-embedding-exp",
                                "text-embedding-004",
                                "embedding-001",
                                # Special Models
                                "aqa"
                            ]
                        },
                        "deepseek": {
                            "api_key": "",
                            "base_url": "https://api.deepseek.com",
                            "active_model": "deepseek-chat",
                            "models": [
                                "deepseek-reasoner",
                                "deepseek-chat", 
                                "deepseek-coder",
                                "deepseek-llm-67b-chat"
                            ]
                        },
                        "mistral": {
                            "api_key": "",
                            "base_url": "https://api.mistral.ai",
                            "active_model": "mistral-large-latest",
                            "models": [
                                "mistral-large-latest",
                                "mistral-medium-latest", 
                                "mistral-small-latest",
                                "open-mistral-7b"
                            ]
                        },
                        "cohere": {
                            "api_key": "",
                            "base_url": "https://api.cohere.ai",
                            "active_model": "command-r-plus",
                            "models": [
                                "command-r-plus",
                                "command-r", 
                                "command-light"
                            ]
                        },
                        "azure-openai": {
                            "api_key": "",
                            "base_url": "", 
                            "active_model": "gpt-4",
                            "models": [
                                "gpt-4",
                                "gpt-4-turbo",
                                "gpt-35-turbo"
                            ],
                            "api_version": "2024-02-15-preview"
                        }
                    },
                    "settings": {
                        "temperature": 0.2,
                        "timeout": 30
                    }
                }
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            return {}
    
    def save_config(self):
        """Save configuration to file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # Dump and log the current config to debug any issues
            logger.debug(f"Current config before saving: {self.config}")
            logger.info(f"API Key for {self.provider}: {self.api_key}")
            
            # Update config with current values
            if "providers" not in self.config:
                self.config["providers"] = {}
                
            # Ensure all providers exist in config
            providers = ["openai", "anthropic", "google", "deepseek", "mistral", "cohere", "azure-openai"]
            for provider in providers:
                if provider not in self.config["providers"]:
                    self.config["providers"][provider] = {
                        "api_key": "",
                        "base_url": "",
                        "active_model": "",
                        "models": []
                    }
                    
                    # Azure OpenAI için ek parametreler
                    if provider == "azure-openai":
                        self.config["providers"][provider]["api_version"] = "2024-02-15-preview"
            
            # Update current provider settings
            prov_config = self.config["providers"][self.provider]
            prov_config["api_key"] = self.api_key
            prov_config["active_model"] = self.model
            prov_config["base_url"] = self.base_url
            
            self.config["activeProvider"] = self.provider
            
            # Ensure settings exist
            if "settings" not in self.config:
                self.config["settings"] = {}
                
            self.config["settings"]["temperature"] = self.temperature
            self.config["settings"]["timeout"] = self.timeout
            
            # Dosyaya yazmadan önce config nesnesini kontrol et ve debug'a yazdır
            logger.debug(f"Config to be saved: {self.config}")
            logger.info(f"API key to save for {self.provider}: {self.api_key}")
            
            # Alternatif dosya yazma yöntemi
            import tempfile
            import shutil
            
            # Geçici dosya oluştur
            fd, temp_path = tempfile.mkstemp(suffix='.json')
            try:
                with os.fdopen(fd, 'w') as temp_file:
                    json.dump(self.config, temp_file, indent=4)
                
                # Geçici dosyayı asıl dosya konumuna taşı
                shutil.move(temp_path, self.config_file)
                
                logger.info(f"Config saved to {self.config_file} using temp file method")
            except Exception as e:
                logger.error(f"Error using temp file method: {str(e)}")
                # Temp file methodunda hata oluşursa direk yazma metodu deneyelim
                try:
                    with open(self.config_file, 'w') as f:
                        json.dump(self.config, f, indent=4)
                    logger.info(f"Config saved using direct write method")
                except Exception as direct_error:
                    logger.error(f"Error using direct write: {str(direct_error)}")
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)  # Geçici dosyı sil
                    raise direct_error
                    
                if os.path.exists(temp_path):
                    os.unlink(temp_path)  # Geçici dosyı sil
                raise e
            
            # Dosyanın yazılıp yazılmadığını kontrol et
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, "r") as f:
                        saved_config = json.load(f)
                    logger.debug(f"Saved config read back: {saved_config}")
                    
                    # API anahtarlarını kontrol et
                    for prov, conf in saved_config.get("providers", {}).items():
                        api_key = conf.get("api_key", "")
                        logger.info(f"Saved API key for {prov}: {api_key[:5] if api_key else 'empty'}")
                except Exception as read_error:
                    logger.error(f"Error reading back config: {str(read_error)}")
            
            return True
        except Exception as e:
            logger.error(f"Error saving config: {str(e)}")
            return False
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client with the API key and base URL"""
        try:
            if self.api_key:
                # Yeni OpenAI kütüphanesinde sadece api_key ve base_url parametreleri destekleniyor
                client_kwargs = {"api_key": self.api_key}
                
                # Eğer özel bir base URL varsa onu da ekle
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url
                
                # OpenAI istemcisini oluştur
                self.openai_client = OpenAI(**client_kwargs)
                logger.info("OpenAI client initialized successfully")
            else:
                logger.warning("No API key found for OpenAI client initialization")
                self.openai_client = None
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            self.openai_client = None
    
    def _initialize_client(self):
        """Initialize the appropriate client based on the provider"""
        if self.provider == "anthropic":
            try:
                # Import based on configuration
                import anthropic
                
                # Set up Anthropic client
                self.anthropic_client = anthropic.Anthropic(
                    api_key=self.api_key
                )
                logger.info("Anthropic client initialized")
                return True
            except Exception as e:
                logger.error(f"Error initializing Anthropic client: {str(e)}")
                self.anthropic_client = None
                return False
        elif self.provider == "google":
            try:
                # Import yeni Google Gen AI SDK
                from google import genai
                from google.genai import types

                # Yeni client oluşturma yöntemi
                self.google_client = genai.Client(api_key=self.api_key)

                logger.info(f"Google Gen AI client created successfully with new SDK.")
                return True
            except ImportError as ie:
                logger.error(f"Import error for Google Gen AI: {str(ie)}. Check if 'google-genai' is installed correctly.")
                self.google_client = None
                return False
            except Exception as e:
                logger.error(f"Error initializing Google Gen AI client: {str(e)}")
                self.google_client = None
                return False
        elif self.provider == "openai":
            return self._initialize_openai_client()
        # Default to true for providers that don't need initialization
        else:
            logger.info(f"No client initialization required for provider: {self.provider}")
            return True
    
    def reload_api_key(self):
        """Reload the API key from config"""
        try:
            # Reload config
            self.config = self._load_config()
            
            # Update the API key for the current provider
            provider_config = self.config.get("providers", {}).get(self.provider, {})
            self.api_key = provider_config.get("api_key", "")
            
            # If using OpenAI, refresh the client
            if self.provider == "openai":
                self._initialize_openai_client()
                
            # Anthropic için istemciyi yenile
            if self.provider == "anthropic":
                try:
                    import anthropic
                    self.anthropic_client = anthropic.Anthropic(api_key=self.api_key)
                    logger.info("Anthropic client initialized")
                except ImportError:
                    logger.warning("Anthropic package not installed, will use REST API")
                    self.anthropic_client = None
                except Exception as e:
                    logger.error(f"Error initializing Anthropic client: {str(e)}")
                    self.anthropic_client = None
            
            return True
        except Exception as e:
            logger.error(f"Error reloading API key: {str(e)}")
            return False
    
    def test_connection(self):
        """Test the connection to the selected API service"""
        try:
            # Reload API key from config to ensure we have the latest
            self.reload_api_key()
            
            if not self.api_key:
                logger.error(f"Missing API key for {self.provider}")
                return False
                
            if self.provider == "openai":
                # Yeni client kullanımına göre bağlantı testi
                if not self.openai_client:
                    self._initialize_openai_client()
                    
                if not self.openai_client:
                    logger.error("OpenAI client could not be initialized")
                    return False
                
                # Reasoning modellerini kontrol et
                is_reasoning_model = any(self.model.startswith(prefix) for prefix in ["o1", "o3"])
                
                # API isteğini gönder
                try:
                    logger.info(f"Testing connection with OpenAI API using model: {self.model}")
                    
                    # Reasoning modelleri için özel API çağrısı
                    if is_reasoning_model:
                        response = self.openai_client.chat.completions.create(
                            model=self.model,
                            reasoning_effort="low",  # Bağlantı testi için low effort
                            messages=[
                                {"role": "user", "content": "Hello, testing the connection."}
                            ]
                        )
                    else:
                        # Standart modeller için normal API çağrısı
                        response = self.openai_client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "user", "content": "Hello, testing the connection."}
                            ],
                            max_tokens=10,
                            temperature=self.temperature
                        )
                    
                    # Yanıt kontrolü
                    if response and hasattr(response, 'choices') and len(response.choices) > 0:
                        result = response.choices[0].message.content.strip()
                        logger.info(f"API connection test successful: {result}")
                        return True
                    else:
                        logger.error("API response is empty or invalid")
                        return False
                    
                except Exception as e:
                    logger.error(f"API connection test failed: {str(e)}")
                    return False
            elif self.provider == "anthropic":
                # Anthropic API test
                # Önce SDK ile test et
                if hasattr(self, 'anthropic_client') and self.anthropic_client:
                    try:
                        # Çok küçük bir mesajla test et
                        logger.info(f"Testing Anthropic connection with SDK and model: {self.model}")
                        response = self.anthropic_client.messages.create(
                            model=self.model,
                            max_tokens=5,
                            messages=[
                                {"role": "user", "content": "Hello, testing the connection."}
                            ]
                        )
                        logger.info(f"Anthropic SDK connection test successful: {response.id}")
                        return True
                    except Exception as e:
                        error_msg = str(e)
                        logger.warning(f"Anthropic SDK test failed: {error_msg}")
                        
                        # Model hatası ise bilinen çalışan bir model dene
                        if "model" in error_msg.lower() or "status_code=404" in error_msg.lower():
                            # Bilinen çalışan modeller listesi
                            fallback_models = ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-3-sonnet-20240229"]
                            
                            for fallback_model in fallback_models:
                                try:
                                    logger.info(f"Trying fallback model: {fallback_model}")
                                    response = self.anthropic_client.messages.create(
                                        model=fallback_model,
                                        max_tokens=5,
                                        messages=[
                                            {"role": "user", "content": "Hello"}
                                        ]
                                    )
                                    # Bu model çalıştı, varsayılan olarak ayarla
                                    logger.info(f"Fallback model successful: {fallback_model}")
                                    self.model = fallback_model
                                    return True
                                except Exception as fallback_error:
                                    logger.warning(f"Fallback model {fallback_model} failed: {str(fallback_error)}")
                                    continue
                
                # SDK testi başarısız olduysa veya SDK yoksa REST API ile dene
                try:
                    logger.info("Testing Anthropic connection with REST API")
                    headers = {
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01", # Corrected API version
                        "content-type": "application/json"
                    }
                    
                    # Bilinen çalışan bir modeli kullan
                    test_model = "claude-3-5-sonnet-20241022"
                    
                    data = {
                        "model": test_model,
                        "messages": [{"role": "user", "content": "Hello, testing the connection."}],
                        "max_tokens": 5
                    }
                    
                    response = requests.post(
                        f"{self.base_url}/v1/messages",
                        headers=headers,
                        json=data,
                        timeout=self.timeout
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Anthropic REST API connection test successful with model: {test_model}")
                        # Bu modeli varsayılan olarak ayarla
                        self.model = test_model
                        return True
                    else:
                        logger.warning(f"Anthropic API connection test failed: {response.status_code}")
                        logger.warning(f"Error response: {response.text}")
                        return False
                except Exception as e:
                    logger.warning(f"Anthropic REST API test failed: {str(e)}")
                    return False
                    
            elif self.provider == "google":
                # Yeni Google Gen AI SDK ile client kullanımı
                try:
                    # Önce client'ın başlatıldığından emin ol
                    if not self.google_client:
                        if not self._initialize_client():
                            logger.error("Google client could not be initialized.")
                            return False
                    
                    logger.info(f"Testing connection with Google Gen AI API using model: {self.model}")
                    
                    # Yeni API call formatı
                    response = self.google_client.models.generate_content(
                        model=self.model,
                        contents="Hello, testing the connection."
                    )
                    
                    # Check response
                    logger.debug(f"Google API test response: {response}")
                    if hasattr(response, 'text') and response.text:
                        result_text = response.text.strip()
                        logger.info(f"Google API connection test successful: {result_text}")
                        return True
                    else:
                        logger.warning(f"Unexpected Google API response format: {response}")
                        return False
                        
                except Exception as e:
                    logger.error(f"Google API test failed: {str(e)}")
                    
                    # Model bulunamazsa varsayılan modeli dene
                    if "model" in str(e).lower() and "not found" in str(e).lower():
                        logger.warning(f"Model {self.model} not found, trying with gemini-1.5-flash")
                        try:
                            self.model = "gemini-1.5-flash"
                            response = self.google_client.models.generate_content(
                                model="gemini-1.5-flash",
                                contents="Hello, testing the connection."
                            )
                            if hasattr(response, 'text') and response.text:
                                logger.info(f"Google API connection test successful with fallback model")
                                return True
                        except Exception as fallback_error:
                            logger.error(f"Fallback model test failed: {str(fallback_error)}")
                    
                    return False
            elif self.provider == "deepseek":
                # DeepSeek API test
                try:
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    }
                    
                    # Use a simple test request
                    data = {
                        "model": self.model,
                        "messages": [{"role": "user", "content": "Hello, testing the connection."}],
                        "max_tokens": 5
                    }
                    
                    response = requests.post(
                        f"{self.base_url}/v1/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=self.timeout
                    )
                    
                    # Check response status
                    logger.debug(f"DeepSeek API Response Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        logger.info(f"DeepSeek API connection test successful")
                        return True
                    elif response.status_code == 400:
                        error_text = response.text
                        logger.warning(f"DeepSeek API error 400: {error_text}")
                        
                        # Check if model not found error
                        if "model parameter" in error_text.lower() or "model not found" in error_text.lower():
                            logger.warning(f"Model {self.model} not supported, trying with deepseek-chat")
                            # Try once more with a different model
                            fallback_data = {
                                "model": "deepseek-chat",
                                "messages": [{"role": "user", "content": "Hello, testing the connection."}],
                                "max_tokens": 5
                            }
                            
                            fallback_response = requests.post(
                                f"{self.base_url}/v1/chat/completions",
                                headers=headers,
                                json=fallback_data,
                                timeout=self.timeout
                            )
                            
                            if fallback_response.status_code == 200:
                                logger.info(f"DeepSeek API connection test successful with fallback model")
                                self.model = "deepseek-chat"
                                return True
                        
                        logger.warning(f"DeepSeek API connection test failed: {response.status_code}")
                        return False
                    else:
                        logger.warning(f"DeepSeek API connection test failed: {response.status_code}")
                        return False
                
                except Exception as e:
                    logger.error(f"DeepSeek API test failed: {str(e)}")
                    return False
            elif self.provider == "azure-openai":
                # Azure OpenAI API test
                try:
                    # Azure OpenAI için gerekli parametreler
                    api_version = self.config.get("providers", {}).get("azure-openai", {}).get("api_version", "2024-02-15-preview")
                    
                    # Base URL kontrolü
                    if not self.base_url:
                        logger.error("Missing base URL for Azure OpenAI")
                        return False
                    
                    # OpenAI client'ı Azure için özel yapılandırma ile başlat
                    azure_client_kwargs = {
                        "api_key": self.api_key,
                        "azure_endpoint": self.base_url,
                        "api_version": api_version
                    }
                    
                    azure_client = OpenAI(**azure_client_kwargs)
                    
                    # Bağlantı testi
                    response = azure_client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": "Hello, testing the connection."}
                        ],
                        max_tokens=5,
                        temperature=self.temperature
                    )
                    
                    # Yanıtı kontrol et
                    if response and hasattr(response, 'choices') and len(response.choices) > 0:
                        logger.info(f"Azure OpenAI API connection test successful: {response}")
                        return True
                    else:
                        logger.warning(f"Azure OpenAI API connection test failed: Unexpected response format")
                        return False
                    
                except Exception as e:
                    logger.error(f"Azure OpenAI API test error: {str(e)}")
                    return False
            
            elif self.provider == "mistral":
                # Mistral AI API test
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                data = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Hello, testing the connection."}],
                    "max_tokens": 5
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    logger.info(f"Mistral AI API connection test successful")
                    return True
                else:
                    logger.warning(f"Mistral AI API connection test failed: {response.status_code} - {response.text}")
                    return False
            
            elif self.provider == "cohere":
                # Cohere API test
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json"
                }
                
                data = {
                    "model": self.model,
                    "message": "Hello, testing the connection.",
                    "max_tokens": 5
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/generate",
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    logger.info(f"Cohere API connection test successful")
                    return True
                else:
                    logger.warning(f"Cohere API connection test failed: {response.status_code} - {response.text}")
                    return False
            
            else:
                logger.warning(f"Unsupported provider: {self.provider}")
                return False
                
        except Exception as e:
            logger.exception(f"API connection test failed: {str(e)}")
            return False
    
    def get_relevance_score(self, title, abstract, keywords, topic, categories=None):
        """
        Get relevance score between publication and topic
        
        Args:
            title (str): Publication title
            abstract (str): Publication abstract
            keywords (str): Publication keywords
            topic (str): Topic to compare against
            categories (str, optional): Publication categories or subject areas
            
        Returns:
            float: Relevance score between 0 and 1
        """
        try:
            # Prepare input for AI
            publication_text = f"Title: {title}\n\nAbstract: {abstract}"
            
            if keywords:
                publication_text += f"\n\nKeywords: {keywords}"
            
            if categories:
                publication_text += f"\n\nCategories/Subject Areas: {categories}"
            
            # System instruction for the AI
            system_message = """
            You are an advanced AI specialized in evaluating the relevance of scientific papers to a specified topic. 
            Your task is to analyze the provided paper information (title, abstract, keywords) and output a 
            relevance score using a 7-point semantic differential scale.

            ANALYSIS INSTRUCTIONS:
            1. Term Matching:
               - Identify key terms, synonyms, and relevant concepts related to the provided topic.
               - Assess the frequency and contextual usage of these terms within the paper's title, abstract, and keywords.

            2. Contextual Alignment:
               - Evaluate both direct and indirect connections between the paper content and the provided topic.
               - Even superficial mentions or indirect references should influence the relevance score.

            3. Depth and Significance:
               - Evaluate the extent to which the paper directly or indirectly focuses on the specified topic.
               - The paper does not need to be centered exclusively around the topic; partial or secondary references also indicate relevance.

            4. 7-POINT SCORING SCALE:
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
            
            # User message template
            user_message = f"""
            TOPIC: {topic}
            
            PAPER TITLE: {title}
            PAPER ABSTRACT: {abstract}
            KEYWORDS: {keywords}
            """
            
            # Process based on provider
            if self.provider == "openai":
                return self._get_score_openai(system_message, user_message)
            elif self.provider == "anthropic":
                return self._get_score_anthropic(system_message, user_message)
            elif self.provider == "google":
                return self._get_score_google(system_message, user_message)
            elif self.provider == "deepseek":
                return self._get_score_deepseek(system_message, user_message)
            elif self.provider == "mistral":
                return self._get_score_mistral(system_message, user_message)
            elif self.provider == "cohere":
                return self._get_score_cohere(system_message, user_message)
            elif self.provider == "azure-openai":
                return self._get_score_azure_openai(system_message, user_message)
            else:
                logger.warning(f"Unsupported provider: {self.provider}")
                return 0.0
            
        except Exception as e:
            logger.exception(f"Error getting relevance score: {str(e)}")
            return 0.0
    
    def _get_score_openai(self, system_message, user_message):
        """Get relevance score using OpenAI API"""
        # o1-mini için özel işleyici kullan
        if self.model == "o1-mini":
            return self._get_score_o1_mini(system_message, user_message)
        
        # Diğer modeller için mevcut işleyici devam eder...
        while True:
            try:
                # Yeni OpenAI istemci ile API çağrısı
                if not self.openai_client:
                    self._initialize_openai_client()
                
                # OpenAI client kontrolü
                if not self.openai_client:
                    logger.error("OpenAI client not initialized")
                    time.sleep(2)
                    continue
                
                # System ve user mesajlarını birleştirerek soruyu hazırla
                prompt = f"{system_message}\n\n{user_message}\n\nIMPORTANT: You MUST respond with ONLY a single digit from 1 to 7 representing the relevance score. No other text is allowed."
                
                # Temel istek parametrelerini hazırla
                request_params = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 10,
                    "temperature": self.temperature
                }
                
                # API isteğini gönder
                logger.info(f"Using OpenAI chat completions API with model: {self.model}")
                logger.debug(f"Request parameters: {request_params}")
                
                response = self.openai_client.chat.completions.create(**request_params)
                
                # Yanıt içeriklerini logla
                logger.debug(f"Response: {response}")
                
                # Extract response
                result_text = response.choices[0].message.content.strip()
                logger.info(f"OpenAI response: '{result_text}'")
                
                # Parse JSON from response
                return self._parse_result(result_text)
            
            except Exception as e:
                error_message = str(e)
                logger.warning(f"API call failed: {error_message}")
                
                # API rate limit aşıldığında daha uzun süre bekle
                if "429" in error_message or "rate limit" in error_message.lower():
                    logger.warning("Rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)  # Rate limit için 20 saniye bekle
                else:
                    time.sleep(2)  # Normal hatalar için 2 saniye bekle
                
                continue  # Continue the loop to wait for API response
    
    def _get_score_o1_mini(self, system_message, user_message):
        """o1-mini modeli için özel işleyici"""
        try:
            # OpenAI istemci kontrolü
            if not self.openai_client:
                self._initialize_openai_client()
            
            if not self.openai_client:
                logger.error("OpenAI client not initialized")
                return 4  # Varsayılan değer
            
            # Sistem ve kullanıcı mesajlarını birleştir
            combined_message = f"{system_message}\n\n{user_message}\n\nIMPORTANT: You MUST respond with ONLY a single digit from 1 to 7 representing the relevance score. No other text is allowed."
            
            # o1-mini için özel format - tam olarak belirtilen şekilde
            response = self.openai_client.chat.completions.create(
                model="o1-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": combined_message
                            }
                        ]
                    }
                ],
                store=True
            )
            
            # Yanıtı logla ve işle
            logger.debug(f"o1-mini response: {response}")
            return self._extract_text_from_openai_response(response)
            
        except Exception as e:
            logger.error(f"Error in o1-mini score calculation: {str(e)}")
            return 4  # Hata durumunda varsayılan değer
    
    def _extract_text_from_openai_response(self, response):
        """
        OpenAI Responses API yanıtından metin çıkarma
        """
        try:
            # Yanıt objesini inceleme ve loğlama
            logger.debug(f"Response type: {type(response)}")
            logger.debug(f"Response attributes: {dir(response)}")
            
            # 1. Output_text attribute (o1, o1-pro API yanıtları genellikle buna sahip)
            if hasattr(response, 'output_text') and response.output_text:
                logger.debug(f"Found 'output_text' attribute: {response.output_text}")
                return response.output_text.strip()
            
            # 2. Output attribute (farklı API yanıt formatları)
            if hasattr(response, 'output') and response.output:
                logger.debug(f"Found 'output' attribute: {response.output}")
                
                # String output
                if isinstance(response.output, str):
                    return response.output.strip()
                
                # Text property içeren object
                if hasattr(response.output, 'text'):
                    return response.output.text.strip()
                
                # Dictionary with text key
                if isinstance(response.output, dict):
                    if 'text' in response.output:
                        return response.output['text'].strip()
                    # Liste içindeki ilk öğe
                    elif isinstance(response.output.get('contents', []), list) and response.output['contents']:
                        return str(response.output['contents'][0]).strip()
            
            # 3. ChatCompletion yanıt yapısı (standard API)
            if hasattr(response, 'choices') and response.choices:
                first_choice = response.choices[0]
                # Message content
                if hasattr(first_choice, 'message') and hasattr(first_choice.message, 'content'):
                    logger.debug(f"Found content in message: {first_choice.message.content}")
                    return first_choice.message.content.strip()
                # Text attribute
                if hasattr(first_choice, 'text'):
                    return first_choice.text.strip()
                # Dictionary format
                if isinstance(first_choice, dict) and 'message' in first_choice:
                    if isinstance(first_choice['message'], dict) and 'content' in first_choice['message']:
                        return first_choice['message']['content'].strip()
            
            # 4. String yanıtı kontrol et
            response_str = str(response)
            logger.debug(f"Response as string: {response_str}")
            
            # JSON formatını direkt parse etmeyi dene
            try:
                # Eğer yanıt JSON string ise
                if response_str.strip().startswith('{') and response_str.strip().endswith('}'):
                    json_data = json.loads(response_str)
                    if 'score' in json_data:
                        return str(json_data['score'])
                    elif 'text' in json_data:
                        return json_data['text'].strip()
            except json.JSONDecodeError:
                logger.debug("Response is not a valid JSON string")
            
            # 5. Regex ile çıkarma işlemleri
            # Sadece bir rakam yanıtı için kontrol et (1-7 arası)
            digit_match = re.search(r'\b([1-7])\b', response_str)
            if digit_match:
                logger.debug(f"Extracted digit via regex: {digit_match.group(1)}")
                return digit_match.group(1)
            
            # JSON formatında yanıt için kontrol et
            json_match = re.search(r'{\s*"score"\s*:\s*(\d+)\s*}', response_str)
            if json_match:
                logger.debug(f"Extracted score from JSON via regex: {json_match.group(1)}")
                return json_match.group(1)
            
            # Text formatında yanıt için kontrol et
            text_match = re.search(r'text=[\'"]?(\d+)[\'"]?', response_str)
            if text_match:
                logger.debug(f"Extracted score from text attribute via regex: {text_match.group(1)}")
                return text_match.group(1)
            
            # Yanıt içindeki herhangi bir rakamı bul
            any_digit_match = re.search(r'(\d+)', response_str)
            if any_digit_match:
                logger.debug(f"Extracted any digit via regex: {any_digit_match.group(1)}")
                return any_digit_match.group(1)
            
            # 6. Son çare olarak, 4 varsayılan değerini döndür
            logger.warning("No text could be extracted from response, returning default score")
            logger.debug(f"Full response dump for debugging: {response}")
            return "4"
        except Exception as e:
            logger.error(f"Error extracting text from response: {str(e)}")
            # Hata durumunda varsayılan değeri döndür
            return "4"

    def _get_score_openai_response(self, model, system_message, user_message):
        """Get relevance score using OpenAI Responses API."""
        try:
            if model == "o1-mini":
                # o1-mini için özel işleyici
                prompt = f"{system_message}\n\n{user_message}"
                # self.openai_client kullan
                response = self.openai_client.completions.create(
                    model=model,
                    prompt=prompt
                )
                logger.debug(f"o1-mini response: {response}")
                return self._extract_text_from_openai_response(response)
            else:
                # Diğer modeller için mevcut işleyici
                messages = [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
                
                # self.openai_client kullan
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=150,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0
                )
                logger.debug(f"OpenAI response: {response}")
                return self._extract_text_from_openai_response(response)
                
        # Hata bloklarında da self.openai_client kullanmaya gerek yok, doğrudan hata tipi kontrolü yeterli
        except self.openai_client.RateLimitError as e:
            logger.error(f"Rate limit exceeded for model {model}: {str(e)}")
            raise
        except self.openai_client.BadRequestError as e:
            if "model not found" in str(e).lower():
                logger.warning(f"Model {model} not found, falling back to gpt-4o")
                # Burada _get_score_openai çağrılırken self.model kullanılır, bu doğru
                return self._get_score_openai("gpt-4o", system_message, user_message)
            raise
        except Exception as e:
            logger.error(f"Error getting score from OpenAI: {str(e)}")
            raise
    
    def _get_score_anthropic(self, system_message, user_message):
        """Get relevance score using Anthropic API"""
        # Sistem ve kullanıcı mesajlarını birleştir
        custom_prompt = f"{system_message}\n\n{user_message}"
        
        while True:
            try:
                # Modern Anthropic kütüphanesi ile dene
                if hasattr(self, 'anthropic_client') and self.anthropic_client:
                    try:
                        # Her zaman messages.create kullan
                        logger.info(f"Using Anthropic SDK messages.create for custom prompt with model: {self.model}")
                        response = self.anthropic_client.messages.create(
                            model=self.model,
                            # System prompt is not used here as it's part of the custom_prompt
                            messages=[
                                {"role": "user", "content": custom_prompt} # Send the full custom prompt as user content
                            ],
                            temperature=self.temperature,
                            max_tokens=10 # Reduced tokens for score
                        )
                        
                        # Yanıtı işle (Claude 3.x formatı varsayılır)
                        if response.content and isinstance(response.content, list) and len(response.content) > 0:
                            result_text = response.content[0].text.strip()
                            logger.info(f"Anthropic SDK response for custom prompt: {result_text}")
                            return self._parse_result(result_text)
                        else:
                            logger.warning(f"Unexpected Anthropic SDK response format for custom prompt: {response}")
                            raise Exception("Unexpected SDK response format") # Force fallback

                    except Exception as sdk_error:
                        logger.warning(f"Anthropic SDK error for custom prompt: {str(sdk_error)}, falling back to REST API")
                        # SDK hata verirse veya format uymazsa REST API'ye geri dön
                
                # --- REST API Fallback --- 
                logger.info("Attempting Anthropic custom prompt request via REST API")
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01", # Corrected API version
                    "content-type": "application/json"
                }
                
                # For custom prompts, the system part is usually included within the prompt itself.
                # We send the entire custom_prompt as a single user message.
                data = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": custom_prompt} 
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 10 # Reduced tokens for score
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/messages", # Use messages endpoint
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                # Check REST response
                if response.status_code == 200:
                    result = response.json()
                    if "content" in result and isinstance(result["content"], list) and len(result["content"]) > 0:
                        result_text = result["content"][0].get("text", "").strip()
                        logger.info(f"Anthropic REST API response for custom prompt: {result_text}")
                        return self._parse_result(result_text)
                    else:
                        logger.warning(f"Unexpected Anthropic REST API response format for custom prompt: {result}")
                elif response.status_code == 429:
                    logger.warning("Anthropic API rate limit exceeded for custom prompt, waiting 20 seconds before retry...")
                    time.sleep(20)
                    continue # Retry loop
                else:
                    # Log other HTTP errors from REST API
                    logger.warning(f"Anthropic REST API custom prompt call failed: {response.status_code} - {response.text}")
                    time.sleep(2)
                    continue # Retry loop

            except Exception as e:
                 # General errors (network issues, etc.)
                logger.warning(f"Anthropic API custom prompt call failed: {str(e)}")
                time.sleep(2)
                continue # Retry loop
    
    def _get_score_google(self, system_message, user_message):
        """Get relevance score using Google Gen AI API"""
        try:
            if not self.google_client:
                if not self._initialize_client():
                     logger.error("Google client could not be initialized.")
                     return 4

            # Sistem ve kullanıcı mesajlarını birleştir
            combined_message = f"{system_message}\n\n{user_message}\n\nIMPORTANT: You MUST respond with ONLY a single digit from 1 to 7 representing the relevance score. No other text is allowed."

            logger.info(f"Sending query to Google Gen AI API: {self.model}")

            # Yeni API call formatı
            response = self.google_client.models.generate_content(
                model=self.model,
                contents=combined_message
            )

            # Process response
            logger.debug(f"Full Google API response: {response}")
            if hasattr(response, 'text') and response.text:
                result_text = response.text.strip()
                logger.info(f"Google response: {result_text}")
                return self._parse_result(result_text)
            else:
                logger.warning(f"Unexpected Google API response format or no text: {response}")
                # Safety feedback kontrolü (eski format uyumluluğu)
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason'):
                    logger.warning(f"Request blocked: {response.prompt_feedback.block_reason}")
                return 4  # Default score

        except Exception as e:
            logger.error(f"Error with Google API call: {str(e)}")
            if "model" in str(e).lower() and "not found" in str(e).lower():
                logger.warning(f"Model {self.model} not found, falling back to gemini-1.5-flash")
                self.model = "gemini-1.5-flash"
            return 4
    
    def _get_score_deepseek(self, system_message, user_message):
        """Get relevance score using DeepSeek API"""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                # DeepSeek-Reasoner için farklı endpoint ve format kullan
                if self.model == "deepseek-reasoner":
                    logger.info(f"Using DeepSeek Reasoner model with special format")
                    
                    # Sistem ve kullanıcı mesajını birleştir
                    combined_message = f"{system_message}\n\n{user_message}"
                    
                    # DeepSeek Reasoner için API isteğini hazırla
                    data = {
                        "model": "deepseek-reasoner",
                        "messages": [
                            {"role": "user", "content": combined_message}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": 20,  # Sadece skorun dönmesi için kısa tutuyoruz
                        "top_p": 0.95
                    }
                    
                    # DeepSeek Reasoner için doğru endpoint kullan
                    url = f"{self.base_url}/v1/chat/completions"
                    
                    logger.debug(f"DeepSeek Reasoner API Request URL: {url}")
                    logger.debug(f"DeepSeek Reasoner API Request Data: {data}")
                    
                    response = requests.post(
                        url,
                        headers=headers,
                        json=data,
                        timeout=self.timeout
                    )
                else:
                    # Standart DeepSeek modelleri için 
                    data = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_message}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": 10
                    }
                    
                    response = requests.post(
                        f"{self.base_url}/v1/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=self.timeout
                    )
                
                # Yanıt durum kodunu kontrol et ve logla
                logger.debug(f"DeepSeek API Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Yanıt logla
                    logger.debug(f"DeepSeek API Response: {result}")
                    
                    # Chat/completions endpoint için
                    if "choices" in result and len(result["choices"]) > 0:
                        result_text = result["choices"][0]["message"]["content"].strip()
                        logger.info(f"DeepSeek API response: {result_text}")
                        return self._parse_result(result_text)
                    else:
                        logger.warning(f"Unexpected DeepSeek API response format: {result}")
                elif response.status_code == 400:
                    error_text = response.text
                    logger.warning(f"DeepSeek API error 400: {error_text}")
                    
                    # Hata mesajını detaylı inceleme
                    if "model parameter" in error_text.lower() or "model not found" in error_text.lower():
                        logger.warning(f"Model {self.model} not supported, falling back to deepseek-chat")
                        self.model = "deepseek-chat"
                        continue
                    elif "api key" in error_text.lower() or "authentication" in error_text.lower():
                        logger.error("DeepSeek API authentication error - invalid API key")
                        return 4  # Authentication error, return default score
                    
                    # Diğer 400 hataları için bekleme ve yeniden deneme
                    time.sleep(2)
                    continue
                elif response.status_code == 429:
                    logger.warning(f"DeepSeek API çağrısı başarısız: {response.status_code} - {response.text}")
                    logger.warning("DeepSeek API rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)  # Rate limit için 20 saniye bekle
                    continue
                else:
                    logger.warning(f"DeepSeek API call failed: {response.status_code} - {response.text}")
                    time.sleep(2)  # Normal hatalar için 2 saniye bekle
                    continue  # Continue the loop to wait for API response
            
            except Exception as e:
                logger.warning(f"DeepSeek API call failed: {str(e)}")
                time.sleep(2)  # Normal hatalar için 2 saniye bekle
                continue  # Continue the loop to wait for API response
    
    def _get_score_mistral(self, system_message, user_message):
        """Get relevance score using Mistral AI API"""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                data = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 10
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    result_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logger.info(f"Mistral AI response: {result_text}")
                    return self._parse_result(result_text)
                elif response.status_code == 429:
                    logger.warning(f"Mistral AI API rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)
                    continue
                else:
                    logger.warning(f"Mistral AI API call failed: {response.status_code} - {response.text}")
                    time.sleep(2)
                    continue
            
            except Exception as e:
                logger.warning(f"API call failed: {str(e)}")
                time.sleep(2)
                continue
    
    def _get_score_cohere(self, system_message, user_message):
        """Get relevance score using Cohere API"""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json"
                }
                
                # Cohere farklı bir API formatı kullanıyor
                # Sistem ve kullanıcı mesajlarını birleştiriyoruz
                combined_message = f"{system_message}\n\n{user_message}"
                
                data = {
                    "model": self.model,
                    "message": combined_message,
                    "temperature": self.temperature,
                    "max_tokens": 10
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/generate",
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    result_text = result.get("text", "").strip()
                    logger.info(f"Cohere API response: {result_text}")
                    return self._parse_result(result_text)
                elif response.status_code == 429:
                    logger.warning(f"Cohere API rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)
                    continue
                else:
                    logger.warning(f"Cohere API call failed: {response.status_code} - {response.text}")
                    time.sleep(2)
                    continue
            
            except Exception as e:
                logger.warning(f"API call failed: {str(e)}")
                time.sleep(2)
                continue
    
    def _get_score_azure_openai(self, system_message, user_message):
        """Get relevance score using Azure OpenAI API"""
        while True:
            try:
                # Azure OpenAI için gerekli parametreler
                api_version = self.config.get("providers", {}).get("azure-openai", {}).get("api_version", "2024-02-15-preview")
                
                # Base URL kontrolü
                if not self.base_url:
                    logger.error("Missing base URL for Azure OpenAI")
                    time.sleep(2)
                    continue
                
                # OpenAI client'ı Azure için özel yapılandırma ile başlat
                azure_client_kwargs = {
                    "api_key": self.api_key,
                    "azure_endpoint": self.base_url,
                    "api_version": api_version
                }
                
                azure_client = OpenAI(**azure_client_kwargs)
                
                # Temel istek parametrelerini hazırla
                request_params = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 10
                }
                
                # GPT Thinking modelleri için ek parametreler
                if "thinking" in self.model:
                    request_params["thinking_step"] = True
                    request_params["thinking_content"] = "detailed"
                
                # API isteğini gönder
                response = azure_client.chat.completions.create(**request_params)
                
                # Yanıtı çıkar
                result_text = response.choices[0].message.content.strip()
                logger.info(f"Azure OpenAI response: {result_text}")
                
                # Sonucu işle
                return self._parse_result(result_text)
            
            except Exception as e:
                error_message = str(e)
                logger.warning(f"Azure OpenAI API call failed: {error_message}")
                
                # API rate limit aşıldığında daha uzun süre bekle
                if "429" in error_message or "rate limit" in error_message.lower():
                    logger.warning("Rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)
                else:
                    time.sleep(2)
                
                continue
    
    def _parse_result(self, result_text):
        """Parse the result text to extract the score"""
        try:
            # Log result text being parsed
            logger.info(f"Parsing result text: '{result_text}'")
            
            # Check if result is empty or None
            if not result_text or result_text.strip() == "":
                logger.warning(f"Empty result received, returning default score 4")
                return 4
                
            # Düşünce adımlarını içeren yanıtlar için (GPT-4o Thinking modellerinden gelen yanıtlar için)
            # Sadece son sayıyı al
            if "My answer is:" in result_text:
                last_part = result_text.split("My answer is:")[-1].strip()
                result_text = last_part
                logger.info(f"Extracted answer part: '{result_text}'")
            
            # Gemini 2.0 ve 2.5 modelleri için düşünce özellikli modellerde çıktı format desteği
            if self.provider == "google" and ("thinking" in self.model or self.model.startswith("gemini-2")):
                # Google thinking/gemini-2.x modelleri için düşünce çıktısını temizle
                if "I need to analyze" in result_text or "Let me analyze" in result_text:
                    # Yanıt formatını kontrol et ve son sonucu bulmaya çalış
                    # Tipik Google thinking formatları: "Final answer: 5" veya "Therefore, the score is 5."
                    if "Final answer:" in result_text:
                        final_part = result_text.split("Final answer:")[-1].strip()
                        result_text = final_part
                        logger.info(f"Extracted Google thinking final answer: '{result_text}'")
                    elif "Therefore, the score is" in result_text:
                        final_part = result_text.split("Therefore, the score is")[-1].strip()
                        # Noktalama işaretlerini kaldır
                        final_part = final_part.rstrip('.').strip()
                        result_text = final_part
                        logger.info(f"Extracted Google thinking score part: '{result_text}'")
            
            # Önce direkt sayısal bir değer olup olmadığını kontrol edelim
            result_text = result_text.strip()
            
            # Doğrudan bir sayı ise (1-7 arası)
            try:
                score = int(float(result_text))
                logger.info(f"Relevance score extracted directly as number: {score}")
                
                # Ensure the score is between 1 and 7
                score = max(1, min(7, score))
                return score
            except ValueError:
                logger.info(f"Result is not a direct number, trying other extraction methods")
                pass
            
            # Direkt değilse, metinden bir sayı çıkarmaya çalışalım
            import re
            numbers = re.findall(r'\d+', result_text)
            if numbers:
                try:
                    score = int(float(numbers[0]))
                    
                    # 1-7 dışında bir değer gelirse, aralığa sıkıştır
                    score = max(1, min(7, score))
                    
                    logger.info(f"Relevance score extracted with regex: {score}")
                    return score
                except ValueError:
                    logger.warning(f"Failed to convert regex match to number: {numbers[0]}")
                    pass
            else:
                logger.warning(f"No numeric values found in result text")
            
            # Sayı bulunamazsa, JSON olarak çözümlemeyi deneyelim
            try:
                result = json.loads(result_text)
                score = int(float(result.get("score", 4)))  # Default to middle (4)
                explanation = result.get("explanation", "No explanation provided")
                
                # 1-7 dışında bir değer gelirse, aralığa sıkıştır
                score = max(1, min(7, score))
                
                logger.info(f"Relevance score from JSON: {score}, Explanation: {explanation}")
                return score
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse response as direct number, regex, or JSON: {result_text}")
                
                # Metin içinde bazı anahtar kelimeleri kontrol et
                lower_text = result_text.lower()
                
                # Skor kelimeleri ve karşılık gelen değerler
                score_keywords = {
                    "extremely relevant": 7,
                    "very relevant": 6,
                    "moderately relevant": 5,
                    "somewhat relevant": 4,
                    "slightly relevant": 3,
                    "very slightly relevant": 2,
                    "not relevant": 1
                }
                
                # En yüksek eşleşen skoru bul
                found_score = None
                for keyword, score_value in score_keywords.items():
                    if keyword in lower_text:
                        if found_score is None or score_value > found_score:
                            found_score = score_value
                
                if found_score is not None:
                    logger.info(f"Relevance score extracted from keywords: {found_score}")
                    return found_score
                
                # Tüm yöntemler başarısız oldu, varsayılan değeri döndür
                logger.warning(f"All parsing methods failed, returning default score 4")
                return 4
                
        except Exception as e:
            logger.exception(f"Error parsing result: {str(e)}")
            # Default orta değer (4)
            return 4
    
    def get_relevance_score_with_prompt(self, title, abstract, keywords, topic, custom_prompt, categories=None):
        """
        Get relevance score using a custom prompt
        
        Args:
            title (str): Publication title
            abstract (str): Publication abstract
            keywords (str): Publication keywords
            topic (str): Topic to compare against
            custom_prompt (str): Custom prompt to use for the analysis
            categories (str, optional): Publication categories or subject areas
            
        Returns:
            float: Relevance score between 0 and 1
        """
        try:
            # Process based on provider
            if self.provider == "openai":
                return self._get_score_with_prompt_openai(custom_prompt)
            elif self.provider == "anthropic":
                return self._get_score_with_prompt_anthropic(custom_prompt)
            elif self.provider == "google":
                return self._get_score_with_prompt_google(custom_prompt)
            elif self.provider == "deepseek":
                return self._get_score_with_prompt_deepseek(custom_prompt)
            elif self.provider == "mistral":
                return self._get_score_with_prompt_mistral(custom_prompt)
            elif self.provider == "cohere":
                return self._get_score_with_prompt_cohere(custom_prompt)
            elif self.provider == "azure-openai":
                return self._get_score_with_prompt_azure_openai(custom_prompt)
            else:
                logger.warning(f"Unsupported provider: {self.provider}")
                return 0.0
            
        except Exception as e:
            logger.exception(f"Error getting relevance score: {str(e)}")
            return 0.0
    
    def _get_score_with_prompt_openai(self, custom_prompt):
        """Get relevance score using OpenAI API with custom prompt"""
        # Reasoning modelleri için ayrı işleyici
        if any(self.model.startswith(prefix) for prefix in ["o1", "o3"]):
            return self._get_score_with_prompt_openai_reasoning(custom_prompt)
        
        # Normal OpenAI modelleri için standart işleyici
        while True:
            try:
                # Yeni OpenAI istemci ile API çağrısı
                if not self.openai_client:
                    self._initialize_openai_client()
                
                # OpenAI client kontrolü
                if not self.openai_client:
                    logger.error("OpenAI client not initialized")
                    time.sleep(2)
                    continue
                
                # Prompt'u düzenle - sadece sayı dönmesi için ek bilgi ekle
                enhanced_prompt = f"{custom_prompt}\n\nIMPORTANT: You MUST respond with ONLY a single digit from 1 to 7 representing the relevance score. No other text is allowed."
                
                # Temel istek parametrelerini hazırla
                request_params = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": enhanced_prompt}
                    ],
                    "max_tokens": 10,
                    "temperature": self.temperature
                }
                
                # API isteğini gönder
                logger.info(f"Using OpenAI chat completions API with model: {self.model}")
                logger.debug(f"Request parameters for custom prompt: {request_params}")
                
                response = self.openai_client.chat.completions.create(**request_params)
                
                # Yanıt içeriklerini logla
                logger.debug(f"Response for custom prompt: {response}")
                
                # Extract response
                result_text = response.choices[0].message.content.strip()
                logger.info(f"OpenAI response for custom prompt: '{result_text}'")
                
                # Parse result using our common parser
                return self._parse_result(result_text)
            
            except Exception as e:
                error_message = str(e)
                logger.warning(f"API call failed with custom prompt: {error_message}")
                
                # API rate limit aşıldığında daha uzun süre bekle
                if "429" in error_message or "rate limit" in error_message.lower():
                    logger.warning("Rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)  # Rate limit için 20 saniye bekle
                else:
                    time.sleep(2)  # Normal hatalar için 2 saniye bekle
                
                continue  # Continue the loop to wait for API response
    
    def _get_score_with_prompt_openai_reasoning(self, custom_prompt):
        """
        OpenAI reasoning modelleri (o1, o1-mini, o3-mini, o1-pro) için özel özel promptla skor hesaplama
        Bu fonksiyon test edilen chat.completions API methodu kullanır
        """
        while True:
            try:
                # Yeni OpenAI istemci kontrolü/oluşturma
                if not self.openai_client:
                    self._initialize_openai_client()
                
                if not self.openai_client:
                    logger.error("OpenAI client not initialized")
                    time.sleep(2)
                    continue
                
                # Prompt'u düzenle - sadece sayı dönmesi için ek bilgi ekle
                enhanced_prompt = f"{custom_prompt}\n\nIMPORTANT: You MUST respond with ONLY a single digit from 1 to 7 representing the relevance score. No other text is allowed."
                
                logger.info(f"Using OpenAI reasoning model for custom prompt: {self.model}")
                logger.info(f"Sending request with custom prompt: {enhanced_prompt[:100]}...")
                
                try:
                    # API isteğini gönder - chat.completions API kullanarak
                    response = self.openai_client.chat.completions.create(
                        model=self.model,
                        reasoning_effort="medium",  # Reasoning eforu orta seviye
                        messages=[
                            {
                                "role": "user", 
                                "content": enhanced_prompt
                            }
                        ]
                    )
                    
                    # Yanıtı yazdır ve logla
                    result = response.choices[0].message.content.strip()
                    logger.info(f"Reasoning model response for custom prompt: '{result}'")
                    
                    # Cevabı ayrıştır - sadece sayıyı bul
                    try:
                        # Regex ile yanıtta sayı ara
                        import re
                        number_match = re.search(r'\b([1-7])\b', result)
                        if number_match:
                            score = int(number_match.group(1))
                            logger.info(f"Extracted score from custom prompt: {score}")
                            return score
                        
                        # Sayı bulunamazsa tüm yanıtı _parse_result ile işle
                        logger.warning(f"No direct score found in custom prompt response, parsing full response")
                        return self._parse_result(result)
                        
                    except Exception as parse_error:
                        logger.error(f"Error parsing score from custom prompt response: {str(parse_error)}")
                        # Varsayılan değer döndür
                        return 4
                    
                except Exception as api_error:
                    logger.warning(f"Reasoning API error for custom prompt: {str(api_error)}")
                    
                    # Model bulunamadıysa standart modele geç
                    if "model not found" in str(api_error).lower():
                        logger.warning(f"Model {self.model} not found, falling back to gpt-4o")
                        original_model = self.model
                        self.model = "gpt-4o"
                        
                        # Standart API yöntemiyle dene
                        try:
                            response = self.openai_client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "user", "content": enhanced_prompt}
                                ],
                                max_tokens=10,
                                temperature=0
                            )
                            
                            result_text = response.choices[0].message.content.strip()
                            logger.info(f"Fallback API response for custom prompt: '{result_text}'")
                            
                            # Modeli geri set et
                            self.model = original_model
                            
                            return self._parse_result(result_text)
                        except Exception as fallback_error:
                            logger.error(f"Fallback API error for custom prompt: {str(fallback_error)}")
                            self.model = original_model
                            # Varsayılan değer döndür
                            return 4
                    
                    # Rate limit hatasında bekle
                    if "429" in str(api_error) or "rate limit" in str(api_error).lower():
                        logger.warning("Rate limit exceeded, waiting 20 seconds before retry...")
                        time.sleep(20)
                        continue
                    
                    # Diğer hatalarda varsayılan değer döndür
                    logger.error(f"Unknown API error for custom prompt: {str(api_error)}")
                    return 4
                    
            except Exception as e:
                logger.error(f"General error in reasoning model score calculation for custom prompt: {str(e)}")
                return 4
    
    def _get_score_with_prompt_anthropic(self, custom_prompt):
        """Get relevance score using Anthropic API with custom prompt"""
        while True:
            try:
                # Modern Anthropic kütüphanesi ile dene
                if hasattr(self, 'anthropic_client') and self.anthropic_client:
                    try:
                        # Her zaman messages.create kullan
                        logger.info(f"Using Anthropic SDK messages.create for custom prompt with model: {self.model}")
                        response = self.anthropic_client.messages.create(
                            model=self.model,
                            # System prompt is not used here as it's part of the custom_prompt
                            messages=[
                                {"role": "user", "content": custom_prompt} # Send the full custom prompt as user content
                            ],
                            temperature=self.temperature,
                            max_tokens=10 # Reduced tokens for score
                        )
                        
                        # Yanıtı işle (Claude 3.x formatı varsayılır)
                        if response.content and isinstance(response.content, list) and len(response.content) > 0:
                            result_text = response.content[0].text.strip()
                            logger.info(f"Anthropic SDK response for custom prompt: {result_text}")
                            return self._parse_result(result_text)
                        else:
                            logger.warning(f"Unexpected Anthropic SDK response format for custom prompt: {response}")
                            raise Exception("Unexpected SDK response format") # Force fallback

                    except Exception as sdk_error:
                        logger.warning(f"Anthropic SDK error for custom prompt: {str(sdk_error)}, falling back to REST API")
                        # SDK hata verirse veya format uymazsa REST API'ye geri dön
                
                # --- REST API Fallback --- 
                logger.info("Attempting Anthropic custom prompt request via REST API")
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01", # Corrected API version
                    "content-type": "application/json"
                }
                
                # For custom prompts, the system part is usually included within the prompt itself.
                # We send the entire custom_prompt as a single user message.
                data = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": custom_prompt} 
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 10 # Reduced tokens for score
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/messages", # Use messages endpoint
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                # Check REST response
                if response.status_code == 200:
                    result = response.json()
                    if "content" in result and isinstance(result["content"], list) and len(result["content"]) > 0:
                        result_text = result["content"][0].get("text", "").strip()
                        logger.info(f"Anthropic REST API response for custom prompt: {result_text}")
                        return self._parse_result(result_text)
                    else:
                        logger.warning(f"Unexpected Anthropic REST API response format for custom prompt: {result}")
                elif response.status_code == 429:
                    logger.warning("Anthropic API rate limit exceeded for custom prompt, waiting 20 seconds before retry...")
                    time.sleep(20)
                    continue # Retry loop
                else:
                    # Log other HTTP errors from REST API
                    logger.warning(f"Anthropic REST API custom prompt call failed: {response.status_code} - {response.text}")
                    time.sleep(2)
                    continue # Retry loop

            except Exception as e:
                 # General errors (network issues, etc.)
                logger.warning(f"Anthropic API custom prompt call failed: {str(e)}")
                time.sleep(2)
                continue # Retry loop
    
    def _get_score_with_prompt_google(self, custom_prompt):
        """Get relevance score using Google Gen AI API with custom prompt"""
        try:
            if not self.google_client:
                if not self._initialize_client():
                     logger.error("Google client could not be initialized.")
                     return 4

            # Log and send the query
            logger.info(f"Sending custom prompt to Google Gen AI API: {self.model}")
            
            # Yeni API call formatı
            response = self.google_client.models.generate_content(
                model=self.model,
                contents=custom_prompt
            )
            
            # Process response
            logger.debug(f"Full Google API response: {response}")
            if hasattr(response, 'text') and response.text:
                result_text = response.text.strip()
                logger.info(f"Google response: {result_text}")
                return self._parse_result(result_text)
            else:
                logger.warning(f"Unexpected Google API response format or no text: {response}")
                # Safety feedback kontrolü (eski format uyumluluğu)
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason'):
                    logger.warning(f"Request blocked: {response.prompt_feedback.block_reason}")
                return 4  # Default score
                
        except Exception as e:
            logger.error(f"Error with Google API call: {str(e)}")
            if "model" in str(e).lower() and "not found" in str(e).lower():
                 logger.warning(f"Model {self.model} not found for custom prompt, falling back to gemini-1.5-flash")
                 self.model = "gemini-1.5-flash"
            return 4
    
    def _get_score_with_prompt_deepseek(self, custom_prompt):
        """Get relevance score using DeepSeek API with custom prompt"""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                # DeepSeek-Reasoner için farklı format kullan
                if self.model == "deepseek-reasoner":
                    logger.info(f"Using DeepSeek Reasoner model with special format for custom prompt")
                    
                    # DeepSeek Reasoner için API isteğini hazırla
                    data = {
                        "model": "deepseek-reasoner",
                        "messages": [
                            {"role": "user", "content": custom_prompt}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": 20,  # Sadece skorun dönmesi için kısa tutuyoruz
                        "top_p": 0.95
                    }
                    
                    # DeepSeek Reasoner için doğru endpoint kullan
                    url = f"{self.base_url}/v1/chat/completions"
                    
                    logger.debug(f"DeepSeek Reasoner API Custom Prompt Request URL: {url}")
                    logger.debug(f"DeepSeek Reasoner API Custom Prompt Request Data: {data}")
                    
                    response = requests.post(
                        url,
                        headers=headers,
                        json=data,
                        timeout=self.timeout
                    )
                else:
                    # Standart DeepSeek modelleri için
                    data = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": custom_prompt}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": 20
                    }
                    
                    response = requests.post(
                        f"{self.base_url}/v1/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=self.timeout
                    )
                
                # Yanıt durum kodunu kontrol et ve logla
                logger.debug(f"DeepSeek API Custom Prompt Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Yanıt logla
                    logger.debug(f"DeepSeek API Custom Prompt Response: {result}")
                    
                    # Yanıt formatını kontrol et
                    if "choices" in result and len(result["choices"]) > 0:
                        result_text = result["choices"][0]["message"]["content"].strip()
                        logger.info(f"DeepSeek response for custom prompt: {result_text}")
                        return self._parse_result(result_text)
                    else:
                        logger.warning(f"Unexpected DeepSeek API response format for custom prompt: {result}")
                        time.sleep(2)
                        continue
                elif response.status_code == 400:
                    error_text = response.text
                    logger.warning(f"DeepSeek API custom prompt error 400: {error_text}")
                    
                    # Hata mesajını detaylı inceleme
                    if "model parameter" in error_text.lower() or "model not found" in error_text.lower():
                        logger.warning(f"Model {self.model} not supported for custom prompt, falling back to deepseek-chat")
                        self.model = "deepseek-chat"
                        continue
                    elif "api key" in error_text.lower() or "authentication" in error_text.lower():
                        logger.error("DeepSeek API authentication error for custom prompt - invalid API key")
                        return 4  # Authentication error, return default score
                    
                    # Diğer 400 hataları için bekleme ve yeniden deneme
                    time.sleep(2)
                    continue
                elif response.status_code == 429:
                    logger.warning(f"DeepSeek API çağrısı başarısız: {response.status_code} - {response.text}")
                    logger.warning("DeepSeek API rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)  # Rate limit için 20 saniye bekle
                    continue
                else:
                    logger.warning(f"DeepSeek API call failed: {response.status_code}")
                    time.sleep(2)  # Normal hatalar için 2 saniye bekle
                    continue
            
            except Exception as e:
                logger.warning(f"API call failed: {str(e)}")
                time.sleep(2)  # Normal hatalar için 2 saniye bekle
                continue
    
    def _get_score_with_prompt_mistral(self, custom_prompt):
        """Get relevance score using Mistral AI API with custom prompt"""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                data = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": custom_prompt}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 10
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    result_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logger.info(f"Mistral AI response for custom prompt: {result_text}")
                    return self._parse_result(result_text)
                elif response.status_code == 429:
                    logger.warning(f"Mistral AI API rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)
                    continue
                else:
                    logger.warning(f"Mistral AI API call failed: {response.status_code} - {response.text}")
                    time.sleep(2)
                    continue
            
            except Exception as e:
                logger.warning(f"API call failed: {str(e)}")
                time.sleep(2)
                continue
    
    def _get_score_with_prompt_cohere(self, custom_prompt):
        """Get relevance score using Cohere API with custom prompt"""
        while True:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json"
                }
                
                # Cohere farklı bir API formatı kullanıyor
                # Sistem ve kullanıcı mesajlarını birleştiriyoruz
                combined_message = f"{custom_prompt}\n\n{self.model}"
                
                data = {
                    "model": self.model,
                    "message": combined_message,
                    "temperature": self.temperature,
                    "max_tokens": 10
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/generate",
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    result_text = result.get("text", "").strip()
                    logger.info(f"Cohere API response for custom prompt: {result_text}")
                    return self._parse_result(result_text)
                elif response.status_code == 429:
                    logger.warning(f"Cohere API rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)
                    continue
                else:
                    logger.warning(f"Cohere API call failed: {response.status_code} - {response.text}")
                    time.sleep(2)
                    continue
            
            except Exception as e:
                logger.warning(f"API call failed: {str(e)}")
                time.sleep(2)
                continue
    
    def _get_score_with_prompt_azure_openai(self, custom_prompt):
        """Get relevance score using Azure OpenAI API with custom prompt"""
        while True:
            try:
                # Azure OpenAI için gerekli parametreler
                api_version = self.config.get("providers", {}).get("azure-openai", {}).get("api_version", "2024-02-15-preview")
                
                # Base URL kontrolü
                if not self.base_url:
                    logger.error("Missing base URL for Azure OpenAI")
                    time.sleep(2)
                    continue
                
                # OpenAI client'ı Azure için özel yapılandırma ile başlat
                azure_client_kwargs = {
                    "api_key": self.api_key,
                    "azure_endpoint": self.base_url,
                    "api_version": api_version
                }
                
                azure_client = OpenAI(**azure_client_kwargs)
                
                # Temel istek parametrelerini hazırla
                request_params = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": custom_prompt}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 10
                }
                
                # GPT Thinking modelleri için ek parametreler
                if "thinking" in self.model:
                    request_params["thinking_step"] = True
                    request_params["thinking_content"] = "detailed"
                
                # API isteğini gönder
                response = azure_client.chat.completions.create(**request_params)
                
                # Yanıtı çıkar
                result_text = response.choices[0].message.content.strip()
                logger.info(f"Azure OpenAI response for custom prompt: {result_text}")
                
                # Sonucu işle
                return self._parse_result(result_text)
            
            except Exception as e:
                error_message = str(e)
                logger.warning(f"Azure OpenAI API call failed: {error_message}")
                
                # API rate limit aşıldığında daha uzun süre bekle
                if "429" in error_message or "rate limit" in error_message.lower():
                    logger.warning("Rate limit exceeded, waiting 20 seconds before retry...")
                    time.sleep(20)
                else:
                    time.sleep(2)
                
                continue
    
    def update_model_combo(self):
        """Update the model combo box based on selected provider"""
        # Clear existing items
        self.model_combo.clear()
        
        # Get models for the current provider
        provider_config = self.config.get("providers", {}).get(self.provider, {})
        models = provider_config.get("models", [])
        active_model = provider_config.get("active_model", "")
        
        # Add models to combo box
        self.model_combo.addItems(models)
        
        # Set current model if it exists in the list
        if active_model in models:
            self.model_combo.setCurrentText(active_model)
            
    def on_provider_changed(self, index):
        """Handle provider selection change"""
        provider_map = {
            0: "openai",
            1: "anthropic",
            2: "google", 
            3: "deepseek"
        }
        
        # Update the provider in the processor
        self.provider = provider_map.get(index, "openai")
        
        # Anthropic sağlayıcısı seçildiyse ve SDK varsa güncel modelleri çek
        if self.provider == "anthropic" and hasattr(self, 'anthropic_client') and self.anthropic_client:
            try:
                self.fetch_anthropic_models()
            except Exception as e:
                logger.warning(f"Error fetching Anthropic models after provider change: {str(e)}")
        
        # Show the current provider's settings
        self.show_current_provider_settings()
        
        # Update the models dropdown
        self.update_model_combo()
        
        # Değişiklik sonrası API anahtarını doğrudan yükleme
        current_provider = self.provider
        if "providers" in self.config and current_provider in self.config["providers"]:
            prov_config = self.config["providers"][current_provider]
            self.api_key = prov_config.get("api_key", "")
            self.base_url = prov_config.get("base_url", "")
            self.model = prov_config.get("active_model", "")

    def fetch_anthropic_models(self):
        """Anthropic API'dan mevcut modelleri çeker"""
        if not hasattr(self, 'anthropic_client') or not self.anthropic_client:
            logger.warning("Anthropic client not initialized, cannot fetch models")
            return

        try:
            # Modelleri API'dan çek
            logger.info("Fetching available Anthropic models from API")
            models_response = self.anthropic_client.models.list(limit=20)
            
            # Modelleri listeye ekle
            model_ids = [model.id for model in models_response.data]
            
            if model_ids:
                logger.info(f"Successfully fetched {len(model_ids)} Anthropic models: {model_ids}")
                
                # Config'e kaydet
                if "providers" in self.config and "anthropic" in self.config["providers"]:
                    # Mevcut modelleri koru ancak API'dan gelen modelleri ekle
                    current_models = self.config["providers"]["anthropic"].get("models", [])
                    
                    # API'dan gelen modelleri listeye ekle (tekrar etmeyecek şekilde)
                    for model_id in model_ids:
                        if model_id not in current_models:
                            current_models.append(model_id)
                    
                    # Güncellenmiş model listesini kaydet
                    self.config["providers"]["anthropic"]["models"] = current_models
                    
                    # Eğer active_model ayarlanmamışsa ilk modeli kullan
                    if not self.config["providers"]["anthropic"].get("active_model"):
                        self.config["providers"]["anthropic"]["active_model"] = model_ids[0]
                        
                    logger.info(f"Updated Anthropic models in config: {current_models}")
                    
                    # Eğer bu mevcut sağlayıcı ise self.model'i de güncelle
                    if self.provider == "anthropic":
                        active_model = self.config["providers"]["anthropic"].get("active_model")
                        if active_model:
                            self.model = active_model
        except Exception as e:
            logger.error(f"Error fetching Anthropic models: {str(e)}")
            # Hata durumunda varsayılan modellere geri dön

    def _update_provider_models(self):
        """Mevcut modellerin listesini günceller"""
        try:
            # OpenAI modelleri - 4.1 ve reasoning modelleri
            openai_models = [
                "gpt-4.1",
                "gpt-4.1-mini",
                "gpt-4.1-nano",
                "o1",
                "o1-mini",
                "o3-mini",
                "o1-pro"
            ]
            
            # Anthropic modelleri
            anthropic_models = [
                "claude-opus-4-20250514",
                "claude-sonnet-4-20250514",
                "claude-3-7-sonnet-20250219",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-5-sonnet-20240620",
                "claude-3-haiku-20240307",
                "claude-3-opus-20240229"
            ]
            
            # Google modelleri - Gen AI SDK ile uyumlu modeller
            google_models = [
                # 2.5 Series - Preview/Experimental
                "gemini-2.5-flash-preview-05-20",
                "gemini-2.5-flash-preview-native-audio-dialog",
                "gemini-2.5-flash-exp-native-audio-thinking-dialog",
                "gemini-2.5-flash-preview-tts",
                "gemini-2.5-pro-preview-05-06",
                "gemini-2.5-pro-preview-tts",
                # 2.0 Series - Stable
                "gemini-2.0-flash",
                "gemini-2.0-flash-preview-image-generation",
                "gemini-2.0-flash-lite",
                # 1.5 Series - Stable
                "gemini-1.5-flash",
                "gemini-1.5-flash-8b",
                "gemini-1.5-pro",
                # Embedding Models
                "gemini-embedding-exp",
                "text-embedding-004",
                "embedding-001",
                # Special Models
                "aqa"
            ]
            
            # DeepSeek modelleri
            deepseek_models = [
                "deepseek-reasoner",
                "deepseek-chat", 
                "deepseek-coder",
                "deepseek-llm-67b-chat"
            ]
            
            # Mistral modelleri
            mistral_models = [
                "mistral-large-latest",
                "mistral-medium-latest", 
                "mistral-small-latest",
                "open-mistral-7b"
            ]
            
            # Cohere modelleri
            cohere_models = [
                "command-r-plus",
                "command-r", 
                "command-light"
            ]
            
            # Azure OpenAI modelleri
            azure_openai_models = [
                "gpt-4",
                "gpt-4-turbo",
                "gpt-35-turbo"
            ]
            
            # Modelleri config'e ekle
            if "providers" in self.config:
                # OpenAI
                if "openai" in self.config["providers"]:
                    self.config["providers"]["openai"]["models"] = openai_models
                
                # Anthropic
                if "anthropic" in self.config["providers"]:
                    self.config["providers"]["anthropic"]["models"] = anthropic_models
                
                # Google
                if "google" in self.config["providers"]:
                    self.config["providers"]["google"]["models"] = google_models
                
                # DeepSeek
                if "deepseek" in self.config["providers"]:
                    self.config["providers"]["deepseek"]["models"] = deepseek_models
                
                # Mistral
                if "mistral" in self.config["providers"]:
                    self.config["providers"]["mistral"]["models"] = mistral_models
                
                # Cohere
                if "cohere" in self.config["providers"]:
                    self.config["providers"]["cohere"]["models"] = cohere_models
                
                # Azure OpenAI
                if "azure-openai" in self.config["providers"]:
                    self.config["providers"]["azure-openai"]["models"] = azure_openai_models
        except Exception as e:
            logger.error(f"Error updating provider models: {str(e)}")
    
    def _set_attributes_from_config(self, model, api_key, base_url, temperature, timeout):
        """Set the processor attributes from the configuration"""
        # Get provider config
        provider_config = self.config.get("providers", {}).get(self.provider, {})
        
        # Set model - use parameter if provided, otherwise use from config
        self.model = model or provider_config.get("active_model", "")
        
        # Set API key - use parameter if provided, otherwise use from config
        self.api_key = api_key or provider_config.get("api_key", "")
        
        # Set base URL - use parameter if provided, otherwise use from config
        self.base_url = base_url or provider_config.get("base_url", "")
        
        # Set temperature - use parameter if provided, otherwise use from config
        settings = self.config.get("settings", {})
        self.temperature = temperature if temperature is not None else settings.get("temperature", 0.2)
        
        # Set timeout - use parameter if provided, otherwise use from config
        self.timeout = timeout if timeout is not None else settings.get("timeout", 30)
        
        # Log the attributes for debugging
        logger.info(f"Provider: {self.provider}")
        logger.info(f"Model: {self.model}")
        logger.info(f"API Key present: {bool(self.api_key)}")
        logger.info(f"Base URL: {self.base_url if self.base_url else 'Default'}")
        logger.info(f"Temperature: {self.temperature}")
        logger.info(f"Timeout: {self.timeout}")