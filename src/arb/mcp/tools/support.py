"""Variant A: support source tools."""

from __future__ import annotations

from typing import Any

from arb.mcp.server_base import SourceServer


def get_ticket(server: SourceServer, *, token: str | None, ticket_id: str) -> Any:
    return server.call(
        token, lambda now: server.store.get(ticket_id, now) or {"error": "not_found"}
    )


def list_tickets_for_customer(
    server: SourceServer,
    *,
    token: str | None,
    customer_id: str,
    limit: int = 50,
) -> Any:
    def body(now: int) -> Any:
        out = [t for t in server.store.view(now).values() if t["customer_id"] == customer_id]
        out.sort(key=lambda t: t["occurred_at_ms"], reverse=True)
        return out[:limit]

    return server.call(token, body)
