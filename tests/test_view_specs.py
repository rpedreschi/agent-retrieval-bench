"""Sanity checks on the view registry + SQL files."""
from __future__ import annotations

from pathlib import Path

from arb.context.views import VIEWS

REPO = Path(__file__).resolve().parent.parent


def test_three_views_registered() -> None:
    assert set(VIEWS.keys()) == {"customer_360", "order_state", "returns_eligibility"}


def test_each_view_has_a_sql_file() -> None:
    for spec in VIEWS.values():
        p = REPO / spec.sql_path
        assert p.exists(), f"missing SQL for {spec.name}"
        text = p.read_text()
        assert "CREATE MATERIALIZED VIEW" in text
        assert spec.name in text


def test_each_view_lists_its_source_topics() -> None:
    for spec in VIEWS.values():
        sql = (REPO / spec.sql_path).read_text()
        for topic in spec.source_topics:
            assert topic in sql, f"{spec.name} SQL does not reference {topic}"
