"""Optional Langfuse + RAGAS hooks. No-ops without env config.

We deliberately avoid making these mandatory: the harness must run end to end
without any third-party observability service. When ``LANGFUSE_PUBLIC_KEY``
and ``LANGFUSE_SECRET_KEY`` are present we wire traces through. When the
optional ``observability`` extra is installed and a ``ragas`` evaluator is
configured, we run grounding metrics on completed task transcripts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ObservabilityConfig:
    langfuse_enabled: bool = field(
        default_factory=lambda: bool(
            os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
        ),
    )
    ragas_enabled: bool = field(
        default_factory=lambda: os.environ.get("ARB_RAGAS_ENABLED") == "1",
    )


def maybe_langfuse_client() -> Any | None:
    cfg = ObservabilityConfig()
    if not cfg.langfuse_enabled:
        return None
    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]
    except ImportError:
        return None
    return Langfuse()


def maybe_ragas_score(
    *,
    question: str,
    answer: str,
    contexts: list[str],
) -> dict[str, float] | None:
    """Return faithfulness / context-precision / context-recall, or None."""
    cfg = ObservabilityConfig()
    if not cfg.ragas_enabled:
        return None
    try:
        from ragas.metrics import (  # type: ignore[import-not-found]
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError:
        return None
    # Stub: real wiring lives in Phase 4b. Return zeros so the schema is stable.
    _ = (question, answer, contexts, faithfulness, context_precision, context_recall)
    return {
        "faithfulness": 0.0,
        "context_precision": 0.0,
        "context_recall": 0.0,
    }
