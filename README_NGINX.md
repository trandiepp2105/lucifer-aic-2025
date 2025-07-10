# AIC Application - Nginx Configuration Guide

## 📁 Cấu hình Nginx cho Static Files và Video Streaming

### 1. Thiết lập file môi trường

```bash
# Copy file cấu hình mẫu
cp .env.example .env

# Chỉnh sửa file .env
nano .env
```

**Cập nhật các giá trị trong `.env`:**
```bash
# Media Storage Configuration
KEYFRAMES_PATH=/media/trandiep2105/newvolume/keyframes
VIDEOS_PATH=/media/trandiep2105/newvolume/videos

# Database Configuration  
MYSQL_DATABASE=aic_db
MYSQL_USER=aic_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_ROOT_PASSWORD=your_root_password

# Redis Configuration
REDIS_PASSWORD=your_redis_password

# Django Configuration
SECRET_KEY=your_secret_key_here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,backend,nginx
```

### 2. Kiểm tra thư mục media

Đảm bảo các thư mục tồn tại và có quyền đọc:
```bash
# Kiểm tra keyframes
ls -la /media/trandiep2105/newvolume/keyframes

# Kiểm tra videos  
ls -la /media/trandiep2105/newvolume/videos

# Nếu chưa có thư mục videos, tạo mới
sudo mkdir -p /media/trandiep2105/newvolume/videos
sudo chown $USER:$USER /media/trandiep2105/newvolume/videos
```

### 3. Chạy ứng dụng

```bash
# Dừng container cũ (nếu có)
docker compose down

# Khởi động dịch vụ
docker compose up -d

# Kiểm tra trạng thái
docker compose ps

# Xem logs
docker compose logs -f
```

### 4. Kiểm tra hoạt động

```bash
# Test health check
curl http://localhost/health

# Test admin access  
curl -I http://localhost/admin/

# Test static files
curl -I http://localhost/media/keyframes/

# Test video streaming
curl -I http://localhost/media/videos/
```

### 5. URLs của ứng dụng

| Service | URL | Mô tả |
|---------|-----|-------|
| **Main App** | http://localhost | Ứng dụng chính |
| **Admin** | http://localhost/admin/ | Django admin |
| **API** | http://localhost/api/ | API endpoints |
| **Keyframes** | http://localhost/media/keyframes/ | Static keyframe images |
| **Videos** | http://localhost/media/videos/ | Video streaming |
| **Health** | http://localhost/health | Health check |

### 6. Cấu hình Django

Sau khi Nginx hoạt động, cập nhật Django để không serve static files:

**Trong `urls.py`:**
```python
# XÓA hoặc comment dòng này:
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Trong `settings.py` (tùy chọn):**
```python
# Có thể tắt static serving trong production
if not DEBUG:
    # Nginx sẽ handle static files
    pass
```

### 7. Lệnh quản lý thường dùng

```bash
# Dừng tất cả services
docker compose down

# Khởi động lại
docker compose restart

# Rebuild và restart
docker compose up -d --build

# Xem logs của service cụ thể
docker compose logs -f nginx
docker compose logs -f backend

# Kiểm tra sử dụng tài nguyên
docker compose top
```

### 8. Troubleshooting

**Lỗi mount volume:**
```bash
# Kiểm tra đường dẫn trong .env
cat .env | grep PATH

# Kiểm tra quyền thư mục
ls -la /media/trandiep2105/newvolume/
```

**Nginx không start:**
```bash
# Kiểm tra config syntax
docker run --rm -v $(pwd)/nginx/default.conf:/etc/nginx/conf.d/default.conf nginx nginx -t

# Xem logs chi tiết
docker compose logs nginx
```

**Backend không connect:**
```bash
# Kiểm tra network
docker compose exec backend ping nginx
docker compose exec nginx ping backend
```

### 9. Tính năng của cấu hình này

**🖼️ Keyframes:**
- URL: `/media/keyframes/` → `/backend/media/keyframes/`
- Cache 1 năm (immutable)
- Serve trực tiếp từ filesystem
- CORS enabled

**🎥 Videos:**
- URL: `/media/videos/` → `/backend/media/videos/`
- Cache 30 ngày
- Support range requests (streaming)
- Optimized cho video playback

**📁 Static Files:**
- URL: `/static/` → `/backend/static/`
- Cache 30 ngày
- Django collectstatic files

**📂 Media Files:**
- URL: `/media/` → `/backend/media/`
- Cache 7 ngày  
- Other media files (không phải keyframes/videos)

**⚡ Performance:**
- Nginx serve static files thay vì Django
- Proper caching headers
- Gzip compression
- Optimized cho production

### 10. Mở rộng sau này

**Thêm CDN:**
```nginx
# Thêm vào nginx config
add_header X-Cache-Status $upstream_cache_status;
```

**Load balancing:**
```nginx
upstream backend {
    server backend1:8000;
    server backend2:8000;
}
```

**SSL/HTTPS:**
```bash
# Thêm certbot cho Let's Encrypt
# Update ports 443 trong docker-compose.yml
```
