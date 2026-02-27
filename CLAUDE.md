# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

ClawController is a task management dashboard for [OpenClaw](https://openclaw.ai) AI agents. It provides a Kanban board, real-time agent status, squad chat, recurring tasks, and a review gate workflow. Agents interact via REST API; the dashboard updates live via WebSockets.

## Architecture

**Backend:** Python FastAPI monolith (`backend/main.py`) — all endpoints, WebSocket handler, Pydantic schemas, and business logic live in this single file. SQLAlchemy models in `models.py`, DB setup in `database.py`.

**Frontend:** React 19 + Vite + Tailwind CSS v4. Zustand store (`frontend/src/store/useMissionStore.js`) manages all client state. API calls centralized in `frontend/src/api.js`. API base URL is derived from `window.location.origin` (same-origin).

**Database:** SQLite at `data/mission_control.db`. Auto-created on startup. Schema migrations are manual ALTER TABLE statements in `database.py:_run_migrations()`.

**Single-port production mode:** In Docker, FastAPI serves both the API (`/api/*`) and the built frontend static files on port 8000. In development, the frontend runs separately on port 5001.

**Background services** (started as asyncio tasks in `main.py`):
- `stuck_task_monitor.py` — detects tasks stuck too long in a status
- `gateway_watchdog.py` — monitors/restarts the OpenClaw gateway process

## Key Domain Concepts

- **Task lifecycle:** `INBOX → ASSIGNED → IN_PROGRESS → REVIEW → DONE`
- **Agent roles:** `LEAD` (one, reviews tasks), `INT` (workers), `SPC` (specialists)
- **Agent statuses:** `WORKING`, `IDLE`, `STANDBY`, `OFFLINE`
- **API auth:** `X-API-Key` header checked by middleware; key from `CLAW_API_KEY` env var (default: `claw-default-key`)
- **Agent source of truth:** Agents are primarily loaded from OpenClaw config (`~/.openclaw/openclaw.json`), not from the DB

## Development Commands

```bash
# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install

# Run backend (with hot reload)
cd backend && source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Run frontend (dev server)
cd frontend
npm run dev -- --port 5001 --host 0.0.0.0

# Start both (background, logs to ./logs/)
./start.sh

# Stop both
./stop.sh

# Frontend lint
cd frontend && npm run lint

# Build frontend for production
cd frontend && npm run build

# Docker build
docker build -t clawcontroller .
```

## Environment Variables

- `CLAW_API_KEY` — API authentication key (default: `claw-default-key`)
- `DATABASE_URL` — SQLAlchemy DB URL (default: `sqlite:///<project>/data/mission_control.db`)
- `OPENCLAW_DIR` — Path to OpenClaw directory (default: `~/.openclaw`)

## Code Style

- **Python:** PEP 8
- **JavaScript:** ESLint (config in `frontend/eslint.config.js`)
- **Frontend uses `python-dotenv`** — backend loads `.env` from working directory at startup
