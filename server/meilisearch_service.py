import json
import os
import threading
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import meilisearch
from rapidfuzz import fuzz
import time
from tqdm import tqdm


class Score2Text:
    def __init__(self, w_partial=1, w_ngrams=1, w_token=1):
        self.w_partial = w_partial
        self.w_ngrams = w_ngrams
        self.w_token = w_token

    def custom_partial_ratio(self, q_no_space, d_no_space):
        len_q = len(q_no_space)
        len_d = len(d_no_space)
        if len_q == 0:
            return 0
        if len_q >= len_d:
            return fuzz.ratio(q_no_space, d_no_space)/100
        else:
            return fuzz.partial_ratio(q_no_space, d_no_space)/100

    @staticmethod
    def generate_ngrams(tokens, n_values=(1,)):
        results = {}
        for n in n_values:
            ngrams = [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]
            results[n] = ngrams
        return results
        
    def custom_ngrams_ratio(self, q_split, d_split):
        len_q = len(q_split)
        q = ' '.join(q_split)
        if len_q == 0:
            return 0
        if len_q > 1:
            n_values = (len_q - 1, len_q)
        else:
            n_values = (len_q, )
        ngrams = self.generate_ngrams(d_split, n_values)
        best = 0
        for ngram in ngrams.values():
            for text in ngram:
                score = fuzz.ratio(q, text)
                best = max(best, score)
        return best/100

    def custom_token_ratio(self, q, d):
        return fuzz.token_set_ratio(q, d)/100
            
    def w_score(self, q, d):
        q_split = q.split()
        d_split = d.split()
        q_no_space = ''.join(q_split)
        d_no_space = ''.join(d_split)
        partial = self.custom_partial_ratio(q_no_space, d_no_space)
        ngrams = self.custom_ngrams_ratio(q_split, d_split)
        token = self.custom_token_ratio(q, d)
        return (self.w_partial*partial + self.w_ngrams*ngrams + self.w_token*token)/(self.w_partial + self.w_ngrams + self.w_token)

