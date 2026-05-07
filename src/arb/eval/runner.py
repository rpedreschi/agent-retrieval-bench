"""Eval runner. Orchestrates: snapshot capture, condition application, agent
construction, task execution, grading, and result emission.

This module provides the harness shape — the actual model invocations land
in :func:`run_task_against_model`, which delegates to Inspect AI. Tests cover
the harness shape (snapshot, condition, grader) with stubbed model calls so
CI never depends on API keys.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from arb.context.engine import ContextEngine
from arb.eval.conditions import AppliedCondition, Condition, apply_condition
from arb.eval.grading import FailureCategory, GradeResult
from arb.eval.models import ModelSpec, resolve
from arb.eval.tasks import TaskInstance, build_all
from arb.mcp.servers.builder import VariantABundle, load_variant_a
from arb.snapshot import snapshot_dict
from arb.world.generator import Generator, GeneratorConfig, InMemorySink


@dataclass
class RunRow:
    task_id: str
    category: str
    variant: str  # "A" | "B"
    model: str  # short name
    condition: str  # clean | degraded | adversarial
    seed: int
    correct: bool
    score: float
    failure: str
    latency_ms: int
    tool_calls: int
    cost_usd: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunMatrix:
    tasks: list[TaskInstance]
    variants: tuple[str, ...]  # ("A", "B")
    models: list[ModelSpec]
    conditions: list[Condition]
    seeds: list[int]


def load_eval_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def build_matrix(
    snapshot: dict[str, Any],
    cfg: dict[str, Any],
) -> RunMatrix:
    return RunMatrix(
        tasks=build_all(snapshot),
        variants=tuple(cfg.get("variants", ("A", "B"))),
        models=[resolve(m) for m in cfg["models"]],
        conditions=[
            Condition(c) for c in cfg.get("conditions", ["clean", "degraded", "adversarial"])
        ],
        seeds=list(cfg.get("seeds", [1, 2, 3])),
    )


def capture_snapshot(world_cfg_path: Path, *, seed: int) -> dict[str, Any]:
    raw = yaml.safe_load(world_cfg_path.read_text())
    g = Generator(
        config=GeneratorConfig.from_dict(raw),
        sink=InMemorySink(),
        seed=seed,
    )
    g.run()
    return snapshot_dict(g.state)


def setup_variant_a(
    *,
    condition: Condition,
    condition_seed: int,
    variant_a_cfg: Path,
) -> tuple[VariantABundle, AppliedCondition]:
    bundle = load_variant_a(variant_a_cfg, inject_sleep=False)
    applied = apply_condition(bundle, condition, seed=condition_seed)
    return bundle, applied


def run_task_against_model(
    *,
    task: TaskInstance,
    variant: str,
    model: ModelSpec,
    bundle: VariantABundle | None,
    engine: ContextEngine | None,
    inspect_solver: Any | None = None,
) -> tuple[dict[str, Any], int, int, float, int]:
    """Execute one (task, variant, model) cell. Returns
    (agent_answer, latency_ms, tool_calls, cost_usd, status).

    Phase 4 ships the harness shape; the actual Inspect AI invocation lives
    behind ``inspect_solver``. Tests pass a stub.
    """
    if inspect_solver is None:
        # Real run: import + execute Inspect AI here. Imports deferred so
        # tests don't require the package.
        raise NotImplementedError(
            "real-model invocation lives behind --execute. Phase 4 ships the "
            "harness shape; pass inspect_solver= in tests."
        )
    return inspect_solver(task=task, variant=variant, model=model, bundle=bundle, engine=engine)


def grade_run(
    task: TaskInstance,
    agent_answer: dict[str, Any],
    snapshot: dict[str, Any],
) -> GradeResult:
    return task.grader(agent_answer, snapshot)


def emit_results(rows: list[RunRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(asdict(r)) + "\n")


def summarise(rows: list[RunRow]) -> dict[str, Any]:
    """Quick aggregations matching the docs/methodology.md headline metrics."""
    if not rows:
        return {"n": 0}
    total_cost = sum(r.cost_usd for r in rows)
    correct = [r for r in rows if r.correct]
    correct_count = len(correct)
    deg = [r for r in rows if r.condition == "degraded"]
    deg_correct = [r for r in deg if r.correct]
    cost_per_correct = total_cost / max(correct_count, 1)
    cost_per_correct_degraded = (
        sum(r.cost_usd for r in deg) / max(len(deg_correct), 1) if deg else float("nan")
    )
    failures: dict[str, int] = {}
    for r in rows:
        if not r.correct:
            failures[r.failure] = failures.get(r.failure, 0) + 1
    by_variant: dict[str, dict[str, Any]] = {}
    for v in {r.variant for r in rows}:
        rs = [r for r in rows if r.variant == v]
        by_variant[v] = {
            "n": len(rs),
            "success_rate": sum(1 for r in rs if r.correct) / len(rs),
        }
    return {
        "n": len(rows),
        "success_rate": correct_count / len(rows),
        "cost_per_correct": cost_per_correct,
        "cost_per_correct_degraded": cost_per_correct_degraded,
        "failures": failures,
        "by_variant": by_variant,
    }


def make_row(
    *,
    task: TaskInstance,
    variant: str,
    model: ModelSpec,
    condition: Condition,
    seed: int,
    grade: GradeResult,
    latency_ms: int,
    tool_calls: int,
    cost_usd: float,
) -> RunRow:
    return RunRow(
        task_id=task.task_id,
        category=task.category.value,
        variant=variant,
        model=model.short,
        condition=condition.value,
        seed=seed,
        correct=grade.correct,
        score=grade.score,
        failure=grade.failure.value if not grade.correct else FailureCategory.NONE.value,
        latency_ms=latency_ms,
        tool_calls=tool_calls,
        cost_usd=cost_usd,
        details=grade.details,
    )
