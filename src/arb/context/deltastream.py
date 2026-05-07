"""DeltaStream-backed ContextEngine — production backend for Variant B.

Reads the three materialised views (defined in ``sql/views/*.sql``) over
DeltaStream's REST API. Credentials come from the environment, never from a
checked-in config:

- ``ARB_DELTASTREAM_URL``
- ``ARB_DELTASTREAM_TOKEN``
- ``ARB_DELTASTREAM_DATABASE``

Imports of the DeltaStream client are deferred so the rest of the harness
(and the test suite) can run without it installed.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from arb.context.engine import ViewQuery, ViewResult
from arb.context.schemas import validate_view_payload
from arb.context.views import VIEWS


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class DeltaStreamContextEngine:
    url: str = field(default_factory=lambda: os.environ.get("ARB_DELTASTREAM_URL", ""))
    token: str = field(default_factory=lambda: os.environ.get("ARB_DELTASTREAM_TOKEN", ""))
    database: str = field(default_factory=lambda: os.environ.get("ARB_DELTASTREAM_DATABASE", ""))
    engine_name: str = "deltastream"
    clock_ms: Callable[[], int] = field(default=_now_ms)
    _client: Any = field(init=False, default=None)

    def __post_init__(self) -> None:
        if not (self.url and self.token and self.database):
            raise RuntimeError(
                "DeltaStream credentials missing. Set ARB_DELTASTREAM_URL, "
                "ARB_DELTASTREAM_TOKEN, ARB_DELTASTREAM_DATABASE (see .env.example)."
            )
        # Lazy import — keeps the rest of the harness usable without the SDK.
        try:
            import httpx  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "DeltaStreamContextEngine requires httpx. Install with: uv pip install httpx"
            ) from e

    def get_view(self, query: ViewQuery) -> ViewResult:
        spec = VIEWS.get(query.name)
        if spec is None:
            return ViewResult(
                name=query.name,
                engine=self.engine_name,
                payload=None,
                visible_at_ms=self.clock_ms(),
                error={"error": "unknown_view", "view": query.name},
            )
        pk_value = query.params.get(spec.primary_key)
        if not pk_value:
            return ViewResult(
                name=spec.name,
                engine=self.engine_name,
                payload=None,
                visible_at_ms=self.clock_ms(),
                error={
                    "error": "missing_param",
                    "view": spec.name,
                    "required": spec.primary_key,
                },
            )
        sql = f"SELECT * FROM {spec.name} WHERE {spec.primary_key} = :pk LIMIT 1"
        rows = self._exec(sql, {"pk": pk_value})
        if not rows:
            return ViewResult(
                name=spec.name,
                engine=self.engine_name,
                payload=None,
                visible_at_ms=self.clock_ms(),
                error={"error": "not_found", "view": spec.name, "key": pk_value},
            )
        payload = rows[0]
        validate_view_payload(spec.name, payload)
        return ViewResult(
            name=spec.name,
            engine=self.engine_name,
            payload=payload,
            visible_at_ms=self.clock_ms(),
        )

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    # ----- transport -----

    def _exec(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:  # pragma: no cover
        import httpx

        if self._client is None:
            self._client = httpx.Client(
                base_url=self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10.0,
            )
        resp = self._client.post(
            "/v1/query",
            json={"database": self.database, "sql": sql, "params": params},
        )
        resp.raise_for_status()
        return list(resp.json().get("rows", []))
