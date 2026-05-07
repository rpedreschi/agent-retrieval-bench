.PHONY: install lint typecheck test up down generate-laptop generate-full \
        snapshot-laptop bench-laptop bench-headline mcp-context

install:
	uv sync --extra dev

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy

test:
	uv run pytest

up:
	docker compose up -d

down:
	docker compose down -v

generate-laptop:
	uv run arb generate --config config/scale.laptop.yaml --seed 42

generate-full:
	uv run arb generate --config config/scale.full.yaml --seed 42

snapshot-laptop:
	mkdir -p out
	uv run arb snapshot --config config/scale.laptop.yaml --seed 42 --out out/ground_truth_snapshot.json

mcp-source-%:
	uv run python -m arb.mcp.servers.entrypoints $* config/variant_a.yaml

mcp-context:
	@if [ -z "$$ARB_DELTASTREAM_URL" ]; then \
	  echo "ERROR: Variant B requires DeltaStream credentials."; \
	  echo "Set ARB_DELTASTREAM_URL, ARB_DELTASTREAM_TOKEN, ARB_DELTASTREAM_DATABASE."; \
	  echo "See .env.example."; \
	  exit 1; \
	fi
	uv run python -m arb.mcp.servers.context_entrypoint config/variant_b.yaml

# Laptop run: generates a snapshot, builds the eval matrix, prints what it
# WOULD execute (dry run). Variant B is skipped if DeltaStream creds aren't
# present; the harness itself produces no run rows in laptop mode.
bench-laptop: snapshot-laptop
	mkdir -p out
	uv run arb eval \
		--config config/eval.yaml \
		--world-config config/scale.laptop.yaml \
		--seed 42 \
		--out out/runs.jsonl \
		--summary out/summary.json
	@echo
	@echo "Laptop run complete. To render charts:"
	@echo "  jupyter notebook notebooks/results.ipynb"
	@echo "Default RUNS_PATH points at the example fixture; switch it to out/runs.jsonl"
	@echo "once Phase 4b lands real-model execution."

# Headline run: requires DeltaStream creds + API keys. Phase 4b wiring.
bench-headline:
	@echo "bench-headline requires Phase 4b (real-model execution wiring)."
	@echo "When ready: ensure ARB_DELTASTREAM_*, ANTHROPIC_API_KEY, OPENAI_API_KEY"
	@echo "are set, then: uv run arb eval --execute --config config/eval.yaml ..."
	@exit 1