scoring = Score2Text()

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
    
    def __init__(self, host: str = None, port: int = None, api_key: str = None, ocr_datasets = None, subscript_datasets = None, limit_search: int = 500):
        # Chỉ khởi tạo nếu chưa được khởi tạo (singleton check)
        if hasattr(self, '_initialized'):
            return
        
        if meilisearch is None:
            raise ImportError("Meilisearch not installed. Run: pip install meilisearch")
        
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
        self.ocr_datasets = ocr_datasets if ocr_datasets is not None else []
        self.subscript_datasets = subscript_datasets if subscript_datasets is not None else []
        self.ocr_index_names = [index_name for _, index_name in self.ocr_datasets]
        self.subscript_index_names = [index_name for _, index_name in self.subscript_datasets]
        self.limit_search = limit_search 
        self._initialized = True
    
    @classmethod
    def get_instance(cls, host: str = None, port: int = None, api_key: str = None, ocr_datasets = None, subscript_datasets = None, limit_search: int = 500):
        """
        Get singleton instance (alternative way to access)
        """
        return cls(host, port, api_key, ocr_datasets, subscript_datasets, limit_search)

    
    def create_indices(self):
        """
        Tạo indices với cấu hình tối ưu cho OCR search
        """
        try:
            for index_name in self.ocr_index_names + self.subscript_index_names:
                print(f"Creating/updating index: {index_name}")
                
                # Try to get existing index first
                index = None
                try:
                    index = self.client.get_index(index_name)
                    print(f"Index {index_name} already exists")
                except Exception:
                    # Index doesn't exist, create it
                    try:
                        task = self.client.create_index(index_name, {'primaryKey': 'id'})
                        print(f"Created index {index_name}, task: {task.task_uid if hasattr(task, 'task_uid') else 'N/A'}")                        
                        # Wait a bit for index to be ready
                        import time
                        time.sleep(1)
                        
                        # Now get the created index
                        index = self.client.get_index(index_name)
                    except Exception as create_e:
                        print(f"Failed to create index {index_name}: {create_e}")
                        continue
                
                # Configure search settings if we have the index
                if index:
                    try:
                        settings = {
                            'searchableAttributes': ['text'],
                            'displayedAttributes': ['video_name', 'frame_index', 'text'],
                            'filterableAttributes': ['video_name', 'frame_index'],
                            'sortableAttributes': [],
                            'rankingRules': [
                                'typo',
                                'proximity',
                                'words',
                                'exactness',
                                'attribute',
                                'sort', 
                            ],
                            'pagination': {
                                'maxTotalHits': 5000  
                            },
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
                        print(f"Index {index_name} settings updated, task: {task.task_uid if hasattr(task, 'task_uid') else 'N/A'}")
                    except Exception as settings_e:
                        print(f"Failed to update settings for {index_name}: {settings_e}")
                
                print(f"Index {index_name} ready")
        except Exception as e:
            print(f"Error in create_indices: {e}")
            raise

    def index_all_dataset(self):
        try:
            total_start = time.time()
            overall_success = 0
            overall_failed = 0
            
            BATCH_FILE_COUNT = 100 

            for data_path, index_name in self.ocr_datasets + self.subscript_datasets:
                if not os.path.exists(data_path):
                    print(f"Bỏ qua {index_name}: Thư mục {data_path} không tồn tại")
                    continue

                print(f"\nBắt đầu index {index_name}...")
                start_time = time.time()
                successful_files = 0
                failed_files = 0

                json_files = list(Path(data_path).rglob('*.json'))
                if not json_files:
                    print(f"Không tìm thấy file JSON nào trong {data_path}")
                    continue

                try:
                    index = self.client.get_index(index_name)
                except Exception as e:
                    print(f"  ✗ Không thể lấy index {index_name}. Bỏ qua bộ dữ liệu này. Lỗi: {e}")
                    continue
                
                document_batch = []

                for i, json_file in enumerate(tqdm(json_files, desc=f"Đang xử lý {index_name}", unit="file")):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        video_name = Path(json_file).stem
                        
                        for frame_index, frame_text in data.items():
                            if frame_text.strip(): # Chỉ index nếu có text
                                doc = {
                                    "id": f"{index_name}_{video_name}_{frame_index}",
                                    "video_name": video_name,
                                    "frame_index": int(frame_index),
                                    "text": frame_text.strip(),
                                    "dataset_type": index_name
                                }
                                document_batch.append(doc)
                        successful_files += 1

                    except Exception as e:
                        # Ghi lại lỗi của từng file mà không làm dừng toàn bộ quá trình
                        tqdm.write(f"  ✗ Lỗi khi đọc hoặc xử lý file {json_file}: {e}")
                        failed_files += 1

                    # Điều kiện để gửi batch đi:
                    # 1. Đã xử lý đủ số file trong một batch (BATCH_FILE_COUNT)
                    # 2. Hoặc đã xử lý đến file cuối cùng của danh sách
                    if (i + 1) % BATCH_FILE_COUNT == 0 or (i + 1) == len(json_files):
                        if document_batch: # Chỉ gửi nếu batch không rỗng
                            try:
                                # Gửi toàn bộ batch đã gom được đến Meilisearch trong 1 lần gọi
                                task = index.add_documents(document_batch)
                                document_batch = [] # Reset lại batch để chuẩn bị cho lô tiếp theo
                            except Exception as e:
                                tqdm.write(f"  ✗ Lỗi khi index lô dữ liệu kết thúc bằng file {json_file}: {e}")
                
                elapsed = time.time() - start_time
                print(f"  ✓ Hoàn tất {index_name}: Thành công: {successful_files}, Thất bại: {failed_files} (trong {elapsed:.1f} giây)")
                
                overall_success += successful_files
                overall_failed += failed_files

            total_elapsed = time.time() - total_start
            print(f"\n✓ Đã index xong tất cả bộ dữ liệu: Thành công: {overall_success}, Thất bại: {overall_failed} (Tổng thời gian: {total_elapsed:.1f} giây)")

        except Exception as e:
            print(f"Một lỗi nghiêm trọng đã xảy ra trong quá trình index: {e}")

    def expansion_query(self, query: str) -> List[str]:
        words = query.strip().split()
        n = len(words)
        if n == 0:
            return []

        all_query = set()
        # query ≥2 từ → thêm bigram liên tiếp
        if n >= 2:
            for i in range(n - 1):
                all_query.add("".join(words[i:i+2]))

        # query =3 → thêm trigram
        if n == 3:
            all_query.add("".join(words))

        list_query = [query]
        list_query.extend(list(all_query))
        return list_query
    
    def search_ocr(self, query: str, size: int = 1000) -> List[Dict[str, Any]]:
        """
        Fast OCR search với multi-search và re-ranking được tối ưu bằng fastfuzz.
        """
        normalized_queries = [remove_vietnamese_accents(expanded_query).lower() for expanded_query in self.expansion_query(query)]
        if not normalized_queries:
            return []
        try:
            # 1. Chuẩn bị danh sách các truy vấn cho multi-search
            # Chỉ thực hiện nếu có index_names được cấu hình
            if not self.ocr_index_names:
                return []
            queries = []
            for index_name in self.ocr_index_names:
                for normalized_query in normalized_queries:
                    queries.append(
                        {
                            "indexUid": index_name,
                            "q": normalized_query,
                            "limit": self.limit_search,
                            "attributesToRetrieve": ['*'],
                            'showRankingScore': False,
                            'matchingStrategy': 'last',
                        }
                    )
            # 2. Gửi một yêu cầu multi-search duy nhất đến Meilisearch
            # Đảm bảo format đúng cho Meilisearch 1.6.2
            multi_search_response = self.client.http.post("multi-search", {"queries": queries})
            # 3. Tập hợp kết quả vào một dict để không bị trùng lặp
            search_result = {}
            for response in multi_search_response['results']:
                for doc in response['hits']:
                    # dùng tuple làm key duy nhất
                    key = (doc['video_name'], doc['frame_index'])
                    if key not in search_result:
                        search_result[key] = doc
            search_result_list = list(search_result.values())
            # 4. Re-ranking hiệu suất cao với fastfuzz
            for result in search_result_list:
                text = result.get('text', '').strip()
                custom_score = self._scoring_matching(text, normalized_queries[0])
                # custom_score = self._calculate_match_quality_fastfuzz(text, normalized_queries[0])
                result['_rankingScore'] = custom_score
    
            # Sắp xếp lại dựa trên điểm số cuối cùng
            search_result_list.sort(key=lambda x: x['_rankingScore'], reverse=True)
            return search_result_list[:size] 
        except Exception as e:
            # Lỗi từ multi_search sẽ được bắt ở đây
            print(f"Multi-search ocr error: {e}")
            return []
    
    def search_subscript(self, query: str, size: int = 1000) -> List[Dict[str, Any]]:
        normalized_queries = [expanded_query.lower() for expanded_query in self.expansion_query(query)]
        if not normalized_queries:
            return []
        try:
            # 1. Chuẩn bị danh sách các truy vấn cho multi-search
            # Chỉ thực hiện nếu có index_names được cấu hình
            if not self.subscript_index_names:
                return []
            queries = []
            for index_name in self.subscript_index_names:
                for normalized_query in normalized_queries:
                    queries.append(
                        {
                            "indexUid": index_name,
                            "q": normalized_query,
                            "limit": self.limit_search,
                            "attributesToRetrieve": ['*'],
                            'showRankingScore': False,
                            'matchingStrategy': 'last',
                        }
                    )
            # 2. Gửi một yêu cầu multi-search duy nhất đến Meilisearch
            # Đảm bảo format đúng cho Meilisearch 1.6.2
            multi_search_response = self.client.http.post("multi-search", {"queries": queries})
            # 3. Tập hợp kết quả vào một dict để không bị trùng lặp
            search_result = {}
            for response in multi_search_response['results']:
                for doc in response['hits']:
                    # dùng tuple làm key duy nhất
                    key = (doc['video_name'], doc['frame_index'])
                    if key not in search_result:
                        search_result[key] = doc
            search_result_list = list(search_result.values())
            # 4. Re-ranking hiệu suất cao với fastfuzz
            for result in search_result_list:
                text = result.get('text', '').strip()
                custom_score = self._scoring_matching(text, normalized_queries[0])
                # custom_score = self._calculate_match_quality_fastfuzz(text, normalized_queries[0])
                result['_rankingScore'] = custom_score
    
            # Sắp xếp lại dựa trên điểm số cuối cùng
            search_result_list.sort(key=lambda x: x['_rankingScore'], reverse=True)
            return search_result_list[:size] 
        except Exception as e:
            # Lỗi từ multi_search sẽ được bắt ở đây
            print(f"Multi-search ocr error: {e}")
            return []


    def _scoring_matching(self, text, query):
        text_norm = ' '.join(text.lower().split())
        if not query or not text_norm:
            return 0.0
        if query in text_norm:
            return 1.0
        return scoring.w_score(q=query, d=text_norm)
            

    def _calculate_match_quality_fastfuzz(self, text: str, query: str) -> float:
        """
        Tính toán chất lượng khớp nối bằng fastfuzz để đạt hiệu suất cao.
        Hàm này thay thế hoàn toàn cho hàm _calculate_match_quality cũ.

        Returns:
            Một điểm số trong khoảng [0.0, 1.0].
        """
        # Chuẩn hóa đầu vào
        text_norm = ' '.join(text.lower().split())
        
        if not query or not text_norm:
            return 0.0
            
        # 1. Kiểm tra khớp chính xác (trường hợp nhanh nhất và phổ biến)
        if query in text_norm:
            return 1.0
            
        # 2. Sử dụng fuzz.WRatio làm thước đo chính.
        # WRatio rất mạnh mẽ, nó tự động xử lý các trường hợp khác biệt về thứ tự từ,
        # khớp một phần, và các vấn đề phức tạp khác. Nó cho điểm từ 0-100.
        main_score = fuzz.WRatio(query, text_norm)
        
        # 3. Xử lý trường hợp đặc biệt: từ ghép không có khoảng trắng (ví dụ: "vet cay" -> "vetcay")
        # Trường hợp này WRatio có thể không xử lý tốt.
        concat_score = 0
        if ' ' in query: # Chỉ xử lý khi query có nhiều từ
            concatenated_query = "".join(query.split())
            # Tìm kiếm chuỗi ghép này bên trong văn bản đã loại bỏ khoảng trắng
            concat_score = fuzz.WRatio(concatenated_query, text_norm)

        # 4. Lấy điểm cao nhất từ hai phương pháp
        final_score = max(main_score*1, concat_score*0.9)
        
        # 5. Chuẩn hóa điểm số về khoảng [0.0, 1.0]
        return final_score / 100.0