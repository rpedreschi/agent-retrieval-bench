"""Fault injection for the degraded condition.

Each source server is configured with a FaultProfile. Latency is modelled as a
fixed (or seeded-jittered) delay added before returning. Errors are injected
probabilistically and surface as a structured ``source_error`` response so the
agent and the failure classifier can distinguish them from real exceptions.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class FaultProfile:
    latency_ms: int = 0
    error_rate: float = 0.0
    error_code: str = "source_timeout"
    error_message: str = "upstream source timed out"

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> FaultProfile:
        if not d:
            return cls()
        return cls(
            latency_ms=int(d.get("latency_ms", 0)),
            error_rate=float(d.get("error_rate", 0.0)),
            error_code=str(d.get("error_code", "source_timeout")),
            error_message=str(d.get("error_message", "upstream source timed out")),
        )


class InjectedSourceError(Exception):
    def __init__(self, profile: FaultProfile) -> None:
        super().__init__(profile.error_message)
        self.code = profile.error_code

    def to_dict(self) -> dict[str, Any]:
        return {"error": "source_error", "code": self.code, "message": str(self)}


@dataclass
class FaultInjector:
    profile: FaultProfile
    rng: np.random.Generator
    sleep: bool = True  # disabled in tests

    def maybe_inject(self) -> None:
        if self.profile.latency_ms > 0 and self.sleep:
            time.sleep(self.profile.latency_ms / 1000.0)
        if self.profile.error_rate > 0.0 and float(self.rng.random()) < self.profile.error_rate:
            raise InjectedSourceError(self.profile)
