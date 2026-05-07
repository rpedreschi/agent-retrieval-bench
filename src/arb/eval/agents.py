"""Inspect AI agent factories for Variant A and Variant B.

The two factories exist to enforce the methodology guarantee that the agents
differ ONLY in their toolset. System prompt, model, temperature, and runtime
controls are identical. Variant A receives six per-source MCP tools; Variant
B receives a single ``get_view`` tool.

Phase 4 wires Inspect AI ``Tool`` shims that call the underlying SourceServer
/ ContextEngine in-process. Phase 6 promotes them to subprocess MCP transport
for the headline runs (so the benchmark exercises real MCP, not in-process
function calls).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from arb.context.engine import ContextEngine, ViewQuery
from arb.mcp.auth import TokenRegistry
from arb.mcp.servers.builder import VariantABundle
from arb.mcp.tools import customers as t_customers
from arb.mcp.tools import inventory as t_inventory
from arb.mcp.tools import orders as t_orders
from arb.mcp.tools import payments as t_payments
from arb.mcp.tools import returns as t_returns
from arb.mcp.tools import support as t_support

# Identical across both variants — methodology guarantee.
SYSTEM_PROMPT = (
    "You are a customer-service agent for a retail business. You have read-only "
    "access to operational data through the tools provided. Use the tools to "
    "answer questions, identify issues, and recommend actions. When you need "
    "data, prefer a single tool call over many. Be precise: cite the order id, "
    "customer id, or return id you reasoned about. If you cannot answer with "
    "the data available, say so explicitly."
)


@dataclass
class AgentBuild:
    system_prompt: str
    tools: list[Any]  # Inspect AI Tool instances (or our test stubs)


# -------- Tool factory: variant A (six per-source servers) ------------------


def variant_a_tools(bundle: VariantABundle, *, token: str) -> list[Any]:
    """Wrap each Variant A tool function as an Inspect AI ``Tool``.

    Imports of ``inspect_ai`` are deferred so unit tests can patch this
    function with a no-network fake without installing Inspect AI.
    """
    from inspect_ai.tool import tool

    @tool
    def get_customer():
        async def execute(customer_id: str) -> Any:
            return t_customers.get_customer(
                bundle.servers["customers"],
                token=token,
                customer_id=customer_id,
            )

        return execute

    @tool
    def get_customer_tier_history():
        async def execute(customer_id: str) -> Any:
            return t_customers.get_customer_tier_history(
                bundle.servers["customer_tier_changes"],
                token=token,
                customer_id=customer_id,
            )

        return execute

    @tool
    def get_order():
        async def execute(order_id: str) -> Any:
            return t_orders.get_order(
                bundle.servers["orders"],
                token=token,
                order_id=order_id,
            )

        return execute

    @tool
    def list_orders_for_customer():
        async def execute(customer_id: str, limit: int = 50) -> Any:
            return t_orders.list_orders_for_customer(
                bundle.servers["orders"],
                token=token,
                customer_id=customer_id,
                limit=limit,
            )

        return execute

    @tool
    def get_order_items():
        async def execute(order_id: str) -> Any:
            return t_orders.get_order_items(
                bundle.servers["order_items"],
                token=token,
                order_id=order_id,
            )

        return execute

    @tool
    def get_stock():
        async def execute(sku: str, warehouse_id: str) -> Any:
            return t_inventory.get_stock(
                bundle.servers["inventory"],
                token=token,
                sku=sku,
                warehouse_id=warehouse_id,
            )

        return execute

    @tool
    def get_return():
        async def execute(return_id: str) -> Any:
            return t_returns.get_return(
                bundle.servers["returns"],
                token=token,
                return_id=return_id,
            )

        return execute

    @tool
    def list_returns_for_order():
        async def execute(order_id: str) -> Any:
            return t_returns.list_returns_for_order(
                bundle.servers["returns"],
                token=token,
                order_id=order_id,
            )

        return execute

    @tool
    def get_ticket():
        async def execute(ticket_id: str) -> Any:
            return t_support.get_ticket(
                bundle.servers["support_tickets"],
                token=token,
                ticket_id=ticket_id,
            )

        return execute

    @tool
    def list_tickets_for_customer():
        async def execute(customer_id: str, limit: int = 50) -> Any:
            return t_support.list_tickets_for_customer(
                bundle.servers["support_tickets"],
                token=token,
                customer_id=customer_id,
                limit=limit,
            )

        return execute

    @tool
    def list_payment_events_for_order():
        async def execute(order_id: str) -> Any:
            return t_payments.list_payment_events_for_order(
                bundle.servers["payment_events"],
                token=token,
                order_id=order_id,
            )

        return execute

    return [
        get_customer(),
        get_customer_tier_history(),
        get_order(),
        list_orders_for_customer(),
        get_order_items(),
        get_stock(),
        get_return(),
        list_returns_for_order(),
        get_ticket(),
        list_tickets_for_customer(),
        list_payment_events_for_order(),
    ]


def variant_a_agent(bundle: VariantABundle, *, token: str) -> AgentBuild:
    return AgentBuild(system_prompt=SYSTEM_PROMPT, tools=variant_a_tools(bundle, token=token))


# -------- Tool factory: variant B (single get_view) -------------------------


def variant_b_tools(
    engine: ContextEngine,
    auth: TokenRegistry,
    *,
    token: str,
) -> list[Any]:
    from inspect_ai.tool import tool

    @tool
    def get_view():
        async def execute(
            name: str,
            params: dict[str, Any] | None = None,
            limit: int | None = None,
        ) -> Any:
            try:
                auth.check(token, "context:read")
            except Exception as e:  # AuthError carries to_dict
                to_dict = getattr(e, "to_dict", None)
                if callable(to_dict):
                    return to_dict()
                raise
            return engine.get_view(
                ViewQuery(name=name, params=params or {}, limit=limit)
            ).to_tool_response()

        return execute

    return [get_view()]


def variant_b_agent(
    engine: ContextEngine,
    auth: TokenRegistry,
    *,
    token: str,
) -> AgentBuild:
    return AgentBuild(
        system_prompt=SYSTEM_PROMPT,
        tools=variant_b_tools(engine, auth, token=token),
    )


# -------- Test hook ---------------------------------------------------------


def _build_for_test(
    *,
    variant: str,
    bundle: VariantABundle | None = None,
    engine: ContextEngine | None = None,
    auth: TokenRegistry | None = None,
    token: str = "",
    tool_factory: Callable[..., list[Any]] | None = None,
) -> AgentBuild:
    """Bypasses inspect_ai imports for unit tests by accepting a tool_factory."""
    if variant == "A":
        assert bundle is not None
        tools = (tool_factory or variant_a_tools)(bundle, token=token)
    elif variant == "B":
        assert engine is not None and auth is not None
        tools = (tool_factory or variant_b_tools)(engine, auth, token=token)
    else:
        raise ValueError(variant)
    return AgentBuild(system_prompt=SYSTEM_PROMPT, tools=tools)
