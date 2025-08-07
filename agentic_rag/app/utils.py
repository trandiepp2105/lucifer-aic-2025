"""
Utility functions for the Agentic RAG system.
"""
import json
import re
import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


def robust_json_parse(text: str, fallback_value: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Robust JSON parsing with multiple fallback strategies.
    
    Args:
        text: The text to parse as JSON
        fallback_value: Default value to return if all parsing fails
        
    Returns:
        Parsed JSON dictionary or fallback value
    """
    if fallback_value is None:
        fallback_value = {"error": "Failed to parse JSON", "raw_text": text}
    
    # Strategy 1: Direct JSON parsing
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Find JSON within text
    try:
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # Strategy 3: Try to find multiple JSON objects
    try:
        json_objects = re.findall(r'\{[^{}]*\}', text)
        for json_str in json_objects:
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    
    # Strategy 4: Create structured response from text analysis
    try:
        return create_structured_response_from_text(text)
    except Exception:
        pass
    
    logger.warning(f"All JSON parsing strategies failed for text: {text[:200]}...")
    return fallback_value


def create_structured_response_from_text(text: str) -> Dict[str, Any]:
    """
    Create a structured response by analyzing text content.
    
    Args:
        text: The text to analyze
        
    Returns:
        Structured dictionary with extracted information
    """
    text_lower = text.lower()
    
    # Determine is_match
    is_match = False
    positive_indicators = ['có', 'khớp', 'true', 'đúng', 'phù hợp', 'tìm thấy', 'match', 'yes']
    negative_indicators = ['không', 'sai', 'false', 'không phù hợp', 'không khớp', 'no match', 'no']
    
    if any(indicator in text_lower for indicator in positive_indicators):
        is_match = True
    elif any(indicator in text_lower for indicator in negative_indicators):
        is_match = False
    
    # Extract confidence score
    confidence_score = 0.5  # Default
    confidence_patterns = [
        r'confidence[:\s]*(\d+\.?\d*)%?',
        r'điểm số[:\s]*(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*%',
        r'(\d+\.?\d*)/10',
        r'(\d+\.?\d*)/100'
    ]
    
    for pattern in confidence_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                score = float(matches[0])
                if score > 1.0:
                    score = score / 100.0  # Convert percentage
                confidence_score = min(1.0, max(0.0, score))
                break
            except ValueError:
                continue
    
    # Extract frame URLs
    frames = []
    url_pattern = r'http[s]?://[^\s\'"<>]+'
    urls = re.findall(url_pattern, text)
    frames.extend(urls)
    
    return {
        "is_match": is_match,
        "confidence_score": confidence_score,
        "reasoning": text,
        "frames": frames
    }


def extract_frame_urls(text: str) -> list:
    """
    Extract frame URLs from text.
    
    Args:
        text: Text to search for URLs
        
    Returns:
        List of frame URLs found
    """
    url_pattern = r'http[s]?://[^\s\'"<>]+'
    return re.findall(url_pattern, text)


def safe_get_nested(data: Dict[str, Any], keys: list, default: Any = None) -> Any:
    """
    Safely get nested dictionary values.
    
    Args:
        data: Dictionary to search
        keys: List of keys for nested access
        default: Default value if key path doesn't exist
        
    Returns:
        Value at the key path or default
    """
    try:
        current = data
        for key in keys:
            current = current[key]
        return current
    except (KeyError, TypeError):
        return default


def strip_markdown_code_fences(text: str) -> str:
    """
    Remove markdown code fences from text to extract plain JSON.
    
    This function handles cases where LLM agents output JSON wrapped in markdown
    code fences like ```json ... ``` or ``` ... ```.
    
    Args:
        text: Input text that may contain markdown-wrapped JSON
        
    Returns:
        Clean text with code fences removed
    """
    text = text.strip()
    
    # Pattern to match markdown code fences with optional language identifier
    # Matches: ```json, ```JSON, ```, etc.
    pattern = r'^```(?:json|JSON)?\s*\n?(.*?)\n?```$'
    
    match = re.match(pattern, text, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    return text