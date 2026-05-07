"""Smoke test: the FastMCP wiring imports and registers tools for each source."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

mcp = pytest.importorskip("mcp.server.fastmcp")


@pytest.mark.parametrize(
    "source", ["customers", "orders", "inventory", "returns", "support", "payments"]
)
def test_each_source_builds_a_mcp_app_with_tools(source) -> None:
    from arb.mcp.servers.entrypoints import build_mcp_for

    app = build_mcp_for(source, REPO / "config" / "variant_a.yaml")
    # FastMCP exposes the registered tools via list_tools() (async). Just
    # confirm the app built; deeper transport tests live in Phase 4.
    assert app is not None
