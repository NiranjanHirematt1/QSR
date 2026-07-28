"""Shared normalisation: turn a raw source frame into the canonical schema."""
from __future__ import annotations

import polars as pl

from .column_mapping import ColumnMapping
from .schema import CLOSE, HIGH, LOW, OPEN, TS, VOLUME


def normalize(raw: pl.DataFrame, mapping: ColumnMapping) -> pl.DataFrame:
    """Map, parse timestamps to UTC, coerce dtypes, sort. Format-agnostic."""
    ts_expr = _timestamp_expr(mapping)

    df = raw.select(
        ts_expr.alias(TS),
        pl.col(mapping.open).cast(pl.Float64).alias(OPEN),
        pl.col(mapping.high).cast(pl.Float64).alias(HIGH),
        pl.col(mapping.low).cast(pl.Float64).alias(LOW),
        pl.col(mapping.close).cast(pl.Float64).alias(CLOSE),
        (pl.col(mapping.volume).cast(pl.Float64) if mapping.volume in raw.columns
         else pl.lit(0.0)).alias(VOLUME),
    )
    return df.sort(TS)


def _timestamp_expr(m: ColumnMapping) -> pl.Expr:
    # Case 1: epoch integers in a single column.
    if m.datetime and m.epoch_unit:
        return (
            pl.col(m.datetime)
            .cast(pl.Int64)
            .cast(pl.Datetime(time_unit=m.epoch_unit))  # type: ignore[arg-type]
            .dt.replace_time_zone("UTC")
        )

    # Case 2: a single combined datetime string column.
    if m.datetime:
        parsed = _parse_str(pl.col(m.datetime), m.datetime_format)
        return _to_utc(parsed, m.source_tz)

    # Case 3: split date (+ optional time) columns.
    if m.date and m.time:
        combined = pl.col(m.date).cast(pl.Utf8) + pl.lit(" ") + pl.col(m.time).cast(pl.Utf8)
        parsed = _parse_str(combined, m.datetime_format)
        return _to_utc(parsed, m.source_tz)

    if m.date:
        parsed = _parse_str(pl.col(m.date), m.datetime_format)
        return _to_utc(parsed, m.source_tz)

    raise ValueError("Unresolvable timestamp mapping")  # pragma: no cover


def _parse_str(expr: pl.Expr, fmt: str | None) -> pl.Expr:
    return expr.str.strptime(pl.Datetime, format=fmt, strict=False)


def _to_utc(expr: pl.Expr, source_tz: str) -> pl.Expr:
    # Interpret naive timestamps as being in source_tz, then convert to UTC.
    if source_tz.upper() == "UTC":
        return expr.dt.replace_time_zone("UTC")
    return expr.dt.replace_time_zone(source_tz).dt.convert_time_zone("UTC")
