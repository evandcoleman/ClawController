"""
Gateway configuration for ClawController.

Auto-detects local vs remote mode based on environment variables.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
import os


@dataclass(frozen=True)
class GatewayConfig:
    """Configuration for connecting to the OpenClaw gateway."""

    mode: Literal["local", "remote"]
    gateway_url: Optional[str] = None
    gateway_token: Optional[str] = None
    timeout: int = 30
    tls_verify: bool = True
    openclaw_dir: Optional[Path] = None

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        """Build config from environment variables.

        If OPENCLAW_GATEWAY_URL is set, remote mode is used.
        Otherwise, local mode (subprocess + filesystem) is used.
        """
        gateway_url = os.getenv("OPENCLAW_GATEWAY_URL")

        if gateway_url:
            # Remote mode
            return cls(
                mode="remote",
                gateway_url=gateway_url.rstrip("/"),
                gateway_token=os.getenv("OPENCLAW_GATEWAY_TOKEN"),
                timeout=int(os.getenv("OPENCLAW_GATEWAY_TIMEOUT", "30")),
                tls_verify=os.getenv("OPENCLAW_GATEWAY_TLS_VERIFY", "true").lower() in ("true", "1", "yes"),
            )

        # Local mode
        openclaw_dir_env = os.getenv("OPENCLAW_DIR")
        openclaw_dir = Path(openclaw_dir_env).resolve() if openclaw_dir_env else (Path.home() / ".openclaw").resolve()

        return cls(
            mode="local",
            openclaw_dir=openclaw_dir,
        )
