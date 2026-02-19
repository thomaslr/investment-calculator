#!/bin/bash
# =============================================================================
# Multi-Architecture Build Script for Investment Calculator
# Builds and pushes Docker image for: linux/amd64, linux/arm64, linux/riscv64
#
# Usage:
#   ./build-multiarch.sh              # Build & push all 3 architectures
#   ./build-multiarch.sh --local      # Build only for current arch (local testing)
#   ./build-multiarch.sh --no-cache   # Build without Docker cache
#   ./build-multiarch.sh --clean      # Remove existing builder & recreate fresh
# =============================================================================

set -euo pipefail

# Configuration
IMAGE_NAME="thomaslr/investment-calculator"
TAG="latest"
PLATFORMS="linux/amd64,linux/arm64,linux/riscv64"
BUILDER_NAME="multiarch-builder"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Parse arguments
LOCAL_ONLY=false
NO_CACHE=""
CLEAN=false
for arg in "$@"; do
    case $arg in
        --local)
            LOCAL_ONLY=true
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            ;;
        --clean)
            CLEAN=true
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${NC}"
            echo "Usage: $0 [--local] [--no-cache] [--clean]"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}=== Multi-Architecture Docker Build ===${NC}"
echo "Image: ${IMAGE_NAME}:${TAG}"

# ---------------------------------------------------------------------------
# Local build mode: single architecture, loads to local Docker
# ---------------------------------------------------------------------------
if [ "$LOCAL_ONLY" = true ]; then
    echo -e "${YELLOW}Building for local architecture only...${NC}"
    docker build ${NO_CACHE} -t "${IMAGE_NAME}:${TAG}" .
    echo -e "${GREEN}Local build complete! Run with:${NC}"
    echo "  docker run -d --name investment-calculator -p 5173:80 ${IMAGE_NAME}:${TAG}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Multi-arch build mode: all platforms, push to registry
# ---------------------------------------------------------------------------

# --- QEMU Setup (using tonistiigi/binfmt, recommended for Apple Silicon) ---
echo -e "${YELLOW}Setting up QEMU for cross-platform builds...${NC}"
if ! docker run --rm --privileged tonistiigi/binfmt --install all; then
    echo -e "${RED}Failed to install QEMU binfmt handlers.${NC}"
    echo -e "${YELLOW}Make sure Docker Desktop is running and try again.${NC}"
    exit 1
fi
echo -e "${GREEN}QEMU setup complete.${NC}"

# --- Buildx Builder Setup ---

# Helper: remove the builder if it exists
remove_builder() {
    if docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
        echo -e "${YELLOW}Removing existing builder '${BUILDER_NAME}'...${NC}"
        docker buildx rm "${BUILDER_NAME}" 2>/dev/null || true
    fi
}

# Helper: create and bootstrap the builder
create_builder() {
    echo -e "${YELLOW}Creating buildx builder '${BUILDER_NAME}'...${NC}"
    docker buildx create --name "${BUILDER_NAME}" \
        --driver docker-container \
        --platform "${PLATFORMS}" \
        --use
    echo -e "${YELLOW}Bootstrapping builder (pulling buildkit image)...${NC}"
    if ! docker buildx inspect --bootstrap "${BUILDER_NAME}"; then
        echo -e "${RED}Bootstrap failed. Removing broken builder and retrying...${NC}"
        docker buildx rm "${BUILDER_NAME}" 2>/dev/null || true
        sleep 2
        docker buildx create --name "${BUILDER_NAME}" \
            --driver docker-container \
            --platform "${PLATFORMS}" \
            --use
        if ! docker buildx inspect --bootstrap "${BUILDER_NAME}"; then
            echo -e "${RED}Builder bootstrap failed after retry.${NC}"
            echo -e "${YELLOW}Try restarting Docker Desktop and running again.${NC}"
            exit 1
        fi
    fi
    echo -e "${GREEN}Builder '${BUILDER_NAME}' is ready.${NC}"
}

# Force-clean the builder if --clean was passed
if [ "$CLEAN" = true ]; then
    remove_builder
fi

# Create builder if it doesn't exist, or verify the existing one is healthy
if ! docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
    create_builder
else
    echo -e "${YELLOW}Checking existing builder '${BUILDER_NAME}'...${NC}"
    docker buildx use "${BUILDER_NAME}"
    # Verify the builder is actually healthy by bootstrapping it
    if ! docker buildx inspect --bootstrap "${BUILDER_NAME}" >/dev/null 2>&1; then
        echo -e "${RED}Existing builder is broken. Recreating...${NC}"
        remove_builder
        create_builder
    else
        echo -e "${GREEN}Builder '${BUILDER_NAME}' is healthy.${NC}"
    fi
fi

# Build and push for all platforms
echo -e "${YELLOW}Building for platforms: ${PLATFORMS}${NC}"
echo -e "${YELLOW}This may take a while (riscv64 numpy builds from source)...${NC}"

docker buildx build \
    ${NO_CACHE} \
    --platform "${PLATFORMS}" \
    --tag "${IMAGE_NAME}:${TAG}" \
    --push \
    .

echo ""
echo -e "${GREEN}=== Build Complete! ===${NC}"
echo -e "Image pushed: ${IMAGE_NAME}:${TAG}"
echo -e "Platforms: ${PLATFORMS}"
echo ""
echo "Verify with:"
echo "  docker buildx imagetools inspect ${IMAGE_NAME}:${TAG}"
