"""Per-source event projectors.

Each projector mutates a view dict in place from one ingested event.
"""

from __future__ import annotations

from typing import Any


def customers(view: dict[str, dict[str, Any]], event: dict[str, Any]) -> None:
    cid = event["customer_id"]
    prev = view.get(cid)
    if prev is None or event.get("version", 0) >= prev.get("version", 0):
        view[cid] = dict(event)


def customer_tier_changes(view: dict[str, list[dict[str, Any]]], event: dict[str, Any]) -> None:
    view.setdefault(event["customer_id"], []).append(dict(event))


def orders(view: dict[str, dict[str, Any]], event: dict[str, Any]) -> None:
    # Latest event per order_id wins (status field is the lifecycle state).
    oid = event["order_id"]
    cur = view.get(oid)
    if cur is None or event["occurred_at_ms"] >= cur["occurred_at_ms"]:
        view[oid] = dict(event)


def order_items(view: dict[str, list[dict[str, Any]]], event: dict[str, Any]) -> None:
    view.setdefault(event["order_id"], []).append(dict(event))


def inventory(view: dict[tuple[str, str], dict[str, Any]], event: dict[str, Any]) -> None:
    key = (event["sku"], event["warehouse_id"])
    cur = view.get(key)
    if cur is None or event["occurred_at_ms"] >= cur["occurred_at_ms"]:
        view[key] = dict(event)


def returns(view: dict[str, dict[str, Any]], event: dict[str, Any]) -> None:
    rid = event["return_id"]
    cur = view.get(rid)
    if cur is None or event["occurred_at_ms"] >= cur["occurred_at_ms"]:
        view[rid] = dict(event)


def support_tickets(view: dict[str, dict[str, Any]], event: dict[str, Any]) -> None:
    tid = event["ticket_id"]
    cur = view.get(tid)
    if cur is None or event["occurred_at_ms"] >= cur["occurred_at_ms"]:
        view[tid] = dict(event)


def payment_events(view: dict[str, list[dict[str, Any]]], event: dict[str, Any]) -> None:
    view.setdefault(event["order_id"], []).append(dict(event))
