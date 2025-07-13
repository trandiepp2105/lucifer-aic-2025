#!/bin/bash
# Script để cài đặt và chạy Google Drive downloader

echo "=========================================="
echo "GOOGLE DRIVE ZIP DOWNLOADER SETUP"
echo "=========================================="

# Kiểm tra Python
if ! command -v python3 &> /dev/null; then
    echo "Cài đặt Python3..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
fi

# Kiểm tra unzip
if ! command -v unzip &> /dev/null; then
    echo "Cài đặt unzip..."
    sudo apt install -y unzip
fi

# Tạo virtual environment
echo "Tạo Python virtual environment..."
cd /home/trandiep/setup
python3 -m venv venv

# Kích hoạt virtual environment
echo "Kích hoạt virtual environment..."
source venv/bin/activate

# Cài đặt dependencies
echo "Cài đặt các package cần thiết..."
pip install --upgrade pip
pip install -r requirements.txt

# Chạy script download
echo "=========================================="
echo "BẮT ĐẦU TẢI XUỐNG..."
echo "=========================================="
python3 download_and_extract.py

echo "=========================================="
echo "HOÀN THÀNH!"
echo "=========================================="
