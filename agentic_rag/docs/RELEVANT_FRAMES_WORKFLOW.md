# Hướng Dẫn Workflow Xử Lý Relevant Frames

## Tổng Quan

Đã implement tính năng mới trong hệ thống agent để tự động xử lý `relevant_frames` từ kết quả `grid_search` và thực hiện validation video một cách hoàn chỉnh.

## Workflow Mới

### 1. Luồng Xử Lý Chuẩn

```
temporal_frame_search_topk 
    ↓
grid_search (trả về relevant_frames)
    ↓
process_relevant_frames (tự động)
    ↓
get_video (với minimum 750 frames)
    ↓
valid_video_query (validation cuối cùng)
    ↓
Final Answer (với video clip URL)
```

### 2. Logic Xử Lý Relevant Frames

Khi `grid_search` trả về kết quả có trường `relevant_frames`:

```json
{
  "is_match": false,
  "confidence_score": 1.0,
  "reasoning": "...",
  "relevant_frames": ["frame_1", "frame_2"]
}
```

Hệ thống sẽ tự động:

1. **Parse Frame Numbers**: Extract số frame từ relevant_frames
   - `"frame_1"` → `1`
   - `"L05_V027/23198.jpg"` → video: `L05_V027`, frame: `23198`

2. **Calculate Frame Range**: Tính toán range cần thiết
   - Tìm `min_frame` và `max_frame` từ relevant_frames
   - Kiểm tra total frames hiện tại

3. **Expand to Minimum 750 Frames**: 
   ```python
   if current_range < 750:
       expand_needed = 750 - current_range
       expand_each_side = expand_needed // 2
       start_frame = max(1, min_frame - expand_each_side)
       end_frame = max_frame + expand_each_side
   ```

4. **Create Video Clip**: Sử dụng `get_video` với expanded range

5. **Validate with valid_video_query**: Validation cuối cùng bắt buộc

### 3. Output Format Mới

Final Answer sẽ bao gồm thêm thông tin về relevant_frames processing:

```json
{
  "success": true,
  "frames": ["L05_V027/23198.jpg", "L05_V027/23199.jpg"],
  "video_clip_url": "http://...",
  "confidence_score": 0.85,
  "reasoning": "...",
  "validation_details": {...},
  "relevant_frames_processed": true,
  "video_frame_range": {
    "start_frame": 23000,
    "end_frame": 23750,
    "total_frames": 751,
    "original_relevant_frames": ["frame_1", "frame_2"]
  }
}
```

## Implementation Details

### 1. Method Mới: `_process_relevant_frames()`

- **Input**: `relevant_frames` list và `agent_output` string
- **Output**: Dict với validation result hoặc error
- **Logic**: Parse frames → Calculate range → Expand → Create video → Validate

### 2. Cập Nhật Constants

Thêm workflow rules mới trong `AGENT_WORKFLOW_PHASE_3`:

```
🔍 RELEVANT_FRAMES PROCESSING (CRITICAL NEW STEP):
f. If grid_search returns relevant_frames field in response:
   - Extract frame numbers from relevant_frames
   - Calculate minimum 750-frame range
   - Use get_video to create video clip with expanded range
   - Use valid_video_query to validate video clip
```

### 3. Enhanced Parsing Logic

Cả JSON parsing và text extraction đều được cập nhật để detect và xử lý `relevant_frames`.

## Error Handling

Hệ thống xử lý các trường hợp lỗi:

1. **Frame Parsing Error**: Không thể parse frame numbers
2. **Video Creation Error**: Lỗi khi tạo video clip
3. **Validation Failed**: valid_video_query thất bại
4. **Processing Error**: Lỗi chung trong quá trình xử lý

## Lợi Ích

1. **Tự động hóa hoàn toàn**: Không cần manual intervention
2. **Đảm bảo chất lượng**: Minimum 750 frames cho video clip
3. **Validation đầy đủ**: Mandatory valid_video_query step
4. **Transparency**: Detailed logging và frame range information
5. **Error resilience**: Comprehensive error handling

## Test Cases

Để test tính năng này:

1. Tạo query dẫn đến grid_search trả về relevant_frames
2. Kiểm tra log để thấy expansion logic
3. Verify video clip có đủ 750+ frames
4. Confirm valid_video_query được gọi
5. Check final answer format có đầy đủ thông tin

## Notes

- Tính năng này backward compatible với workflow cũ
- Chỉ activate khi grid_search có relevant_frames
- Luôn ưu tiên relevant_frames processing trước standard processing
- Video frame expansion logic đảm bảo không vượt quá video boundaries
