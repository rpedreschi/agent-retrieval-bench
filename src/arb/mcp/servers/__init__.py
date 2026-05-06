"""MCP server entrypoints (FastMCP wiring).

Each entrypoint loads ``config/variant_a.yaml``, builds a SourceServer plus
its companion stores, and exposes tools over stdio. Tests target the tool
functions directly; the FastMCP wiring is exercised by a smoke test.
"""
