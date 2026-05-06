"""Named, replayable scenarios.

A scenario observes WorldState at each tick and may push synthetic events into
the generator's outbox. Phase 1 ships one reference scenario:
chargeback -> tier downgrade -> refund attempt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from arb.world.state import PaymentEventKind, ReturnStatus, WorldState

if TYPE_CHECKING:
    from arb.world.generator import Outbox


class Scenario(Protocol):
    name: str

    def maybe_fire(self, state: WorldState, tick: int, outbox: Outbox) -> None: ...


@dataclass
class ChargebackDowngradeRefund:
    fire_at_tick: int
    name: str = "chargeback_downgrade_refund"
    fired: bool = False

    def maybe_fire(self, state: WorldState, tick: int, outbox: Outbox) -> None:
        if self.fired or tick < self.fire_at_tick:
            return
        # Pick the first PAID/SHIPPED/DELIVERED order whose customer is at least SILVER.
        target = None
        for o in state.orders.values():
            cust = state.customers.get(o.customer_id)
            if cust is None:
                continue
            if cust.tier in ("SILVER", "GOLD", "PLATINUM"):
                target = o
                break
        if target is None:
            return  # try again next tick
        self.fired = True
        cust = state.customers[target.customer_id]
        now_ms = outbox.now_ms

        # 1. chargeback
        outbox.payment_event(
            order_id=target.order_id,
            kind=PaymentEventKind.CHARGEBACK,
            amount_cents=target.total_cents,
            currency=target.currency,
            occurred_at_ms=now_ms,
        )
        # 2. tier downgrade (one step down)
        from_tier = cust.tier
        ladder = ["BRONZE", "SILVER", "GOLD", "PLATINUM"]
        to_tier = ladder[max(0, ladder.index(from_tier) - 1)]
        cust.tier = to_tier
        cust.version += 1
        cust.updated_at_ms = now_ms
        outbox.tier_change(
            customer_id=cust.customer_id,
            from_tier=from_tier,
            to_tier=to_tier,
            reason="chargeback_auto_downgrade",
            occurred_at_ms=now_ms,
        )
        outbox.customer_upsert(cust)
        # 3. refund attempt that fails (creates a return that gets REJECTED)
        ret_id = f"ret-scn-{state.next_id('scenario_return')}"
        outbox.return_event(
            return_id=ret_id,
            order_id=target.order_id,
            status=ReturnStatus.REJECTED,
            reason="chargeback_already_filed",
            amount_cents=target.total_cents,
            occurred_at_ms=now_ms,
        )


SCENARIOS: dict[str, type[Scenario]] = {
    "chargeback_downgrade_refund": ChargebackDowngradeRefund,  # type: ignore[dict-item]
}
