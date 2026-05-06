"""Variant A: customers source tools.

Two topics live behind this server: retail.customers (latest record per
customer_id) and retail.customer_tier_changes (append-only event log per
customer). The customer-tier history view is fed via a sibling ServingStore.
"""
from __future__ import annotations

from typing import Any

from arb.mcp.server_base import SourceServer


def get_customer(server: SourceServer, *, token: str | None, customer_id: str) -> Any:
    return server.call(
        token, lambda now: server.store.get(customer_id, now) or {"error": "not_found"}
    )


def get_customer_tier_history(
    history_server: SourceServer, *, token: str | None, customer_id: str
) -> Any:
    return history_server.call(
        token, lambda now: history_server.store.view(now).get(customer_id, [])
    )
