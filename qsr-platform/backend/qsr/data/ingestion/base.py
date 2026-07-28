"""CandleSource port — the ingestion boundary."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import polars as pl

from .column_mapping import ColumnMapping


@runtime_checkable
class CandleSource(Protocol):
    """Reads a source file and returns a DataFrame in the canonical schema
    (UTC, sorted, correctly typed). Implementations differ only in file format;
    the normalisation contract is identical."""

    def read(self, path: Path, mapping: ColumnMapping) -> pl.DataFrame: ...
