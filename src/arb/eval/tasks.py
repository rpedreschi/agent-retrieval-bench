"""Three task categories: lookup, transactional, multi-hop.

Each task is a small dataclass: a question template parameterised by a
ground-truth pick from the snapshot, plus a grader that judges the agent's
final structured answer.

The multi-hop task ``returns_eligibility_after_chargeback`` is the marquee
example. It requires the agent to:

  1. Find the customer's most recent return.
  2. Look up the originating order.
  3. Inspect payment events on that order for a CHARGEBACK.
  4. Conclude the return is INELIGIBLE for refund.

Variant A must compose this from four-plus tool calls. Variant B answers it
with a single ``get_view("returns_eligibility", {return_id})`` call.

The lookup and transactional categories exist for statistical breadth; the
multi-hop is the one that drives the headline chart.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from arb.eval.grading import (
    FailureCategory,
    Grader,
    GradeResult,
    find_customer,
    find_order,
    find_return,
)


class TaskCategory(StrEnum):
    LOOKUP = "lookup"
    TRANSACTIONAL = "transactional"
    MULTI_HOP = "multi_hop"


@dataclass
class TaskInstance:
    task_id: str
    category: TaskCategory
    question: str
    expected_answer_keys: tuple[str, ...]  # keys the agent's JSON answer must include
    grader: Grader
    target_ids: dict[str, str]  # customer_id / order_id / return_id used to pick this case


# ----------------------------------------------------------------- pickers ---


def _pick_customer(snapshot: dict[str, Any]) -> dict[str, Any]:
    customers = snapshot.get("customers", [])
    if not customers:
        raise ValueError("no customers in snapshot")
    return customers[0]


def _pick_chargeback_return(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Pick the return produced by the chargeback scenario (REJECTED, reason=chargeback)."""
    for r in snapshot.get("returns", []):
        if r.get("reason") == "chargeback_already_filed":
            return r
    return None


# ----------------------------------------------------------------- graders ---


def _grade_lookup_customer(answer: dict[str, Any], snapshot: dict[str, Any]) -> GradeResult:
    cid = answer.get("customer_id")
    if not cid:
        return GradeResult(
            False, 0.0, FailureCategory.REASONING_ERROR, {"reason": "missing customer_id"}
        )
    c = find_customer(snapshot, cid)
    if c is None:
        return GradeResult(
            False, 0.0, FailureCategory.REASONING_ERROR, {"reason": "unknown customer"}
        )
    actual_tier = c["tier"]
    correct = answer.get("tier") == actual_tier
    if not correct:
        return GradeResult(
            False,
            0.0,
            FailureCategory.TEMPORAL_MISALIGNMENT,
            {"expected": actual_tier, "got": answer.get("tier")},
        )
    return GradeResult(True, 1.0, FailureCategory.NONE, {"tier": actual_tier})


def _grade_transactional_order_status(
    answer: dict[str, Any],
    snapshot: dict[str, Any],
) -> GradeResult:
    oid = answer.get("order_id")
    if not oid:
        return GradeResult(
            False, 0.0, FailureCategory.REASONING_ERROR, {"reason": "missing order_id"}
        )
    o = find_order(snapshot, oid)
    if o is None:
        return GradeResult(False, 0.0, FailureCategory.REASONING_ERROR, {"reason": "unknown order"})
    status_correct = answer.get("status") == o["status"]
    total_correct = answer.get("total_cents") == o["total_cents"]
    if status_correct and total_correct:
        return GradeResult(True, 1.0, FailureCategory.NONE, {})
    return GradeResult(
        False,
        0.0,
        FailureCategory.MISSED_JOIN,
        {
            "status_expected": o["status"],
            "status_got": answer.get("status"),
            "total_expected": o["total_cents"],
            "total_got": answer.get("total_cents"),
        },
    )


def _grade_returns_eligibility(answer: dict[str, Any], snapshot: dict[str, Any]) -> GradeResult:
    rid = answer.get("return_id")
    if not rid:
        return GradeResult(
            False, 0.0, FailureCategory.REASONING_ERROR, {"reason": "missing return_id"}
        )
    r = find_return(snapshot, rid)
    if r is None:
        return GradeResult(
            False, 0.0, FailureCategory.REASONING_ERROR, {"reason": "unknown return"}
        )
    expected_eligible = r.get("reason") != "chargeback_already_filed"
    if answer.get("eligible_for_refund") is not expected_eligible:
        return GradeResult(
            False,
            0.0,
            FailureCategory.MISSED_JOIN,
            {
                "expected_eligible": expected_eligible,
                "got": answer.get("eligible_for_refund"),
            },
        )
    return GradeResult(True, 1.0, FailureCategory.NONE, {"return_id": rid})


# ----------------------------------------------------------------- builders


def build_lookup_task(snapshot: dict[str, Any]) -> TaskInstance:
    c = _pick_customer(snapshot)
    return TaskInstance(
        task_id=f"lookup-customer-tier:{c['customer_id']}",
        category=TaskCategory.LOOKUP,
        question=(
            f"What loyalty tier is customer {c['customer_id']} currently on? "
            "Answer JSON: {customer_id, tier}."
        ),
        expected_answer_keys=("customer_id", "tier"),
        grader=_grade_lookup_customer,
        target_ids={"customer_id": c["customer_id"]},
    )


def build_transactional_task(snapshot: dict[str, Any]) -> TaskInstance:
    orders = snapshot.get("orders", [])
    if not orders:
        raise ValueError("no orders in snapshot")
    o = orders[len(orders) // 2]
    return TaskInstance(
        task_id=f"transactional-order-status:{o['order_id']}",
        category=TaskCategory.TRANSACTIONAL,
        question=(
            f"Report the current status and total_cents of order {o['order_id']}. "
            "Answer JSON: {order_id, status, total_cents}."
        ),
        expected_answer_keys=("order_id", "status", "total_cents"),
        grader=_grade_transactional_order_status,
        target_ids={"order_id": o["order_id"]},
    )


def build_multi_hop_task(snapshot: dict[str, Any]) -> TaskInstance:
    r = _pick_chargeback_return(snapshot)
    if r is None:
        raise ValueError(
            "no chargeback-driven return in snapshot; ensure the "
            "chargeback_downgrade_refund scenario fires before snapshot."
        )
    return TaskInstance(
        task_id=f"multi-hop-returns-eligibility:{r['return_id']}",
        category=TaskCategory.MULTI_HOP,
        question=(
            f"For return {r['return_id']}, determine whether it is eligible "
            "for a refund. A return is INELIGIBLE if a chargeback has been "
            "filed on the originating order. "
            "Answer JSON: {return_id, eligible_for_refund, reason}."
        ),
        expected_answer_keys=("return_id", "eligible_for_refund", "reason"),
        grader=_grade_returns_eligibility,
        target_ids={"return_id": r["return_id"], "order_id": r["order_id"]},
    )


def build_all(snapshot: dict[str, Any]) -> list[TaskInstance]:
    return [
        build_lookup_task(snapshot),
        build_transactional_task(snapshot),
        build_multi_hop_task(snapshot),
    ]
