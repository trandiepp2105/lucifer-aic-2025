# Grid Search Tool - Hướng Dẫn Sử Dụng Chi Tiết

## 🎯 Tổng Quan

Grid Search là công cụ phân tích hàng loạt frame bằng cách tạo lưới hình ảnh và sử dụng Vision AI để phân tích đồng thời. Đây là công cụ tối ưu nhất để xử lý nhiều frame cùng lúc.

## ⚡ Ưu Điểm Chính

- **Tiết kiệm API calls**: 80-90% so với phân tích từng frame riêng lẻ  
- **Phân tích đồng thời**: Vision AI có thể so sánh và tìm mối liên hệ giữa các frame
- **2 chế độ linh hoạt**: Legacy (đơn giản) và Enhanced (nâng cao)
- **Tối ưu hiệu suất**: 1 API call xử lý 4-50 frame

## 📋 Khi Nào Sử Dụng

### ✅ NÊN DÙNG
- Sau khi có frame URLs từ `temporal_frame_search_topk`
- Cần đánh giá/so sánh 3-20 frame cùng lúc
- Tìm frame tốt nhất trong nhóm ứng viên
- So sánh nhiều chuỗi frame từ các kết quả khác nhau
- Xác thực nhanh tính phù hợp của nhiều frame

### ❌ KHÔNG NÊN DÙNG
- Chỉ có 1-2 frame (dùng `valid_frame_query`)
- Cần phân tích chi tiết từng frame riêng biệt
- Chưa có frame URLs cụ thể
- Cần xử lý quá 50 frame (chia nhỏ thành nhiều lần)

## 🎮 Cách Sử Dụng

### 1. LEGACY MODE - Phân Tích Đơn Giản

**Mục đích**: Phân tích một nhóm frame với một câu hỏi chung

**Input Structure**:
```json
{
    "frame_urls": ["url1", "url2", "url3", "url4"],
    "grid_dimensions": [2, 2],
    "query": "Câu hỏi phân tích"
}
```

**Ví Dụ Thực Tế**:

```json
// Tìm frame tốt nhất
{
    "frame_urls": [
        "video1_frame_100.jpg",
        "video1_frame_105.jpg", 
        "video1_frame_110.jpg",
        "video1_frame_115.jpg"
    ],
    "grid_dimensions": [2, 2],
    "query": "Frame nào cho thấy người đàn ông mặc áo đỏ đang cầm microphone và nói chuyện rõ nhất?"
}

// Sắp xếp thứ tự thời gian
{
    "frame_urls": [
        "scene_a.jpg", "scene_b.jpg", "scene_c.jpg", 
        "scene_d.jpg", "scene_e.jpg", "scene_f.jpg"
    ],
    "grid_dimensions": [2, 3],
    "query": "Sắp xếp 6 frame này theo thứ tự thời gian hợp lý nhất dựa trên nội dung"
}

// Tìm frame chất lượng tốt
{
    "frame_urls": ["blurry1.jpg", "clear1.jpg", "dark1.jpg", "bright1.jpg"],
    "grid_dimensions": [2, 2], 
    "query": "Frame nào có chất lượng hình ảnh tốt nhất, rõ nét và đủ sáng?"
}
```

**Output Legacy Mode**:
```json
{
    "is_match": true,
    "confidence_score": 0.85,
    "reasoning": "Frame số 2 (video1_frame_105.jpg) cho thấy rõ nhất người đàn ông mặc áo đỏ đang cầm microphone...",
    "relevant_frames": ["video1_frame_105.jpg"],
    "debug_info": {...}
}
```

### 2. ENHANCED MODE - So Sánh Nâng Cao

**Mục đích**: So sánh nhiều nhóm frame với câu hỏi riêng cho từng nhóm và câu hỏi so sánh

**Input Structure**:
```json
{
    "frame_groups": [
        ["group1_url1", "group1_url2"],
        ["group2_url1", "group2_url2"]
    ],
    "group_queries": ["Query cho group 1", "Query cho group 2"],
    "comparison_query": "So sánh giữa các group",
    "layout_mode": "separate",
    "max_images_per_group": 6
}
```

**Ví Dụ Thực Tế**:

```json
// So sánh kết quả từ nhiều temporal search
{
    "frame_groups": [
        [
            "person_A_speaking_1.jpg",
            "person_A_speaking_2.jpg",
            "person_A_speaking_3.jpg"
        ],
        [
            "person_B_responding_1.jpg", 
            "person_B_responding_2.jpg",
            "person_B_responding_3.jpg"
        ],
        [
            "audience_reaction_1.jpg",
            "audience_reaction_2.jpg", 
            "audience_reaction_3.jpg"
        ]
    ],
    "group_queries": [
        "Nhóm này có frame nào cho thấy người A đang nói chuyện rõ ràng nhất?",
        "Nhóm này có frame nào cho thấy người B đang phản ứng/trả lời?", 
        "Nhóm này có frame nào cho thấy phản ứng của khán giả?"
    ],
    "comparison_query": "Xác định thứ tự thời gian: ai nói trước, ai phản ứng sau, và phản ứng của khán giả?",
    "layout_mode": "separate"
}

// So sánh chất lượng giữa nhiều nguồn video
{
    "frame_groups": [
        ["cam1_scene.jpg", "cam1_scene2.jpg"],
        ["cam2_scene.jpg", "cam2_scene2.jpg"], 
        ["cam3_scene.jpg", "cam3_scene2.jpg"]
    ],
    "comparison_query": "Camera nào có chất lượng hình ảnh tốt nhất và góc quay phù hợp nhất?",
    "layout_mode": "separate"
}
```

