"""
Agentic RAG Video Retrieval System

A sophisticated agent-based system for video retrieval using natural language descriptions,
powered by Google Gemini and LangGraph.
"""

__version__ = "2.0.0"
__author__ = "Agentic RAG Team"
__description__ = "Agent Truy xuất và Xác thực Video với Gemini"

from .config import config
from .agent_core import get_agent, reset_agent
from .schemas import VideoSearchRequest, VideoSearchResponse, ErrorResponse

__all__ = [
    "config",
    "get_agent", 
    "reset_agent",
    "VideoSearchRequest",
    "VideoSearchResponse", 
    "ErrorResponse"
]
