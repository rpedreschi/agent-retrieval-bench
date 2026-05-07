"""Run-row aggregation with bootstrapped 95% CIs.

Operates on the JSONL produced by ``arb eval`` (one ``RunRow`` per line).
Bootstrap is used everywhere instead of parametric CIs because we make no
distributional assumptions about per-run cost or latency.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


def load_runs(path: Path) -> list[dict[str, Any]]:
    """Read JSONL of RunRow records."""
    with Path(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]


@dataclass(frozen=True)
class BootstrapCI:
    point: float
    lo: float
    hi: float

    def as_tuple(self) -> tuple[float, float, float]:
        return self.point, self.lo, self.hi


def bootstrap_ci(
    values: Sequence[float],
    *,
    statistic: Callable[[Sequence[float]], float] = float,  # placeholder; overridden below
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> BootstrapCI:
    """Bootstrapped CI for a scalar statistic over ``values``.

    Default ``statistic`` is the mean. For ratios (e.g. success rate) the
    caller passes a custom statistic that operates on the resample.
    """
    if not values:
        return BootstrapCI(float("nan"), float("nan"), float("nan"))
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    def _mean(xs: Sequence[float]) -> float:
        return float(np.mean(xs))

    stat: Callable[[Sequence[float]], float] = _mean if statistic is float else statistic
    point = stat(arr)
    n = len(arr)
    samples = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        samples[i] = stat(arr[idx])
    alpha = (1.0 - confidence) / 2.0
    lo = float(np.quantile(samples, alpha))
    hi = float(np.quantile(samples, 1.0 - alpha))
    return BootstrapCI(point=float(point), lo=lo, hi=hi)


# ----------------------------------------------------------------- helpers


def _filter(rows: Iterable[dict[str, Any]], **kw: Any) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        if all(r.get(k) == v for k, v in kw.items()):
            out.append(r)
    return out


# ----------------------------------------------------------------- metrics


def success_rate(rows: Sequence[dict[str, Any]], *, seed: int = 0) -> BootstrapCI:
    """Fraction of correct rows with bootstrapped CI."""
    flags = [1.0 if r["correct"] else 0.0 for r in rows]
    return bootstrap_ci(flags, seed=seed)


def cost_per_correct(rows: Sequence[dict[str, Any]], *, seed: int = 0) -> BootstrapCI:
    """Total cost divided by # correct, with CI by bootstrapping the row set."""
    if not rows:
        return BootstrapCI(float("nan"), float("nan"), float("nan"))

    def stat(sample: Sequence[dict[str, Any]] | np.ndarray) -> float:
        # When called by bootstrap_ci, sample is a numpy array of indices
        # into the original list — so we accept either dicts or indices.
        if len(sample) == 0:
            return float("nan")
        xs = sample if isinstance(sample[0], dict) else [rows[int(i)] for i in sample]
        total_cost = sum(r["cost_usd"] for r in xs)
        correct = sum(1 for r in xs if r["correct"])
        return total_cost / correct if correct else float("nan")

    # Operate on indices so we can deref dicts inside the statistic.
    n = len(rows)
    rng = np.random.default_rng(seed)
    point = stat(list(range(n)))
    n_resamples = 2000
    samples = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        samples[i] = stat(idx)
    samples = samples[~np.isnan(samples)]
    if samples.size == 0:
        return BootstrapCI(float(point), float("nan"), float("nan"))
    return BootstrapCI(
        point=float(point),
        lo=float(np.quantile(samples, 0.025)),
        hi=float(np.quantile(samples, 0.975)),
    )


def cost_per_correct_degraded(rows: Sequence[dict[str, Any]], *, seed: int = 0) -> BootstrapCI:
    """Headline metric: cost_per_correct restricted to the degraded condition."""
    return cost_per_correct(_filter(rows, condition="degraded"), seed=seed)


def latency_percentile(
    rows: Sequence[dict[str, Any]], *, p: float = 0.95, seed: int = 0,
) -> BootstrapCI:
    if not rows:
        return BootstrapCI(float("nan"), float("nan"), float("nan"))

    def stat(xs: Sequence[float]) -> float:
        return float(np.quantile(xs, p))

    return bootstrap_ci([r["latency_ms"] for r in rows], statistic=stat, seed=seed)


def by_variant(rows: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["variant"], []).append(r)
    return out


def by_condition(rows: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["condition"], []).append(r)
    return out
