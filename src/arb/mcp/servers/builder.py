"""Programmatic builder for the six Variant A SourceServers.

Used both by the MCP entrypoints (which then attach FastMCP wiring) and by
tests (which call tool functions directly).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from arb.mcp.auth import TokenRegistry
from arb.mcp.faults import FaultProfile
from arb.mcp.server_base import SourceServer, build_source_server
from arb.serving import projectors
from arb.serving.store import FreshnessProfile

# Logical store name -> (projector, required scope, time field on the event).
_STORE_SPECS: dict[str, tuple[Any, str, str]] = {
    "customers": (projectors.customers, "customers:read", "updated_at_ms"),
    "customer_tier_changes": (projectors.customer_tier_changes, "customers:read", "occurred_at_ms"),
    "orders": (projectors.orders, "orders:read", "occurred_at_ms"),
    "order_items": (projectors.order_items, "orders:read", "occurred_at_ms"),
    "inventory": (projectors.inventory, "inventory:read", "occurred_at_ms"),
    "returns": (projectors.returns, "returns:read", "occurred_at_ms"),
    "support_tickets": (projectors.support_tickets, "support:read", "occurred_at_ms"),
    "payment_events": (projectors.payment_events, "payments:read", "occurred_at_ms"),
}

# Each server in Variant A wraps one or more stores.
SERVER_TO_STORES: dict[str, list[str]] = {
    "customers": ["customers", "customer_tier_changes"],
    "orders": ["orders", "order_items"],
    "inventory": ["inventory"],
    "returns": ["returns"],
    "support": ["support_tickets"],
    "payments": ["payment_events"],
}

STORE_TO_TOPIC: dict[str, str] = {
    "customers": "retail.customers",
    "customer_tier_changes": "retail.customer_tier_changes",
    "orders": "retail.orders",
    "order_items": "retail.order_items",
    "inventory": "retail.inventory_snapshots",
    "returns": "retail.returns",
    "support_tickets": "retail.support_tickets",
    "payment_events": "retail.payment_events",
}


@dataclass
class VariantABundle:
    """All six SourceServers, keyed by store name (so tools can grab the right one)."""
    auth: TokenRegistry
    servers: dict[str, SourceServer] = field(default_factory=dict)

    def feed(self, events_by_topic: dict[str, list[dict[str, Any]]]) -> None:
        for store_name, topic in STORE_TO_TOPIC.items():
            if store_name in self.servers:
                self.servers[store_name].store.ingest(events_by_topic.get(topic, []))


def load_variant_a(config_path: Path, *, inject_sleep: bool = True) -> VariantABundle:
    raw = yaml.safe_load(config_path.read_text())
    auth = TokenRegistry.from_dict(raw.get("auth", {}))
    sources_cfg: dict[str, Any] = raw.get("sources", {})

    bundle = VariantABundle(auth=auth)
    for server_name, store_names in SERVER_TO_STORES.items():
        scfg = sources_cfg.get(server_name, {})
        freshness = FreshnessProfile.from_dict(scfg.get("freshness"))
        fault = FaultProfile.from_dict(scfg.get("faults"))
        for store_name in store_names:
            projector, scope, time_field = _STORE_SPECS[store_name]
            srv = build_source_server(
                name=f"{server_name}:{store_name}",
                required_scope=scope,
                projector=projector,
                auth=auth,
                freshness=freshness,
                fault_profile=fault,
                seed=int(scfg.get("seed", 0)),
                inject_sleep=inject_sleep,
                time_field=time_field,
            )
            bundle.servers[store_name] = srv
    return bundle
