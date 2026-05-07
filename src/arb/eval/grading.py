"""Snapshot-based grading.

Each task declares an ``expected`` predicate over the ground-truth snapshot.
The agent's final answer is graded by comparing structured fields against
the snapshot via that predicate. See docs/methodology.md §1.

Failure taxonomy: when a task fails, the grader returns one of the
canonical categories so the failure-distribution chart can be aggregated
without ad-hoc post-processing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class FailureCategory(StrEnum):
    NONE = "none"
    TEMPORAL_MISALIGNMENT = "temporal_misalignment"
    TOOL_SELECTION_ERROR = "tool_selection_error"
    MISSED_JOIN = "missed_join"
    SCHEMA_MISMATCH = "schema_mismatch"
    SOURCE_TIMEOUT = "source_timeout"
    REASONING_ERROR = "reasoning_error"
    AMBIGUOUS_RESULT = "ambiguous_result"
    AUTH_DENIED = "auth_denied"


@dataclass
class GradeResult:
    correct: bool
    score: float  # 0.0 or 1.0 for exact-match tasks; partial credit allowed
    failure: FailureCategory
    details: dict[str, Any]


# A grader is a pure function from (agent_output, snapshot) -> GradeResult.
Grader = Callable[[dict[str, Any], dict[str, Any]], GradeResult]


def grade_against_snapshot(
    agent_output: dict[str, Any],
    snapshot: dict[str, Any],
    grader: Grader,
) -> GradeResult:
    """Apply ``grader`` to (agent_output, snapshot). Trivial today, but the
    indirection lets Phase 5 plug in an LLM-as-judge classifier without
    changing call sites."""
    return grader(agent_output, snapshot)


# ----------------------------------------------------------------- helpers


def find_customer(snapshot: dict[str, Any], customer_id: str) -> dict[str, Any] | None:
    for c in snapshot.get("customers", []):
        if c["customer_id"] == customer_id:
            return c
    return None


def find_order(snapshot: dict[str, Any], order_id: str) -> dict[str, Any] | None:
    for o in snapshot.get("orders", []):
        if o["order_id"] == order_id:
            return o
    return None


def find_return(snapshot: dict[str, Any], return_id: str) -> dict[str, Any] | None:
    for r in snapshot.get("returns", []):
        if r["return_id"] == return_id:
            return r
    return None
