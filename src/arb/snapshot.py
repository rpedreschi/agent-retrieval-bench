"""Deterministic snapshot of WorldState used for grading.

The snapshot is the *frozen ground truth* against which the grader compares
agent output. See docs/methodology.md.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from arb.world.state import WorldState


def snapshot_dict(state: WorldState) -> dict[str, Any]:
    """Serialise WorldState to a deterministic dict.

    All collections are sorted by their natural key so output is byte-identical
    across runs with the same seed.
    """
    return {
        "tenant_id": state.tenant_id,
        "warehouses": sorted(state.warehouses),
        "skus": sorted(state.skus),
        "customers": [
            asdict(state.customers[k]) for k in sorted(state.customers)
        ],
        "orders": [
            {
                **{f: getattr(state.orders[k], f) for f in (
                    "order_id", "customer_id", "total_cents",
                    "currency", "created_at_ms",
                )},
                "status": state.orders[k].status.value,
                "items": [asdict(it) for it in state.orders[k].items],
            }
            for k in sorted(state.orders)
        ],
        "inventory": [
            {"sku": sku, "warehouse_id": wh, "quantity_on_hand": inv.quantity_on_hand}
            for (sku, wh), inv in sorted(state.inventory.items())
        ],
        "returns": [
            {
                "return_id": r.return_id,
                "order_id": r.order_id,
                "status": r.status.value,
                "reason": r.reason,
                "amount_cents": r.amount_cents,
            }
            for k, r in sorted(state.returns.items())
        ],
        "tickets": [
            {
                "ticket_id": t.ticket_id,
                "customer_id": t.customer_id,
                "order_id": t.order_id,
                "status": t.status.value,
                "subject": t.subject,
            }
            for k, t in sorted(state.tickets.items())
        ],
    }


def write_snapshot(state: WorldState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot_dict(state), sort_keys=True, indent=2))
