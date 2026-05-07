"""LLM-as-judge failure classifier (stub for Phase 5; gated on env).

The grader (``arb.eval.tasks``) already populates a ``failure`` category for
every failed run via deterministic rule. Phase 5 ships a stub that simply
trusts the grader's category. When ``ARB_LLM_JUDGE=1`` and an Anthropic
key is configured, this is replaced by a structured-output LLM call that
re-classifies the failure given the agent's transcript and the task
question. That wiring lands when Phase 4b produces real transcripts.
"""
from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from arb.eval.grading import FailureCategory


def llm_judge_enabled() -> bool:
    return os.environ.get("ARB_LLM_JUDGE") == "1"


def classify_row(row: dict[str, Any]) -> str:
    """Return a FailureCategory string. ``none`` for successful rows."""
    if row.get("correct"):
        return FailureCategory.NONE.value
    if not llm_judge_enabled():
        return row.get("failure", FailureCategory.REASONING_ERROR.value)
    # Phase 4b plugs the structured-output call in here.
    return row.get("failure", FailureCategory.REASONING_ERROR.value)


def reclassify(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return rows with the ``failure`` field replaced by classifier output."""
    out = []
    for r in rows:
        new = dict(r)
        new["failure"] = classify_row(r)
        out.append(new)
    return out
