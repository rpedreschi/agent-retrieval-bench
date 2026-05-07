"""Condition application: deterministic per seed, correct fault profiles."""

from __future__ import annotations

from pathlib import Path

from arb.eval.conditions import Condition, apply_condition
from arb.mcp.servers.builder import load_variant_a

REPO = Path(__file__).resolve().parent.parent


def _bundle():
    return load_variant_a(REPO / "config" / "variant_a.yaml", inject_sleep=False)


def test_clean_zeroes_all_fault_profiles() -> None:
    bundle = _bundle()
    apply_condition(bundle, Condition.CLEAN, seed=1)
    for srv in bundle.servers.values():
        assert srv.faults.profile.latency_ms == 0
        assert srv.faults.profile.error_rate == 0.0


def test_degraded_picks_one_latency_and_one_error_source() -> None:
    bundle = _bundle()
    applied = apply_condition(bundle, Condition.DEGRADED, seed=42)
    assert applied.latency_source is not None
    assert applied.error_source is not None
    assert applied.latency_source != applied.error_source
    # At least one server has injected latency, at least one has error_rate>0.
    latency_servers = [s for s in bundle.servers.values() if s.faults.profile.latency_ms > 0]
    error_servers = [s for s in bundle.servers.values() if s.faults.profile.error_rate > 0]
    assert latency_servers and error_servers


def test_degraded_is_seed_deterministic() -> None:
    a = apply_condition(_bundle(), Condition.DEGRADED, seed=99)
    b = apply_condition(_bundle(), Condition.DEGRADED, seed=99)
    assert a.latency_source == b.latency_source
    assert a.error_source == b.error_source


def test_adversarial_sets_schema_drift_flag() -> None:
    applied = apply_condition(_bundle(), Condition.ADVERSARIAL, seed=7)
    assert applied.schema_drift is True
