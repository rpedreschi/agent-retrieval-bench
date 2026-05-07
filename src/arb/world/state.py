"""In-memory coherent world state.

This is the single source of truth. All emitters are pure functions of state
transitions; they never invent IDs that don't exist in WorldState. This is what
guarantees referential integrity across the eight Kafka topics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

TIERS = ("BRONZE", "SILVER", "GOLD", "PLATINUM")


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class ReturnStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    RECEIVED = "RECEIVED"
    REFUNDED = "REFUNDED"
    REJECTED = "REJECTED"


class PaymentEventKind(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    REFUND = "REFUND"
    CHARGEBACK = "CHARGEBACK"
    FAILED = "FAILED"


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


@dataclass
class Customer:
    customer_id: str
    email: str
    name: str
    tier: str
    created_at_ms: int
    updated_at_ms: int
    version: int = 1


@dataclass
class OrderItem:
    order_item_id: str
    order_id: str
    sku: str
    quantity: int
    unit_price_cents: int
    warehouse_id: str


@dataclass
class Order:
    order_id: str
    customer_id: str
    status: OrderStatus
    total_cents: int
    currency: str
    created_at_ms: int
    items: list[OrderItem] = field(default_factory=list)


@dataclass
class InventoryRow:
    sku: str
    warehouse_id: str
    quantity_on_hand: int


@dataclass
class Return:
    return_id: str
    order_id: str
    status: ReturnStatus
    reason: str
    amount_cents: int


@dataclass
class SupportTicket:
    ticket_id: str
    customer_id: str
    order_id: str | None
    status: TicketStatus
    subject: str


@dataclass
class WorldState:
    tenant_id: str
    customers: dict[str, Customer] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    inventory: dict[tuple[str, str], InventoryRow] = field(default_factory=dict)
    returns: dict[str, Return] = field(default_factory=dict)
    tickets: dict[str, SupportTicket] = field(default_factory=dict)
    skus: list[str] = field(default_factory=list)
    warehouses: list[str] = field(default_factory=list)

    # Monotonic per-stream counters used for deterministic IDs.
    counters: dict[str, int] = field(default_factory=dict)

    def next_id(self, kind: str) -> int:
        n = self.counters.get(kind, 0) + 1
        self.counters[kind] = n
        return n

    # ----- invariant checks (used by tests + optional runtime asserts) -----

    def check_invariants(self) -> None:
        for o in self.orders.values():
            if o.customer_id not in self.customers:
                raise AssertionError(f"order {o.order_id} references missing customer")
            for it in o.items:
                if it.order_id != o.order_id:
                    raise AssertionError("order_item.order_id mismatch")
                if it.sku not in self.skus:
                    raise AssertionError(f"order_item references unknown sku {it.sku}")
                if it.warehouse_id not in self.warehouses:
                    raise AssertionError("order_item references unknown warehouse")
        for r in self.returns.values():
            if r.order_id not in self.orders:
                raise AssertionError(f"return {r.return_id} references missing order")
        for t in self.tickets.values():
            if t.customer_id not in self.customers:
                raise AssertionError(f"ticket {t.ticket_id} references missing customer")
            if t.order_id is not None and t.order_id not in self.orders:
                raise AssertionError(f"ticket {t.ticket_id} references missing order")
        for inv in self.inventory.values():
            if inv.quantity_on_hand < 0:
                raise AssertionError(f"inventory negative for {inv.sku}@{inv.warehouse_id}")
