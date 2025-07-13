#!/usr/bin/env python3
"""
Google Drive Recursive Folder Downloader
Tải xuống một thư mục Google Drive và các thư mục con của nó, giữ nguyên cấu trúc.
"""

import os
import io
import zipfile
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload
import pickle
from tqdm import tqdm

# --- CẤU HÌNH ---
# THAY ĐỔI ID NÀY thành ID của thư mục gốc bạn muốn tải
FOLDER_ID_TO_DOWNLOAD = '1cHcnZIWAAZkDh_2FwwvW4PiEc1XZUvQN' 

# Thư mục lưu trữ chính trên máy của bạn
BASE_DOWNLOAD_DIR = '/home/trandiep/index'

# Cấu hình xác thực (giữ nguyên như cũ)
CREDENTIALS_FILE = '/home/trandiep/credentials.json'
TOKEN_FILE = '/home/trandiep/setup/token_recursive.pickle' # File token riêng
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

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

def scan_drive_folder_recursively(service, folder_id, current_path, pbar):
    """
    Quét đệ quy thư mục trên Drive để lấy danh sách tất cả các file.
    Không tải xuống ở bước này, chỉ lập danh sách.
    """
    file_list = []
    page_token = None

    while True:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageSize=1000,
            pageToken=page_token
        ).execute()

        items = results.get('files', [])
        for item in items:
            item_path = os.path.join(current_path, item['name'])
            # Nếu là thư mục, đi sâu vào (đệ quy)
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                file_list.extend(scan_drive_folder_recursively(service, item['id'], item_path, pbar))
            # Nếu là file, thêm vào danh sách
            else:
                file_list.append({
                    'id': item['id'],
                    'name': item['name'],
                    'mimeType': item['mimeType'],
                    'path': item_path  # Đường dẫn đầy đủ trên máy local
                })
        
        pbar.set_postfix_str(f"Đã quét {len(file_list)} file...")
        page_token = results.get('nextPageToken')
        if not page_token:
            break
            
    return file_list

def download_file(service, file_id, download_path):
    """Tải xuống một file."""
    try:
        request = service.files().get_media(fileId=file_id)
        with open(download_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return True
    except Exception as e:
        tqdm.write(f"\n  ✗ Lỗi khi tải xuống {os.path.basename(download_path)}: {e}")
        return False

def extract_zip_file(zip_path):
    """Giải nén file ZIP vào một thư mục con cùng tên và xóa file ZIP."""
    try:
        extract_dir = os.path.splitext(zip_path)[0] # Thư mục giải nén cùng tên với file zip
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        os.remove(zip_path) # Xóa file zip sau khi giải nén
        return True
    except Exception as e:
        tqdm.write(f"\n  ✗ Lỗi khi giải nén {os.path.basename(zip_path)}: {e}")
        return False

def main():
    """Hàm chính - Quy trình tự động"""
    print("=" * 60)
    print("GOOGLE DRIVE RECURSIVE FOLDER DOWNLOADER")
    print("=" * 60)

    if FOLDER_ID_TO_DOWNLOAD == 'YOUR_FOLDER_ID_HERE':
        print("✗ VUI LÒNG THAY ĐỔI 'FOLDER_ID_TO_DOWNLOAD' TRONG SCRIPT!")
        return

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"✗ Không tìm thấy file credentials: {CREDENTIALS_FILE}")
        return
    
    service = setup_google_drive_service()
    if not service:
        return

    # Lấy tên thư mục gốc để tạo thư mục tương ứng trên máy
    try:
        root_folder_info = service.files().get(fileId=FOLDER_ID_TO_DOWNLOAD, fields='name').execute()
        root_folder_name = root_folder_info.get('name', 'GoogleDrive_Download')
        destination_root_path = os.path.join(BASE_DOWNLOAD_DIR, root_folder_name)
        print(f"✓ Sẽ tải nội dung vào: {destination_root_path}")
    except Exception as e:
        print(f"✗ Không thể lấy thông tin thư mục gốc (ID: {FOLDER_ID_TO_DOWNLOAD}). Lỗi: {e}")
        return

    # 1. Quét toàn bộ cây thư mục để lập danh sách file
    print("\n[BƯỚC 1/2] Đang quét toàn bộ cây thư mục trên Google Drive...")
    with tqdm(desc="Đang quét", unit=" API call") as pbar:
        files_to_download = scan_drive_folder_recursively(service, FOLDER_ID_TO_DOWNLOAD, destination_root_path, pbar)
    
    if not files_to_download:
        print("\n✓ Không tìm thấy file nào trong thư mục được chỉ định. Kết thúc.")
        return
        
    print(f"✓ Quét hoàn tất! Tìm thấy tổng cộng {len(files_to_download)} file để tải xuống.")

    # 2. Tải và xử lý các file trong danh sách
    print("\n[BƯỚC 2/2] Bắt đầu tải xuống và xử lý file...")
    success_count = 0
    failed_list = []

    progress_bar = tqdm(files_to_download, desc="Đang xử lý", unit="file")
    for file_info in progress_bar:
        local_file_path = file_info['path']
        progress_bar.set_postfix_str(f"{os.path.basename(local_file_path)[:40]}...")

        # Tạo thư mục cha nếu nó chưa tồn tại
        local_dir = os.path.dirname(local_file_path)
        os.makedirs(local_dir, exist_ok=True)
        
        # Tải file
        if download_file(service, file_info['id'], local_file_path):
            # Nếu là file zip, giải nén nó
            if file_info['mimeType'] == 'application/zip':
                if extract_zip_file(local_file_path):
                    success_count += 1
                else:
                    failed_list.append(local_file_path)
            else:
                success_count += 1
        else:
            failed_list.append(local_file_path)

    # 3. Thống kê kết quả
    print(f"\n{'=' * 60}")
    print("HOÀN THÀNH - KẾT QUẢ TỔNG QUAN")
    print(f"{'=' * 60}")
    print(f"Tổng số file đã quét: {len(files_to_download)}")
    print(f"✅ Xử lý thành công: {success_count}")
    print(f"❌ Thất bại: {len(failed_list)}")
    print(f"Thư mục lưu trữ chính: {BASE_DOWNLOAD_DIR}")
    
    if failed_list:
        print(f"\n⚠️ DANH SÁCH FILE/THƯ MỤC THẤT BẠI ({len(failed_list)}):")
        for path in failed_list:
            print(f"  - {path}")
    
    print("\n✓ Chương trình đã hoàn tất.")

if __name__ == "__main__":
    main()