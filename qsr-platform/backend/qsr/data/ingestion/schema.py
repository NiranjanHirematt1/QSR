"""Canonical in-memory schema for candle data.

After ingestion, *all* candle data — regardless of source format — is a Polars
DataFrame with exactly these columns and dtypes, timestamps in UTC. Every
component downstream (validation, resampling, storage) can therefore assume one
shape. This normalisation is the whole job of the ingestion layer.
"""
from __future__ import annotations

import polars as pl

# Column names (single source of truth; never hardcode these strings elsewhere).
TS = "open_time"      # pl.Datetime("us", "UTC")
OPEN = "open"
HIGH = "high"
LOW = "low"
CLOSE = "close"
VOLUME = "volume"

OHLCV = (OPEN, HIGH, LOW, CLOSE, VOLUME)
ALL_COLUMNS = (TS, *OHLCV)

CANONICAL_SCHEMA: dict[str, pl.DataType] = {
    TS: pl.Datetime(time_unit="us", time_zone="UTC"),
    OPEN: pl.Float64,
    HIGH: pl.Float64,
    LOW: pl.Float64,
    CLOSE: pl.Float64,
    VOLUME: pl.Float64,
}


def empty_frame() -> pl.DataFrame:
    return pl.DataFrame(schema=CANONICAL_SCHEMA)
