from pathlib import Path
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from collections import defaultdict
import os
from PIL import Image
import concurrent.futures

from faiss_engine import FAISSSearchEngine
from meilisearch_service import MeiliSearchService


class SearchEngine:
    """
    Search Engine được tối ưu hóa cho temporal search, tận dụng tối đa batch processing 
    và re-ranking đa mô hình.
    """
    def __init__(self, vector_engine: FAISSSearchEngine, ocr_engine: MeiliSearchService):
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
        raw_subtitle_results: List[Dict[str, Any]],
        weights: Dict[str, float]
    ) -> List[Tuple[str, float]]:
        """
        Hàm re-rank chuyên dụng.
        Kết hợp các kết quả thô, thực hiện chuẩn hóa Min-Max hai lần:
        1. Chuẩn hóa điểm từ mỗi nguồn (text, image, ocr).
        2. Chuẩn hóa điểm tổng hợp cuối cùng (fusion_score).
        """
        all_scores = defaultdict(lambda: {'text': 0.0, 'image': 0.0, 'ocr': 0.0, 'subtitle': 0.0})
        for path, score in raw_text_results: 
            all_scores[path]['text'] = score
        for path, score in raw_image_results: 
            all_scores[path]['image'] = score
        for ocr_hit in raw_ocr_results:
            video_name = ocr_hit.get('video_name', '')
            frame_index = ocr_hit.get('frame_index', -1)
            ocr_score = ocr_hit.get('_rankingScore', 0.0) 
            if video_name and frame_index != -1:
                path = f"{video_name}/{frame_index}.jpg"
                all_scores[path]['ocr'] = ocr_score
        for ocr_hit in raw_subtitle_results:
            video_name = ocr_hit.get('video_name', '')
            frame_index = ocr_hit.get('frame_index', -1)
            ocr_score = ocr_hit.get('_rankingScore', 0.0) 
            if video_name and frame_index != -1:
                path = f"{video_name}/{frame_index}.jpg"
                all_scores[path]['subtitle'] = ocr_score

        if not all_scores:
            return []

        # --- BƯỚC CHUẨN HÓA 1: CHUẨN HÓA ĐIỂM THÀNH PHẦN ---
        text_scores = [s['text'] for s in all_scores.values() if s['text'] > 0]
        image_scores = [s['image'] for s in all_scores.values() if s['image'] > 0]
        ocr_scores = [s['ocr'] for s in all_scores.values() if s['ocr'] > 0]
        subtitle_scores = [s['subtitle'] for s in all_scores.values() if s['subtitle'] > 0]

        min_max_map = {
            'text': (min(text_scores, default=0), max(text_scores, default=0)),
            'image': (min(image_scores, default=0), max(image_scores, default=0)),
            'ocr': (min(ocr_scores, default=0), max(ocr_scores, default=0)),
            'subtitle': (min(subtitle_scores, default=0), max(subtitle_scores, default=0))
        }

        temp_combined_results = []
        for path, scores in all_scores.items():
            normalized_scores = {}
            for score_type in ['text', 'image', 'ocr', 'subtitle']:
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
                weights.get('ocr', 0.0) * normalized_scores['ocr'] +
                weights.get('subtitle', 0.0) * normalized_scores['subtitle']
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
        subtitle_query: Optional[str] = None,
        k: int = 100,
        weights: Dict[str, float] = None,
        vector_models_config: Optional[List[Dict[str, Any]]] = None
    ) -> List[Tuple[str, float]]:
        """
        Thực hiện tìm kiếm hybrid cho một truy vấn đơn giản (một stage).
        """
        if weights is None: 
            weights = {'text': 0.3, 'ocr': 0.3, 'image': 0.1, 'subtitle': 0.3}
        if vector_models_config is None:
            available_model_names = list(self.vector_engine.configs.keys())
            num_models = len(available_model_names)
            if num_models > 0:
                equal_weight = 1.0 / num_models
                vector_models_config = [{'model_name': model_name, 'weight': equal_weight} for model_name in available_model_names]
            else:
                vector_models_config = []

        raw_results = {'text': [], 'image': [], 'ocr': [], 'subtitle': []}
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
            
            future_subtitle = None
            if subtitle_query:
                future_subtitle = executor.submit(self.ocr_engine.search_subscript, subtitle_query, k)
            
            future_ocr = None
            if ocr_query:
                future_ocr = executor.submit(self.ocr_engine.search_ocr, ocr_query, k)
            if future_vector:
                batch_vector_results = future_vector.result()
                for i, q_type in enumerate(vector_types):
                    raw_results[q_type] = batch_vector_results[i]
                    
            if future_ocr:
                raw_results['ocr'] = future_ocr.result()

            if future_subtitle:
                raw_results['subtitle'] = future_subtitle.result()

        combined_results = self._fuse_and_rerank_candidates(
            raw_text_results=raw_results['text'],
            raw_image_results=raw_results['image'],
            raw_ocr_results=raw_results['ocr'],
            raw_subtitle_results=raw_results['subtitle'],
            weights=weights
        )
        return combined_results[:k]

    def temporal_search(
        self,
        queries: Optional[List[Dict[str, Any]]] = None,
        k: int = 10,
        time_distance: int = 30,
        initial_search_k: int = 2048,
        weights: Dict[str, float] = None,
        vector_models_config: Optional[List[Dict[str, Any]]] = None,
        agent_format: bool = False
    ) -> List[List[Tuple[str, float]]]:
        """
        Thực hiện tìm kiếm tuần tự theo thời gian với dynamic programming.
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
                subtitle_query=stage_query.get('subtitle'),
                k=initial_search_k,
                weights=weights,
                vector_models_config=vector_models_config
            )
            return results[:k] if results else []
        
        # Collect queries for parallel processing
        vector_queries_to_process, vector_batch_map = [], []
        ocr_queries_to_process, subtitle_queries_to_process = [], []
        
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
            if stage_data.get('subtitle'):
                subtitle_queries_to_process.append((stage_idx, stage_data['subtitle']))
        
        # Execute parallel searches
        batch_vector_results, ocr_results_by_stage, subtitle_results_by_stage = [], defaultdict(list), defaultdict(list)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_vector = executor.submit(self.vector_engine.search, vector_queries_to_process, vector_models_config, initial_search_k)
            future_ocr = {executor.submit(self.ocr_engine.search_ocr, ocr_text, 1024): stage_idx for stage_idx, ocr_text in ocr_queries_to_process}
            future_subtitle = {executor.submit(self.ocr_engine.search_subscript, subtitle_text, 1024): stage_idx for stage_idx, subtitle_text in subtitle_queries_to_process}

            try: 
                batch_vector_results = future_vector.result()
            except Exception as e: 
                print(f"Lỗi batch vector search: {e}")
            for future in concurrent.futures.as_completed(future_ocr):
                try: 
                    ocr_results_by_stage[future_ocr[future]] = future.result()
                except Exception as e: 
                    print(f"Lỗi OCR search cho stage {future_ocr[future]}: {e}")

            for future in concurrent.futures.as_completed(future_subtitle):
                try: 
                    subtitle_results_by_stage[future_subtitle[future]] = future.result()
                except Exception as e: 
                    print(f"Lỗi subtitle search cho stage {future_subtitle[future]}: {e}")

        # Merge results by stage
        raw_results_by_stage = defaultdict(lambda: {'text': [], 'image': [], 'ocr': [], 'subtitle': []})
        for i, mapping in enumerate(vector_batch_map):
            if mapping['type'] != 'placeholder':
                stage_idx, q_type = mapping['stage_idx'], mapping['type']
                raw_results_by_stage[stage_idx][q_type] = batch_vector_results[i]
        for stage_idx, results in ocr_results_by_stage.items():
            raw_results_by_stage[stage_idx]['ocr'] = results
        for stage_idx, results in subtitle_results_by_stage.items():
            raw_results_by_stage[stage_idx]['subtitle'] = results       
            
        # Create full result map
        full_resuit_map = defaultdict(lambda: {'scores': [0.0] * num_stages, 'info': None, 'path': ''})
        for stage_idx in range(num_stages):
            stage_data = raw_results_by_stage[stage_idx]
            reranked_results = self._fuse_and_rerank_candidates(
                stage_data['text'], 
                stage_data['image'], 
                stage_data['ocr'], 
                stage_data['subtitle'], 
                weights if weights else {'text': 0.3, 'ocr': 0.3, 'subtitle': 0.3, 'image': 0.1}
            )
            for path, score in reranked_results:
                full_resuit_map[path]['scores'][stage_idx] = score
                if not full_resuit_map[path]['info']:
                    try:
                        video_name = os.path.dirname(path)
                        frame_id = int(os.path.splitext(os.path.basename(path))[0])
                        second = frame_id / 30.0
                        full_resuit_map[path]['info'] = (video_name, frame_id, second)
                        full_resuit_map[path]['path'] = path
                    except (ValueError, IndexError):
                        continue
        
        valid_results = [v for k, v in full_resuit_map.items() if v['info']]
        full_resuit = [(item['info'], tuple(item['scores']), item['path']) for item in valid_results]

        if not full_resuit: 
            return []
        full_resuit.sort(key=lambda x: (x[0][0], x[0][1]))

        # Group by time distance
        rerank_results = []
        for item in full_resuit:
            item_info = item[0]
            video, frame, second = item_info
            if not rerank_results or video != rerank_results[-1][-1][0][0] or second - rerank_results[-1][-1][0][2] > time_distance:
                rerank_results.append([])
            if rerank_results[-1] and frame == rerank_results[-1][-1][0][1]:
                rerank_results[-1][-1][1] = [a + b for a, b in zip(rerank_results[-1][-1][1], item[1])]
            else:
                rerank_results[-1].append(item)

        # Dynamic programming to find best chains
        final_chains = []
        for group in rerank_results:
            if not group: 
                continue
            
            dp = [[0.0] * num_stages for _ in range(len(group))]
            path_trace = [[-1] * num_stages for _ in range(len(group))]

            for i in range(len(group)):
                for j in range(num_stages):
                    if i == 0:
                        dp[i][j] = group[i][1][j]
                        path_trace[i][j] = i
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
                    clone_score = best_final_score
                    while clone_score > 0 and max_stage > -1:
                        if current_frame_idx == -1: 
                            break
                        if group[current_frame_idx][1][max_stage] > 0:
                            result_chain.append(group[current_frame_idx])
                            clone_score -= group[current_frame_idx][1][max_stage]
                        max_stage -= 1
                        current_frame_idx = path_trace[current_frame_idx - 1][max_stage] if current_frame_idx > 0 else -1

                    result_chain.reverse()
                    final_chains.append({'chain': result_chain, 'score': best_final_score})
                else:
                    result_chain = group
                    final_chains.append({'chain': result_chain, 'score': best_final_score})

        final_chains.sort(key=lambda x: (len(x['chain']), x['score']), reverse=True)

        output_results = []
        for item in final_chains[:k]:
            formatted_chain = []
            chain_data = item['chain']
            for stage_idx, frame_data in enumerate(chain_data):
                frame_path = frame_data[2]
                score_for_stage = (frame_data[1], item['score'])
                formatted_chain.append((frame_path, score_for_stage))
            output_results.append(formatted_chain)

        return output_results
