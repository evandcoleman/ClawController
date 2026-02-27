#!/bin/bash
set -e

cd /app/backend
source venv/bin/activate

# Ensure data directory exists (volume mount may be empty)
mkdir -p /app/data

# Redirect stderr to stdout so all logs go to a single stream
# (some log drivers only capture stdout)
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info 2>&1
