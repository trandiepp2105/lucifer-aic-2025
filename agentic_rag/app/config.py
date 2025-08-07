"""
Configuration management for the Agentic RAG system.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Central configuration class for all environment variables and settings."""
    
    # API Keys
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    
    # External API URLs
    SEARCH_API_URL: str = os.getenv("SEARCH_API_URL", "http://35.194.169.93/search")
    MEDIA_API_URL: str = os.getenv("MEDIA_API_URL", "http://35.194.169.93/media/frames")
    
    # Gemini Configuration
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-pro-vision")
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))
    GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "2048"))
    
    # Application Settings
    APP_NAME: str = "Agentic RAG Video Retrieval"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Video Processing
    MAX_FRAMES_TO_EXTRACT: int = int(os.getenv("MAX_FRAMES_TO_EXTRACT", "3"))
    FRAME_EXTRACTION_INTERVALS: list = [1, 5, 10]  # seconds
    
    # Request timeouts
    API_REQUEST_TIMEOUT: int = int(os.getenv("API_REQUEST_TIMEOUT", "30"))
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate that all required configuration is present."""
        required_configs = [
            ("GOOGLE_API_KEY", cls.GOOGLE_API_KEY),
        ]
        
        missing_configs = []
        for config_name, config_value in required_configs:
            if not config_value:
                missing_configs.append(config_name)
        
        if missing_configs:
            raise ValueError(f"Missing required configuration: {', '.join(missing_configs)}")
        
        return True


# Global configuration instance
config = Config()
