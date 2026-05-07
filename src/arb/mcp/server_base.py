"""Shared per-source server scaffolding.

Each source server in Variant A is an instance of ``SourceServer``: a serving
store + a fault injector + an auth registry + a clock. Tool functions in
``arb.mcp.tools.*`` accept a ``SourceServer`` and operate on it. The MCP
transport wiring lives in ``arb.mcp.servers.*`` and is intentionally thin so
that tool behaviour can be tested without spinning up an MCP transport.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from arb.mcp.auth import TokenRegistry
from arb.mcp.faults import FaultInjector, FaultProfile, InjectedSourceError
from arb.serving.store import FreshnessProfile, ServingStore


def default_clock_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class SourceServer:
    name: str
    required_scope: str
    store: ServingStore
    auth: TokenRegistry
    faults: FaultInjector
    clock_ms: Callable[[], int] = field(default=default_clock_ms)

    def call(self, token: str | None, fn: Callable[[int], Any]) -> Any:
        """Run a tool body with auth + fault hooks applied.

        ``fn`` receives the current clock_ms.
        """
        try:
            self.auth.check(token, self.required_scope)
            self.faults.maybe_inject()
            return fn(self.clock_ms())
        except InjectedSourceError as e:
            return e.to_dict()
        except Exception as e:  # auth errors carry to_dict; others re-raise
            to_dict = getattr(e, "to_dict", None)
            if callable(to_dict):
                return to_dict()
            raise


def build_source_server(
    *,
    name: str,
    required_scope: str,
    projector: Callable[[dict[Any, Any], dict[str, Any]], None],
    auth: TokenRegistry,
    freshness: FreshnessProfile,
    fault_profile: FaultProfile,
    seed: int = 0,
    clock_ms: Callable[[], int] | None = None,
    inject_sleep: bool = True,
    time_field: str = "occurred_at_ms",
) -> SourceServer:
    store = ServingStore(name=name, projector=projector, profile=freshness, time_field=time_field)
    rng = np.random.default_rng(seed)
    faults = FaultInjector(profile=fault_profile, rng=rng, sleep=inject_sleep)
    return SourceServer(
        name=name,
        required_scope=required_scope,
        store=store,
        auth=auth,
        faults=faults,
        clock_ms=clock_ms or default_clock_ms,
    )
