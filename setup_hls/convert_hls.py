import os
import shutil
import cv2
import json
import logging
import math
from pathlib import Path
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
import ffmpeg

class VideoProcess:
    def __init__(self, input_path: str, output_path: str, progress_info: dict = {}):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.progress_file_path = Path("progress.json")
        self.progress_info = progress_info or {}

        logging.info(f"Dọn dẹp thư mục đầu ra '{self.output_path}'...")
        shutil.rmtree(self.output_path, ignore_errors=True)
        self.output_path.mkdir(parents=True, exist_ok=True)

        if not self.input_path.is_dir():
            raise NotADirectoryError(f"Đường dẫn đầu vào không tồn tại hoặc không phải là thư mục: {self.input_path}")
        logging.info(f"Khởi tạo VideoProcess thành công. Output sẽ được lưu tại: '{self.output_path}'")

    def get_video_files(self, file_extension: str = '.mp4') -> list:
        file_list = sorted([Path(root) / f for root, _, files in os.walk(self.input_path) for f in files if f.endswith(file_extension)])
        logging.info(f"Tìm thấy tổng cộng {len(file_list)} file video với phần mở rộng '{file_extension}'.")

        if not self.progress_info:
            self.progress_info = {
                "total_files": len(file_list),
                "start_index": 0,
                "end_index": len(file_list)
            }
            with open(self.progress_file_path, 'w') as f:
                json.dump(self.progress_info, f, indent=4)
            logging.info(f"Tạo mới file tiến trình: {self.progress_file_path}")

        return file_list[self.progress_info["start_index"]:self.progress_info["end_index"]]

    @staticmethod
    def _convert_to_hls_worker(task: tuple) -> tuple:
        input_video, hls_output_dir, segment_duration = task
        try:
            hls_output_dir.mkdir(parents=True, exist_ok=True)
            playlist_path = hls_output_dir / 'playlist.m3u8'
            segment_filename = hls_output_dir / 'segment-%05d.ts'

            (
                ffmpeg.input(str(input_video))
                .output(str(playlist_path), format='hls', hls_time=segment_duration,
                        hls_list_size=0, hls_segment_filename=str(segment_filename), c='copy')
                .run(capture_stdout=True, capture_stderr=True, quiet=True)
            )
            return (input_video.name, True, f"Đã tạo HLS tại: {hls_output_dir}")
        except ffmpeg.Error as e:
            error_message = e.stderr.decode('utf-8', errors='ignore').strip()
            shutil.rmtree(hls_output_dir, ignore_errors=True)
            return (input_video.name, False, error_message)
        except Exception as e:
            shutil.rmtree(hls_output_dir, ignore_errors=True)
            return (input_video.name, False, str(e))

    def _get_dir_size_in_gb(self, dir_path: Path) -> float:
        total_size = sum(f.stat().st_size for f in dir_path.glob('**/*') if f.is_file())
        return total_size / (1024 ** 3)

    def process_videos_in_batches(self, batch_size: int, segment_duration: int = 30, file_extension: str = '.mp4'):
        list_video = self.get_video_files(file_extension)
        if not list_video:
            logging.warning("Không tìm thấy video nào để xử lý.")
            return

        num_batches = math.ceil(len(list_video) / batch_size)
        logging.info(f"Tổng số video sẽ được chia thành {num_batches} lô, mỗi lô có tối đa {batch_size} video.")
        all_results = []

        for i in range(num_batches):
            batch_suffix = f"-batch-{i+1:03d}"
            print(f"\n{'='*20} BẮT ĐẦU LÔ {i + 1}/{num_batches} {'='*20}")

            start_index = i * batch_size
            end_index = start_index + batch_size
            current_batch_videos = list_video[start_index:end_index]

            tasks = []
            for video_path in current_batch_videos:
                output_dir_for_video = self.output_path / video_path.with_suffix('').name
                tasks.append((video_path, output_dir_for_video, segment_duration))

            with Pool(cpu_count()) as p:
                iterator = p.imap_unordered(self._convert_to_hls_worker, tasks)
                batch_results = list(tqdm(iterator, total=len(current_batch_videos), desc=f"Lô {i+1}/{num_batches}"))
                all_results.extend(batch_results)

            batch_size_gb = self._get_dir_size_in_gb(self.output_path)
            print(f"Hoàn tất xử lý Lô {i + 1}. Dung lượng: {batch_size_gb:.4f} GB.")
            if batch_size_gb == 0:
                print("Cảnh báo: Lô trống, bỏ qua.")
                continue

        print(f"\n{'='*20} TẤT CẢ CÁC LÔ ĐÃ HOÀN TẤT {'='*20}")
        success_count = sum(1 for _, success, _ in all_results if success)
        failed_files = [(name, msg) for name, success, msg in all_results if not success]

        print(f"Tổng số file đã xử lý: {len(all_results)}")
        print(f"✅ Thành công: {success_count}")
        print(f"❌ Thất bại: {len(failed_files)}")
        if failed_files:
            print("\n--- DANH SÁCH FILE LỖI ---")
            for filename, error in failed_files:
                print(f"  - File: {filename}\n    Lỗi: {error[:250]}...")
        print("="*58)


# Cấu hình chính
INPUT_DATASET_PATH = '/home/trandiep/storage/videos'  # Thư mục chứa video đầu vào
OUTPUT_HLS_PATH = '/home/trandiep/storage/videos_hls'  # Thư mục đầu ra cho HLS
BATCH_SIZE = 25  # Xử lý 25 video mỗi lô

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    try:
        processor = VideoProcess(
            input_path=INPUT_DATASET_PATH, 
            output_path=OUTPUT_HLS_PATH
        )
        
        processor.process_videos_in_batches(
            batch_size=BATCH_SIZE,
            segment_duration=10,
            file_extension='.mp4'
        )

    except Exception as e:
        logging.error(f"Một lỗi nghiêm trọng đã xảy ra trong chương trình chính: {e}")