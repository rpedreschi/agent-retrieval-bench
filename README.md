# agent-retrieval-bench

Open benchmark comparing two retrieval architectures for production AI agents:

- **Variant A** — MCP-per-source. One tool per operational data source; the LLM composes joins.
- **Variant B** — Context engine. A single retrieval interface backed by continuously joined materialized views on a streaming engine.

This repository is built in phases. **Phase 1 ships the world-state generator and Kafka topic layer only.** Subsequent phases add the two variants, the eval harness, the failure taxonomy, and the reproducibility wrapper.

## Methodology

Three load-bearing decisions are documented in `docs/methodology.md`:
snapshot-first grading, per-agent MCP token scoping, and the standardised
metric names (`cost_per_correct`, `cost_per_correct_degraded`).

## Phase 3 status

- Variant B (consolidated context engine) under `src/arb/context/`:
  - Three materialised views — `customer_360`, `order_state`,
    `returns_eligibility` — with output schemas in
    `src/arb/context/schemas.py` and reference SQL under `sql/views/`.
  - `ContextEngine` protocol with `get_view(name, params)`.
  - `LocalContextEngine` — in-process reference oracle for
    `make bench-laptop` and CI. Tagged `engine=local` in every result.
    **Not the system under test.** See `docs/byo_streaming.md`.
  - `DeltaStreamContextEngine` — production backend. Credentials via env
    vars (see `.env.example`); imports deferred so the local path runs
    without the SDK.
- Single Variant B MCP server (`python -m arb.mcp.servers.context_entrypoint`)
  with one bearer token carrying only `context:read`.
- `config/variant_b.yaml` with per-view freshness SLA (default 250 ms,
  per-view overrides supported).
- `docs/byo_streaming.md` documents the BYO-streaming-stack contract for
  forkers who don't use DeltaStream (Flink + ClickHouse, Materialize, etc).

## Phase 2 status

- Six per-source MCP servers (Variant A) under `src/arb/mcp/`:
  customers, orders, inventory, returns, support, payments.
- Each server is fed by a `ServingStore` with configurable
  `replication_lag_ms` and `cache_ttl_ms` (per-source freshness profiles in
  `config/variant_a.yaml`).
- Bearer-token auth: Variant A's token carries the six `*:read` scopes and
  nothing else. Calls without scope return a structured `auth_error`.
- Fault injection (`latency_ms`, `error_rate`) wired for the degraded
  condition; injected errors return a structured `source_error`.
- `arb snapshot` writes a deterministic ground-truth JSON used for grading.
- FastMCP wiring exposes one MCP server per source over stdio:
  `python -m arb.mcp.servers.entrypoints {customers|orders|...}`.

## Phase 1 status

- Single coherent world-state generator emitting to 8 Avro-encoded Kafka topics under the `retail.` namespace.
- Configurable scale (`config/scale.laptop.yaml`, `config/scale.full.yaml`).
- Deterministic given a seed; replayable named scenarios (incl. `chargeback_downgrade_refund`).
- Local Kafka (KRaft) + Confluent Schema Registry via `docker compose`.
- Tests for referential integrity, determinism, and scenario replay.

## Quickstart (laptop mode)

```bash
uv sync --extra dev
docker compose up -d            # local Kafka + Schema Registry
uv run arb generate --config config/scale.laptop.yaml --seed 42
uv run pytest
```

## Topics

All topics carry a `tenant_id` field (single-tenant in v1).

| Topic | Description |
|---|---|
| `retail.customers` | Customer profile / tier (SCD-style upserts). |
| `retail.customer_tier_changes` | Tier upgrade / downgrade event stream. |
| `retail.orders` | Order lifecycle events. |
| `retail.order_items` | Line-item granularity. |
| `retail.inventory_snapshots` | Per-SKU per-warehouse stock snapshots. |
| `retail.returns` | Return request lifecycle. |
| `retail.support_tickets` | Customer service interactions. |
| `retail.payment_events` | Chargebacks, refunds, payment failures. |

## Architecture decisions (locked for v1)

See `docs/` (added in later phases) and the inline rationale in `src/arb/world/`.

## What's NOT in v1

- Vector / embedding topic — extension point for future RAG comparison.
- Multi-tenancy — `tenant_id` exists but is hardcoded to one value.
- Variants A/B implementations — Phases 2 and 3.
- Eval harness — Phase 4.

## License

Apache-2.0. See `LICENSE`.
