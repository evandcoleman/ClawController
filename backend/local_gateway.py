"""
Local gateway implementations for ClawController.

Uses subprocess calls to the ``openclaw`` CLI and direct filesystem access
to ``~/.openclaw/``.  This is the default mode when ClawController runs on
the same machine as the OpenClaw gateway.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from openclaw_paths import (
    get_agent_dir,
    get_agent_sessions_dir,
    get_config_path,
    get_default_workspace,
    is_within_allowed,
    is_within_openclaw,
)

logger = logging.getLogger("clawcontroller.local_gateway")


# ── Helpers ────────────────────────────────────────────────────────────

def _validate_agent_id(agent_id: str) -> str:
    if not agent_id or not re.match(r"^[a-zA-Z0-9_-]+$", agent_id):
        raise ValueError(f"Invalid agent ID for CLI: {agent_id}")
    return agent_id


# ── AgentMessenger ─────────────────────────────────────────────────────

class LocalAgentMessenger:
    """Send messages to agents via ``openclaw agent`` CLI."""

    def send_message(self, agent_id: str, message: str) -> None:
        """Fire-and-forget message (Popen, no wait)."""
        _validate_agent_id(agent_id)
        try:
            subprocess.Popen(
                ["openclaw", "agent", "--agent", agent_id, "--message", message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(Path.home()),
            )
        except Exception as e:
            logger.error("Failed to send message to agent %s: %s", agent_id, e)

    def send_message_sync(self, agent_id: str, message: str, timeout: int = 120) -> dict:
        """Send message and wait for agent's response (blocking)."""
        _validate_agent_id(agent_id)
        result = subprocess.run(
            ["openclaw", "agent", "--agent", agent_id, "--message", message, "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path.home()),
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"raw": result.stdout.strip()}
        return {"error": result.stderr.strip() if result.stderr else "Unknown error", "returncode": result.returncode}


# ── SessionManager ─────────────────────────────────────────────────────

class LocalSessionManager:
    """Manage sessions via ``openclaw sessions`` CLI."""

    def list_sessions(self) -> dict:
        result = subprocess.run(
            ["openclaw", "sessions", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {"sessions": []}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"sessions": []}

    def spawn_session(self, agent_id: str, label: str, message: str) -> dict:
        _validate_agent_id(agent_id)
        result = subprocess.run(
            [
                "openclaw", "sessions", "spawn",
                "--agent", agent_id,
                "--label", label,
                "--message", message,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            # Fallback to direct agent command
            result = subprocess.run(
                ["openclaw", "agent", "--agent", agent_id, "--message", message],
                capture_output=True,
                text=True,
                timeout=30,
            )
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


# ── ConfigManager ──────────────────────────────────────────────────────

class LocalConfigManager:
    """Read/write ``openclaw.json`` and agent workspace files."""

    def config_exists(self) -> bool:
        return get_config_path().exists()

    def get_config(self) -> dict:
        config_path = get_config_path()
        with open(config_path) as f:
            return json.load(f)

    def write_config(self, config: dict) -> None:
        config_path = get_config_path()
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    def get_agent_list(self) -> list[dict]:
        if not self.config_exists():
            return []
        try:
            config = self.get_config()
            return config.get("agents", {}).get("list", [])
        except Exception:
            return []

    def get_agent_files(self, agent_id: str) -> dict:
        """Read SOUL.md, TOOLS.md, AGENTS.md for an agent."""
        config = self.get_config()
        agent_list = config.get("agents", {}).get("list", [])
        agent = next((a for a in agent_list if a.get("id") == agent_id), None)
        if not agent:
            raise FileNotFoundError(f"Agent '{agent_id}' not found in config")

        agent_dir = self._resolve_agent_dir(agent, agent_id)

        soul = ""
        tools = ""
        agents_md = ""
        soul_path = agent_dir / "SOUL.md"
        if soul_path.exists():
            soul = soul_path.read_text()
        tools_path = agent_dir / "TOOLS.md"
        if tools_path.exists():
            tools = tools_path.read_text()
        agents_path = agent_dir / "AGENTS.md"
        if agents_path.exists():
            agents_md = agents_path.read_text()

        return {"soul": soul, "tools": tools, "agentsMd": agents_md}

    def write_agent_files(self, agent_id: str, soul: str | None = None,
                          tools: str | None = None, agents_md: str | None = None) -> None:
        config = self.get_config()
        agent_list = config.get("agents", {}).get("list", [])
        agent = next((a for a in agent_list if a.get("id") == agent_id), None)
        if not agent:
            raise FileNotFoundError(f"Agent '{agent_id}' not found in config")

        agent_dir = self._resolve_agent_dir(agent, agent_id)
        if not agent_dir.exists():
            agent_dir.mkdir(parents=True, exist_ok=True)

        if soul is not None:
            (agent_dir / "SOUL.md").write_text(soul)
        if tools is not None:
            (agent_dir / "TOOLS.md").write_text(tools)
        if agents_md is not None:
            (agent_dir / "AGENTS.md").write_text(agents_md)

    def create_agent_workspace(self, agent_id: str, agent_entry: dict,
                               soul: str, tools: str, agents_md: str) -> dict:
        agent_dir = get_agent_dir(agent_id)
        if not is_within_openclaw(agent_dir):
            raise PermissionError("Access denied")

        workspace_path = agent_dir / "workspace"
        agent_config_dir = agent_dir / "agent"

        workspace_path.mkdir(parents=True, exist_ok=True)
        agent_config_dir.mkdir(parents=True, exist_ok=True)

        (agent_config_dir / "SOUL.md").write_text(soul)
        (agent_config_dir / "TOOLS.md").write_text(tools)
        (agent_config_dir / "AGENTS.md").write_text(agents_md)

        agent_entry["workspace"] = str(workspace_path)
        agent_entry["agentDir"] = str(agent_config_dir)
        return agent_entry

    # ── private helpers ──

    @staticmethod
    def _resolve_agent_dir(agent: dict, agent_id: str) -> Path:
        """Resolve the agent config directory with security checks and fallbacks."""
        agent_dir_raw = agent.get("agentDir", str(get_default_workspace(agent_id)))
        agent_dir = Path(agent_dir_raw).resolve()

        if not is_within_allowed(agent_dir):
            raise PermissionError("Access denied to agent directory")

        if not agent_dir.exists():
            workspace_raw = agent.get("workspace", str(get_default_workspace(agent_id)))
            workspace = Path(workspace_raw).resolve()
            if not is_within_allowed(workspace):
                raise PermissionError("Access denied to workspace directory")
            agent_dir = workspace

        return agent_dir


# ── AgentStatusProvider ────────────────────────────────────────────────

class LocalAgentStatusProvider:
    """Determine agent status from session file modification times."""

    def get_agent_status(self, agent_id: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", agent_id):
            return "OFFLINE"

        sessions_dir = get_agent_sessions_dir(agent_id)
        if not is_within_openclaw(sessions_dir):
            return "OFFLINE"
        if not sessions_dir.exists():
            return "STANDBY"

        session_files = list(sessions_dir.glob("*.jsonl"))
        if not session_files:
            return "STANDBY"

        latest_mtime = 0
        for f in session_files:
            try:
                mtime = f.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime
            except Exception:
                continue

        if latest_mtime == 0:
            return "STANDBY"

        elapsed = time.time() - latest_mtime
        if elapsed < 300:
            return "WORKING"
        elif elapsed < 1800:
            return "IDLE"
        return "STANDBY"


# ── GatewayController ─────────────────────────────────────────────────

class LocalGatewayController:
    """Check health and restart the gateway via ``openclaw`` CLI."""

    HEALTH_CHECK_TIMEOUT = 10

    async def check_health(self) -> tuple[bool, str]:
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "openclaw", "status", "--json",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=self.HEALTH_CHECK_TIMEOUT,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                try:
                    status_data = json.loads(stdout.decode())
                    gateway_info = status_data.get("gateway", {})
                    if gateway_info.get("reachable", False):
                        return True, "Gateway healthy"
                    error = gateway_info.get("error", "unreachable")
                    return False, f"Gateway status: {error}"
                except json.JSONDecodeError:
                    return False, "Gateway responding but status unreadable"
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            return False, f"Status check failed: {error_msg}"

        except asyncio.TimeoutError:
            return False, "Health check timed out"
        except Exception as e:
            return False, f"Health check error: {e}"

    async def restart(self) -> tuple[bool, str]:
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "openclaw", "gateway", "start",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=30,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                await asyncio.sleep(5)
                is_healthy, status_msg = await self.check_health()
                if is_healthy:
                    return True, "Gateway restarted successfully"
                return False, f"Gateway started but not healthy: {status_msg}"
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            return False, f"Restart command failed: {error_msg}"

        except asyncio.TimeoutError:
            return False, "Restart command timed out"
        except Exception as e:
            return False, f"Restart failed: {e}"

    def can_restart(self) -> bool:
        return True


# ── ModelCatalog ───────────────────────────────────────────────────────

class LocalModelCatalog:
    """List models via ``openclaw models list`` CLI."""

    def list_models(self) -> list[dict]:
        try:
            result = subprocess.run(
                ["openclaw", "models", "list", "--all", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(Path.home()),
            )
            if result.returncode != 0:
                return []
            data = json.loads(result.stdout)
            return data.get("models", [])
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            logger.error("Failed to list models: %s", e)
            return []
