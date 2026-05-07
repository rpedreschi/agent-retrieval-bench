"""FastMCP entrypoints for the six Variant A source servers.

Each entrypoint is invoked as e.g. ``python -m arb.mcp.servers.entrypoints customers``
and exposes that source's tools over MCP stdio. The bearer token is read from
the ``ARB_MCP_TOKEN`` request header (set by the harness).

Tests do not exercise this transport — they call the tool functions directly
via the SourceServer. The entrypoints are thin enough that one smoke test
covers the wiring end to end.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from arb.mcp.servers.builder import VariantABundle, load_variant_a


def _token() -> str | None:
    return os.environ.get("ARB_MCP_TOKEN")


def _register_customers(mcp: Any, bundle: VariantABundle) -> None:
    from arb.mcp.tools import customers as t

    @mcp.tool()
    def get_customer(customer_id: str) -> Any:
        return t.get_customer(bundle.servers["customers"], token=_token(), customer_id=customer_id)

    @mcp.tool()
    def get_customer_tier_history(customer_id: str) -> Any:
        return t.get_customer_tier_history(
            bundle.servers["customer_tier_changes"],
            token=_token(),
            customer_id=customer_id,
        )


def _register_orders(mcp: Any, bundle: VariantABundle) -> None:
    from arb.mcp.tools import orders as t

    @mcp.tool()
    def get_order(order_id: str) -> Any:
        return t.get_order(bundle.servers["orders"], token=_token(), order_id=order_id)

    @mcp.tool()
    def list_orders_for_customer(customer_id: str, limit: int = 50) -> Any:
        return t.list_orders_for_customer(
            bundle.servers["orders"],
            token=_token(),
            customer_id=customer_id,
            limit=limit,
        )

    @mcp.tool()
    def get_order_items(order_id: str) -> Any:
        return t.get_order_items(bundle.servers["order_items"], token=_token(), order_id=order_id)


def _register_inventory(mcp: Any, bundle: VariantABundle) -> None:
    from arb.mcp.tools import inventory as t

    @mcp.tool()
    def get_stock(sku: str, warehouse_id: str) -> Any:
        return t.get_stock(
            bundle.servers["inventory"],
            token=_token(),
            sku=sku,
            warehouse_id=warehouse_id,
        )

    @mcp.tool()
    def list_stock_for_sku(sku: str) -> Any:
        return t.list_stock_for_sku(bundle.servers["inventory"], token=_token(), sku=sku)


def _register_returns(mcp: Any, bundle: VariantABundle) -> None:
    from arb.mcp.tools import returns as t

    @mcp.tool()
    def get_return(return_id: str) -> Any:
        return t.get_return(bundle.servers["returns"], token=_token(), return_id=return_id)

    @mcp.tool()
    def list_returns_for_order(order_id: str) -> Any:
        return t.list_returns_for_order(
            bundle.servers["returns"],
            token=_token(),
            order_id=order_id,
        )


def _register_support(mcp: Any, bundle: VariantABundle) -> None:
    from arb.mcp.tools import support as t

    @mcp.tool()
    def get_ticket(ticket_id: str) -> Any:
        return t.get_ticket(bundle.servers["support_tickets"], token=_token(), ticket_id=ticket_id)

    @mcp.tool()
    def list_tickets_for_customer(customer_id: str, limit: int = 50) -> Any:
        return t.list_tickets_for_customer(
            bundle.servers["support_tickets"],
            token=_token(),
            customer_id=customer_id,
            limit=limit,
        )


def _register_payments(mcp: Any, bundle: VariantABundle) -> None:
    from arb.mcp.tools import payments as t

    @mcp.tool()
    def list_payment_events_for_order(order_id: str) -> Any:
        return t.list_payment_events_for_order(
            bundle.servers["payment_events"],
            token=_token(),
            order_id=order_id,
        )


REGISTRARS: dict[str, Callable[[Any, VariantABundle], None]] = {
    "customers": _register_customers,
    "orders": _register_orders,
    "inventory": _register_inventory,
    "returns": _register_returns,
    "support": _register_support,
    "payments": _register_payments,
}


def build_mcp_for(source: str, config_path: Path) -> Any:
    """Build a FastMCP app for one source. Imports mcp lazily."""
    from mcp.server.fastmcp import FastMCP

    bundle = load_variant_a(config_path)
    mcp = FastMCP(f"arb-variant-a-{source}")
    REGISTRARS[source](mcp, bundle)
    return mcp


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 1 or args[0] not in REGISTRARS:
        print(f"usage: entrypoints <{'|'.join(REGISTRARS)}> [config_path]", file=sys.stderr)
        return 2
    source = args[0]
    cfg = Path(args[1]) if len(args) > 1 else Path("config/variant_a.yaml")
    mcp = build_mcp_for(source, cfg)
    mcp.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
