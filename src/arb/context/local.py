"""In-process reference implementation of ContextEngine.

NOT the system under test. See docs/byo_streaming.md and the docstring of
:mod:`arb.context`.

Implementation notes: the local engine holds raw events per topic and assembles
each view at read time by filtering events with ``time_field <= now - sla``.
This is intentionally not the same execution model as DeltaStream (which
maintains the joins continuously), but the externally-observable result on a
fixed input is identical, which is what the equivalence tests in Phase 6 will
assert.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from arb.context.engine import ViewQuery, ViewResult
from arb.context.schemas import validate_view_payload
from arb.context.views import VIEWS, ViewSpec

# Per topic: which timestamp field to use when applying the freshness cutoff.
_TIME_FIELDS: dict[str, str] = {
    "retail.customers": "updated_at_ms",
    "retail.customer_tier_changes": "occurred_at_ms",
    "retail.orders": "occurred_at_ms",
    "retail.order_items": "occurred_at_ms",
    "retail.inventory_snapshots": "occurred_at_ms",
    "retail.returns": "occurred_at_ms",
    "retail.support_tickets": "occurred_at_ms",
    "retail.payment_events": "occurred_at_ms",
}

_ALL_TOPICS = tuple(_TIME_FIELDS.keys())


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class LocalContextEngine:
    freshness_sla_ms: dict[str, int]  # per-view-name SLA
    engine_name: str = "local"
    clock_ms: Callable[[], int] = field(default=_now_ms)
    _events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for topic in _ALL_TOPICS:
            self._events.setdefault(topic, [])

    def feed(self, events_by_topic: dict[str, list[dict[str, Any]]]) -> None:
        for topic, events in events_by_topic.items():
            if topic in self._events:
                self._events[topic].extend(events)

    def get_view(self, query: ViewQuery) -> ViewResult:
        spec = VIEWS.get(query.name)
        if spec is None:
            return ViewResult(
                name=query.name,
                engine=self.engine_name,
                payload=None,
                visible_at_ms=self.clock_ms(),
                error={"error": "unknown_view", "view": query.name},
            )
        sla = self.freshness_sla_ms.get(spec.name, 0)
        visible_at = self.clock_ms() - sla
        try:
            payload = self._build(spec, query, visible_at)
        except _NotFoundError as e:
            return ViewResult(
                name=spec.name,
                engine=self.engine_name,
                payload=None,
                visible_at_ms=visible_at,
                error={"error": "not_found", "view": spec.name, "key": e.key},
            )
        validate_view_payload(spec.name, payload)
        return ViewResult(
            name=spec.name,
            engine=self.engine_name,
            payload=payload,
            visible_at_ms=visible_at,
        )

    def close(self) -> None:
        return None

    # ----- helpers -----

    def _visible(self, topic: str, at_ms: int) -> list[dict[str, Any]]:
        tf = _TIME_FIELDS[topic]
        return [e for e in self._events[topic] if e[tf] <= at_ms]

    @staticmethod
    def _latest_by(
        events: list[dict[str, Any]], key: str, time_field: str
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for e in events:
            k = e[key]
            cur = out.get(k)
            if cur is None or e[time_field] >= cur[time_field]:
                out[k] = e
        return out

    # ----- view assembly -----

    def _build(self, spec: ViewSpec, q: ViewQuery, at_ms: int) -> dict[str, Any]:
        if spec.name == "customer_360":
            return self._customer_360(q, at_ms)
        if spec.name == "order_state":
            return self._order_state(q, at_ms)
        if spec.name == "returns_eligibility":
            return self._returns_eligibility(q, at_ms)
        raise _NotFoundError(spec.name, "unimplemented")

    def _customer_360(self, q: ViewQuery, at_ms: int) -> dict[str, Any]:
        cid = q.params.get("customer_id")
        if not cid:
            raise _NotFoundError("customer_360", "missing customer_id")

        customers = self._latest_by(
            self._visible("retail.customers", at_ms),
            key="customer_id",
            time_field="updated_at_ms",
        )
        c = customers.get(cid)
        if c is None:
            raise _NotFoundError("customer_360", cid)

        tier_history = sorted(
            (
                e
                for e in self._visible("retail.customer_tier_changes", at_ms)
                if e["customer_id"] == cid
            ),
            key=lambda e: e["occurred_at_ms"],
        )
        tier_history = [
            {k: e[k] for k in ("from_tier", "to_tier", "reason", "occurred_at_ms")}
            for e in tier_history
        ]

        orders_latest = self._latest_by(
            self._visible("retail.orders", at_ms),
            key="order_id",
            time_field="occurred_at_ms",
        )
        recent_orders = sorted(
            (o for o in orders_latest.values() if o["customer_id"] == cid),
            key=lambda o: o["occurred_at_ms"],
            reverse=True,
        )[: (q.limit or 20)]
        recent_orders = [
            {k: o[k] for k in ("order_id", "status", "total_cents", "currency", "occurred_at_ms")}
            for o in recent_orders
        ]

        tickets_latest = self._latest_by(
            self._visible("retail.support_tickets", at_ms),
            key="ticket_id",
            time_field="occurred_at_ms",
        )
        open_tickets = sorted(
            (
                t
                for t in tickets_latest.values()
                if t["customer_id"] == cid and t["status"] in ("OPEN", "PENDING")
            ),
            key=lambda t: t["occurred_at_ms"],
            reverse=True,
        )
        open_tickets = [
            {k: t[k] for k in ("ticket_id", "order_id", "status", "subject", "occurred_at_ms")}
            for t in open_tickets
        ]

        return {
            "customer_id": cid,
            "email": c["email"],
            "name": c["name"],
            "tier": c["tier"],
            "updated_at_ms": c["updated_at_ms"],
            "tier_history": tier_history,
            "recent_orders": recent_orders,
            "open_tickets": open_tickets,
        }

    def _order_state(self, q: ViewQuery, at_ms: int) -> dict[str, Any]:
        oid = q.params.get("order_id")
        if not oid:
            raise _NotFoundError("order_state", "missing order_id")

        orders_latest = self._latest_by(
            self._visible("retail.orders", at_ms),
            key="order_id",
            time_field="occurred_at_ms",
        )
        o = orders_latest.get(oid)
        if o is None:
            raise _NotFoundError("order_state", oid)

        item_events = [
            e for e in self._visible("retail.order_items", at_ms) if e["order_id"] == oid
        ]
        items_latest = self._latest_by(
            item_events, key="order_item_id", time_field="occurred_at_ms"
        )
        items = [
            {
                k: it[k]
                for k in (
                    "order_item_id",
                    "sku",
                    "quantity",
                    "unit_price_cents",
                    "warehouse_id",
                )
            }
            for it in items_latest.values()
        ]

        inventory_latest_all = self._latest_by_pair(
            self._visible("retail.inventory_snapshots", at_ms),
            keys=("sku", "warehouse_id"),
            time_field="occurred_at_ms",
        )
        inv_for_items: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for it in items:
            key = (it["sku"], it["warehouse_id"])
            if key in seen:
                continue
            seen.add(key)
            row = inventory_latest_all.get(key)
            if row is not None:
                inv_for_items.append(
                    {
                        "sku": row["sku"],
                        "warehouse_id": row["warehouse_id"],
                        "quantity_on_hand": row["quantity_on_hand"],
                        "occurred_at_ms": row["occurred_at_ms"],
                    }
                )

        payments = sorted(
            (e for e in self._visible("retail.payment_events", at_ms) if e["order_id"] == oid),
            key=lambda e: e["occurred_at_ms"],
        )
        payments_clean = [
            {k: p[k] for k in ("kind", "amount_cents", "currency", "occurred_at_ms")}
            for p in payments
        ]

        returns_latest = self._latest_by(
            self._visible("retail.returns", at_ms),
            key="return_id",
            time_field="occurred_at_ms",
        )
        open_return_id: str | None = None
        for r in returns_latest.values():
            if r["order_id"] == oid and r["status"] in ("REQUESTED", "APPROVED", "RECEIVED"):
                open_return_id = r["return_id"]
                break

        return {
            "order_id": oid,
            "customer_id": o["customer_id"],
            "status": o["status"],
            "total_cents": o["total_cents"],
            "currency": o["currency"],
            "occurred_at_ms": o["occurred_at_ms"],
            "items": items,
            "inventory_for_items": inv_for_items,
            "payment_events": payments_clean,
            "open_return_id": open_return_id,
        }

    def _returns_eligibility(self, q: ViewQuery, at_ms: int) -> dict[str, Any]:
        rid = q.params.get("return_id")
        if not rid:
            raise _NotFoundError("returns_eligibility", "missing return_id")

        returns_latest = self._latest_by(
            self._visible("retail.returns", at_ms),
            key="return_id",
            time_field="occurred_at_ms",
        )
        r = returns_latest.get(rid)
        if r is None:
            raise _NotFoundError("returns_eligibility", rid)
        oid = r["order_id"]

        orders_latest = self._latest_by(
            self._visible("retail.orders", at_ms),
            key="order_id",
            time_field="occurred_at_ms",
        )
        o = orders_latest.get(oid)
        if o is None:
            raise _NotFoundError("returns_eligibility", f"order:{oid}")
        order_summary = {
            k: o[k] for k in ("order_id", "status", "total_cents", "currency", "occurred_at_ms")
        }

        payments = sorted(
            (e for e in self._visible("retail.payment_events", at_ms) if e["order_id"] == oid),
            key=lambda e: e["occurred_at_ms"],
        )
        has_chargeback = any(p["kind"] == "CHARGEBACK" for p in payments)
        payments_clean = [
            {k: p[k] for k in ("kind", "amount_cents", "currency", "occurred_at_ms")}
            for p in payments
        ]

        return {
            "return_id": rid,
            "order_id": oid,
            "return_status": r["status"],
            "return_amount_cents": r["amount_cents"],
            "order": order_summary,
            "payment_events": payments_clean,
            "has_chargeback": has_chargeback,
            "eligible_for_refund": not has_chargeback,
            "ineligibility_reason": "chargeback_already_filed" if has_chargeback else None,
        }

    @staticmethod
    def _latest_by_pair(
        events: list[dict[str, Any]],
        *,
        keys: tuple[str, str],
        time_field: str,
    ) -> dict[tuple[str, str], dict[str, Any]]:
        out: dict[tuple[str, str], dict[str, Any]] = {}
        for e in events:
            k = (e[keys[0]], e[keys[1]])
            cur = out.get(k)
            if cur is None or e[time_field] >= cur[time_field]:
                out[k] = e
        return out


class _NotFoundError(Exception):
    def __init__(self, view: str, key: str) -> None:
        super().__init__(f"{view}: {key}")
        self.view = view
        self.key = key
