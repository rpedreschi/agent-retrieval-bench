"""FastMCP entrypoint for the single Variant B context server.

Variant B is backed by DeltaStream. Credentials must be set in the environment
(see ``.env.example``); this entrypoint exits with a clear error if they are
missing.

Run with::

    python -m arb.mcp.servers.context_entrypoint [config_path]

A DuckDB-backed alternative is stubbed in ``arb.context.duckdb_engine`` for a
future addition.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml

from arb.context.deltastream import DeltaStreamContextEngine
from arb.context.engine import ContextEngine
from arb.mcp.auth import TokenRegistry
from arb.mcp.tools.context import get_view


def _token() -> str | None:
    return os.environ.get("ARB_MCP_TOKEN")


def build_engine() -> ContextEngine:
    return DeltaStreamContextEngine()


def build_mcp(config_path: Path) -> Any:
    from mcp.server.fastmcp import FastMCP

    raw = yaml.safe_load(config_path.read_text())
    auth = TokenRegistry.from_dict(raw.get("auth", {}))
    engine = build_engine()

    mcp = FastMCP("arb-variant-b-context")

    @mcp.tool()
    def get_view_tool(
        name: str,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return get_view(
            engine=engine,
            auth=auth,
            token=_token(),
            name=name,
            params=params,
            limit=limit,
        )

    return mcp


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    args = argv if argv is not None else sys.argv[1:]
    cfg = Path(args[0]) if args else Path("config/variant_b.yaml")
    mcp = build_mcp(cfg)
    mcp.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
