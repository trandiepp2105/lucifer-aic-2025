# Lucifer AIC 2025 - Multi-modal Search Engine

Hệ thống tìm kiếm đa phương thức (multi-modal) với CLIP, FAISS, và Meilisearch cho AIC 2025.

## 📋 Tính năng

- **Multi-modal Search**: Hỗ trợ tìm kiếm bằng text, image, OCR, và subtitle
- **Temporal Search**: Tìm kiếm chuỗi video theo thời gian
- **Multi-model Fusion**: Kết hợp nhiều mô hình CLIP với reranking thông minh
- **GPU Acceleration**: Tối ưu hóa cho multi-GPU
- **Fast OCR Search**: Sử dụng Meilisearch cho tìm kiếm OCR nhanh

## 🏗️ Cấu trúc dự án

```
server/
├── main.py                    # FastAPI application
├── config.py                  # Configuration management
├── embedder.py                # CLIP embedder
├── meilisearch_service.py     # Meilisearch OCR/subtitle search
├── faiss_engine.py            # FAISS vector search engine
├── reranker.py                # Multi-model reranking
├── search_engine.py           # Main search orchestrator
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variables example
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose configuration
└── README.md                  # This file
```

## 🚀 Cài đặt

### Yêu cầu hệ thống

- Python 3.10+
- CUDA 12.1+ (nếu sử dụng GPU)
- Docker & Docker Compose (tùy chọn)
- RAM: 32GB+ khuyến nghị
- GPU: 2x GPU với 16GB+ VRAM khuyến nghị

### Cài đặt thủ công

1. **Clone repository**:
```bash
cd /media/trandiep/trandiepssd/workspace/aic-2025/lucifer-aic-2025/server
```

2. **Tạo môi trường ảo**:
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc: venv\Scripts\activate  # Windows
```

3. **Cài đặt dependencies**:
```bash
pip install -r requirements.txt
```

4. **Cấu hình môi trường**:
```bash
cp .env.example .env
# Chỉnh sửa .env với các đường dẫn và cấu hình của bạn
nano .env
```

5. **Tải Meilisearch** (nếu không dùng Docker):
```bash
wget https://github.com/meilisearch/meilisearch/releases/latest/download/meilisearch-linux-amd64 -O meilisearch
chmod +x meilisearch
```

6. **Chạy Meilisearch**:
```bash
./meilisearch --http-addr 127.0.0.1:7700 --master-key=meilisearch-api-key &
```

7. **Chạy ứng dụng**:
```bash
python main.py
```

### Cài đặt với Docker

1. **Cấu hình môi trường**:
```bash
cp .env.example .env
# Chỉnh sửa .env
nano .env
```

2. **Chuẩn bị dữ liệu**:
```bash
# Tạo các thư mục cần thiết
mkdir -p data/ocr data/subtitle data/embeddings indexes outputs

# Copy dữ liệu của bạn vào:
# - data/ocr: OCR JSON files
# - data/subtitle: Subtitle JSON files
# - data/embeddings/clip: CLIP embeddings (embedding_info.pkl)
# - data/embeddings/siglip: SigLIP embeddings (embedding_info.pkl)
# - indexes/clip-index: Pre-built CLIP FAISS index
# - indexes/siglip-index: Pre-built SigLIP FAISS index
```

3. **Build và chạy**:
```bash
# Build image
docker-compose build

# Chạy services
docker-compose up -d

# Xem logs
docker-compose logs -f api
```

4. **Kiểm tra**:
```bash
curl http://localhost:8000/health
```

## 📝 Cấu hình

### File .env

Các biến môi trường quan trọng:

```bash
# Meilisearch
MEILISEARCH_HOST=127.0.0.1
MEILISEARCH_PORT=7700
MEILISEARCH_API_KEY=your-api-key

# Datasets (format: path:index_name,path2:index_name2)
OCR_DATASETS=/path/to/ocr:parseq_ocr_index
SUBTITLE_DATASETS=/path/to/subtitle:frame_transcript_index

# Device
DEVICE_0=cuda:0
DEVICE_1=cuda:1
USE_GPU=true

