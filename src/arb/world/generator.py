"""Coherent world-state generator.

Tick-driven. Each tick:
  1) ages the simulated clock
  2) applies inbound natural events (new orders, inventory snapshots, tickets, ...)
  3) gives every scenario a chance to fire
  4) flushes the outbox to the configured sink (Kafka or in-memory)

All randomness goes through arb.world.rng.RngBundle so a fixed seed produces a
byte-identical event stream across runs.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from arb.world.rng import RngBundle
from arb.world.scenarios import SCENARIOS, Scenario
from arb.world.state import (
    Customer,
    InventoryRow,
    Order,
    OrderItem,
    OrderStatus,
    PaymentEventKind,
    Return,
    ReturnStatus,
    SupportTicket,
    TicketStatus,
    WorldState,
)

# ---------------------------------------------------------------- sinks ------


class Sink(Protocol):
    def emit(self, topic: str, key: str, value: dict[str, Any]) -> None: ...
    def flush(self) -> None: ...


@dataclass
class InMemorySink:
    """Records every emission. Used by tests and by --dry-run runs."""
    events: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def emit(self, topic: str, key: str, value: dict[str, Any]) -> None:
        self.events.append((topic, key, value))

    def flush(self) -> None:
        return None

    def by_topic(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for topic, _key, value in self.events:
            out.setdefault(topic, []).append(value)
        return out


# ---------------------------------------------------------------- outbox -----


@dataclass
class Outbox:
    """Per-tick event buffer. Holds (topic, key, value) tuples and the wall-clock ms.

    Centralising emission here means scenarios and the natural generator share
    the same emission contract and the same ID conventions.
    """
    tenant_id: str
    now_ms: int
    sink: Sink
    state: WorldState

    def emit(self, topic: str, key: str, value: dict[str, Any]) -> None:
        self.sink.emit(topic, key, value)

    # ----- typed helpers (one per topic) -----

    def customer_upsert(self, c: Customer) -> None:
        self.emit("retail.customers", c.customer_id, {
            "tenant_id": self.tenant_id,
            "customer_id": c.customer_id,
            "email": c.email,
            "name": c.name,
            "tier": c.tier,
            "created_at_ms": c.created_at_ms,
            "updated_at_ms": c.updated_at_ms,
            "version": c.version,
        })

    def tier_change(
        self, *, customer_id: str, from_tier: str, to_tier: str,
        reason: str, occurred_at_ms: int,
    ) -> None:
        eid = f"tc-{self.state.next_id('tier_change')}"
        self.emit("retail.customer_tier_changes", customer_id, {
            "tenant_id": self.tenant_id,
            "event_id": eid,
            "customer_id": customer_id,
            "from_tier": from_tier,
            "to_tier": to_tier,
            "reason": reason,
            "occurred_at_ms": occurred_at_ms,
        })

    def order_event(self, o: Order, occurred_at_ms: int) -> None:
        eid = f"oe-{self.state.next_id('order_event')}"
        self.emit("retail.orders", o.order_id, {
            "tenant_id": self.tenant_id,
            "event_id": eid,
            "order_id": o.order_id,
            "customer_id": o.customer_id,
            "status": o.status.value,
            "total_cents": o.total_cents,
            "currency": o.currency,
            "occurred_at_ms": occurred_at_ms,
        })

    def order_item(self, it: OrderItem, occurred_at_ms: int) -> None:
        self.emit("retail.order_items", it.order_id, {
            "tenant_id": self.tenant_id,
            "order_item_id": it.order_item_id,
            "order_id": it.order_id,
            "sku": it.sku,
            "quantity": it.quantity,
            "unit_price_cents": it.unit_price_cents,
            "warehouse_id": it.warehouse_id,
            "occurred_at_ms": occurred_at_ms,
        })

    def inventory_snapshot(self, inv: InventoryRow, occurred_at_ms: int) -> None:
        sid = f"is-{self.state.next_id('inv_snap')}"
        self.emit("retail.inventory_snapshots", f"{inv.sku}@{inv.warehouse_id}", {
            "tenant_id": self.tenant_id,
            "snapshot_id": sid,
            "sku": inv.sku,
            "warehouse_id": inv.warehouse_id,
            "quantity_on_hand": inv.quantity_on_hand,
            "occurred_at_ms": occurred_at_ms,
        })

    def return_event(
        self, *, return_id: str, order_id: str, status: ReturnStatus,
        reason: str, amount_cents: int, occurred_at_ms: int,
    ) -> None:
        eid = f"re-{self.state.next_id('return_event')}"
        self.emit("retail.returns", return_id, {
            "tenant_id": self.tenant_id,
            "event_id": eid,
            "return_id": return_id,
            "order_id": order_id,
            "status": status.value,
            "reason": reason,
            "amount_cents": amount_cents,
            "occurred_at_ms": occurred_at_ms,
        })

    def support_ticket(self, t: SupportTicket, occurred_at_ms: int) -> None:
        eid = f"se-{self.state.next_id('ticket_event')}"
        self.emit("retail.support_tickets", t.ticket_id, {
            "tenant_id": self.tenant_id,
            "event_id": eid,
            "ticket_id": t.ticket_id,
            "customer_id": t.customer_id,
            "order_id": t.order_id,
            "status": t.status.value,
            "subject": t.subject,
            "occurred_at_ms": occurred_at_ms,
        })

    def payment_event(
        self, *, order_id: str, kind: PaymentEventKind,
        amount_cents: int, currency: str, occurred_at_ms: int,
    ) -> None:
        eid = f"pe-{self.state.next_id('payment_event')}"
        self.emit("retail.payment_events", order_id, {
            "tenant_id": self.tenant_id,
            "event_id": eid,
            "order_id": order_id,
            "kind": kind.value,
            "amount_cents": amount_cents,
            "currency": currency,
            "occurred_at_ms": occurred_at_ms,
        })


# ---------------------------------------------------------------- config -----


@dataclass
class GeneratorConfig:
    tenant_id: str
    customers: int
    warehouses: int
    skus: int
    baseline_orders: int
    orders_per_sec: float
    inventory_snapshot_interval_sec: float
    return_probability: float
    payment_event_probability: float
    support_ticket_per_sec: float
    duration_sec: int
    tick_sec: float
    start_epoch_ms: int
    scenarios: list[tuple[str, int]] = field(default_factory=list)  # (name, fire_at_tick)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GeneratorConfig:
        c = d["cardinalities"]
        r = d["rates"]
        s = d["simulation"]
        scenarios = [(item["name"], int(item["fire_at_tick"])) for item in d.get("scenarios", [])]
        return cls(
            tenant_id=d["tenant_id"],
            customers=int(c["customers"]),
            warehouses=int(c["warehouses"]),
            skus=int(c["skus"]),
            baseline_orders=int(c["baseline_orders"]),
            orders_per_sec=float(r["orders_per_sec"]),
            inventory_snapshot_interval_sec=float(r["inventory_snapshot_interval_sec"]),
            return_probability=float(r["return_probability"]),
            payment_event_probability=float(r["payment_event_probability"]),
            support_ticket_per_sec=float(r["support_ticket_per_sec"]),
            duration_sec=int(s["duration_sec"]),
            tick_sec=float(s["tick_sec"]),
            start_epoch_ms=int(s["start_epoch_ms"]),
            scenarios=scenarios,
        )


# ---------------------------------------------------------------- engine -----


@dataclass
class Generator:
    config: GeneratorConfig
    sink: Sink
    seed: int
    state: WorldState = field(init=False)
    rng: RngBundle = field(init=False)
    scenarios: list[Scenario] = field(init=False)

    def __post_init__(self) -> None:
        self.state = WorldState(tenant_id=self.config.tenant_id)
        self.rng = RngBundle(self.seed)
        self.scenarios = []
        for name, fire_at in self.config.scenarios:
            cls = SCENARIOS[name]
            self.scenarios.append(cls(fire_at_tick=fire_at))  # type: ignore[call-arg]

    # ----- bootstrap -----

    def bootstrap(self) -> None:
        cfg = self.config
        t0 = cfg.start_epoch_ms
        # warehouses, skus
        self.state.warehouses = [f"wh-{i:04d}" for i in range(cfg.warehouses)]
        self.state.skus = [f"sku-{i:06d}" for i in range(cfg.skus)]

        out = Outbox(cfg.tenant_id, t0, self.sink, self.state)

        # customers
        rng = self.rng.stream("customers")
        for i in range(cfg.customers):
            cid = f"cust-{i:08d}"
            tier = ("BRONZE", "SILVER", "GOLD", "PLATINUM")[int(rng.integers(0, 4))]
            c = Customer(
                customer_id=cid,
                email=f"{cid}@example.invalid",
                name=f"Customer {i}",
                tier=tier,
                created_at_ms=t0,
                updated_at_ms=t0,
            )
            self.state.customers[cid] = c
            out.customer_upsert(c)

        # inventory: each (sku, warehouse) starts with seeded stock
        rng = self.rng.stream("inventory_init")
        for sku in self.state.skus:
            for wh in self.state.warehouses:
                qty = int(rng.integers(50, 500))
                inv = InventoryRow(sku=sku, warehouse_id=wh, quantity_on_hand=qty)
                self.state.inventory[(sku, wh)] = inv
                out.inventory_snapshot(inv, t0)

        # baseline orders
        for _ in range(cfg.baseline_orders):
            self._create_order(out, t0)

    # ----- tick -----

    def run(self) -> None:
        self.bootstrap()
        cfg = self.config
        ticks = int(cfg.duration_sec / cfg.tick_sec)
        for tick in range(ticks):
            now_ms = cfg.start_epoch_ms + int((tick + 1) * cfg.tick_sec * 1000)
            out = Outbox(cfg.tenant_id, now_ms, self.sink, self.state)
            self._tick_natural(out, tick)
            for scn in self.scenarios:
                scn.maybe_fire(self.state, tick, out)
        self.sink.flush()

    def _tick_natural(self, out: Outbox, tick: int) -> None:
        cfg = self.config

        # New orders this tick (Poisson-ish; deterministic via seeded RNG)
        rng = self.rng.stream("orders_per_tick")
        n_new = int(rng.poisson(cfg.orders_per_sec * cfg.tick_sec))
        for _ in range(n_new):
            self._create_order(out, out.now_ms)

        # Inventory snapshots (every N seconds)
        if tick > 0 and (tick * cfg.tick_sec) % cfg.inventory_snapshot_interval_sec == 0:
            for inv in self.state.inventory.values():
                out.inventory_snapshot(inv, out.now_ms)

        # Returns (probabilistic on existing delivered orders)
        rng = self.rng.stream("returns")
        for o in list(self.state.orders.values())[-1000:]:  # cap scan for perf
            if o.status != OrderStatus.DELIVERED:
                continue
            if rng.random() < cfg.return_probability * cfg.tick_sec:
                ret_id = f"ret-{self.state.next_id('return')}"
                r = Return(
                    return_id=ret_id, order_id=o.order_id,
                    status=ReturnStatus.REQUESTED,
                    reason="customer_request", amount_cents=o.total_cents,
                )
                self.state.returns[ret_id] = r
                out.return_event(
                    return_id=ret_id, order_id=o.order_id,
                    status=r.status, reason=r.reason,
                    amount_cents=r.amount_cents, occurred_at_ms=out.now_ms,
                )

        # Payment events (probabilistic)
        rng = self.rng.stream("payments")
        for o in list(self.state.orders.values())[-1000:]:
            if rng.random() < cfg.payment_event_probability * cfg.tick_sec:
                kind = PaymentEventKind.FAILED if rng.random() < 0.5 else PaymentEventKind.REFUND
                out.payment_event(
                    order_id=o.order_id, kind=kind,
                    amount_cents=o.total_cents, currency=o.currency,
                    occurred_at_ms=out.now_ms,
                )

        # Support tickets
        rng = self.rng.stream("tickets")
        n_tix = int(rng.poisson(cfg.support_ticket_per_sec * cfg.tick_sec))
        cust_ids = list(self.state.customers.keys())
        order_ids = list(self.state.orders.keys())
        for _ in range(n_tix):
            if not cust_ids:
                break
            cid = cust_ids[int(rng.integers(0, len(cust_ids)))]
            oid: str | None = None
            if order_ids and rng.random() < 0.6:
                oid = order_ids[int(rng.integers(0, len(order_ids)))]
            tid = f"tic-{self.state.next_id('ticket')}"
            t = SupportTicket(
                ticket_id=tid, customer_id=cid, order_id=oid,
                status=TicketStatus.OPEN, subject="help",
            )
            self.state.tickets[tid] = t
            out.support_ticket(t, out.now_ms)

        # Advance some orders' status (created -> paid -> shipped -> delivered)
        rng = self.rng.stream("order_lifecycle")
        for o in list(self.state.orders.values())[-200:]:
            if o.status == OrderStatus.DELIVERED or o.status == OrderStatus.CANCELLED:
                continue
            if rng.random() < 0.5:
                nxt = {
                    OrderStatus.CREATED: OrderStatus.PAID,
                    OrderStatus.PAID: OrderStatus.SHIPPED,
                    OrderStatus.SHIPPED: OrderStatus.DELIVERED,
                }[o.status]
                o.status = nxt
                out.order_event(o, out.now_ms)
                if nxt == OrderStatus.PAID:
                    out.payment_event(
                        order_id=o.order_id, kind=PaymentEventKind.CAPTURED,
                        amount_cents=o.total_cents, currency=o.currency,
                        occurred_at_ms=out.now_ms,
                    )

    # ----- helpers -----

    def _create_order(self, out: Outbox, now_ms: int) -> None:
        rng = self.rng.stream("orders")
        cust_ids = list(self.state.customers.keys())
        if not cust_ids:
            return
        cid = cust_ids[int(rng.integers(0, len(cust_ids)))]
        oid = f"ord-{self.state.next_id('order'):010d}"
        n_items = int(rng.integers(1, 4))
        items: list[OrderItem] = []
        total = 0
        for j in range(n_items):
            sku = self.state.skus[int(rng.integers(0, len(self.state.skus)))]
            wh = self.state.warehouses[int(rng.integers(0, len(self.state.warehouses)))]
            qty = int(rng.integers(1, 4))
            unit = int(rng.integers(500, 5000))
            inv = self.state.inventory.get((sku, wh))
            if inv is not None:
                inv.quantity_on_hand = max(0, inv.quantity_on_hand - qty)
            it = OrderItem(
                order_item_id=f"{oid}-it-{j}", order_id=oid, sku=sku,
                quantity=qty, unit_price_cents=unit, warehouse_id=wh,
            )
            items.append(it)
            total += qty * unit
        o = Order(
            order_id=oid, customer_id=cid, status=OrderStatus.CREATED,
            total_cents=total, currency="USD", created_at_ms=now_ms, items=items,
        )
        self.state.orders[oid] = o
        out.order_event(o, now_ms)
        for it in items:
            out.order_item(it, now_ms)


def run(config: GeneratorConfig, sink: Sink, seed: int) -> WorldState:
    g = Generator(config=config, sink=sink, seed=seed)
    g.run()
    return g.state


def iter_topics() -> Iterator[str]:
    yield from (
        "retail.customers",
        "retail.customer_tier_changes",
        "retail.orders",
        "retail.order_items",
        "retail.inventory_snapshots",
        "retail.returns",
        "retail.support_tickets",
        "retail.payment_events",
    )


__all__ = [
    "Generator", "GeneratorConfig", "InMemorySink", "Outbox", "Sink",
    "iter_topics", "run",
]


def _typing_only() -> Iterable[Any]:  # pragma: no cover
    return ()
