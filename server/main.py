import io
import json
import time
import traceback
from typing import List, Optional
from PIL import Image
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import torch

from config import settings
from embedder import CLIPEmbedder
from meilisearch_service import MeiliSearchService
from faiss_engine import FAISSSearchEngine
from search_engine import SearchEngine

# Initialize FastAPI app
app = FastAPI(
    title="Lucifer AIC 2025 Search API",
    description="Multi-modal temporal search engine with CLIP, FAISS, and Meilisearch",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
meilisearch_service: MeiliSearchService = None
faiss_search_engine: FAISSSearchEngine = None
search_engine: SearchEngine = None


@app.on_event("startup")
async def startup_event():
    """Initialize all search engines on startup"""
    global meilisearch_service, faiss_search_engine, search_engine
    
    print("🚀 Initializing search engines...")
    
    # 1. Initialize Meilisearch
    print("\n📚 Initializing Meilisearch...")
    meilisearch_service = MeiliSearchService.get_instance(
        host=settings.meilisearch_host,
        port=int(settings.meilisearch_port),
        api_key=settings.meilisearch_api_key,
        ocr_datasets=settings.get_ocr_datasets(),
        subscript_datasets=settings.get_subtitle_datasets(),
        limit_search=settings.meilisearch_limit_search
    )
    
    # Create indices (they will be created if not exists)
    meilisearch_service.create_indices()
    print("✅ Meilisearch initialized")
    
    # 2. Determine devices
    print("\n🔧 Configuring devices...")
    if torch.cuda.is_available():
        device_0 = torch.device(settings.device_0)
        device_1 = torch.device(settings.device_1)
        print(f"✅ Using GPUs: {device_0}, {device_1}")
    else:
        device_0 = torch.device("cpu")
        device_1 = torch.device("cpu")
        print("⚠️ No GPU available, using CPU")
    
    # 3. Initialize models and embedders
    print("\n🤖 Loading models...")
    models_config = []
    
    # Model 1
    if settings.model_1_input_index_path:
        embedder_1 = CLIPEmbedder(
            device=device_0,
            model_name=settings.model_1_name,
            pretrained=settings.model_1_pretrained,
        )
        
        faiss_config_1 = {
            "model_name": settings.model_1_name,
            "embedder": embedder_1,
            "embedding_path": settings.model_1_embedding_path,
            "index_type": settings.model_1_index_type,
            "nlist": settings.faiss_nlist,
            "nprobe": settings.faiss_nprobe,
            "input_index_path": settings.model_1_input_index_path,
            "output_index_path": settings.model_1_output_index_path,
            'use_gpu': settings.faiss_use_gpu and torch.cuda.is_available()
        }
        models_config.append(faiss_config_1)
        print(f"✅ Model 1 loaded: {settings.model_1_name}")
    
    # Model 2
    if settings.model_2_input_index_path:
        embedder_2 = CLIPEmbedder(
            device=device_1,
            model_name=settings.model_2_name,
            pretrained=settings.model_2_pretrained,
        )
        
        faiss_config_2 = {
            "model_name": settings.model_2_name,
            "embedder": embedder_2,
            "embedding_path": settings.model_2_embedding_path,
            "index_type": settings.model_2_index_type,
            "nlist": settings.faiss_nlist,
            "nprobe": settings.faiss_nprobe,
            "input_index_path": settings.model_2_input_index_path,
            "output_index_path": settings.model_2_output_index_path,
            'use_gpu': settings.faiss_use_gpu and torch.cuda.is_available()
        }
        models_config.append(faiss_config_2)
        print(f"✅ Model 2 loaded: {settings.model_2_name}")
    
    # 4. Initialize FAISS search engine
    print("\n🔍 Initializing FAISS search engine...")
    faiss_search_engine = FAISSSearchEngine(list_faiss_configs=models_config)
    faiss_search_engine.load_all_indexes()
    print("✅ FAISS search engine initialized")
    
    # 5. Initialize main search engine
    print("\n⚡ Initializing main search engine...")
    search_engine = SearchEngine(
        vector_engine=faiss_search_engine,
        ocr_engine=meilisearch_service,
        segments_dir=settings.segment_path
    )
    print("✅ All engines initialized successfully!\n")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Lucifer AIC 2025 Search API is running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "meilisearch": meilisearch_service is not None,
        "faiss_engine": faiss_search_engine is not None,
        "search_engine": search_engine is not None,
        "gpu_available": torch.cuda.is_available(),
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
    }


