"""Per-source serving layer.

Each source MCP server in Variant A reads from its own ServingStore. The store
ingests Kafka events (or, in tests, events from an InMemorySink) and projects
them into the read-side state the tools serve.

Two knobs simulate the real-world inconsistency that motivates Variant B:

- ``replication_lag_ms`` — the store's visible state lags wall-clock by this
  many ms. Concretely: queries at time ``now`` see only events whose
  ``occurred_at_ms <= now - replication_lag_ms``.
- ``cache_ttl_ms`` — once a record has been served, callers may receive the
  same record again for up to ``cache_ttl_ms`` even if a fresher event has
  since been ingested. Models a read-through cache in front of a serving DB.

These knobs are configured per-source in ``config/variant_a.yaml`` and are the
mechanism by which the benchmark exposes Variant A to realistic per-source
freshness profiles.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FreshnessProfile:
    replication_lag_ms: int = 0
    cache_ttl_ms: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> FreshnessProfile:
        if not d:
            return cls()
        return cls(
            replication_lag_ms=int(d.get("replication_lag_ms", 0)),
            cache_ttl_ms=int(d.get("cache_ttl_ms", 0)),
        )


# A projector takes (current_state, event) and returns updated_state in place.
Projector = Callable[[dict[Any, Any], dict[str, Any]], None]


@dataclass
class ServingStore:
    """In-memory eventually-consistent store.

    The store keeps every ingested event in arrival order plus a projected
    "view" dict. Reads at time T see only events with occurred_at_ms <=
    T - replication_lag_ms.
    """
    name: str
    projector: Projector
    profile: FreshnessProfile = field(default_factory=FreshnessProfile)
    time_field: str = "occurred_at_ms"
    _events: list[dict[str, Any]] = field(default_factory=list)
    _last_applied_idx: int = -1
    _view: dict[Any, Any] = field(default_factory=dict)
    _last_visible_at: int = -1
    _cache_first_served_at: dict[Any, int] = field(default_factory=dict)
    _cache_value: dict[Any, Any] = field(default_factory=dict)

    def ingest(self, events: Iterable[dict[str, Any]]) -> None:
        for e in events:
            self._events.append(e)

    def _apply_visible(self, now_ms: int) -> None:
        cutoff = now_ms - self.profile.replication_lag_ms
        if cutoff <= self._last_visible_at:
            return
        for i in range(self._last_applied_idx + 1, len(self._events)):
            e = self._events[i]
            if e[self.time_field] > cutoff:
                break
            self.projector(self._view, e)
            self._last_applied_idx = i
        self._last_visible_at = cutoff

    def get(self, key: Any, now_ms: int) -> Any:
        """Look up a key honouring replication lag and cache TTL."""
        self._apply_visible(now_ms)
        ttl = self.profile.cache_ttl_ms
        if ttl > 0 and key in self._cache_first_served_at:
            served_at = self._cache_first_served_at[key]
            if now_ms - served_at <= ttl:
                return self._cache_value.get(key)
        value = self._view.get(key)
        if ttl > 0:
            self._cache_first_served_at[key] = now_ms
            self._cache_value[key] = value
        return value

    def view(self, now_ms: int) -> dict[Any, Any]:
        """Whole-projection view (used for list / scan style queries)."""
        self._apply_visible(now_ms)
        return self._view
