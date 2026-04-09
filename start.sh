#!/bin/bash
cd "silveredge_platform 3/silveredge_platform/backend"
uvicorn main:app --host 0.0.0.0 --port $PORT
