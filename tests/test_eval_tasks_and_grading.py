"""Task building + grading on a real snapshot."""

from __future__ import annotations

from arb.eval.grading import FailureCategory
from arb.eval.tasks import (
    TaskCategory,
    build_lookup_task,
    build_multi_hop_task,
    build_transactional_task,
)
from arb.snapshot import snapshot_dict
from arb.world.generator import Generator, InMemorySink


def _snap(laptop_config):
    g = Generator(config=laptop_config, sink=InMemorySink(), seed=42)
    g.run()
    return snapshot_dict(g.state)


def test_lookup_task_grades_correct_tier(laptop_config) -> None:
    snap = _snap(laptop_config)
    task = build_lookup_task(snap)
    assert task.category is TaskCategory.LOOKUP
    cid = task.target_ids["customer_id"]
    real_tier = next(c["tier"] for c in snap["customers"] if c["customer_id"] == cid)
    grade = task.grader({"customer_id": cid, "tier": real_tier}, snap)
    assert grade.correct
    assert grade.failure is FailureCategory.NONE


def test_lookup_task_flags_temporal_misalignment_on_wrong_tier(laptop_config) -> None:
    snap = _snap(laptop_config)
    task = build_lookup_task(snap)
    cid = task.target_ids["customer_id"]
    grade = task.grader({"customer_id": cid, "tier": "WRONG"}, snap)
    assert not grade.correct
    assert grade.failure is FailureCategory.TEMPORAL_MISALIGNMENT


def test_transactional_task_requires_status_and_total(laptop_config) -> None:
    snap = _snap(laptop_config)
    task = build_transactional_task(snap)
    oid = task.target_ids["order_id"]
    o = next(o for o in snap["orders"] if o["order_id"] == oid)
    grade = task.grader(
        {"order_id": oid, "status": o["status"], "total_cents": o["total_cents"]},
        snap,
    )
    assert grade.correct
    bad = task.grader(
        {"order_id": oid, "status": o["status"], "total_cents": o["total_cents"] + 1},
        snap,
    )
    assert not bad.correct
    assert bad.failure is FailureCategory.MISSED_JOIN


def test_multi_hop_task_returns_eligibility_after_chargeback(laptop_config) -> None:
    snap = _snap(laptop_config)
    task = build_multi_hop_task(snap)
    rid = task.target_ids["return_id"]
    # Correct reasoning: ineligible because chargeback.
    good = task.grader(
        {"return_id": rid, "eligible_for_refund": False, "reason": "chargeback"},
        snap,
    )
    assert good.correct
    # Wrong: agent says eligible.
    bad = task.grader(
        {"return_id": rid, "eligible_for_refund": True, "reason": "ok"},
        snap,
    )
    assert not bad.correct
    assert bad.failure is FailureCategory.MISSED_JOIN


def test_grader_handles_missing_keys(laptop_config) -> None:
    snap = _snap(laptop_config)
    task = build_lookup_task(snap)
    grade = task.grader({}, snap)
    assert not grade.correct
    assert grade.failure is FailureCategory.REASONING_ERROR
