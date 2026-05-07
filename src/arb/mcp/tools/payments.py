"""Variant A: payments source tools."""

from __future__ import annotations

from typing import Any

from arb.mcp.server_base import SourceServer


def list_payment_events_for_order(
    server: SourceServer,
    *,
    token: str | None,
    order_id: str,
) -> Any:
    def body(now: int) -> Any:
        events = list(server.store.view(now).get(order_id, []))
        events.sort(key=lambda e: e["occurred_at_ms"])
        return events

    return server.call(token, body)
