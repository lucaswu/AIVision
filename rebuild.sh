#!/bin/bash
set -e
echo "Building backend..."
docker build -t aivision-backend:latest -f backEnd/api_gateway/Dockerfile .

echo "Building frontend..."
docker build -t aivision-frontend:latest ./frontEnd

echo "Building AI inference..."
cd model/weld
docker build -t aivision-ai-inference:latest -f Dockerfile.ai .
cd ../..

echo "Restarting services..."
cd deploy
docker compose down
docker compose up -d

echo "Done!"
