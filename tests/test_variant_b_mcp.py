"""Variant B MCP tool: auth + dispatch through ContextEngine.

Uses an in-test FakeContextEngine so CI can exercise auth/scope/wiring without
DeltaStream credentials. Real view semantics are covered by integration tests
against DeltaStream (Phase 6).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from arb.mcp.auth import TokenRegistry
from arb.mcp.tools.context import get_view
from tests._fakes import FakeContextEngine

REPO = Path(__file__).resolve().parent.parent
TOKEN = "arb-variant-b-token"


@pytest.fixture
def setup():
    eng = FakeContextEngine()
    eng.put("customer_360", "cust-1", {"customer_id": "cust-1", "tier": "GOLD"})
    auth = TokenRegistry.from_dict({"tokens": {TOKEN: ["context:read"]}})
    return eng, auth


def test_get_view_with_valid_token_returns_payload(setup) -> None:
    eng, auth = setup
    res = get_view(
        engine=eng, auth=auth, token=TOKEN,
        name="customer_360", params={"customer_id": "cust-1"},
    )
    assert res["view"] == "customer_360"
    assert res["engine"] == "fake"
    assert res["payload"]["customer_id"] == "cust-1"


def test_get_view_without_token_returns_auth_error(setup) -> None:
    eng, auth = setup
    res = get_view(engine=eng, auth=auth, token=None, name="customer_360")
    assert res["error"] == "auth_error"
    assert res["code"] == "missing_token"


def test_get_view_with_wrong_scope_returns_auth_error(setup) -> None:
    eng, auth = setup
    auth.tokens["a-only"] = {"customers:read"}  # Variant A scope; not context:read
    res = get_view(engine=eng, auth=auth, token="a-only", name="customer_360")
    assert res["error"] == "auth_error"
    assert res["code"] == "insufficient_scope"


def test_unknown_key_returns_not_found(setup) -> None:
    eng, auth = setup
    res = get_view(
        engine=eng, auth=auth, token=TOKEN,
        name="customer_360", params={"customer_id": "ghost"},
    )
    assert res["error"] == "not_found"


def test_variant_b_token_carries_only_context_read() -> None:
    """Methodology guarantee: Variant B's token has exactly the one scope."""
    raw = yaml.safe_load((REPO / "config" / "variant_b.yaml").read_text())
    scopes = set(raw["auth"]["tokens"]["arb-variant-b-token"])
    assert scopes == {"context:read"}


def test_duckdb_stub_raises_not_implemented() -> None:
    """The DuckDB engine is a stub for a future addition."""
    from arb.context.duckdb_engine import DuckDBContextEngine
    with pytest.raises(NotImplementedError):
        DuckDBContextEngine()


def test_context_entrypoint_requires_deltastream_creds(monkeypatch) -> None:
    """build_mcp surfaces a clear error if DeltaStream credentials are missing."""
    pytest.importorskip("mcp.server.fastmcp")
    from arb.mcp.servers.context_entrypoint import build_mcp

    for k in ("ARB_DELTASTREAM_URL", "ARB_DELTASTREAM_TOKEN", "ARB_DELTASTREAM_DATABASE"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="DeltaStream credentials missing"):
        build_mcp(REPO / "config" / "variant_b.yaml")
