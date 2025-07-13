import os
import io
import zipfile
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload
import json
import pickle
from tqdm import tqdm # <--- THÊM IMPORT NÀY

# Cấu hình đường dẫn
CREDENTIALS_FILE = '/home/trandiep/credentials.json'
TOKEN_FILE = '/home/trandiep/setup/token.pickle'
DOWNLOAD_DIR = '/home/trandiep/storage/frames'
FOLDER_ID = '1NbX0GGvR_GcIqKc4TG6K0VZnnLWbXQqJ'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
BATCH_SIZE = 100

def setup_google_drive_service():
    """Thiết lập service Google Drive API với OAuth2"""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Đang làm mới token...")
                creds.refresh(Request())
            except Exception as e:
                print(f"Không thể làm mới token: {e}")
                creds = None
        if not creds:
            print("Cần xác thực với Google...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    try:
        service = build('drive', 'v3', credentials=creds)
        print("✓ Đã kết nối thành công với Google Drive API")
        return service
    except Exception as e:
        print(f"✗ Lỗi khi tạo service: {e}")
        return None

def create_download_directory():
    """Tạo thư mục download nếu chưa tồn tại"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"✓ Đã tạo thư mục: {DOWNLOAD_DIR}")

def get_zip_files_from_folder(service, folder_id):
    """Lấy danh sách các file ZIP từ Google Drive folder với pagination"""
    try:
        query = f"'{folder_id}' in parents and mimeType='application/zip'"
        all_files = []
        page_token = None
        print("Đang quét thư mục Google Drive...")
        while True:
            request_params = {
                'q': query,
                'pageSize': 1000,
                'fields': "nextPageToken, files(id, name, size)",
                'pageToken': page_token
            }
            results = service.files().list(**request_params).execute()
            files = results.get('files', [])
            all_files.extend(files)
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        
        print(f"✓ Quét hoàn thành! Tìm thấy {len(all_files)} file ZIP.")
        if not all_files:
            return []
        
        total_size_mb = sum(int(f.get('size', 0)) for f in all_files) / (1024 * 1024)
        print(f"✓ Tổng dung lượng: {total_size_mb:.2f} MB ({total_size_mb/1024:.2f} GB)")
        return all_files
    except Exception as e:
        print(f"✗ Lỗi khi lấy danh sách file: {e}")
        return []

def download_file(service, file_id, file_name, download_path):
    """Tải xuống một file từ Google Drive"""
    try:
        request = service.files().get_media(fileId=file_id)
        with open(download_path, 'wb') as file_handle:
            downloader = MediaIoBaseDownload(file_handle, request)
            done = False
            while not done:
                # Dòng print tiến độ của từng file đã được xóa để không làm rối progress bar của TQDM
                _, done = downloader.next_chunk()
        return True
    except Exception as e:
        tqdm.write(f"\n  ✗ Lỗi khi tải xuống {file_name}: {e}") # Dùng tqdm.write để không làm hỏng thanh progress
        return False

def extract_zip_file(zip_path, extract_to_dir):
    """Giải nén file ZIP và xóa file ZIP sau đó"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            extract_dir = os.path.join(extract_to_dir, zip_name)
            os.makedirs(extract_dir, exist_ok=True)
            zip_ref.extractall(extract_dir)
        os.remove(zip_path)
        return True
    except Exception as e:
        tqdm.write(f"  ✗ Lỗi khi giải nén {os.path.basename(zip_path)}: {e}")
        return False

def process_files_in_batches(service, files, batch_size):
    """Tự động xử lý tất cả các file theo từng batch với thanh tiến trình TQDM"""
    total_files = len(files)
    total_batches = (total_files + batch_size - 1) // batch_size
    overall_success = 0
    failed_files_list = []
    
    print(f"\n📦 SẼ TỰ ĐỘNG XỬ LÝ {total_files} FILE TRONG {total_batches} BATCH")
    print(f"📏 Kích thước mỗi batch: {batch_size} file")
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_files)
        batch_files = files[start_idx:end_idx]
        
        print(f"\n{'='*60}")
        # --- THAY ĐỔI CHÍNH NẰM Ở ĐÂY ---
        # Tạo một thanh tiến trình cho batch hiện tại
        progress_bar = tqdm(batch_files, desc=f"Batch {batch_num + 1}/{total_batches}", unit="file")

        for file in progress_bar:
            # Cập nhật tên file đang xử lý trên thanh tiến trình
            progress_bar.set_postfix_str(f"Processing: {file['name'][:30]}...")

            temp_zip_path = os.path.join(DOWNLOAD_DIR, file['name'])
            
            if download_file(service, file['id'], file['name'], temp_zip_path):
                if extract_zip_file(temp_zip_path, DOWNLOAD_DIR):
                    overall_success += 1
                else:
                    failed_files_list.append(file['name'])
            else:
                failed_files_list.append(file['name'])
    
    return overall_success, failed_files_list

def main():
    """Hàm chính - Quy trình tự động"""
    print("=" * 60)
    print("GOOGLE DRIVE ZIP DOWNLOADER & EXTRACTOR (TỰ ĐỘNG)")
    print("=" * 60)
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"✗ Không tìm thấy file credentials: {CREDENTIALS_FILE}")
        return
    
    create_download_directory()
    service = setup_google_drive_service()
    if not service:
        return
        
    zip_files = get_zip_files_from_folder(service, FOLDER_ID)
    if not zip_files:
        print("\nKhông tìm thấy file ZIP nào để xử lý. Kết thúc chương trình.")
        return

    total_files_to_process = len(zip_files)
    
    success_count, failed_files = process_files_in_batches(service, zip_files, BATCH_SIZE)
    
    print(f"\n{'=' * 60}")
    print("HOÀN THÀNH - KẾT QUẢ TỔNG QUAN")
    print(f"{'=' * 60}")
    print(f"Tổng số file ZIP đã quét: {total_files_to_process}")
    print(f"✅ Xử lý thành công: {success_count}")
    failed_count = len(failed_files)
    print(f"❌ Thất bại: {failed_count}")
    
    if total_files_to_process > 0:
        success_rate = (success_count / total_files_to_process * 100)
        print(f"Tỷ lệ thành công: {success_rate:.1f}%")
        
    print(f"Thư mục lưu trữ: {DOWNLOAD_DIR}")
    
    if failed_files:
        print(f"\n⚠️ DANH SÁCH FILE THẤT BẠI ({failed_count}):")
        for failed_file in failed_files:
            print(f"  - {failed_file}")
    
    print("\n✓ Chương trình đã hoàn tất.")

if __name__ == "__main__":
    main()