import json
import os
import threading
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

# Use same logger as Django to ensure logs are visible
logger = logging.getLogger('django')

try:
    import meilisearch
    logger.info("Using sync Meilisearch client")
except ImportError:
    logger.error("Meilisearch not installed. Run: pip install meilisearch")
    meilisearch = None

# Import config
try:
    from .config import MEILISEARCH_HOST, MEILISEARCH_PORT, MEILISEARCH_API_KEY, LIST_DATASET
except ImportError:
    # Fallback to environment variables or defaults
    MEILISEARCH_HOST = os.getenv('MEILISEARCH_HOST', 'localhost')
    MEILISEARCH_PORT = int(os.getenv('MEILISEARCH_PORT', '7700'))
    MEILISEARCH_API_KEY = os.getenv('MEILISEARCH_API_KEY', 'masterKey')
    LIST_DATASET = [
        ('/backend/ocr-data/viet-ocr-json-data', 'viet_ocr_index'),
        ('/backend/ocr-data/parseq-ocr-json-data', 'parseq_ocr_index')
    ]


class SingletonMeta(type):
    """
    Metaclass để implement Singleton pattern
    Thread-safe singleton implementation
    """
    _instances = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        """
        Thread-safe singleton instance creation
        """
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]
    
    @classmethod
    def reset_instance(mcs, cls):
        """
        Reset singleton instance (useful for testing or config reload)
        """
        with mcs._lock:
            if cls in mcs._instances:
                del mcs._instances[cls]


