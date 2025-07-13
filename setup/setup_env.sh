#!/bin/bash

# ==============================================================================
# Script cài đặt môi trường phát triển web trên Ubuntu
#
# Bao gồm:
#   - Docker Engine
#   - Docker Compose (phiên bản mới nhất)
#   - Node.js (phiên bản LTS mới nhất từ NodeSource)
#   - Build Essentials
#
# Cách sử dụng:
#   1. chmod +x setup_dev_env.sh
#   2. ./setup_dev_env.sh
# ==============================================================================

# Dừng script ngay lập tức nếu có bất kỳ lệnh nào thất bại
set -e

# Hàm in thông báo
print_header() {
  echo -e "\n\e[1;34m=======================================================================\e[0m"
  echo -e "\e[1;32m$1\e[0m"
  echo -e "\e[1;34m=======================================================================\e[0m"
}

# --- BƯỚC 1: CẬP NHẬT HỆ THỐNG ---
print_header "Bước 1: Cập nhật hệ thống và các gói tin"
sudo apt-get update
sudo apt-get upgrade -y

# --- BƯỚC 2: CÀI ĐẶT DOCKER ENGINE ---
print_header "Bước 2: Cài đặt Docker Engine"
# Cài các gói phụ thuộc cần thiết
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg

# Thêm khóa GPG chính thức của Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Thêm kho lưu trữ (repository) của Docker vào APT sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Cập nhật lại danh sách gói tin sau khi thêm repo của Docker
sudo apt-get update

# Cài đặt phiên bản mới nhất của Docker
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

# --- BƯỚC 3: CẤU HÌNH SAU CÀI ĐẶT DOCKER ---
print_header "Bước 3: Cấu hình Docker để chạy không cần sudo"
# Tạo nhóm 'docker' nếu nó chưa tồn tại
sudo groupadd --force docker
# Thêm người dùng hiện tại vào nhóm 'docker'
sudo usermod -aG docker $USER

echo -e "\e[1;33m>>> LƯU Ý QUAN TRỌNG: Bạn cần ĐĂNG XUẤT và ĐĂNG NHẬP LẠI để có thể chạy docker không cần sudo.\e[0m"
echo -e "\e[1;33m>>> Hoặc bạn có thể chạy lệnh sau trong terminal hiện tại: newgrp docker\e[0m"

# --- BƯỚC 4: CÀI ĐẶT DOCKER COMPOSE ---
print_header "Bước 4: Cài đặt Docker Compose"
# Tìm phiên bản mới nhất của Docker Compose
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
echo "Phiên bản Docker Compose mới nhất là: $DOCKER_COMPOSE_VERSION"

# Tải Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Cấp quyền thực thi cho file binary
sudo chmod +x /usr/local/bin/docker-compose

# Kiểm tra phiên bản
echo "Kiểm tra phiên bản Docker Compose:"
docker-compose --version

# --- BƯỚC 5: CÀI ĐẶT NODE.JS VÀ NPM ---
print_header "Bước 5: Cài đặt Node.js (phiên bản LTS) và các công cụ build"
# Tải và chạy script cài đặt từ NodeSource cho phiên bản Node.js 20.x (LTS hiện tại)
# Bạn có thể thay đổi setup_20.x thành phiên bản khác nếu muốn
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# Cài đặt Node.js và các công cụ build cần thiết
sudo apt-get install -y nodejs build-essential

# --- BƯỚC 6: KIỂM TRA VÀ HOÀN TẤT ---
print_header "Bước 6: Hoàn tất! Kiểm tra lại các phiên bản đã cài đặt"
echo "Phiên bản Docker:"
docker --version
echo -e "\nPhiên bản Docker Compose:"
docker-compose --version
echo -e "\nPhiên bản Node.js:"
node -v
echo -e "\nPhiên bản NPM:"
npm -v

echo -e "\n\e[1;32m=======================================================================\e[0m"
echo -e "\e[1;32m CÀI ĐẶT MÔI TRƯỜNG PHÁT TRIỂN WEB HOÀN TẤT! \e[0m"
echo -e "\e[1;33m NHỚ ĐĂNG XUẤT VÀ ĐĂNG NHẬP LẠI ĐỂ ÁP DỤNG THAY ĐỔI NHÓM DOCKER. \e[0m"
echo -e "\e[1;32m=======================================================================\e[0m"