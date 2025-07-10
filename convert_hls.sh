#!/bin/bash

# HLS Video Converter - Parallel Processing
# Edit paths and MAX_JOBS below as needed

INPUT_DIR="/media/trandiep2105/newvolume/videos_no_audio"
OUTPUT_DIR="/home/trandiep2105/Documents/videos_hls"

# Maximum parallel jobs (adjust based on your CPU cores)
# Recommended: number of CPU cores - 1
MAX_JOBS=6

# Function to convert a single video
convert_video() {
    local video_file="$1"
    local filename=$(basename "$video_file" .mp4)
    local output_subdir="$OUTPUT_DIR/$filename"
    
    mkdir -p "$output_subdir"
    
    echo "[$(date '+%H:%M:%S')] Starting: $filename"
    
    ffmpeg -i "$video_file" \
        -c:v libx264 -c:a aac \
        -preset fast \
        -hls_time 6 \
        -hls_playlist_type vod \
        -hls_segment_filename "$output_subdir/%03d.ts" \
        "$output_subdir/index.m3u8" \
        -loglevel error -y
    
    if [ $? -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] ✓ Completed: $filename"
    else
        echo "[$(date '+%H:%M:%S')] ✗ Failed: $filename"
    fi
}

# Export function so it can be used by parallel processes
export -f convert_video
export OUTPUT_DIR

# Check input directory
if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: Input directory does not exist: $INPUT_DIR"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Count total videos
total_videos=$(find "$INPUT_DIR" -name "*.mp4" -type f | wc -l)
echo "Found $total_videos MP4 files to convert"
echo "Using maximum $MAX_JOBS parallel jobs"
echo "Started at: $(date)"
echo "----------------------------------------"

# Process videos in parallel
find "$INPUT_DIR" -name "*.mp4" -type f | \
    xargs -I {} -P "$MAX_JOBS" bash -c 'convert_video "$@"' _ {}

echo "----------------------------------------"
echo "Conversion completed at: $(date)"
