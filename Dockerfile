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

# Install system dependencies + Caddy binary
RUN apt-get update && apt-get install -y curl \
    && curl -sL "https://caddyserver.com/api/download?os=linux&arch=amd64" -o /usr/local/bin/caddy \
    && chmod +x /usr/local/bin/caddy \
    && rm -rf /var/lib/apt/lists/*

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

# Copy Caddyfile
COPY Caddyfile /app/Caddyfile

# Expose single port (Caddy proxies both frontend + API)
EXPOSE 5001

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV BACKEND_PORT=8000
ENV FRONTEND_PORT=5001

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "🚀 Starting ClawController..."\n\
\n\
# Start backend\n\
cd /app/backend\n\
source venv/bin/activate\n\
python -m uvicorn main:app --host 127.0.0.1 --port 8000 &\n\
BACKEND_PID=$!\n\
echo "Backend started (PID: $BACKEND_PID)"\n\
\n\
# Start Caddy (reverse proxy + static files on port 5001)\n\
cd /app\n\
caddy run --config /app/Caddyfile &\n\
CADDY_PID=$!\n\
echo "Caddy started (PID: $CADDY_PID)"\n\
\n\
echo ""\n\
echo "Dashboard: http://localhost:5001"\n\
echo ""\n\
\n\
# Wait for any process to exit\n\
wait -n\n\
\n\
# Exit with status of process that exited first\n\
exit $?\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
