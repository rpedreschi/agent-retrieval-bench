"""End-to-end Variant A tool tests.

Run the world generator, feed its events into the Variant A bundle, then call
each tool through SourceServer.call so auth + freshness behaviour are exercised.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from arb.mcp.servers.builder import load_variant_a
from arb.mcp.tools import customers as t_customers
from arb.mcp.tools import inventory as t_inventory
from arb.mcp.tools import orders as t_orders
from arb.mcp.tools import payments as t_payments
from arb.mcp.tools import returns as t_returns
from arb.mcp.tools import support as t_support
from arb.world.generator import InMemorySink, run

REPO_ROOT = Path(__file__).resolve().parent.parent
TOKEN = "arb-variant-a-token"


@pytest.fixture
def fed_bundle(laptop_config):
    sink = InMemorySink()
    run(laptop_config, sink, seed=42)
    bundle = load_variant_a(REPO_ROOT / "config" / "variant_a.yaml", inject_sleep=False)
    bundle.feed(sink.by_topic())
    # Pin all server clocks to far in the future so replication lag doesn't hide events.
    for srv in bundle.servers.values():
        srv.clock_ms = lambda: 10**13
    return bundle, sink


def test_get_customer_returns_record(fed_bundle) -> None:
    bundle, sink = fed_bundle
    cid = sink.by_topic()["retail.customers"][0]["customer_id"]
    res = t_customers.get_customer(bundle.servers["customers"], token=TOKEN, customer_id=cid)
    assert res["customer_id"] == cid


def test_get_customer_unknown_returns_not_found(fed_bundle) -> None:
    bundle, _ = fed_bundle
    res = t_customers.get_customer(bundle.servers["customers"], token=TOKEN, customer_id="nope")
    assert res == {"error": "not_found"}


def test_get_order_and_items(fed_bundle) -> None:
    bundle, sink = fed_bundle
    oid = sink.by_topic()["retail.orders"][0]["order_id"]
    o = t_orders.get_order(bundle.servers["orders"], token=TOKEN, order_id=oid)
    assert o["order_id"] == oid
    items = t_orders.get_order_items(bundle.servers["order_items"], token=TOKEN, order_id=oid)
    assert isinstance(items, list)


def test_inventory_lookup(fed_bundle) -> None:
    bundle, sink = fed_bundle
    snap = sink.by_topic()["retail.inventory_snapshots"][0]
    res = t_inventory.get_stock(
        bundle.servers["inventory"], token=TOKEN,
        sku=snap["sku"], warehouse_id=snap["warehouse_id"],
    )
    assert res["sku"] == snap["sku"]


def test_returns_lookup(fed_bundle) -> None:
    bundle, sink = fed_bundle
    rs = sink.by_topic().get("retail.returns", [])
    if not rs:
        pytest.skip("no returns produced this run")
    rid = rs[0]["return_id"]
    r = t_returns.get_return(bundle.servers["returns"], token=TOKEN, return_id=rid)
    assert r["return_id"] == rid


def test_support_tickets_for_customer(fed_bundle) -> None:
    bundle, sink = fed_bundle
    tix = sink.by_topic().get("retail.support_tickets", [])
    if not tix:
        pytest.skip("no tickets produced this run")
    cid = tix[0]["customer_id"]
    out = t_support.list_tickets_for_customer(
        bundle.servers["support_tickets"], token=TOKEN, customer_id=cid,
    )
    assert any(t["customer_id"] == cid for t in out)


def test_payment_events_for_order(fed_bundle) -> None:
    bundle, sink = fed_bundle
    pe = sink.by_topic().get("retail.payment_events", [])
    if not pe:
        pytest.skip("no payment events this run")
    oid = pe[0]["order_id"]
    out = t_payments.list_payment_events_for_order(
        bundle.servers["payment_events"], token=TOKEN, order_id=oid,
    )
    assert all(e["order_id"] == oid for e in out)


def test_tool_call_without_token_returns_auth_error(fed_bundle) -> None:
    bundle, sink = fed_bundle
    cid = sink.by_topic()["retail.customers"][0]["customer_id"]
    res = t_customers.get_customer(
        bundle.servers["customers"], token=None, customer_id=cid,
    )
    assert res == {
        "error": "auth_error",
        "code": "missing_token",
        "message": "no bearer token provided",
    }


def test_tool_call_with_wrong_scope_returns_auth_error(fed_bundle) -> None:
    bundle, sink = fed_bundle
    # Hand-craft a token that only has support:read; calling get_customer must fail.
    bundle.auth.tokens["support-only"] = {"support:read"}
    cid = sink.by_topic()["retail.customers"][0]["customer_id"]
    res = t_customers.get_customer(
        bundle.servers["customers"], token="support-only", customer_id=cid,
    )
    assert res["error"] == "auth_error"
    assert res["code"] == "insufficient_scope"
