"""Model registry for the eval harness.

Inspect AI uses provider-prefixed model strings (``anthropic/...``,
``openai/...``, ``google/...``). The registry below pins the two models the
benchmark reports headline numbers against; everything else is reachable via
the same Inspect AI strings, so a forker can plug in their own model with
one line of YAML — see docs/models.md.

API keys are read from the environment by Inspect AI directly:
``ANTHROPIC_API_KEY``, ``OPENAI_API_KEY``, etc. We never thread them
through code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    name: str  # Inspect AI provider/id, e.g. "anthropic/claude-opus-4-7"
    short: str  # display name in result tables
    family: str  # "anthropic" | "openai" | "google" | "<other>"


# Headline models. To add another, append to this list AND list it in your
# config/eval.yaml ``models:`` block. Inspect AI will route to it as long as
# the corresponding API key is exported.
MODELS: dict[str, ModelSpec] = {
    "claude-opus-4-7": ModelSpec(
        name="anthropic/claude-opus-4-7",
        short="claude-opus-4-7",
        family="anthropic",
    ),
    "gpt-5": ModelSpec(
        name="openai/gpt-5",
        short="gpt-5",
        family="openai",
    ),
}


def resolve(name: str) -> ModelSpec:
    """Look up a model by short name, or pass-through a fully-qualified
    Inspect AI string for forkers using a model not in the headline registry."""
    if name in MODELS:
        return MODELS[name]
    if "/" in name:
        family = name.split("/", 1)[0]
        return ModelSpec(name=name, short=name.rsplit("/", 1)[-1], family=family)
    raise KeyError(
        f"unknown model {name!r}; either add it to arb.eval.models.MODELS or "
        "pass a fully-qualified Inspect AI string like 'anthropic/<id>'."
    )
