from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.common import AdapterError


class ProviderPreflightError(AdapterError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProviderContext:
    provider_id: str
    descriptor: dict[str, Any]
    profile_path: Path
    profile: dict[str, Any]
    machine: dict[str, Any]
    settings: dict[str, Any]
    generated_at: str
