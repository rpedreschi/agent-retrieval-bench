from __future__ import annotations

from arb.mcp.auth import TokenRegistry
from arb.mcp.faults import FaultProfile
from arb.mcp.server_base import build_source_server
from arb.mcp.tools import customers as t_customers
from arb.serving import projectors
from arb.serving.store import FreshnessProfile

TOKEN = "tok"


def _server(error_rate: float, seed: int = 0):
    auth = TokenRegistry.from_dict({"tokens": {TOKEN: ["customers:read"]}})
    srv = build_source_server(
        name="customers",
        required_scope="customers:read",
        projector=projectors.customers,
        auth=auth,
        freshness=FreshnessProfile(),
        fault_profile=FaultProfile(error_rate=error_rate),
        seed=seed,
        inject_sleep=False,
    )
    srv.store.ingest(
        [
            {"customer_id": "c1", "tier": "BRONZE", "occurred_at_ms": 1, "version": 1},
        ]
    )
    srv.clock_ms = lambda: 10**13
    return srv


def test_zero_error_rate_never_injects() -> None:
    srv = _server(0.0)
    for _ in range(50):
        res = t_customers.get_customer(srv, token=TOKEN, customer_id="c1")
        assert res["customer_id"] == "c1"


def test_full_error_rate_always_injects_structured_error() -> None:
    srv = _server(1.0)
    res = t_customers.get_customer(srv, token=TOKEN, customer_id="c1")
    assert res["error"] == "source_error"
    assert res["code"] == "source_timeout"


def test_partial_error_rate_is_seed_deterministic() -> None:
    s1 = _server(0.5, seed=123)
    s2 = _server(0.5, seed=123)
    out1 = [t_customers.get_customer(s1, token=TOKEN, customer_id="c1") for _ in range(50)]
    out2 = [t_customers.get_customer(s2, token=TOKEN, customer_id="c1") for _ in range(50)]
    assert out1 == out2
    assert any(r.get("error") == "source_error" for r in out1)
    assert any(r.get("customer_id") == "c1" for r in out1)


def test_variant_a_token_has_all_six_scopes() -> None:
    """Methodology guarantee: Variant A's token covers every per-source read scope."""
    from pathlib import Path

    from arb.mcp.servers.builder import load_variant_a

    repo = Path(__file__).resolve().parent.parent
    bundle = load_variant_a(repo / "config" / "variant_a.yaml", inject_sleep=False)
    scopes = bundle.auth.tokens["arb-variant-a-token"]
    expected = {
        "customers:read",
        "orders:read",
        "inventory:read",
        "returns:read",
        "support:read",
        "payments:read",
    }
    assert scopes == expected
