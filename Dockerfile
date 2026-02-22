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

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
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

# Expose ports
EXPOSE 8000 5001

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
python -m uvicorn main:app --host 0.0.0.0 --port ${BACKEND_PORT} &\n\
BACKEND_PID=$!\n\
echo "Backend started (PID: $BACKEND_PID)"\n\
\n\
# Serve frontend static files with Python\n\
cd /app/frontend/dist\n\
python -m http.server ${FRONTEND_PORT} &\n\
FRONTEND_PID=$!\n\
echo "Frontend started (PID: $FRONTEND_PID)"\n\
\n\
echo ""\n\
echo "Dashboard: http://localhost:${FRONTEND_PORT}"\n\
echo "API: http://localhost:${BACKEND_PORT}"\n\
echo ""\n\
\n\
# Wait for any process to exit\n\
wait -n\n\
\n\
# Exit with status of process that exited first\n\
exit $?\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
