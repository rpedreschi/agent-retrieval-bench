"""Variant A: orders source tools.

Backed by two stores: one for the latest order event per order_id, one for the
order_items append log per order_id.
"""
from __future__ import annotations

from typing import Any

from arb.mcp.server_base import SourceServer


def get_order(server: SourceServer, *, token: str | None, order_id: str) -> Any:
    return server.call(
        token, lambda now: server.store.get(order_id, now) or {"error": "not_found"}
    )


def list_orders_for_customer(
    server: SourceServer, *, token: str | None, customer_id: str, limit: int = 50,
) -> Any:
    def body(now: int) -> Any:
        view = server.store.view(now)
        out = [o for o in view.values() if o["customer_id"] == customer_id]
        out.sort(key=lambda o: o["occurred_at_ms"], reverse=True)
        return out[:limit]
    return server.call(token, body)


def get_order_items(
    items_server: SourceServer, *, token: str | None, order_id: str,
) -> Any:
    return items_server.call(
        token, lambda now: items_server.store.view(now).get(order_id, [])
    )
