"""
Constants and configuration settings for the Agentic RAG tools.
Contains prompt templates, JSON formats, and Gemini API configurations.
"""

import google.generativeai as genai
from .config import config

# Constants for prompts and configurations
COMMON_REQUIREMENTS = """
Yêu cầu:
- Nên đầy đủ các chi tiết của câu query.
- Về phần phương hướng thì không cần tuyệt đối (khoảng 50% thôi, tuy nhiên các yếu tố như hướng của mũi tên thì nên 90%).
- Lưu ý bạn valid frame nên các yếu tố liên quan đến sự chuyển động, hướng đi, etc. không cần quá chính xác, chỉ cần khớp với mô tả chung.
"""

JSON_OUTPUT_FORMATS = {
    "basic_validation": """{{
    "is_match": true/false,
    "confidence_score": 0.0-1.0,
    "reasoning": "Giải thích chi tiết",
    "relevant_frames": ["frame_1", "frame_2", ...]
}}""",
    "enhanced_grid": """{
    "overall_match": boolean,
    "confidence_score": float (0.0-1.0),
    "reasoning": "string",
    "group_results": [
        {
            "group_id": int,
            "is_match": boolean,
            "confidence_score": float,
            "reasoning": "string",
            "key_observations": ["string"]
        }
    ],
    "comparison_insights": "string",
    "best_matching_group": int (optional),
    "recommendations": ["string"]
}"""
}

# Gemini configuration constants
GEMINI_GENERATION_CONFIG = genai.types.GenerationConfig(
    temperature=0.1,
    max_output_tokens=config.GEMINI_MAX_TOKENS,
    top_p=0.8,
    top_k=40,
)

GEMINI_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# API configuration
MAX_RETRIES = 3
DEFAULT_TIMEOUT = (5, 120)  # (connect_timeout, read_timeout)
MAX_IMAGE_DIMENSION = 1024
