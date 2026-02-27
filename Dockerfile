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

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --system appuser && useradd --system --gid appuser appuser

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

# Copy entrypoint script
COPY docker-entrypoint.sh ./

# Create directories and set ownership
RUN mkdir -p logs data && chown -R appuser:appuser /app

# Persistent data volume
VOLUME /app/data

# Single port — FastAPI serves API + frontend
EXPOSE 8000

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

USER appuser

CMD ["/app/docker-entrypoint.sh"]
