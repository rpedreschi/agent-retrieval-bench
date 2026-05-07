"""Variant A: inventory source tools."""

from __future__ import annotations

from typing import Any

from arb.mcp.server_base import SourceServer


def get_stock(
    server: SourceServer,
    *,
    token: str | None,
    sku: str,
    warehouse_id: str,
) -> Any:
    return server.call(
        token,
        lambda now: server.store.get((sku, warehouse_id), now) or {"error": "not_found"},
    )


def list_stock_for_sku(server: SourceServer, *, token: str | None, sku: str) -> Any:
    def body(now: int) -> Any:
        return [v for (s, _wh), v in server.store.view(now).items() if s == sku]

    return server.call(token, body)