**Output Enhanced Mode**:
```json
{
    "overall_analysis": {
        "is_match": true,
        "confidence_score": 0.9,
        "reasoning": "Đã xác định được trình tự rõ ràng: Person A nói trước, Person B phản ứng sau..."
    },
    "group_analysis": [
        {
            "group_id": 0,
            "analysis": "Frame 2 trong nhóm này cho thấy Person A đang nói rõ nhất...",
            "best_frames": ["person_A_speaking_2.jpg"]
        },
        // ... các nhóm khác
    ],
    "comparison_result": {
        "temporal_order": [0, 1, 2],
        "reasoning": "Dựa trên ngôn ngữ cơ thể và hướng nhìn..."
    },
    "metadata": {
        "total_groups": 3,
        "layout_mode": "separate", 
        "groups_processed": 3
    }
}
```

## 🔧 Tham Số Chi Tiết

### Layout Mode
- **"separate"**: Mỗi nhóm một lưới riêng, có label
  - ✅ Ưu điểm: Dễ phân biệt nhóm, tốt cho so sánh
  - ❌ Nhược điểm: Cần nhiều không gian
  
- **"combined"**: Tất cả frame trong một lưới lớn  
  - ✅ Ưu điểm: Compact, dễ nhìn tổng thể
  - ❌ Nhược điểm: Khó phân biệt nhóm

### Grid Dimensions
- **[2, 2]**: 4 frame - Phù hợp quick comparison
- **[2, 3]**: 6 frame - Cân bằng tốt  
- **[3, 3]**: 9 frame - Chi tiết hơn
- **[2, 4]**: 8 frame - Dạng panorama

### Max Images Per Group
- **4-6**: Chuẩn cho most cases
- **8-10**: Khi cần chi tiết cao
- **>10**: Tránh vì lưới quá nhỏ

## 🎯 Workflow Chuẩn

```
1. User Query
   ↓
2. temporal_frame_search_topk 
   ↓ (có frame URLs)
3. Nhóm frame theo logic:
   - Cùng chuỗi thời gian
   - Cùng chủ đề/người
   - Cùng góc camera
   ↓
4. grid_search (Legacy hoặc Enhanced)
   ↓ (có frame tốt nhất)
5. valid_frame_query (nếu cần chi tiết)
   ↓
6. Trả kết quả cho user
```

## 📊 Performance Tips

### Tối Ưu API Calls
- **Thay vì**: 10 lần `valid_frame_query` = 10 API calls
- **Dùng**: 1 lần `grid_search` = 1 API call (tiết kiệm 90%)

### Tối Ưu Chất Lượng
- Dùng câu hỏi cụ thể thay vì mơ hồ
- Nhóm frame logic thay vì random
- Chọn layout phù hợp với mục đích

### Xử Lý Lỗi
- Frame load fails → tool sẽ skip frame đó
- Gemini no response → có fallback logic
- Too many frames → chia nhỏ thành nhiều lần

## 🚫 Lỗi Thường Gặp

### ❌ Câu hỏi mơ hồ
```json
// SAI
{"query": "Phân tích lưới này"}

// ĐÚNG  
{"query": "Frame nào cho thấy người đàn ông mặc áo xanh đang cầm điện thoại?"}
```

### ❌ Quá nhiều frame
```json
// SAI - 25 frame quá nhiều
{"frame_urls": [...25 URLs...]}

// ĐÚNG - Chia thành 2 lần
// Lần 1: 12 frame, Lần 2: 13 frame
```

### ❌ Không đồng bộ group_queries
```json
// SAI - 3 nhóm nhưng chỉ 2 queries
{
    "frame_groups": [group1, group2, group3],
    "group_queries": ["query1", "query2"]
}

// ĐÚNG - Số lượng phải bằng nhau
{
    "frame_groups": [group1, group2, group3], 
    "group_queries": ["query1", "query2", "query3"]
}
```

## 💡 Best Practices

1. **Luôn bắt đầu với temporal_frame_search_topk** để có frame candidates
2. **Nhóm frame theo logic** (thời gian, chủ đề, người, camera...)
3. **Dùng câu hỏi cụ thể** thay vì general
4. **Chọn layout phù hợp**: separate cho comparison, combined cho overview
5. **Giới hạn frame hợp lý**: 4-16 frame cho legacy, 6-30 frame cho enhanced
6. **Fallback plan**: Nếu grid_search fail, dùng valid_frame_query cho frame quan trọng nhất
