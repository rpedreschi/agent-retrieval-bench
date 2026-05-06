# agent-retrieval-bench

Open benchmark comparing two retrieval architectures for production AI agents:

- **Variant A** — MCP-per-source. One tool per operational data source; the LLM composes joins.
- **Variant B** — Context engine. A single retrieval interface backed by continuously joined materialized views on a streaming engine.

This repository is built in phases. **Phase 1 ships the world-state generator and Kafka topic layer only.** Subsequent phases add the two variants, the eval harness, the failure taxonomy, and the reproducibility wrapper.

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
