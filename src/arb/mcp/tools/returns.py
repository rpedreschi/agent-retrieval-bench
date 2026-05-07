"""Variant A: returns source tools."""

from __future__ import annotations

from typing import Any

from arb.mcp.server_base import SourceServer


def get_return(server: SourceServer, *, token: str | None, return_id: str) -> Any:
    return server.call(
        token, lambda now: server.store.get(return_id, now) or {"error": "not_found"}
    )


def list_returns_for_order(
    server: SourceServer,
    *,
    token: str | None,
    order_id: str,
) -> Any:
    def body(now: int) -> Any:
        return [r for r in server.store.view(now).values() if r["order_id"] == order_id]

    return server.call(token, body)
