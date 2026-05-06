from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from arb.world.generator import GeneratorConfig

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def laptop_config() -> GeneratorConfig:
    raw = yaml.safe_load((REPO_ROOT / "config" / "scale.laptop.yaml").read_text())
    # Shrink for fast tests.
    raw["cardinalities"]["customers"] = 100
    raw["cardinalities"]["skus"] = 20
    raw["cardinalities"]["warehouses"] = 2
    raw["cardinalities"]["baseline_orders"] = 50
    raw["simulation"]["duration_sec"] = 15
    # Bump rates so every topic is exercised within the short test window.
    raw["rates"]["support_ticket_per_sec"] = 2.0
    raw["rates"]["return_probability"] = 0.1
    raw["rates"]["payment_event_probability"] = 0.1
    return GeneratorConfig.from_dict(raw)


@pytest.fixture
def schemas_dir() -> Path:
    return REPO_ROOT / "schemas"


@pytest.fixture
def fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "fixtures"
