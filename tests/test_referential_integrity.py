from __future__ import annotations

from arb.world.generator import InMemorySink, run


def test_state_invariants_hold(laptop_config) -> None:
    sink = InMemorySink()
    state = run(laptop_config, sink, seed=42)
    state.check_invariants()


def test_emitted_events_are_referentially_consistent(laptop_config) -> None:
    sink = InMemorySink()
    run(laptop_config, sink, seed=42)
    by_topic = sink.by_topic()

    customer_ids = {e["customer_id"] for e in by_topic.get("retail.customers", [])}
    order_ids = {e["order_id"] for e in by_topic.get("retail.orders", [])}
    skus = {e["sku"] for e in by_topic.get("retail.inventory_snapshots", [])}

    # orders -> customers
    for e in by_topic.get("retail.orders", []):
        assert e["customer_id"] in customer_ids
    # order_items -> orders + skus
    for e in by_topic.get("retail.order_items", []):
        assert e["order_id"] in order_ids
        assert e["sku"] in skus
    # returns -> orders
    for e in by_topic.get("retail.returns", []):
        assert e["order_id"] in order_ids
    # support_tickets -> customers (and orders, when present)
    for e in by_topic.get("retail.support_tickets", []):
        assert e["customer_id"] in customer_ids
        if e["order_id"] is not None:
            assert e["order_id"] in order_ids
    # payment_events -> orders
    for e in by_topic.get("retail.payment_events", []):
        assert e["order_id"] in order_ids
    # tier_changes -> customers
    for e in by_topic.get("retail.customer_tier_changes", []):
        assert e["customer_id"] in customer_ids


def test_all_eight_topics_emitted(laptop_config) -> None:
    sink = InMemorySink()
    run(laptop_config, sink, seed=42)
    topics = set(sink.by_topic().keys())
    expected = {
        "retail.customers", "retail.customer_tier_changes",
        "retail.orders", "retail.order_items",
        "retail.inventory_snapshots", "retail.returns",
        "retail.support_tickets", "retail.payment_events",
    }
    # tier_changes only fires via scenarios, but the laptop config schedules one.
    assert expected.issubset(topics), f"missing: {expected - topics}"
