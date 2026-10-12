"""Gateway configuration, loaded from environment variables only.

No secrets are required: the gateway validates Microsoft Entra access tokens
using the tenant's public signing keys. Upstream is always a project-owned
OpenSTAAD MCP child process over stdio; no upstream URL is configurable.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Microsoft Enterprise token store client ID used by Microsoft 365 Copilot for
# Entra SSO plugin tokens (Microsoft Learn: plugin-authentication-entra-sso).
ENTERPRISE_TOKEN_STORE_CLIENT_ID = "ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b"


class ConfigError(ValueError):
    pass


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").replace(";", ",").split(",") if v.strip()]


@dataclass(frozen=True)
class GatewayConfig:
    tenant_id: str
    audiences: list[str]
    allowed_object_ids: frozenset[str]
    required_scopes: list[str]
    allowed_client_ids: frozenset[str] = frozenset({ENTERPRISE_TOKEN_STORE_CLIENT_ID})
    port: int = 18130
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    upstream_timeout_s: float = 30.0
    max_body_bytes: int = 64 * 1024

    @property
    def issuers(self) -> list[str]:
        # v2.0 and v1.0 issuer formats for this tenant only.
        return [
            f"https://login.microsoftonline.com/{self.tenant_id}/v2.0",
            f"https://sts.windows.net/{self.tenant_id}/",
        ]

    @property
    def jwks_uri(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "GatewayConfig":
        env = dict(os.environ if env is None else env)
        tenant = env.get("STAAD_GW_TENANT_ID", "").strip()
        if not _GUID.match(tenant):
            raise ConfigError("STAAD_GW_TENANT_ID must be the Entra tenant GUID")
        audiences = _split(env.get("STAAD_GW_AUDIENCES"))
        if not audiences:
            raise ConfigError("STAAD_GW_AUDIENCES must list the Entra app client ID and/or Application ID URI")
        oids = _split(env.get("STAAD_GW_ALLOWED_OIDS"))
        if not oids or not all(_GUID.match(o) for o in oids):
            raise ConfigError("STAAD_GW_ALLOWED_OIDS must list one or more Entra user object ID GUIDs")
        scopes = _split(env.get("STAAD_GW_REQUIRED_SCOPES", "access_as_user"))
        clients = _split(env.get("STAAD_GW_ALLOWED_CLIENT_IDS", ENTERPRISE_TOKEN_STORE_CLIENT_ID))
        if not clients or not all(_GUID.match(c) for c in clients):
            raise ConfigError("STAAD_GW_ALLOWED_CLIENT_IDS must list client application ID GUIDs")
        port = int(env.get("STAAD_GW_PORT", "18130"))
        if not 1024 <= port <= 65535:
            raise ConfigError("STAAD_GW_PORT must be between 1024 and 65535")
        return cls(
            tenant_id=tenant.lower(),
            audiences=audiences,
            allowed_object_ids=frozenset(o.lower() for o in oids),
            required_scopes=scopes,
            allowed_client_ids=frozenset(c.lower() for c in clients),
            port=port,
            log_dir=Path(env.get("STAAD_GW_LOG_DIR", "logs")),
            upstream_timeout_s=float(env.get("STAAD_GW_UPSTREAM_TIMEOUT_S", "30")),
            max_body_bytes=int(env.get("STAAD_GW_MAX_BODY_BYTES", str(64 * 1024))),
        )
