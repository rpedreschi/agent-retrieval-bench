"""Matplotlib chart helpers for the results notebook.

Each function returns ``(fig, ax)``. The notebook composes them into the
pictures used in the blog post and talk. We keep these helpers stylistically
neutral — no theming, no branded palette — so the same code runs in CI for
test-coverage and in the notebook for publication.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from arb.analysis.metrics import (
    BootstrapCI,
    by_condition,
    by_variant,
    cost_per_correct,
    success_rate,
)
from arb.analysis.taxonomy import CATEGORIES, failure_histogram_by_variant


def chart_failure_taxonomy(rows: Sequence[dict[str, Any]]) -> tuple[Any, Any]:
    """Per-variant failure histogram. The headline chart for the talk."""
    hist = failure_histogram_by_variant(rows)
    variants = sorted(hist.keys())
    x = np.arange(len(CATEGORIES))
    width = 0.8 / max(len(variants), 1)

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, v in enumerate(variants):
        counts = [hist[v].get(c, 0) for c in CATEGORIES]
        ax.bar(x + i * width, counts, width, label=f"Variant {v}")
    ax.set_xticks(x + width * (len(variants) - 1) / 2)
    ax.set_xticklabels(CATEGORIES, rotation=30, ha="right")
    ax.set_ylabel("# failures")
    ax.set_title("Failure distribution by category, per variant")
    ax.legend()
    fig.tight_layout()
    return fig, ax


def chart_success_rate_by_condition(rows: Sequence[dict[str, Any]]) -> tuple[Any, Any]:
    """Per-condition success rate with bootstrapped 95% CIs, grouped by variant."""
    by_v = by_variant(rows)
    conditions = ["clean", "degraded", "adversarial"]
    variants = sorted(by_v.keys())
    x = np.arange(len(conditions))
    width = 0.8 / max(len(variants), 1)

    fig, ax = plt.subplots(figsize=(8, 5))
    for i, v in enumerate(variants):
        cis: list[BootstrapCI] = []
        for cond in conditions:
            subset = [r for r in by_v[v] if r["condition"] == cond]
            cis.append(success_rate(subset))
        points = [c.point for c in cis]
        errs_lo = [c.point - c.lo for c in cis]
        errs_hi = [c.hi - c.point for c in cis]
        ax.bar(
            x + i * width, points, width, label=f"Variant {v}",
            yerr=[errs_lo, errs_hi], capsize=4,
        )
    ax.set_xticks(x + width * (len(variants) - 1) / 2)
    ax.set_xticklabels(conditions)
    ax.set_ylabel("success rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("Task success rate by condition (95% CIs)")
    ax.legend()
    fig.tight_layout()
    return fig, ax


def chart_cost_per_correct(rows: Sequence[dict[str, Any]]) -> tuple[Any, Any]:
    """Cost-per-correct comparison, separating clean vs degraded for the
    headline ``cost_per_correct_degraded`` story."""
    by_v = by_variant(rows)
    splits = ["clean", "degraded"]
    variants = sorted(by_v.keys())
    x = np.arange(len(splits))
    width = 0.8 / max(len(variants), 1)

    fig, ax = plt.subplots(figsize=(7, 5))
    for i, v in enumerate(variants):
        points = []
        errs_lo = []
        errs_hi = []
        for cond in splits:
            ci = cost_per_correct([r for r in by_v[v] if r["condition"] == cond])
            points.append(0.0 if np.isnan(ci.point) else ci.point)
            errs_lo.append(0.0 if np.isnan(ci.lo) else ci.point - ci.lo)
            errs_hi.append(0.0 if np.isnan(ci.hi) else ci.hi - ci.point)
        ax.bar(
            x + i * width, points, width, label=f"Variant {v}",
            yerr=[errs_lo, errs_hi], capsize=4,
        )
    ax.set_xticks(x + width * (len(variants) - 1) / 2)
    ax.set_xticklabels(splits)
    ax.set_ylabel("cost per correct (USD)")
    ax.set_title("Cost per correct task — clean vs degraded")
    ax.legend()
    fig.tight_layout()
    return fig, ax


def chart_summary_table(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Numeric summary used by the notebook header. Not a chart, but lives
    next to them so import sites are simple."""
    out: dict[str, Any] = {"n": len(rows), "by_variant": {}}
    for v, rs in by_variant(rows).items():
        sr = success_rate(rs)
        cpc = cost_per_correct(rs)
        cpc_deg = cost_per_correct([r for r in rs if r["condition"] == "degraded"])
        out["by_variant"][v] = {
            "n": len(rs),
            "success_rate": sr.as_tuple(),
            "cost_per_correct": cpc.as_tuple(),
            "cost_per_correct_degraded": cpc_deg.as_tuple(),
        }
    out["by_condition"] = {c: len(rs) for c, rs in by_condition(rows).items()}
    return out
