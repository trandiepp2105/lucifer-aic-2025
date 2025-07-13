#!/usr/bin/env python3
"""
Google Drive MP4 Downloader
Tải xuống các file MP4 từ một thư mục Google Drive (Phiên bản tự động với TQDM)
"""

import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload
import pickle
from tqdm import tqdm

# --- CẤU HÌNH ---
# Đường dẫn file credentials và token
CREDENTIALS_FILE = '/home/trandiep/credentials.json'
TOKEN_FILE = '/home/trandiep/setup/token_video.pickle' # Dùng file token riêng để tránh xung đột

# Thư mục lưu video tải về
DOWNLOAD_DIR = '/home/trandiep/storage/videos'

# ID thư mục Google Drive (tự động trích xuất từ URL)
# URL: https://drive.google.com/drive/folders/16st_3DejnvL-RLwc1MdapRCedoriaSle?fbclid=...
FOLDER_ID = '16st_3DejnvL-RLwc1MdapRCedoriaSle'

# Google API Scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
# Kích thước mỗi batch để xử lý
BATCH_SIZE = 50 # Giảm batch size cho file video lớn có thể ổn định hơn

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
            creds = flow.run_local_server(port=8081, open_browser=True)
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
    print(f"✓ Đã tạo thư mục lưu trữ: {DOWNLOAD_DIR}")

def get_mp4_files_from_folder(service, folder_id):
    """Lấy danh sách các file MP4 từ Google Drive folder"""
    try:
        # Thay đổi mimeType để tìm file video/mp4
        query = f"'{folder_id}' in parents and mimeType='video/mp4'"
        all_files = []
        page_token = None
        print("Đang quét thư mục Google Drive để tìm file MP4...")
        
        with tqdm(desc="Đang quét các trang API", unit=" trang") as pbar:
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
                pbar.update(1)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
        
        print(f"\n✓ Quét hoàn thành! Tìm thấy {len(all_files)} file MP4.")
        if not all_files:
            return []
        
        total_size_mb = sum(int(f.get('size', 0)) for f in all_files) / (1024 * 1024)
        print(f"✓ Tổng dung lượng: {total_size_mb:.2f} MB ({total_size_mb/1024:.2f} GB)")
        return all_files
    except Exception as e:
        print(f"\n✗ Lỗi khi lấy danh sách file: {e}")
        return []

def download_file_with_progress(service, file_id, file_name, download_path, pbar):
    """Tải xuống một file từ Google Drive và cập nhật progress bar của TQDM"""
    try:
        request = service.files().get_media(fileId=file_id)
        
        with open(download_path, 'wb') as file_handle:
            downloader = MediaIoBaseDownload(file_handle, request)
            done = False
            while not done:
                # Không in gì ở đây để TQDM toàn quyền kiểm soát giao diện
                _, done = downloader.next_chunk()
        return True
    except Exception as e:
        # Ghi lỗi mà không làm hỏng thanh progress bar
        pbar.write(f"\n  ✗ Lỗi khi tải xuống {file_name}: {e}")
        return False

def process_files_in_batches(service, files, batch_size):
    """Tự động tải xuống tất cả các file theo từng batch với thanh tiến trình TQDM"""
    total_files = len(files)
    total_batches = (total_files + batch_size - 1) // batch_size
    overall_success = 0
    failed_files_list = []
    
    print(f"\n📦 SẼ TỰ ĐỘNG TẢI XUỐNG {total_files} FILE TRONG {total_batches} BATCH")
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_files)
        batch_files = files[start_idx:end_idx]
        
        # Tạo một thanh tiến trình cho batch hiện tại
        progress_bar = tqdm(batch_files, desc=f"Batch {batch_num + 1}/{total_batches}", unit="file")

        for file in progress_bar:
            # Cập nhật tên file đang xử lý trên thanh tiến trình
            progress_bar.set_postfix_str(f"Downloading: {file['name'][:30]}...")

            destination_path = os.path.join(DOWNLOAD_DIR, file['name'])
            
            # Kiểm tra nếu file đã tồn tại thì bỏ qua
            if os.path.exists(destination_path):
                progress_bar.write(f"  - Bỏ qua: {file['name']} (đã tồn tại).")
                overall_success += 1
                continue

            if download_file_with_progress(service, file['id'], file['name'], destination_path, progress_bar):
                overall_success += 1
            else:
                failed_files_list.append(file['name'])
    
    return overall_success, failed_files_list

def main():
    """Hàm chính - Quy trình tự động"""
    print("=" * 60)
    print("GOOGLE DRIVE MP4 DOWNLOADER (TỰ ĐỘNG)")
    print("=" * 60)
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"✗ Không tìm thấy file credentials: {CREDENTIALS_FILE}")
        return
    
    create_download_directory()
    service = setup_google_drive_service()
    if not service:
        return
        
    mp4_files = get_mp4_files_from_folder(service, FOLDER_ID)
    if not mp4_files:
        print("\nKhông tìm thấy file MP4 nào để xử lý. Kết thúc chương trình.")
        return

    total_files_to_process = len(mp4_files)
    
    success_count, failed_files = process_files_in_batches(service, mp4_files, BATCH_SIZE)
    
    print(f"\n{'=' * 60}")
    print("HOÀN THÀNH - KẾT QUẢ TỔNG QUAN")
    print(f"{'=' * 60}")
    print(f"Tổng số file MP4 đã quét: {total_files_to_process}")
    print(f"✅ Tải xuống thành công: {success_count}")
    failed_count = len(failed_files)
    print(f"❌ Thất bại: {failed_count}")
    
    if total_files_to_process > 0:
        success_rate = (success_count / total_files_to_process * 100)
        print(f"Tỷ lệ thành công: {success_rate:.1f}%")
        
    print(f"Thư mục lưu trữ video: {DOWNLOAD_DIR}")
    
    if failed_files:
        print(f"\n⚠️ DANH SÁCH FILE TẢI THẤT BẠI ({failed_count}):")
        for failed_file in failed_files:
            print(f"  - {failed_file}")
    
    print("\n✓ Chương trình đã hoàn tất.")

if __name__ == "__main__":
    main()