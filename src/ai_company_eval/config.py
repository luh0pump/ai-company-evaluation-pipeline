"""Explicit, fail-closed configuration shared by the CLI and web entry points."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _flag(name: str) -> bool:
    value = os.getenv(name, "false").strip().lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return value == "true"


@dataclass(frozen=True)
class Settings:
    mode: str = "portfolio"
    allow_live_fetch: bool = False
    allow_live_providers: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"portfolio", "local"}:
            raise ValueError("APP_MODE must be portfolio or local")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            mode=os.getenv("APP_MODE", "portfolio").strip().lower(),
            allow_live_fetch=_flag("ALLOW_LIVE_FETCH"),
            allow_live_providers=_flag("ALLOW_LIVE_PROVIDERS"),
        )

    @property
    def live_fetch_enabled(self) -> bool:
        return self.mode == "local" and self.allow_live_fetch

    def live_model(self, provider: str, model: str | None) -> str:
        if self.mode != "local" or not self.allow_live_providers:
            raise ValueError("Live providers require APP_MODE=local and ALLOW_LIVE_PROVIDERS=true")
        prefix = provider.upper()
        if not os.getenv(f"{prefix}_API_KEY", "").strip():
            raise ValueError(f"{prefix}_API_KEY is required")
        resolved = (model or os.getenv(f"{prefix}_MODEL", "")).strip()
        if not resolved:
            raise ValueError(f"Set --model or {prefix}_MODEL for this provider")
        return resolved
