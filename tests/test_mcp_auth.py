from __future__ import annotations

from arb.mcp.auth import AuthError, TokenRegistry


def test_known_token_with_scope_passes() -> None:
    reg = TokenRegistry.from_dict({"tokens": {"good": ["customers:read"]}})
    reg.check("good", "customers:read")  # should not raise


def test_unknown_token_rejected() -> None:
    reg = TokenRegistry.from_dict({"tokens": {"good": ["customers:read"]}})
    try:
        reg.check("bad", "customers:read")
    except AuthError as e:
        assert e.code == "unknown_token"
    else:
        raise AssertionError("expected AuthError")


def test_missing_scope_rejected() -> None:
    reg = TokenRegistry.from_dict({"tokens": {"good": ["customers:read"]}})
    try:
        reg.check("good", "orders:read")
    except AuthError as e:
        assert e.code == "insufficient_scope"
    else:
        raise AssertionError("expected AuthError")


def test_missing_token_rejected() -> None:
    reg = TokenRegistry()
    try:
        reg.check(None, "customers:read")
    except AuthError as e:
        assert e.code == "missing_token"
    else:
        raise AssertionError("expected AuthError")
