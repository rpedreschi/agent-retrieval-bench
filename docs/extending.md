# Extending the benchmark

Four common extensions, each one PR.

## Add a new materialised view (Variant B)

1. Append a `ViewSpec` to `arb.context.views.VIEWS` with the new view's `primary_key`, `source_topics`, and `sql_path`.
2. Add an output schema (a Pydantic model) to `arb.context.schemas` and register it in `VIEW_SCHEMAS`.
3. Author the view's SQL under `sql/views/<name>.sql`. Treat the DeltaStream dialect as canonical.
4. Update `config/variant_b.yaml`'s `freshness_sla_ms` block if the new view has a different SLA.
5. Tests in `tests/test_view_specs.py` will auto-pick up the new file via the registry.

The MCP interface does not change — `get_view(name, params)` already accepts arbitrary view names.

## Add a new task category

1. In `arb.eval.tasks`, add a `build_<category>_task(snapshot)` builder + a grader.
2. Append the new category to `TaskCategory` (at the end — never reorder).
3. Add it to `build_all()` so the eval matrix picks it up.
4. Tests in `tests/test_eval_tasks_and_grading.py` should cover both the happy path and a deliberate wrong-answer that maps to the right `FailureCategory`.

## Add a new condition

1. Add a value to `arb.eval.conditions.Condition`.
2. Extend `apply_condition()` to set the right fault profiles for the new condition.
3. Update `config/eval.yaml` to reference it (or omit if it's opt-in).
4. The runner picks it up via `build_matrix()` automatically.

## Plug in a new model

See `docs/models.md`. Either append to `arb.eval.models.MODELS` (preferred for repeated use) or pass a fully-qualified Inspect AI string in `config/eval.yaml`. Both routes work.

## Anti-patterns

- Adding a new failure category in the middle of `FailureCategory` (breaks chart ordering).
- Adding a Variant A tool that does join logic in the server (defeats the purpose of the comparison; that work belongs in the agent).
- Defining a Variant B view in Python instead of SQL (the SQL is the spec).
- Tuning the system prompt per variant (methodology violation).
