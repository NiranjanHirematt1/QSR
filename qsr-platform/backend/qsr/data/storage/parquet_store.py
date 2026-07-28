"""Parquet-backed CandleRepository.

Candle series live as columnar Parquet under ``<root>/<dataset_id>/base.parquet``.
Derived-timeframe caches can live alongside as ``<tf>.parquet`` (memoised on
first request by higher layers).
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from ..ingestion.schema import ALL_COLUMNS


class ParquetCandleRepository:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, dataset_id: str) -> Path:
        d = self._root / dataset_id
        d.mkdir(parents=True, exist_ok=True)
        return d / "base.parquet"

    def write(self, dataset_id: str, df: pl.DataFrame) -> None:
        df.select(ALL_COLUMNS).write_parquet(self._path(dataset_id))

    def read(self, dataset_id: str) -> pl.DataFrame:
        return pl.read_parquet(self._path(dataset_id))

    def exists(self, dataset_id: str) -> bool:
        return self._path(dataset_id).exists()
