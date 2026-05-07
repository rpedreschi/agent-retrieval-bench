"""Phase 5 analysis surface: bootstrapped metrics, failure taxonomy, charts."""

from arb.analysis.metrics import (
    BootstrapCI,
    bootstrap_ci,
    cost_per_correct,
    cost_per_correct_degraded,
    load_runs,
    success_rate,
)
from arb.analysis.taxonomy import (
    failure_histogram,
    failure_histogram_by_variant,
)

__all__ = [
    "BootstrapCI",
    "bootstrap_ci",
    "cost_per_correct",
    "cost_per_correct_degraded",
    "failure_histogram",
    "failure_histogram_by_variant",
    "load_runs",
    "success_rate",
]
