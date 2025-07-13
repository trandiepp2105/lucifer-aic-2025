# 🚀 AIC Query Management API

## 📋 Tổng quan

Hệ thống API quản lý Query và Answer được xây dựng bằng Django REST Framework với APIView pattern và tích hợp Swagger documentation.

## 🏗 Kiến trúc hệ thống

```
backend/
├── core/                 # Django project settings
│   ├── settings.py      # Configuration với Swagger
│   ├── urls.py          # Main URLs với Swagger endpoints
│   └── ...
├── query/               # Main application
│   ├── models.py        # Query & Answer models
│   ├── views.py         # APIView-based endpoints
│   ├── serializers.py   # DRF serializers với validation
│   ├── urls.py          # API routing
│   └── api_examples.py  # API usage examples
├── requirements.txt     # Dependencies với drf-yasg
├── SWAGGER_GUIDE.md    # Hướng dẫn Swagger
└── test_api.sh         # API testing script
```

## 🔧 Cài đặt

### 1. Cài đặt dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Database migration

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Khởi động server

```bash
python manage.py runserver
```

### 4. Truy cập API Documentation

- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/
- **API Docs**: http://localhost:8000/docs/

## 📡 API Endpoints

### Query Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/queries/` | Danh sách queries với filtering & pagination |
| POST | `/api/queries/` | Tạo query mới (hỗ trợ upload image) |
| GET | `/api/queries/{id}/` | Chi tiết query |
| PUT | `/api/queries/{id}/` | Cập nhật đầy đủ query |
| PATCH | `/api/queries/{id}/` | Cập nhật một phần query |
| DELETE | `/api/queries/{id}/` | Xóa query |
| DELETE | `/api/queries/bulk-delete/` | Xóa hàng loạt queries |
| GET | `/api/queries/{id}/answers/` | Lấy answers của query |

### Answer Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/answers/` | Danh sách answers với filtering & pagination |
| POST | `/api/answers/` | Tạo answer mới |
| GET | `/api/answers/{id}/` | Chi tiết answer |
| PUT | `/api/answers/{id}/` | Cập nhật đầy đủ answer |
| PATCH | `/api/answers/{id}/` | Cập nhật một phần answer |
| DELETE | `/api/answers/{id}/` | Xóa answer |
| DELETE | `/api/answers/bulk-delete/` | Xóa hàng loạt answers |
| GET | `/api/answers/by-query/` | Lấy answers theo query ID |

## 🔍 Filtering & Search

### Query Filtering

```bash
# Search trong text, OCR, speech
GET /api/queries/?search=artificial+intelligence

# Filter theo ngày
GET /api/queries/?start_date=2025-01-01&end_date=2025-12-31

# Pagination
GET /api/queries/?page=1&page_size=10

# Kết hợp filters
GET /api/queries/?search=AI&page=1&page_size=5&start_date=2025-06-01
```

### Answer Filtering

```bash
# Filter theo query ID
GET /api/answers/?query_id=1

# Search trong video field
GET /api/answers/?video_search=mp4

# Search trong key field
GET /api/answers/?key_search=ai_basics

# Lấy answers theo query ID (endpoint riêng)
GET /api/answers/by-query/?query_id=1
```

## 📝 Request/Response Examples

### 1. Tạo Query mới

```bash
curl -X POST http://localhost:8000/api/queries/ \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is artificial intelligence?",
    "ocr": "AI text from image",
    "speech": "AI speech transcription",
    "background_sound": "classroom environment"
  }'
```

**Response:**
```json
{
  "message": "Query created successfully",
  "data": {
    "id": 1,
    "text": "What is artificial intelligence?",
    "ocr": "AI text from image",
    "speech": "AI speech transcription",
    "image": null,
    "image_url": null,
    "time": "2025-06-18T10:00:00Z",
    "background_sound": "classroom environment",
    "created_at": "2025-06-18T10:00:00Z",
    "updated_at": "2025-06-18T10:00:00Z",
    "answers_count": 0
  }
}
```

### 2. Upload Image với Query

```bash
curl -X POST http://localhost:8000/api/queries/ \
  -H "Content-Type: multipart/form-data" \
  -F "text=Query with image" \
  -F "image=@/path/to/image.jpg"
```