class MeiliSearchService(metaclass=SingletonMeta):
    """
    Service để search OCR text bằng Meilisearch.
    Meilisearch có tốc độ search cực nhanh và setup đơn giản.
    Tự động typo tolerance và ranking algorithm tốt.
    """
    
    def __init__(self, host: str = None, port: int = None, api_key: str = None):
        # Chỉ khởi tạo nếu chưa được khởi tạo (singleton check)
        if hasattr(self, '_initialized'):
            return
        
        if meilisearch is None:
            raise ImportError("Meilisearch not installed. Run: pip install meilisearch")
        
        # Sử dụng config hoặc parameters
        if host is None:
            host = MEILISEARCH_HOST
        if port is None:
            port = MEILISEARCH_PORT
        if api_key is None:
            api_key = MEILISEARCH_API_KEY
            
        self.host = host
        self.port = port
        self.api_key = api_key
        self.url = f"http://{host}:{port}"
        
        # Tạo sync client
        self.client = meilisearch.Client(self.url, api_key)
        
        # Cấu hình datasets
        self.datasets = LIST_DATASET
        self.index_names = [index_name for _, index_name in self.datasets]
        self.viet_ocr_index = self.index_names[0]  # First dataset
        self.parseq_ocr_index = self.index_names[1]  # Second dataset
        
        self._initialized = True
        
        logger.info(f"MeiliSearchService singleton instance created - Meili: {self.url}")
        logger.info(f"Loaded {len(self.datasets)} datasets: {[name for _, name in self.datasets]}")
    
    @classmethod
    def reset_singleton(cls):
        """
        Reset singleton instance (useful for testing or config changes)
        """
        SingletonMeta.reset_instance(cls)
    
    @classmethod
    def get_instance(cls, host: str = None, port: int = None, api_key: str = None):
        """
        Get singleton instance (alternative way to access)
        """
        return cls(host, port, api_key)
    
    def close(self):
        """
        Close connections if needed (sync version)
        """
        try:
            if hasattr(self.client, 'close'):
                self.client.close()
            logger.info("MeiliSearch client closed")
        except Exception as e:
            logger.error(f"Error closing MeiliSearch client: {e}")
    
    def create_indices(self):
        """
        Tạo indices với cấu hình tối ưu cho OCR search
        """
        try:
            for index_name in self.index_names:
                logger.info(f"Creating/updating index: {index_name}")
                
                # Try to get existing index first
                index = None
                try:
                    index = self.client.get_index(index_name)
                    logger.info(f"Index {index_name} already exists")
                except Exception:
                    # Index doesn't exist, create it
                    try:
                        task = self.client.create_index(index_name, {'primaryKey': 'id'})
                        logger.info(f"Created index {index_name}, task: {task.task_uid if hasattr(task, 'task_uid') else 'N/A'}")
                        
                        # Wait a bit for index to be ready
                        import time
                        time.sleep(1)
                        
                        # Now get the created index
                        index = self.client.get_index(index_name)
                    except Exception as create_e:
                        logger.error(f"Failed to create index {index_name}: {create_e}")
                        continue
                
                # Configure search settings if we have the index
                if index:
                    try:
                        settings = {
                            'searchableAttributes': ['text', 'video_name'],
                            'displayedAttributes': ['*'],
                            'filterableAttributes': ['video_name', 'frame_index'],
                            'sortableAttributes': ['frame_index'],
                            'rankingRules': [
                                'words',
                               
                                'proximity',
                                'attribute',
                                'sort',
                                'exactness'
                            ],
                            'stopWords': [],
                            'synonyms': {},
                            'distinctAttribute': None,
                            'typoTolerance': {
                                'enabled': True,
                                'minWordSizeForTypos': {
                                    'oneTypo': 3,
                                    'twoTypos': 7
                                }
                            }
                        }
                        
                        task = index.update_settings(settings)
                        logger.info(f"✅ Index {index_name} settings updated, task: {task.task_uid if hasattr(task, 'task_uid') else 'N/A'}")
                    except Exception as settings_e:
                        logger.warning(f"Failed to update settings for {index_name}: {settings_e}")
                
                logger.info(f"✅ Index {index_name} ready")
                
        except Exception as e:
            logger.error(f"Error in create_indices: {e}")
            raise
    
    def index_ocr_data(self, json_file_path: str, index_name: str):
        """
        Index dữ liệu OCR từ file JSON vào Meilisearch.
        Chỉ index trường text, không index fps.
        
        Args:
            json_file_path: Đường dẫn đến file JSON
            index_name: Tên index để lưu dữ liệu
        """
        if index_name not in self.index_names:
            raise ValueError(f"Index name '{index_name}' not found in configured datasets")
            
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        video_name = Path(json_file_path).stem
        
        # Chuẩn bị documents cho Meilisearch
        documents = []
        for frame_index, frame_data in data.items():
            if isinstance(frame_data, dict) and 'text' in frame_data:
                text = frame_data['text']
                if text and text.strip():  # Chỉ index nếu text không rỗng
                    doc = {
                        "id": f"{video_name}_{frame_index}_{index_name}",
                        "video_name": video_name,
                        "frame_index": int(frame_index),
                        "text": text.strip(),
                        "dataset_type": index_name
                    }
                    documents.append(doc)
        
        # Add documents to Meilisearch
        if documents:
            try:
                index = self.client.get_index(index_name)
                task = index.add_documents(documents)
                
                logger.info(f"Indexed {len(documents)} documents for {video_name} in {index_name}")
                logger.info(f"Meilisearch task ID: {task.task_uid if hasattr(task, 'task_uid') else 'N/A'}")
                
            except Exception as e:
                logger.error(f"Error indexing {video_name} in {index_name}: {e}")
                raise
    
    def search_ocr(self, query: str, size: int = 100, normalize_method: str = 'advanced') -> List[Dict[str, Any]]:
        """
        Fast OCR search with optimized ranking.
        Uses Meilisearch built-in ranking + lightweight custom scoring.
        Auto-normalizes Vietnamese text to match processed dataset.
        
        Args:
            query: Search query
            size: Maximum number of results
            normalize_method: 'minmax' for min-max normalization, 'advanced' for tier-based
        """
        import time
        search_start_time = time.time()
        
        # Normalize query to match dataset format (Vietnamese without accents)
        normalized_query = remove_vietnamese_accents(query.strip())
        logger.info(f"🔍 Search query: '{query}' → normalized: '{normalized_query}'")
        
        try:
            all_results = []
            
            # Search with optimized settings for speed
            for index_name in self.index_names:
                try:
                    index = self.client.get_index(index_name)
                    
                    # Use Meilisearch multi-search for better performance
                    search_params = {
                        'limit': size,  # Request only what we need per index
                        'attributesToHighlight': ['text'],
                        'highlightPreTag': '<mark>',
                        'highlightPostTag': '</mark>',
                        'attributesToRetrieve': ['*'],
                        'showRankingScore': True,
                        'matchingStrategy': 'all',  # Require all words (better for exact match)
                    }
                    
                    # Use normalized query for search
                    search_result = index.search(normalized_query, search_params)
                    
                    # Light-weight processing for speed
                    for hit in search_result['hits']:
                        text = hit.get('text', '').lower().strip()
                        query_lower = normalized_query.lower().strip()
                        
                        # Meilisearch base score (0-1)
                        meili_score = hit.get('_rankingScore', 0.5)
                        
                        # Hierarchical scoring based on match quality
                        custom_score = self._calculate_match_quality(text, query_lower)
                        
                        # Dataset preference (minimal)
                        dataset_bonus = 0.05 if index_name == 'viet_ocr_index' else 0
                        
                        # Final score: Custom hierarchy + Meilisearch + dataset
                        final_score = custom_score + (meili_score * 0.1) + dataset_bonus
                        
                        result = {
                            'video_name': hit.get('video_name', ''),
                            'frame_index': hit.get('frame_index', 0),
                            'text': hit.get('text', ''),
                            'dataset_type': hit.get('dataset_type', index_name),
                            'score': final_score,
                            'highlight': hit.get('_formatted', {}).get('text', hit.get('text', ''))
                        }
                        all_results.append(result)
                        
                except Exception as e:
                    logger.error(f"Error searching index {index_name}: {e}")
                    continue
            
            # Fast sorting by score
            all_results.sort(key=lambda x: x['score'], reverse=True)
            
            # Deduplicate by video_name + frame_index (keep highest score)
            deduplicated_results = self._deduplicate_results(all_results)
            
            # Return top results after deduplication
            final_results = deduplicated_results[:size]
            
            # Normalize scores to 0-1 range
            if normalize_method == 'advanced':
                final_results = self._normalize_scores_advanced(final_results)
            else:
                final_results = self._normalize_scores(final_results)
            
            search_time = time.time() - search_start_time
            logger.info(f"🔍 Fast Meilisearch completed: {len(final_results)} results from {len(all_results)} total in {search_time:.3f}s")
            
            return final_results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def search_ocr_with_detailed_performance(self, query: str, size: int = 100) -> Dict[str, Any]:
        """
        Search với detailed performance analysis để debug tốc độ
        """
        import time
        
        total_start = time.time()
        performance = {}
        
        try:
            all_results = []
            
            for index_name in self.index_names:
                index_start = time.time()
                
                try:
                    index = self.client.get_index(index_name)
                    
                    search_start = time.time()
                    search_result = index.search(
                        query,
                        {
                            'limit': size,
                            'attributesToHighlight': ['text'],
                            'highlightPreTag': '<mark>',
                            'highlightPostTag': '</mark>',
                            'attributesToRetrieve': ['*'],
                            'showRankingScore': True,
                        }
                    )
                    search_time = time.time() - search_start
                    
                    processing_start = time.time()
                    # Simple processing
                    for hit in search_result['hits']:
                        text = hit.get('text', '').lower().strip()
                        query_lower = query.lower().strip()
                        
                        meili_score = hit.get('_rankingScore', 0.5)
                        exact_phrase_bonus = 2.0 if query_lower in text else 0
                        dataset_bonus = 0.1 if index_name == 'viet_ocr_index' else 0
                        
                        final_score = meili_score + exact_phrase_bonus + dataset_bonus
                        
                        result = {
                            'video_name': hit.get('video_name', ''),
                            'frame_index': hit.get('frame_index', 0),
                            'text': hit.get('text', ''),
                            'dataset_type': hit.get('dataset_type', index_name),
                            'score': final_score,
                            'highlight': hit.get('_formatted', {}).get('text', hit.get('text', ''))
                        }
                        all_results.append(result)
                    
                    processing_time = time.time() - processing_start
                    index_total_time = time.time() - index_start
                    
                    performance[index_name] = {
                        'search_time': search_time,
                        'processing_time': processing_time,
                        'total_time': index_total_time,
                        'results_count': len(search_result['hits'])
                    }
                    
                except Exception as e:
                    logger.error(f"Error in performance test for {index_name}: {e}")
                    performance[index_name] = {'error': str(e)}
            
            # Sorting time
            sort_start = time.time()
            all_results.sort(key=lambda x: x['score'], reverse=True)
            final_results = all_results[:size]
            sort_time = time.time() - sort_start
            
            # Normalize scores to 0-1 range
            final_results = self._normalize_scores(final_results)
            
            total_time = time.time() - total_start
            
            performance['summary'] = {
                'total_search_time': total_time,
                'sorting_time': sort_time,
                'total_results': len(all_results),
                'final_results': len(final_results),
                'query': query
            }
            
            logger.info(f"🔍 Performance Analysis: {performance}")
            
            return {
                'results': final_results,
                'performance': performance
            }
            
        except Exception as e:
            logger.error(f"Performance test error: {e}")
            return {'results': [], 'performance': {'error': str(e)}}

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê về indices
        """
        try:
            stats = {}
            for index_name in self.index_names:
                try:
                    index = self.client.get_index(index_name)
                    index_stats = index.get_stats()
                    
                    # Truy cập attributes trực tiếp thay vì dùng get()
                    stats[index_name] = {
                        'numberOfDocuments': getattr(index_stats, 'number_of_documents', 0),
                        'isIndexing': getattr(index_stats, 'is_indexing', False),
                        'fieldDistribution': getattr(index_stats, 'field_distribution', {})
                    }
                    
                    logger.info(f"📈 Meilisearch Index '{index_name}': {stats[index_name]['numberOfDocuments']} docs")
                    
                except Exception as e:
                    logger.error(f"Error getting stats for {index_name}: {e}")
                    stats[index_name] = {'error': str(e)}
                    
            return stats
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {}

    def _calculate_match_score(self, text: str, query: str) -> float:
        """
        Calculate custom match score based on match quality priority:
        1. Exact phrase match (10.0)
        2. All words present, correct order (8.0)
        3. All words present, wrong order (6.0) 
        4. Partial word match (4.0)
        5. Fuzzy versions of above (with penalty)
        """
        from difflib import SequenceMatcher
        
        # Normalize whitespace
        text = ' '.join(text.split())
        query = ' '.join(query.split())
        
        if not query or not text:
            return 0.0
            
        # Split query into words
        query_words = query.split()
        
        # 1. EXACT PHRASE MATCH (highest priority)
        if query in text:
            return 10.0
            
        # 2. CHECK WORD MATCHES
        exact_words_found = []
        fuzzy_words_found = []
        
        for query_word in query_words:
            # Check exact word match
            if query_word in text:
                exact_words_found.append(query_word)
            else:
                # Check fuzzy match
                text_words = text.split()
                best_fuzzy_score = 0
                for text_word in text_words:
                    similarity = SequenceMatcher(None, query_word, text_word).ratio()
                    if similarity >= 0.7 and similarity > best_fuzzy_score:
                        best_fuzzy_score = similarity
                        
                if best_fuzzy_score > 0:
                    fuzzy_words_found.append((query_word, best_fuzzy_score))
        
        total_query_words = len(query_words)
        exact_match_count = len(exact_words_found)
        fuzzy_match_count = len(fuzzy_words_found)
        total_match_count = exact_match_count + fuzzy_match_count
        
        # ALL WORDS PRESENT
        if total_match_count == total_query_words:
            if exact_match_count == total_query_words:
                # All exact matches - check order
                if self._check_word_order(text, query_words):
                    return 8.0  # All words, correct order
                else:
                    return 6.0  # All words, wrong order
            else:
                # Mix of exact and fuzzy matches
                fuzzy_penalty = sum(1 - score for _, score in fuzzy_words_found) * 0.5
                return max(4.0, 6.0 - fuzzy_penalty)
        
        # PARTIAL MATCHES
        elif total_match_count > 0:
            if exact_match_count > 0:
                return 4.0 * (exact_match_count / total_query_words)
            else:
                # Only fuzzy matches
                avg_fuzzy_score = sum(score for _, score in fuzzy_words_found) / len(fuzzy_words_found)
                return avg_fuzzy_score * 3.0
        
        return 0.0

    def _check_word_order(self, text: str, words: list) -> bool:
        """Check if words appear in correct order in text"""
        if not words:
            return True
            
        last_pos = -1
        for word in words:
            pos = text.find(word, last_pos + 1)
            if pos == -1:
                return False
            last_pos = pos
        return True

    def _calculate_match_quality(self, text: str, query: str) -> float:
        """
        Calculate match quality with hierarchical scoring:
        1. Exact phrase match (10.0) - highest priority
        2. All words present, correct order (8.0) 
        3. All words present, wrong order (6.0)
        4. Substring/partial word matches (4.0-6.0)
        5. Partial word match (2.0-4.0)
        6. Poor match (0.0-2.0)
        """
        # Normalize whitespace
        text = ' '.join(text.split())
        query = ' '.join(query.split())
        
        if not query or not text:
            return 0.0
            
        # 1. EXACT PHRASE MATCH (highest priority)
        if query in text:
            return 10.0
            
        # Split into words for detailed analysis
        query_words = query.split()
        text_words = text.split()
        
        if len(query_words) == 1:
            # Single word query
            single_word = query_words[0]
            if single_word in text_words:
                return 8.0  # Exact word match
            elif any(single_word in word for word in text_words):
                return 6.0  # Substring match in some word
            else:
                return 0.0  # Not found
        
        # Multi-word query analysis
        exact_words_found = []
        substring_matches = []
        
        for query_word in query_words:
            # Check exact word match
            if query_word in text_words:
                exact_words_found.append(query_word)
            else:
                # Check substring matches
                for text_word in text_words:
                    if query_word in text_word:
                        substring_matches.append((query_word, text_word))
                        break
        
        exact_count = len(exact_words_found)
        substring_count = len(substring_matches)
        total_words = len(query_words)
        total_found = exact_count + substring_count
        
        # 2. ALL WORDS FOUND (exact or substring)
        if total_found == total_words:
            if exact_count == total_words:
                # All exact matches - check order
                if self._check_word_order_simple(text, query_words):
                    return 8.0  # All words exact, correct order
                else:
                    return 6.0  # All words exact, wrong order
            else:
                # Mix of exact and substring matches
                exact_ratio = exact_count / total_words
                if exact_ratio >= 0.5:  # Majority are exact matches
                    return 5.0 + exact_ratio  # 5.5 to 6.0
                else:
                    return 4.0 + exact_ratio  # 4.0 to 4.5
        
        # 3. PARTIAL MATCHES
        elif total_found > 0:
            match_ratio = total_found / total_words
            exact_ratio = exact_count / total_words if total_words > 0 else 0
            
            # Bonus for exact word matches
            base_score = match_ratio * 4.0  # Base: 0-4.0 based on coverage
            exact_bonus = exact_ratio * 1.0  # Extra 0-1.0 for exact matches
            
            return min(5.0, base_score + exact_bonus)
        
        # 4. CHECK FOR CONCATENATED MATCHES
        # Handle "vet cay" → "vetcay" case
        concatenated_query = ''.join(query_words)
        for text_word in text_words:
            if concatenated_query in text_word:
                return 7.0  # High score for concatenated match
            elif len(concatenated_query) > 3:  # Only for longer queries
                # Check partial concatenated match
                similarity = self._calculate_substring_similarity(concatenated_query, text_word)
                if similarity > 0.7:  # 70% similarity threshold
                    return 3.0 + similarity  # 3.7 to 4.0
        
        # 5. NO SIGNIFICANT MATCHES
        return 0.0
    
    def _calculate_substring_similarity(self, query_concat: str, text_word: str) -> float:
        """
        Calculate similarity between concatenated query and text word
        Handles cases like "vetcay" vs "vetca" (missing chars)
        """
        if not query_concat or not text_word:
            return 0.0
            
        # Simple similarity: longest common substring ratio
        longer = query_concat if len(query_concat) > len(text_word) else text_word
        shorter = text_word if longer == query_concat else query_concat
        
        if shorter in longer:
            return len(shorter) / len(longer)
        
        # Find longest common substring
        max_length = 0
        for i in range(len(shorter)):
            for j in range(i + 1, len(shorter) + 1):
                substr = shorter[i:j]
                if substr in longer and len(substr) > max_length:
                    max_length = len(substr)
        
        return max_length / len(longer) if max_length > 0 else 0.0
    
    def _check_word_order_simple(self, text: str, words: list) -> bool:
        """
        Fast check if words appear in the same order in text as in query
        """
        if not words:
            return True
            
        last_pos = -1
        for word in words:
            pos = text.find(word, last_pos + 1)
            if pos == -1:
                return False
            last_pos = pos
        return True

    def _normalize_scores(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize scores to 0-1 range using min-max normalization
        Also adds normalized_score field while keeping original score
        """
        if not results:
            return results
        
        # Extract scores
        scores = [result['score'] for result in results]
        
        if not scores:
            return results
            
        # Find min and max scores
        min_score = min(scores)
        max_score = max(scores)
        
        # Avoid division by zero
        score_range = max_score - min_score
        if score_range == 0:
            # All scores are the same, assign 1.0 to all
            for result in results:
                result['normalized_score'] = 1.0
            return results
        
        # Apply min-max normalization
        for result in results:
            original_score = result['score']
            normalized = (original_score - min_score) / score_range
            result['normalized_score'] = round(normalized, 4)  # Keep 4 decimal places
            
            # Keep original score for debugging/analysis
            result['original_score'] = original_score
            
        return results
    
    def _normalize_scores_advanced(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Advanced score normalization with different strategies
        Maps hierarchical scores to meaningful 0-1 ranges
        """
        if not results:
            return results
            
        for result in results:
            original_score = result['score']
            
            # Map score ranges to 0-1 based on quality tiers
            if original_score >= 10.0:
                # Exact phrase matches: 0.95-1.0
                normalized = 0.95 + min(0.05, (original_score - 10.0) * 0.1)
            elif original_score >= 8.0:
                # All words correct order: 0.85-0.95  
                normalized = 0.85 + ((original_score - 8.0) / 2.0) * 0.1
            elif original_score >= 7.0:
                # Concatenated matches: 0.75-0.85
                normalized = 0.75 + ((original_score - 7.0) / 1.0) * 0.1
            elif original_score >= 6.0:
                # All words wrong order / substring: 0.65-0.75
                normalized = 0.65 + ((original_score - 6.0) / 1.0) * 0.1
            elif original_score >= 4.0:
                # Mixed/partial matches: 0.4-0.65
                normalized = 0.4 + ((original_score - 4.0) / 2.0) * 0.25
            elif original_score >= 2.0:
                # Poor matches: 0.15-0.4
                normalized = 0.15 + ((original_score - 2.0) / 2.0) * 0.25
            else:
                # Very poor matches: 0.0-0.15
                normalized = min(0.15, original_score / 2.0 * 0.15)
            
            result['normalized_score'] = round(min(1.0, max(0.0, normalized)), 4)
            result['original_score'] = original_score
            
        return results

    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate results from multiple datasets.
        Keep the result with highest score for each video_name + frame_index combination.
        Also merge information from both datasets when possible.
        """
        if not results:
            return results
        
        # Group by unique video + frame combination
        unique_results = {}
        
        for result in results:
            video_name = result.get('video_name', '')
            frame_index = result.get('frame_index', 0)
            
            # Create unique key
            unique_key = f"{video_name}_{frame_index}"
            
            if unique_key not in unique_results:
                # First occurrence - add it
                unique_results[unique_key] = result.copy()
                unique_results[unique_key]['datasets_found'] = [result.get('dataset_type', 'unknown')]
            else:
                # Duplicate found - keep higher score result
                existing_result = unique_results[unique_key]
                current_score = result.get('score', 0)
                existing_score = existing_result.get('score', 0)
                
                # Track which datasets contain this result
                existing_datasets = existing_result.get('datasets_found', [])
                current_dataset = result.get('dataset_type', 'unknown')
                if current_dataset not in existing_datasets:
                    existing_datasets.append(current_dataset)
                
                if current_score > existing_score:
                    # Replace with higher score result
                    unique_results[unique_key] = result.copy()
                    unique_results[unique_key]['datasets_found'] = existing_datasets
                    unique_results[unique_key]['alternative_text'] = existing_result.get('text', '')
                    unique_results[unique_key]['score_difference'] = current_score - existing_score
                else:
                    # Keep existing, but store alternative info
                    existing_result['datasets_found'] = existing_datasets
                    existing_result['alternative_text'] = result.get('text', '')
                    existing_result['score_difference'] = existing_score - current_score
        
        # Convert back to list and sort by score
        deduplicated = list(unique_results.values())
        deduplicated.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # Log deduplication stats
        original_count = len(results)
        final_count = len(deduplicated)
        if original_count != final_count:
            logger.info(f"🔄 Deduplication: {original_count} → {final_count} results ({original_count - final_count} duplicates removed)")
        
        return deduplicated
def remove_vietnamese_accents(text: str) -> str:
    """
    Remove Vietnamese diacritics/accents to match processed dataset format
    """
    import unicodedata
    
    # Vietnamese accent mapping
    vietnamese_map = {
        'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
        'đ': 'd',
        # Uppercase versions
        'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
        'Ă': 'A', 'Ằ': 'A', 'Ắ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
        'Â': 'A', 'Ầ': 'A', 'Ấ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
        'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
        'Ê': 'E', 'Ề': 'E', 'Ế': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
        'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
        'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
        'Ô': 'O', 'Ồ': 'O', 'Ố': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
        'Ơ': 'O', 'Ờ': 'O', 'Ớ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
        'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
        'Ư': 'U', 'Ừ': 'U', 'Ứ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
        'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y',
        'Đ': 'D'
    }
    
    # Apply mapping
    result = ""
    for char in text:
        if char in vietnamese_map:
            result += vietnamese_map[char]
        else:
            result += char
    
    return result


# Create singleton instance
meili_search_service = MeiliSearchService.get_instance(
    host=MEILISEARCH_HOST,
    port=MEILISEARCH_PORT,
    api_key=MEILISEARCH_API_KEY
)
