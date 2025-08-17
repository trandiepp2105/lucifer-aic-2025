"""
Utility functions for the Agentic RAG tools.
Contains helper functions for Gemini API calls, image processing, and API requests.
"""

import json
import logging
import io
import os
import time
from typing import List, Dict, Any, Optional, Tuple
import requests
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
import httpx

from .config import config
from .constants import (
    COMMON_REQUIREMENTS, 
    JSON_OUTPUT_FORMATS, 
    GEMINI_GENERATION_CONFIG, 
    GEMINI_SAFETY_SETTINGS,
    MAX_RETRIES,
    DEFAULT_TIMEOUT,
    MAX_IMAGE_DIMENSION
)
from .utils import robust_json_parse

# Configure logging
logger = logging.getLogger(__name__)


def log_gemini_response_details(response, context=""):
    """
    Helper function to log detailed information about Gemini response,
    especially when there are no candidates returned.
    """
    try:
        logger.info(f"=== Gemini Response Details ({context}) ===")
        
        # Check if response has candidates
        has_candidates = hasattr(response, 'candidates') and response.candidates
        logger.info(f"Has candidates: {has_candidates}")
        
        if has_candidates:
            logger.info(f"Number of candidates: {len(response.candidates)}")
            for i, candidate in enumerate(response.candidates):
                finish_reason = getattr(candidate, 'finish_reason', 'unknown')
                logger.info(f"Candidate {i} finish_reason: {finish_reason}")
                
                # Log safety ratings if available
                if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                    logger.info(f"Candidate {i} safety ratings:")
                    for rating in candidate.safety_ratings:
                        logger.info(f"  - {rating.category}: {rating.probability}")
        
        # Always check prompt feedback
        if hasattr(response, 'prompt_feedback'):
            feedback = response.prompt_feedback
            logger.info(f"Prompt feedback: {feedback}")
            
            if hasattr(feedback, 'block_reason') and feedback.block_reason:
                logger.error(f"Block reason: {feedback.block_reason}")
            
            if hasattr(feedback, 'safety_ratings') and feedback.safety_ratings:
                logger.info("Prompt safety ratings:")
                for rating in feedback.safety_ratings:
                    logger.info(f"  - {rating.category}: {rating.probability}")
        else:
            logger.info("No prompt feedback available")
            
        logger.info("=== End Gemini Response Details ===")
        
    except Exception as e:
        logger.error(f"Error logging Gemini response details: {e}")


def create_prompt_with_requirements(base_prompt: str, json_format: str, include_requirements: bool = True) -> str:
    """
    Helper function to create standardized prompts with common requirements and JSON format.
    """
    parts = [base_prompt]
    
    if include_requirements:
        parts.append(COMMON_REQUIREMENTS)
    
    parts.append(f"Trả về kết quả chính xác theo định dạng JSON sau:\n{json_format}")
    parts.append("CHỈ trả về JSON, không thêm text nào khác.")
    
    return "\n".join(parts)


def prepare_image_for_gemini(image: Image.Image, max_dim: int = MAX_IMAGE_DIMENSION) -> bytes:
    """
    Helper function to prepare image for Gemini API call.
    """
    # Resize image to reduce block probability
    if image.width > max_dim or image.height > max_dim:
        image = image.copy()
        image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()


