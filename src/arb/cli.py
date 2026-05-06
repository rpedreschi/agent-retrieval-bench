"""arb CLI."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
import structlog
import yaml

from arb.world.generator import GeneratorConfig, InMemorySink, run

log = structlog.get_logger()


@click.group()
def main() -> None:
    """agent-retrieval-bench command-line interface."""


@main.command("generate")
@click.option(
    "--config", "config_path",
    type=click.Path(exists=True, dir_okay=False), required=True,
)
@click.option("--seed", type=int, required=True)
@click.option(
    "--dry-run/--no-dry-run", default=None,
    help="Force in-memory sink even if config enables Kafka.",
)
@click.option(
    "--out", "out_path", type=click.Path(dir_okay=False), default=None,
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


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
