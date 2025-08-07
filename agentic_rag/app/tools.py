"""
Tool implementations for the Agentic RAG system.
Each tool is a standalone function that can be called by the LangChain agent.

Recent refactoring:
- Moved constants to constants.py
- Moved utility functions to tool_utils.py
- Improved code organization and maintainability
"""
import json
import logging
import os
import base64

import asyncio

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
    create_enhanced_prompt
)
from .schemas import GetFrameInput, GetVideoInput, TemporalSearchInput, GridSearchInput, ValidFrameQueryInput, ValidVideoQueryInput, SynthesisInput, SearchFramesInput
from .utils import robust_json_parse, strip_markdown_code_fences
import requests
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=config.GOOGLE_API_KEY)


# def search_frames(input_params: str) -> str:
#     """
#     Tool: Thực hiện tìm kiếm đa phương thức (text, OCR, hình ảnh) và theo trình tự thời gian
#     bằng cách gọi đến API tìm kiếm vector.
#     Đây là công cụ tìm kiếm chính, hỗ trợ các truy vấn phức tạp với cấu trúc và trọng số tùy chỉnh.

#     Args:
#         input_params (str): JSON string chứa các tham số:
#             - k (int): Số lượng chuỗi kết quả cuối cùng cần trả về, mặc định là 10.
#             - queries_structure (List[Dict]): Một danh sách các đối tượng mô tả các stage truy vấn.
#               Mỗi stage có thể chứa 'text' (str), 'ocr' (str), hoặc 'image_ref' (str - tên file ảnh).
#             - images_data (Optional[Dict[str, str]]): Một đối tượng ánh xạ tên file ảnh (image_ref)
#               tới dữ liệu ảnh base64. Chỉ cần thiết nếu queries_structure chứa 'image_ref'.
#             - weights (Optional[Dict[str, float]]): Một đối tượng JSON chứa các trọng số
#               cho các loại truy vấn (ví dụ: {"text": 0.5, "ocr": 0.3, "image": 0.2}).

#     Returns:
#         str: JSON string chứa danh sách kết quả tìm kiếm hoặc thông báo lỗi.
#     """
#     try:
#         # Strip markdown code fences if present
#         clean_input = strip_markdown_code_fences(input_params)
#         parsed_input = SearchFramesInput.parse_raw(clean_input)
#         k = parsed_input.k
#         queries_structure = parsed_input.queries_structure
#         images_data = parsed_input.images_data
#         weights = parsed_input.weights

#         logger.info(f"Searching frames with k={k}, queries_structure={queries_structure}, weights={weights}")

#         # Prepare form-data and files for the API request
#         form_data = {
#             "k": str(k),
#             "queries_structure": json.dumps([stage.dict(exclude_unset=True) for stage in queries_structure]),
#         }

#         if weights:
#             form_data["weights"] = json.dumps(weights)

#         files = []
#         if images_data:
#             for filename, base64_data in images_data.items():
#                 try:
#                     img_bytes = base64.b64decode(base64_data)
#                     mime_type = "image/png"  # Default, could be improved by inferring from filename
#                     files.append(("image_files", (filename, img_bytes, mime_type)))
#                 except Exception as e:
#                     logger.warning(f"Could not decode base64 image for {filename}: {e}")
#                     return f"Lỗi: Không thể giải mã ảnh base64 cho '{filename}': {e}"

#         # Use helper function for API request
#         api_result = make_search_api_request(form_data, files)
        
#         if api_result["success"]:
#             return json.dumps(api_result["data"])
#         else:
#             return json.dumps({"error": api_result["error"]})

#     except Exception as e:
#         error_msg = f"Unexpected error in search_frames: {str(e)}"
#         logger.error(error_msg)
#         return json.dumps({"error": f"Lỗi không xác định: {error_msg}"})


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
            {"model_name": "ViT-H-14-quickgelu", "weight": 0.45}
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
    return get_frames_from_urls(frame_urls)


