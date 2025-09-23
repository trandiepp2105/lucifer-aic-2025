# Build stage với OpenJDK 11 (như chúng ta đã cài)
FROM openjdk:11-jdk AS build

# Copy source code
COPY . /dres-src
WORKDIR /dres-src

# Download FFmpeg dependencies trước khi build
RUN ./gradlew setupFFMpeg

# Build với distZip (như chúng ta đã làm thành công) thay vì distTar
RUN ./gradlew distZip && \
    cd backend/build/distributions && \
    unzip -q dres-dist.zip

# Runtime stage với OpenJDK 11 JRE
FROM openjdk:11-jre-slim

# Install cần thiết dependencies
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Copy distribution đã build từ stage trước
COPY --from=build /dres-src/backend/build/distributions/dres-dist /dres-dist

# Copy keystore.jks (cần thiết để chạy HTTPS)
COPY --from=build /dres-src/backend/keystore.jks /dres-dist/

# Tạo thư mục data
RUN mkdir -p /dres-dist/data

# Set executable permissions cho FFmpeg
RUN find /dres-dist -name "ffmpeg" -type f -exec chmod +x {} \; && \
    find /dres-dist -name "ffprobe" -type f -exec chmod +x {} \;

# Set working directory
WORKDIR /dres-dist

# Expose ports
EXPOSE 8080
EXPOSE 8443

# Health check để verify server đang chạy
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/api/v2/status || exit 1

# Entry point - chạy backend executable
ENTRYPOINT ["./bin/backend"]