### 3. Tạo Answer

```bash
curl -X POST http://localhost:8000/api/answers/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": 1,
    "video": "https://example.com/ai-video.mp4",
    "key": "ai_explanation_basic"
  }'
```

### 4. Bulk Delete

```bash
curl -X DELETE http://localhost:8000/api/queries/bulk-delete/ \
  -H "Content-Type: application/json" \
  -d '{
    "ids": [1, 2, 3]
  }'
```

## 🧪 Testing

### 1. Sử dụng Test Script

```bash
# Chạy toàn bộ test suite
./test_api.sh

# Hoặc test từng phần
chmod +x test_api.sh
./test_api.sh
```

### 2. Sử dụng Swagger UI

1. Truy cập http://localhost:8000/swagger/
2. Click "Try it out" trên endpoint muốn test
3. Nhập parameters và request body
4. Click "Execute"
5. Xem response và status code

### 3. Manual Testing với CURL

Xem file `test_api.sh` để có ví dụ chi tiết về tất cả endpoints.

## 📊 Response Format

### Success Response
```json
{
  "message": "Operation successful",
  "data": {...},
  "total": 10,
  "page": 1,
  "pages": 2
}
```

### Error Response
```json
{
  "message": "Error occurred",
  "errors": {
    "field_name": ["Error detail message"]
  }
}
```

## 🔒 Validation Rules

### Query Validation
- Ít nhất một trong `text`, `ocr`, `speech`, hoặc `image` phải có giá trị
- Image file phải < 10MB
- Image file phải là định dạng image/*

### Answer Validation
- `query` phải tồn tại trong database
- Ít nhất `video` hoặc `key` phải có giá trị

## 🎨 Swagger Features

### ✅ Đã tích hợp:
- **Interactive API Explorer**: Test API trực tiếp
- **Request/Response Schema**: Documentation đầy đủ
- **Authentication Support**: Có thể thêm auth headers
- **File Upload Support**: Test upload image
- **Filtering Parameters**: Document tất cả query parameters
- **Error Response Examples**: Ví dụ error handling

### 🔗 Swagger URLs:
- **Main UI**: http://localhost:8000/swagger/
- **Alternative**: http://localhost:8000/docs/
- **ReDoc**: http://localhost:8000/redoc/
- **JSON Schema**: http://localhost:8000/swagger.json/

## 🛠 Development Tools

### 1. API Examples
File `query/api_examples.py` chứa:
- Detailed request/response examples
- CURL commands
- Error handling examples

### 2. Test Script
File `test_api.sh` để:
- Test tất cả endpoints
- Validate responses
- Error handling testing

### 3. Swagger Documentation
File `SWAGGER_GUIDE.md` để:
- Hướng dẫn sử dụng Swagger
- Configuration notes
- Production considerations

## 🚀 Production Notes

### Security Considerations:
1. **Disable Swagger** trong production:
   ```python
   # settings.py for production
   INSTALLED_APPS = [
       # Remove 'drf_yasg',
   ]
   ```

2. **Add Authentication**:
   ```python
   # urls.py
   schema_view = get_schema_view(
       permission_classes=(permissions.IsAuthenticated,),
   )
   ```

3. **File Upload Security**:
   - Validate file types strictly
   - Scan uploaded files for malware
   - Limit file sizes appropriately

### Performance Optimization:
1. **Database Indexing**: Add indexes for filtering fields
2. **Pagination**: Always use pagination for list endpoints
3. **Query Optimization**: Use select_related for foreign keys

## 📚 Technology Stack

- **Backend**: Django 5.2.3
- **API Framework**: Django REST Framework 3.15.2
- **Documentation**: drf-yasg 1.21.7
- **Database**: MySQL (configurable)
- **File Storage**: Django file handling
- **CORS**: django-cors-headers 4.6.0

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new features
4. Update Swagger documentation
5. Submit pull request

## 📞 Support

- **API Documentation**: http://localhost:8000/swagger/
- **Test Script**: `./test_api.sh`
- **Examples**: `query/api_examples.py`

---

🎉 **Happy Coding with APIView + Swagger!** 🎉
