import os
import json
import glob
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
            
            self.stdout.write("🚀 Setting up Meilisearch...")
            
            # Run setup (no async needed)
            self._setup(service, options)
            
        except Exception as e:
            self.stderr.write(f"❌ Error: {e}")
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
                self.stdout.write("⏭️  Skipping cache warmup")
            
            self.stdout.write("✅ Meilisearch setup completed!")
            
        except Exception as e:
            self.stderr.write(f"❌ Setup failed: {e}")
            raise

    def _index_all_datasets(self, service, reset=False):
        """Index all datasets from config"""
        from search.config import LIST_DATASET
        
        for dataset_path, index_name in LIST_DATASET:
            self.stdout.write(f"📂 Processing dataset: {index_name}")
            
            # Get absolute path
            if dataset_path.startswith('/backend/'):
                # Docker path
                abs_path = dataset_path
            else:
                # Local path - relative to backend directory
                abs_path = os.path.join(settings.BASE_DIR, dataset_path.lstrip('/'))
            
            if not os.path.exists(abs_path):
                self.stderr.write(f"⚠️  Dataset path not found: {abs_path}")
                continue
            
            # Find all JSON files
            json_files = glob.glob(os.path.join(abs_path, "*.json"))
            
            if not json_files:
                self.stderr.write(f"⚠️  No JSON files found in: {abs_path}")
                continue
            
            self.stdout.write(f"📄 Found {len(json_files)} JSON files")
            
            # Index each file
            for json_file in json_files:
                try:
                    service.index_ocr_data(json_file, index_name)
                    video_name = Path(json_file).stem
                    self.stdout.write(f"   ✅ Indexed: {video_name}")
                except Exception as e:
                    video_name = Path(json_file).stem
                    self.stderr.write(f"   ❌ Failed to index {video_name}: {e}")

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
            self.stderr.write(f"❌ Dataset '{dataset_name}' not found. Available: {available}")
            return
        
        dataset_path, index_name = dataset_config
        
        # Get absolute path
        if dataset_path.startswith('/backend/'):
            abs_path = dataset_path
        else:
            abs_path = os.path.join(settings.BASE_DIR, dataset_path.lstrip('/'))
        
        if not os.path.exists(abs_path):
            self.stderr.write(f"⚠️  Dataset path not found: {abs_path}")
            return
        
        # Find all JSON files
        json_files = glob.glob(os.path.join(abs_path, "*.json"))
        
        if not json_files:
            self.stderr.write(f"⚠️  No JSON files found in: {abs_path}")
            return
        
        self.stdout.write(f"📂 Processing dataset: {index_name}")
        self.stdout.write(f"📄 Found {len(json_files)} JSON files")
        
        # Index each file
        for json_file in json_files:
            try:
                service.index_ocr_data(json_file, index_name)
                video_name = Path(json_file).stem
                self.stdout.write(f"   ✅ Indexed: {video_name}")
            except Exception as e:
                video_name = Path(json_file).stem
                self.stderr.write(f"   ❌ Failed to index {video_name}: {e}")

    def _show_stats(self, service):
        """Show indexing statistics"""
        try:
            stats = service.get_index_stats()
            
            self.stdout.write("\n📊 Index Statistics:")
            for index_name, index_stats in stats.items():
                if 'error' in index_stats:
                    self.stderr.write(f"   ❌ {index_name}: {index_stats['error']}")
                else:
                    doc_count = index_stats.get('numberOfDocuments', 0)
                    is_indexing = index_stats.get('isIndexing', False)
                    status = "🔄 Indexing..." if is_indexing else "✅ Ready"
                    self.stdout.write(f"   📈 {index_name}: {doc_count:,} documents {status}")
            
        except Exception as e:
            self.stderr.write(f"⚠️  Could not get statistics: {e}")

    def _warmup_cache(self, service):
        """Pre-warm Meilisearch cache with common queries"""
        try:
            self.stdout.write("\n🔥 Pre-warming Meilisearch cache...")
            
            # Common warmup queries - optimized for Vietnamese without diacritics + English
            warmup_queries = [
                # Vietnamese common words (without diacritics - matching your processed data)
                "xin chao", "cam on", "toi", "ban", "lam", "nhu", "nay", "co", "khong",
                "viet", "nam", "ha", "noi", "thanh", "pho", "quan", "huyen", "xa",
                "la", "cua", "va", "duoc", "tai", "voi", "tu", "cho", "ve", "den",
                "moi", "nhung", "cac", "trong", "ngoai", "tren", "duoi", "giua",
                "covid", "virus", "benh", "dich", "y te", "bac si", "benh vien",
                
                # English common words  
                "hello", "thank", "you", "how", "what", "time", "day", "good", "bad",
                "the", "and", "or", "but", "with", "for", "from", "to", "at", "in",
                "covid", "virus", "pandemic", "vaccine", "test", "health", "doctor",
                
                # Numbers and dates (common in OCR)
                "2024", "2023", "2022", "19", "20", "01", "02", "10", "100", "1000",
                "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
                
                # OCR-specific terms
                "video", "frame", "text", "document", "page", "line", "word",
                "time", "timestamp", "second", "minute", "hour",
                
                # Single characters (very common in OCR)
                "a", "b", "c", "d", "e", "i", "o", "u", "n", "t", "s", "r",
                
                # Common short words
                "an", "on", "at", "to", "of", "in", "is", "it", "be", "or"
            ]
            
            import time
            total_start_time = time.time()
            successful_warmups = 0
            
            for i, query in enumerate(warmup_queries, 1):
                try:
                    start_time = time.time()
                    results = service.search_ocr(query, size=5)  # Small result set for speed
                    elapsed = time.time() - start_time
                    
                    if results:
                        successful_warmups += 1
                        # Show progress every 5 queries
                        if i % 5 == 0:
                            self.stdout.write(f"   🔥 Warmed {i}/{len(warmup_queries)} queries ({elapsed:.3f}s)")
                    
                except Exception as e:
                    # Don't fail entire warmup for one query
                    self.stdout.write(f"   ⚠️  Warmup failed for '{query}': {e}")
                    continue
            
            total_elapsed = time.time() - total_start_time
            
            self.stdout.write(f"✅ Cache warmup completed!")
            self.stdout.write(f"   📊 {successful_warmups}/{len(warmup_queries)} queries successful")
            self.stdout.write(f"   ⏱️  Total warmup time: {total_elapsed:.2f}s")
            self.stdout.write(f"   🚀 Search cache is now ready for fast responses!")
            
        except Exception as e:
            self.stderr.write(f"⚠️  Cache warmup failed: {e}")
            # Don't fail entire setup if warmup fails
