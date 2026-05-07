"""Runner shape: matrix building, run-row construction, summarisation."""

from __future__ import annotations

import json
from pathlib import Path

from arb.eval.conditions import Condition
from arb.eval.grading import FailureCategory, GradeResult
from arb.eval.models import resolve
from arb.eval.runner import (
    RunRow,
    build_matrix,
    capture_snapshot,
    emit_results,
    make_row,
    summarise,
)
from arb.eval.tasks import build_lookup_task

REPO = Path(__file__).resolve().parent.parent


def test_capture_snapshot_returns_dict(laptop_config, tmp_path: Path) -> None:
    cfg_path = tmp_path / "world.yaml"
    import yaml

    cfg_path.write_text(
        yaml.safe_dump(
            {
                "tenant_id": laptop_config.tenant_id,
                "cardinalities": {
                    "customers": laptop_config.customers,
                    "warehouses": laptop_config.warehouses,
                    "skus": laptop_config.skus,
                    "baseline_orders": laptop_config.baseline_orders,
                },
                "rates": {
                    "orders_per_sec": laptop_config.orders_per_sec,
                    "inventory_snapshot_interval_sec": (
                        laptop_config.inventory_snapshot_interval_sec
                    ),
                    "return_probability": laptop_config.return_probability,
                    "payment_event_probability": laptop_config.payment_event_probability,
                    "support_ticket_per_sec": laptop_config.support_ticket_per_sec,
                },
                "simulation": {
                    "duration_sec": laptop_config.duration_sec,
                    "tick_sec": laptop_config.tick_sec,
                    "start_epoch_ms": laptop_config.start_epoch_ms,
                },
                "scenarios": [{"name": n, "fire_at_tick": t} for n, t in laptop_config.scenarios],
            }
        )
    )
    snap = capture_snapshot(cfg_path, seed=42)
    assert "customers" in snap and snap["customers"]


def test_build_matrix_resolves_models_and_conditions(laptop_config) -> None:
    snap = capture_snapshot.__wrapped__ if False else None  # silence linters
    # Build a minimal snapshot inline for matrix building.
    from arb.snapshot import snapshot_dict
    from arb.world.generator import Generator, InMemorySink

    g = Generator(config=laptop_config, sink=InMemorySink(), seed=42)
    g.run()
    snap = snapshot_dict(g.state)
    matrix = build_matrix(
        snap,
        {
            "variants": ["A", "B"],
            "models": ["claude-opus-4-7", "gpt-5", "google/gemini-2.5-pro"],
            "conditions": ["clean", "degraded"],
            "seeds": [1, 2],
        },
    )
    assert {m.short for m in matrix.models} == {"claude-opus-4-7", "gpt-5", "gemini-2.5-pro"}
    assert matrix.conditions == [Condition.CLEAN, Condition.DEGRADED]
    assert len(matrix.tasks) == 3


def test_make_row_and_summarise(laptop_config) -> None:
    from arb.snapshot import snapshot_dict
    from arb.world.generator import Generator, InMemorySink

    g = Generator(config=laptop_config, sink=InMemorySink(), seed=42)
    g.run()
    snap = snapshot_dict(g.state)
    task = build_lookup_task(snap)
    rows = []
    for variant in ("A", "B"):
        for cond in (Condition.CLEAN, Condition.DEGRADED):
            grade = GradeResult(
                correct=(variant == "B"),
                score=1.0 if variant == "B" else 0.0,
                failure=FailureCategory.NONE if variant == "B" else FailureCategory.MISSED_JOIN,
                details={},
            )
            rows.append(
                make_row(
                    task=task,
                    variant=variant,
                    model=resolve("gpt-5"),
                    condition=cond,
                    seed=1,
                    grade=grade,
                    latency_ms=120,
                    tool_calls=4,
                    cost_usd=0.01,
                )
            )
    s = summarise(rows)
    assert s["n"] == 4
    assert s["by_variant"]["B"]["success_rate"] == 1.0
    assert s["by_variant"]["A"]["success_rate"] == 0.0
    assert s["failures"]["missed_join"] == 2
    assert s["cost_per_correct"] > 0


def test_emit_results_writes_jsonl(tmp_path: Path) -> None:
    rows = [
        RunRow(
            task_id="t",
            category="lookup",
            variant="A",
            model="m",
            condition="clean",
            seed=1,
            correct=True,
            score=1.0,
            failure="none",
            latency_ms=10,
            tool_calls=1,
            cost_usd=0.0,
            details={},
        )
    ]
    p = tmp_path / "rows.jsonl"
    emit_results(rows, p)
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["task_id"] == "t"
