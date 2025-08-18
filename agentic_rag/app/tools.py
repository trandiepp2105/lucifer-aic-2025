"""
Tool implementations for the Agentic RAG system.
Each tool is a standalone function that can be called by the LangGraph agent.

Recent refactoring:
- Moved constants to constants.py
- Moved utility functions to tool_utils.py
- Improved code organization and maintainability
"""
import json
import logging
import os
import base64
import re
import asyncio
import time
import tempfile

from .config import config
from .constants import JSON_OUTPUT_FORMATS
from .tool_utils import (
    create_prompt_with_requirements,
    prepare_image_for_gemini,
    call_gemini_with_retry,
    make_search_api_request,
    get_frames_from_urls,
    create_grid_from_images,
    create_separate_grids,
    create_combined_grid,
    create_enhanced_prompt,
    get_frames_wrapper,
    grid_search_legacy,
    grid_search_enhanced
)
from .schemas import GetFrameInput, GetVideoInput, TemporalSearchInput, GridSearchInput, ValidFrameQueryInput, ValidVideoQueryInput, SynthesisInput, SearchFramesInput
from .utils import robust_json_parse, strip_markdown_code_fences
import requests
import google.generativeai as genai
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=config.GOOGLE_API_KEY)

def temporal_frame_search_topk(input_params: str) -> str:
    """
    Tool: Tìm kiếm và xếp hạng các chuỗi khung hình (temporal sequences) phù hợp nhất với một chuỗi các mô tả văn bản và OCR.
    Tool này rất quan trọng cho các truy vấn dạng "hành động A, sau đó đến hành động B".
    Sử dụng khi người dùng mô tả một kịch bản gồm nhiều hành động xảy ra nối tiếp nhau (ví dụ: "A làm X, sau đó B làm Y").
    Tool này tìm kiếm các chuỗi frame trong kho dữ liệu khớp với chuỗi mô tả này và trả về các chuỗi có khả năng khớp cao nhất.
    Hỗ trợ cả text search và OCR search trong cùng một stage.

    Args:
        input_params (str): JSON string chứa các tham số:
            - query_sequence (List[Dict]): Một chuỗi các stage truy vấn, mỗi stage có thể chứa 'text' hoặc 'ocr'.
            - k (int): Số lượng chuỗi frame hàng đầu cần trả về.
            - weights (Optional[Dict]): Trọng số cho các loại tìm kiếm (text, ocr).

    Returns:
        str: JSON string chứa danh sách chuỗi frame results hoặc thông báo lỗi.
    """
    try:
        # Strip markdown code fences if present
        clean_input = strip_markdown_code_fences(input_params)
        parsed_input = TemporalSearchInput.parse_raw(clean_input)
        query_sequence = parsed_input.query_sequence
        k = parsed_input.k
        weights = parsed_input.weights

        if not query_sequence:
            return json.dumps({"error": "Tham số 'query_sequence' không thể rỗng."})

        logger.info(f"Searching temporal frames for query sequence: {query_sequence}")

        # Validate and prepare queries_structure
        queries_structure = []
        for i, stage in enumerate(query_sequence):
            if not isinstance(stage, dict):
                return json.dumps({"error": f"Stage {i} phải là object (dict)."})
            
            current_stage = {}
            if 'text' in stage and stage['text']:
                current_stage['text'] = stage['text']
            if 'ocr' in stage and stage['ocr']:
                current_stage['ocr'] = stage['ocr']
            
            if not current_stage:
                return json.dumps({"error": f"Stage {i} không có truy vấn hợp lệ (text/ocr)."})
            
            queries_structure.append(current_stage)

        form_data = {
            "k": str(k),
            "queries_structure": json.dumps(queries_structure),
        }
        
        if weights:
            form_data["weights"] = json.dumps(weights)

        # Add vector_models_config to form_data
        form_data["vector_models_config"] = json.dumps([
            {"model_name": "ViT-H-14-378-quickgelu", "weight": 0.55},
            {"model_name": "ViT-gopt-16-SigLIP2-384", "weight": 0.45}
        ])

        # Use helper function for API request

        print(f"Making API request with form_data: {form_data}")

        api_result = make_search_api_request(form_data, [])
        
        if api_result["success"]:
            logger.info(f"Found {api_result['data'].get('results_found', 0)} temporal frame results")
            return json.dumps(api_result["data"])
        else:
            return json.dumps({"error": api_result["error"]})

    except Exception as e:
        error_msg = f"Unexpected error in temporal_frame_search_topk: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

def get_frames(frame_urls):
    """
    Wrapper function for backward compatibility.
    """
    return get_frames_wrapper(frame_urls)


