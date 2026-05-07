"""arb CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
import structlog
import yaml

from arb.snapshot import write_snapshot
from arb.world.generator import Generator, GeneratorConfig, InMemorySink, run

log = structlog.get_logger()


@click.group()
def main() -> None:
    """agent-retrieval-bench command-line interface."""


@main.command("generate")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
)
@click.option("--seed", type=int, required=True)
@click.option(
    "--dry-run/--no-dry-run",
    default=None,
    help="Force in-memory sink even if config enables Kafka.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False),
    default=None,
    help="If set, write all emitted events as JSONL to this file.",
)
def generate(config_path: str, seed: int, dry_run: bool | None, out_path: str | None) -> None:
    """Run the world-state generator."""
    raw = yaml.safe_load(Path(config_path).read_text())
    cfg = GeneratorConfig.from_dict(raw)
    use_kafka = bool(raw.get("kafka", {}).get("enabled", False))
    if dry_run is True:
        use_kafka = False

    sink: Any
    if use_kafka:
        from arb.kafka import KafkaAvroSink

        kcfg = raw["kafka"]
        sink = KafkaAvroSink(
            bootstrap_servers=kcfg["bootstrap_servers"],
            schema_registry_url=kcfg["schema_registry_url"],
            schemas_dir=Path(__file__).resolve().parent.parent.parent / "schemas",
        )
        log.info("sink.kafka", bootstrap=kcfg["bootstrap_servers"])
    else:
        sink = InMemorySink()
        log.info("sink.in_memory")

    log.info("generator.start", seed=seed, duration_sec=cfg.duration_sec)
    run(cfg, sink, seed=seed)
    log.info("generator.done")

    if out_path is not None and isinstance(sink, InMemorySink):
        with Path(out_path).open("w") as f:
            for topic, key, value in sink.events:
                f.write(json.dumps({"topic": topic, "key": key, "value": value}) + "\n")
        log.info("dump.written", path=out_path, count=len(sink.events))


@main.command("snapshot")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
)
@click.option("--seed", type=int, required=True)
@click.option(
    "--at-tick",
    type=int,
    default=None,
    help="Tick at which to capture the snapshot. Defaults to end-of-run.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False),
    required=True,
    help="Where to write ground_truth_snapshot.json.",
)
def snapshot(config_path: str, seed: int, at_tick: int | None, out_path: str) -> None:
    """Run the generator and write a deterministic ground-truth snapshot.

    Used by the eval harness at task-start time. See docs/methodology.md.
    """
    raw = yaml.safe_load(Path(config_path).read_text())
    cfg = GeneratorConfig.from_dict(raw)
    sink = InMemorySink()
    g = Generator(config=cfg, sink=sink, seed=seed)
    g.bootstrap()
    ticks = int(cfg.duration_sec / cfg.tick_sec) if at_tick is None else at_tick
    for tick in range(ticks):
        g.tick(tick)
    write_snapshot(g.state, Path(out_path))
    log.info("snapshot.written", path=out_path, at_tick=ticks)


@main.command("eval")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to config/eval.yaml.",
)
@click.option(
    "--world-config",
    "world_cfg_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="World-state generator config (defines the snapshot at task start).",
)
@click.option(
    "--variant-a-config",
    type=click.Path(exists=True, dir_okay=False),
    default="config/variant_a.yaml",
    show_default=True,
)
@click.option("--seed", type=int, default=42, show_default=True)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False),
    required=True,
    help="JSONL run-rows output.",
)
@click.option(
    "--summary",
    "summary_path",
    type=click.Path(dir_okay=False),
    default=None,
    help="Optional JSON summary aggregations output.",
)
@click.option(
    "--execute/--dry-run",
    default=False,
    help=(
        "When --dry-run (default), build the matrix and emit empty rows so "
        "you can confirm the harness wires correctly without API keys."
    ),
)
def eval_cmd(
    config_path: str,
    world_cfg_path: str,
    variant_a_config: str,
    seed: int,
    out_path: str,
    summary_path: str | None,
    execute: bool,
) -> None:
    """Run the evaluation matrix (tasks × variants × models × conditions × seeds)."""
    from arb.eval.runner import (
        build_matrix,
        capture_snapshot,
        emit_results,
        load_eval_config,
    )

    cfg = load_eval_config(Path(config_path))
    log.info("eval.snapshot.start", world_cfg=world_cfg_path, seed=seed)
    snap = capture_snapshot(Path(world_cfg_path), seed=seed)
    matrix = build_matrix(snap, cfg)
    log.info(
        "eval.matrix",
        tasks=len(matrix.tasks),
        variants=matrix.variants,
        models=[m.short for m in matrix.models],
        conditions=[c.value for c in matrix.conditions],
        seeds=matrix.seeds,
    )
    if not execute:
        log.info("eval.dry_run", note="not invoking models; pass --execute to run")
        emit_results([], Path(out_path))
        if summary_path:
            Path(summary_path).write_text(json.dumps({"n": 0, "dry_run": True}))
        return
    raise click.ClickException("real-model execution is wired in Phase 4b; for now use --dry-run.")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
