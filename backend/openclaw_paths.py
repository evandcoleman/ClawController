from pathlib import Path
import os


def get_openclaw_dir() -> Path:
    """Resolve the OpenClaw base directory.

    Checks OPENCLAW_DIR env var, falls back to ~/.openclaw.
    """
    env = os.getenv("OPENCLAW_DIR")
    if env:
        return Path(env).resolve()
    return (Path.home() / ".openclaw").resolve()


def get_config_path() -> Path:
    return get_openclaw_dir() / "openclaw.json"


def get_agents_dir() -> Path:
    return get_openclaw_dir() / "agents"


def get_agent_sessions_dir(agent_id: str) -> Path:
    return get_agents_dir() / agent_id / "sessions"


def get_agent_dir(agent_id: str) -> Path:
    return get_agents_dir() / agent_id


def get_default_workspace(agent_id: str) -> Path:
    return get_openclaw_dir() / f"workspace-{agent_id}"


def is_within_openclaw(path: Path) -> bool:
    """Check if resolved path is within the OpenClaw directory tree."""
    return str(path.resolve()).startswith(str(get_openclaw_dir()))


def is_within_allowed(path: Path) -> bool:
    """Check if resolved path is within OpenClaw dir or /tmp."""
    resolved = str(path.resolve())
    return resolved.startswith(str(get_openclaw_dir())) or resolved.startswith("/tmp")
