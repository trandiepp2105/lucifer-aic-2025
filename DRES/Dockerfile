# Build stage với OpenJDK 11 (như chúng ta đã cài)
FROM openjdk:11-jdk AS build

# Copy source code
COPY . /dres-src
WORKDIR /dres-src

# Set Gradle options để tăng timeout và retry
ENV GRADLE_OPTS="-Dorg.gradle.daemon=false -Dorg.gradle.jvmargs='-Xmx2g -XX:MaxMetaspaceSize=512m' -Dorg.gradle.internal.http.connectionTimeout=900000 -Dorg.gradle.internal.http.socketTimeout=900000"

# Download dependencies với nhiều retry attempts và timeout lớn hơn
RUN for attempt in 1 2 3 4 5; do \
        echo "Attempt $attempt: Downloading Gradle and FFmpeg dependencies..." && \
        timeout 1200 ./gradlew setupFFMpeg --no-daemon --stacktrace --refresh-dependencies && \
        echo "setupFFMpeg completed successfully" && break || \
        echo "Attempt $attempt failed, waiting 60s before retry..."; \
        sleep 60; \
    done

# Build backend only, skip frontend để tránh git issues
RUN for attempt in 1 2 3; do \
        echo "Build attempt $attempt: Creating backend distribution..." && \
        timeout 900 ./gradlew backend:distZip --no-daemon --stacktrace && \
        cd backend/build/distributions && \
        unzip -q dres-dist.zip && \
        echo "Backend build completed successfully" && break || \
        echo "Build attempt $attempt failed, waiting 30s before retry..."; \
        sleep 30; \
        cd /dres-src; \
    done

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