def get_video(input_params: str) -> str:
    """
    Tool: Trích xuất một đoạn video ngắn từ một video dài hơn trên server, dựa vào frame range.
    
    🎯 WORKFLOW SEQUENCE:
    1. Validate Input → 2. Call API → 3. Validate Response → 4. Format Output
    
    Tool này được tối ưu hóa theo Sequence Thinking để đảm bảo:
    - Validation đầu vào tuần tự và đầy đủ
    - Xử lý API call robust với error handling
    - Verification response để đảm bảo video clip accessible
    - Output format tối ưu cho valid_video_query tool

    Args:
        input_params (str): JSON string chứa các tham số:
            - video_name (str): Tên video theo format L##_V### (ví dụ: L01_V001)
            - start_frame (int): Frame bắt đầu (số nguyên dương)
            - end_frame (int): Frame kết thúc (phải > start_frame)

    Returns:
        str: JSON string chứa thông tin video clip đã tạo hoặc lỗi chi tiết.
        
    Response Format:
        Success: {
            "success": true,
            "clip_url": "/media/video_clips/L01_V001_f100-150.mp4",
            "full_url": "http://server/media/video_clips/L01_V001_f100-150.mp4",
            "duration": 2.0,
            "frame_range": "100-150",
            "video_name": "L01_V001",
            "cached": false,
            "ready_for_validation": true
        }
        Error: {
            "success": false,
            "error": "Chi tiết lỗi",
            "suggestion": "Gợi ý khắc phục"
        }
    """
    try:
        # ===== BƯỚC 1: INPUT VALIDATION TUẦN TỰ =====
        logger.info("Bước 1: Validating input parameters...")
        
        # Parse input với error handling
        try:
            clean_input = strip_markdown_code_fences(input_params)
            parsed_input = GetVideoInput.parse_raw(clean_input)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Lỗi parse input parameters: {str(e)}",
                "suggestion": "Kiểm tra format JSON input và đảm bảo có đủ các field bắt buộc"
            })
        
        video_name = parsed_input.video_name
        start_frame = parsed_input.start_frame
        end_frame = parsed_input.end_frame

        # Validate video_name format
        import re
        if not re.match(r'^L\d{2}_V\d{3}$', video_name):
            return json.dumps({
                "success": False,
                "error": f"Video name '{video_name}' không đúng format",
                "suggestion": "Video name phải theo format L##_V### (ví dụ: L01_V001, L05_V010)"
            })

        # Validate frame numbers
        if start_frame < 0 or end_frame < 0:
            return json.dumps({
                "success": False,
                "error": "Frame numbers phải là số nguyên dương",
                "suggestion": "Sử dụng start_frame >= 0 và end_frame >= 0"
            })

        # Ensure logical frame range
        if end_frame <= start_frame:
            logger.info(f"Adjusting end_frame from {end_frame} to {start_frame + 1} for single frame clip")
            end_frame = start_frame + 1

        # Validate reasonable frame range (không quá dài)
        frame_count = end_frame - start_frame
        if frame_count > 1800:  # ~1 minute at 30fps
            return json.dumps({
                "success": False,
                "error": f"Frame range quá dài ({frame_count} frames)",
                "suggestion": "Giới hạn video clip dưới 1 phút (≤1800 frames) để tránh file quá lớn"
            })

        logger.info(f"✅ Input validation passed: {video_name}, frames {start_frame}-{end_frame} ({frame_count} frames)")

        # ===== BƯỚC 2: API CALL PROCESSING =====
        logger.info("Bước 2: Calling video clip API...")
        
        clip_api_url = f"{config.VIDEO_API_URL}/api/video/clip/"
        
        payload = {
            "video_name": video_name,
            "start_frame": start_frame,
            "end_frame": end_frame
        }
        
        logger.info(f"API URL: {clip_api_url}")
        logger.info(f"Payload: {payload}")
        
        response = requests.post(
            clip_api_url,
            json=payload,
            timeout=config.API_REQUEST_TIMEOUT
        )
        
        # Detailed HTTP error handling
        if response.status_code == 404:
            return json.dumps({
                "success": False,
                "error": "Video clip API endpoint không tồn tại",
                "suggestion": "Kiểm tra API server có đang chạy và URL có đúng không"
            })
        elif response.status_code == 400:
            return json.dumps({
                "success": False,
                "error": "Request không hợp lệ (400 Bad Request)",
                "suggestion": "Kiểm tra video_name có tồn tại và frame range có hợp lệ không"
            })
        elif response.status_code >= 500:
            return json.dumps({
                "success": False,
                "error": f"Server error ({response.status_code})",
                "suggestion": "Lỗi server tạm thời, thử lại sau vài giây"
            })
        
        response.raise_for_status()
        
        # ===== BƯỚC 3: RESPONSE VALIDATION =====
        logger.info("Bước 3: Validating API response...")
        
        try:
            api_result = response.json()
        except json.JSONDecodeError:
            return json.dumps({
                "success": False,
                "error": "API response không phải JSON hợp lệ",
                "suggestion": "Server có thể đang gặp sự cố, thử lại sau"
            })

        # Check API response structure
        if not isinstance(api_result, dict):
            return json.dumps({
                "success": False,
                "error": "API response format không đúng",
                "suggestion": "Server response không phải dict object"
            })

        # Validate required fields in response
        if "success" not in api_result:
            return json.dumps({
                "success": False,
                "error": "API response thiếu field 'success'",
                "suggestion": "Server response format không đúng chuẩn"
            })

        if not api_result.get("success", False):
            api_error = api_result.get("error", "Unknown error from API")
            return json.dumps({
                "success": False,
                "error": f"API failed: {api_error}",
                "suggestion": "Kiểm tra video file có tồn tại và frame range có hợp lệ không"
            })

        clip_url = api_result.get("clip_url")
        if not clip_url:
            return json.dumps({
                "success": False,
                "error": "API response thiếu clip_url",
                "suggestion": "Video clip có thể chưa được tạo thành công"
            })

        logger.info(f"✅ API call successful: {clip_url}")

        # ===== BƯỚC 4: OUTPUT FORMATTING =====
        logger.info("Bước 4: Formatting enhanced output...")
        
        # Create enhanced response for agent consumption
        enhanced_result = {
            "success": True,
            "clip_url": clip_url,
            "full_url": f"{config.VIDEO_API_URL}{clip_url}" if clip_url.startswith('/') else clip_url,
            "duration": api_result.get("duration", 0.0),
            "frame_range": f"{start_frame}-{end_frame}",
            "frame_count": frame_count,
            "video_name": video_name,
            "cached": api_result.get("cached", False),
            "ready_for_validation": True,  # Signal cho valid_video_query tool
            "metadata": {
                "start_time": api_result.get("start_time", 0.0),
                "end_time": api_result.get("end_time", 0.0),
                "created_at": api_result.get("created_at", ""),
                "file_size_mb": api_result.get("file_size_mb", 0.0)
            }
        }

        logger.info(f"✅ Video clip ready: {enhanced_result['full_url']}")
        logger.info(f"Duration: {enhanced_result['duration']}s, Cached: {enhanced_result['cached']}")
        
        return json.dumps(enhanced_result)

    except requests.exceptions.Timeout:
        error_msg = "Timeout khi gọi video clip API (>30s)"
        logger.error(error_msg)
        return json.dumps({
            "success": False,
            "error": error_msg,
            "suggestion": "API server có thể đang quá tải, thử lại với frame range nhỏ hơn"
        })
    except requests.exceptions.ConnectionError:
        error_msg = "Không thể kết nối tới video clip API server"
        logger.error(error_msg)
        return json.dumps({
            "success": False,
            "error": error_msg,
            "suggestion": "Kiểm tra API server có đang chạy và network connection"
        })
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error calling video clip API: {str(e)}"
        logger.error(error_msg)
        return json.dumps({
            "success": False,
            "error": error_msg,
            "suggestion": "Kiểm tra network connection và API server status"
        })
    except Exception as e:
        error_msg = f"Unexpected error in get_video: {str(e)}"
        logger.error(error_msg)
        return json.dumps({
            "success": False,
            "error": error_msg,
            "suggestion": "Lỗi không xác định, kiểm tra logs để biết chi tiết"
        })


