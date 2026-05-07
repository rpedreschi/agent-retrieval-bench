from __future__ import annotations

from arb.world.generator import InMemorySink, run
from arb.world.state import PaymentEventKind, ReturnStatus


def test_chargeback_downgrade_refund_scenario_fires(laptop_config) -> None:
    sink = InMemorySink()
    run(laptop_config, sink, seed=42)
    by_topic = sink.by_topic()

    chargebacks = [
        e
        for e in by_topic.get("retail.payment_events", [])
        if e["kind"] == PaymentEventKind.CHARGEBACK.value
    ]
    assert len(chargebacks) >= 1, "scenario should produce at least one chargeback"

    downgrades = [
        e
        for e in by_topic.get("retail.customer_tier_changes", [])
        if e["reason"] == "chargeback_auto_downgrade"
    ]
    assert len(downgrades) >= 1
    # Downgrade must move strictly down the ladder.
    ladder = ["BRONZE", "SILVER", "GOLD", "PLATINUM"]
    for e in downgrades:
        assert ladder.index(e["to_tier"]) < ladder.index(e["from_tier"])

    rejected = [
        e
        for e in by_topic.get("retail.returns", [])
        if e["status"] == ReturnStatus.REJECTED.value and e["reason"] == "chargeback_already_filed"
    ]
    assert len(rejected) >= 1

    # All three artifacts must point at the same order.
    order_ids = {e["order_id"] for e in chargebacks}
    rej_orders = {e["order_id"] for e in rejected}
    assert order_ids & rej_orders


def test_avro_schema_files_present(schemas_dir) -> None:
    expected = [
        "customers.avsc",
        "customer_tier_changes.avsc",
        "orders.avsc",
        "order_items.avsc",
        "inventory_snapshots.avsc",
        "returns.avsc",
        "support_tickets.avsc",
        "payment_events.avsc",
    ]
    for name in expected:
        assert (schemas_dir / name).exists(), f"missing schema {name}"
