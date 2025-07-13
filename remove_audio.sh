#!/bin/bash

# Remove Audio from Videos - Parallel Processing
# Edit paths and MAX_JOBS below as needed

INPUT_DIR="/media/trandiep2105/newvolume/storage/videos"
OUTPUT_DIR="/media/trandiep2105/newvolume/videos_no_audio"

# Maximum parallel jobs (adjust based on your CPU cores)
# Recommended: number of CPU cores - 1
MAX_JOBS=6

# Function to remove audio from a single video
remove_audio() {
    local video_file="$1"
    local filename=$(basename "$video_file")
    local output_file="$OUTPUT_DIR/$filename"
    
    echo "[$(date '+%H:%M:%S')] Starting: $filename"
    
    ffmpeg -i "$video_file" \
        -an \
        -c:v copy \
        "$output_file" \
        -loglevel error -y
    
    if [ $? -eq 0 ]; then
        # Get file sizes for comparison
        original_size=$(stat -c%s "$video_file")
        new_size=$(stat -c%s "$output_file")
        saved_percent=$(( (original_size - new_size) * 100 / original_size ))
        
        echo "[$(date '+%H:%M:%S')] ✓ Completed: $filename (Saved: ${saved_percent}%)"
    else
        echo "[$(date '+%H:%M:%S')] ✗ Failed: $filename"
    fi
}

# Export function so it can be used by parallel processes
export -f remove_audio
export OUTPUT_DIR

# Check input directory
if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: Input directory does not exist: $INPUT_DIR"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Count total videos
total_videos=$(find "$INPUT_DIR" -name "*.mp4" -type f | wc -l)
echo "Found $total_videos MP4 files to process"
echo "Using maximum $MAX_JOBS parallel jobs"
echo "Input:  $INPUT_DIR"
echo "Output: $OUTPUT_DIR"
echo "Started at: $(date)"
echo "----------------------------------------"

# Process videos in parallel
find "$INPUT_DIR" -name "*.mp4" -type f | \
    xargs -I {} -P "$MAX_JOBS" bash -c 'remove_audio "$@"' _ {}

echo "----------------------------------------"
echo "Audio removal completed at: $(date)"

# Calculate total space saved
original_total=$(find "$INPUT_DIR" -name "*.mp4" -exec stat -c%s {} + | awk '{sum+=$1} END {print sum}')
new_total=$(find "$OUTPUT_DIR" -name "*.mp4" -exec stat -c%s {} + | awk '{sum+=$1} END {print sum}')

if [ ! -z "$original_total" ] && [ ! -z "$new_total" ]; then
    saved_bytes=$((original_total - new_total))
    saved_mb=$((saved_bytes / 1024 / 1024))
    saved_percent=$(( saved_bytes * 100 / original_total ))
    
    echo "Total space saved: ${saved_mb}MB (${saved_percent}%)"
fi
