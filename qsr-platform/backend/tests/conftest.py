"""Shared fixtures: synthetic candle frames in the canonical schema."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl
import pytest

from qsr.data.ingestion.schema import CLOSE, HIGH, LOW, OPEN, TS, VOLUME


def _utc(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def make_frame(rows: list[tuple]) -> pl.DataFrame:
    """rows = list of (open_time, o, h, l, c, v)."""
    return pl.DataFrame(
        {
            TS: [r[0] for r in rows],
            OPEN: [float(r[1]) for r in rows],
            HIGH: [float(r[2]) for r in rows],
            LOW: [float(r[3]) for r in rows],
            CLOSE: [float(r[4]) for r in rows],
            VOLUME: [float(r[5]) for r in rows],
        },
        schema_overrides={TS: pl.Datetime("us", "UTC")},
    ).sort(TS)


@pytest.fixture
def clean_m1() -> pl.DataFrame:
    """Ten consecutive 1-minute bars, all valid."""
    start = _utc(2024, 1, 2, 9, 0)  # a Tuesday, in-session
    rows = []
    price = 100.0
    for i in range(10):
        o = price
        h = o + 0.5
        low = o - 0.5
        c = o + 0.2
        rows.append((start + timedelta(minutes=i), o, h, low, c, 1000 + i))
        price = c
    return make_frame(rows)
