"""Shared normalisation: turn a raw source frame into the canonical schema.

Given a frame whose columns have already been *resolved* to concrete names (by
the reader's auto-detection), this maps them to the canonical OHLCV schema,
parses timestamps to UTC microseconds, and coerces dtypes. It never silently
drops columns: a missing required column raises :class:`IngestionError` with a
clear message, and unparseable prices/timestamps become nulls that the
validation pipeline then surfaces loudly (fail-closed).
"""
from __future__ import annotations

import polars as pl

from .column_mapping import ColumnMapping
from .detect import detect_datetime_format, epoch_unit_for
from .errors import IngestionError
from .schema import CLOSE, HIGH, LOW, OPEN, TS, VOLUME

_CANONICAL_TS = pl.Datetime(time_unit="us", time_zone="UTC")


def normalize(raw: pl.DataFrame, mapping: ColumnMapping) -> pl.DataFrame:
    """Map, parse timestamps to UTC, coerce dtypes, sort. Format-agnostic.

    Prices are cast non-strictly (a stray non-numeric cell becomes null and is
    flagged downstream rather than aborting the whole import).
    """
    _require_columns(raw, mapping)
    ts_expr = _timestamp_expr(raw, mapping).cast(_CANONICAL_TS)

    volume_expr = (
        pl.col(mapping.volume).cast(pl.Float64, strict=False)
        if mapping.volume and mapping.volume in raw.columns
        else pl.lit(0.0)
    ).alias(VOLUME)

    df = raw.select(
        ts_expr.alias(TS),
        pl.col(mapping.open).cast(pl.Float64, strict=False).alias(OPEN),
        pl.col(mapping.high).cast(pl.Float64, strict=False).alias(HIGH),
        pl.col(mapping.low).cast(pl.Float64, strict=False).alias(LOW),
        pl.col(mapping.close).cast(pl.Float64, strict=False).alias(CLOSE),
        volume_expr,
    )
    return df.sort(TS, nulls_last=False)


def _require_columns(raw: pl.DataFrame, m: ColumnMapping) -> None:
    """Fail with an actionable message rather than a raw ColumnNotFoundError."""
    needed = {"open": m.open, "high": m.high, "low": m.low, "close": m.close}
    if m.datetime:
        needed["datetime"] = m.datetime
    if m.date:
        needed["date"] = m.date
    if m.time:
        needed["time"] = m.time
    missing = {role: col for role, col in needed.items() if col not in raw.columns}
    if missing:
        raise IngestionError(
            "Source is missing required column(s): "
            + ", ".join(f"{role}='{col}'" for role, col in missing.items())
            + f". Available columns: {raw.columns}."
        )


def _timestamp_expr(raw: pl.DataFrame, m: ColumnMapping) -> pl.Expr:
    # Case 1: split date (+ time) columns.
    if m.date and m.time:
        combined = (
            pl.col(m.date).cast(pl.Utf8).str.strip_chars()
            + pl.lit(" ")
            + pl.col(m.time).cast(pl.Utf8).str.strip_chars()
        )
        fmt = m.datetime_format or _detect_format_from(
            raw, [m.date, m.time], joiner=" "
        )
        return _to_utc(_parse_str(combined, fmt), m.source_tz)

    if m.date and not m.datetime:
        fmt = m.datetime_format or _detect_format_from(raw, [m.date])
        return _to_utc(_parse_str(pl.col(m.date).cast(pl.Utf8), fmt), m.source_tz)

    # Case 2: a single combined column — may be epoch integers or a datetime string.
    if m.datetime:
        unit = m.epoch_unit or _epoch_unit_if_epoch(raw, m.datetime)
        if unit:
            col = pl.col(m.datetime).cast(pl.Int64, strict=False)
            if unit == "s":
                # Polars has no second-granularity Datetime; scale to ms.
                col = col * 1000
            return col.cast(pl.Datetime(time_unit=_polars_unit(unit))).dt.replace_time_zone("UTC")
        fmt = m.datetime_format or _detect_format_from(raw, [m.datetime])
        return _to_utc(_parse_str(pl.col(m.datetime).cast(pl.Utf8), fmt), m.source_tz)

    raise IngestionError("Unresolvable timestamp mapping (no date/datetime column).")


# --- helpers ---------------------------------------------------------------

def _parse_str(expr: pl.Expr, fmt: str | None) -> pl.Expr:
    return expr.str.strptime(pl.Datetime("us"), format=fmt, strict=False)


def _to_utc(expr: pl.Expr, source_tz: str) -> pl.Expr:
    # Interpret naive timestamps as being in source_tz, then convert to UTC.
    # ``ambiguous``/``non_existent`` make DST fall-back/spring-forward safe
    # rather than aborting the whole import.
    if source_tz.upper() == "UTC":
        return expr.dt.replace_time_zone("UTC")
    return (
        expr.dt.replace_time_zone(source_tz, ambiguous="earliest", non_existent="null")
        .dt.convert_time_zone("UTC")
    )


def _polars_unit(unit: str) -> str:
    # Polars datetime supports ns/us/ms only; scale seconds up to ms.
    return "ms" if unit == "s" else unit


def _detect_format_from(raw: pl.DataFrame, cols: list[str], joiner: str = " ") -> str | None:
    """Sample real values from ``cols`` and pick a strptime format once."""
    frame = raw.select([pl.col(c).cast(pl.Utf8) for c in cols]).drop_nulls().head(50)
    if frame.height == 0:
        return None
    if len(cols) == 1:
        samples = frame.get_column(frame.columns[0]).to_list()
    else:
        samples = [joiner.join(str(v) for v in row) for row in frame.iter_rows()]
    return detect_datetime_format([s.strip() for s in samples if s])


def _epoch_unit_if_epoch(raw: pl.DataFrame, col: str) -> str | None:
    """Return an epoch unit if ``col`` holds integer-like epochs, else None."""
    series = raw.get_column(col)
    if series.dtype.is_integer():
        sample = series.drop_nulls().head(1).to_list()
        return epoch_unit_for(sample[0]) if sample else None
    if series.dtype == pl.Float64:
        return None
    # String column: epoch only if values are pure digits (optionally signed).
    sample = series.cast(pl.Utf8).drop_nulls().head(20).to_list()
    if sample and all(s.strip().lstrip("-").isdigit() for s in sample):
        return epoch_unit_for(int(sample[0]))
    return None
