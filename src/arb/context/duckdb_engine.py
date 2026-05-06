"""DuckDB-backed ContextEngine — STUB / TODO.

Not implemented in v1. The intent: an embedded ContextEngine that loads events
into DuckDB tables and runs DuckDB-dialect mirrors of the views in
``sql/views/`` so the laptop pipeline can run end-to-end without DeltaStream
credentials. Until then, Variant B requires DeltaStream — see
``arb.context.deltastream``.

When wiring this up, the work is roughly:

1. Add ``duckdb`` to dependencies.
2. Add ``sql/views/duckdb/{customer_360,order_state,returns_eligibility}.sql``
   mirroring the DeltaStream files (separate dialect, kept in sync).
3. Implement ``DuckDBContextEngine.feed(events_by_topic)`` to insert into
   per-topic tables, and ``get_view`` to ``SELECT`` against the view.
4. Add a Phase-6 equivalence test asserting payload equality against
   DeltaStream on a fixed fixture.
5. Re-introduce ``ARB_CONTEXT_ENGINE=duckdb|deltastream`` selection in
   ``arb.mcp.servers.context_entrypoint``.

Headline benchmark numbers must continue to come from DeltaStream regardless.
"""
from __future__ import annotations

from typing import Any

from arb.context.engine import ViewQuery, ViewResult


class DuckDBContextEngine:
    engine_name: str = "duckdb"

    def __init__(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError(
            "DuckDBContextEngine is a stub for a future addition. "
            "Variant B currently requires DeltaStream — see "
            "arb.context.deltastream.DeltaStreamContextEngine."
        )

    def get_view(self, query: ViewQuery) -> ViewResult:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover
        raise NotImplementedError
