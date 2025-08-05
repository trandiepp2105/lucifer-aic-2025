#!/usr/bin/env python3
import os
import json
import cv2
from pathlib import Path

# Configuration
INPUT_PATH = "/media/hkduy/ssd_duy_deptrai/storage/videos"  # Path to input videos
OUTPUT_PATH = "/media/hkduy/ssd_duy_deptrai/storage/frames"  # Path to save metadata

def extract_video_metadata(video_path):
    """Extract metadata from a video file"""
    try:
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"Error: Cannot open video {video_path}")
            return None
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        metadata = {
            "fps": fps,
            "duration": duration,
        }
        
        return metadata
        
    except Exception as e:
        print(f"Error extracting metadata from {video_path}: {e}")
        return None

def main():
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    
    # Process all MP4 files in input directory
    input_dir = Path(INPUT_PATH)
    
    if not input_dir.exists():
        print(f"Error: Input directory {INPUT_PATH} does not exist")
        return
    
    mp4_files = list(input_dir.glob("*.mp4"))
    
    if not mp4_files:
        print(f"No MP4 files found in {INPUT_PATH}")
        return
    
    print(f"Found {len(mp4_files)} MP4 files to process")
    
    for video_file in mp4_files:
        print(f"Processing: {video_file.name}")
        
        # Extract metadata
        metadata = extract_video_metadata(str(video_file))
        
        if metadata is None:
            continue
        
        # Create output directory for this video
        video_name = video_file.stem  # filename without extension
        output_dir = Path(OUTPUT_PATH) / video_name
        output_dir.mkdir(exist_ok=True)
        
        # Save metadata to JSON file
        metadata_file = output_dir / "metadata.json"
        
        try:
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"  ✗ Error saving metadata: {e}")

if __name__ == "__main__":
    main()
