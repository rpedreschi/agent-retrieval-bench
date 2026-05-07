"""Kafka Avro sink, backed by confluent-kafka + Schema Registry.

Imports of confluent-kafka are deferred so that the in-memory generator and
tests do not require a broker or the native librdkafka build at import time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TOPIC_TO_SCHEMA_FILE: dict[str, str] = {
    "retail.customers": "customers.avsc",
    "retail.customer_tier_changes": "customer_tier_changes.avsc",
    "retail.orders": "orders.avsc",
    "retail.order_items": "order_items.avsc",
    "retail.inventory_snapshots": "inventory_snapshots.avsc",
    "retail.returns": "returns.avsc",
    "retail.support_tickets": "support_tickets.avsc",
    "retail.payment_events": "payment_events.avsc",
}


def load_schemas(schemas_dir: Path) -> dict[str, str]:
    """Load Avro schema JSON strings keyed by topic."""
    out: dict[str, str] = {}
    for topic, fname in TOPIC_TO_SCHEMA_FILE.items():
        p = schemas_dir / fname
        out[topic] = p.read_text()
        # Validate it parses as JSON.
        json.loads(out[topic])
    return out


@dataclass
class KafkaAvroSink:
    bootstrap_servers: str
    schema_registry_url: str
    schemas_dir: Path
    _producer: Any = field(init=False, default=None)
    _serializers: dict[str, Any] = field(init=False, default_factory=dict)
    _string_serializer: Any = field(init=False, default=None)

    def __post_init__(self) -> None:
        from confluent_kafka import Producer
        from confluent_kafka.schema_registry import SchemaRegistryClient
        from confluent_kafka.schema_registry.avro import AvroSerializer
        from confluent_kafka.serialization import StringSerializer

        sr = SchemaRegistryClient({"url": self.schema_registry_url})
        schemas = load_schemas(self.schemas_dir)
        self._serializers = {
            topic: AvroSerializer(sr, schema_str) for topic, schema_str in schemas.items()
        }
        self._string_serializer = StringSerializer("utf_8")
        self._producer = Producer({"bootstrap.servers": self.bootstrap_servers})

    def emit(self, topic: str, key: str, value: dict[str, Any]) -> None:
        from confluent_kafka.serialization import MessageField, SerializationContext

        ser = self._serializers[topic]
        ctx = SerializationContext(topic, MessageField.VALUE)
        self._producer.produce(
            topic=topic,
            key=self._string_serializer(key),
            value=ser(value, ctx),
        )
        self._producer.poll(0)

    def flush(self) -> None:
        if self._producer is not None:
            self._producer.flush(10)
