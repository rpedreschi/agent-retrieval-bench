"""Validate emitted events against the Avro schemas via fastavro."""
from __future__ import annotations

import io
import json

import fastavro
import pytest

from arb.kafka.producer import TOPIC_TO_SCHEMA_FILE
from arb.world.generator import InMemorySink, run


def _parsed_schema(schemas_dir, topic: str):
    raw = (schemas_dir / TOPIC_TO_SCHEMA_FILE[topic]).read_text()
    return fastavro.parse_schema(json.loads(raw))


@pytest.mark.parametrize("topic", list(TOPIC_TO_SCHEMA_FILE.keys()))
def test_every_event_validates_against_its_schema(topic, laptop_config, schemas_dir) -> None:
    sink = InMemorySink()
    run(laptop_config, sink, seed=7)
    schema = _parsed_schema(schemas_dir, topic)
    payloads = sink.by_topic().get(topic, [])
    assert payloads, f"no events emitted for {topic}"
    buf = io.BytesIO()
    fastavro.writer(buf, schema, payloads)  # raises if any record is invalid
