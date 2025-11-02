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
    
    ⚡ OPTIMIZATIONS:
    1. Precomputed Segment Structure: 
       - Tạo lookup table O(1) cho frame -> segment mapping
       - Precompute shot frames (mod 7 = 0) cho mỗi segment ngay khi load
    
    2. Lazy Shot Expansion:
       - Chỉ expand shots SAU KHI đã lấy top-k candidates
       - Giảm đáng kể số lượng phải xử lý (chỉ xử lý k chains thay vì tất cả)
    
    3. Fast Shot Retrieval:
       - Sử dụng precomputed shot_frames từ lookup table
       - Không cần loop hoặc tính toán lại mod 7
    
    => Tăng tốc độ xử lý đáng kể, đặc biệt khi có nhiều temporal chains!
    """
    def __init__(self, vector_engine: 'FAISSSearchEngine', ocr_engine: 'MeiliSearchService', 
                 segments_dir: str = './video_segments_json'):
        """
        Khởi tạo Search Engine. Embedder giờ đây được quản lý bởi FAISSSearchEngine.
        Cấu trúc segment được tối ưu hóa với lookup table nhanh.
        """
        self.vector_engine = vector_engine
        self.ocr_engine = ocr_engine
        self.segments_dir = segments_dir
        
        # Cache tối ưu: lưu cả segments và lookup table
        self.segments_cache = {}  # {video_name: list of segments}
        self.frame_to_segment_cache = {}  # {video_name: {frame_idx: segment_info}}
        self.segment_shots_cache = {}  # {video_name: {segment_idx: [shot_frames]}}
        
        print("✅ Main SearchEngine (Optimized Multi-Model Version) initialized.")
    
    def preload_all_segments(self):
        """
        Preload tất cả các segment files trước khi khởi động server.
        Điều này giúp tránh việc load on-demand trong quá trình search.
        """
        segments_path = Path(self.segments_dir)
        if not segments_path.exists():
            print(f"⚠️ Segments directory not found: {self.segments_dir}")
            return
        
        segment_files = list(segments_path.glob("segments_*.json"))
        
        if not segment_files:
            print(f"⚠️ No segment files found in {self.segments_dir}")
            return
        
        print(f"🔄 Preloading {len(segment_files)} segment files...")
        start_time = time.time()
        
        for segment_file in segment_files:
            # Extract video name from filename (e.g., segments_K01_V001.json -> K01_V001)
            video_name = segment_file.stem.replace("segments_", "")
            self._load_video_segments(video_name)
        
        elapsed = time.time() - start_time
        stats = self.get_cache_stats()
        print(f"✅ Preloaded segments in {elapsed:.2f}s:")
        print(f"   - Videos: {stats['videos_cached']}")
        print(f"   - Total segments: {stats['total_segments']}")
        print(f"   - Frame lookups ready: {stats['frame_lookups_ready']}")
        print(f"   - Precomputed shots: {stats['precomputed_shots']}")
    
    def _load_video_segments(self, video_name: str) -> List[Dict[str, int]]:
        """
        Load video segments từ file JSON cho một video cụ thể.
        Tạo lookup table để tra cứu nhanh frame -> segment và precompute shot frames.
        
        Args:
            video_name: Tên video (ví dụ: K01_V001)
        
        Returns:
            List các segment dạng [{"start": frame_start, "end": frame_end}, ...]
        """
        if video_name in self.segments_cache:
            return self.segments_cache[video_name]
        
        segment_file = Path(self.segments_dir) / f"segments_{video_name}.json"
        
        if not segment_file.exists():
            print(f"⚠️ Segment file not found for {video_name}")
            return []
        
        try:
            with open(segment_file, 'r') as f:
                segments = json.load(f)
            
            # Cache segments
            self.segments_cache[video_name] = segments
            
            # Tạo lookup table: frame -> segment info (O(1) lookup)
            frame_lookup = {}
            segment_shots = {}
            
            for seg_idx, segment in enumerate(segments):
                start, end = segment['start'], segment['end']
                
                # Precompute shot frames (mod 7 = 0)
                shot_start = start if start % 7 == 0 else ((start // 7) + 1) * 7
                shot_end = (end // 7) * 7
                
                # Lưu tất cả shot frames trong segment này
                shot_frames = []
                if shot_start <= shot_end:
                    shot_frames = [shot_start]
                    # Có thể thêm shot_end nếu cần
                    # if shot_end != shot_start:
                    #     shot_frames.append(shot_end)
                    
                segment_shots[seg_idx] = shot_frames
                
                # Map từng frame -> segment info
                for frame_idx in range(start, end + 1):
                    frame_lookup[frame_idx] = {
                        'segment_idx': seg_idx,
                        'segment': segment,
                        'shot_frames': shot_frames
                    }
            
            self.frame_to_segment_cache[video_name] = frame_lookup
            self.segment_shots_cache[video_name] = segment_shots
            
            return segments
            
        except Exception as e:
            print(f"❌ Error loading segments for {video_name}: {e}")
            return []
    
    def _find_segment_for_frame(self, video_name: str, frame_index: int) -> Optional[Dict[str, Any]]:
        """
        Tìm segment chứa frame_index cho video bằng O(1) lookup.
        
        Args:
            video_name: Tên video
            frame_index: Index của frame cần tìm
        
        Returns:
            Dict chứa segment info và shot_frames hoặc None nếu không tìm thấy
        """
        # Load segments để tạo lookup table nếu chưa có
        if video_name not in self.frame_to_segment_cache:
            self._load_video_segments(video_name)
        
        return self.frame_to_segment_cache.get(video_name, {}).get(frame_index)
    
    def _get_shot_frames_for_range(self, video_name: str, start_frame: int, end_frame: int) -> List[int]:
        """
        Lấy tất cả shot frames (mod 7 = 0) trong khoảng [start_frame, end_frame].
        Tối ưu hóa bằng cách sử dụng precomputed data.
        
        Args:
            video_name: Tên video
            start_frame: Frame bắt đầu của khoảng
            end_frame: Frame kết thúc của khoảng
        
        Returns:
            List các shot frames đã được sort
        """
        # Load segments để tạo lookup table nếu chưa có
        if video_name not in self.frame_to_segment_cache:
            self._load_video_segments(video_name)
        
        frame_lookup = self.frame_to_segment_cache.get(video_name, {})
        seen_segments = set()
        shot_frames = []
        
        # Duyệt qua range và collect shot frames từ các segments liên quan
        for frame_idx in range(start_frame, end_frame + 1):
            segment_info = frame_lookup.get(frame_idx)
            if segment_info:
                seg_idx = segment_info['segment_idx']
                if seg_idx not in seen_segments:
                    seen_segments.add(seg_idx)
                    # Lấy shot frames đã precomputed
                    shot_frames.extend(segment_info['shot_frames'])
        
        # Remove duplicates và sort
        shot_frames = sorted(set(shot_frames))
        return shot_frames

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


        # --- BƯỚC CHUẨN HÓA 1: CHUẨN HÓA ĐIỂM THÀNH PHẦN (CHIA CHO MAX) ---
        text_scores = [s['text'] for s in all_scores.values() if s['text'] > 0]
        image_scores = [s['image'] for s in all_scores.values() if s['image'] > 0]
        ocr_scores = [s['ocr'] for s in all_scores.values() if s['ocr'] > 0]
        subtitle_scores = [s['subtitle'] for s in all_scores.values() if s['subtitle'] > 0]

        max_map = {
            'text': max(text_scores, default=0),
            'image': max(image_scores, default=0),
            'ocr': max(ocr_scores, default=0),
            'subtitle': max(subtitle_scores, default=0)
        }

        temp_combined_results = []
        for path, scores in all_scores.items():
            normalized_scores = {}
            for score_type in ['text', 'image', 'ocr', 'subtitle']:
                max_val = max_map[score_type]
                raw_score = scores[score_type]

                if (raw_score == 0):
                    normalized_scores[score_type] = 0.0
                    continue
                
                if max_val > 0:
                    normalized_scores[score_type] = raw_score / max_val
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


        # --- BƯỚC CHUẨN HÓA 2: CHUẨN HÓA ĐIỂM TỔNG HỢP (CHIA CHO MAX) ---
        fusion_scores = [score for _, score in temp_combined_results]
        max_fusion_score = max(fusion_scores)

        final_results = []
        for path, score in temp_combined_results:
            if max_fusion_score > 0:
                normalized_fusion_score = score / max_fusion_score
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
        k: int = 10, # top_k
        time_distance: int = 30, # time_distance in seconds
        initial_search_k: int = 2048, # num_of_frames
        weights: Dict[str, float] = None,
        vector_models_config: Optional[List[Dict[str, Any]]] = None,
        format: str = "all"
    ) -> List[List[Tuple[str, float]]]:
        """
        Thực hiện tìm kiếm tuần tự theo thời gian, áp dụng logic xử lý mới từ người dùng.
        Phần quy hoạch động đã được sửa lại để đảm bảo tính đúng đắn.
        Định dạng output là List[List[Tuple[str, float]]].
        
        Args:
            format: Định dạng trả về, có thể là:
                - "all": Trả về tất cả frames trong mỗi chain
                - "agent": Chỉ trả về các frames có điểm cao nhất cho mỗi stage
                - "shot": Trả về đầu và cuối của mỗi shot segment với các stage điểm cao nhất
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
            # Chuyển đổi sang định dạng output mong muốn
            return results[:k] if results else []
        # === BƯỚC 1 & 2: TÌM KIẾM BAN ĐẦU (Giữ nguyên để tối ưu hiệu năng) ===
        vector_queries_to_process, vector_batch_map, ocr_queries_to_process, subtitle_queries_to_process = [], [], [], []
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
            if stage_data.get('subtitle'):
                subtitle_queries_to_process.append((stage_idx, stage_data['subtitle']))
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
                    print(f"Lỗi OCR search cho stage {future_subtitle[future]}: {e}")

        # === BƯỚC 3: TẠO CẤU TRÚC DỮ LIỆU `full_resuit` (Theo logic mới) ===
        raw_results_by_stage = defaultdict(lambda: {'text': [], 'image': [], 'ocr': [], 'subtitle': []})
        for i, mapping in enumerate(vector_batch_map):
            if mapping['type'] != 'placeholder':
                stage_idx, q_type = mapping['stage_idx'], mapping['type']
                raw_results_by_stage[stage_idx][q_type] = batch_vector_results[i]
        for stage_idx, results in ocr_results_by_stage.items():
            raw_results_by_stage[stage_idx]['ocr'] = results

        for stage_idx, results in subtitle_results_by_stage.items():
            raw_results_by_stage[stage_idx]['subtitle'] = results       
            
        full_resuit_map = defaultdict(lambda: {'scores': [0.0] * num_stages, 'info': None, 'path': ''})
        for stage_idx in range(num_stages):
            stage_data = raw_results_by_stage[stage_idx]
            reranked_results = self._fuse_and_rerank_candidates(
                stage_data['text'], 
                stage_data['image'], 
                stage_data['ocr'], 
                stage_data['subtitle'], 
                weights if weights else {'text': 0.3, 'ocr': 0.3, 'subtitle': 0.3,'image': 0.1}
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

        # === BƯỚC 4: SẮP XẾP VÀ NHÓM THEO THỜI GIAN (Theo logic mới) ===
        if not full_resuit: return []
        full_resuit.sort(key=lambda x: (x[0][0], x[0][1])) # Sắp xếp theo video, rồi theo frame

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
                # Đầu tiên, tính số stages match (dùng cho sorting)
                # Logic này giống với format="agent"
                num_stages_matched = 0
                current_frame_idx = stage_idx
                clone_score = best_final_score
                temp_max_stage = max_stage
                agent_chain = []
                
                while clone_score > 0 and temp_max_stage > -1:
                    if current_frame_idx == -1: break
                    if group[current_frame_idx][1][temp_max_stage] > 0:
                        agent_chain.append(group[current_frame_idx])
                        num_stages_matched += 1
                        clone_score -= group[current_frame_idx][1][temp_max_stage]
                    temp_max_stage -= 1
                    current_frame_idx = path_trace[current_frame_idx - 1][temp_max_stage]
                
                agent_chain.reverse()
                
                # Bây giờ xử lý theo format
                if format == "agent":
                    final_chains.append({
                        'chain': agent_chain, 
                        'score': best_final_score,
                        'num_stages_matched': num_stages_matched
                    })
                elif format == "shot":
                    # Với shot format: Lưu thông tin cơ bản, sẽ add shots SAU khi đã chọn top-k
                    # Chỉ lưu agent_chain và metadata, không expand shots ngay
                    final_chains.append({
                        'chain': agent_chain,  # Chỉ lưu agent chain
                        'score': best_final_score,
                        'num_stages_matched': num_stages_matched,
                        'format': 'shot',  # Đánh dấu để expand sau
                        'video_name': group[0][0][0],
                        'min_frame': min(frame_data[0][1] for frame_data in group),
                        'max_frame': max(frame_data[0][1] for frame_data in group)
                    })
                else:  # format == "all"
                    final_chains.append({
                        'chain': group, 
                        'score': best_final_score,
                        'num_stages_matched': len(group)  # Với "all", dùng tất cả frames
                    })

        # === BƯỚC 6: SẮP XẾP VÀ LẤY TOP-K (CHƯA EXPAND SHOTS) ===
        # Sort theo số stages match (num_stages_matched) và score
        final_chains.sort(key=lambda x: (x['num_stages_matched'], x['score']), reverse=True)
        
        # Lấy top-k chains trước khi expand shots
        top_k_chains = final_chains[:k]
        
        # # === BƯỚC 7: EXPAND SHOTS CHỈ CHO TOP-K (GIẢM SỐ LƯỢNG XỬ LÝ) ===
        # output_results = []
        # start_ = time.time()
        # for item in top_k_chains:
        #     if item.get('format') == 'shot':
        #         # Expand shots CHỈ cho top-k results
        #         video_name = item['video_name']
        #         min_frame = item['min_frame']
        #         max_frame = item['max_frame']
                
        #         # Lấy shot frames bằng O(1) lookup với precomputed data
        #         shot_frames = self._get_shot_frames_for_range(video_name, min_frame, max_frame)
                
        #         # Tạo result chain với shot frames
        #         formatted_chain = []
        #         dummy_scores = tuple([0.0] * num_stages)
                
        #         for shot_frame in shot_frames:
        #             shot_second = shot_frame / 30.0
        #             shot_info = (video_name, shot_frame, shot_second)
        #             shot_path = f"{video_name}/{shot_frame}.jpg"
        #             # Format: (path, (scores_tuple, total_score))
        #             formatted_chain.append((shot_path, (dummy_scores, item['score'])))
                
        #         output_results.append(formatted_chain)
        #     else:
        #         # Xử lý format "agent" hoặc "all" như cũ
        #         formatted_chain = []
        #         chain_data = item['chain']
        #         for frame_data in chain_data:
        #             # frame_data: ((video, frame, sec), (s1, s2, ...), path)
        #             frame_path = frame_data[2]
        #             score_for_stage = (frame_data[1], item['score'])
        #             formatted_chain.append((frame_path, score_for_stage))
        #         output_results.append(formatted_chain)
        # print('time', time.time()-start_)
        
        # return output_results

        # === BƯỚC 7: EXPAND SHOTS CHỈ CHO TOP-K (GIẢM SỐ LƯỢNG XỬ LÝ) ===
        output_results = []
        start_ = time.time()
        MAX_IMAGES = 16

        for item in top_k_chains:
            # Với "shot" mới: bao gồm agent frames + shot frames (tối đa 20 ảnh)
            if item.get('format') == 'shot':
                video_name = item['video_name']
                min_frame = item['min_frame']
                max_frame = item['max_frame']
                agent_chain = item['chain']  # list các phần tử group: ((video, frame, sec), (scores_tuple), path)

                # 1) Lấy danh sách shot frames đã precompute
                shot_frames = self._get_shot_frames_for_range(video_name, min_frame, max_frame)

                # 2) Lấy danh sách agent frames và xác định peak frames ngay
                agent_frames = []
                agent_frame_map = {}  # frame_idx -> frame_data để lấy lại scores cho agent
                stage_peak_frames = {}  # {stage_idx: (frame_index, max_score)}
                
                for frame_data in agent_chain:
                    # frame_data: ((video, frame, sec), (s1, s2, ...), path)
                    v, f, sec = frame_data[0]
                    if v != video_name:
                        continue
                    agent_frames.append(f)
                    agent_frame_map[f] = frame_data
                    
                    # Xác định peak frame cho mỗi stage
                    scores_tuple = frame_data[1]
                    for stage_idx, stage_score in enumerate(scores_tuple):
                        if stage_score > 0:
                            if stage_idx not in stage_peak_frames or stage_score > stage_peak_frames[stage_idx][1]:
                                stage_peak_frames[stage_idx] = (f, stage_score)

                # 3) Hợp nhất: ưu tiên agent_frames trước, sau đó thêm shot_frames không trùng
                merged_frames = []
                seen = set()

                # a) Thêm toàn bộ agent frames theo thứ tự xuất hiệnimages
                for f in agent_frames:
                    if f not in seen:
                        merged_frames.append(('agent', f))
                        seen.add(f)

                # b) Thêm shot frames (đã sort) không trùng
                for f in shot_frames:
                    if f not in seen:
                        merged_frames.append(('shot', f))
                        seen.add(f)

                # 4) Sắp xếp tăng dần theo frame index để trình bày mạch lạc theo thời gian
                merged_frames.sort(key=lambda x: x[1])

                # 5) Giới hạn tối đa 20 ảnh, luôn ưu tiên giữ agent frames
                # Nếu >20: giữ tất cả agent trước (theo thứ tự thời gian), sau đó lấp đầy bằng shot
                if len(merged_frames) > MAX_IMAGES:
                    agents = [t for t in merged_frames if t[0] == 'agent']
                    shots  = [t for t in merged_frames if t[0] == 'shot']

                    kept = []
                    for t in agents:
                        if len(kept) < MAX_IMAGES:
                            kept.append(t)
                        else:
                            break
                    # Lấp đầy bằng shot nếu còn chỗ
                    for t in shots:
                        if len(kept) < MAX_IMAGES:
                            kept.append(t)
                        else:
                            break
                    merged_frames = kept

                    # Sau chọn xong, sort lại theo thời gian
                    merged_frames.sort(key=lambda x: x[1])

                # 6) Build formatted_chain: 
                #  - Với agent frame: giữ nguyên (scores_tuple, total_chain_score) và đánh dấu peak
                #  - Với shot frame thêm: dùng dummy score tuple
                formatted_chain = []
                dummy_scores = tuple([0.0] * num_stages)
                
                for tag, f in merged_frames:
                    sec = f / 30.0
                    frame_path = f"{video_name}/{f}.jpg"
                    
                    # Kiểm tra xem frame này có phải là peak frame của stage nào không
                    is_peak_frame = False
                    peak_stage = -1
                    for stage_idx, (peak_f, _) in stage_peak_frames.items():
                        if f == peak_f:
                            is_peak_frame = True
                            peak_stage = stage_idx
                            break
                    
                    if tag == 'agent' and f in agent_frame_map:
                        # frame_data: ((video, frame, sec), (scores_tuple), path)
                        frame_data = agent_frame_map[f]
                        formatted_chain.append(
                            (frame_path, (frame_data[1], item['score'], is_peak_frame, peak_stage))
                        )
                    else:
                        # shot bổ sung
                        formatted_chain.append(
                            (frame_path, (dummy_scores, item['score'], False, -1))
                        )

                output_results.append(formatted_chain)

            else:
                # Xử lý format "agent" hoặc "all" như cũ
                formatted_chain = []
                chain_data = item['chain']
                
                # Tìm peak frame cho mỗi stage - chỉ cần 1 vòng lặp
                stage_peak_frames = {}  # {stage_idx: (idx, max_score)}
                for idx, frame_data in enumerate(chain_data):
                    # frame_data: ((video, frame, sec), (scores_tuple), path)
                    scores_tuple = frame_data[1]
                    for stage_idx, stage_score in enumerate(scores_tuple):
                        if stage_score > 0:
                            if stage_idx not in stage_peak_frames or stage_score > stage_peak_frames[stage_idx][1]:
                                stage_peak_frames[stage_idx] = (idx, stage_score)
                
                # Build formatted chain với peak frame info
                for idx, frame_data in enumerate(chain_data):
                    frame_path = frame_data[2]
                    
                    # Kiểm tra xem frame này có phải là peak frame của stage nào không
                    is_peak_frame = False
                    peak_stage = -1
                    for stage_idx, (peak_idx, _) in stage_peak_frames.items():
                        if idx == peak_idx:
                            is_peak_frame = True
                            peak_stage = stage_idx
                            break
                    
                    score_for_stage = (frame_data[1], item['score'], is_peak_frame, peak_stage)
                    formatted_chain.append((frame_path, score_for_stage))
                output_results.append(formatted_chain)

        print('time', time.time()-start_)
        return output_results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê về cache để đánh giá hiệu năng.
        
        Returns:
            Dict chứa thông tin về cache size và precomputed data
        """
        stats = {
            'videos_cached': len(self.segments_cache),
            'total_segments': sum(len(segs) for segs in self.segments_cache.values()),
            'frame_lookups_ready': sum(len(lookup) for lookup in self.frame_to_segment_cache.values()),
            'precomputed_shots': sum(
                sum(len(shots) for shots in shot_dict.values()) 
                for shot_dict in self.segment_shots_cache.values()
            )
        }
        return stats
