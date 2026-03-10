#!/bin/bash

set -e #Exit if any command fails

VERSION=$(date +%Y%m%d-%H%M)
REGISTRY="repo.digiscout.uk"
IMAGE_NAME="geoip_convert-v2-v1"

echo "Building version $VERSION..."
docker build -t $REGISTRY/$IMAGE_NAME:$VERSION -t $REGISTRY/$IMAGE_NAME:latest .

echo "Pushing to private repo..."
docker push $REGISTRY/$IMAGE_NAME:$VERSION
docker push $REGISTRY/$IMAGE_NAME:latest

echo "Done! Deployed $VERSION"