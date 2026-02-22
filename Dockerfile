# Multi-stage build for ClawController
# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend
COPY backend/ ./backend/
COPY start.sh stop.sh ./

# Install Python dependencies
RUN cd backend && \
    python -m venv venv && \
    . venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create logs directory
RUN mkdir -p logs

# Single port — FastAPI serves API + frontend
EXPOSE 8000

ENV PYTHONUNBUFFERED=1

RUN echo '#!/bin/bash\n\
set -e\n\
cd /app/backend\n\
source venv/bin/activate\n\
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