def call_gemini_with_retry(prompt: str, image_data: bytes, context: str = "") -> Dict[str, Any]:
    """
    Helper function to call Gemini API with retry logic for empty responses.
    Returns structured result dict.
    """
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    
    try:
        response = model.generate_content(
            [prompt, {"mime_type": "image/png", "data": image_data}],
            generation_config=GEMINI_GENERATION_CONFIG,
            safety_settings=GEMINI_SAFETY_SETTINGS
        )
        
        # Debug chi tiết response
        log_gemini_response_details(response, context)
        
        try:
            # Check if response has candidates first
            if not hasattr(response, 'candidates') or not response.candidates:
                logger.error(f"{context}: Gemini returned no candidates!")
                response_text = ""
            else:
                response_text = response.text.strip() if response.text else ""
                logger.info(f"Gemini {context} raw response: '{response.text}'")
                logger.info(f"Gemini {context} cleaned response: '{response_text}'")
                logger.info(f"Response length: {len(response_text)}")
                
        except Exception as e:
            logger.error(f"Error accessing response text for {context}: {e}")
            response_text = ""

        # Nếu response rỗng, thử lại với prompt đơn giản hơn
        if not response_text or len(response_text) < 10:
            logger.warning(f"Empty response for {context}, trying simplified prompt...")
            
            simplified_prompt = f"""Nhìn vào ảnh này và phân tích.

{COMMON_REQUIREMENTS}

Trả về JSON: {{"is_match": true/false, "confidence_score": 0.5, "reasoning": "your analysis"}}"""
            
            try:
                retry_response = model.generate_content(
                    [simplified_prompt, {"mime_type": "image/png", "data": image_data}],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=config.GEMINI_MAX_TOKENS,
                    ),
                    safety_settings=GEMINI_SAFETY_SETTINGS
                )
                
                log_gemini_response_details(retry_response, f"{context}_retry")
                
                if not hasattr(retry_response, 'candidates') or not retry_response.candidates:
                    logger.error(f"Retry: Gemini returned no candidates for {context}!")
                else:
                    if retry_response.text and retry_response.text.strip():
                        response_text = retry_response.text.strip()
                        logger.info(f"Retry response for {context}: {response_text}")
                    else:
                        logger.error(f"Retry returned empty response text for {context}")
                        
            except Exception as retry_e:
                logger.error(f"Retry request failed for {context}: {retry_e}")

        return {
            "success": bool(response_text),
            "response_text": response_text,
            "image_size": len(image_data)
        }
            
    except Exception as e:
        logger.error(f"Error calling Gemini for {context}: {e}")
        return {
            "success": False,
            "response_text": "",
            "error": str(e),
            "image_size": len(image_data)
        }


def make_search_api_request(form_data: Dict, files: List = None) -> Dict[str, Any]:
    """
    Helper function to make search API requests with consistent error handling.
    """
    try:
        response = requests.post(
            config.SEARCH_API_URL,
            data=form_data,
            files=files if files else None,
            timeout=config.API_REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            try:
                results = response.json()
                logger.info(f"Search API returned {results.get('results_found', 0)} results.")
                return {"success": True, "data": results}
            except Exception as e:
                logger.error(f"Error decoding JSON from search API: {e}")
                return {"success": False, "error": f"Lỗi giải mã kết quả từ API: {str(e)}"}
        else:
            error_msg = f"Search API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {"success": False, "error": f"Lỗi API tìm kiếm: {error_msg}"}
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error calling search API: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": f"Lỗi kết nối API tìm kiếm: {error_msg}"}


def get_frames_from_urls(frame_urls: List[str]) -> List[Image.Image]:
    """
    Utility function: Lấy một hoặc nhiều khung hình (frame) cụ thể từ media server.
    """
    images = []
    
    # Add proper headers and session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    for frame_url in frame_urls:
        logger.info(f"Get frame from media URL: {frame_url}")
        full_url = f"{config.MEDIA_API_URL}/{frame_url}"
        logger.info(f"Full URL: {full_url}")
        
        # Retry logic
        for attempt in range(MAX_RETRIES):
            try:
                response = session.get(
                    full_url, 
                    timeout=DEFAULT_TIMEOUT,
                    stream=True
                )
                response.raise_for_status()
                
                # Use BytesIO instead of direct response.content
                image_data = io.BytesIO(response.content)
                image = Image.open(image_data)
                images.append(image)
                break
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"Attempt {attempt + 1} failed for {frame_url}: {e}")
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"All retries failed for frame {frame_url}")
                    images.append(None)
                else:
                    time.sleep(2)  # Wait before retry
            except Exception as e:
                logger.error(f"Error processing frame {frame_url}: {e}")
                images.append(None)
                break
    
    return images


