"""Variant B: consolidated context engine.

The contract Variant B implementations must satisfy lives in :mod:`engine`.
The shipped backend is :class:`arb.context.deltastream.DeltaStreamContextEngine`.

A DuckDB-backed engine is stubbed in :mod:`arb.context.duckdb_engine` for a
future addition — see that module's docstring for the work required to wire
it up.
"""

from arb.context.engine import ContextEngine, ViewQuery, ViewResult
from arb.context.views import VIEWS, ViewSpec

__all__ = ["VIEWS", "ContextEngine", "ViewQuery", "ViewResult", "ViewSpec"]
