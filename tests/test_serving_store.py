from __future__ import annotations

from arb.serving import projectors
from arb.serving.store import FreshnessProfile, ServingStore


def test_replication_lag_hides_recent_events() -> None:
    store = ServingStore(
        name="orders",
        projector=projectors.orders,
        profile=FreshnessProfile(replication_lag_ms=1000),
    )
    store.ingest(
        [
            {"order_id": "o1", "customer_id": "c1", "occurred_at_ms": 1000, "status": "CREATED"},
            {"order_id": "o2", "customer_id": "c1", "occurred_at_ms": 5000, "status": "CREATED"},
        ]
    )
    # At now=2000 only the o1 event is visible (occurred_at_ms<=2000-1000=1000).
    assert store.get("o1", 2000)["order_id"] == "o1"
    assert store.get("o2", 2000) is None
    # At now=6000 both events are visible.
    assert store.get("o2", 6000)["order_id"] == "o2"


def test_cache_ttl_serves_stale_value() -> None:
    store = ServingStore(
        name="customers",
        projector=projectors.customers,
        profile=FreshnessProfile(cache_ttl_ms=1000),
    )
    store.ingest(
        [
            {"customer_id": "c1", "tier": "BRONZE", "occurred_at_ms": 100, "version": 1},
        ]
    )
    first = store.get("c1", 200)
    assert first["tier"] == "BRONZE"
    # New event arrives but cache pins the old value within TTL.
    store.ingest(
        [
            {"customer_id": "c1", "tier": "GOLD", "occurred_at_ms": 300, "version": 2},
        ]
    )
    cached = store.get("c1", 500)
    assert cached["tier"] == "BRONZE"
    # After TTL elapses, the fresh value surfaces.
    fresh = store.get("c1", 1500)
    assert fresh["tier"] == "GOLD"


def test_view_returns_full_projection() -> None:
    store = ServingStore(name="returns", projector=projectors.returns)
    store.ingest(
        [
            {
                "return_id": "r1",
                "order_id": "o1",
                "occurred_at_ms": 1,
                "status": "REQUESTED",
                "reason": "x",
                "amount_cents": 0,
            },
            {
                "return_id": "r2",
                "order_id": "o1",
                "occurred_at_ms": 2,
                "status": "APPROVED",
                "reason": "y",
                "amount_cents": 0,
            },
        ]
    )
    v = store.view(now_ms=10)
    assert set(v.keys()) == {"r1", "r2"}