def create_grid_from_images(pil_images: List[Image.Image], grid_dimensions: Tuple[int, int]) -> Image.Image:
    """
    Helper function to create a grid image from a list of PIL images.
    """
    rows, cols = grid_dimensions
    
    if len(pil_images) > rows * cols:
        pil_images = pil_images[:rows * cols]

    max_width = max(img.width for img in pil_images)
    max_height = max(img.height for img in pil_images)

    grid_width = cols * max_width
    grid_height = rows * max_height
    grid_image = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))

    for i, img in enumerate(pil_images):
        row = i // cols
        col = i % cols
        x_offset = col * max_width
        y_offset = row * max_height
        
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        grid_image.paste(img, (x_offset, y_offset))

    return grid_image


def create_separate_grids(all_group_images: List[List[Image.Image]], grid_dims: Tuple[int, int], group_info: List[Dict]) -> Image.Image:
    """Create separate grids for each group with labels."""
    rows_per_grid, cols_per_grid = grid_dims
    
    # Calculate dimensions
    max_width = max(img.width for group_images in all_group_images for img in group_images)
    max_height = max(img.height for group_images in all_group_images for img in group_images)
    
    grid_width = cols_per_grid * max_width
    grid_height = rows_per_grid * max_height
    total_grid_height = grid_height + 50  # Add space for labels
    
    # Calculate final image dimensions
    num_groups = len(all_group_images)
    groups_per_row = min(3, num_groups)  # Max 3 groups per row
    num_rows = (num_groups + groups_per_row - 1) // groups_per_row
    
    final_width = groups_per_row * grid_width
    final_height = num_rows * total_grid_height
    
    # Create final image
    final_image = Image.new('RGB', (final_width, final_height), color=(240, 240, 240))
    draw = ImageDraw.Draw(final_image)
    
    # Try to load font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    for group_idx, (group_images, info) in enumerate(zip(all_group_images, group_info)):
        # Calculate position for this group
        row = group_idx // groups_per_row
        col = group_idx % groups_per_row
        
        group_x = col * grid_width
        group_y = row * total_grid_height
        
        # Create grid for this group
        group_grid = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        
        for img_idx, img in enumerate(group_images[:rows_per_grid * cols_per_grid]):
            img_row = img_idx // cols_per_grid
            img_col = img_idx % cols_per_grid
            
            x_offset = img_col * max_width
            y_offset = img_row * max_height
            
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            group_grid.paste(img, (x_offset, y_offset))
        
        # Paste group grid to final image
        final_image.paste(group_grid, (group_x, group_y + 50))
        
        # Add label
        label_text = f"Group {info['group_id'] + 1} ({info['frame_count']} frames)"
        draw.text((group_x + 10, group_y + 10), label_text, fill=(0, 0, 0), font=font)
    
    return final_image


def create_combined_grid(all_group_images: List[List[Image.Image]], group_info: List[Dict]) -> Image.Image:
    """Create one large combined grid with visual separators."""
    # Flatten all images
    all_images = []
    group_boundaries = []
    current_pos = 0
    
    for group_images in all_group_images:
        all_images.extend(group_images)
        current_pos += len(group_images)
        group_boundaries.append(current_pos)
    
    if not all_images:
        return Image.new('RGB', (400, 400), color=(255, 255, 255))
    
    # Calculate grid dimensions for all images
    total_images = len(all_images)
    cols = min(6, total_images)  # Max 6 columns
    rows = (total_images + cols - 1) // cols
    
    # Calculate image dimensions
    max_width = max(img.width for img in all_images)
    max_height = max(img.height for img in all_images)
    
    # Add separator space
    separator_width = 5
    grid_width = cols * max_width + (cols - 1) * separator_width
    grid_height = rows * max_height + (rows - 1) * separator_width
    
    # Create final grid
    final_image = Image.new('RGB', (grid_width, grid_height), color=(200, 200, 200))
    
    for i, img in enumerate(all_images):
        row = i // cols
        col = i % cols
        
        x_offset = col * (max_width + separator_width)
        y_offset = row * (max_height + separator_width)
        
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        final_image.paste(img, (x_offset, y_offset))
    
    return final_image


