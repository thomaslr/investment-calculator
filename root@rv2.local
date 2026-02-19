#!/bin/bash
CONTAINER_NAME="investment-calculator"
IMAGE_NAME="thomaslr/investment-calculator:latest"
PORT="5173"

echo "Stopping running container..."
docker stop $CONTAINER_NAME || true

echo "Removing existing container..."
docker rm $CONTAINER_NAME || true

echo "Pulling latest image from Docker Hub..."
docker pull $IMAGE_NAME

echo "Starting new container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "$PORT":80 \
  "$IMAGE_NAME"

echo "Pruning old images..."
docker image prune -f

echo "Done! Container updated."
