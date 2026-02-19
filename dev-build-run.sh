#!/bin/bash

# Configuration
CONTAINER_NAME="investment-calculator"
IMAGE_NAME="thomaslr/investment-calculator:latest"
PORT="5173"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting update process for $CONTAINER_NAME...${NC}"

# 1. Build the image locally (to include changes)
echo "Building local image..."
if docker build -t "$IMAGE_NAME" .; then
    echo -e "${GREEN}Successfully built new image.${NC}"
else
    echo -e "${RED}Failed to build image. Aborting update.${NC}"
    exit 1
fi

# 2. Stop the existing container
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo "Stopping running container..."
    docker stop "$CONTAINER_NAME"
fi

# 3. Remove the container (stopped or running)
if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "Removing old container..."
    docker rm "$CONTAINER_NAME"
fi

# 4. Prune old images (optional, to save space)
echo "Cleaning up old dangling images..."
docker image prune -f

# 5. Run the new container
echo "Starting new container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart always \
  -p "$PORT":80 \
  "$IMAGE_NAME"

# 6. Verify success
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo -e "${GREEN}Update Complete! Container is running on port $PORT.${NC}"
else
    echo -e "${RED}Error: Container failed to start.${NC}"
    exit 1
fi