def grid_search(input_params: str) -> str:
    """
    🎯 GRID SEARCH - CÔNG CỤ TÌM ỨNG CỬ VIÊN (CANDIDATE FINDER)
    
    🔥 VAI TRÒ CHÍNH: Công cụ chuyên biệt để tìm và xếp hạng các ứng cử viên frame/chuỗi frame tốt nhất 
    từ kết quả temporal search, chuẩn bị cho bước xác thực cuối cùng bằng valid_video_query.
    
    📋 WORKFLOW CHUẨN (QUAN TRỌNG):
    🔸 Temporal Search (1 stage) → Grid Search LEGACY → valid_video_query
    🔸 Temporal Search (≥2 stages) → Grid Search ENHANCED SEPARATE → valid_video_query
    
    ⚡ TÍNH NĂNG CHÍNH:
    - Phân tích đồng thời nhiều frame bằng Vision AI để ranking candidates
    - Tiết kiệm 80-90% API calls so với phân tích từng frame riêng lẻ
    - Intelligent ranking để tìm ra TOP candidates phù hợp nhất
    - 2 chế độ tối ưu cho different temporal search scenarios
    
    🎯 LEGACY MODE - Cho Temporal Search 1 Stage:
    ✅ INPUT: frame_urls (từ temporal search) + query (tìm candidates)
    ✅ OUTPUT: Ranked frame candidates để chuyển cho valid_video_query
    ✅ EXAMPLE: Tìm 3-5 frame candidates tốt nhất từ 12 frames cho cảnh "người đàn ông mặc áo đỏ nói chuyện"
    
    🎯 ENHANCED SEPARATE MODE - Cho Temporal Search Multi-Stage:  
    ✅ INPUT: frame_groups (từ multiple temporal stages) + comparison_query
    ✅ OUTPUT: Ranked stage candidates để chuyển cho valid_video_query
    ✅ EXAMPLE: So sánh stages "người A nói" vs "người B phản ứng" vs "kết quả cuối"

    Args:
        input_params (str): JSON string chứa các tham số:
        
        🔸 LEGACY FORMAT (cho 1 stage temporal search):
            - frame_urls (List[str]): Danh sách frame URLs từ temporal_frame_search_topk
            - grid_dimensions (Tuple[int, int], optional): Kích thước lưới (rows, cols), mặc định (2,2)
            - query (str): Câu hỏi để tìm và rank candidates (focus vào "tìm top X candidates")
            
        🔸 ENHANCED FORMAT (cho multi-stage temporal search):
            - frame_groups (List[List[str]]): Nhóm frame URLs từ different temporal stages
            - comparison_query (str): Câu hỏi so sánh để rank stage candidates
            - layout_mode (str): "separate" (required cho temporal stages)
            - max_images_per_group (int): Giới hạn frame mỗi stage (mặc định 6)

    Returns:
        str: JSON string chứa:
        - is_match (bool): Có candidates phù hợp không
        - confidence_score (float): Độ tin cậy tổng thể 0.0-1.0
        - reasoning (str): Giải thích chi tiết về ranking và candidates
        - relevant_frames (List): TOP candidates được recommend (ready cho valid_video_query)
        - metadata (dict): Thông tin về quá trình candidate finding
        
    Examples:
        # Legacy mode - tìm frame candidates từ 1 stage temporal search
        {
            "frame_urls": ["frame1.jpg", "frame2.jpg", ..., "frame12.jpg"],
            "grid_dimensions": [3, 4],
            "query": "Tìm 3-5 frame candidates tốt nhất cho cảnh người đàn ông mặc áo đỏ đang nói chuyện. Rank theo độ phù hợp và chất lượng."
        }
        
        # Enhanced mode - so sánh stage candidates từ multi-stage temporal search
        {
            "frame_groups": [
                ["stage1_frame1.jpg", "stage1_frame2.jpg"],  # Stage: "người A nói"
                ["stage2_frame1.jpg", "stage2_frame2.jpg"],  # Stage: "người B phản ứng"
                ["stage3_frame1.jpg", "stage3_frame2.jpg"]   # Stage: "kết thúc"
            ],
            "comparison_query": "So sánh 3 temporal stages. Stage nào có candidates tốt nhất để validate với valid_video_query?",
            "layout_mode": "separate"
        }
    """
    try:
        # Strip markdown code fences if present
        clean_input = strip_markdown_code_fences(input_params)
        parsed_input = GridSearchInput.parse_raw(clean_input)
        
        # Detect format: legacy vs enhanced
        if parsed_input.frame_groups is not None:
            # Enhanced format - multiple frame groups
            return _grid_search_enhanced(parsed_input)
        elif parsed_input.frame_urls is not None:
            # Legacy format - single frame list
            return _grid_search_legacy(parsed_input)
        else:
            return json.dumps({"error": "Phải cung cấp 'frame_urls' (legacy) hoặc 'frame_groups' (enhanced)."})

    except Exception as e:
        error_msg = f"Unexpected error in grid_search: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


def _grid_search_legacy(parsed_input: GridSearchInput) -> str:
    """Handle legacy single-group grid search format."""
    return grid_search_legacy(parsed_input)


def _grid_search_enhanced(parsed_input: GridSearchInput) -> str:
    """Handle enhanced multi-group grid search format."""
    return grid_search_enhanced(parsed_input)


