#!/bin/bash

# Check if tag is provided, default to latest if not
TAG=${1:-latest}

echo "Using tag: $TAG"

# Registry address
REGISTRY="crpi-wypvanlammbrxwe3.cn-hangzhou.personal.cr.aliyuncs.com/aivisondocker"


# Pulling images
echo "Pulling images..."
docker pull ${REGISTRY}/aivision-ai-inference:${TAG}
docker pull ${REGISTRY}/aivision-frontend:${TAG}
docker pull ${REGISTRY}/aivision-backend:${TAG}
docker pull ${REGISTRY}/aivision-model-agent:${TAG}

echo "Done."
