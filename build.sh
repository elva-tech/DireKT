#!/bin/bash
set -e

echo "==> Building React frontend..."
cd "silveredge_platform 3/silveredge_platform/frontend"
npm install
npm run build
cd ../../..

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Build complete!"
