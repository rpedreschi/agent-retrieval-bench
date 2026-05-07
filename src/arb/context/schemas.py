"""Output schemas for the three Variant B views.

These are the contract every Variant B implementation (DeltaStream, local,
your-streaming-stack-of-choice) must produce on a fixed input. The shapes
deliberately denormalise across source topics so the agent does not have to
compose joins at inference time — that is the whole point of Variant B.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ----------------------------------------------------------------- shared ---


class TierChange(BaseModel):
    from_tier: str
    to_tier: str
    reason: str
    occurred_at_ms: int


class OrderSummary(BaseModel):
    order_id: str
    status: str
    total_cents: int
    currency: str
    occurred_at_ms: int


class TicketSummary(BaseModel):
    ticket_id: str
    order_id: str | None
    status: str
    subject: str
    occurred_at_ms: int


class OrderItemRow(BaseModel):
    order_item_id: str
    sku: str
    quantity: int
    unit_price_cents: int
    warehouse_id: str


class InventoryForItem(BaseModel):
    sku: str
    warehouse_id: str
    quantity_on_hand: int
    occurred_at_ms: int


class PaymentEventRow(BaseModel):
    kind: str
    amount_cents: int
    currency: str
    occurred_at_ms: int


# ----------------------------------------------------------------- views ---


class Customer360(BaseModel):
    customer_id: str
    email: str
    name: str
    tier: str
    updated_at_ms: int
    tier_history: list[TierChange] = Field(default_factory=list)
    recent_orders: list[OrderSummary] = Field(default_factory=list)
    open_tickets: list[TicketSummary] = Field(default_factory=list)


class OrderState(BaseModel):
    order_id: str
    customer_id: str
    status: str
    total_cents: int
    currency: str
    occurred_at_ms: int
    items: list[OrderItemRow] = Field(default_factory=list)
    inventory_for_items: list[InventoryForItem] = Field(default_factory=list)
    payment_events: list[PaymentEventRow] = Field(default_factory=list)
    open_return_id: str | None = None


class ReturnsEligibility(BaseModel):
    return_id: str
    order_id: str
    return_status: str
    return_amount_cents: int
    order: OrderSummary
    payment_events: list[PaymentEventRow] = Field(default_factory=list)
    has_chargeback: bool = False
    eligible_for_refund: bool = True
    ineligibility_reason: str | None = None


VIEW_SCHEMAS: dict[str, type[BaseModel]] = {
    "customer_360": Customer360,
    "order_state": OrderState,
    "returns_eligibility": ReturnsEligibility,
}


def validate_view_payload(name: str, payload: dict[str, Any]) -> BaseModel:
    schema = VIEW_SCHEMAS[name]
    return schema.model_validate(payload)