def create_enhanced_prompt(group_info: List[Dict], group_queries: Optional[List[str]], 
                          comparison_query: Optional[str], layout_mode: str) -> str:
    """Create comprehensive prompt for enhanced grid analysis."""
    
    prompt_parts = []
    
    # Context setting
    prompt_parts.append("Bạn đang phân tích một lưới ảnh chứa nhiều nhóm frame từ video.")
    prompt_parts.append(f"Layout mode: {layout_mode}")
    prompt_parts.append(f"Tổng số nhóm: {len(group_info)}")
    
    # Group information
    for info in group_info:
        prompt_parts.append(f"- Group {info['group_id'] + 1}: {info['frame_count']} frames")
    
    # Specific queries for each group
    if group_queries:
        prompt_parts.append("\nPhân tích từng nhóm theo các câu hỏi sau:")
        for i, query in enumerate(group_queries):
            prompt_parts.append(f"Group {i + 1}: {query}")
    
    # Comparison query
    if comparison_query:
        prompt_parts.append(f"\nCâu hỏi so sánh giữa các nhóm: {comparison_query}")

    # Add common requirements
    prompt_parts.append(COMMON_REQUIREMENTS)
    
    # Output format
    prompt_parts.append(f"""
Trả về kết quả dưới dạng JSON với cấu trúc sau:
{JSON_OUTPUT_FORMATS["enhanced_grid"]}""")
    
    return "\n".join(prompt_parts)


def get_frames_wrapper(frame_urls):
    """
    Wrapper function for backward compatibility.
    """
    return get_frames_from_urls(frame_urls)


def grid_search_legacy(parsed_input) -> str:
    """Handle legacy single-group grid search format."""
    from .utils import robust_json_parse
    import os
    
    frame_urls = parsed_input.frame_urls
    grid_dimensions = parsed_input.grid_dimensions or (2, 2)
    query = parsed_input.query

    if not frame_urls:
        return json.dumps({"error": "Tham số 'frame_urls' không thể rỗng."})
    if not query:
        return json.dumps({"error": "Tham số 'query' không thể rỗng."})

    # Use existing logic
    pil_images = get_frames_from_urls(frame_urls)
    pil_images = [img for img in pil_images if img is not None]
    if not pil_images:
        return json.dumps({"error": "Không thể tải bất kỳ frame nào để tạo lưới."})

    # Create grid using helper function
    grid_image = create_grid_from_images(pil_images, grid_dimensions)

    #delete if exists
    if os.path.exists("grid_image.png"):
        os.remove("grid_image.png")

    grid_image.save("grid_image.png")

    # Prepare image data for Gemini
    image_data = prepare_image_for_gemini(grid_image)

    # Create prompt using helper
    user_prompt = create_prompt_with_requirements(
        f'Phân tích lưới ảnh này dựa trên câu hỏi: "{query}"',
        JSON_OUTPUT_FORMATS["basic_validation"]
    )

    # Call Gemini with retry logic
    gemini_result = call_gemini_with_retry(user_prompt, image_data, "grid_search_legacy")
    
    if gemini_result["success"] and gemini_result["response_text"]:
        result = robust_json_parse(gemini_result["response_text"], {
            "is_match": False,
            "confidence_score": 0.5,
            "reasoning": f"Phản hồi từ Gemini không đúng định dạng: {gemini_result['response_text']}",
            "relevant_frames": []
        })
    else:
        # Provide detailed debug info when response is empty
        result = {
            "is_match": False,
            "confidence_score": 0.0,
            "reasoning": "Gemini trả về response rỗng. Có thể do: 1) Ảnh quá lớn/phức tạp, 2) Prompt bị chặn bởi safety filter, 3) Lỗi API tạm thời, 4) Nội dung ảnh vi phạm chính sách. Vui lòng kiểm tra logs để biết chi tiết.",
            "relevant_frames": [],
            "debug_info": {
                "image_size_bytes": gemini_result.get("image_size", 0),
                "prompt_length": len(user_prompt),
                "image_dimensions": f"{grid_image.width}x{grid_image.height}",
                "frame_count": len(frame_urls),
                "error": gemini_result.get("error", "Unknown"),
                "suggested_solutions": [
                    "Giảm số lượng frame trong lưới",
                    "Thử prompt đơn giản hơn",
                    "Kiểm tra nội dung ảnh có phù hợp không",
                    "Thử lại sau vài phút"
                ]
            }
        }
    
    return json.dumps(result)


