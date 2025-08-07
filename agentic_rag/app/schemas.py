"""
Pydantic models for API request/response and tool schemas.
"""
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field


# API Request/Response Models
class VideoSearchRequest(BaseModel):
    """Request model for the /find-video endpoint."""
    descriptions: List[str] = Field(
        ...,
        description="Danh sách mô tả video bằng ngôn ngữ tự nhiên (tiếng Việt hoặc tiếng Anh). Mỗi phần tử là một mô tả.",
        min_items=1
    )


class VideoSearchResponse(BaseModel):
    """Response model for successful video search."""
    success: bool = Field(default=True)
    clip_url: Optional[str] = Field(None, description="URL của đoạn video clip tìm được.")
    frames: List[str] = Field(..., description="Danh sách các frame_url liên quan.")
    confidence_score: float = Field(..., description="Điểm tin cậy từ 0.0 đến 1.0.")
    reasoning: str = Field(..., description="Lý do Agent chọn các frame/video này.")
    answer_to_question: Optional[str] = Field(None, description="Câu trả lời cho câu hỏi nếu có.")


class ErrorResponse(BaseModel):
    """Response model for errors."""
    success: bool = Field(default=False)
    error_type: str = Field(..., description="Loại lỗi")
    error_message: str = Field(..., description="Chi tiết lỗi")


# Tool Input Models
class GetFrameInput(BaseModel):
    """Input schema for get_frame tool."""
    frame_urls: List[str] = Field(description="Danh sách các URL định danh của khung hình cần lấy.")


class GetVideoInput(BaseModel):
    """Input schema for get_video tool."""
    start_frame_id: str = Field(description="ID của frame bắt đầu cho đoạn video.")
    duration_seconds: int = Field(default=5, description="Thời lượng của đoạn video cần trích xuất (tính bằng giây).")


class TemporalSearchInput(BaseModel):
    """Input schema for temporal_frame_search_topk tool."""
    query_sequence: List[Dict[str, Any]] = Field(description="Một chuỗi các stage truy vấn, mỗi stage có thể chứa 'text' hoặc 'ocr'.")
    k: int = Field(default=5, description="Số lượng chuỗi frame hàng đầu cần trả về.")
    weights: Optional[Dict[str, float]] = Field(default=None, description="Trọng số cho các loại tìm kiếm (text, ocr).")


class GridSearchInput(BaseModel):
    """Input schema for grid_search tool - Enhanced to support multiple frame groups."""
    # Legacy format (backward compatible)
    frame_urls: Optional[List[str]] = Field(default=None, description="[Legacy] Danh sách các URL của frame cần xếp vào lưới.")
    grid_dimensions: Optional[Tuple[int, int]] = Field(default=None, description="[Legacy] Kích thước của lưới, ví dụ (2, 2) cho lưới 4 ảnh.")
    query: Optional[str] = Field(default=None, description="[Legacy] Câu hỏi hoặc mô tả chung để Gemini phân tích toàn bộ lưới ảnh.")
    
    # Enhanced format for multiple frame groups
    frame_groups: Optional[List[List[str]]] = Field(default=None, description="Danh sách các nhóm frame URLs. Mỗi nhóm là một list các frame URLs.")
    group_queries: Optional[List[str]] = Field(default=None, description="Câu hỏi riêng cho từng nhóm frame (optional).")
    comparison_query: Optional[str] = Field(default=None, description="Câu hỏi để so sánh giữa các nhóm frame.")
    layout_mode: str = Field(default="separate", description="Layout mode: 'separate' (mỗi group một lưới riêng) hoặc 'combined' (tất cả trong một lưới lớn).")
    max_images_per_group: int = Field(default=6, description="Số lượng ảnh tối đa mỗi nhóm để tránh lưới quá lớn.")
    grid_dimensions_per_group: Optional[Tuple[int, int]] = Field(default=(2, 3), description="Kích thước lưới cho mỗi nhóm khi dùng layout separate.")


class ValidFrameQueryInput(BaseModel):
    """Input schema for valid_frame_query tool."""
    frames: List[str] = Field(description="Danh sách frame_url cần xác thực.")
    queries: List[str] = Field(description="Danh sách các câu mô tả tương ứng với từng frame.")


class ValidVideoQueryInput(BaseModel):
    """Input schema for valid_video_query tool."""
    video_clip_url: str = Field(description="URL của đoạn video ngắn cần xác thực.")
    query_sequence: List[str] = Field(description="Chuỗi các mô tả sự kiện trong video.")
    question: Optional[str] = Field(default=None, description="Câu hỏi tùy chọn về nội dung video.")


class SynthesisInput(BaseModel):
    """Input schema for result_synthesizer tool."""
    intermediate_steps: List[dict] = Field(description="Lịch sử các hành động và quan sát của Agent.")
    final_data: dict = Field(description="Dữ liệu cuối cùng được chọn (ví dụ: từ valid_video_query).")


class QueryStage(BaseModel):
    text: Optional[str] = None
    ocr: Optional[str] = None
    image_ref: Optional[str] = None  # This will be a key to an image in the 'images_data' map


class SearchFramesInput(BaseModel):
    k: int = Field(10, description="Số lượng chuỗi kết quả cuối cùng cần trả về.")
    queries_structure: List[QueryStage] = Field(
        ...,
        description='Một danh sách các đối tượng mô tả các stage truy vấn, mỗi stage có thể chứa text, ocr, hoặc image_ref.'
    )
    images_data: Optional[Dict[str, str]] = Field(
        None,
        description='Một đối tượng ánh xạ tên file ảnh (image_ref) tới dữ liệu ảnh base64.'
    )
    weights: Optional[Dict[str, float]] = Field(
        None,
        description='Một đối tượng JSON chứa các trọng số cho các loại truy vấn (text, ocr, image).'
    )


# Internal Agent Models
class AgentThought(BaseModel):
    """Represents an agent's reasoning step."""
    step: str
    reasoning: str
    action: Optional[str] = None
    observation: Optional[str] = None


class AgentResult(BaseModel):
    """Final result from agent execution."""
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None
    thoughts: List[AgentThought] = []
