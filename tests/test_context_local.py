"""Tests for LocalContextEngine — semantics and freshness SLA."""
from __future__ import annotations

import pytest

from arb.context.engine import ViewQuery
from arb.context.local import LocalContextEngine
from arb.context.schemas import Customer360, OrderState, ReturnsEligibility
from arb.world.generator import InMemorySink, run


@pytest.fixture
def fed_engine(laptop_config):
    sink = InMemorySink()
    run(laptop_config, sink, seed=42)
    eng = LocalContextEngine(
        freshness_sla_ms={"customer_360": 0, "order_state": 0, "returns_eligibility": 0},
        clock_ms=lambda: 10**13,
    )
    eng.feed(sink.by_topic())
    return eng, sink


def test_unknown_view_returns_error(fed_engine) -> None:
    eng, _ = fed_engine
    res = eng.get_view(ViewQuery(name="nope"))
    assert res.error == {"error": "unknown_view", "view": "nope"}


def test_customer_360_validates_against_schema(fed_engine) -> None:
    eng, sink = fed_engine
    cid = sink.by_topic()["retail.customers"][0]["customer_id"]
    res = eng.get_view(ViewQuery(name="customer_360", params={"customer_id": cid}))
    assert res.payload is not None
    Customer360.model_validate(res.payload)
    assert res.payload["customer_id"] == cid


def test_order_state_includes_items_inventory_and_payments(fed_engine) -> None:
    eng, sink = fed_engine
    oid = sink.by_topic()["retail.orders"][0]["order_id"]
    res = eng.get_view(ViewQuery(name="order_state", params={"order_id": oid}))
    payload = OrderState.model_validate(res.payload).model_dump()
    assert payload["order_id"] == oid
    assert isinstance(payload["items"], list) and len(payload["items"]) >= 1
    skus_in_items = {it["sku"] for it in payload["items"]}
    skus_in_inv = {row["sku"] for row in payload["inventory_for_items"]}
    assert skus_in_items >= skus_in_inv


def test_returns_eligibility_flips_on_chargeback(fed_engine) -> None:
    """The chargeback_downgrade_refund scenario must drive eligible_for_refund=False."""
    eng, sink = fed_engine
    chargebacks = [
        e for e in sink.by_topic().get("retail.payment_events", [])
        if e["kind"] == "CHARGEBACK"
    ]
    assert chargebacks, "scenario must produce at least one chargeback"
    target_oid = chargebacks[0]["order_id"]
    rejected = [
        e for e in sink.by_topic().get("retail.returns", [])
        if e["order_id"] == target_oid
    ]
    assert rejected, "scenario must produce a return on the chargeback'd order"
    rid = rejected[0]["return_id"]
    res = eng.get_view(ViewQuery(name="returns_eligibility", params={"return_id": rid}))
    payload = ReturnsEligibility.model_validate(res.payload).model_dump()
    assert payload["has_chargeback"] is True
    assert payload["eligible_for_refund"] is False
    assert payload["ineligibility_reason"] == "chargeback_already_filed"


def test_missing_param_returns_not_found(fed_engine) -> None:
    eng, _ = fed_engine
    res = eng.get_view(ViewQuery(name="customer_360", params={}))
    assert res.error is not None
    assert res.error["error"] == "not_found"


def test_unknown_key_returns_not_found(fed_engine) -> None:
    eng, _ = fed_engine
    res = eng.get_view(ViewQuery(name="customer_360", params={"customer_id": "ghost"}))
    assert res.error == {"error": "not_found", "view": "customer_360", "key": "ghost"}


def test_freshness_sla_hides_recent_events(laptop_config) -> None:
    sink = InMemorySink()
    run(laptop_config, sink, seed=7)
    # SLA equal to the entire run window — every event is "in the future"
    # relative to the engine's view of now.
    big_sla = laptop_config.duration_sec * 2000
    eng = LocalContextEngine(
        freshness_sla_ms={"customer_360": big_sla},
        clock_ms=lambda: laptop_config.start_epoch_ms,
    )
    eng.feed(sink.by_topic())
    cid = sink.by_topic()["retail.customers"][0]["customer_id"]
    res = eng.get_view(ViewQuery(name="customer_360", params={"customer_id": cid}))
    # Customer was created at start_epoch_ms; with a huge SLA pushing the
    # cutoff into the past, even the bootstrap upsert is not yet visible.
    assert res.error is not None
    assert res.error["error"] == "not_found"


def test_engine_tag_is_local(fed_engine) -> None:
    eng, sink = fed_engine
    cid = sink.by_topic()["retail.customers"][0]["customer_id"]
    res = eng.get_view(ViewQuery(name="customer_360", params={"customer_id": cid}))
    assert res.engine == "local"
    assert res.to_tool_response()["engine"] == "local"
