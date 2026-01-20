#!/bin/bash
# Deploy script for ABA Notes
# Usage: ./deploy.sh

set -e

echo "==> Fetching changes..."
git fetch --all

echo "==> Updating..."
git reset --hard origin/main

echo "==> Stopping containers..."
docker compose down

echo "==> Rebuilding and starting containers..."
docker compose up -d --build

echo "==> Done! Checking status..."
docker compose ps
