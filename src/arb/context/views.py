"""Per-view metadata: primary key, accepted params, source topics, freshness SLA.

Both engines (DeltaStream and Local) consult this registry. To add a fourth
view in the future you append a ``ViewSpec`` here, ship the SQL under
``sql/views/``, and add a corresponding builder in :mod:`arb.context.local` —
the MCP interface does not change.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ViewSpec:
    name: str
    primary_key: str
    source_topics: tuple[str, ...]
    sql_path: str
    description: str


VIEWS: dict[str, ViewSpec] = {
    "customer_360": ViewSpec(
        name="customer_360",
        primary_key="customer_id",
        source_topics=(
            "retail.customers",
            "retail.customer_tier_changes",
            "retail.orders",
            "retail.support_tickets",
        ),
        sql_path="sql/views/customer_360.sql",
        description=(
            "Joined customer profile with tier history, recent orders, and "
            "open tickets. Primary key: customer_id."
        ),
    ),
    "order_state": ViewSpec(
        name="order_state",
        primary_key="order_id",
        source_topics=(
            "retail.orders",
            "retail.order_items",
            "retail.inventory_snapshots",
            "retail.payment_events",
            "retail.returns",
        ),
        sql_path="sql/views/order_state.sql",
        description=(
            "Joined order header + items + per-item inventory + payment "
            "lifecycle + open return id. Primary key: order_id."
        ),
    ),
    "returns_eligibility": ViewSpec(
        name="returns_eligibility",
        primary_key="return_id",
        source_topics=(
            "retail.returns",
            "retail.orders",
            "retail.payment_events",
        ),
        sql_path="sql/views/returns_eligibility.sql",
        description=(
            "Joined return + originating order + payment events with "
            "computed eligibility (false if a chargeback has been filed). "
            "Primary key: return_id."
        ),
    ),
}
