"""Variant B: single retrieval tool over the consolidated ContextEngine."""
from __future__ import annotations

from typing import Any

from arb.context.engine import ContextEngine, ViewQuery
from arb.mcp.auth import AuthError, TokenRegistry

CONTEXT_SCOPE = "context:read"


def get_view(
    *,
    engine: ContextEngine,
    auth: TokenRegistry,
    token: str | None,
    name: str,
    params: dict[str, Any] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    try:
        auth.check(token, CONTEXT_SCOPE)
    except AuthError as e:
        return e.to_dict()
    result = engine.get_view(ViewQuery(name=name, params=params or {}, limit=limit))
    return result.to_tool_response()
