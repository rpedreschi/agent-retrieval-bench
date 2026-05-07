"""Phase 5 analysis: metrics, taxonomy, charts."""
from __future__ import annotations

from pathlib import Path

import pytest

from arb.analysis import (
    cost_per_correct,
    cost_per_correct_degraded,
    failure_histogram_by_variant,
    load_runs,
    success_rate,
)
from arb.analysis.classifier import classify_row, llm_judge_enabled, reclassify
from arb.analysis.metrics import bootstrap_ci, latency_percentile
from arb.analysis.taxonomy import CATEGORIES, failure_histogram, failure_rate_by_category

REPO = Path(__file__).resolve().parent.parent
EX = REPO / "tests" / "fixtures" / "example_runs.jsonl"


@pytest.fixture
def rows() -> list[dict]:
    return load_runs(EX)


def test_load_example_fixture(rows) -> None:
    assert len(rows) == 18
    assert all("variant" in r and "condition" in r for r in rows)


def test_bootstrap_ci_brackets_point_estimate() -> None:
    ci = bootstrap_ci([0.0, 1.0, 1.0, 1.0], seed=1)
    assert ci.lo <= ci.point <= ci.hi
    assert ci.lo >= 0 and ci.hi <= 1


def test_bootstrap_ci_handles_empty() -> None:
    import math
    ci = bootstrap_ci([])
    assert math.isnan(ci.point) and math.isnan(ci.lo) and math.isnan(ci.hi)


def test_success_rate_variant_b_beats_a(rows) -> None:
    a = success_rate([r for r in rows if r["variant"] == "A"])
    b = success_rate([r for r in rows if r["variant"] == "B"])
    assert b.point > a.point


def test_cost_per_correct_variant_b_lower_than_a(rows) -> None:
    a = cost_per_correct([r for r in rows if r["variant"] == "A"])
    b = cost_per_correct([r for r in rows if r["variant"] == "B"])
    # In the synthetic fixture B is correct often and cheap; A is mostly wrong.
    assert b.point < a.point


def test_cost_per_correct_degraded_filters_to_degraded(rows) -> None:
    ci = cost_per_correct_degraded([r for r in rows if r["variant"] == "B"])
    # Variant B has 3 degraded rows in the fixture, all correct, costs 0.006+0.008+0.011.
    assert abs(ci.point - (0.006 + 0.008 + 0.011) / 3) < 1e-9


def test_latency_p95_returns_finite_ci(rows) -> None:
    ci = latency_percentile(rows, p=0.95)
    assert ci.lo <= ci.point <= ci.hi


def test_failure_histogram_categories_complete(rows) -> None:
    hist = failure_histogram([r for r in rows if r["variant"] == "A"])
    assert set(hist.keys()) == set(CATEGORIES)
    # A's failures span multiple categories in the fixture.
    nonzero = {k for k, v in hist.items() if v > 0}
    assert {"missed_join", "temporal_misalignment", "schema_mismatch", "source_timeout"} <= nonzero


def test_failure_histogram_by_variant(rows) -> None:
    hist = failure_histogram_by_variant(rows)
    assert set(hist.keys()) == {"A", "B"}
    a_total = sum(hist["A"].values())
    b_total = sum(hist["B"].values())
    assert a_total > b_total  # the headline finding


def test_failure_rate_by_category_sums_to_overall_failure_rate(rows) -> None:
    a_rows = [r for r in rows if r["variant"] == "A"]
    rates = failure_rate_by_category(a_rows)
    overall = sum(rates.values())
    expected = sum(1 for r in a_rows if not r["correct"]) / len(a_rows)
    assert abs(overall - expected) < 1e-9


def test_classifier_passthrough_without_llm_judge() -> None:
    assert llm_judge_enabled() is False
    row = {"correct": False, "failure": "missed_join"}
    assert classify_row(row) == "missed_join"
    assert classify_row({"correct": True, "failure": "x"}) == "none"


def test_reclassify_preserves_other_fields() -> None:
    rows = [{"correct": False, "failure": "missed_join", "task_id": "t1"}]
    out = reclassify(rows)
    assert out[0]["task_id"] == "t1"
    assert out[0]["failure"] == "missed_join"


# ----- charts -----


def test_chart_failure_taxonomy_returns_figure_with_two_variants(rows) -> None:
    from arb.analysis.charts import chart_failure_taxonomy
    fig, ax = chart_failure_taxonomy(rows)
    assert ax.get_title().startswith("Failure distribution")
    # Two variants -> two bar groups -> at least 2*N bars.
    bars = [c for c in ax.containers]
    assert len(bars) >= 2


def test_chart_success_rate_has_three_conditions(rows) -> None:
    from arb.analysis.charts import chart_success_rate_by_condition
    fig, ax = chart_success_rate_by_condition(rows)
    labels = [t.get_text() for t in ax.get_xticklabels()]
    assert labels == ["clean", "degraded", "adversarial"]


def test_chart_cost_per_correct_separates_clean_and_degraded(rows) -> None:
    from arb.analysis.charts import chart_cost_per_correct
    fig, ax = chart_cost_per_correct(rows)
    labels = [t.get_text() for t in ax.get_xticklabels()]
    assert labels == ["clean", "degraded"]


def test_summary_table_shape(rows) -> None:
    from arb.analysis.charts import chart_summary_table
    s = chart_summary_table(rows)
    assert s["n"] == 18
    assert set(s["by_variant"].keys()) == {"A", "B"}
    assert "success_rate" in s["by_variant"]["A"]
    assert "cost_per_correct_degraded" in s["by_variant"]["B"]
