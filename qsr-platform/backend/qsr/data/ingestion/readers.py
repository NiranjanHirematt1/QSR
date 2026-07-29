"""Concrete CandleSource implementations for CSV/TSV and Parquet.

The CSV reader auto-detects delimiter (comma/tab/semicolon/pipe/space), whether
a header row is present, and how columns map to the canonical schema — so
standard CSV, TSV, MT4 (header-less, ``YYYY.MM.DD`` dates) and MT5 (tab, ``<...>``
headers) all import without manual configuration. A caller may still pass a
:class:`ColumnMapping` to override any part of the detection.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from .column_mapping import ColumnMapping
from .detect import (
    looks_like_header,
    map_named_columns,
    positional_mapping,
    sniff_delimiter,
)
from .errors import IngestionError
from .normalize import normalize

_SAMPLE_BYTES = 65_536


def _read_text_sample(path: Path) -> tuple[str, str]:
    """Return (decoded sample, encoding) handling UTF-8/UTF-16 BOMs."""
    head = path.read_bytes()[:_SAMPLE_BYTES]
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return head.decode("utf-16", errors="replace"), "utf-16"
    return head.decode("utf-8-sig", errors="replace"), "utf8"


class CsvReader:
    """Reads OHLCV CSV/TSV files with automatic shape detection."""

    def read(self, path: Path, mapping: ColumnMapping | None = None) -> pl.DataFrame:
        hint = mapping or ColumnMapping()
        sample, encoding = _read_text_sample(path)
        first_line = next((ln for ln in sample.splitlines() if ln.strip()), "")
        if not first_line:
            raise IngestionError("File appears to be empty — no data rows found.")

        separator = sniff_delimiter(sample)
        header_fields = first_line.split(separator)
        has_header = looks_like_header(header_fields)

        try:
            raw = pl.read_csv(
                path,
                separator=separator,
                has_header=has_header,
                infer_schema_length=10_000,
                encoding=encoding,
                truncate_ragged_lines=True,
                try_parse_dates=False,
            )
        except Exception as exc:
            raise IngestionError(f"Failed to parse CSV/TSV file: {exc}") from exc

        if has_header:
            resolved = map_named_columns(raw.columns, hint)
        else:
            resolved = positional_mapping([str(v) for v in raw.row(0)], hint)
        return normalize(raw, resolved)


class ParquetReader:
    """Reads OHLCV Parquet files."""

    def read(self, path: Path, mapping: ColumnMapping | None = None) -> pl.DataFrame:
        hint = mapping or ColumnMapping()
        raw = pl.read_parquet(path)
        resolved = map_named_columns(raw.columns, hint)
        return normalize(raw, resolved)