def valid_video_query(input_params: str) -> str:
    """
    🎬 ENHANCED VIDEO VALIDATION - TRỰC TIẾP ANALYZE VIDEO BẰNG GEMINI
    
    Tool: Xác thực xem một đoạn video có khớp với chuỗi mô tả sự kiện hay không.
    Sử dụng Gemini Video API để phân tích trực tiếp video content thay vì extract frames.
    
    🔥 CẢI TIẾN CHÍNH:
    ✅ Upload video trực tiếp lên Gemini File API 
    ✅ Analyze video với temporal continuity và motion understanding
    ✅ Hiểu được context đầy đủ của video sequence
    ✅ Robust error handling cho video processing
    ✅ Enhanced insights về temporal patterns và transitions
    
    🎯 WORKFLOW SEQUENCE:
    1. Download Video → 2. Upload to Gemini → 3. Wait Processing → 4. Video Analysis → 5. Cleanup
    
    Args:
        input_params (str): JSON string chứa các tham số:
            - video_clip_url (str): URL của đoạn video ngắn cần xác thực (từ get_video tool)
            - query_sequence (List[str]): Chuỗi các mô tả sự kiện trong video theo thời gian
            - question (str, optional): Câu hỏi tùy chọn về nội dung video

    Returns:
        str: JSON string chứa kết quả xác thực video chi tiết.
        
    Response Format:
        {
            "is_match": bool,
            "confidence_score": float,
            "reasoning": str,
            "sequence_analysis": [...],
            "video_analysis": {
                "duration_seconds": float,
                "temporal_insights": str,
                "motion_analysis": str,
                "scene_transitions": [...]
            },
            "metadata": {...}
        }
    """
    try:
        # ===== BƯỚC 1: INPUT VALIDATION =====
        logger.info("Bước 1: Validating input parameters...")
        
        clean_input = strip_markdown_code_fences(input_params)
        parsed_input = ValidVideoQueryInput.parse_raw(clean_input)
        video_clip_url = parsed_input.video_clip_url
        query_sequence = parsed_input.query_sequence
        question = parsed_input.question

        if not video_clip_url or not query_sequence:
            return json.dumps({
                "error": "Tham số 'video_clip_url' và 'query_sequence' không thể rỗng.",
                "suggestion": "Cung cấp video URL và sequence mô tả sự kiện"
            })

        logger.info(f"Validating video clip: {video_clip_url} with {len(query_sequence)} sequence steps")

        # ===== BƯỚC 2: VIDEO DOWNLOAD =====
        logger.info("Bước 2: Downloading video for analysis...")
        
        try:
            # Construct full URL if relative path
            if video_clip_url.startswith('/'):
                full_video_url = f"{config.MEDIA_API_URL}{video_clip_url}"
            else:
                full_video_url = video_clip_url
                
            logger.info(f"Full video URL: {full_video_url}")
            
            # Download video to temporary location
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                response = requests.get(full_video_url, timeout=30, stream=True)
                response.raise_for_status()
                
                total_size = 0
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                    total_size += len(chunk)
                    
                    # Limit video size (50MB max)
                    if total_size > 50 * 1024 * 1024:
                        raise Exception("Video file quá lớn (>50MB) cho analysis")
                    
                temp_video_path = temp_file.name
                
            logger.info(f"✅ Downloaded video: {total_size / 1024 / 1024:.2f}MB")

        except requests.exceptions.RequestException as e:
            error_msg = f"Không thể download video từ {video_clip_url}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({
                "error": error_msg,
                "suggestion": "Kiểm tra video URL có accessible không và network connection"
            })

        # ===== BƯỚC 3: PREPARE VIDEO FOR GEMINI ANALYSIS =====
        logger.info("Bước 3: Preparing video for Gemini analysis...")
        
        video_content = None  # Will store either file reference or inline data
        cleanup_uploaded_file = None  # Track uploaded file for cleanup
        
        try:
            # Determine approach based on file size
            video_size_mb = total_size / 1024 / 1024
            logger.info(f"Video size: {video_size_mb:.2f}MB")
            
            if video_size_mb < 20:
                # ===== APPROACH 1: INLINE VIDEO DATA (<20MB) =====
                logger.info("Using inline video data approach (video <20MB)")
                
                # Read video file as bytes
                with open(temp_video_path, 'rb') as video_file:
                    video_bytes = video_file.read()
                
                # Create inline video content
                video_content = {
                    "mime_type": "video/mp4",
                    "data": video_bytes
                }
                
                logger.info(f"✅ Video prepared as inline data: {len(video_bytes)} bytes")
                
            else:
                # ===== APPROACH 2: FILES API (>=20MB) =====
                logger.info("Using Files API approach (video >=20MB)")
                
                # Import the new genai client
                from google import genai as genai_client
                
                # Create client
                client = genai_client.Client(api_key=config.GOOGLE_API_KEY)
                
                # Upload video file to Gemini Files API
                uploaded_file = client.files.upload(
                    path=temp_video_path,
                    display_name=f"video_validation_{int(time.time())}.mp4"
                )
                
                # Store reference for cleanup
                cleanup_uploaded_file = uploaded_file
                video_content = uploaded_file
                
                logger.info(f"✅ Video uploaded to Files API: {uploaded_file.name}")

        except ImportError as e:
            error_msg = f"Không thể import Files API client: {str(e)}"
            logger.error(error_msg)
            
            # Fallback: Try inline approach even for larger files
            logger.info("Fallback: Attempting inline approach for larger video...")
            try:
                with open(temp_video_path, 'rb') as video_file:
                    video_bytes = video_file.read()
                
                video_content = {
                    "mime_type": "video/mp4", 
                    "data": video_bytes
                }
                
                logger.info(f"✅ Fallback successful: Using inline data for {video_size_mb:.2f}MB video")
                
            except Exception as fallback_error:
                # Cleanup
                try:
                    os.unlink(temp_video_path)
                except:
                    pass
                    
                return json.dumps({
                    "error": f"Both Files API and inline approaches failed: {str(fallback_error)}",
                    "suggestion": "Video có thể quá lớn hoặc format không support. Thử video ngắn hơn hoặc convert sang MP4."
                })
                
        except Exception as e:
            error_msg = f"Lỗi prepare video cho Gemini: {str(e)}"
            logger.error(error_msg)
            
            # Cleanup
            try:
                os.unlink(temp_video_path)
            except:
                pass
                
            if cleanup_uploaded_file:
                try:
                    from google import genai as genai_client
                    client = genai_client.Client(api_key=config.GOOGLE_API_KEY)
                    client.files.delete(cleanup_uploaded_file.name)
                except:
                    pass
                    
            return json.dumps({
                "error": error_msg,
                "suggestion": "Video có thể quá lớn, format không support, hoặc API limit. Thử video ngắn hơn."
            })

        # ===== BƯỚC 4: CREATE ENHANCED VIDEO ANALYSIS PROMPT =====
        logger.info("Bước 4: Creating comprehensive video analysis prompt...")
        
        sequence_text = "\n".join([f"{i+1}. {desc}" for i, desc in enumerate(query_sequence)])
        
        base_prompt = f"""🎬 PHÂN TÍCH VIDEO VALIDATION - TEMPORAL SEQUENCE ANALYSIS

📋 NHIỆM VỤ: Phân tích video này để xác định xem nó có khớp với chuỗi sự kiện được mô tả không.

🎯 CHUỖI SỰ KIỆN CẦN VALIDATE:
{sequence_text}

🔍 YÊU CẦU PHÂN TÍCH CHI TIẾT:

1. **TEMPORAL SEQUENCE VALIDATION:**
   - Phân tích từng bước trong chuỗi sự kiện
   - Kiểm tra thứ tự thời gian có đúng không
   - Xác định transitions giữa các sự kiện

2. **MOTION & ACTION ANALYSIS:**
   - Phân tích movement và actions trong video
   - Kiểm tra continuity của các hành động
   - Đánh giá quality của temporal progression

3. **CONTENT MATCHING:**
   - So sánh nội dung video với từng mô tả
   - Identify missing hoặc extra elements
   - Đánh giá overall coherence

4. **SCENE QUALITY ASSESSMENT:**
   - Lighting, angle, clarity của video
   - Visibility của key elements được mô tả
   - Technical quality affect validation"""

        if question:
            base_prompt += f"\n\n🤔 **ADDITIONAL QUESTION:**\n{question}"

        base_prompt += f"""

📊 **RESPONSE FORMAT REQUIRED:**
Trả về JSON với format sau (STRICTLY follow this structure):

{{
    "is_match": true/false,
    "confidence_score": 0.0-1.0,
    "reasoning": "Giải thích chi tiết về kết quả validation",
    "sequence_analysis": [
        {{
            "step": 1,
            "description": "Mô tả step đầu tiên",
            "found_in_video": true/false,
            "timestamp_range": "0s-2s",
            "confidence": 0.0-1.0,
            "details": "Chi tiết về step này trong video"
        }}
    ],
    "video_analysis": {{
        "duration_seconds": 5.2,
        "temporal_insights": "Phân tích về temporal flow và transitions",
        "motion_analysis": "Phân tích về movement và actions",
        "scene_transitions": ["List các transitions quan trọng"],
        "overall_quality": "Assessment về technical quality"
    }},
    "missing_elements": ["Các elements được mô tả nhưng không có trong video"],
    "extra_elements": ["Các elements có trong video nhưng không được mô tả"],
    "recommendations": ["Gợi ý để improve validation"]
}}

🚀 **ANALYZE VIDEO NOW:**"""

        # ===== BƯỚC 5: CALL GEMINI WITH VIDEO =====
        logger.info("Bước 5: Calling Gemini for video analysis...")
        
        try:
            # Create model for video analysis
            model = genai.GenerativeModel(
                model_name="gemini-1.5-pro",
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 4096,
                }
            )
            
            # Prepare content based on video type
            if isinstance(video_content, dict) and "data" in video_content:
                # Inline video data approach
                logger.info("Generating content with inline video data...")
                
                # Create content parts for inline video
                content_parts = [
                    {
                        "inline_data": {
                            "mime_type": video_content["mime_type"],
                            "data": base64.b64encode(video_content["data"]).decode('utf-8')
                        }
                    },
                    {"text": base_prompt}
                ]
                
                response = model.generate_content(
                    content_parts,
                    # request_options={"timeout": 120}
                )
                
            else:
                # Files API approach 
                logger.info("Generating content with Files API reference...")
                
                response = model.generate_content(
                    [video_content, base_prompt],
                    # request_options={"timeout": 120}
                )
            
            if not response.text:
                raise Exception("Gemini trả về response rỗng cho video analysis")
                
            logger.info(f"✅ Gemini video analysis completed: {len(response.text)} chars")
            
            # Parse JSON response
            result = robust_json_parse(response.text, {
                "is_match": False,
                "confidence_score": 0.0,
                "reasoning": f"Không thể parse response từ Gemini: {response.text[:500]}...",
                "sequence_analysis": [],
                "video_analysis": {
                    "duration_seconds": 0.0,
                    "temporal_insights": "Analysis failed",
                    "motion_analysis": "Analysis failed",
                    "scene_transitions": [],
                    "overall_quality": "Unknown"
                }
            })

        except Exception as e:
            error_msg = f"Lỗi Gemini video analysis: {str(e)}"
            logger.error(error_msg)
            
            result = {
                "is_match": False,
                "confidence_score": 0.0,
                "reasoning": f"Gemini video analysis failed: {error_msg}",
                "sequence_analysis": [],
                "video_analysis": {
                    "error": error_msg,
                    "suggestion": "Thử video ngắn hơn hoặc format khác"
                },
                "debug_info": {
                    "video_size_mb": total_size / 1024 / 1024,
                    "video_url": video_clip_url,
                    "approach_used": "inline" if isinstance(video_content, dict) else "files_api"
                }
            }

        # ===== BƯỚC 6: CLEANUP & ENHANCE METADATA =====
        logger.info("Bước 6: Cleanup and finalizing results...")
        
        # Cleanup uploaded file if using Files API
        if cleanup_uploaded_file:
            try:
                from google import genai as genai_client
                client = genai_client.Client(api_key=config.GOOGLE_API_KEY)
                client.files.delete(cleanup_uploaded_file.name)
                logger.info("✅ Cleaned up Gemini uploaded file (Files API)")
            except Exception as e:
                logger.warning(f"Could not delete Gemini file: {e}")
        
        # Cleanup local temp file
        try:
            os.unlink(temp_video_path)
            logger.info("✅ Cleaned up local temp file")
        except Exception as e:
            logger.warning(f"Could not delete temp file: {e}")

        # Add enhanced metadata
        analysis_method = "inline_video_data" if isinstance(video_content, dict) else "files_api_upload"
        
        result["metadata"] = {
            "video_url": video_clip_url,
            "video_size_mb": total_size / 1024 / 1024,
            "query_sequence_length": len(query_sequence),
            "analysis_method": analysis_method,
            "gemini_model": "gemini-1.5-pro",
            "processing_time": "video_native_analysis",
            "approach_used": "inline" if isinstance(video_content, dict) else "files_api"
        }

        logger.info(f"✅ Video validation completed: match={result.get('is_match', False)}, confidence={result.get('confidence_score', 0.0)}")
        
        return json.dumps(result)

    except Exception as e:
        error_msg = f"Unexpected error in valid_video_query: {str(e)}"
        logger.error(error_msg)
        return json.dumps({
            "error": error_msg,
            "suggestion": "Lỗi không xác định trong video validation, kiểm tra logs để biết chi tiết"
        })


