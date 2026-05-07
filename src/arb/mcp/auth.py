"""Bearer-token auth + scope check.

See docs/methodology.md §2. Variant A's token must carry every per-source
read scope; Variant B's token (Phase 3) carries only ``context:read``.

Tokens and scopes are loaded from a YAML config so experiments can rotate them
between runs without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class AuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def to_dict(self) -> dict[str, Any]:
        return {"error": "auth_error", "code": self.code, "message": str(self)}


@dataclass
class TokenRegistry:
    """Maps bearer token -> set of granted scopes."""

    tokens: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TokenRegistry:
        return cls(tokens={k: set(v) for k, v in d.get("tokens", {}).items()})

    @classmethod
    def from_yaml(cls, path: Path) -> TokenRegistry:
        return cls.from_dict(yaml.safe_load(path.read_text()))

    def check(self, token: str | None, required_scope: str) -> None:
        if not token:
            raise AuthError("missing_token", "no bearer token provided")
        scopes = self.tokens.get(token)
        if scopes is None:
            raise AuthError("unknown_token", "bearer token not recognised")
        if required_scope not in scopes:
            raise AuthError(
                "insufficient_scope",
                f"token lacks required scope {required_scope!r}",
            )
