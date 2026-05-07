"""Seeded RNG plumbing.

A single root SeedSequence spawns named child streams. Spawning is deterministic
in spawn order, so as long as we always request the same named streams in the
same order we get reproducible event payloads across runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class RngBundle:
    root_seed: int
    _root: np.random.SeedSequence = field(init=False)
    _streams: dict[str, np.random.Generator] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._root = np.random.SeedSequence(self.root_seed)

    def stream(self, name: str) -> np.random.Generator:
        """Return (and cache) a named child stream.

        Streams are spawned in first-request order; tests assert that the order
        of first-request matches between runs by checking event-stream hashes.
        """
        if name not in self._streams:
            (child,) = self._root.spawn(1)
            # Re-seed deterministically from the child seq + a stable hash of the name
            # so streams are also independent of spawn order across versions.
            mixed = np.random.SeedSequence(entropy=child.entropy, spawn_key=(_stable_hash(name),))
            self._streams[name] = np.random.default_rng(mixed)
        return self._streams[name]


def _stable_hash(name: str) -> int:
    # Deterministic across processes (Python's hash() is salted).
    h = 1469598103934665603
    for b in name.encode("utf-8"):
        h ^= b
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h & 0x7FFFFFFF