@app.post("/search")
async def handle_search(
    request: Request,

    k: int = Form(10, description="Số lượng chuỗi video kết quả cuối cùng cần trả về."),

    temporal_time: int = Form(10, description="Thời gian tối đa giữa hai frame"),

    queries_structure: str = Form(
        ..., 
        description='Một chuỗi JSON mô tả các stage. Ví dụ: \'[{"text": "a plane"}, {"ocr": "spirit"}]\' '
    ),

    image_files: Optional[List[UploadFile]] = Form(
        [],
        description="Một danh sách chứa tất cả các file ảnh được tham chiếu trong 'queries_structure'."
    ),

    weights: Optional[str] = Form(
        None, 
        description='(Optional) Một chuỗi JSON chứa trọng số giữa các loại truy vấn. Ví dụ: \'{"text": 0.5, "ocr": 0.3, "image": 0.2}\''
    ),
    
    vector_models_config: Optional[str] = Form(
        None,
        description='(Optional) Một chuỗi JSON cấu hình các model vector và trọng số. Ví dụ: \'[{"model_name": "clip-vit-h", "weight": 0.7}, {"model_name": "clip-vit-l", "weight": 0.3}]\' '
    )
):
    """
    Thực hiện Temporal Search với cấu hình đa mô hình và trọng số tùy chỉnh.
    """

    try:
        # --- 1. Phân tích các tham số đầu vào (dưới dạng chuỗi JSON) ---
        try:
            parsed_structure = json.loads(queries_structure)
            if not isinstance(parsed_structure, list):
                raise ValueError("queries_structure phải là một mảng JSON.")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Lỗi phân tích 'queries_structure': {e}")

        parsed_weights = None
        if weights:
            try:
                parsed_weights = json.loads(weights)
                if not isinstance(parsed_weights, dict):
                    raise ValueError("weights phải là một JSON object.")
            except (json.JSONDecodeError, ValueError) as e:
                raise HTTPException(status_code=400, detail=f"Lỗi phân tích 'weights': {e}")
        
        # --- THÊM LOGIC PHÂN TÍCH CHO vector_models_config ---
        parsed_vector_models = None
        if vector_models_config:
            try:
                parsed_vector_models = json.loads(vector_models_config)
                if not isinstance(parsed_vector_models, list):
                    raise ValueError("vector_models_config phải là một mảng JSON.")
                # (Tùy chọn) Thêm kiểm tra sâu hơn cho từng phần tử trong mảng nếu cần
            except (json.JSONDecodeError, ValueError) as e:
                 raise HTTPException(status_code=400, detail=f"Lỗi phân tích 'vector_models_config': {e}")


        # --- 2. Xây dựng lại truy vấn với dữ liệu ảnh ---
        uploaded_images = {file.filename: file for file in image_files}
        reconstructed_queries: List[Dict[str, Any]] = []

        def is_valid(value: Any) -> bool:
            return value not in [None, "", "null"]

        for i, stage_data in enumerate(parsed_structure):
            if not isinstance(stage_data, dict):
                raise HTTPException(status_code=400, detail=f"Stage {i} phải là một object.")

            current_stage = {}
            if 'text' in stage_data and is_valid(stage_data['text']):
                current_stage['text'] = stage_data['text']
            if 'ocr' in stage_data and is_valid(stage_data['ocr']):
                current_stage['ocr'] = stage_data['ocr']
            if 'subtitle' in stage_data and is_valid(stage_data['subtitle']):
                current_stage['subtitle'] = stage_data['subtitle']
            if 'image_ref' in stage_data and is_valid(stage_data['image_ref']):
                image_filename = stage_data['image_ref']
                if image_filename not in uploaded_images:
                    raise HTTPException(status_code=400, detail=f"Ảnh '{image_filename}' được tham chiếu nhưng không có trong 'image_files'.")
                
                image_file = uploaded_images[image_filename]
                image_data = await image_file.read()
                pil_image = Image.open(io.BytesIO(image_data)).convert('RGB')
                current_stage['image'] = pil_image

            if not current_stage:
                raise HTTPException(status_code=400, detail=f"Stage {i} không chứa truy vấn hợp lệ (text, ocr, hoặc image_ref).")

            reconstructed_queries.append(current_stage)
        # --- 3. Gọi hàm tìm kiếm với đầy đủ các tham số đã được phân tích ---
        results = search_engine.temporal_search(
            queries=reconstructed_queries, 
            k=k,
            time_distance=temporal_time,
            weights=parsed_weights,
            # Truyền cấu hình đa mô hình vào đây
            vector_models_config=parsed_vector_models,
            format = 'shot'
        )

        
        # --- 4. Trả kết quả ---
        return {
            "status": "success",
            "k_requested": k,
            "results_found": len(results),
            "query_details": {
                 "stages_processed": len(reconstructed_queries),
                 "fusion_weights_used": parsed_weights,
                 "vector_models_used": parsed_vector_models
            },
            "results": results,
        }

    except HTTPException as http_exc:
        # Ghi log lỗi và re-raise để FastAPI xử lý
        print(f"❌ API Error: {http_exc.status_code}, Detail: {http_exc.detail}")
        raise http_exc

    except Exception as e:
        # Ghi log lỗi hệ thống để debug
        print(f"❌ Unhandled System Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống không mong muốn: {str(e)}")