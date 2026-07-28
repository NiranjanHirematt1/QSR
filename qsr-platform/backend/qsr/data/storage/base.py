"""Storage ports — the seam that makes SQLite->Postgres a config change.

Two repositories, two responsibilities:
  * CandleRepository  -> bulk OHLCV series (Parquet today, TimescaleDB later)
  * CatalogRepository -> dataset metadata & validation reports (SQLite today,
                         PostgreSQL later)

Nothing in the domain or application layer references SQLite or Parquet
directly; they depend only on these Protocols.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import polars as pl

from .models import DatasetMeta


@runtime_checkable
class CandleRepository(Protocol):
    def write(self, dataset_id: str, df: pl.DataFrame) -> None: ...
    def read(self, dataset_id: str) -> pl.DataFrame: ...
    def exists(self, dataset_id: str) -> bool: ...


@runtime_checkable
class CatalogRepository(Protocol):
    def save(self, meta: DatasetMeta) -> None: ...
    def get(self, dataset_id: str) -> DatasetMeta | None: ...
    def list_all(self) -> list[DatasetMeta]: ...


from .models import StoredBacktest  # noqa: E402


@runtime_checkable
class BacktestResultRepository(Protocol):
    def save(self, record: StoredBacktest) -> None: ...
    def get(self, run_id: str) -> StoredBacktest | None: ...
    def list_all(self) -> list[StoredBacktest]: ...
