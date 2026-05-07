# Contributing

This benchmark is forkable by design. The most useful contributions are: adding a new materialised view, adding a new task category, adding a new condition, or plugging in a new model. Each is documented in `docs/extending.md` with the exact files to change.

## Development setup

```bash
uv sync --extra dev
docker compose up -d   # local Kafka + Schema Registry, only needed for end-to-end runs
uv run pytest          # 89 tests, no creds required
uv run ruff check src tests
```

## Pull request expectations

- One concern per PR. New view? Just the view. New task? Just the task.
- Tests for any non-trivial change. The world generator, conditions, grading, and analysis layer are load-bearing — bugs there compromise the benchmark's credibility.
- `ruff check` clean. Type hints on public functions.
- If a change shifts a number reported in the blog/talk, say so explicitly in the PR description.

## What to avoid

- **Tuning prompts to make a model look better.** The methodology guarantees identical system prompts across variants and models. If a model fails a category disproportionately, that's a finding — log it; don't compensate.
- **Adding a second Variant B implementation.** Variant B is DeltaStream-backed. A DuckDB stub exists for a future addition; that's the only alternative we'll consider.
- **Changing the failure taxonomy without a chart change.** The categories in `arb.eval.grading.FailureCategory` are referenced by the headline chart and the results notebook. Add new categories at the end; never reorder.
- **Running headline numbers from non-headline models.** Anything outside `arb.eval.models.MODELS` is valid for forker exploration but must be tagged separately. See `docs/models.md`.

## Repository layout

```
src/arb/
  world/        # world-state generator + 8 Kafka topics
  kafka/        # Avro producer
  serving/      # per-source serving stores with replication lag + cache TTL
  mcp/          # auth, fault injection, six Variant A servers, single Variant B server
  context/      # ContextEngine protocol, DeltaStream client, view schemas
  eval/         # Inspect AI harness: conditions, agents, tasks, grading, models, runner
  analysis/    # bootstrapped metrics, failure taxonomy, matplotlib charts
  snapshot.py  # deterministic ground-truth JSON
  cli.py       # arb generate / arb snapshot / arb eval

sql/views/     # canonical SQL for the three Variant B views
schemas/       # Avro schemas for the eight Kafka topics
config/        # scale.{laptop,full}.yaml, variant_{a,b}.yaml, eval.yaml
docs/          # methodology, architecture, models, extending
notebooks/     # results.ipynb
tests/         # 89 tests; tests/_fakes.py for in-test mocks
```

## Reporting results

If you publish numbers from this harness, include:

- The git revision used.
- The model versions actually exercised (Inspect AI strings).
- Whether you ran headline mode (DeltaStream) or with a substitute backend.
- Confidence intervals on every reported metric. Bootstrap, n=2000.
- The full failure-taxonomy chart, not just the success rate.

If your numbers diverge directionally from the published headline, that's interesting — open an issue with the JSONL output attached.
