import os
import json
import glob
import time
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


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
            
            # Run setup
            self._setup(service, options)
            
        except Exception as e:
            self.stderr.write(f"Error: {e}")
            raise

    def _setup(self, service, options):
        """Setup method"""
        try:
            # Step 1: Create indices
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
                
            self.stdout.write(self.style.SUCCESS("✓ Meilisearch setup completed successfully!"))
            
        except Exception as e:
            self.stderr.write(f"Setup failed: {e}")
            raise

    def _index_all_datasets(self, service, reset=False):
        """Index all datasets with minimal logging"""
        try:
            from search.config import LIST_DATASET
            
            total_start = time.time()
            overall_success = 0
            overall_failed = 0
            
            for data_path, index_name in LIST_DATASET:
                if not os.path.exists(data_path):
                    self.stdout.write(f"Skipping {index_name}: Directory {data_path} does not exist")
                    continue
                
                self.stdout.write(f"Indexing {index_name}...")
                start_time = time.time()
                
                successful = 0
                failed = 0
                
                # Get all JSON files
                json_files = list(Path(data_path).rglob('*.json'))
                
                if not json_files:
                    self.stdout.write(f"No JSON files found in {data_path}")
                    continue
                
                # Process files without progress bar
                for json_file in json_files:
                    try:
                        # Use the correct service method
                        service.index_ocr_data(json_file, index_name)
                        successful += 1
                                
                    except Exception as e:
                        failed += 1
                
                elapsed = time.time() - start_time
                self.stdout.write(f"  ✓ {index_name}: OK: {successful}, FAILED: {failed} ({elapsed:.1f}s)")
                
                overall_success += successful
                overall_failed += failed
            
            total_elapsed = time.time() - total_start
            self.stdout.write(f"✓ All datasets indexed: OK: {overall_success}, FAILED: {overall_failed} ({total_elapsed:.1f}s)")
            
        except Exception as e:
            self.stderr.write(f"Indexing failed: {e}")

    def _index_specific_dataset(self, service, dataset_name):
        """Index specific dataset"""
        try:
            from search.config import LIST_DATASET
            
            # Find dataset config
            target_config = None
            for data_path, index_name in LIST_DATASET:
                if index_name == dataset_name:
                    target_config = (data_path, index_name)
                    break
            
            if not target_config:
                self.stderr.write(f"Dataset '{dataset_name}' not found in configuration")
                return
            
            self._index_all_datasets(service, False)  # Will process only existing datasets
            
        except Exception as e:
            self.stderr.write(f"Specific dataset indexing failed: {e}")

    def _show_stats(self, service):
        """Show final statistics"""
        try:
            stats = service.get_index_stats()  # Use correct method
            
            for index_name, index_stats in stats.items():
                if 'error' in index_stats:
                    self.stderr.write(f"   {index_name}: {index_stats['error']}")
                else:
                    doc_count = index_stats.get('numberOfDocuments', 0)
                    self.stdout.write(f"   {index_name}: {doc_count:,} documents indexed")
                    
        except Exception as e:
            self.stderr.write(f"Could not get statistics: {e}")

    def _warmup_cache(self, service):
        """Pre-warm Meilisearch cache with minimal logging"""
        try:
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
                "0 dong", "24 7", "1 1", "7 2025",
                # Single characters (very common in OCR)
                "a", "b", "c", "d", "e", "i", "o", "u", "n", "t", "s", "r",
                # Common short words
                "an", "on", "at", "to", "of", "in", "is", "it", "be", "or"
            ]
            
            total_start_time = time.time()
            successful_warmups = 0
            
            # Process queries without progress bar
            for query in warmup_queries:
                try:
                    # Use optimized search for warmup
                    if hasattr(service, 'search_ocr_optimized'):
                        results = service.search_ocr_optimized(query, size=5)
                    else:
                        results = service.search_ocr(query, size=5)
                    
                    if results:
                        successful_warmups += 1
                        
                except Exception:
                    # Don't fail entire warmup for one query
                    continue
            
            total_elapsed = time.time() - total_start_time
            
            self.stdout.write(f"✓ Cache warmed up: {successful_warmups}/{len(warmup_queries)} queries successful ({total_elapsed:.1f}s)")
            
        except Exception as e:
            self.stderr.write(f"Cache warmup failed: {e}")
