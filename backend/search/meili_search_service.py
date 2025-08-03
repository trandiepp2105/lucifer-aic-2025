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
        # self.viet_ocr_index = self.index_names[0]  # First dataset
        # self.parseq_ocr_index = self.index_names[1]  # Second dataset
        
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
                                'typo',
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
                                    'oneTypo': 2,
                                    'twoTypos': 3
                                }
                            }
                        }
                        
                        task = index.update_settings(settings)
                        logger.info(f"Index {index_name} settings updated, task: {task.task_uid if hasattr(task, 'task_uid') else 'N/A'}")
                    except Exception as settings_e:
                        logger.warning(f"Failed to update settings for {index_name}: {settings_e}")
                
                logger.info(f"Index {index_name} ready")
                
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
                        "id": f"{index_name}_{video_name}_{frame_index}",
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
                
                # Only log at DEBUG level to reduce spam
                logger.debug(f"Indexed {len(documents)} documents for {video_name} in {index_name}")
                logger.debug(f"Meilisearch task ID: {task.task_uid if hasattr(task, 'task_uid') else 'N/A'}")
                
            except Exception as e:
                logger.error(f"Error indexing {video_name} in {index_name}: {e}")
                raise


    # def search_ocr(self, query: str, size: int = 1000) -> List[Dict[str, Any]]:
    #     """
    #     Fast OCR search with optimized ranking.
    #     Uses Meilisearch built-in ranking + lightweight custom scoring.
    #     Auto-normalizes Vietnamese text to match processed dataset.
        
    #     Args:
    #         query: Search query
    #         size: Maximum number of results
    #         normalize_method: 'minmax' for min-max normalization, 'advanced' for tier-based
    #     """
        
    #     # Normalize query to match dataset format (Vietnamese without accents)
    #     normalized_query = remove_vietnamese_accents(query.strip())
        
    #     try:
    #         search_result = []
            
    #         # Search with optimized settings for speed
    #         for index_name in self.index_names:
    #             try:
    #                 index = self.client.get_index(index_name)
                    
    #                 # Use Meilisearch multi-search for better performance
    #                 search_params = {
    #                     'limit': size,  
    #                     'attributesToRetrieve': ['*'],
    #                     'showRankingScore': True,
    #                     'matchingStrategy': 'last',  # Require all words (better for exact match)
    #                 }
                    
    #                 meili_response = index.search(normalized_query, search_params)
    #                 search_result.extend(meili_response['hits'])
    #             except Exception as e:
    #                 print(f"Error searching index {index_name}: {e}")
    #                 continue
            
    #         # Fast sorting by score
    #         search_result.sort(key=lambda x: x['_rankingScore'], reverse=True)
            
    #         # Deduplicate by video_name + frame_index (keep highest score)
    #         deduplicated_results = self._deduplicate_results(search_result)
            
    #         # Return top results after deduplication
    #         final_results = deduplicated_results[:size]
            
            
    #         return final_results
            
    #     except Exception as e:
    #         print(f"Search error: {e}")
    #         return []


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
        
        # Normalize query to match dataset format (Vietnamese without accents)
        normalized_query = remove_vietnamese_accents(query.strip())
        
        try:
            all_results = []
            
            # Search with optimized settings for speed
            for index_name in self.index_names:
                try:
                    index = self.client.get_index(index_name)
                    
                    # Use Meilisearch multi-search for better performance
                    search_params = {
                        'limit': size * 2,  # Request only what we need per index
                        'attributesToRetrieve': ['*'],
                        'showRankingScore': True,
                        'matchingStrategy': 'last',  # Require all words (better for exact match)
                    }
                    
                    # Use normalized query for search
                    
                    search_result = index.search(normalized_query, search_params)
                    
                    # Light-weight processing for speed
                    for hit in search_result['hits']:
                        text = hit.get('text', '').lower().strip()
                        query_lower = normalized_query.lower().strip()
                        
                        # Meilisearch base score (0-1)
                        meili_score = hit.get('_rankingScore', 0.5)
                        
                        # Hierarchical scoring based on match quality (0-1)
                        custom_score = self._calculate_match_quality(text, query_lower)
                        
                        # Final score: Average of custom score and Meilisearch score
                        final_score = (custom_score + meili_score) / 2.0
                        
                        result = {
                            'video_name': hit.get('video_name', ''),
                            'frame_index': hit.get('frame_index', 0),
                            # 'text': hit.get('text', ''),
                            # 'dataset_type': hit.get('dataset_type', index_name),
                            '_rankingScore': final_score,
                        }
                        all_results.append(result)
                except Exception as e:
                    logger.error(f"Error searching index {index_name}: {e}")
                    continue
            # Fast sorting by score
            all_results.sort(key=lambda x: x['_rankingScore'], reverse=True)
            
            # Deduplicate by video_name + frame_index (keep highest score)
            deduplicated_results = self._deduplicate_results(all_results)
            
            # Return top results after deduplication
            final_results = deduplicated_results[:size]
            
            
            
            return final_results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
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
        Calculate match quality with hierarchical scoring (normalized to 0-1):
        1. Exact phrase match (1.0) - highest priority
        2. All words present, correct order (0.8) 
        3. All words present, wrong order (0.6)
        4. Substring/partial word matches (0.4-0.6)
        5. Partial word match (0.2-0.4)
        6. Poor match (0.0-0.2)
        """
        # Normalize whitespace
        text = ' '.join(text.split())
        query = ' '.join(query.split())
        
        if not query or not text:
            return 0.0
            
        # 1. EXACT PHRASE MATCH (highest priority)
        if query in text:
            return 1.0
            
        # Split into words for detailed analysis
        query_words = query.split()
        text_words = text.split()
        
        if len(query_words) == 1:
            # Single word query
            single_word = query_words[0]
            if single_word in text_words:
                return 0.8  # Exact word match
            elif any(single_word in word for word in text_words):
                return 0.6  # Substring match in some word
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
                    return 0.8  # All words exact, correct order
                else:
                    return 0.6  # All words exact, wrong order
            else:
                # Mix of exact and substring matches
                exact_ratio = exact_count / total_words
                if exact_ratio >= 0.5:  # Majority are exact matches
                    return 0.5 + (exact_ratio * 0.1)  # 0.55 to 0.6
                else:
                    return 0.4 + (exact_ratio * 0.1)  # 0.4 to 0.45
        
        # 3. PARTIAL MATCHES
        elif total_found > 0:
            match_ratio = total_found / total_words
            exact_ratio = exact_count / total_words if total_words > 0 else 0
            
            # Bonus for exact word matches
            base_score = match_ratio * 0.4  # Base: 0-0.4 based on coverage
            exact_bonus = exact_ratio * 0.1  # Extra 0-0.1 for exact matches
            
            return min(0.5, base_score + exact_bonus)
        
        # 4. CHECK FOR CONCATENATED MATCHES
        # Handle "vet cay" → "vetcay" case
        concatenated_query = ''.join(query_words)
        for text_word in text_words:
            if concatenated_query in text_word:
                return 0.7  # High score for concatenated match
            elif len(concatenated_query) > 3:  # Only for longer queries
                # Check partial concatenated match
                similarity = self._calculate_substring_similarity(concatenated_query, text_word)
                if similarity > 0.7:  # 70% similarity threshold
                    return 0.3 + (similarity * 0.1)  # 0.37 to 0.4
        
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
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate results from multiple datasets.
        Keep the result with highest score for each video_name + frame_index combination.
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
                unique_results[unique_key] = result
            else:
                # Duplicate found - keep higher score result
                current_score = result.get('_rankingScore', 0)
                existing_score = unique_results[unique_key].get('_rankingScore', 0)
                
                if current_score > existing_score:
                    # Replace with higher score result
                    unique_results[unique_key] = result
        
        # Convert back to list and sort by score
        deduplicated = list(unique_results.values())
        deduplicated.sort(key=lambda x: x.get('_rankingScore', 0), reverse=True)

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
