"""
Gateway client protocols and factory for ClawController.

Defines the abstract interfaces for all gateway interactions and a factory
that builds the appropriate local or remote implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from gateway_config import GatewayConfig


# ── Protocols ──────────────────────────────────────────────────────────


@runtime_checkable
class AgentMessenger(Protocol):
    """Send messages to OpenClaw agents."""

    def send_message(self, agent_id: str, message: str) -> None:
        """Fire-and-forget message to an agent (non-blocking)."""
        ...

    def send_message_sync(self, agent_id: str, message: str, timeout: int = 120) -> dict:
        """Send message and wait for the agent's response."""
        ...


@runtime_checkable
class SessionManager(Protocol):
    """Manage OpenClaw sessions."""

    def list_sessions(self) -> dict:
        """List active sessions. Returns parsed JSON dict."""
        ...

    def spawn_session(self, agent_id: str, label: str, message: str) -> dict:
        """Spawn an isolated session for an agent."""
        ...


@runtime_checkable
class ConfigManager(Protocol):
    """Read/write OpenClaw configuration and agent files."""

    def config_exists(self) -> bool:
        ...

    def get_config(self) -> dict:
        """Return parsed openclaw.json content."""
        ...

    def write_config(self, config: dict) -> None:
        """Write config back to openclaw.json."""
        ...

    def get_agent_list(self) -> list[dict]:
        """Return the agents list from config."""
        ...

    def get_agent_files(self, agent_id: str) -> dict:
        """Return {'soul': str, 'tools': str, 'agentsMd': str} for an agent."""
        ...

    def write_agent_files(self, agent_id: str, soul: str | None = None,
                          tools: str | None = None, agents_md: str | None = None) -> None:
        """Write SOUL.md / TOOLS.md / AGENTS.md for an agent."""
        ...

    def create_agent_workspace(self, agent_id: str, agent_entry: dict,
                               soul: str, tools: str, agents_md: str) -> dict:
        """Create workspace dirs and config files for a new agent.

        Returns the agent entry dict (with workspace/agentDir filled in).
        """
        ...


@runtime_checkable
class AgentStatusProvider(Protocol):
    """Determine agent status from session activity."""

    def get_agent_status(self, agent_id: str) -> str:
        """Return one of WORKING / IDLE / STANDBY / OFFLINE."""
        ...


@runtime_checkable
class GatewayController(Protocol):
    """Health-check and restart the OpenClaw gateway."""

    async def check_health(self) -> tuple[bool, str]:
        """Return (is_healthy, status_message)."""
        ...

    async def restart(self) -> tuple[bool, str]:
        """Attempt restart. Return (success, message)."""
        ...

    def can_restart(self) -> bool:
        """Whether restart is supported in this mode."""
        ...


@runtime_checkable
class ModelCatalog(Protocol):
    """List available models."""

    def list_models(self) -> list[dict]:
        """Return list of model dicts from OpenClaw."""
        ...


# ── Composite client ──────────────────────────────────────────────────


@dataclass
class GatewayClient:
    """Composite object that holds all gateway sub-clients."""

    config: GatewayConfig
    messenger: AgentMessenger
    sessions: SessionManager
    config_manager: ConfigManager
    status: AgentStatusProvider
    controller: GatewayController
    models: ModelCatalog


# ── Factory ───────────────────────────────────────────────────────────


def create_gateway_client(config: GatewayConfig) -> GatewayClient:
    """Build the appropriate local or remote gateway client."""

    if config.mode == "remote":
        from remote_gateway import (
            RemoteAgentMessenger,
            RemoteConfigManager,
            RemoteAgentStatusProvider,
            RemoteGatewayController,
            RemoteModelCatalog,
            RemoteSessionManager,
        )
        return GatewayClient(
            config=config,
            messenger=RemoteAgentMessenger(config),
            sessions=RemoteSessionManager(config),
            config_manager=RemoteConfigManager(config),
            status=RemoteAgentStatusProvider(),
            controller=RemoteGatewayController(config),
            models=RemoteModelCatalog(),
        )

    # Local mode
    from local_gateway import (
        LocalAgentMessenger,
        LocalConfigManager,
        LocalAgentStatusProvider,
        LocalGatewayController,
        LocalModelCatalog,
        LocalSessionManager,
    )
    return GatewayClient(
        config=config,
        messenger=LocalAgentMessenger(),
        sessions=LocalSessionManager(),
        config_manager=LocalConfigManager(),
        status=LocalAgentStatusProvider(),
        controller=LocalGatewayController(),
        models=LocalModelCatalog(),
    )
