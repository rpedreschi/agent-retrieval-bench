"""Agent factories: identical system prompt across variants; tools differ."""

from __future__ import annotations

from pathlib import Path

import pytest

from arb.eval.agents import SYSTEM_PROMPT, _build_for_test
from arb.mcp.auth import TokenRegistry
from arb.mcp.servers.builder import load_variant_a
from tests._fakes import FakeContextEngine

REPO = Path(__file__).resolve().parent.parent


def _stub_factory_a(bundle, *, token):
    return [("tool", "get_customer"), ("tool", "get_order"), ("tool", "get_view_NOT")]


def _stub_factory_b(engine, auth, *, token):
    return [("tool", "get_view")]


def test_variant_a_and_b_share_system_prompt() -> None:
    bundle = load_variant_a(REPO / "config" / "variant_a.yaml", inject_sleep=False)
    auth = TokenRegistry.from_dict({"tokens": {"t": ["context:read"]}})
    a = _build_for_test(
        variant="A",
        bundle=bundle,
        token="arb-variant-a-token",
        tool_factory=_stub_factory_a,
    )
    b = _build_for_test(
        variant="B",
        engine=FakeContextEngine(),
        auth=auth,
        token="t",
        tool_factory=_stub_factory_b,
    )
    assert a.system_prompt == SYSTEM_PROMPT == b.system_prompt


def test_variant_a_has_more_tools_than_b() -> None:
    bundle = load_variant_a(REPO / "config" / "variant_a.yaml", inject_sleep=False)
    auth = TokenRegistry.from_dict({"tokens": {"t": ["context:read"]}})
    a = _build_for_test(
        variant="A",
        bundle=bundle,
        token="arb-variant-a-token",
        tool_factory=_stub_factory_a,
    )
    b = _build_for_test(
        variant="B",
        engine=FakeContextEngine(),
        auth=auth,
        token="t",
        tool_factory=_stub_factory_b,
    )
    assert len(a.tools) > len(b.tools)
    assert len(b.tools) == 1


def test_real_tool_factories_build_with_inspect_ai() -> None:
    """Smoke test: the real factories return non-empty tool lists when
    inspect_ai is available."""
    pytest.importorskip("inspect_ai.tool")
    from arb.eval.agents import variant_a_tools, variant_b_tools

    bundle = load_variant_a(REPO / "config" / "variant_a.yaml", inject_sleep=False)
    auth = TokenRegistry.from_dict({"tokens": {"t": ["context:read"]}})
    a_tools = variant_a_tools(bundle, token="arb-variant-a-token")
    b_tools = variant_b_tools(FakeContextEngine(), auth, token="t")
    assert len(a_tools) >= 6  # at least one per source
    assert len(b_tools) == 1
