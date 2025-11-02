#!/bin/bash

# Script to download folder from Google Drive
# Usage: ./download_and_extract.sh

set -e  # Exit on error

# Configuration
GDRIVE_FOLDER_ID="1ICJFum5TV3I37V-NpjzTVFkJWEMZ7DQU"  # Google Drive folder ID
OUTPUT_DIR="/lucifer_data"    # Destination directory

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting download from Google Drive folder...${NC}"

# Check if gdown is installed
if ! command -v gdown &> /dev/null && ! command -v ~/.local/bin/gdown &> /dev/null; then
    echo -e "${YELLOW}gdown is not installed. Installing with pip3...${NC}"
    # Try with --break-system-packages first (Python 3.11+), fallback to regular install
    if ! pip3 install gdown --break-system-packages 2>/dev/null; then
        echo -e "${YELLOW}Trying installation without --break-system-packages...${NC}"
        pip3 install --user gdown || pip3 install gdown
    fi
fi

# Use gdown from local bin if not in PATH
if command -v gdown &> /dev/null; then
    GDOWN_CMD="gdown"
else
    GDOWN_CMD="$HOME/.local/bin/gdown"
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Clean up any incomplete downloads (.part files)
echo -e "${YELLOW}Cleaning up incomplete downloads...${NC}"
find "$OUTPUT_DIR" -name "*.part" -type f -delete

# Download entire folder from Google Drive
echo -e "${GREEN}Downloading folder with gdown...${NC}"
$GDOWN_CMD --folder "https://drive.google.com/drive/folders/${GDRIVE_FOLDER_ID}" -O "$OUTPUT_DIR" --remaining-ok

echo -e "${GREEN}Download completed!${NC}"

# Check for incomplete downloads
PART_FILES=$(find "$OUTPUT_DIR" -name "*.part" -type f)
if [ -n "$PART_FILES" ]; then
    echo -e "${RED}Warning: Found incomplete downloads (.part files)${NC}"
    echo -e "${YELLOW}Download may have been interrupted. Please check your connection and try again.${NC}"
    ls -lh "$OUTPUT_DIR"/*.part 2>/dev/null || true
    exit 1
fi

# Look for lucifer-data.zip and extract it
ZIP_FILE=$(find "$OUTPUT_DIR" -name "lucifer-data.zip" -type f | head -n 1)

if [ -n "$ZIP_FILE" ]; then
    echo -e "${GREEN}Found lucifer-data.zip at: $ZIP_FILE${NC}"
    echo -e "${GREEN}Extracting lucifer-data.zip...${NC}"
    
    unzip -o "$ZIP_FILE" -d "$OUTPUT_DIR"
    
    echo -e "${GREEN}Extraction completed!${NC}"
    
    # Optional: Remove the zip file after extraction
    echo -e "${YELLOW}Removing zip file...${NC}"
    rm -f "$ZIP_FILE"
else
    echo -e "${YELLOW}Warning: lucifer-data.zip not found in downloaded folder${NC}"
fi

echo -e "${GREEN}Done! Files available at: $OUTPUT_DIR${NC}"

# List downloaded contents
echo -e "${YELLOW}Final contents:${NC}"
ls -lh "$OUTPUT_DIR"
