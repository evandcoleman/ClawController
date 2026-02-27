#!/bin/bash
export HOME="${HOME:-$(eval echo ~$(whoami))}"
# ClawController - Start Script
# Starts both backend and frontend services

set -e

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "🚀 Starting ClawController..."
echo ""

# Create logs directory
mkdir -p "$LOGS_DIR"

# Check if setup has been run
if [ ! -d "$BACKEND_DIR/venv" ]; then
    echo "❌ Backend not set up. Run: clawcontroller setup"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "❌ Frontend not set up. Run: clawcontroller setup"
    exit 1
fi

# Kill any existing processes
pkill -f "uvicorn main:app.*8000" 2>/dev/null || true
pkill -f "vite.*5001" 2>/dev/null || true

# Wait up to 5s for processes to actually terminate
for i in $(seq 1 10); do
    pgrep -f "uvicorn main:app.*8000" >/dev/null 2>&1 || pgrep -f "vite.*5001" >/dev/null 2>&1 || break
    sleep 0.5
done

# Start backend
echo "Starting backend..."
cd "$BACKEND_DIR"
source venv/bin/activate
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 > "$LOGS_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Start frontend
echo "Starting frontend..."
cd "$FRONTEND_DIR"
nohup npm run dev -- --port 5001 --host 0.0.0.0 > "$LOGS_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# Wait for services to start
sleep 3

# Verify services
echo ""
echo "Service Status:"
if kill -0 $BACKEND_PID 2>/dev/null; then
    echo "  ✅ Backend running (PID: $BACKEND_PID)"
else
    echo "  ❌ Backend failed - check $LOGS_DIR/backend.log"
fi

if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "  ✅ Frontend running (PID: $FRONTEND_PID)"
else
    echo "  ❌ Frontend failed - check $LOGS_DIR/frontend.log"
fi

echo ""
echo "Dashboard: http://localhost:5001"
echo "API:       http://localhost:8000"
echo ""
echo "Logs: $LOGS_DIR/"
