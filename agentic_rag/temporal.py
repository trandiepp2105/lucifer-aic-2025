from pathlib import Path
import numpy as np
import pickle
from typing import List, Dict, Tuple, Optional, Any
import torch
from collections import defaultdict
import json
from PIL import Image
import concurrent.futures
import time
import gc
import os

class SearchEngine:
    """
    Search Engine được tối ưu hóa cho temporal search, tận dụng tối đa batch processing 
    và re-ranking đa mô hình.
    """
    def __init__(self, vector_engine: 'FAISSSearchEngine', ocr_engine: 'MeiliSearchService'):
        """
        Khởi tạo Search Engine. Embedder giờ đây được quản lý bởi FAISSSearchEngine.
        """
        self.vector_engine = vector_engine
        self.ocr_engine = ocr_engine
        print("✅ Main SearchEngine (Optimized Multi-Model Version) initialized.")

    def _fuse_and_rerank_candidates(
        self,
        raw_text_results: List[Tuple[str, float]],
        raw_image_results: List[Tuple[str, float]],
        raw_ocr_results: List[Dict[str, Any]],
        weights: Dict[str, float]
    ) -> List[Tuple[str, float]]:
        """
        Hàm re-rank chuyên dụng.
        Kết hợp các kết quả thô, thực hiện chuẩn hóa Min-Max hai lần:
        1. Chuẩn hóa điểm từ mỗi nguồn (text, image, ocr).
        2. Chuẩn hóa điểm tổng hợp cuối cùng (fusion_score).
        """
        all_scores = defaultdict(lambda: {'text': 0.0, 'image': 0.0, 'ocr': 0.0})
        for path, score in raw_text_results: all_scores[path]['text'] = score
        for path, score in raw_image_results: all_scores[path]['image'] = score
        for ocr_hit in raw_ocr_results:
            video_name = ocr_hit.get('video_name', '')
            frame_index = ocr_hit.get('frame_index', -1)
            ocr_score = ocr_hit.get('_rankingScore', 0.0) 
            if video_name and frame_index != -1:
                path = f"{video_name}/{frame_index}.jpg"
                all_scores[path]['ocr'] = ocr_score

        if not all_scores:
            return []


        # --- BƯỚC CHUẨN HÓA 1: CHUẨN HÓA ĐIỂM THÀNH PHẦN ---
        text_scores = [s['text'] for s in all_scores.values() if s['text'] > 0]
        image_scores = [s['image'] for s in all_scores.values() if s['image'] > 0]
        ocr_scores = [s['ocr'] for s in all_scores.values() if s['ocr'] > 0]

        min_max_map = {
            'text': (min(text_scores, default=0), max(text_scores, default=0)),
            'image': (min(image_scores, default=0), max(image_scores, default=0)),
            'ocr': (min(ocr_scores, default=0), max(ocr_scores, default=0))
        }

        temp_combined_results = []
        for path, scores in all_scores.items():
            normalized_scores = {}
            for score_type in ['text', 'image', 'ocr']:
                min_val, max_val = min_max_map[score_type]
                raw_score = scores[score_type]
                score_range = max_val - min_val

                if (raw_score == 0):
                    normalized_scores[score_type] = 0.0
                    continue
                
                if score_range > 0:
                    normalized_scores[score_type] = (raw_score - min_val) / score_range
                elif raw_score > 0:
                    normalized_scores[score_type] = 1.0
                else:
                    normalized_scores[score_type] = 0.0

            fusion_score = (
                weights.get('text', 0.0) * normalized_scores['text'] +
                weights.get('image', 0.0) * normalized_scores['image'] +
                weights.get('ocr', 0.0) * normalized_scores['ocr']
            )

            if fusion_score > 0:
                temp_combined_results.append((path, fusion_score))

        if not temp_combined_results:
            return []


        # --- BƯỚC CHUẨN HÓA 2: CHUẨN HÓA ĐIỂM TỔNG HỢP (FUSION SCORE) ---
        fusion_scores = [score for _, score in temp_combined_results]
        min_fusion_score = min(fusion_scores)
        max_fusion_score = max(fusion_scores)
        fusion_score_range = max_fusion_score - min_fusion_score

        final_results = []
        for path, score in temp_combined_results:
            if fusion_score_range > 0:
                normalized_fusion_score = (score - min_fusion_score) / fusion_score_range
            else:
                normalized_fusion_score = 1.0 if score > 0 else 0.0
            final_results.append((path, normalized_fusion_score))
            
        final_results.sort(key=lambda x: x[1], reverse=True)

        return final_results

    def hybrid_search(
        self,
        text_query: Optional[str] = None,
        image_query: Optional[Image.Image] = None,
        ocr_query: Optional[str] = None,
        k: int = 100,
        weights: Dict[str, float] = None,
        vector_models_config: Optional[List[Dict[str, Any]]] = None
    ) -> List[Tuple[str, float]]:
        """
        Thực hiện tìm kiếm hybrid cho một truy vấn đơn giản (một stage).
        """
        if weights is None: 
            weights = {'text': 0.45, 'ocr': 0.35, 'image': 0.20}
        if vector_models_config is None:
            available_model_names = list(self.vector_engine.configs.keys())
            num_models = len(available_model_names)
            if num_models > 0:
                equal_weight = 1.0 / num_models
                vector_models_config = [{'model_name': model_name, 'weight': equal_weight} for model_name in available_model_names]
            else:
                vector_models_config = []

        raw_results = {'text': [], 'image': [], 'ocr': []}
        vector_queries, vector_types = [], []
        if text_query: 
            vector_queries.append(text_query)
            vector_types.append('text')
        if image_query: 
            vector_queries.append(image_query)
            vector_types.append('image')

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_vector = None
            if vector_queries:
                future_vector = executor.submit(self.vector_engine.search, vector_queries, vector_models_config, k)
            future_ocr = None
            if ocr_query:
                future_ocr = executor.submit(self.ocr_engine.search_ocr, ocr_query, k)
            if future_vector:
                batch_vector_results = future_vector.result()
                for i, q_type in enumerate(vector_types):
                    raw_results[q_type] = batch_vector_results[i]
            if future_ocr:
                raw_results['ocr'] = future_ocr.result()

        combined_results = self._fuse_and_rerank_candidates(
            raw_text_results=raw_results['text'],
            raw_image_results=raw_results['image'],
            raw_ocr_results=raw_results['ocr'],
            weights=weights
        )
        return combined_results[:k]

    def temporal_search(
        self,
        queries: Optional[List[Dict[str, Any]]] = None,
        k: int = 10, # top_k
        time_distance: int = 30, # time_distance in seconds
        initial_search_k: int = 2048, # num_of_frames
        weights: Dict[str, float] = None,
        vector_models_config: Optional[List[Dict[str, Any]]] = None,
        agent_format: bool = False
    ) -> List[List[Tuple[str, float]]]:
        """
        Thực hiện tìm kiếm tuần tự theo thời gian, áp dụng logic xử lý mới từ người dùng.
        Phần quy hoạch động đã được sửa lại để đảm bảo tính đúng đắn.
        Định dạng output là List[List[Tuple[str, float]]].
        """
        if not queries:
            return []
        
        num_stages = len(queries)
        if num_stages <= 1:
            stage_query = queries[0] if queries else {}
            results = self.hybrid_search(
                text_query=stage_query.get('text'),
                image_query=stage_query.get('image'),
                ocr_query=stage_query.get('ocr'),
                k=k,
                weights=weights,
                vector_models_config=vector_models_config
            )
            # Chuyển đổi sang định dạng output mong muốn
            return [results] if results else []
        start = time.time()
        # === BƯỚC 1 & 2: TÌM KIẾM BAN ĐẦU (Giữ nguyên để tối ưu hiệu năng) ===
        vector_queries_to_process, vector_batch_map, ocr_queries_to_process = [], [], []
        # ... (logic tập hợp và thực thi song song không đổi)
        placeholder_query = "placeholder"
        has_placeholder = False
        for stage_idx, stage_data in enumerate(queries):
            has_vector_query_in_stage = False
            if stage_data.get('text'):
                vector_queries_to_process.append(stage_data['text'])
                vector_batch_map.append({'stage_idx': stage_idx, 'type': 'text'})
                has_vector_query_in_stage = True
            if stage_data.get('image'):
                vector_queries_to_process.append(stage_data['image'])
                vector_batch_map.append({'stage_idx': stage_idx, 'type': 'image'})
                has_vector_query_in_stage = True
            if not has_vector_query_in_stage and stage_data.get('ocr'):
                if not has_placeholder:
                    vector_queries_to_process.append(placeholder_query)
                    has_placeholder = True
                vector_batch_map.append({'stage_idx': stage_idx, 'type': 'placeholder', 'query_ref': placeholder_query})
            if stage_data.get('ocr'):
                ocr_queries_to_process.append((stage_idx, stage_data['ocr']))
        print(f"process time: {time.time() - start}")
        start = time.time()
        batch_vector_results, ocr_results_by_stage = [], defaultdict(list)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_vector = executor.submit(self.vector_engine.search, vector_queries_to_process, vector_models_config, initial_search_k)
            future_ocr = {executor.submit(self.ocr_engine.search_ocr, ocr_text, 50): stage_idx for stage_idx, ocr_text in ocr_queries_to_process}
            try: batch_vector_results = future_vector.result()
            except Exception as e: print(f"Lỗi batch vector search: {e}")
            for future in concurrent.futures.as_completed(future_ocr):
                try: ocr_results_by_stage[future_ocr[future]] = future.result()
                except Exception as e: print(f"Lỗi OCR search cho stage {future_ocr[future]}: {e}")
        print(f"Search time: {time.time() - start}")
        start = time.time()
        # === BƯỚC 3: TẠO CẤU TRÚC DỮ LIỆU `full_resuit` (Theo logic mới) ===
        raw_results_by_stage = defaultdict(lambda: {'text': [], 'image': [], 'ocr': []})
        for i, mapping in enumerate(vector_batch_map):
            if mapping['type'] != 'placeholder':
                stage_idx, q_type = mapping['stage_idx'], mapping['type']
                raw_results_by_stage[stage_idx][q_type] = batch_vector_results[i]
        for stage_idx, results in ocr_results_by_stage.items():
            raw_results_by_stage[stage_idx]['ocr'] = results
        
        full_resuit_map = defaultdict(lambda: {'scores': [0.0] * num_stages, 'info': None, 'path': ''})
        for stage_idx in range(num_stages):
            stage_data = raw_results_by_stage[stage_idx]
            reranked_results = self._fuse_and_rerank_candidates(
                stage_data['text'], stage_data['image'], stage_data['ocr'], {'text': 0.4, 'ocr': 0.4, 'image': 0.2}
            )
            for path, score in reranked_results:
                full_resuit_map[path]['scores'][stage_idx] = score
                if not full_resuit_map[path]['info']:
                    try:
                        video_name = os.path.dirname(path)
                        frame_id = int(os.path.splitext(os.path.basename(path))[0])
                        second = frame_id / 30.0 # Giả định 30 FPS
                        full_resuit_map[path]['info'] = (video_name, frame_id, second)
                        full_resuit_map[path]['path'] = path
                    except (ValueError, IndexError):
                        continue
        
        # Lọc bỏ các mục không có thông tin hợp lệ
        valid_results = [v for k, v in full_resuit_map.items() if v['info']]
        full_resuit = [(item['info'], tuple(item['scores']), item['path']) for item in valid_results]
        print(f"Fomart time: {time.time() - start}")
        start = time.time()
        # === BƯỚC 4: SẮP XẾP VÀ NHÓM THEO THỜI GIAN (Theo logic mới) ===
        if not full_resuit: return []
        full_resuit.sort(key=lambda x: (x[0][0], x[0][1])) # Sắp xếp theo video, rồi theo frame

        rerank_results = []
        for item in full_resuit:
            item_info = item[0]
            video, _, second = item_info
            if not rerank_results or video != rerank_results[-1][-1][0][0] or second - rerank_results[-1][-1][0][2] > time_distance:
                rerank_results.append([])
            rerank_results[-1].append(item)
        print(f"Chia time: {time.time() - start}")
        start = time.time()
        # === BƯỚC 5: QUY HOẠCH ĐỘNG ĐỂ TÌM CHUỖI TỐT NHẤT (Logic được sửa lại cho đúng) ===
        final_chains = []
        for group in rerank_results:
            if not group: continue
            
            dp = [[0.0] * num_stages for _ in range(len(group))]
            path_trace = [[-1] * num_stages for _ in range(len(group))]

            for i in range(len(group)):
                dp[i][0] = group[i][1][0]
                for j in range(num_stages):
                    # max_prev_score = 0.0
                    # best_prev_idx = -1
                    # for p in range(i):
                    #     if dp[p][j-1] > max_prev_score:
                    #         max_prev_score = dp[p][j-1]
                    #         best_prev_idx = p
                    # if max_prev_score > 0: # Chỉ tạo chuỗi nếu có stage trước đó hợp lệ
                    #     dp[i][j] = group[i][1][j] + max_prev_score
                    #     path_trace[i][j] = best_prev_idx
                    if i == 0:
                        dp[i][j] = group[i][1][j]
                        path_trace[i][j] = -1
                    else:
                        dp[i][j] = group[i][1][j]
                        path_trace[i][j] = i
                        if dp[i-1][j] > 0 and dp[i-1][j] > group[i][1][j]:
                            dp[i][j] = dp[i-1][j]
                            path_trace[i][j] = path_trace[i-1][j]
                        if j > 0 and dp[i-1][j-1] > 0 and dp[i-1][j-1] + group[i][1][j] > dp[i][j]:
                            dp[i][j] = dp[i-1][j-1] + group[i][1][j]
                            path_trace[i][j] = i

            best_final_score = 0.0
            stage_idx = -1
            max_stage = -1
            for i in range(num_stages):
                if dp[-1][i] > best_final_score:
                    best_final_score = dp[-1][i]
                    stage_idx = path_trace[-1][i]
                    max_stage = i

            if stage_idx != -1:
                if agent_format:
                    result_chain = []
                    current_frame_idx = stage_idx
        
                    # for j in range(num_stages - 1, -1, -1):
                    #     if current_frame_idx == -1: break
                    #     result_chain.append(group[current_frame_idx + 1])
                    #     current_frame_idx = path_trace[current_frame_idx][j]
                    while best_final_score > 0 and max_stage > -1:
                        if current_frame_idx == -1: break
                        result_chain.append(group[current_frame_idx])
                        max_stage -= 1
                        current_frame_idx = path_trace[current_frame_idx - 1][max_stage]

                    result_chain.reverse()
                    final_chains.append({'chain': result_chain, 'score': best_final_score})
                else:
                    result_chain = group
                    final_chains.append({'chain': result_chain, 'score': best_final_score})
        print(f"Temporal time: {time.time() - start}")
        start = time.time()
        # === BƯỚC 6: SẮP XẾP VÀ TRẢ VỀ KẾT QUẢ CUỐI CÙNG ===
        final_chains.sort(key=lambda x: x['score'], reverse=True)

        output_results = []
        for item in final_chains[:k]:
            formatted_chain = []
            chain_data = item['chain']
            for stage_idx, frame_data in enumerate(chain_data):
                # frame_data: ((video, frame, sec), (s1, s2, ...), path)
                frame_path = frame_data[2]
                score_for_stage = max(frame_data[1])
                formatted_chain.append((frame_path, score_for_stage))
            output_results.append(formatted_chain)
        print(f"Finish time: {time.time() - start}")
        start = time.time()
        print(output_results)
        return output_results
