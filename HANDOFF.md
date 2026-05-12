# HANDOFF.md — agent-retrieval-bench

A briefing document for someone who hasn't seen this repo before. Contains the literal contents of all key files; nothing is paraphrased.

---

## 1. Purpose & origin

**`agent-retrieval-bench`** is an open benchmark comparing two retrieval architectures for production AI agents in a tau-bench-style retail customer-service domain:

- **Variant A — MCP per source.** Six MCP tools, one per operational data source (customers, orders, inventory, returns, support, payments). The LLM composes joins at inference time.
- **Variant B — Context engine.** A single MCP retrieval tool (`get_view`) backed by three continuously joined materialised views maintained on a streaming engine ([DeltaStream](https://www.deltastream.io/)).

The benchmark is intended to back a blog post, plus talks at AI Engineer, Confluent Current, and QCon. **The author also uses it for marketing/sales materials**, which drove the decision to ship Variant B as DeltaStream-only (no DuckDB or local fallback in v1; just a stub for the future).

### Headline metrics

- `success_rate` per (variant × condition × model) — bootstrapped 95% CI.
- `cost_per_correct` — total cost / number of correct tasks.
- **`cost_per_correct_degraded`** — restricted to the *degraded* condition. **This is the headline number.** Clean is the demo; degraded is production.
- Failure-taxonomy histogram per variant — the marquee chart.

### Phase status

| Phase | Scope | Status |
|---|---|---|
| 1 | World-state generator + 8 Avro Kafka topics + Docker Compose | ✅ |
| 2 | Variant A: six per-source MCP servers, freshness profiles, fault injection, scoped auth | ✅ |
| 3 | Variant B: single DeltaStream-backed MCP server, three materialised views | ✅ |
| 4 | Inspect AI eval harness skeleton (3 task categories, snapshot grading, model registry) | ✅ shape only — real model invocation is **Phase 4b**, not yet implemented |
| 5 | Analysis surface: bootstrapped CIs, failure-taxonomy aggregation, matplotlib charts, results notebook | ✅ |
| 6 | Reproducibility: `make bench-laptop`, CONTRIBUTING.md, extension-point docs | ✅ |

### Commit history

```
7656b86 Phase 6: reproducibility + open-source readiness
0b5860d Phase 5: analysis surface — bootstrapped metrics, failure taxonomy, charts
51a282f Phase 4: Inspect AI eval harness skeleton with three task categories
b8b47d8 Phase 3 revision: Variant B is DeltaStream-only
1f9fa88 Phase 3: Variant B — consolidated context engine + LocalContextEngine
c1538c5 Phase 2: Variant A — six per-source MCP servers + auth + faults + snapshot
d87c05a Phase 1: world-state generator + Kafka topic layer
```

There was a brief discussion of shipping a `LocalContextEngine` (in-process Python join maintainer) and then a DuckDB alternative for Variant B. Both were rejected: LocalContextEngine for credibility risk ("we benchmark DeltaStream and also wrote our own DeltaStream"); DuckDB deferred to a future addition. The DuckDB stub raises `NotImplementedError` on construction.

### Test counts

89 tests pass. `ruff check src tests` clean. `make bench-laptop` runs end-to-end in dry-run mode (no creds needed) and produces `out/ground_truth_snapshot.json`, `out/runs.jsonl` (empty in dry-run), `out/summary.json`.

---

## 2. Repo tree

```
.
├── .env.example
├── .gitignore
├── CONTRIBUTING.md
├── HANDOFF.md                  # this file
├── LICENSE                     # Apache-2.0
├── Makefile
├── README.md
├── config/                     # YAML configs, no secrets
│   ├── eval.yaml
│   ├── scale.full.yaml
│   ├── scale.laptop.yaml
│   ├── variant_a.yaml
│   └── variant_b.yaml
├── docker-compose.yml          # local Kafka (KRaft) + Schema Registry
├── docs/                       # methodology, architecture, extension docs
│   ├── architecture.md
│   ├── extending.md
│   ├── methodology.md
│   └── models.md
├── notebooks/
│   └── results.ipynb           # produces every chart for blog/talk
├── pyproject.toml              # uv/hatch; deps + dev/observability/tau-bench extras
├── schemas/                    # 8 Avro schemas (one per Kafka topic)
│   ├── customer_tier_changes.avsc
│   ├── customers.avsc
│   ├── inventory_snapshots.avsc
│   ├── order_items.avsc
│   ├── orders.avsc
│   ├── payment_events.avsc
│   ├── returns.avsc
│   └── support_tickets.avsc
├── sql/views/                  # canonical Variant B materialised-view SQL
│   ├── customer_360.sql
│   ├── order_state.sql
│   └── returns_eligibility.sql
├── src/arb/
│   ├── __init__.py
│   ├── analysis/               # Phase 5: bootstrapped metrics, taxonomy, charts
│   │   ├── __init__.py
│   │   ├── charts.py
│   │   ├── classifier.py       # LLM-as-judge stub
│   │   ├── metrics.py
│   │   └── taxonomy.py
│   ├── cli.py                  # arb generate / arb snapshot / arb eval
│   ├── context/                # Variant B: ContextEngine protocol + DeltaStream client + view contract
│   │   ├── __init__.py
│   │   ├── deltastream.py
│   │   ├── duckdb_engine.py    # STUB — raises NotImplementedError
│   │   ├── engine.py
│   │   ├── schemas.py          # Pydantic output schemas
│   │   └── views.py            # ViewSpec registry
│   ├── eval/                   # Phase 4: Inspect AI harness
│   │   ├── __init__.py
│   │   ├── agents.py           # variant_a_tools (11 tools) + variant_b_tools (1 tool)
│   │   ├── conditions.py       # clean / degraded / adversarial
│   │   ├── grading.py          # FailureCategory + GradeResult
│   │   ├── models.py           # claude-opus-4-7, gpt-5
│   │   ├── observability.py    # Langfuse + RAGAS hooks (env-gated)
│   │   ├── runner.py           # matrix builder, run rows, summarise
│   │   └── tasks.py            # 3 task categories
│   ├── kafka/
│   │   ├── __init__.py
│   │   └── producer.py         # KafkaAvroSink (confluent-kafka + Schema Registry)
│   ├── mcp/                    # MCP servers + auth + fault injection
│   │   ├── __init__.py
│   │   ├── auth.py             # bearer token + scope check
│   │   ├── faults.py           # latency + error injection
│   │   ├── server_base.py      # SourceServer scaffolding
│   │   ├── servers/
│   │   │   ├── __init__.py
│   │   │   ├── builder.py      # six SourceServers from variant_a.yaml
│   │   │   ├── context_entrypoint.py   # Variant B FastMCP server
│   │   │   └── entrypoints.py  # Variant A: six FastMCP servers
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── context.py      # Variant B get_view
│   │       ├── customers.py
│   │       ├── inventory.py
│   │       ├── orders.py
│   │       ├── payments.py
│   │       ├── returns.py
│   │       └── support.py
│   ├── serving/                # per-source serving stores with replication lag + cache TTL
│   │   ├── __init__.py
│   │   ├── projectors.py       # one projector per topic
│   │   └── store.py            # ServingStore + FreshnessProfile
│   ├── snapshot.py             # WorldState -> deterministic JSON
│   └── world/                  # world-state generator + 8 Kafka topic emitters
│       ├── __init__.py
│       ├── generator.py        # tick-driven, seeded RNG
│       ├── rng.py              # named child streams from a single root SeedSequence
│       ├── scenarios.py        # ChargebackDowngradeRefund (replayable)
│       └── state.py            # WorldState dataclasses + invariant checks
├── tests/                      # 89 tests; tests/_fakes.py for in-test mocks
│   ├── __init__.py
│   ├── _fakes.py               # FakeContextEngine (NOT shipped)
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── .gitkeep
│   │   └── example_runs.jsonl  # 18 synthetic RunRows (used by notebook + tests)
│   ├── test_analysis.py
│   ├── test_avro_compat.py
│   ├── test_determinism.py
│   ├── test_eval_agents.py
│   ├── test_eval_conditions.py
│   ├── test_eval_models.py
│   ├── test_eval_runner.py
│   ├── test_eval_tasks_and_grading.py
│   ├── test_mcp_auth.py
│   ├── test_mcp_faults.py
│   ├── test_mcp_tools.py
│   ├── test_mcp_wiring.py
│   ├── test_referential_integrity.py
│   ├── test_scenarios.py
│   ├── test_serving_store.py
│   ├── test_snapshot.py
│   ├── test_variant_b_mcp.py
│   └── test_view_specs.py
└── uv.lock
```

---

## 3. Entry points

### CLI

The `arb` command is a Click group installed by `pyproject.toml` (`[project.scripts] arb = "arb.cli:main"`).

| Command | What it does |
|---|---|
| `arb generate --config <yaml> --seed <int> [--dry-run] [--out <jsonl>]` | Runs the world-state generator. With `--dry-run` (or with `kafka.enabled: false` in config) it emits to an in-memory sink and optionally dumps JSONL. With Kafka enabled it produces Avro to the brokers in the config. |
| `arb snapshot --config <yaml> --seed <int> [--at-tick <n>] --out <path>` | Runs the generator and writes a deterministic ground-truth snapshot JSON used for grading. See `docs/methodology.md`. |
| `arb eval --config config/eval.yaml --world-config <yaml> --seed <int> --out <jsonl> [--summary <json>] [--execute]` | Builds the eval matrix (tasks × variants × models × conditions × seeds). Default is `--dry-run` (shape only). `--execute` is reserved for Phase 4b and currently raises. |

### Python module entrypoints (MCP servers)

| Command | What it does |
|---|---|
| `python -m arb.mcp.servers.entrypoints {customers\|orders\|inventory\|returns\|support\|payments} [config_path]` | Variant A: starts one of six FastMCP servers over stdio. Bearer token via `ARB_MCP_TOKEN` env var. |
| `python -m arb.mcp.servers.context_entrypoint [config_path]` | Variant B: starts the single context-engine FastMCP server. Requires DeltaStream creds (`ARB_DELTASTREAM_*`) in env or it exits. |

### Make targets

```
make install            # uv sync --extra dev
make lint               # ruff check + ruff format --check
make typecheck          # mypy
make test               # uv run pytest (89 tests, no creds)
make up / down          # docker compose up/down (Kafka + Schema Registry)
make generate-laptop    # arb generate --config config/scale.laptop.yaml --seed 42
make generate-full      # arb generate --config config/scale.full.yaml --seed 42
make snapshot-laptop    # writes out/ground_truth_snapshot.json
make mcp-source-NAME    # runs the Variant A MCP server for source NAME
make mcp-context        # runs the Variant B MCP server (requires creds)
make bench-laptop       # snapshot + dry-run eval; prints "open notebooks/results.ipynb"
make bench-headline     # not yet — exits with explanation; Phase 4b
```

### Notebook

`notebooks/results.ipynb` — Jupyter notebook that loads `RUNS_PATH` (defaults to `tests/fixtures/example_runs.jsonl`), prints a summary table, and renders three matplotlib charts (`chart_failure_taxonomy`, `chart_success_rate_by_condition`, `chart_cost_per_correct`).

### Required env vars

```
# .env.example (literal):
ARB_DELTASTREAM_URL=
ARB_DELTASTREAM_TOKEN=
ARB_DELTASTREAM_DATABASE=
ARB_MCP_TOKEN=
```

Plus, if you wire real-model execution (Phase 4b):
- `ANTHROPIC_API_KEY` (for `claude-opus-4-7`)
- `OPENAI_API_KEY` (for `gpt-5`)
- Optionally: `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` (Langfuse traces); `ARB_RAGAS_ENABLED=1` (RAGAS scoring); `ARB_LLM_JUDGE=1` (LLM-as-judge classifier).

---

## 4. Architecture

### One picture

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

### End-to-end flow

1. **Snapshot capture (`arb.eval.runner.capture_snapshot`).** At task-start time, the world generator runs deterministically (`seed=42` by default) and `arb.snapshot.snapshot_dict` serialises the in-memory `WorldState` to a sorted JSON dict written to `out/ground_truth_snapshot.json`. The grader compares agent output against this snapshot — never against live Kafka.
2. **Condition setup (`arb.eval.conditions.apply_condition`).** Mutates a `VariantABundle`'s six `SourceServer` fault profiles in place. Clean → all zeros. Degraded → picks one source for `latency_ms=200`, a different source for `error_rate=0.05`, deterministic by seed. Adversarial → degraded + `schema_drift=True` flag.
3. **Agent build (`arb.eval.agents.variant_a_agent` / `variant_b_agent`).** Each returns an `AgentBuild(system_prompt, tools)`. Same prompt for both variants — methodology guarantee, tested. Variant A returns 11 Inspect AI Tools across 6 SourceServers. Variant B returns 1 tool (`get_view`).
4. **Task execution (`arb.eval.runner.run_task_against_model`).** Currently raises `NotImplementedError` with message "real-model invocation lives behind --execute. Phase 4 ships the harness shape; pass inspect_solver= in tests." The shape it will produce: `(agent_answer: dict, latency_ms: int, tool_calls: int, cost_usd: float, status: int)`.
5. **Grading (`task.grader(agent_answer, snapshot)`).** Each task carries a deterministic grader function (pure: takes agent JSON answer + the frozen snapshot, returns `GradeResult(correct, score, failure: FailureCategory, details)`).
6. **Row emission (`arb.eval.runner.make_row` + `emit_results`).** One JSONL row per (task × variant × model × condition × seed) cell.
7. **Analysis (`arb.analysis`).** `load_runs` reads JSONL; `bootstrap_ci` (n=2000) wraps every metric; `failure_histogram_by_variant` produces the marquee chart input; `chart_*` functions render matplotlib figures.

### Pluggability

- **Model:** config-driven via `config/eval.yaml`. `arb.eval.models.MODELS` lists headline models (`claude-opus-4-7`, `gpt-5`); fully-qualified Inspect AI strings (`google/gemini-2.5-pro`) pass through `resolve()`. See `docs/models.md`.
- **Variant B engine:** Hardcoded to `DeltaStreamContextEngine` in `arb.mcp.servers.context_entrypoint.build_engine()`. A `DuckDBContextEngine` stub exists in `arb/context/duckdb_engine.py` (raises `NotImplementedError`) — wiring it back in is documented in that file's docstring.
- **Tasks:** Defined programmatically in `arb.eval.tasks`. To add one: write a `build_<name>_task(snapshot)` builder + grader, append to `TaskCategory`, add to `build_all()`.
- **Conditions:** Add a `Condition` enum value + a branch in `apply_condition()`.
- **Views (Variant B):** Append a `ViewSpec` to `arb.context.views.VIEWS`, a Pydantic schema to `arb.context.schemas`, and SQL under `sql/views/<name>.sql`. The MCP `get_view(name, params)` interface does not change.

### What's hardcoded

- The eight Kafka topic names and their schemas.
- The `tenant_id` field exists on every event but is hardcoded to one value (single-tenant in v1).
- The chargeback scenario is the only replayable scenario shipped (`SCENARIOS["chargeback_downgrade_refund"]`).
- `SYSTEM_PROMPT` in `arb/eval/agents.py` is shared across variants and is not config-driven (intentional — methodology guarantee).
- The three view names (`customer_360`, `order_state`, `returns_eligibility`) and their primary keys.

---

## 5. Data layer

### Source: synthetic, generated at runtime

The world generator (`src/arb/world/generator.py`) is the only data source. There are no real datasets and no fixtures of generated events checked in. All event data is produced from a single `WorldState` (`src/arb/world/state.py`) given a config and a seed; given the same seed, output is byte-identical (verified by `tests/test_determinism.py`).

### Cardinalities

**Laptop mode (`config/scale.laptop.yaml`):**

| Entity | Count |
|---|---|
| customers | 1,000 |
| warehouses | 3 |
| skus | 200 |
| baseline_orders | 500 |
| orders/sec | 1.0 |
| inventory snapshot interval | 5 sec |
| return probability | 0.025 |
| payment-event probability | 0.015 |
| support tickets/sec | 0.2 |
| simulation duration | 30 sec |
| tick duration | 1 sec |
| start_epoch_ms | 1735689600000 (2025-01-01T00:00:00Z) |
| scenario | `chargeback_downgrade_refund` fires at tick 10 |

**Full mode (`config/scale.full.yaml`):**

| Entity | Count |
|---|---|
| customers | 100,000 |
| warehouses | 20 |
| skus | 20,000 |
| baseline_orders | 50,000 |
| orders/sec | 100.0 |
| support tickets/sec | 5.0 |
| simulation duration | 600 sec |
| scenario | `chargeback_downgrade_refund` fires at tick 60 |
| Kafka enabled | `true` |

### Eight Kafka topics (Avro)

All under the `retail.` namespace. All carry a `tenant_id` field. Schemas are checked into `schemas/`.

#### `retail.customers` — SCD-style customer profile (latest record per `customer_id`)

```json
{
  "type": "record", "name": "Customer", "namespace": "retail",
  "fields": [
    {"name": "tenant_id", "type": "string"},
    {"name": "customer_id", "type": "string"},
    {"name": "email", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "tier", "type": {"type": "enum", "name": "CustomerTier",
        "symbols": ["BRONZE", "SILVER", "GOLD", "PLATINUM"]}},
    {"name": "created_at_ms", "type": "long"},
    {"name": "updated_at_ms", "type": "long"},
    {"name": "version", "type": "long"}
  ]
}
```

Note: time field is `updated_at_ms` (not `occurred_at_ms`).

#### `retail.customer_tier_changes` — append-only tier upgrade/downgrade log

```json
{
  "type": "record", "name": "CustomerTierChange", "namespace": "retail",
  "fields": [
    {"name": "tenant_id", "type": "string"},
    {"name": "event_id", "type": "string"},
    {"name": "customer_id", "type": "string"},
    {"name": "from_tier", "type": {"type": "enum", "name": "CustomerTier",
        "symbols": ["BRONZE", "SILVER", "GOLD", "PLATINUM"]}},
    {"name": "to_tier", "type": "retail.CustomerTier"},
    {"name": "reason", "type": "string"},
    {"name": "occurred_at_ms", "type": "long"}
  ]
}
```

#### `retail.orders` — order lifecycle events (latest event per `order_id` wins)

```json
{
  "type": "record", "name": "OrderEvent", "namespace": "retail",
  "fields": [
    {"name": "tenant_id", "type": "string"},
    {"name": "event_id", "type": "string"},
    {"name": "order_id", "type": "string"},
    {"name": "customer_id", "type": "string"},
    {"name": "status", "type": {"type": "enum", "name": "OrderStatus",
        "symbols": ["CREATED", "PAID", "SHIPPED", "DELIVERED", "CANCELLED"]}},
    {"name": "total_cents", "type": "long"},
    {"name": "currency", "type": "string"},
    {"name": "occurred_at_ms", "type": "long"}
  ]
}
```

#### `retail.order_items` — line items (append per `order_id`)

```json
{
  "type": "record", "name": "OrderItem", "namespace": "retail",
  "fields": [
    {"name": "tenant_id", "type": "string"},
    {"name": "order_item_id", "type": "string"},
    {"name": "order_id", "type": "string"},
    {"name": "sku", "type": "string"},
    {"name": "quantity", "type": "int"},
    {"name": "unit_price_cents", "type": "long"},
    {"name": "warehouse_id", "type": "string"},
    {"name": "occurred_at_ms", "type": "long"}
  ]
}
```

#### `retail.inventory_snapshots` — per-SKU per-warehouse stock snapshots

```json
{
  "type": "record", "name": "InventorySnapshot", "namespace": "retail",
  "fields": [
    {"name": "tenant_id", "type": "string"},
    {"name": "snapshot_id", "type": "string"},
    {"name": "sku", "type": "string"},
    {"name": "warehouse_id", "type": "string"},
    {"name": "quantity_on_hand", "type": "int"},
    {"name": "occurred_at_ms", "type": "long"}
  ]
}
```

#### `retail.returns` — return request lifecycle (latest event per `return_id`)

```json
{
  "type": "record", "name": "ReturnEvent", "namespace": "retail",
  "fields": [
    {"name": "tenant_id", "type": "string"},
    {"name": "event_id", "type": "string"},
    {"name": "return_id", "type": "string"},
    {"name": "order_id", "type": "string"},
    {"name": "status", "type": {"type": "enum", "name": "ReturnStatus",
        "symbols": ["REQUESTED", "APPROVED", "RECEIVED", "REFUNDED", "REJECTED"]}},
    {"name": "reason", "type": "string"},
    {"name": "amount_cents", "type": "long"},
    {"name": "occurred_at_ms", "type": "long"}
  ]
}
```

#### `retail.support_tickets` — customer-service tickets

```json
{
  "type": "record", "name": "SupportTicket", "namespace": "retail",
  "fields": [
    {"name": "tenant_id", "type": "string"},
    {"name": "event_id", "type": "string"},
    {"name": "ticket_id", "type": "string"},
    {"name": "customer_id", "type": "string"},
    {"name": "order_id", "type": ["null", "string"], "default": null},
    {"name": "status", "type": {"type": "enum", "name": "TicketStatus",
        "symbols": ["OPEN", "PENDING", "RESOLVED", "CLOSED"]}},
    {"name": "subject", "type": "string"},
    {"name": "occurred_at_ms", "type": "long"}
  ]
}
```

#### `retail.payment_events` — append-only payment lifecycle

```json
{
  "type": "record", "name": "PaymentEvent", "namespace": "retail",
  "fields": [
    {"name": "tenant_id", "type": "string"},
    {"name": "event_id", "type": "string"},
    {"name": "order_id", "type": "string"},
    {"name": "kind", "type": {"type": "enum", "name": "PaymentEventKind",
        "symbols": ["AUTHORIZED", "CAPTURED", "REFUND", "CHARGEBACK", "FAILED"]}},
    {"name": "amount_cents", "type": "long"},
    {"name": "currency", "type": "string"},
    {"name": "occurred_at_ms", "type": "long"}
  ]
}
```

### `WorldState` dataclasses (the in-memory source of truth)

From `src/arb/world/state.py`:

```python
TIERS = ("BRONZE", "SILVER", "GOLD", "PLATINUM")

class OrderStatus(StrEnum):
    CREATED = "CREATED"; PAID = "PAID"; SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"; CANCELLED = "CANCELLED"

class ReturnStatus(StrEnum):
    REQUESTED = "REQUESTED"; APPROVED = "APPROVED"; RECEIVED = "RECEIVED"
    REFUNDED = "REFUNDED"; REJECTED = "REJECTED"

class PaymentEventKind(StrEnum):
    AUTHORIZED = "AUTHORIZED"; CAPTURED = "CAPTURED"; REFUND = "REFUND"
    CHARGEBACK = "CHARGEBACK"; FAILED = "FAILED"

class TicketStatus(StrEnum):
    OPEN = "OPEN"; PENDING = "PENDING"; RESOLVED = "RESOLVED"; CLOSED = "CLOSED"

@dataclass
class Customer:
    customer_id: str; email: str; name: str; tier: str
    created_at_ms: int; updated_at_ms: int; version: int = 1

@dataclass
class OrderItem:
    order_item_id: str; order_id: str; sku: str
    quantity: int; unit_price_cents: int; warehouse_id: str

@dataclass
class Order:
    order_id: str; customer_id: str; status: OrderStatus
    total_cents: int; currency: str; created_at_ms: int
    items: list[OrderItem] = field(default_factory=list)

@dataclass
class InventoryRow:
    sku: str; warehouse_id: str; quantity_on_hand: int

@dataclass
class Return:
    return_id: str; order_id: str; status: ReturnStatus
    reason: str; amount_cents: int

@dataclass
class SupportTicket:
    ticket_id: str; customer_id: str; order_id: str | None
    status: TicketStatus; subject: str

@dataclass
class WorldState:
    tenant_id: str
    customers: dict[str, Customer] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    inventory: dict[tuple[str, str], InventoryRow] = field(default_factory=dict)
    returns: dict[str, Return] = field(default_factory=dict)
    tickets: dict[str, SupportTicket] = field(default_factory=dict)
    skus: list[str] = field(default_factory=list)
    warehouses: list[str] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
```

`WorldState.check_invariants()` enforces referential integrity (every order's customer_id, every order_item's sku/warehouse, every return's order_id, every ticket's customer_id/order_id; non-negative inventory). Tests run this on every laptop-mode generator output.

### The ground-truth snapshot

`arb.snapshot.snapshot_dict(state)` serialises the WorldState to a sorted dict with these top-level keys:
- `tenant_id` (string)
- `warehouses` (sorted list of strings, e.g. `["wh-0000", "wh-0001", "wh-0002"]`)
- `skus` (sorted list of strings, e.g. `["sku-000000", ..., "sku-000199"]`)
- `customers` (list of dicts sorted by `customer_id`)
- `orders` (list of dicts sorted by `order_id`, each with embedded `items` list)
- `inventory` (list of `{sku, warehouse_id, quantity_on_hand}`)
- `returns` (list of `{return_id, order_id, status, reason, amount_cents}`)
- `tickets` (list of `{ticket_id, customer_id, order_id, status, subject}`)

Snapshots are deterministic given a seed — `tests/test_snapshot.py::test_snapshot_is_deterministic_for_seed` asserts this.

---

## 6. Prompts & test cases

### System prompt (identical across both variants)

From `src/arb/eval/agents.py`:

```python
SYSTEM_PROMPT = (
    "You are a customer-service agent for a retail business. You have read-only "
    "access to operational data through the tools provided. Use the tools to "
    "answer questions, identify issues, and recommend actions. When you need "
    "data, prefer a single tool call over many. Be precise: cite the order id, "
    "customer id, or return id you reasoned about. If you cannot answer with "
    "the data available, say so explicitly."
)
```

### Three task categories (literal question text)

#### Lookup task — `lookup-customer-tier:<customer_id>`

Generated by `arb.eval.tasks.build_lookup_task(snapshot)`. Question template:

> What loyalty tier is customer `{customer_id}` currently on? Answer JSON: `{customer_id, tier}`.

Picker: `_pick_customer(snapshot)` returns the first customer in the snapshot.
Expected answer keys: `("customer_id", "tier")`.

#### Transactional task — `transactional-order-status:<order_id>`

Generated by `arb.eval.tasks.build_transactional_task(snapshot)`. Question template:

> Report the current status and total_cents of order `{order_id}`. Answer JSON: `{order_id, status, total_cents}`.

Picker: middle of the snapshot's `orders` list (`orders[len(orders) // 2]`).
Expected answer keys: `("order_id", "status", "total_cents")`.

#### Multi-hop task — `multi-hop-returns-eligibility:<return_id>` (the marquee)

Generated by `arb.eval.tasks.build_multi_hop_task(snapshot)`. Question template:

> For return `{return_id}`, determine whether it is eligible for a refund. A return is INELIGIBLE if a chargeback has been filed on the originating order. Answer JSON: `{return_id, eligible_for_refund, reason}`.

Picker: `_pick_chargeback_return(snapshot)` finds a return with `reason == "chargeback_already_filed"` (produced by the `chargeback_downgrade_refund` scenario).
Expected answer keys: `("return_id", "eligible_for_refund", "reason")`.

This is the headline task. Variant A must compose the answer from 4+ tool calls (find return → look up order → fetch payment events → check for `CHARGEBACK`). Variant B answers it with a single `get_view("returns_eligibility", {return_id})` call.

### LLM-as-judge prompt

There is no LLM-as-judge prompt yet. `arb.analysis.classifier.classify_row` is a stub that trusts the deterministic grader's `failure` field. When `ARB_LLM_JUDGE=1` and Phase 4b lands, a structured-output Anthropic call replaces it; the prompt has not been written.

### Replayable scenario

The world generator includes one named scenario, `chargeback_downgrade_refund`, in `src/arb/world/scenarios.py`. When triggered (configured `fire_at_tick`), it picks the first PAID/SHIPPED/DELIVERED order whose customer is at SILVER+ tier, then:
1. Emits a `CHARGEBACK` payment event on that order.
2. Downgrades the customer's tier by one step (reason: `chargeback_auto_downgrade`).
3. Mutates `state.returns` to add a `REJECTED` return with `reason="chargeback_already_filed"` for that order, and emits the matching event.

This is what makes the multi-hop task answerable from the snapshot.

---

## 7. Models & providers

From `src/arb/eval/models.py`:

```python
@dataclass(frozen=True)
class ModelSpec:
    name: str       # Inspect AI provider/id, e.g. "anthropic/claude-opus-4-7"
    short: str      # display name in result tables
    family: str     # "anthropic" | "openai" | "google" | "<other>"

MODELS: dict[str, ModelSpec] = {
    "claude-opus-4-7": ModelSpec(
        name="anthropic/claude-opus-4-7",
        short="claude-opus-4-7",
        family="anthropic",
    ),
    "gpt-5": ModelSpec(
        name="openai/gpt-5",
        short="gpt-5",
        family="openai",
    ),
}

def resolve(name: str) -> ModelSpec:
    if name in MODELS:
        return MODELS[name]
    if "/" in name:
        family = name.split("/", 1)[0]
        return ModelSpec(name=name, short=name.rsplit("/", 1)[-1], family=family)
    raise KeyError(...)
```

**Provider selection is config-driven** via `config/eval.yaml`:

```yaml
variants: ["A", "B"]
models:
  - claude-opus-4-7
  - gpt-5
conditions: ["clean", "degraded", "adversarial"]
seeds: [1, 2, 3]
```

API keys come from environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) — Inspect AI reads them directly; the harness never threads keys through code.

To add a model: append to `MODELS` *and* list the short name in `config/eval.yaml`, OR list a fully-qualified Inspect AI string like `"google/gemini-2.5-pro"` directly. See `docs/models.md`.

**Inspect AI is not yet wired to actually invoke models.** `run_task_against_model` raises `NotImplementedError`; that's the Phase 4b work. The shape it returns is tuple `(agent_answer, latency_ms, tool_calls, cost_usd, status)`.

---

## 8. Metrics captured

### `RunRow` schema (one per (task × variant × model × condition × seed) cell)

From `src/arb/eval/runner.py`:

```python
@dataclass
class RunRow:
    task_id: str
    category: str               # "lookup" | "transactional" | "multi_hop"
    variant: str                # "A" | "B"
    model: str                  # short name
    condition: str              # "clean" | "degraded" | "adversarial"
    seed: int
    correct: bool
    score: float                # 0.0 or 1.0 (partial credit allowed)
    failure: str                # FailureCategory value or "none"
    latency_ms: int             # total task latency
    tool_calls: int             # count of tool invocations
    cost_usd: float
    details: dict[str, Any] = field(default_factory=dict)  # per-grader extras
```

Token counts (input/output/cached) and time-to-first-token are **not** currently captured as separate fields. They land in Phase 4b when Inspect AI traces are processed; cost is the rolled-up dollar number for now.

### Output sink

JSONL file. Default `out/runs.jsonl`. Plus an optional summary JSON via `--summary`.

### Sample row (literal, from `tests/fixtures/example_runs.jsonl`)

```json
{"task_id":"multi-hop-returns-eligibility:ret-scn-1","category":"multi_hop","variant":"A","model":"claude-opus-4-7","condition":"degraded","seed":1,"correct":false,"score":0.0,"failure":"missed_join","latency_ms":11000,"tool_calls":9,"cost_usd":0.071,"details":{}}
{"task_id":"multi-hop-returns-eligibility:ret-scn-1","category":"multi_hop","variant":"B","model":"claude-opus-4-7","condition":"degraded","seed":1,"correct":true,"score":1.0,"failure":"none","latency_ms":1900,"tool_calls":1,"cost_usd":0.011,"details":{}}
```

The full 18-row fixture lives at `tests/fixtures/example_runs.jsonl` and is shaped to look like the expected headline finding (Variant A struggles on multi-hop and degraded; Variant B nearly clean).

### Aggregations (from `arb.analysis.metrics`)

- `success_rate(rows)` → bootstrapped `BootstrapCI(point, lo, hi)` with n=2000 resamples.
- `cost_per_correct(rows)` → bootstrap of total cost / # correct.
- `cost_per_correct_degraded(rows)` → same, restricted to `condition == "degraded"`. **Headline metric.**
- `latency_percentile(rows, p=0.95)` → bootstrap of pth percentile latency.
- `failure_histogram_by_variant(rows)` → `{variant: {category: count}}`.

### Run-level summary (from `arb.eval.runner.summarise`)

```python
{
    "n": int,
    "success_rate": float,
    "cost_per_correct": float,
    "cost_per_correct_degraded": float,
    "failures": {category: count, ...},
    "by_variant": {
        variant: {"n": int, "success_rate": float},
        ...
    },
}
```

### Optional observability hooks

- **Langfuse** — `arb.eval.observability.maybe_langfuse_client()`. Returns `None` unless both `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set. Trace wiring lands in Phase 4b.
- **RAGAS** — `arb.eval.observability.maybe_ragas_score(question, answer, contexts)`. Stub returns `{faithfulness: 0.0, context_precision: 0.0, context_recall: 0.0}` when `ARB_RAGAS_ENABLED=1`. Real wiring needs Phase 4b transcripts.

---

## 9. Grading / correctness evaluation

### Method: deterministic structured-answer comparison against the ground-truth snapshot

Each task has a Python grader function: `Grader = Callable[[dict[str, Any], dict[str, Any]], GradeResult]`. The two arguments are the agent's parsed JSON answer and the frozen snapshot.

`GradeResult` from `src/arb/eval/grading.py`:

```python
@dataclass
class GradeResult:
    correct: bool
    score: float                       # 0.0 or 1.0 today; partial credit allowed
    failure: FailureCategory
    details: dict[str, Any]
```

### Failure taxonomy (the canonical categories)

```python
class FailureCategory(StrEnum):
    NONE = "none"
    TEMPORAL_MISALIGNMENT = "temporal_misalignment"
    TOOL_SELECTION_ERROR = "tool_selection_error"
    MISSED_JOIN = "missed_join"
    SCHEMA_MISMATCH = "schema_mismatch"
    SOURCE_TIMEOUT = "source_timeout"
    REASONING_ERROR = "reasoning_error"
    AMBIGUOUS_RESULT = "ambiguous_result"
    AUTH_DENIED = "auth_denied"
```

`AUTH_DENIED` is a sentinel — it should never legitimately fire in a correctly-configured experiment, so its presence indicates misconfiguration.

### Three grader functions (literal source)

```python
def _grade_lookup_customer(answer, snapshot) -> GradeResult:
    cid = answer.get("customer_id")
    if not cid:
        return GradeResult(False, 0.0, FailureCategory.REASONING_ERROR,
                           {"reason": "missing customer_id"})
    c = find_customer(snapshot, cid)
    if c is None:
        return GradeResult(False, 0.0, FailureCategory.REASONING_ERROR,
                           {"reason": "unknown customer"})
    actual_tier = c["tier"]
    if answer.get("tier") != actual_tier:
        return GradeResult(False, 0.0, FailureCategory.TEMPORAL_MISALIGNMENT,
                           {"expected": actual_tier, "got": answer.get("tier")})
    return GradeResult(True, 1.0, FailureCategory.NONE, {"tier": actual_tier})


def _grade_transactional_order_status(answer, snapshot) -> GradeResult:
    oid = answer.get("order_id")
    if not oid:
        return GradeResult(False, 0.0, FailureCategory.REASONING_ERROR,
                           {"reason": "missing order_id"})
    o = find_order(snapshot, oid)
    if o is None:
        return GradeResult(False, 0.0, FailureCategory.REASONING_ERROR,
                           {"reason": "unknown order"})
    status_correct = answer.get("status") == o["status"]
    total_correct = answer.get("total_cents") == o["total_cents"]
    if status_correct and total_correct:
        return GradeResult(True, 1.0, FailureCategory.NONE, {})
    return GradeResult(False, 0.0, FailureCategory.MISSED_JOIN, {
        "status_expected": o["status"], "status_got": answer.get("status"),
        "total_expected": o["total_cents"], "total_got": answer.get("total_cents"),
    })


def _grade_returns_eligibility(answer, snapshot) -> GradeResult:
    rid = answer.get("return_id")
    if not rid:
        return GradeResult(False, 0.0, FailureCategory.REASONING_ERROR,
                           {"reason": "missing return_id"})
    r = find_return(snapshot, rid)
    if r is None:
        return GradeResult(False, 0.0, FailureCategory.REASONING_ERROR,
                           {"reason": "unknown return"})
    expected_eligible = r.get("reason") != "chargeback_already_filed"
    if answer.get("eligible_for_refund") is not expected_eligible:
        return GradeResult(False, 0.0, FailureCategory.MISSED_JOIN, {
            "expected_eligible": expected_eligible,
            "got": answer.get("eligible_for_refund"),
        })
    return GradeResult(True, 1.0, FailureCategory.NONE, {"return_id": rid})
```

### Reference answer examples (synthesised from a real laptop-mode snapshot)

For the lookup task, a correct answer looks like:
```json
{"customer_id": "cust-00000000", "tier": "GOLD"}
```

For the transactional task:
```json
{"order_id": "ord-0000000010", "status": "PAID", "total_cents": 4250}
```

For the multi-hop task (the chargeback case is always INELIGIBLE):
```json
{"return_id": "ret-scn-1", "eligible_for_refund": false, "reason": "chargeback filed on order ord-XXXXXXXXXX"}
```

The grader does not check the `reason` text — only `return_id` and the `eligible_for_refund` boolean.

### LLM-as-judge

Stub only. `arb.analysis.classifier.classify_row(row)` returns the deterministic grader's `failure` field unless `ARB_LLM_JUDGE=1`, in which case the same passthrough runs (the structured-output call is documented as "lands when Phase 4b produces real transcripts"). The classifier prompt has not been written.

### Human spot-check workflow

Not implemented in v1. The original spec called for human spot-checking 10–20% of LLM-as-judge outputs to validate accuracy; this is a Phase 5b item.

---

## 10. Variance & repetition

Each (task × variant × model × condition) cell runs **3 seeds** by default. From `config/eval.yaml`:

```yaml
seeds: [1, 2, 3]
```

That gives 3 repetitions per cell. The matrix is therefore `3 tasks × 2 variants × 2 models × 3 conditions × 3 seeds = 108 cells`.

Variance is reported as **bootstrapped 95% CIs** (n=2000 resamples) on every metric in the analysis layer. From `src/arb/analysis/metrics.py`:

```python
def bootstrap_ci(values, *, statistic=mean, n_resamples=2000, confidence=0.95, seed=0):
    ...
```

The notebook's chart helpers (`chart_success_rate_by_condition`, `chart_cost_per_correct`) render error bars from these CIs. The failure-taxonomy chart shows raw counts (no CIs) because it's a categorical distribution.

The world generator itself is fully deterministic given a seed (`tests/test_determinism.py` hashes the entire event stream and asserts byte-equality across runs with the same seed).

---

## 11. The two paths being compared

### Variant A — MCP per source, agent composes joins

The agent receives a bearer token (`arb-variant-a-token`) carrying six per-source `*:read` scopes (from `config/variant_a.yaml`):

```yaml
auth:
  tokens:
    "arb-variant-a-token":
      - "customers:read"
      - "orders:read"
      - "inventory:read"
      - "returns:read"
      - "support:read"
      - "payments:read"
```

It is given **11 Inspect AI tools** wrapping the six per-source MCP servers. The full list (from `arb.eval.agents.variant_a_tools`):

| Tool | Backed by store | Scope | Signature |
|---|---|---|---|
| `get_customer` | `customers` | `customers:read` | `(customer_id: str) -> dict` |
| `get_customer_tier_history` | `customer_tier_changes` | `customers:read` | `(customer_id: str) -> list[dict]` |
| `get_order` | `orders` | `orders:read` | `(order_id: str) -> dict` |
| `list_orders_for_customer` | `orders` | `orders:read` | `(customer_id: str, limit: int = 50) -> list[dict]` |
| `get_order_items` | `order_items` | `orders:read` | `(order_id: str) -> list[dict]` |
| `get_stock` | `inventory` | `inventory:read` | `(sku: str, warehouse_id: str) -> dict` |
| `get_return` | `returns` | `returns:read` | `(return_id: str) -> dict` |
| `list_returns_for_order` | `returns` | `returns:read` | `(order_id: str) -> list[dict]` |
| `get_ticket` | `support_tickets` | `support:read` | `(ticket_id: str) -> dict` |
| `list_tickets_for_customer` | `support_tickets` | `support:read` | `(customer_id: str, limit: int = 50) -> list[dict]` |
| `list_payment_events_for_order` | `payment_events` | `payments:read` | `(order_id: str) -> list[dict]` |

Each tool ultimately calls a `ServingStore.get(key, now_ms)` or `.view(now_ms)` — the store applies `replication_lag_ms` and `cache_ttl_ms` (per-source from `config/variant_a.yaml`):

| Source | replication_lag_ms | cache_ttl_ms |
|---|---|---|
| customers | 1500 | 5000 |
| orders | 800 | 1000 |
| inventory | 200 | 0 |
| returns | 2000 | 5000 |
| support | 1000 | 3000 |
| payments | 5000 | 0 |

Under the *degraded* condition, `apply_condition` (in `src/arb/eval/conditions.py`) picks one source for `latency_ms=200` and a different one for `error_rate=0.05` (deterministic by seed). Under *adversarial*, schema drift is layered on top.

### Variant B — single context engine, joins precomputed

The agent receives a different bearer token (`arb-variant-b-token`) carrying only `context:read` (from `config/variant_b.yaml`):

```yaml
auth:
  tokens:
    "arb-variant-b-token":
      - "context:read"
```

It is given **one Inspect AI tool**, `get_view`, with signature:

```python
get_view(name: str, params: dict | None = None, limit: int | None = None) -> dict
```

Calling `get_view` dispatches via `arb.context.engine.ContextEngine.get_view(ViewQuery(name, params, limit))`. The shipped implementation is `DeltaStreamContextEngine` (`arb/context/deltastream.py`), which executes:

```sql
SELECT * FROM <view_name> WHERE <primary_key> = :pk LIMIT 1
```

against DeltaStream's REST API. The three views are defined by SQL files under `sql/views/` and contracted by Pydantic schemas in `arb/context/schemas.py`.

#### View registry (`arb.context.views.VIEWS`)

| View | Primary key | Source topics |
|---|---|---|
| `customer_360` | `customer_id` | `retail.customers`, `retail.customer_tier_changes`, `retail.orders`, `retail.support_tickets` |
| `order_state` | `order_id` | `retail.orders`, `retail.order_items`, `retail.inventory_snapshots`, `retail.payment_events`, `retail.returns` |
| `returns_eligibility` | `return_id` | `retail.returns`, `retail.orders`, `retail.payment_events` |

#### Output schemas (Pydantic models from `src/arb/context/schemas.py`)

```python
class TierChange(BaseModel):
    from_tier: str; to_tier: str; reason: str; occurred_at_ms: int

class OrderSummary(BaseModel):
    order_id: str; status: str; total_cents: int; currency: str; occurred_at_ms: int

class TicketSummary(BaseModel):
    ticket_id: str; order_id: str | None; status: str; subject: str; occurred_at_ms: int

class OrderItemRow(BaseModel):
    order_item_id: str; sku: str; quantity: int; unit_price_cents: int; warehouse_id: str

class InventoryForItem(BaseModel):
    sku: str; warehouse_id: str; quantity_on_hand: int; occurred_at_ms: int

class PaymentEventRow(BaseModel):
    kind: str; amount_cents: int; currency: str; occurred_at_ms: int


class Customer360(BaseModel):
    customer_id: str; email: str; name: str; tier: str; updated_at_ms: int
    tier_history: list[TierChange] = Field(default_factory=list)
    recent_orders: list[OrderSummary] = Field(default_factory=list)
    open_tickets: list[TicketSummary] = Field(default_factory=list)


class OrderState(BaseModel):
    order_id: str; customer_id: str; status: str; total_cents: int; currency: str
    occurred_at_ms: int
    items: list[OrderItemRow] = Field(default_factory=list)
    inventory_for_items: list[InventoryForItem] = Field(default_factory=list)
    payment_events: list[PaymentEventRow] = Field(default_factory=list)
    open_return_id: str | None = None


class ReturnsEligibility(BaseModel):
    return_id: str; order_id: str; return_status: str; return_amount_cents: int
    order: OrderSummary
    payment_events: list[PaymentEventRow] = Field(default_factory=list)
    has_chargeback: bool = False
    eligible_for_refund: bool = True
    ineligibility_reason: str | None = None
```

#### Materialised view SQL (literal, DeltaStream dialect)

These three files in `sql/views/` are the canonical Variant B spec. Treat them as the contract any BYO implementation must match.

**`sql/views/customer_360.sql`:**

```sql
CREATE MATERIALIZED VIEW customer_360 AS
WITH latest_customer AS (
  SELECT
    customer_id,
    LAST_VALUE(email)         AS email,
    LAST_VALUE(name)          AS name,
    LAST_VALUE(tier)          AS tier,
    LAST_VALUE(updated_at_ms) AS updated_at_ms
  FROM "retail.customers"
  GROUP BY customer_id
),
tier_history AS (
  SELECT customer_id,
    ARRAY_AGG(STRUCT(from_tier, to_tier, reason, occurred_at_ms)
              ORDER BY occurred_at_ms ASC) AS tier_history
  FROM "retail.customer_tier_changes"
  GROUP BY customer_id
),
recent_orders AS (
  SELECT customer_id,
    ARRAY_AGG(STRUCT(order_id, status, total_cents, currency, occurred_at_ms)
              ORDER BY occurred_at_ms DESC LIMIT 20) AS recent_orders
  FROM "retail.orders"
  GROUP BY customer_id
),
open_tickets AS (
  SELECT customer_id,
    ARRAY_AGG(STRUCT(ticket_id, order_id, status, subject, occurred_at_ms)
              ORDER BY occurred_at_ms DESC) AS open_tickets
  FROM "retail.support_tickets"
  WHERE status IN ('OPEN', 'PENDING')
  GROUP BY customer_id
)
SELECT
  c.customer_id, c.email, c.name, c.tier, c.updated_at_ms,
  COALESCE(th.tier_history,   ARRAY[]) AS tier_history,
  COALESCE(ro.recent_orders,  ARRAY[]) AS recent_orders,
  COALESCE(ot.open_tickets,   ARRAY[]) AS open_tickets
FROM latest_customer c
LEFT JOIN tier_history  th USING (customer_id)
LEFT JOIN recent_orders ro USING (customer_id)
LEFT JOIN open_tickets  ot USING (customer_id);
```

**`sql/views/order_state.sql`:**

```sql
CREATE MATERIALIZED VIEW order_state AS
WITH latest_order AS (
  SELECT order_id,
    LAST_VALUE(customer_id)    AS customer_id,
    LAST_VALUE(status)         AS status,
    LAST_VALUE(total_cents)    AS total_cents,
    LAST_VALUE(currency)       AS currency,
    LAST_VALUE(occurred_at_ms) AS occurred_at_ms
  FROM "retail.orders"
  GROUP BY order_id
),
items AS (
  SELECT order_id,
    ARRAY_AGG(STRUCT(order_item_id, sku, quantity, unit_price_cents, warehouse_id)) AS items
  FROM "retail.order_items"
  GROUP BY order_id
),
inventory_for_items AS (
  SELECT oi.order_id,
    ARRAY_AGG(STRUCT(inv.sku, inv.warehouse_id, inv.quantity_on_hand, inv.occurred_at_ms)) AS inventory_for_items
  FROM "retail.order_items" oi
  JOIN (
    SELECT sku, warehouse_id,
      LAST_VALUE(quantity_on_hand) AS quantity_on_hand,
      LAST_VALUE(occurred_at_ms)   AS occurred_at_ms
    FROM "retail.inventory_snapshots"
    GROUP BY sku, warehouse_id
  ) inv ON inv.sku = oi.sku AND inv.warehouse_id = oi.warehouse_id
  GROUP BY oi.order_id
),
payments AS (
  SELECT order_id,
    ARRAY_AGG(STRUCT(kind, amount_cents, currency, occurred_at_ms)
              ORDER BY occurred_at_ms ASC) AS payment_events
  FROM "retail.payment_events"
  GROUP BY order_id
),
open_returns AS (
  SELECT order_id, LAST_VALUE(return_id) AS open_return_id
  FROM "retail.returns"
  WHERE status IN ('REQUESTED', 'APPROVED', 'RECEIVED')
  GROUP BY order_id
)
SELECT
  o.order_id, o.customer_id, o.status, o.total_cents, o.currency, o.occurred_at_ms,
  COALESCE(i.items,                 ARRAY[]) AS items,
  COALESCE(inv.inventory_for_items, ARRAY[]) AS inventory_for_items,
  COALESCE(p.payment_events,        ARRAY[]) AS payment_events,
  r.open_return_id
FROM latest_order o
LEFT JOIN items               i   USING (order_id)
LEFT JOIN inventory_for_items inv USING (order_id)
LEFT JOIN payments            p   USING (order_id)
LEFT JOIN open_returns        r   USING (order_id);
```

**`sql/views/returns_eligibility.sql`:**

```sql
CREATE MATERIALIZED VIEW returns_eligibility AS
WITH latest_return AS (
  SELECT return_id,
    LAST_VALUE(order_id)       AS order_id,
    LAST_VALUE(status)         AS return_status,
    LAST_VALUE(amount_cents)   AS return_amount_cents,
    LAST_VALUE(occurred_at_ms) AS occurred_at_ms
  FROM "retail.returns"
  GROUP BY return_id
),
order_summary AS (
  SELECT order_id,
    LAST_VALUE(STRUCT(order_id, status, total_cents, currency, occurred_at_ms)) AS order
  FROM "retail.orders"
  GROUP BY order_id
),
order_payments AS (
  SELECT order_id,
    ARRAY_AGG(STRUCT(kind, amount_cents, currency, occurred_at_ms)
              ORDER BY occurred_at_ms ASC) AS payment_events,
    BOOL_OR(kind = 'CHARGEBACK')   AS has_chargeback
  FROM "retail.payment_events"
  GROUP BY order_id
)
SELECT
  r.return_id, r.order_id, r.return_status, r.return_amount_cents,
  os.order,
  COALESCE(p.payment_events, ARRAY[])     AS payment_events,
  COALESCE(p.has_chargeback, FALSE)       AS has_chargeback,
  NOT COALESCE(p.has_chargeback, FALSE)   AS eligible_for_refund,
  CASE WHEN COALESCE(p.has_chargeback, FALSE) THEN 'chargeback_already_filed'
       ELSE NULL END AS ineligibility_reason
FROM latest_return r
LEFT JOIN order_summary  os USING (order_id)
LEFT JOIN order_payments p  USING (order_id);
```

### How the comparison stays fair

- **Identical system prompt** (`SYSTEM_PROMPT` constant, used by both `variant_a_agent` and `variant_b_agent`). Tested in `tests/test_eval_agents.py::test_variant_a_and_b_share_system_prompt`.
- **Identical model** for any given run (driven by `config/eval.yaml`).
- **Same task definitions** (same `TaskInstance.question`, same grader).
- **Same conditions** (clean / degraded / adversarial all apply to the upstream Kafka topics; Variant B's degraded behaviour comes from upstream sources being slow, not from the context engine being slow).
- **Variant A has 11 tools, Variant B has 1.** Asserted in `tests/test_eval_agents.py::test_variant_a_has_more_tools_than_b`.

### Variant B freshness SLA

`config/variant_b.yaml`:

```yaml
freshness_sla_ms:
  default:             250
  customer_360:        250
  order_state:         250
  returns_eligibility: 250
```

Per-view overrides supported. The default of 250 ms is the contract DeltaStream is expected to honour from event commit on the source Kafka topic to visibility in the materialised view.

---

## 12. Known gaps & TODOs

### Stubs / NotImplementedError

| Location | What's missing |
|---|---|
| `src/arb/context/duckdb_engine.py` | Entire DuckDB engine. `__init__` raises `NotImplementedError`. The docstring lists the 5 steps to wire it up later. |
| `src/arb/eval/runner.py:run_task_against_model` | Real Inspect AI model invocation. Today raises `NotImplementedError("real-model invocation lives behind --execute. Phase 4 ships the harness shape; pass inspect_solver= in tests.")`. This is **Phase 4b**. |
| `src/arb/cli.py:eval_cmd` (`--execute` branch) | Raises `ClickException("real-model execution is wired in Phase 4b; for now use --dry-run.")`. |
| `src/arb/analysis/classifier.py:classify_row` | LLM-as-judge stub. Trusts deterministic grader's category. Real structured-output Anthropic call is "Phase 4b plugs the structured-output call in here." |
| `src/arb/eval/observability.py:maybe_ragas_score` | Returns zeros. Comment: "Stub: real wiring lives in Phase 4b." |
| `src/arb/eval/observability.py:maybe_langfuse_client` | Returns a `Langfuse()` client but no traces are emitted yet — Phase 4b. |
| `Makefile:bench-headline` | Exits with explanation. Phase 4b. |
| `src/arb/eval/conditions.py` (adversarial condition) | Sets `schema_drift=True` flag but the world generator does not currently honour it — schema drift is not actually injected. |
| `src/arb/context/deltastream.py:_exec` | Marked `# pragma: no cover`. The REST shape (`POST /v1/query` with `{database, sql, params}` JSON body) is plausible but **not validated against a real DeltaStream cluster.** SQL dialect (`LAST_VALUE`, `STRUCT`, `BOOL_OR`, `ARRAY_AGG ORDER BY`) may need adjustment. |

### Other gaps

- **Token counts** (input/output/cached separately, time-to-first-token) are not in `RunRow`. Only total `cost_usd`, `latency_ms`, `tool_calls`. Phase 4b should add them.
- **Human spot-check workflow** for LLM-as-judge accuracy (10–20% sample) — not implemented.
- **Tool transport is in-process**, not real MCP subprocess. The agent factories call SourceServer/ContextEngine directly. The MCP entrypoints exist (`arb.mcp.servers.entrypoints`, `arb.mcp.servers.context_entrypoint`) but the eval harness doesn't use them. Phase 6 docstring in `arb/eval/agents.py` says: "Phase 6 promotes them to subprocess MCP transport for the headline runs (so the benchmark exercises real MCP, not in-process function calls)." — this was not actually done.
- **Single-tenancy hardcoded.** `tenant_id` exists on every event but is set from config; multi-tenancy is an extension point.
- **No vector / RAG topic.** Documented as "What's NOT in v1."
- **`arb.eval.tasks.build_lookup_task`** picks the first customer (`customers[0]`). Could be made parameterised but isn't — only one instance per category exists per snapshot.

### To swap out the dataset

The dataset is synthetic; "swapping" means changing what the world generator emits. To use a different domain (e.g. healthcare, ad tech):

1. Replace `src/arb/world/state.py` dataclasses with the new domain entities.
2. Replace `src/arb/world/generator.py` with a generator that emits the new entities.
3. Rewrite the Avro schemas in `schemas/` and the topic list in `arb.world.generator.iter_topics`.
4. Rewrite the per-source projectors (`src/arb/serving/projectors.py`) and the `SERVER_TO_STORES` / `STORE_TO_TOPIC` maps in `arb.mcp.servers.builder`.
5. Rewrite the three view SQL files under `sql/views/` and the Pydantic schemas in `arb/context/schemas.py`.
6. Rewrite the task builders in `arb/eval/tasks.py`.

There is no plug-in dataset abstraction; this is a deliberate v1 simplification.

---

## 13. Key files to read first

In this order:

1. **`README.md`** — five minutes; orients you to the two variants and the three phases of status.
2. **`docs/methodology.md`** — the three load-bearing decisions (snapshot-first grading, per-agent token scoping, headline metric naming). Everything downstream depends on these.
3. **`docs/architecture.md`** — the ASCII flow diagram + "why this shape" explanations.
4. **`src/arb/world/state.py` + `src/arb/world/generator.py`** — the in-memory `WorldState` and the tick-driven generator. Read `state.py` for the entities; skim `generator.py` for the bootstrap + tick loop.
5. **`src/arb/eval/tasks.py`** — the three task definitions and graders. The multi-hop task (chargeback story) is the marquee.
6. **`src/arb/context/views.py` + `src/arb/context/schemas.py` + `sql/views/*.sql`** — the entire Variant B contract: registry, output schemas, SQL.
7. **`src/arb/eval/agents.py`** — confirms the methodology guarantee that variants share a system prompt and differ only in toolset.
8. **`src/arb/mcp/servers/builder.py`** — how the six Variant A SourceServers get assembled from `config/variant_a.yaml`. Maps store names → topic names → projectors → scopes.
9. **`src/arb/eval/runner.py`** — orchestration: matrix building, snapshot capture, run-row construction, summarisation. The `NotImplementedError` in `run_task_against_model` is the Phase 4b boundary.
10. **`notebooks/results.ipynb` + `tests/fixtures/example_runs.jsonl`** — open the notebook against the synthetic fixture to see the marquee charts immediately.

---

## File: `HANDOFF.md`

Path: `/home/user/agent-retrieval-bench/HANDOFF.md`
