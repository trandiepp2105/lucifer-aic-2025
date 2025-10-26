#!/bin/bash

# Setup script to install Docker and Docker Compose
# Usage: ./setup.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Docker & Docker Compose Setup Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Please do not run this script as root (without sudo)${NC}"
    echo -e "${YELLOW}The script will ask for sudo password when needed${NC}"
    exit 1
fi

# Update package index
echo -e "${GREEN}[1/6] Updating package index...${NC}"
sudo apt-get update

# Install prerequisites
echo -e "${GREEN}[2/6] Installing prerequisites...${NC}"
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
echo -e "${GREEN}[3/6] Adding Docker's official GPG key...${NC}"
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up Docker repository
echo -e "${GREEN}[4/6] Setting up Docker repository...${NC}"
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index again
sudo apt-get update

# Install Docker Engine, CLI, containerd, and Docker Compose plugin
echo -e "${GREEN}[5/6] Installing Docker Engine and Docker Compose...${NC}"
sudo apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

# Add current user to docker group
echo -e "${GREEN}[6/6] Adding current user to docker group...${NC}"
sudo usermod -aG docker $USER

# Verify installation
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verifying Installation${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "${YELLOW}Docker version:${NC}"
docker --version

echo -e "${YELLOW}Docker Compose version:${NC}"
docker compose version

# Check if NVIDIA Container Toolkit should be installed
echo ""
echo -e "${YELLOW}Do you want to install NVIDIA Container Toolkit for GPU support? (y/n)${NC}"
read -r install_nvidia

if [[ "$install_nvidia" =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Installing NVIDIA Container Toolkit...${NC}"
    
    # Add NVIDIA Container Toolkit repository
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
    
    # Configure Docker to use NVIDIA runtime
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    
    echo -e "${GREEN}NVIDIA Container Toolkit installed successfully!${NC}"
fi

# Final instructions
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Installation completed successfully!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo -e "You need to ${RED}log out and log back in${NC} (or restart your system)"
echo -e "for the docker group changes to take effect."
echo ""
echo -e "After logging back in, verify Docker works without sudo:"
echo -e "  ${BLUE}docker run hello-world${NC}"
echo ""
echo -e "To start using Docker Compose:"
echo -e "  ${BLUE}docker compose up -d${NC}"
echo ""
