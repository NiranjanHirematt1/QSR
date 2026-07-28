"""Concrete CandleSource implementations for CSV and Parquet."""
from __future__ import annotations

from pathlib import Path

import polars as pl

from .column_mapping import ColumnMapping
from .normalize import normalize


class CsvReader:
    """Reads OHLCV CSV files."""

    def read(self, path: Path, mapping: ColumnMapping) -> pl.DataFrame:
        raw = pl.read_csv(path, infer_schema_length=1000)
        return normalize(raw, mapping)


class ParquetReader:
    """Reads OHLCV Parquet files."""

    def read(self, path: Path, mapping: ColumnMapping) -> pl.DataFrame:
        raw = pl.read_parquet(path)
        return normalize(raw, mapping)
