# Architecture

## One picture

```
       ┌──────────────────────────┐
       │  WorldState generator    │   one coherent in-memory state
       │  (src/arb/world/)        │   tick-driven, seeded RNG
       └────────────┬─────────────┘
                    │ emits (Avro)
                    ▼
   ┌────────────────────────────────────┐
   │  8 Kafka topics under retail.*     │
   │  customers / tier_changes / orders │
   │  order_items / inventory_snapshots │
   │  returns / support_tickets         │
   │  payment_events                    │
   └──┬─────────────────────────────┬──┘
      │                             │
      │ per-source ingestion        │ continuous join
      ▼                             ▼
┌───────────────────┐     ┌──────────────────────┐
│  Variant A        │     │  Variant B           │
│  6 ServingStores  │     │  DeltaStream         │
│  + 6 MCP servers  │     │  3 materialised views│
│  *:read scopes    │     │  + 1 MCP server      │
│  per-source SLA   │     │  context:read scope  │
└─────────┬─────────┘     └──────────┬───────────┘
          │                          │
          │  identical system prompt │
          │  identical model         │
          ▼                          ▼
   ┌─────────────────────────────────────┐
   │      Inspect AI agent harness       │
   │   (src/arb/eval/, runs per task ×   │
   │    variant × model × condition ×    │
   │    seed)                            │
   └────────────────┬────────────────────┘
                    │ JSONL run rows
                    ▼
       ┌──────────────────────────┐
       │  Analysis (Phase 5)      │
       │  bootstrapped CIs        │
       │  failure taxonomy        │
       │  matplotlib charts       │
       └──────────────────────────┘
```

## Why this shape

### One coherent generator (not eight)

A separate generator per topic creates referential integrity gaps that destroy benchmark credibility. The single `WorldState` is the only source of truth: every emitted event is a pure function of a state transition, so an order can't reference a non-existent customer and a return can't reference a non-existent order. Tests assert this invariant on every run.

### Per-source serving stores (Variant A)

Real production systems have wildly different freshness profiles per source: inventory updates fast, payment events take seconds to settle, customer-tier rollups lag minutes. Each Variant A serving store carries its own `replication_lag_ms` and `cache_ttl_ms`, configured in `config/variant_a.yaml`. The agent must compose joins across this inconsistency in flight.

### Materialised views (Variant B)

Variant B collapses the per-source freshness story to a single, much-tighter SLA across all joined views. The reference SQL lives in `sql/views/` and is treated as the canonical spec. The single MCP `get_view(name, params)` interface means new views slot in without an interface change.

### Identical agent, different toolset

The methodology guarantees the agents differ *only* in their toolset. Same system prompt, same model, same temperature, same task — only the tools change. Anything else makes the comparison unfair and the talk slide harder to draw.

### Three conditions, two models, three seeds

Every (task, variant) cell runs under clean / degraded / adversarial, against `claude-opus-4-7` and `gpt-5`, with three seeds. Bootstrapped 95% CIs on every reported metric. The headline metric is `cost_per_correct_degraded` because clean is the demo and degraded is production.

### Snapshot-first grading

Each task captures a frozen `ground_truth_snapshot.json` at task-start time. The grader compares agent output against the snapshot, not against live Kafka — which has moved on by the time the agent finishes. Without this, grading races state and metrics drift between runs.

## Where the code lives

| Concern | Module |
|---|---|
| World state, scenarios, RNG | `src/arb/world/` |
| Avro producer | `src/arb/kafka/` |
| Per-source serving stores | `src/arb/serving/` |
| MCP auth, faults, six servers, one context server | `src/arb/mcp/` |
| ContextEngine protocol + DeltaStream client + view schemas | `src/arb/context/` |
| Eval harness (Inspect AI) | `src/arb/eval/` |
| Bootstrapped metrics + failure taxonomy + charts | `src/arb/analysis/` |
| Deterministic snapshot | `src/arb/snapshot.py` |
| CLI | `src/arb/cli.py` |
