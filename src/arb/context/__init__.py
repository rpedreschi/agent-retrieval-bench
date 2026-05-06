"""Variant B: consolidated context engine.

The contract two implementations must satisfy is in ``engine.py``. The
DeltaStream-backed implementation (``deltastream.py``) produces the headline
benchmark numbers. The in-process ``local.py`` implementation lets the laptop
pipeline run without DeltaStream credentials and serves as a reference oracle
for view semantics. See docs/byo_streaming.md.
"""
from arb.context.engine import ContextEngine, ViewQuery, ViewResult
from arb.context.views import VIEWS, ViewSpec

__all__ = ["VIEWS", "ContextEngine", "ViewQuery", "ViewResult", "ViewSpec"]
