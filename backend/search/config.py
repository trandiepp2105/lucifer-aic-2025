"""
Configuration settings for OCR Search Service with Meilisearch
"""

import os
import glob

# Meilisearch settings
MEILISEARCH_HOST = os.getenv('MEILISEARCH_HOST', 'localhost')
MEILISEARCH_PORT = int(os.getenv('MEILISEARCH_PORT', '7700'))
MEILISEARCH_API_KEY = os.getenv('MEILISEARCH_API_KEY', 'masterKey')

def get_dynamic_datasets():
    """
    Dynamically discover OCR datasets from CONTAINER_STORAGE_DIR environment variable.
    
    Directory structure expected:
    CONTAINER_STORAGE_DIR/
    └── ocr-data/
        ├── viet-ocr-json-data/     → dataset_path + index_name: "viet_ocr_json_data"
        ├── parseq-ocr-json-data/   → dataset_path + index_name: "parseq_ocr_json_data" 
        └── other-dataset/          → dataset_path + index_name: "other_dataset"
    
    Returns:
        List[Tuple[str, str]]: List of (dataset_path, index_name) tuples
    """
    container_storage_dir = os.getenv('CONTAINER_STORAGE_DIR')
    
    if not container_storage_dir:
        # Fallback to hardcoded datasets if env var not set
        return [
            ('/backend/ocr-data/viet-ocr-json-data', "viet_ocr_index"),
            ('/backend/ocr-data/parseq-ocr-json-data', "parseq_ocr_index")
        ]
    
    # Build ocr-data path
    ocr_data_dir = os.path.join(container_storage_dir, 'ocr-data')
    
    if not os.path.exists(ocr_data_dir):
        print(f"Warning: OCR data directory not found: {ocr_data_dir}")
        return []
    
    datasets = []
    
    # Find all subdirectories in ocr-data
    for item in os.listdir(ocr_data_dir):
        dataset_path = os.path.join(ocr_data_dir, item)
        
        # Check if it's a directory and contains JSON files
        if os.path.isdir(dataset_path):
            json_files = glob.glob(os.path.join(dataset_path, "*.json"))
            
            if json_files:  # Only include if contains JSON files
                # Convert directory name to valid index name
                # Example: "viet-ocr-json-data" → "viet_ocr_json_data"
                index_name = item.replace('-', '_').replace(' ', '_').lower()
                
                datasets.append((dataset_path, index_name))
                print(f"Discovered dataset: {dataset_path} → index: {index_name}")
    
    # Sort for consistent ordering
    datasets.sort(key=lambda x: x[1])  # Sort by index name
    
    return datasets

# OCR datasets configuration - dynamically loaded
LIST_DATASET = get_dynamic_datasets()

# DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# MODEL_NAME = "ViT-H-14-quickgelu"
# PRETRAINED = "dfn5b"
# TOKENIZER_MODEL = "ViT-H-14-quickgelu"
# USE_MULTI_GPU = False

# # FAISS configuration
# INDEX_TYPE = "IVF"  # "Flat" or "IVF"
# NLIST = 4096       # Number of clusters for IVF index
# SEARCH_K = 10      # Default number of results