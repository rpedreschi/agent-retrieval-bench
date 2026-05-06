"""Variant B MCP tool: auth + dispatch through ContextEngine."""
from __future__ import annotations

from pathlib import Path

import pytest

from arb.context.local import LocalContextEngine
from arb.mcp.auth import TokenRegistry
from arb.mcp.tools.context import get_view
from arb.world.generator import InMemorySink, run

REPO = Path(__file__).resolve().parent.parent
TOKEN = "arb-variant-b-token"


@pytest.fixture
def setup(laptop_config):
    sink = InMemorySink()
    run(laptop_config, sink, seed=42)
    eng = LocalContextEngine(
        freshness_sla_ms={"customer_360": 0, "order_state": 0, "returns_eligibility": 0},
        clock_ms=lambda: 10**13,
    )
    eng.feed(sink.by_topic())
    auth = TokenRegistry.from_dict({"tokens": {TOKEN: ["context:read"]}})
    return eng, auth, sink


def test_get_view_with_valid_token_returns_payload(setup) -> None:
    eng, auth, sink = setup
    cid = sink.by_topic()["retail.customers"][0]["customer_id"]
    res = get_view(
        engine=eng, auth=auth, token=TOKEN,
        name="customer_360", params={"customer_id": cid},
    )
    assert res["view"] == "customer_360"
    assert res["engine"] == "local"
    assert res["payload"]["customer_id"] == cid


def test_get_view_without_token_returns_auth_error(setup) -> None:
    eng, auth, _ = setup
    res = get_view(engine=eng, auth=auth, token=None, name="customer_360")
    assert res["error"] == "auth_error"
    assert res["code"] == "missing_token"


def test_get_view_with_wrong_scope_returns_auth_error(setup) -> None:
    eng, auth, _ = setup
    auth.tokens["a-only"] = {"customers:read"}  # Variant A's first scope; not context:read
    res = get_view(engine=eng, auth=auth, token="a-only", name="customer_360")
    assert res["error"] == "auth_error"
    assert res["code"] == "insufficient_scope"


def test_variant_b_token_carries_only_context_read() -> None:
    """Methodology guarantee: Variant B's token has exactly the one scope."""
    import yaml
    raw = yaml.safe_load((REPO / "config" / "variant_b.yaml").read_text())
    scopes = set(raw["auth"]["tokens"]["arb-variant-b-token"])
    assert scopes == {"context:read"}


def test_mcp_wiring_builds() -> None:
    """Smoke test: the FastMCP context server builds and registers the tool."""
    pytest.importorskip("mcp.server.fastmcp")
    from arb.mcp.servers.context_entrypoint import build_mcp
    app = build_mcp(REPO / "config" / "variant_b.yaml")
    assert app is not None
