# Methodology

This document captures three load-bearing decisions that the rest of the
benchmark depends on. Change them only with strong reason and a PR that updates
this file in the same commit.

## 1. Snapshot-first grading

The world-state generator emits events to Kafka continuously, which is correct
for testing agents under live conditions. But **grading is performed against a
frozen snapshot** of the world state captured at task-start time.

- At the moment a task begins, the harness calls `arb snapshot` (or the
  programmatic equivalent) to write `ground_truth_snapshot.json`.
- The snapshot captures the exact `WorldState` the agent is being asked to
  reason about: customers, orders, items, inventory, returns, tickets, and the
  scenario state.
- The grader compares agent output against the snapshot — never against live
  Kafka, which has moved on by the time the agent finishes.
- The agent still sees the live system through its tools; only correctness
  judgement is frozen.

Snapshots are deterministic given a seed: identical seed + identical config +
identical tick number produces a byte-identical snapshot.

## 2. Per-agent MCP token scoping

Authorisation is enforced from day one. Each variant gets a bearer token whose
scopes determine which MCP tools it can invoke.

- **Variant A token** scopes: `customers:read`, `orders:read`, `inventory:read`,
  `returns:read`, `support:read`, `payments:read` — six source MCP servers,
  read-only.
- **Variant B token** scope: `context:read` — only the consolidated retrieval
  MCP server.
- Tokens and scopes live in `config/variant_a.yaml` and (Phase 3)
  `config/variant_b.yaml`.
- Every MCP tool call validates the bearer token against the scope set for its
  server. Calls without a valid token, or with a token missing the required
  scope, return a structured `auth_error` response and are counted in the
  failure taxonomy as `auth_denied` (which should never legitimately fire and
  is therefore a sentinel for misconfigured experiments).

This gives the least-privilege story for the talk without a retrofit.

## 3. Headline metric names

Standardised across the harness and the results notebook:

- `cost_per_correct` — total token + tool-call cost divided by number of
  correctly-completed tasks. Replaces the longer `cost_per_successful_task`.
- `cost_per_correct_degraded` — same metric, restricted to tasks run under the
  *degraded* condition. **This is the headline metric.** Clean conditions are
  the demo; degraded conditions are production.

Other reported metrics (task success rate, grounding scores, latency
percentiles, failure-taxonomy histogram) keep their natural names.
