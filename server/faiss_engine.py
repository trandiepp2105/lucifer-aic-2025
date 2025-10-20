import os
import faiss
from pathlib import Path
import numpy as np
import pickle
from typing import List, Dict, Tuple, Optional, Any
from tqdm.auto import tqdm
import torch
from collections import defaultdict
import concurrent.futures

from reranker import Reranker


class FAISSSearchEngine:
    """
    FAISS Search Engine quản lý nhiều chỉ mục và phân chia chúng lên các GPU khác nhau.
    """
    def __init__(self, list_faiss_configs: List[Dict[str, Any]], reranker: Reranker = None):
        self.configs = {cfg['model_name']: cfg for cfg in list_faiss_configs}
        self.embedders: Dict[str, Any] = {cfg['model_name']: cfg['embedder'] for cfg in list_faiss_configs}
        self.indexes: Dict[str, faiss.Index] = {}
        # Quản lý tài nguyên cho từng GPU riêng biệt
        self.gpu_resources_map: Dict[int, faiss.StandardGpuResources] = {}
        
        self.id_to_path_maps: Dict[str, Dict[int, str]] = {}
        self.path_to_id_maps: Dict[str, Dict[str, int]] = {}
        self.total_vectors: Dict[str, int] = {}
        self.embedding_dims: Dict[str, int] = {}
        self.reranker = reranker if reranker else Reranker()

    def _get_gpu_resource(self, gpu_id: int) -> Optional[faiss.StandardGpuResources]:
        """Khởi tạo và trả về resource cho một GPU ID cụ thể."""
        if gpu_id not in self.gpu_resources_map:
            try:
                print(f"🚀 Initializing GPU resources for device cuda:{gpu_id}")
                self.gpu_resources_map[gpu_id] = faiss.StandardGpuResources()
            except Exception as e:
                print(f"⚠️ Failed to initialize resources for GPU {gpu_id}: {e}")
                self.gpu_resources_map[gpu_id] = None
        return self.gpu_resources_map[gpu_id]

    def _build_single_index(self, model_name: str):
        print(f"\n--- Building index for model: '{model_name}' ---")
        config = self.configs[model_name]
        embedding_file_path = Path(config['embedding_path'])

        if not embedding_file_path.is_file() or embedding_file_path.suffix != '.pkl':
            print(f"❌ Embedding path for '{model_name}' is not a valid pickle file: {embedding_file_path}")
            return

        with open(embedding_file_path, 'rb') as f:
            data = pickle.load(f)
        
        paths = data['paths']
        raw_embs = data['embeddings']
        
        if isinstance(raw_embs, list):
            try:
                embeddings_array = np.vstack([np.asarray(v, dtype=np.float32) for v in raw_embs])
            except ValueError as e:
                print(f"❌ Embeddings có chiều không đồng nhất: {e}")
                return
        else:
            embeddings_array = np.asarray(raw_embs, dtype=np.float32)
            if embeddings_array.ndim == 1:
                embeddings_array = embeddings_array.reshape(1, -1)
        
        if embeddings_array.ndim != 2:
            print(f"❌ Embeddings phải là mảng 2D (n, d), hiện là {embeddings_array.shape}")
            return
        embeddings_array = np.ascontiguousarray(embeddings_array, dtype=np.float32)
        
        num_vectors = embeddings_array.shape[0]
        d = embeddings_array.shape[1]
        if len(paths) != num_vectors:
            print(f"❌ Data mismatch: len(paths)={len(paths)} != num_vectors={num_vectors}")
            return
        if 'length' in data and data['length'] != num_vectors:
            print(f"⚠️ length trong pickle={data['length']} != thực tế={num_vectors}; dùng thực tế.")
        
        self.embedding_dims[model_name] = d
        self.total_vectors[model_name] = num_vectors
        self.id_to_path_maps[model_name] = {i: p for i, p in enumerate(paths)}
        self.path_to_id_maps[model_name] = {p: i for i, p in enumerate(paths)}
        
        index_type = config.get("index_type", "Flat")
        if index_type == "Flat":
            cpu_index = faiss.IndexFlatIP(d)
        elif index_type == "IVF":
            nlist = config.get("nlist", 1024)
            quantizer = faiss.IndexFlatIP(d)
            cpu_index = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_INNER_PRODUCT)
        else:
            raise ValueError(f"Unsupported index type '{index_type}' for model '{model_name}'")

        if index_type == "IVF":
            print(f"🔧 Training IVF index for '{model_name}'...")
            cpu_index.train(embeddings_array)

        print(f"📊 Adding {self.total_vectors[model_name]} embeddings to '{model_name}' index...")
        cpu_index.add(embeddings_array)
        
        embedder_device = self.embedders[model_name].device
        if config.get('use_gpu', False) and embedder_device.type == 'cuda':
            gpu_id = embedder_device.index
            res = self._get_gpu_resource(gpu_id)
            if res:
                try:
                    self.indexes[model_name] = faiss.index_cpu_to_gpu(res, gpu_id, cpu_index)
                    print(f"✅ Index for '{model_name}' is on GPU {gpu_id}.")
                except Exception as e:
                    print(f"⚠️ GPU transfer failed for '{model_name}', using CPU. Error: {e}")
                    self.indexes[model_name] = cpu_index
            else:
                self.indexes[model_name] = cpu_index
        else:
            self.indexes[model_name] = cpu_index
            print(f"✅ Index for '{model_name}' is on CPU.")
            
        if index_type == "IVF":
            self.indexes[model_name].nprobe = config.get("nprobe", 64)

    def build_all_indexes(self):
        for model_name in self.configs.keys():
            self._build_single_index(model_name)

    def save_all_indexes(self):
        for model_name, index in self.indexes.items():
            config = self.configs[model_name]
            output_path_str = config.get("output_index_path")
            if not output_path_str:
                print(f"⚠️ Skipping save for '{model_name}': 'output_index_path' not provided.")
                continue
            save_path = Path(output_path_str)
            save_path.mkdir(parents=True, exist_ok=True)
            print(f"--- Saving index for model: '{model_name}' to {save_path} ---")
            try:
                cpu_index = faiss.index_gpu_to_cpu(index) if 'gpu' in str(type(index)).lower() else index
                faiss.write_index(cpu_index, str(save_path / "faiss_index.bin"))
                metadata = {
                    'id_to_path': self.id_to_path_maps[model_name],
                    'path_to_id': self.path_to_id_maps[model_name],
                    'embedding_dim': self.embedding_dims[model_name],
                    'total_vectors': self.total_vectors[model_name]
                }
                with open(save_path / "metadata.pkl", 'wb') as f:
                    pickle.dump(metadata, f)
                print(f"✅ Saved '{model_name}' successfully.")
            except Exception as e:
                print(f"❌ Error saving index for '{model_name}': {e}")

    def load_all_indexes(self):
        for model_name, config in self.configs.items():
            load_path_str = config.get("input_index_path")
            if not load_path_str:
                print(f"⚠️ Skipping load for '{model_name}': 'input_index_path' not provided.")
                continue
            load_path = Path(load_path_str)
            print(f"\n--- Loading index for model: '{model_name}' from {load_path} ---")
            index_file, metadata_file = load_path / "faiss_index.bin", load_path / "metadata.pkl"
            if not index_file.exists() or not metadata_file.exists():
                print(f"⚠️ Skipping '{model_name}': missing index or metadata file in {load_path}.")
                continue
            try:
                cpu_index = faiss.read_index(str(index_file))
                with open(metadata_file, 'rb') as f: 
                    metadata = pickle.load(f)
                self.id_to_path_maps[model_name] = metadata['id_to_path']
                self.path_to_id_maps[model_name] = metadata['path_to_id']
                self.embedding_dims[model_name] = metadata['embedding_dim']
                self.total_vectors[model_name] = metadata['total_vectors']
                
                current_config = self.configs[model_name]
                embedder_device = self.embedders[model_name].device
                if current_config.get('use_gpu', False) and embedder_device.type == 'cuda':
                    gpu_id = embedder_device.index
                    res = self._get_gpu_resource(gpu_id)
                    if res:
                        self.indexes[model_name] = faiss.index_cpu_to_gpu(res, gpu_id, cpu_index)
                        print(f"✅ Index for '{model_name}' loaded on GPU {gpu_id}.")
                    else:
                        self.indexes[model_name] = cpu_index
                else:
                    self.indexes[model_name] = cpu_index
                    print(f"✅ Index for '{model_name}' loaded on CPU.")
                if current_config.get("index_type") == "IVF":
                    self.indexes[model_name].nprobe = current_config.get("nprobe", 64)
            except Exception as e:
                print(f"❌ Error loading index for '{model_name}': {e}")

    def _search_single_model(self, model_name: str, queries: List[Any], k: int) -> List[List[Tuple[str, float]]]:
        index = self.indexes.get(model_name)
        embedder = self.embedders.get(model_name)
        id_to_path = self.id_to_path_maps.get(model_name)
        if not all([index, embedder, id_to_path]):
            print(f"⚠️ Cannot search model '{model_name}': component is missing.")
            return [[] for _ in queries]
        query_array = embedder.encode_batch(queries)
        scores_batch, indices_batch = index.search(query_array, k)
        batch_results = []
        for scores, indices in zip(scores_batch, indices_batch):
            single_query_results = []
            for score, idx in zip(scores, indices):
                if idx != -1 and idx in id_to_path:
                    single_query_results.append((id_to_path[idx], float(score)))
            batch_results.append(single_query_results)
        return batch_results

    def search(
        self,
        queries: List[Any],
        models_to_search: List[Dict[str, Any]],
        k: int = 100
    ) -> List[List[Tuple[str, float]]]:

        raw_results_by_model: Dict[str, List[List[Tuple[str, float]]]] = {}
        model_configs = {m['model_name']: m for m in models_to_search}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_model = {
                executor.submit(self._search_single_model, model_name, queries, k): model_name
                for model_name in model_configs.keys() if model_name in self.indexes
            }
            for future in concurrent.futures.as_completed(future_to_model):
                model_name = future_to_model[future]
                try:
                    raw_results_by_model[model_name] = future.result()
                except Exception as e:
                    print(f"❌ Search failed for model '{model_name}': {e}")
                    raw_results_by_model[model_name] = [[] for _ in queries]

        list_batch_result = [batch_result for model_name, batch_result in raw_results_by_model.items()]
        final_reranked_results = self.reranker(list_batch_result=list_batch_result, top_k=k)
        return final_reranked_results
    
    def cleanup_gpu_memory(self):
        if self.gpu_resources_map:
            del self.indexes
            del self.gpu_resources_map
            self.indexes = {}
            self.gpu_resources_map = {}
            if torch.cuda.is_available(): 
                torch.cuda.empty_cache()
            print("🧹 GPU memory and indexes cleaned up.")