def grid_search_enhanced(parsed_input) -> str:
    """Handle enhanced multi-group grid search format."""
    from .utils import robust_json_parse
    
    frame_groups = parsed_input.frame_groups
    group_queries = parsed_input.group_queries
    comparison_query = parsed_input.comparison_query
    layout_mode = parsed_input.layout_mode
    max_images_per_group = parsed_input.max_images_per_group
    grid_dims_per_group = parsed_input.grid_dimensions_per_group or (2, 3)

    if not frame_groups:
        return json.dumps({"error": "Tham số 'frame_groups' không thể rỗng."})
    
    if not comparison_query and not group_queries:
        return json.dumps({"error": "Phải cung cấp 'comparison_query' hoặc 'group_queries'."})

    # Validate group_queries length if provided
    if group_queries and len(group_queries) != len(frame_groups):
        return json.dumps({"error": "Số lượng 'group_queries' phải bằng số lượng 'frame_groups'."})

    logger.info(f"Enhanced grid search: {len(frame_groups)} groups, layout_mode={layout_mode}")

    try:
        # Load all images for all groups
        all_group_images = []
        group_info = []
        
        for i, frame_urls in enumerate(frame_groups):
            if not frame_urls:
                continue
                
            # Limit images per group
            limited_urls = frame_urls[:max_images_per_group]
            pil_images = get_frames_from_urls(limited_urls)
            valid_images = [img for img in pil_images if img is not None]
            
            if valid_images:
                all_group_images.append(valid_images)
                group_info.append({
                    "group_id": i,
                    "frame_count": len(valid_images),
                    "original_urls": limited_urls
                })

        if not all_group_images:
            return json.dumps({"error": "Không thể tải bất kỳ frame nào từ tất cả các nhóm."})

        # Create visual layout
        if layout_mode == "separate":
            final_image = create_separate_grids(all_group_images, grid_dims_per_group, group_info)
        else:  # combined
            final_image = create_combined_grid(all_group_images, group_info)

        # Save the final image
        final_image.save("grid_image_enhanced.png")

        # Prepare image data for Gemini
        image_data = prepare_image_for_gemini(final_image)

        # Create comprehensive prompt for Gemini
        prompt = create_enhanced_prompt(group_info, group_queries, comparison_query, layout_mode)

        # Call Gemini with retry logic
        gemini_result = call_gemini_with_retry(prompt, image_data, "grid_search_enhanced")
        
        if gemini_result["success"] and gemini_result["response_text"]:
            result = robust_json_parse(gemini_result["response_text"], {
                "overall_match": False,
                "confidence_score": 0.0,
                "reasoning": f"Không thể phân tích phản hồi từ Gemini: {gemini_result['response_text']}",
                "group_results": []
            })
        else:
            result = {
                "overall_match": False,
                "confidence_score": 0.0,
                "reasoning": "Gemini trả về response rỗng cho enhanced grid search",
                "group_results": [],
                "debug_info": {
                    "image_size": gemini_result.get("image_size", 0),
                    "prompt_length": len(prompt),
                    "error": gemini_result.get("error", "Unknown")
                }
            }
        
        # Add metadata
        result["metadata"] = {
            "total_groups": len(frame_groups),
            "layout_mode": layout_mode,
            "groups_processed": len(all_group_images),
            "group_info": group_info
        }
        
        return json.dumps(result)

    except Exception as e:
        error_msg = f"Error in enhanced grid search: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
