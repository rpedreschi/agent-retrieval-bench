.PHONY: install lint typecheck test up down generate-laptop generate-full bench-laptop

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

mcp-source-%:
	uv run python -m arb.mcp.servers.entrypoints $* config/variant_a.yaml

mcp-context:
	ARB_CONTEXT_ENGINE=local uv run python -m arb.mcp.servers.context_entrypoint config/variant_b.yaml

# Phase 6 will wire this end-to-end. For now it just runs the laptop-mode generator.
bench-laptop: up generate-laptop
