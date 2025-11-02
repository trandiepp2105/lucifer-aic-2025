import os
from typing import List, Tuple
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Meilisearch Configuration
    meilisearch_host: str = Field(default="127.0.0.1", env="MEILISEARCH_HOST")
    meilisearch_port: str = Field(default="7700", env="MEILISEARCH_PORT")
    meilisearch_api_key: str = Field(default="meilisearch-api-key", env="MEILISEARCH_API_KEY")
    meilisearch_limit_search: int = Field(default=500, env="MEILISEARCH_LIMIT_SEARCH")
    
    # Dataset Paths
    ocr_datasets: str = Field(default="", env="OCR_DATASETS")
    subtitle_datasets: str = Field(default="", env="SUBTITLE_DATASETS")
    
    # Device Configuration
    device_0: str = Field(default="cuda:0", env="DEVICE_0")
    device_1: str = Field(default="cuda:0", env="DEVICE_1")
    use_gpu: bool = Field(default=True, env="USE_GPU")
    
    # Model 1 Configuration (CLIP)
    model_1_name: str = Field(default="ViT-H-14-378-quickgelu", env="MODEL_1_NAME")
    model_1_weight: float = Field(default=0.55, env="MODEL_1_WEIGHT")
    model_1_pretrained: str = Field(default="dfn5b", env="MODEL_1_PRETRAINED")
    model_1_embedding_path: str = Field(default="", env="MODEL_1_EMBEDDING_PATH")
    model_1_index_type: str = Field(default="Flat", env="MODEL_1_INDEX_TYPE")
    model_1_input_index_path: str = Field(default="", env="MODEL_1_INPUT_INDEX_PATH")
    model_1_output_index_path: str = Field(default="/app/outputs/clip-index", env="MODEL_1_OUTPUT_INDEX_PATH")
    
    # Model 2 Configuration (SigLIP)
    model_2_name: str = Field(default="ViT-gopt-16-SigLIP2-384", env="MODEL_2_NAME")
    model_2_weight: float = Field(default=0.45, env="MODEL_2_WEIGHT")
    model_2_pretrained: str = Field(default="webli", env="MODEL_2_PRETRAINED")
    model_2_embedding_path: str = Field(default="", env="MODEL_2_EMBEDDING_PATH")
    model_2_index_type: str = Field(default="Flat", env="MODEL_2_INDEX_TYPE")
    model_2_input_index_path: str = Field(default="", env="MODEL_2_INPUT_INDEX_PATH")
    model_2_output_index_path: str = Field(default="/app/outputs/siglip-index", env="MODEL_2_OUTPUT_INDEX_PATH")
    
    # FAISS Configuration
    faiss_use_gpu: bool = Field(default=True, env="FAISS_USE_GPU")
    faiss_nprobe: int = Field(default=64, env="FAISS_NPROBE")
    faiss_nlist: int = Field(default=1024, env="FAISS_NLIST")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_workers: int = Field(default=1, env="API_WORKERS")
    
    # Search Default Parameters
    default_top_k: int = Field(default=10, env="DEFAULT_TOP_K")
    default_temporal_time: int = Field(default=30, env="DEFAULT_TEMPORAL_TIME")
    default_initial_search_k: int = Field(default=2048, env="DEFAULT_INITIAL_SEARCH_K")
    
    # Fusion Weights
    weight_text: float = Field(default=0.3, env="WEIGHT_TEXT")
    weight_ocr: float = Field(default=0.3, env="WEIGHT_OCR")
    weight_subtitle: float = Field(default=0.3, env="WEIGHT_SUBTITLE")
    weight_image: float = Field(default=0.1, env="WEIGHT_IMAGE")
    
    # segment path
    segment_path: str = Field(default="/app/segments", env="SEGMENT_PATH")
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def parse_datasets(self, datasets_str: str) -> List[Tuple[str, str]]:
        """Parse dataset string format: path1:index1,path2:index2"""
        if not datasets_str:
            return []
        result = []
        for item in datasets_str.split(','):
            item = item.strip()
            if ':' in item:
                path, index_name = item.split(':', 1)
                result.append((path.strip(), index_name.strip()))
        return result
    
    def get_ocr_datasets(self) -> List[Tuple[str, str]]:
        """Get parsed OCR datasets"""
        return self.parse_datasets(self.ocr_datasets)
    
    def get_subtitle_datasets(self) -> List[Tuple[str, str]]:
        """Get parsed subtitle datasets"""
        return self.parse_datasets(self.subtitle_datasets)
    
    def get_fusion_weights(self) -> dict:
        """Get fusion weights as dictionary"""
        return {
            'text': self.weight_text,
            'ocr': self.weight_ocr,
            'subtitle': self.weight_subtitle,
            'image': self.weight_image
        }


# Global settings instance
settings = Settings()
