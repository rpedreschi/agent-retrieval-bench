# Bring-your-own streaming stack for Variant B

Variant B (the "context engine" arm) ships against [DeltaStream](https://www.deltastream.io/)
as the supported backend. The headline benchmark numbers are produced against
DeltaStream and only DeltaStream — see `docs/methodology.md`.

If you do not want to use DeltaStream, you can still run the benchmark, but
**you have to stand up an equivalent stack yourself**. This is not a small job.
A realistic substitute is roughly:

- A streaming-SQL engine that can read Kafka and maintain materialised joins
  with low end-to-end latency. Examples: Apache Flink, Materialize,
  RisingWave, ksqlDB.
- A serving layer the materialised views are pushed into and read from.
  Examples: ClickHouse, Apache Pinot, Snowflake interactive, Redis.
- The wiring between them (Kafka → Flink job → ClickHouse sink, or
  equivalent) and operational handling of schema evolution, backpressure,
  recovery, etc.

This benchmark **does not** ship a turn-key Flink+ClickHouse compose. We
considered it and decided against it: a half-good substitute would harm
benchmark credibility more than no substitute at all, and the operational
gap between a demo compose file and a real production deployment of those
components is exactly the gap the benchmark exists to measure.

## The contract Variant B must satisfy

Whatever stack you pick, your implementation has to honour the same contract
the DeltaStream-backed implementation honours:

1. **Three named materialised views**, with the schemas defined in
   `src/arb/context/schemas.py`:
   - `customer_360`
   - `order_state`
   - `returns_eligibility`

2. **End-to-end freshness SLA** matching the per-view configuration in
   `config/variant_b.yaml`. The default is 250 ms p99 from event commit on the
   source Kafka topic to visibility in the materialised view, applied
   uniformly across the three views. Per-view overrides are supported in case
   one view legitimately tolerates more lag than another.

3. **A single MCP retrieval interface** conforming to
   `arb.context.engine.ContextEngine` (one tool: `get_view(name, params)`),
   protected by a bearer token carrying only the `context:read` scope. The
   parameter shape per view is defined in `src/arb/context/views.py`.

The reference SQL for the three views lives under `sql/views/` and is
authored against DeltaStream's dialect. Treat it as the canonical
specification. Translate to your engine of choice; do not reinterpret the
join semantics.

## What the local engine is and is not

The repo also ships a `LocalContextEngine` (`src/arb/context/local.py`) used by
`make bench-laptop`. It is a deliberately simple in-process Python join
maintainer built on the existing per-source `ServingStore` infrastructure.

- **It is** a way to run the full pipeline end-to-end without provisioning
  any streaming infrastructure, a reference oracle for view semantics on a
  fixed input, and an aid to harness development.
- **It is not** the system under test. Its performance characteristics are
  irrelevant to the benchmark. Runs that use it are tagged `engine=local` in
  every trace and result row so they cannot be silently substituted for the
  headline numbers.

If you submit results based on a non-DeltaStream stack, please tag them with
`engine=<your-stack>` and report them separately from the headline numbers.
