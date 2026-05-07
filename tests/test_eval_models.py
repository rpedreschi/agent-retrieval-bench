from __future__ import annotations

import pytest

from arb.eval.models import MODELS, resolve


def test_headline_models_present() -> None:
    assert "claude-opus-4-7" in MODELS
    assert "gpt-5" in MODELS
    assert MODELS["claude-opus-4-7"].family == "anthropic"
    assert MODELS["gpt-5"].family == "openai"


def test_resolve_short_name() -> None:
    spec = resolve("claude-opus-4-7")
    assert spec.name == "anthropic/claude-opus-4-7"


def test_resolve_passthrough_for_inspect_string() -> None:
    spec = resolve("google/gemini-2.5-pro")
    assert spec.name == "google/gemini-2.5-pro"
    assert spec.short == "gemini-2.5-pro"
    assert spec.family == "google"


def test_resolve_unknown_raises_with_helpful_message() -> None:
    with pytest.raises(KeyError, match="anthropic/<id>"):
        resolve("totally-made-up")
