"""Dependency-injection composition root.

Repositories and services are constructed here (and only here). Storage roots
come from settings, so swapping SQLite for PostgreSQL later is a change confined
to this file plus a new repository adapter.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from ..application.backtest_service import BacktestService
from ..data.storage.backtest_store import SqliteBacktestRepository
from ..data.storage.parquet_store import ParquetCandleRepository
from ..data.storage.sqlite_catalog import SqliteCatalogRepository


@lru_cache
def _data_root() -> Path:
    return Path(os.environ.get("QSR_DATA_DIR", "data"))


@lru_cache
def candle_repo() -> ParquetCandleRepository:
    return ParquetCandleRepository(_data_root() / "datasets")


@lru_cache
def catalog_repo() -> SqliteCatalogRepository:
    return SqliteCatalogRepository(_data_root() / "catalog.sqlite")


@lru_cache
def backtest_repo() -> SqliteBacktestRepository:
    return SqliteBacktestRepository(_data_root() / "backtests.sqlite")


@lru_cache
def backtest_service() -> BacktestService:
    return BacktestService(candle_repo(), catalog_repo(), backtest_repo())