def get_video(input_params: str) -> str:
    """
    Tool: Trích xuất một đoạn video ngắn từ một video dài hơn trên server, dựa vào frame bắt đầu và thời lượng.
    Chỉ sử dụng tool này sau khi bạn đã xác định được một frame bắt đầu tiềm năng (ví dụ: từ temporal_frame_search_topk)
    và cần lấy cả đoạn video xung quanh nó để xác thực toàn diện hơn.

    Args:
        start_frame_id (str): ID của frame bắt đầu cho đoạn video.
        duration_seconds (int): Thời lượng của đoạn video cần trích xuất (tính bằng giây).

    Returns:
        str: JSON string chứa URL của đoạn video clip đã trích xuất hoặc thông báo lỗi.
    """
    try:
        # Strip markdown code fences if present
        clean_input = strip_markdown_code_fences(input_params)
        parsed_input = GetVideoInput.parse_raw(clean_input)
        start_frame_id = parsed_input.start_frame_id
        duration_seconds = parsed_input.duration_seconds

        logger.info(f"Getting video clip from start_frame_id: {start_frame_id} with duration: {duration_seconds}s")
        
        # Assuming a dedicated endpoint for video clipping
        clip_api_url = f"{config.MEDIA_API_URL}/video/clip"
        
        payload = {
            "start_frame_id": start_frame_id,
            "duration_seconds": duration_seconds
        }
        
        response = requests.post(
            clip_api_url,
            json=payload,
            timeout=config.API_REQUEST_TIMEOUT
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        result = response.json()
        logger.info(f"Video clip result: {result}")
        return json.dumps(result)

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error calling video clip API: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Unexpected error in get_video: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


def grid_search(input_params: str) -> str:
    """
    🔍 GRID SEARCH - Công cụ phân tích đồng thời nhiều frame bằng lưới hình ảnh
    
    ⚡ TÍNH NĂNG CHÍNH:
    - Ghép nhiều frame thành lưới ảnh và gửi đến Gemini để phân tích cùng lúc
    - Tiết kiệm 80-90% API calls so với phân tích từng frame riêng lẻ
    - Hỗ trợ so sánh và tìm mối liên hệ giữa các frame
    - 2 chế độ: Legacy (đơn giản) và Enhanced (nâng cao, nhiều nhóm)
    
    📋 KHI NÀO SỬ DỤNG:
    ✅ Sau khi có danh sách frame ứng viên từ temporal_frame_search_topk
    ✅ Cần đánh giá/so sánh 3-20 frame cùng lúc
    ✅ Tìm frame tốt nhất trong nhóm ứng viên
    ✅ So sánh nhiều chuỗi frame từ các kết quả khác nhau
    ✅ Xác thực nhanh tính phù hợp của nhiều frame
    
    🎯 WORKFLOW KHUYẾN NGHỊ:
    1. Dùng temporal_frame_search_topk → có frame URLs
    2. Nhóm frame theo logic (cùng chuỗi, cùng chủ đề...)
    3. Dùng grid_search để phân tích/so sánh nhanh
    4. Nếu cần chi tiết hơn → dùng valid_frame_query cho frame cụ thể

    Args:
        input_params (str): JSON string chứa các tham số:
        
        🔸 LEGACY FORMAT (đơn giản):
            - frame_urls (List[str]): Danh sách URL frame cần phân tích
            - grid_dimensions (Tuple[int, int], optional): Kích thước lưới (rows, cols), mặc định (2,2)
            - query (str): Câu hỏi phân tích cho toàn bộ lưới
            
        🔸 ENHANCED FORMAT (nâng cao):
            - frame_groups (List[List[str]]): Nhiều nhóm frame URLs để so sánh
            - group_queries (List[str], optional): Câu hỏi riêng cho từng nhóm
            - comparison_query (str, optional): Câu hỏi so sánh giữa các nhóm
            - layout_mode (str): "separate" hoặc "combined"
            - max_images_per_group (int): Giới hạn frame mỗi nhóm (mặc định 6)
            - grid_dimensions_per_group (Tuple[int, int]): Kích thước lưới mỗi nhóm

    Returns:
        str: JSON string chứa:
        - is_match (bool): Có frame phù hợp không
        - confidence_score (float): Độ tin cậy 0.0-1.0
        - reasoning (str): Giải thích chi tiết
        - relevant_frames (List): Danh sách frame phù hợp nhất
        - metadata (dict): Thông tin về quá trình xử lý
        
    Examples:
        # Legacy mode - tìm frame tốt nhất
        {
            "frame_urls": ["frame1.jpg", "frame2.jpg", "frame3.jpg", "frame4.jpg"],
            "grid_dimensions": [2, 2],
            "query": "Frame nào cho thấy người đàn ông mặc áo đỏ đang nói chuyện?"
        }
        
        # Enhanced mode - so sánh nhiều chuỗi
        {
            "frame_groups": [
                ["seq1_frame1.jpg", "seq1_frame2.jpg"],
                ["seq2_frame1.jpg", "seq2_frame2.jpg"]
            ],
            "comparison_query": "Chuỗi nào diễn ra trước?",
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
    frame_urls = parsed_input.frame_urls
    grid_dimensions = parsed_input.grid_dimensions or (2, 2)
    query = parsed_input.query

    if not frame_urls:
        return json.dumps({"error": "Tham số 'frame_urls' không thể rỗng."})
    if not query:
        return json.dumps({"error": "Tham số 'query' không thể rỗng."})

    # Use existing logic
    pil_images = get_frames(frame_urls)
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


def _grid_search_enhanced(parsed_input: GridSearchInput) -> str:
    """Handle enhanced multi-group grid search format."""
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
            pil_images = get_frames(limited_urls)
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


def valid_frame_query(input_params: str) -> str:
    """
    Tool: Xác thực xem một chuỗi các khung hình có khớp với một chuỗi các mô tả tương ứng hay không.
    Sử dụng khi cần kiểm tra từng frame một cách chi tiết. Tool này kém hiệu quả hơn grid_search nếu chỉ cần một đánh giá tổng thể.

    Args:
        frames (List[str]): Danh sách frame_url cần xác thực.
        queries (List[str]): Danh sách các câu mô tả tương ứng với từng frame.

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


# Tool descriptions for LangChain
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
        "description": """🔍 GRID SEARCH - Công cụ phân tích đồng thời nhiều frame bằng lưới hình ảnh

⚡ ĐẶC ĐIỂM CHÍNH:
- Ghép nhiều frame thành lưới ảnh và phân tích đồng thời bằng Vision AI
- Tiết kiệm đáng kể API calls so với phân tích từng frame riêng lẻ
- Hỗ trợ 2 chế độ: Legacy (đơn giản) và Enhanced (nâng cao)

📋 KHI NÀO SỬ DỤNG:
✅ Sau khi có danh sách frame ứng viên từ temporal_frame_search_topk
✅ Cần so sánh/đánh giá nhiều frame cùng lúc (3-20 frame)
✅ Tìm frame tốt nhất trong một nhóm ứng viên
✅ So sánh nhiều chuỗi frame khác nhau
✅ Xác thực nhanh tính phù hợp của nhiều frame

❌ KHÔNG DÙNG KHI:
❌ Chỉ có 1-2 frame (dùng valid_frame_query thay thế)
❌ Cần phân tích chi tiết từng frame riêng biệt
❌ Chưa có frame URLs cụ thể

🎯 USE CASES THỰC TẾ:

1️⃣ LEGACY MODE - Phân tích đơn giản:
   - Input: 1 danh sách frame URLs + 1 câu hỏi chung
   - Output: Đánh giá tổng thể + frame nào phù hợp nhất
   - Ví dụ: "Trong 8 frame này, frame nào cho thấy người đàn ông mặc áo đỏ đang nói chuyện?"

2️⃣ ENHANCED MODE - So sánh nâng cao:
   - Input: Nhiều nhóm frame + câu hỏi riêng cho từng nhóm + câu hỏi so sánh
   - Output: Phân tích từng nhóm + so sánh giữa các nhóm
   - Ví dụ: So sánh 3 chuỗi frame khác nhau về cùng một sự kiện

💡 WORKFLOW KHUYẾN NGHỊ:
1. Dùng temporal_frame_search_topk để tìm frame ứng viên
2. Nhóm frame theo logic (cùng chuỗi thời gian, cùng chủ đề, etc.)
3. Dùng grid_search để phân tích/so sánh nhanh
4. Nếu cần chi tiết hơn, dùng valid_frame_query cho frame cụ thể

📊 HIỆU SUẤT:
- Legacy: 1 API call cho 4-16 frame
- Enhanced: 1 API call cho nhiều nhóm frame (tối đa ~50 frame)
- Tiết kiệm 80-90% API calls so với phân tích riêng lẻ""",
        "parameters": {
            "type": "object",
            "properties": {
                "frame_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": """[LEGACY MODE] Danh sách URL frame cần phân tích trong một lưới đơn.
                    
📝 Cách dùng: Cung cấp 4-16 frame URLs để tạo lưới 2x2, 3x3, 4x4...
💡 Ví dụ: ["frame1.jpg", "frame2.jpg", "frame3.jpg", "frame4.jpg"]
⚠️ Lưu ý: Phải đi kèm với 'query', không dùng cùng 'frame_groups'"""
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
                    "description": """[LEGACY MODE] Câu hỏi/nhiệm vụ phân tích cho toàn bộ lưới.
                    
📝 Ví dụ tốt:
- "Frame nào trong lưới này cho thấy người đàn ông mặc áo đỏ đang nói chuyện?"
- "Sắp xếp các frame theo thứ tự thời gian hợp lý nhất"
- "Frame nào có chất lượng hình ảnh tốt nhất và rõ nét nhất?"
- "Tìm frame có nhiều người nhất trong cảnh"

❌ Tránh câu hỏi mơ hồ: "Phân tích lưới này", "Frame nào tốt?"
✅ Câu hỏi cụ thể: "Frame nào cho thấy X đang làm Y?"
"""
                },
                "frame_groups": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "description": """[ENHANCED MODE] Danh sách các nhóm frame để so sánh.
                    
📝 Cấu trúc: [["group1_frame1", "group1_frame2"], ["group2_frame1", "group2_frame2"]]
💡 Use cases:
- So sánh nhiều chuỗi thời gian khác nhau
- So sánh kết quả từ các query khác nhau
- Phân tích nhiều góc nhìn của cùng một sự kiện

📊 Giới hạn: Mỗi nhóm tối đa 6 frame (có thể tùy chỉnh bằng max_images_per_group)
⚠️ Phải đi kèm group_queries HOẶC comparison_query"""
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
                    "description": """[ENHANCED MODE] Câu hỏi so sánh giữa các nhóm.
                    
📝 Mục đích: Phân tích mối quan hệ/khác biệt giữa các nhóm
💡 Ví dụ:
- "Nhóm nào cho thấy sự kiện diễn ra sớm hơn?"
- "So sánh chất lượng hình ảnh giữa các nhóm"
- "Nhóm nào có nhiều người tham gia hơn?"
- "Xác định thứ tự thời gian của các nhóm sự kiện"

⚠️ Có thể dùng thay thế hoặc kết hợp với group_queries"""
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
    }
}
