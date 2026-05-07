"""Failure-taxonomy aggregation.

The headline chart in the talk is a per-variant histogram over
:class:`arb.eval.grading.FailureCategory`. Variant A is expected to show a
fat ``missed_join`` / ``temporal_misalignment`` band; Variant B is expected
to show a much smaller, differently-shaped distribution.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from arb.eval.grading import FailureCategory

CATEGORIES: tuple[str, ...] = tuple(
    c.value for c in FailureCategory if c is not FailureCategory.NONE
)


def failure_histogram(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Count failures by category. Successes are excluded."""
    out: dict[str, int] = {c: 0 for c in CATEGORIES}
    for r in rows:
        if not r["correct"]:
            cat = r.get("failure", "reasoning_error")
            out[cat] = out.get(cat, 0) + 1
    return out


def failure_histogram_by_variant(
    rows: Sequence[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    by_v: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_v.setdefault(r["variant"], []).append(r)
    return {v: failure_histogram(rs) for v, rs in by_v.items()}


def failure_rate_by_category(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Fraction of all rows that failed in each category (so they sum to overall failure rate)."""
    n = len(rows)
    if n == 0:
        return {c: 0.0 for c in CATEGORIES}
    hist = failure_histogram(rows)
    return {c: hist.get(c, 0) / n for c in CATEGORIES}
