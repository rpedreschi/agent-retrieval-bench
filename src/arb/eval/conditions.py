"""Apply one of three conditions to a Variant A bundle / Variant B engine.

The conditions are the headline experimental axis. Every task runs under each:

- ``clean``: no fault injection, default freshness, default scopes.
- ``degraded``: latency added to one randomly-chosen source per task; 5%
  error rate on a different randomly-chosen source. Replication lag and
  cache TTL are unchanged — they're the *baseline* freshness profile.
- ``adversarial``: degraded + a schema-drift event injected at the task's
  midpoint (one topic gains an optional field, one enum value changes).
  The drift is implemented as a marker on the task; the world generator
  honours it when present.

Condition selection is seeded so a (task_id, condition, seed) triple
reproduces the exact same fault profile across runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from arb.mcp.faults import FaultProfile
from arb.mcp.servers.builder import SERVER_TO_STORES, VariantABundle


class Condition(StrEnum):
    CLEAN = "clean"
    DEGRADED = "degraded"
    ADVERSARIAL = "adversarial"


@dataclass
class AppliedCondition:
    condition: Condition
    latency_source: str | None = None
    error_source: str | None = None
    schema_drift: bool = False


def apply_condition(
    bundle: VariantABundle,
    condition: Condition,
    *,
    seed: int,
) -> AppliedCondition:
    """Mutate ``bundle``'s servers in place to reflect the requested condition.

    Variant B's engine is unaffected: its single SLA already reflects the
    streaming engine's natural freshness. Variant B's degraded behaviour
    arises from the same upstream Kafka topics having degraded sources, not
    from the context engine being slow.
    """
    if condition is Condition.CLEAN:
        for srv in bundle.servers.values():
            srv.faults.profile = FaultProfile()
        return AppliedCondition(condition=condition)

    rng = np.random.default_rng(seed)
    sources = list(SERVER_TO_STORES.keys())
    latency_src = sources[int(rng.integers(0, len(sources)))]
    remaining = [s for s in sources if s != latency_src]
    error_src = remaining[int(rng.integers(0, len(remaining)))]

    for store_name, srv in bundle.servers.items():
        # Map store_name back to its server name.
        owning_server = next(s for s, stores in SERVER_TO_STORES.items() if store_name in stores)
        if owning_server == latency_src:
            srv.faults.profile = FaultProfile(latency_ms=200)
        elif owning_server == error_src:
            srv.faults.profile = FaultProfile(
                error_rate=0.05,
                error_code="source_timeout",
            )
        else:
            srv.faults.profile = FaultProfile()

    return AppliedCondition(
        condition=condition,
        latency_source=latency_src,
        error_source=error_src,
        schema_drift=(condition is Condition.ADVERSARIAL),
    )
