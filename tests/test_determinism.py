from __future__ import annotations

import hashlib
import json

from arb.world.generator import InMemorySink, run


def _digest(events: list[tuple[str, str, dict]]) -> str:
    h = hashlib.sha256()
    for topic, key, value in events:
        h.update(topic.encode())
        h.update(b"\x00")
        h.update(key.encode())
        h.update(b"\x00")
        h.update(json.dumps(value, sort_keys=True).encode())
        h.update(b"\n")
    return h.hexdigest()


def test_same_seed_produces_identical_event_stream(laptop_config) -> None:
    a = InMemorySink()
    b = InMemorySink()
    run(laptop_config, a, seed=12345)
    run(laptop_config, b, seed=12345)
    assert _digest(a.events) == _digest(b.events)
    assert len(a.events) == len(b.events) > 0


def test_different_seed_changes_event_stream(laptop_config) -> None:
    a = InMemorySink()
    b = InMemorySink()
    run(laptop_config, a, seed=1)
    run(laptop_config, b, seed=2)
    assert _digest(a.events) != _digest(b.events)
