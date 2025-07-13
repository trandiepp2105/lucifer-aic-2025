import os
import json
import glob
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

try:
    from tqdm import tqdm
except ImportError:
    # Fallback nếu tqdm chưa được cài
    class tqdm:
        def __init__(self, iterable=None, total=None, desc=None, **kwargs):
            self.iterable = iterable
            self.total = total or (len(iterable) if iterable else 0)
            self.desc = desc
            self.n = 0
            
        def __iter__(self):
            if self.iterable:
                for item in self.iterable:
                    yield item
                    self.update(1)
            
        def __enter__(self):
            return self
            
        def __exit__(self, *args):
            pass
            
        def update(self, n=1):
            self.n += n
            if self.total > 0:
                percent = (self.n / self.total) * 100
                print(f"\r{self.desc}: {percent:.1f}% ({self.n}/{self.total})", end="", flush=True)
        
        def close(self):
            print()  # New line after progress


class Command(BaseCommand):
    help = 'Setup Meilisearch indices and index OCR datasets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset indices before indexing',
        )
        parser.add_argument(
            '--dataset',
            type=str,
            help='Index specific dataset (viet_ocr_index or parseq_ocr_index)',
        )
        parser.add_argument(
            '--skip-warmup',
            action='store_true',
            help='Skip cache warmup step',
        )

    def handle(self, *args, **options):
        """Main entry point for the command"""
        try:
            # Import from current app
            from search.meili_search_service import MeiliSearchService
            from search.config import LIST_DATASET
            
            # Get service instance
            service = MeiliSearchService.get_instance()
            
            self.stdout.write("Setting up Meilisearch...")
            
            # Run setup (no async needed)
            self._setup(service, options)
            
        except Exception as e:
            self.stderr.write(f"Error: {e}")
            raise

    def _setup(self, service, options):
        """Setup method"""
        try:
            # Step 1: Create indices
            self.stdout.write("📝 Creating/updating indices...")
            service.create_indices()
            
            # Step 2: Index datasets
            if options['dataset']:
                # Index specific dataset
                self._index_specific_dataset(service, options['dataset'])
            else:
                # Index all datasets
                self._index_all_datasets(service, options['reset'])
            
            # Step 3: Show stats
            self._show_stats(service)
            
            # Step 4: Pre-warm cache
            if not options.get('skip_warmup', False):
                self._warmup_cache(service)
            else:
                self.stdout.write("Skipping cache warmup")
            
            self.stdout.write("Meilisearch setup completed!")
            
        except Exception as e:
            self.stderr.write(f"Setup failed: {e}")
            raise

    def _index_all_datasets(self, service, reset=False):
        """Index all datasets from config"""
        from search.config import LIST_DATASET
        
        for dataset_path, index_name in LIST_DATASET:
            self.stdout.write(f"Processing dataset: {index_name}")
            
            # Get absolute path
            if dataset_path.startswith('/backend/'):
                # Docker path
                abs_path = dataset_path
            else:
                # Local path - relative to backend directory
                abs_path = os.path.join(settings.BASE_DIR, dataset_path.lstrip('/'))
            
            if not os.path.exists(abs_path):
                self.stderr.write(f"Dataset path not found: {abs_path}")
                continue
            
            # Find all JSON files
            json_files = glob.glob(os.path.join(abs_path, "*.json"))
            
            if not json_files:
                self.stderr.write(f"No JSON files found in: {abs_path}")
                continue
            
            self.stdout.write(f"Found {len(json_files)} JSON files")
            
            # Index each file with progress bar
            successful = 0
            failed = 0
            
            with tqdm(json_files, desc=f"Indexing {index_name}", unit="files") as pbar:
                for json_file in pbar:
                    try:
                        service.index_ocr_data(json_file, index_name)
                        successful += 1
                        pbar.set_postfix({"OK": successful, "FAIL": failed})
                    except Exception as e:
                        failed += 1
                        video_name = Path(json_file).stem
                        pbar.set_postfix({"OK": successful, "FAIL": failed})
                        # Only log severe errors, not every failure
                        if failed <= 3:  # Show first 3 errors only
                            self.stderr.write(f"\n   Failed to index {video_name}: {e}")
            
            self.stdout.write(f"Completed {index_name}: {successful} successful, {failed} failed")

    def _index_specific_dataset(self, service, dataset_name):
        """Index a specific dataset"""
        from search.config import LIST_DATASET
        
        # Find dataset config
        dataset_config = None
        for dataset_path, index_name in LIST_DATASET:
            if index_name == dataset_name:
                dataset_config = (dataset_path, index_name)
                break
        
        if not dataset_config:
            available = [name for _, name in LIST_DATASET]
            self.stderr.write(f"Dataset '{dataset_name}' not found. Available: {available}")
            return
        
        dataset_path, index_name = dataset_config
        
        # Get absolute path
        if dataset_path.startswith('/backend/'):
            abs_path = dataset_path
        else:
            abs_path = os.path.join(settings.BASE_DIR, dataset_path.lstrip('/'))
        
        if not os.path.exists(abs_path):
            self.stderr.write(f"Dataset path not found: {abs_path}")
            return
        
        # Find all JSON files
        json_files = glob.glob(os.path.join(abs_path, "*.json"))
        
        if not json_files:
            self.stderr.write(f"No JSON files found in: {abs_path}")
            return
        
        self.stdout.write(f"Processing dataset: {index_name}")
        self.stdout.write(f"Found {len(json_files)} JSON files")
        
        # Index each file with progress bar
        successful = 0
        failed = 0
        
        with tqdm(json_files, desc=f"Indexing {index_name}", unit="files") as pbar:
            for json_file in pbar:
                try:
                    service.index_ocr_data(json_file, index_name)
                    successful += 1
                    pbar.set_postfix({"OK": successful, "FAIL": failed})
                except Exception as e:
                    failed += 1
                    video_name = Path(json_file).stem
                    pbar.set_postfix({"OK": successful, "FAIL": failed})
                    # Only log severe errors, not every failure
                    if failed <= 3:  # Show first 3 errors only
                        self.stderr.write(f"\n   Failed to index {video_name}: {e}")
        
        self.stdout.write(f"Completed {index_name}: {successful} successful, {failed} failed")

    def _show_stats(self, service):
        """Show indexing statistics"""
        try:
            stats = service.get_index_stats()
            
            self.stdout.write("\nIndex Statistics:")
            for index_name, index_stats in stats.items():
                if 'error' in index_stats:
                    self.stderr.write(f"   {index_name}: {index_stats['error']}")
                else:
                    doc_count = index_stats.get('numberOfDocuments', 0)
                    is_indexing = index_stats.get('isIndexing', False)
                    status = "Indexing..." if is_indexing else "Ready"
                    self.stdout.write(f"   {index_name}: {doc_count:,} documents {status}")
            
        except Exception as e:
            self.stderr.write(f"Could not get statistics: {e}")

    def _warmup_cache(self, service):
        """Pre-warm Meilisearch cache with common queries"""
        try:
            self.stdout.write("\nPre-warming Meilisearch cache...")
            
            # Common warmup queries - optimized for Vietnamese without diacritics + English
            warmup_queries = [
                "duong mot chieu", "cam di lai", "cam dung do", "loi ra", "loi vao", 
                "loi di bo", "khu vuc cam", "khu dan cu", "vung nguy hiem", "truong hoc", 
                "cong truong dang thi cong", "chot kiem dich", "khu cach ly", "benh vien", 
                "tru so", "uy ban nhan dan", "so giao thong van tai", "bo cong an", "bo y te", 
                "bo quoc phong", "hoi chu thap do", "trung tam y te", "dai truyen hinh viet nam", 
                "dai tieng noi viet nam", "so thong tin va truyen thong", "truong tieu hoc", 
                "truong trung hoc co so", "truong trung hoc pho thong", "dai hoc quoc gia", 
                "hoc vien an ninh", "ben xe mien dong", "ben xe nuoc ngam", "san bay tan son nhat", 
                "san bay noi bai", "cong vien le van tam", "cong vien thong nhat", "nha van hoa", 
                "hoi dong nhan dan", "thanh uy", "khu pho van hoa", "ap van hoa", "xa an toan", 
                "moi truong xanh sach dep", "khong rac thai", "hay giu gin ve sinh chung", 
                "khong hut thuoc noi cong cong", "khong uong ruou bia khi lai xe", 
                "an toan giao thong la hanh phuc cua moi nha", "toan dan doan ket xay dung doi song van hoa", 
                "cuoc thi tim hieu phap luat", "hoi thi giao thong hoc duong", 
                "thi dua day tot hoc tot", "ngay hoi doc sach", "ngay hoi van hoa the thao", 
                "giai chay vi suc khoe cong dong", "dem van nghe chao mung", "hoi cho viec lam", 
                "hoi nghi tong ket", "hoi nghi trien khai nhiem vu", "ky ket hop tac chien luoc", 
                "ban chi dao phong chong dich", "trung tam bao tro xa hoi", "phong giao duc va dao tao", 
                "trung tam cong nghe thong tin", "phong tai nguyen moi truong", "trung tam du bao khi tuong thuy van", 
                "ban ton giao chinh phu", 

                "ngay 01 thang 01 nam 2025", "ngay 15 thang 7 nam 2025", "thu hai", "thu bay", "hom nay", 
                "sang nay", "toi nay", "luc 19 gio", "luc 7 gio sang", "23h45", "14h30", "00h00", "24h00", 
                "thoi gian ap dung tu 1 7 den 31 7", 

                "29A 12345", "30F 67890", "51H 23456", 
                "43B 11223", "60C 45678", "29D 99887", 
                "xe 7 cho", "xe tai 5 tan", "xe khach", "xe buyt so 8", 

                "gia xang 25000 dong", "gia dau 21000 dong", "tien dien 2000 dong kwh", 
                "tien nuoc 15000 dong khoi", "thu nhap 10 trieu dong", "gia vang 7400000 dong luong", 
                "ty gia usd 24000", "phi truoc ba 10 phan tram", 

                "100", "2025", "50 trieu dong", "10 ngay", "5 gio", "3 lan", "2 phut", "12 thang", "100000", 
                "0 dong", "24 7", "1 1", "7 2025"


                # Single characters (very common in OCR)
                "a", "b", "c", "d", "e", "i", "o", "u", "n", "t", "s", "r",
                
                # Common short words
                "an", "on", "at", "to", "of", "in", "is", "it", "be", "or"
            ]
            
            import time
            total_start_time = time.time()
            successful_warmups = 0
            
            # Use tqdm for warmup progress
            with tqdm(warmup_queries, desc="Warming up cache", unit="queries") as pbar:
                for query in pbar:
                    try:
                        start_time = time.time()
                        # Use optimized search for warmup
                        if hasattr(service, 'search_ocr_optimized'):
                            results = service.search_ocr_optimized(query, size=5)  # Use optimized method
                        else:
                            results = service.search_ocr(query, size=5)  # Fallback
                        elapsed = time.time() - start_time
                        
                        if results:
                            successful_warmups += 1
                        
                        # Update progress bar with stats
                        pbar.set_postfix({
                            "OK": successful_warmups, 
                            "time": f"{elapsed:.3f}s",
                            "avg": f"{(time.time() - total_start_time) / (pbar.n + 1):.3f}s"
                        })
                        
                    except Exception as e:
                        # Don't fail entire warmup for one query, but don't spam logs
                        pbar.set_postfix({
                            "OK": successful_warmups, 
                            "FAIL": "error",
                            "avg": f"{(time.time() - total_start_time) / (pbar.n + 1):.3f}s"
                        })
                        continue
            
            total_elapsed = time.time() - total_start_time
            
            self.stdout.write(f"Cache warmup completed!")
            self.stdout.write(f"   {successful_warmups}/{len(warmup_queries)} queries successful")
            self.stdout.write(f"   Total warmup time: {total_elapsed:.2f}s")
            self.stdout.write(f"   Search cache is now ready for fast responses!")
            
        except Exception as e:
            self.stderr.write(f"Cache warmup failed: {e}")
            # Don't fail entire setup if warmup fails
