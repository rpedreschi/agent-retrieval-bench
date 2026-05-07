# agent-retrieval-bench

An open benchmark comparing two retrieval architectures for production AI agents:

- **Variant A** — *MCP per source.* One MCP tool per operational data source. The LLM composes joins at inference time across customers, orders, inventory, returns, support, and payments.
- **Variant B** — *Context engine.* A single MCP retrieval tool backed by continuously joined materialised views maintained on a streaming engine ([DeltaStream](https://www.deltastream.io/)).

The benchmark measures whether the architectural shift improves task success rate, grounding quality, latency distributions, cost per successful task, and the **shape of the failure distribution** under realistic production conditions (clean / degraded / adversarial).

Engineering credibility, statistical rigor, and honest reporting matter more than headline numbers.

## Quickstart

```bash
uv sync --extra dev
docker compose up -d            # local Kafka (KRaft) + Confluent Schema Registry
make bench-laptop               # end-to-end laptop run (Variant A only; B needs DeltaStream)
uv run pytest                   # 89 tests, no creds required
jupyter notebook notebooks/results.ipynb
```

The notebook produces every chart used in the blog post and conference talks. By default it consumes a synthetic fixture so it runs without a real benchmark; point `RUNS_PATH` at the output of `arb eval --execute` to render real numbers.

## Methodology

Three load-bearing decisions documented in `docs/methodology.md`:

1. **Snapshot-first grading.** The world generator emits to Kafka continuously, but each task is graded against a frozen `ground_truth_snapshot.json` captured at task-start time. Grading never races live state.
2. **Per-agent MCP token scoping.** Variant A's bearer token carries six per-source `*:read` scopes; Variant B's carries only `context:read`. Auth is enforced from day one.
3. **Headline metric:** `cost_per_correct_degraded` — total cost divided by # correct, restricted to the *degraded* condition. Clean is the demo; degraded is production.

## Architecture

See `docs/architecture.md` for the full picture. In one paragraph:

A single coherent world-state generator emits Avro-encoded events to eight Kafka topics under the `retail.` namespace. Variant A reads from those topics through six per-source serving stores (each with its own configurable replication lag and cache TTL); Variant B reads from three DeltaStream materialised views (`customer_360`, `order_state`, `returns_eligibility`) defined in `sql/views/`. The eval harness (Inspect AI) runs the same agent — same model, same system prompt — under both, the only difference being the toolset, across three conditions and two models, with bootstrapped 95% CIs and a structured failure taxonomy.

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

## Phase status

- **Phase 1** — World-state generator + 8 Avro Kafka topics + Docker Compose. ✅
- **Phase 2** — Variant A: six per-source MCP servers with freshness profiles, fault injection, scoped auth. ✅
- **Phase 3** — Variant B: single DeltaStream-backed MCP server with three materialised views. ✅ A DuckDB-backed alternative is stubbed (`arb.context.duckdb_engine`).
- **Phase 4** — Inspect AI eval harness skeleton: three task categories, snapshot grading, model registry. ✅ Real-model invocation lands in Phase 4b.
- **Phase 5** — Analysis surface: bootstrapped CIs, failure-taxonomy aggregation, matplotlib charts, results notebook. ✅
- **Phase 6** — Reproducibility: `make bench-laptop`, `CONTRIBUTING.md`, extension-point docs. ✅ (this phase)

## Extending

`docs/extending.md` — how to add a new materialised view, a new task category, a new condition, or a new model.

## What's NOT in v1

- Vector / embedding topic — extension point for future RAG comparison.
- Multi-tenancy — `tenant_id` exists but is hardcoded to one value.
- DuckDB-backed Variant B — stub only; see `arb.context.duckdb_engine`.
- Real-model execution wiring — Phase 4b.

## License

Apache-2.0. See `LICENSE`.
