"""
Remote gateway implementations for ClawController.

Uses HTTP calls (via ``httpx``) to the OpenClaw gateway.
Activated when ``OPENCLAW_GATEWAY_URL`` is set.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from gateway_config import GatewayConfig

logger = logging.getLogger("clawcontroller.remote_gateway")


class NotAvailableInRemoteMode(Exception):
    """Raised when an operation is not supported in remote mode."""


# ── Helpers ────────────────────────────────────────────────────────────

def _build_client(config: GatewayConfig) -> httpx.Client:
    headers = {}
    if config.gateway_token:
        headers["Authorization"] = f"Bearer {config.gateway_token}"
    return httpx.Client(
        base_url=config.gateway_url,
        headers=headers,
        timeout=config.timeout,
        verify=config.tls_verify,
    )


# ── AgentMessenger ─────────────────────────────────────────────────────

class RemoteAgentMessenger:
    """Send messages to agents via the gateway HTTP API."""

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    def send_message(self, agent_id: str, message: str) -> None:
        """Fire-and-forget via POST /hooks/agent."""
        try:
            with _build_client(self._config) as client:
                client.post("/hooks/agent", json={"agent": agent_id, "message": message})
        except Exception as e:
            logger.error("Remote send_message failed for agent %s: %s", agent_id, e)

    def send_message_sync(self, agent_id: str, message: str, timeout: int = 120) -> dict:
        """Synchronous message via POST /v1/chat/completions (OpenAI-compatible)."""
        try:
            with _build_client(self._config) as client:
                resp = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": f"openclaw:{agent_id}",
                        "messages": [{"role": "user", "content": message}],
                    },
                    timeout=timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                # Extract text from OpenAI-format response
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    return {"result": {"payloads": [{"text": content}]}}
                return data
        except httpx.TimeoutException:
            return {"error": "Agent response timed out"}
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}


# ── SessionManager ─────────────────────────────────────────────────────

class RemoteSessionManager:
    """Manage sessions via POST /tools/invoke."""

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    def list_sessions(self) -> dict:
        """Session listing is not available remotely; return empty."""
        return {"sessions": []}

    def spawn_session(self, agent_id: str, label: str, message: str) -> dict:
        """Spawn session via POST /tools/invoke."""
        try:
            with _build_client(self._config) as client:
                resp = client.post(
                    "/tools/invoke",
                    json={
                        "tool": "sessions_spawn",
                        "args": {
                            "agent": agent_id,
                            "label": label,
                            "message": message,
                        },
                    },
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            return {"error": "Session spawn timed out"}
        except Exception as e:
            logger.error("Remote spawn_session failed: %s", e)
            return {"error": str(e)}


# ── ConfigManager ──────────────────────────────────────────────────────

class RemoteConfigManager:
    """Config management is not available in remote mode.

    Read operations return empty/safe defaults.
    Write operations raise ``NotAvailableInRemoteMode``.
    """

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    def config_exists(self) -> bool:
        # In remote mode, config is not directly accessible
        return False

    def get_config(self) -> dict:
        raise NotAvailableInRemoteMode("OpenClaw config is not accessible in remote mode")

    def write_config(self, config: dict) -> None:
        raise NotAvailableInRemoteMode("Cannot write OpenClaw config in remote mode")

    def get_agent_list(self) -> list[dict]:
        return []

    def get_agent_files(self, agent_id: str) -> dict:
        raise NotAvailableInRemoteMode("Agent files are not accessible in remote mode")

    def write_agent_files(self, agent_id: str, soul: str | None = None,
                          tools: str | None = None, agents_md: str | None = None) -> None:
        raise NotAvailableInRemoteMode("Cannot write agent files in remote mode")

    def create_agent_workspace(self, agent_id: str, agent_entry: dict,
                               soul: str, tools: str, agents_md: str) -> dict:
        raise NotAvailableInRemoteMode("Cannot create agent workspaces in remote mode")


# ── AgentStatusProvider ────────────────────────────────────────────────

class RemoteAgentStatusProvider:
    """Session files are not accessible remotely; status comes from DB only."""

    def get_agent_status(self, agent_id: str) -> str:
        return "UNKNOWN"


# ── GatewayController ─────────────────────────────────────────────────

class RemoteGatewayController:
    """Health checks via HTTP; restart is not supported remotely."""

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    async def check_health(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(
                base_url=self._config.gateway_url,
                headers={"Authorization": f"Bearer {self._config.gateway_token}"} if self._config.gateway_token else {},
                timeout=self._config.timeout,
                verify=self._config.tls_verify,
            ) as client:
                resp = await client.get("/")
                if resp.is_success:
                    return True, "Gateway healthy"
                return False, f"Gateway returned HTTP {resp.status_code}"
        except httpx.TimeoutException:
            return False, "Health check timed out"
        except Exception as e:
            return False, f"Health check error: {e}"

    async def restart(self) -> tuple[bool, str]:
        return False, "Gateway restart is not available in remote mode"

    def can_restart(self) -> bool:
        return False


# ── ModelCatalog ───────────────────────────────────────────────────────

class RemoteModelCatalog:
    """Model listing is not available remotely."""

    def list_models(self) -> list[dict]:
        return []
