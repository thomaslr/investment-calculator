#!/bin/bash

# Update Investment Calculator Docker Container

echo "Stopping existing container..."
docker stop investment-calculator 2>/dev/null || true

echo "Removing existing container..."
docker rm investment-calculator 2>/dev/null || true

echo "Removing old image to force fresh pull..."
docker rmi thomaslr/investment-calculator:latest 2>/dev/null || true

echo "Pulling latest image from DockerHub..."
docker pull thomaslr/investment-calculator:latest

echo "Starting new container..."
docker run -d --name investment-calculator -p 5174:80 --restart unless-stopped thomaslr/investment-calculator:latest

echo "Done! Container is running."
echo "Access at http://localhost:5174"
