"""Catalog metadata model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DatasetMeta:
    dataset_id: str
    symbol: str
    base_timeframe: str
    source_format: str
    row_count: int
    start: datetime
    end: datetime
    checksum: str
    imported_at: datetime
    validation_json: str  # serialised ValidationReport


@dataclass(frozen=True, slots=True)
class StoredBacktest:
    """A persisted backtest run. Payloads are opaque JSON strings so the data
    layer stays ignorant of analytics/reporting types."""

    run_id: str
    strategy_id: str
    instrument: str
    base_timeframe: str
    dataset_id: str
    created_at: datetime
    net_profit: float
    trade_count: int
    manifest_json: str
    result_json: str   # trades + equity + performance report