# Model configurations
MODEL_1_EMBEDDING_PATH=/path/to/clip/embedding_info.pkl
MODEL_1_INPUT_INDEX_PATH=/path/to/clip/index

MODEL_2_EMBEDDING_PATH=/path/to/siglip/embedding_info.pkl
MODEL_2_INPUT_INDEX_PATH=/path/to/siglip/index

# Fusion weights
WEIGHT_TEXT=0.3
WEIGHT_OCR=0.3
WEIGHT_SUBTITLE=0.3
WEIGHT_IMAGE=0.1
```

## 🔌 API Usage

### Health Check

```bash
curl http://localhost:8000/health
```

### Search Endpoint

**Endpoint**: `POST /search`

**Parameters**:
- `k` (int): Số lượng kết quả trả về (default: 10)
- `temporal_time` (int): Khoảng thời gian tối đa giữa 2 frames (seconds, default: 30)
- `queries_structure` (JSON string): Cấu trúc truy vấn
- `image_files` (files): Danh sách file ảnh (nếu có)
- `weights` (JSON string, optional): Trọng số fusion
- `vector_models_config` (JSON string, optional): Cấu hình models

**Example 1: Text search**:
```bash
curl -X POST "http://localhost:8000/search" \
  -F 'k=5' \
  -F 'temporal_time=30' \
  -F 'queries_structure=[{"text": "blue car"}]'
```

**Example 2: Multi-stage temporal search**:
```bash
curl -X POST "http://localhost:8000/search" \
  -F 'k=10' \
  -F 'temporal_time=30' \
  -F 'queries_structure=[{"text": "blue car"}, {"ocr": "spirit"}, {"subtitle": "hello"}]'
```

**Example 3: With image**:
```bash
curl -X POST "http://localhost:8000/search" \
  -F 'k=5' \
  -F 'queries_structure=[{"image_ref": "query.jpg"}]' \
  -F 'image_files=@/path/to/query.jpg'
```

**Example 4: Complex search with custom weights**:
```bash
curl -X POST "http://localhost:8000/search" \
  -F 'k=10' \
  -F 'temporal_time=30' \
  -F 'queries_structure=[{"text": "car", "ocr": "toyota"}]' \
  -F 'weights={"text": 0.4, "ocr": 0.4, "subtitle": 0.1, "image": 0.1}' \
  -F 'vector_models_config=[{"model_name": "ViT-H-14-378-quickgelu", "weight": 1.0}]'
```

## 🧪 Testing

### Test với Python:

```python
import requests

url = "http://localhost:8000/search"

# Simple text search
data = {
    'k': 5,
    'queries_structure': '[{"text": "blue car"}]'
}

response = requests.post(url, data=data)
print(response.json())
```

### Test với curl:

```bash
# Text + OCR search
curl -X POST "http://localhost:8000/search" \
  -F 'k=10' \
  -F 'queries_structure=[{"text": "car"}, {"ocr": "toyota"}]'
```

## 🐛 Troubleshooting

### GPU không được nhận diện:
```bash
# Kiểm tra CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Kiểm tra GPU trong Docker
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Meilisearch không kết nối được:
```bash
# Kiểm tra Meilisearch đang chạy
curl http://localhost:7700/health

# Xem logs
docker-compose logs meilisearch
```

### Out of Memory:
- Giảm `DEFAULT_INITIAL_SEARCH_K` trong .env
- Giảm `MEILISEARCH_LIMIT_SEARCH`
- Sử dụng ít models hơn
- Tăng swap memory

## 📊 Performance Tips

1. **Pre-build FAISS indexes**: Build indexes trước và mount vào container
2. **Use GPU**: Bật `USE_GPU=true` và `FAISS_USE_GPU=true`
3. **Optimize batch size**: Điều chỉnh `DEFAULT_INITIAL_SEARCH_K`
4. **Multi-GPU**: Phân bổ models lên các GPU khác nhau
5. **Index type**: Sử dụng IVF thay vì Flat cho datasets lớn

## 📄 License

[Your License Here]

## 👥 Contributors

- Tran Diep

## 🙏 Acknowledgments

- OpenAI CLIP
- Meilisearch
- FAISS
- FastAPI