def valid_frame_query(input_params: str) -> str:
    """
    Tool: Xác thực xem một chuỗi các khung hình có khớp với một chuỗi các mô tả tương ứng hay không.
    Sử dụng khi cần kiểm tra từng frame một cách chi tiết. Tool này kém hiệu quả hơn grid_search nếu chỉ cần một đánh giá tổng thể.

    Args:
        input_params (str): JSON string chứa các tham số:
            - frames (List[str]): Danh sách frame_url cần xác thực.
            - queries (List[str]): Danh sách các câu mô tả tương ứng với từng frame.

    Returns:
        str: JSON string chứa kết quả xác thực cho từng cặp (frame, mô tả) và một kết luận tổng thể.
    """
    try:
        # Strip markdown code fences if present
        clean_input = strip_markdown_code_fences(input_params)
        parsed_input = ValidFrameQueryInput.parse_raw(clean_input)
        frames_urls = parsed_input.frames
        queries = parsed_input.queries

        if not frames_urls or not queries:
            return json.dumps({"error": "Tham số 'frames' hoặc 'queries' không thể rỗng."})
        if len(frames_urls) != len(queries):
            return json.dumps({"error": "Số lượng frames và queries phải bằng nhau."})

        # 1. Tải các ảnh từ frames bằng get_frames.
        pil_images = get_frames(frames_urls)
        
        # Lọc các ảnh hợp lệ (không phải None)
        valid_indices = [i for i, img in enumerate(pil_images) if img is not None]
        if not valid_indices:
            return json.dumps({"overall_match": False, "confidence_score": 0.0, "reasoning": "Không thể tải bất kỳ frame nào để xác thực."})

        # 2. Xác thực từng cặp (ảnh, mô tả).
        overall_match = True
        overall_confidence = 0.0
        details = []

        for i in valid_indices:
            img = pil_images[i]
            query = queries[i]
            frame_url = frames_urls[i]

            # Prepare image data for Gemini
            image_data = prepare_image_for_gemini(img)

            # Create prompt using helper
            user_prompt = create_prompt_with_requirements(
                f'Phân tích hình ảnh và xác định xem nó có khớp với mô tả sau không: "{query}"',
                '{"is_match": true/false, "confidence_score": 0.0-1.0, "reasoning": "Giải thích chi tiết lý do"}'
            )

            # Call Gemini with retry logic
            gemini_result = call_gemini_with_retry(user_prompt, image_data, f"valid_frame_query_{frame_url}")
            
            if gemini_result["success"] and gemini_result["response_text"]:
                frame_validation_result = robust_json_parse(gemini_result["response_text"], {
                    "is_match": False,
                    "confidence_score": 0.0,
                    "reasoning": f"Không thể phân tích phản hồi từ Gemini: {gemini_result['response_text']}"
                })
            else:
                frame_validation_result = {
                    "is_match": False,
                    "confidence_score": 0.0,
                    "reasoning": f"Gemini trả về response rỗng cho frame {frame_url}. Error: {gemini_result.get('error', 'Unknown')}"
                }
            
            # Extract thông tin từ kết quả
            is_match = frame_validation_result.get("is_match", False)
            confidence_score = frame_validation_result.get("confidence_score", 0.0)
            reasoning = frame_validation_result.get("reasoning", gemini_result.get("response_text", "No response"))

            details.append({
                "frame": frame_url,
                "query": query,
                "is_match": is_match,
                "confidence_score": confidence_score,
                "reasoning": reasoning
            })
            
            if not is_match:
                overall_match = False
            overall_confidence += confidence_score

        final_reasoning = "Tất cả các frame khớp với mô tả." if overall_match else "Một hoặc nhiều frame không khớp với mô tả."
        if pil_images:
            overall_confidence /= len(pil_images) # Average confidence
        
        return json.dumps({
            "overall_match": overall_match,
            "confidence_score": overall_confidence,
            "reasoning": final_reasoning,
            "details": details
        })

    except Exception as e:
        error_msg = f"Unexpected error in valid_frame_query: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


