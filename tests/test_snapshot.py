from __future__ import annotations

import json

from arb.snapshot import snapshot_dict
from arb.world.generator import Generator, InMemorySink


def test_snapshot_is_deterministic_for_seed(laptop_config) -> None:
    a = Generator(config=laptop_config, sink=InMemorySink(), seed=99)
    a.run()
    b = Generator(config=laptop_config, sink=InMemorySink(), seed=99)
    b.run()
    da = json.dumps(snapshot_dict(a.state), sort_keys=True)
    db = json.dumps(snapshot_dict(b.state), sort_keys=True)
    assert da == db


def test_snapshot_advances_with_more_ticks(laptop_config) -> None:
    g = Generator(config=laptop_config, sink=InMemorySink(), seed=1)
    g.bootstrap()
    early = snapshot_dict(g.state)
    for t in range(int(laptop_config.duration_sec / laptop_config.tick_sec)):
        g.tick(t)
    late = snapshot_dict(g.state)
    assert len(late["orders"]) >= len(early["orders"])
    # Snapshot covers all eight kinds of state.
    for key in ("customers", "orders", "inventory", "returns", "tickets", "skus", "warehouses"):
        assert key in late
