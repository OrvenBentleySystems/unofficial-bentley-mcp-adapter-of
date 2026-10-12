"""Microsoft Entra access-token verification for the gateway.

Signature, issuer, audience, expiry and scope checks are delegated to
FastMCP's JWTVerifier (authlib). This subclass adds the checks Entra tokens
need for a single-user workstation: mandatory exp, nbf, tenant (tid) and an
explicit allowlist of user object IDs (oid).
"""

from __future__ import annotations

import logging
import time

from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.jwt import JWTVerifier

from .config import GatewayConfig

log = logging.getLogger("staad_mcp_gateway.auth")

_CLOCK_SKEW_S = 120


class EntraUserVerifier(JWTVerifier):
    def __init__(self, cfg: GatewayConfig, **kwargs):
        if "public_key" not in kwargs:  # unit tests inject a local key; production always uses tenant JWKS
            kwargs.setdefault("jwks_uri", cfg.jwks_uri)
        super().__init__(
            issuer=cfg.issuers,
            audience=cfg.audiences,
            algorithm="RS256",
            required_scopes=cfg.required_scopes,
            **kwargs,
        )
        self._tenant_id = cfg.tenant_id
        self._allowed_oids = cfg.allowed_object_ids
        self._allowed_clients = cfg.allowed_client_ids

    async def load_access_token(self, token: str) -> AccessToken | None:
        access = await super().load_access_token(token)
        if access is None:
            log.warning("auth_reject reason=invalid_token")
            return None
        claims = access.claims or {}
        now = time.time()
        if claims.get("exp") is None:
            log.warning("auth_reject reason=missing_exp")
            return None
        nbf = claims.get("nbf")
        if nbf is not None and nbf > now + _CLOCK_SKEW_S:
            log.warning("auth_reject reason=not_yet_valid")
            return None
        if str(claims.get("tid", "")).lower() != self._tenant_id:
            log.warning("auth_reject reason=tenant_mismatch")
            return None
        oid = str(claims.get("oid", "")).lower()
        if oid not in self._allowed_oids:
            log.warning("auth_reject reason=user_not_allowed oid=%s", oid or "<none>")
            return None
        client = str(claims.get("azp") or claims.get("appid") or "").lower()
        if self._allowed_clients and client not in self._allowed_clients:
            log.warning("auth_reject reason=client_not_allowed client=%s", client or "<none>")
            return None
        return access