# Tool descriptions for LangGraph
TOOL_DESCRIPTIONS = {
    "temporal_frame_search_topk": {
        "name": "temporal_frame_search_topk",
        "description": "Công cụ quan trọng để xử lý các truy vấn liên quan đến chuỗi sự kiện theo thời gian "
                       "với hỗ trợ text và OCR search. Sử dụng khi người dùng mô tả một kịch bản gồm nhiều hành động "
                       "xảy ra nối tiếp nhau (ví dụ: 'A làm X, sau đó B làm Y'). Tool này tìm kiếm các chuỗi "
                       "frame trong kho dữ liệu khớp với chuỗi mô tả này và trả về các chuỗi có khả năng khớp cao nhất.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_sequence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "ocr": {"type": "string"}
                        }
                    },
                    "description": "Danh sách các stage truy vấn, mỗi stage có thể chứa 'text' hoặc 'ocr'."
                },
                "k": {
                    "type": "integer",
                    "default": 50,
                    "description": "Số lượng chuỗi frame cần trả về, mặc định là 50."
                },
                "weights": {
                    "type": "object",
                    "description": "Trọng số cho các loại tìm kiếm (text, ocr)."
                }
            },
            "required": ["query_sequence"]
        }
    },
    "get_frame": {
        "name": "get_frame",
        "description": "Lấy dữ liệu hình ảnh thực tế từ một hoặc nhiều URL của frame. Dùng khi bạn cần hình ảnh để cung cấp cho các tool xác thực như valid_frame_query hoặc grid_search.",
        "parameters": {
            "type": "object",
            "properties": {
                "frame_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách URL của hình ảnh."
                }
            },
            "required": ["frame_urls"]
        }
    },
    "valid_frame_query": {
        "name": "valid_frame_query",
        "description": "Xác thực xem một chuỗi các frame riêng lẻ có khớp với một chuỗi các mô tả tương ứng hay không. Sử dụng khi cần kiểm tra từng frame một cách chi tiết. Tool này kém hiệu quả hơn grid_search nếu chỉ cần một đánh giá tổng thể.",
        "parameters": {
            "type": "object",
            "properties": {
                "frames": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách URL của các frame."
                },
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách mô tả tương ứng cho từng frame."
                }
            },
            "required": ["frames", "queries"]
        }
    },
    "grid_search": {
        "name": "grid_search", 
        "description": """🎯 GRID SEARCH - CÔNG CỤ TÌM ỨNG CỬ VIÊN (CANDIDATE FINDER)

🔥 VAI TRÒ CHÍNH: Công cụ chuyên biệt để tìm và xếp hạng các ứng cử viên frame/chuỗi frame tốt nhất từ kết quả temporal search, chuẩn bị cho bước xác thực cuối cùng bằng valid_video_query.

⚡ TÍNH NĂNG CHÍNH:
- Phân tích đồng thời nhiều frame bằng lưới hình ảnh với Vision AI
- Tiết kiệm 80-90% API calls so với phân tích từng frame riêng lẻ  
- Ranking thông minh để tìm ra TOP candidates phù hợp nhất
- 2 chế độ tối ưu cho different temporal search scenarios

📋 WORKFLOW CHUẨN (QUAN TRỌNG):
🔸 Temporal Search (1 stage) → Grid Search LEGACY → valid_video_query
🔸 Temporal Search (≥2 stages) → Grid Search ENHANCED SEPARATE → valid_video_query

🎯 LEGACY MODE - Cho Temporal Search 1 Stage:
✅ KHI NÀO: Sau temporal_frame_search_topk với query_sequence chỉ có 1 stage
✅ MỤC ĐÍCH: Tìm frame/chuỗi frame tốt nhất từ một tập ứng viên đồng nhất  
✅ INPUT: Danh sách frame URLs từ temporal search + query tìm candidates
✅ OUTPUT: Ranking các frame candidates để chuyển cho valid_video_query
✅ VÍ DỤ: "Từ 12 frame này, tìm 3-5 frame candidates tốt nhất cho cảnh người đàn ông mặc áo đỏ đang nói chuyện"

🎯 ENHANCED SEPARATE MODE - Cho Temporal Search Multi-Stage:
✅ KHI NÀO: Sau temporal_frame_search_topk với query_sequence có ≥2 stages
✅ MỤC ĐÍCH: So sánh các chuỗi frame từ different stages, tìm chuỗi candidates tốt nhất
✅ INPUT: Múltiple frame groups từ different temporal stages + comparison queries
✅ OUTPUT: Ranking các chuỗi candidates tốt nhất để chuyển cho valid_video_query
✅ VÍ DỤ: So sánh chuỗi "người A nói" vs "người B phản ứng" vs "kết quả cuối cùng"

❌ KHÔNG DÙNG KHI:
❌ Chưa có kết quả từ temporal_frame_search_topk
❌ Chỉ cần xác thực 1-2 frame cụ thể (dùng valid_frame_query trực tiếp)
❌ Đã xác định chắc chắn frame target (skip đến valid_video_query)

🔗 KẾT NỐI VỚI VALID_VIDEO_QUERY:
- Grid search output sẽ cung cấp ranked candidates
- valid_video_query sẽ xác thực chi tiết từng candidate được recommend
- Workflow hoàn chỉnh: temporal → grid (find candidates) → valid_video (validate candidates)

📊 HIỆU SUẤT:
- Legacy: 1 API call cho 4-20 frame candidates analysis
- Enhanced: 1 API call cho multi-group comparison từ temporal stages
- Tiết kiệm massive API calls và time so với validate từng frame riêng lẻ""",
        "parameters": {
            "type": "object",
            "properties": {
                "frame_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": """[LEGACY MODE - Temporal Search 1 Stage] Danh sách frame URLs từ temporal_frame_search_topk để tìm candidates.
                    
🎯 MỤC ĐÍCH: Phân tích đồng thời để rank và tìm TOP frame candidates tốt nhất
📝 INPUT: 4-20 frame URLs từ temporal search results  
💡 WORKFLOW: temporal_frame_search_topk → frame_urls → grid_search LEGACY → candidates cho valid_video_query

📋 CÁCH DÙNG:
- Lấy frame URLs từ temporal search kết quả (usually top 10-20)
- Grid search sẽ analyze tất cả và rank để tìm 3-5 top candidates
- Kết quả candidates sẽ được pass cho valid_video_query để final validation

⚠️ LƯU Ý: 
- Chỉ dùng cho temporal search có 1 stage duy nhất
- Phải đi kèm với 'query' parameter
- Không dùng cùng 'frame_groups' (đó là ENHANCED mode)"""
                },
                "grid_dimensions": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": """[LEGACY MODE] Kích thước lưới [rows, cols].
                    
📝 Mặc định: [2, 2] cho 4 ảnh
💡 Gợi ý: [2, 3] cho 6 ảnh, [3, 3] cho 9 ảnh, [2, 4] cho 8 ảnh
⚠️ Không nên quá 4x4 (16 ảnh) để tránh lưới quá nhỏ"""
                },
                "query": {
                    "type": "string",
                    "description": """[LEGACY MODE] Câu hỏi để tìm và rank frame candidates từ temporal search results.
                    
🎯 FOCUS: Tìm ứng cử viên (candidates) tốt nhất, không chỉ đánh giá yes/no
📝 FORMAT MẪU để tối ưu candidate finding:

✅ VÍ DỤ TỐT (focus vào ranking candidates):
- "Tìm 3-5 frame candidates tốt nhất cho cảnh người đàn ông mặc áo đỏ đang nói chuyện. Rank theo độ rõ nét và phù hợp."
- "Rank các frame theo thứ tự phù hợp nhất với mô tả '[temporal_query]'. Chọn top 3 candidates để validate tiếp."
- "Từ các frame này, tìm candidates tốt nhất cho chuỗi sự kiện '[temporal_sequence]'. Ưu tiên frame có chất lượng cao và nội dung rõ ràng."
- "Phân tích và recommend 3-5 frame candidates có khả năng match cao nhất với query '[original_query]'"

❌ TRÁNH (không focus vào candidates):
- "Phân tích lưới này" (quá mơ hồ)
- "Frame nào tốt?" (không rõ criteria)
- "Có frame nào match không?" (chỉ yes/no, không rank)

🔗 CONNECTION với valid_video_query:
Query này sẽ tạo ra ranked candidates list → valid_video_query sẽ validate từng candidate chi tiết"""
                },
                "frame_groups": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "description": """[ENHANCED SEPARATE MODE - Temporal Search Multi-Stage] Danh sách các nhóm frame URLs từ different stages của temporal search.
                    
🎯 MỤC ĐÍCH: So sánh candidates từ múltiple temporal stages để tìm chuỗi tốt nhất
📝 STRUCTURE: [["stage1_frames"], ["stage2_frames"], ["stage3_frames"]]
💡 WORKFLOW: temporal_frame_search_topk (multi-stage) → frame_groups → grid_search ENHANCED → stage candidates cho valid_video_query

� USE CASES:
🔸 Temporal sequence có 2+ stages: "người A nói" → "người B phản ứng" → "kết quả"
🔸 So sánh candidates từ different temporal stages
🔸 Tìm stage/chuỗi có candidates quality cao nhất
🔸 Rank multiple temporal sequences để chọn tốt nhất cho validation

📊 VÍ DỤ THỰC TẾ:
```json
{
  "frame_groups": [
    ["stage1_frame1.jpg", "stage1_frame2.jpg", "stage1_frame3.jpg"],  // Stage: "người A bắt đầu nói"
    ["stage2_frame1.jpg", "stage2_frame2.jpg"],                       // Stage: "người B phản ứng" 
    ["stage3_frame1.jpg", "stage3_frame2.jpg", "stage3_frame3.jpg"]   // Stage: "kết thúc cuộc trò chuyện"
  ]
}
```

⚠️ LƯU Ý:
- Mỗi nhóm = 1 temporal stage từ query_sequence
- Mỗi nhóm tối đa 6 frame (có thể tùy chỉnh)
- Phải dùng layout_mode="separate" để phân biệt stages
- Kết quả sẽ rank stages và recommend stage candidates tốt nhất"""
                },
                "group_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": """[ENHANCED MODE] Câu hỏi riêng cho từng nhóm frame.
                    
📝 Quy tắc: Số lượng phải bằng số nhóm trong frame_groups
💡 Ví dụ:
- Group 1: "Nhóm này có frame nào cho thấy người A đang nói?"
- Group 2: "Nhóm này có frame nào cho thấy người B phản ứng?"
- Group 3: "Nhóm này có frame nào cho thấy kết quả cuối cùng?"

✅ Mỗi query nên tập trung vào đặc điểm riêng của nhóm đó"""
                },
                "comparison_query": {
                    "type": "string", 
                    "description": """[ENHANCED SEPARATE MODE] Câu hỏi so sánh để rank temporal stage candidates.
                    
🎯 FOCUS: So sánh multiple temporal stages để tìm stage có candidates tốt nhất cho validation
📝 FORMAT MẪU để tối ưu stage candidate finding:

✅ VÍ DỤ TỐT (focus vào ranking stage candidates):
- "So sánh 3 temporal stages này. Stage nào có frame candidates chất lượng cao nhất và phù hợp với sequence gốc? Rank theo độ ưu tiên."
- "Đánh giá từng temporal stage và recommend 1-2 stages có candidates tốt nhất để validate với valid_video_query."
- "Từ các stages này, stage nào có frame sequence candidates phù hợp và rõ ràng nhất? Rank theo khả năng thành công khi validate."
- "Compare temporal stages quality. Recommend top stage candidates có potential cao nhất cho video validation."

💡 STAGE COMPARISON CRITERIA:
- Chất lượng frame (độ rõ nét, lighting, angle)
- Tính phù hợp với original temporal sequence  
- Completeness của stage (có đủ thông tin không)
- Continuity between frames trong stage

🔗 CONNECTION với valid_video_query:
Comparison này sẽ tạo ra ranked stage candidates → valid_video_query sẽ validate stage tốt nhất đầu tiên

⚠️ LƯU Ý: Dùng thay thế hoặc kết hợp với group_queries"""
                },
                "layout_mode": {
                    "type": "string",
                    "enum": ["separate", "combined"],
                    "default": "separate",
                    "description": """[ENHANCED MODE] Cách bố trí lưới hình ảnh.
                    
🔸 "separate": Mỗi nhóm tạo lưới riêng, có label phân biệt
   - Ưu điểm: Dễ phân biệt nhóm, phù hợp so sánh
   - Nhược điểm: Cần nhiều không gian hình ảnh

🔸 "combined": Tất cả frame trong một lưới lớn
   - Ưu điểm: Compact, dễ nhìn tổng thể  
   - Nhược điểm: Khó phân biệt nhóm
   
💡 Khuyến nghị: "separate" cho so sánh, "combined" cho overview"""
                },
                "max_images_per_group": {
                    "type": "integer",
                    "default": 6,
                    "description": """[ENHANCED MODE] Số lượng frame tối đa mỗi nhóm.
                    
📝 Mặc định: 6 frame/nhóm
⚖️ Trade-off:
- Nhiều frame = thông tin đầy đủ hơn nhưng lưới lớn hơn
- Ít frame = lưới gọn nhưng có thể thiếu thông tin

💡 Gợi ý: 4-6 frame cho most cases, 8-10 nếu cần chi tiết"""
                },
                "grid_dimensions_per_group": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 2,
                    "default": [2, 3],
                    "description": """[ENHANCED MODE] Kích thước lưới cho mỗi nhóm khi dùng separate mode.
                    
📝 Mặc định: [2, 3] = 2 hàng x 3 cột = 6 ảnh/nhóm
💡 Các option phổ biến:
- [2, 2] = 4 ảnh/nhóm
- [2, 3] = 6 ảnh/nhóm  
- [3, 3] = 9 ảnh/nhóm
- [2, 4] = 8 ảnh/nhóm"""
                }
            },
            "anyOf": [
                {"required": ["frame_urls", "query"]},
                {"required": ["frame_groups"], "anyOf": [{"required": ["comparison_query"]}, {"required": ["group_queries"]}]}
            ]
        }
    },
    "get_video": {
        "name": "get_video",
        "description": """🎬 GET VIDEO - ENHANCED VIDEO CLIP GENERATOR

🔥 VAI TRÒ CHÍNH: Tool tạo video clip từ frame range với validation toàn diện và output tối ưu cho agent workflow.

⚡ CÁCH HOẠT ĐỘNG (Sequence Thinking):
1️⃣ Input Validation → 2️⃣ API Call → 3️⃣ Response Validation → 4️⃣ Enhanced Output

📋 WORKFLOW CHUẨN:
🔸 temporal_frame_search_topk → grid_search → get_video → valid_video_query
🔸 Tạo video clip từ frame range được xác định bởi grid_search
🔸 Prepare video cho valid_video_query validation

⚡ TÍNH NĂNG ENHANCED:
✅ Input validation: video name format, frame range logic, reasonable duration
✅ Robust error handling: network, server, validation errors với detailed suggestions
✅ Response verification: đảm bảo video clip thực sự accessible
✅ Enhanced output: metadata đầy đủ, ready_for_validation signal
✅ Integration-ready: output format tối ưu cho valid_video_query tool

🎯 KHI NÀO SỬ DỤNG:
✅ Sau khi grid_search đã identify frame range phù hợp
✅ Cần tạo video clip để validate với valid_video_query  
✅ Có video_name và frame range cụ thể từ temporal search results

❌ KHÔNG DÙNG KHI:
❌ Chưa có frame range cụ thể (dùng temporal_search trước)
❌ Chỉ cần static frame analysis (dùng valid_frame_query)
❌ Video name không rõ ràng hoặc frame range không hợp lệ

🔗 OUTPUT CHO VALID_VIDEO_QUERY:
- clip_url: URL tương đối của video clip
- full_url: URL đầy đủ để access video  
- ready_for_validation: true signal
- metadata: duration, frame_count, timing info""",
        "parameters": {
            "type": "object",
            "properties": {
                "video_name": {
                    "type": "string",
                    "description": """Tên video theo format L##_V### (ví dụ: L01_V001, L05_V010).
                    
📝 FORMAT REQUIRED: L##_V###
- L: Literal character
- ##: 2-digit lesson number (01-99)  
- _V: Literal separator + V
- ###: 3-digit video number (001-999)

✅ VÍ DỤ HỢP LỆ: L01_V001, L05_V010, L12_V045
❌ VÍ DỤ KHÔNG HỢP LỆ: L1_V1, video01, L01_V1

💡 Lấy từ temporal search results hoặc grid search metadata"""
                },
                "start_frame": {
                    "type": "integer",
                    "description": """Frame bắt đầu (số nguyên dương, ≥ 0).
                    
📝 VALIDATION RULES:
- Phải ≥ 0 (frame index bắt đầu từ 0)
- Phải < end_frame để có video clip hợp lệ
- Thường lấy từ temporal search result start point

💡 Frame numbering thường bắt đầu từ 0, so với timestamp có thể khác nhau tùy video"""
                },
                "end_frame": {
                    "type": "integer", 
                    "description": """Frame kết thúc (số nguyên dương, > start_frame).
                    
📝 VALIDATION RULES:
- Phải > start_frame (tối thiểu start_frame + 1 cho single frame clip)
- Auto-adjust: nếu ≤ start_frame sẽ được set thành start_frame + 1
- Frame count ≤ 1800 (tối đa ~1 phút at 30fps) để tránh file quá lớn

💡 Tool sẽ tự động điều chỉnh nếu end_frame ≤ start_frame để tạo clip tối thiểu 1 frame"""
                }
            },
            "required": ["video_name", "start_frame", "end_frame"]
        }
    },
    "valid_video_query": {
        "name": "valid_video_query",
        "description": """🎬 ENHANCED VIDEO VALIDATION - TRỰC TIẾP ANALYZE VIDEO

🔥 VAI TRÒ CHÍNH: Tool validation cuối cùng trong workflow, sử dụng Gemini Video API để phân tích trực tiếp video content với temporal understanding đầy đủ.

⚡ CẢI TIẾN QUAN TRỌNG:
✅ DIRECT VIDEO UPLOAD: Gửi video trực tiếp lên Gemini thay vì extract frames
✅ TEMPORAL CONTINUITY: Hiểu được motion, transitions, và temporal flow
✅ MOTION ANALYSIS: Phân tích movement và actions trong video context
✅ ENHANCED VALIDATION: Chi tiết hơn về sequence validation và scene analysis
✅ ROBUST PROCESSING: Handle video upload, processing, timeout với comprehensive error handling

📋 WORKFLOW CHUẨN:
🔸 temporal_frame_search_topk → grid_search → get_video → valid_video_query (FINAL VALIDATION)
🔸 Grid search identifies candidates → get_video creates clips → valid_video_query validates with full video context

🎯 KHI NÀO SỬ DỤNG:
✅ Có video clip URL từ get_video tool
✅ Cần validation chi tiết cho temporal sequence
✅ Yêu cầu analysis về motion, transitions, và temporal patterns
✅ Final step để confirm video matches query requirements

⚡ WORKFLOW SEQUENCE:
1️⃣ Download Video → 2️⃣ Upload to Gemini → 3️⃣ Wait Processing → 4️⃣ Video Analysis → 5️⃣ Cleanup

🔗 INPUT từ GET_VIDEO:
- video_clip_url: URL của video clip đã được tạo
- query_sequence: Chuỗi temporal events cần validate
- question: Optional câu hỏi specific về video content

📊 OUTPUT ENHANCED:
- Detailed sequence_analysis cho từng step
- Video_analysis với temporal_insights, motion_analysis, scene_transitions
- Missing_elements và extra_elements analysis
- Recommendations để improve validation
- Technical quality assessment

❌ KHÔNG DÙNG KHI:
❌ Chưa có video clip URL (cần get_video trước)
❌ Chỉ cần frame-level analysis (dùng valid_frame_query)
❌ Video quá lớn (>50MB) hoặc quá dài (>5 phút)

🚀 PERFORMANCE:
- Video upload và processing time: 10-60 seconds
- Analysis time: 30-120 seconds depending on video complexity
- File size limit: 50MB per video clip
- Supported formats: MP4, AVI, MOV, WebM""",
        "parameters": {
            "type": "object",
            "properties": {
                "video_clip_url": {
                    "type": "string",
                    "description": """URL của đoạn video ngắn cần xác thực (từ get_video tool).
                    
📝 FORMAT: Relative path (/media/video_clips/...) hoặc full URL
💡 SOURCE: Output từ get_video tool provide clip_url hoặc full_url
✅ VÍ DỤ: "/media/video_clips/L01_V001_f100-150.mp4"

🔗 INTEGRATION: get_video tool tạo video clip → provide URL → valid_video_query validate"""
                },
                "query_sequence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": """Chuỗi các mô tả sự kiện trong video theo thứ tự thời gian.
                    
📝 STRUCTURE: Danh sách các mô tả events theo temporal order
💡 SOURCE: Original temporal query sequence từ user hoặc temporal_frame_search_topk

✅ VÍ DỤ:
[
    "Người đàn ông mặc áo đỏ bắt đầu nói chuyện",
    "Anh ta chỉ tay về phía bảng white board", 
    "Người phụ nữ ngồi bên cạnh gật đầu đồng ý",
    "Cuộc trò chuyện kết thúc với cả hai người cười"
]

🎯 MỤC ĐÍCH: Validate từng step trong sequence có xuất hiện đúng thứ tự trong video không"""
                },
                "question": {
                    "type": "string",
                    "description": """Câu hỏi tùy chọn về nội dung video để phân tích thêm.
                    
📝 OPTIONAL: Không bắt buộc, nhưng useful cho specific analysis
💡 USE CASES:
- "Video có rõ ràng không? Có bị mờ hoặc tối không?"
- "Người nói có pronunciation rõ ràng không?"
- "Background có ảnh hưởng đến nội dung chính không?"
- "Video có đủ context để hiểu complete story không?"

✅ VÍ DỤ SPECIFIC QUESTIONS:
- "Người đàn ông có đang hold microphone không?"
- "Slide presentation có visible và readable không?"
- "Audio quality có tốt không (nếu có)?"
- "Camera angle có phù hợp với nội dung không?"

🎯 ENHANCE: Cung cấp additional context cho comprehensive validation"""
                }
            },
            "required": ["video_clip_url", "query_sequence"]
        }
    }
}
