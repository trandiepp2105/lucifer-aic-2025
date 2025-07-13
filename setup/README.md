# Google Drive ZIP Downloader & Extractor

Script để tải xuống và giải nén các file ZIP từ Google Drive folder.

## Cấu trúc thư mục

```
/home/trandiep/
├── credentials.json          # File cấu hình Google Drive API
├── setup/
│   ├── requirements.txt      # Dependencies Python
│   ├── download_and_extract.py  # Script chính
│   ├── run.sh               # Script cài đặt và chạy
│   └── README.md            # File hướng dẫn này
└── storage/
    └── frames/              # Thư mục lưu file đã giải nén
```

## Hướng dẫn sử dụng

### Cách 1: Chạy script tự động (khuyến nghị)
```bash
cd /home/trandiep/setup
./run.sh
```

### Cách 2: Chạy thủ công
```bash
# Cài đặt Python và unzip
sudo apt update
sudo apt install -y python3 python3-pip python3-venv unzip

# Tạo virtual environment
cd /home/trandiep/setup
python3 -m venv venv
source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt

# Chạy script
python3 download_and_extract.py
```

## Cấu hình

### Google Drive Folder ID
Script được cấu hình để tải từ folder:
- URL: https://drive.google.com/drive/folders/1NbX0GGvR_GcIqKc4TG6K0VZnnLWbXQqJ
- Folder ID: `1NbX0GGvR_GcIqKc4TG6K0VZnnLWbXQqJ`

### Thư mục lưu trữ
- File được tải về và giải nén vào: `/home/trandiep/storage/frames/`
- Mỗi file ZIP sẽ được giải nén vào thư mục con riêng

## Yêu cầu

1. **File credentials.json**: Phải có trong `/home/trandiep/credentials.json`
2. **Google Drive API**: Service account phải có quyền truy cập folder
3. **Internet connection**: Để tải file từ Google Drive

## Lưu ý

- Script sẽ tự động tạo thư mục `storage/frames` nếu chưa tồn tại
- File ZIP sẽ bị xóa sau khi giải nén thành công
- Mỗi file ZIP sẽ được giải nén vào thư mục con riêng để tránh conflict
- Script hiển thị progress và thống kê chi tiết

## Troubleshooting

### Lỗi credentials
- Kiểm tra file `credentials.json` có tồn tại
- Đảm bảo service account có quyền truy cập folder

### Lỗi quyền truy cập
- Chạy với quyền sudo nếu cần: `sudo ./run.sh`
- Kiểm tra quyền ghi thư mục `/home/trandiep/storage/frames`

### Lỗi network
- Kiểm tra kết nối internet
- Kiểm tra Google Drive API có hoạt động
