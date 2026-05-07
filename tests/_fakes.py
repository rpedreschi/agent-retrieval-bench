"""In-test fakes. NOT shipped — only imported from tests/.

These exist so the MCP / auth / wiring layers can be exercised in CI without
standing up DeltaStream. They are deliberately dumb: no real join semantics,
just a lookup table keyed by primary key. Tests that need real view semantics
must be marked as integration tests and run against DeltaStream.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from arb.context.engine import ViewQuery, ViewResult


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class FakeContextEngine:
    """Returns whatever was preloaded via ``put``. No join logic."""

    engine_name: str = "fake"
    clock_ms: Callable[[], int] = field(default=_now_ms)
    _data: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def put(self, view: str, key: str, payload: dict[str, Any]) -> None:
        self._data[(view, key)] = payload

    def get_view(self, query: ViewQuery) -> ViewResult:
        # Use the first param value as the key — good enough for unit tests.
        key = next(iter(query.params.values()), "") if query.params else ""
        payload = self._data.get((query.name, str(key)))
        if payload is None:
            return ViewResult(
                name=query.name,
                engine=self.engine_name,
                payload=None,
                visible_at_ms=self.clock_ms(),
                error={"error": "not_found", "view": query.name, "key": key},
            )
        return ViewResult(
            name=query.name,
            engine=self.engine_name,
            payload=payload,
            visible_at_ms=self.clock_ms(),
        )

    def close(self) -> None:
        return None
