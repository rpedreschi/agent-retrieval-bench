"""ContextEngine protocol — the single retrieval interface Variant B exposes.

Implementations:

- :class:`arb.context.local.LocalContextEngine` — in-process; for laptop mode
  and as a reference oracle. Tagged ``engine=local`` in traces.
- :class:`arb.context.deltastream.DeltaStreamContextEngine` — production
  backend; produces the headline benchmark numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ViewQuery:
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    limit: int | None = None


@dataclass
class ViewResult:
    name: str
    engine: str  # "deltastream" | "local" | "<byo>"
    payload: dict[str, Any] | None
    visible_at_ms: int
    error: dict[str, Any] | None = None

    def to_tool_response(self) -> dict[str, Any]:
        if self.error is not None:
            return self.error
        return {
            "view": self.name,
            "engine": self.engine,
            "visible_at_ms": self.visible_at_ms,
            "payload": self.payload,
        }


class ContextEngine(Protocol):
    """Single retrieval interface for Variant B."""

    engine_name: str

    def get_view(self, query: ViewQuery) -> ViewResult: ...
    def close(self) -> None: ...
