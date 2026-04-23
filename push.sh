#!/bin/bash

# Check if tag is provided, default to latest if not
TAG=${1:-latest}

echo "Using tag: $TAG"

# Registry address
REGISTRY="crpi-wypvanlammbrxwe3.cn-hangzhou.personal.cr.aliyuncs.com/aivisondocker"

# Tagging images
echo "Tagging images..."
docker tag aivision-ai-inference:latest ${REGISTRY}/aivision-ai-inference:${TAG}
docker tag aivision-frontend:latest ${REGISTRY}/aivision-frontend:${TAG}
docker tag aivision-backend:latest ${REGISTRY}/aivision-backend:${TAG}

# Pushing images
echo "Pushing images..."
docker push ${REGISTRY}/aivision-ai-inference:${TAG}
docker push ${REGISTRY}/aivision-frontend:${TAG}
docker push ${REGISTRY}/aivision-backend:${TAG}

echo "Done."
