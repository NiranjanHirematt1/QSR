"""Automatic source-shape detection.

Real broker exports vary wildly: comma / tab / semicolon delimiters, with or
without a header row, ``Open`` vs ``<OPEN>`` (MT5) vs positional columns (MT4),
epoch integers vs ISO strings vs ``YYYY.MM.DD`` dates. This module turns that
variability into a concrete, resolved :class:`ColumnMapping` plus a delimiter and
header flag, so :func:`normalize` can stay format-agnostic.

Everything here is pure/String-level and side-effect free, so it is trivially
unit-testable without touching Polars or the filesystem.
"""
from __future__ import annotations

import re
from datetime import datetime

from .column_mapping import ColumnMapping
from .errors import IngestionError

# --- delimiter sniffing ----------------------------------------------------

_DELIM_CANDIDATES = ("\t", ",", ";", "|", " ")
_DELIM_PREFERENCE = {d: i for i, d in enumerate(_DELIM_CANDIDATES)}


def sniff_delimiter(sample: str) -> str:
    """Detect the column delimiter from a text sample.

    Picks the candidate that appears a *consistent* number of times (>=1) on
    every sampled non-empty line, preferring the one yielding the most columns.
    """
    lines = [ln for ln in sample.splitlines() if ln.strip()][:20]
    if not lines:
        raise IngestionError("File appears to be empty — no data rows found.")

    scores: dict[str, int] = {}
    for d in _DELIM_CANDIDATES:
        counts = [ln.count(d) for ln in lines]
        if min(counts) >= 1 and max(counts) == min(counts):
            scores[d] = counts[0]
    if not scores:
        # Relax consistency: accept the most frequent candidate that appears.
        for d in _DELIM_CANDIDATES:
            total = sum(ln.count(d) for ln in lines)
            if total:
                scores[d] = total // len(lines)
    if not scores:
        raise IngestionError(
            "Could not detect a column delimiter (tried tab, comma, semicolon, "
            "pipe, space). Provide a delimited OHLCV file."
        )
    # Highest column count wins; tie broken by preference order (tab first).
    return max(scores, key=lambda d: (scores[d], -_DELIM_PREFERENCE[d]))


# --- header detection & column mapping -------------------------------------

def _norm(token: str) -> str:
    """Canonicalise a header token: lowercase, drop MT5 ``<>`` and separators."""
    return re.sub(r"[^a-z0-9]", "", token.strip().lower())


# Synonyms keyed by canonical role. Order within a set does not matter.
_SYNONYMS: dict[str, set[str]] = {
    "datetime": {"datetime", "timestamp", "date_time", "datetimeutc", "gmttime",
                 "gmttimestamp", "dt", "opentime", "time"},
    "date": {"date"},
    "time": {"time"},
    "open": {"open", "o"},
    "high": {"high", "h"},
    "low": {"low", "l"},
    "close": {"close", "c", "price", "last", "adjclose"},
    "volume": {"volume", "vol", "v", "tickvol", "tickvolume", "realvolume",
               "qty", "quantity"},
}
# Every token that would mark a row as a header.
_ALL_HEADER_TOKENS = {t for s in _SYNONYMS.values() for t in s}


def _is_floatish(value: str) -> bool:
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def looks_like_header(fields: list[str]) -> bool:
    """True if the first row is column names rather than data.

    A row is a header if it names any known column, or if none of its fields
    parse as a number (a data row always carries numeric OHLC values).
    """
    norms = [_norm(f) for f in fields]
    if any(n in _ALL_HEADER_TOKENS for n in norms):
        return True
    return not any(_is_floatish(f) for f in fields)


def map_named_columns(columns: list[str], hint: ColumnMapping) -> ColumnMapping:
    """Resolve canonical roles against real header names.

    ``hint`` supplies optional user overrides. For each role we honour an
    explicit hint that actually exists in the file, otherwise we auto-match by
    synonym. Raises :class:`IngestionError` when a required OHLC column is
    missing so the API can report exactly which one.
    """
    by_norm: dict[str, str] = {}
    for col in columns:
        by_norm.setdefault(_norm(col), col)

    def resolve(role: str, hinted: str | None, required: bool) -> str | None:
        if hinted and hinted in columns:
            return hinted
        for syn in _SYNONYMS[role]:
            if syn in by_norm:
                return by_norm[syn]
        if required:
            raise IngestionError(
                f"Required '{role}' column not found. Looked for "
                f"{sorted(_SYNONYMS[role])}; file has columns {columns}."
            )
        return None

    date = resolve("date", hint.date, required=False)
    time = resolve("time", hint.time, required=False)
    dt = resolve("datetime", hint.datetime, required=False)
    # Prefer split date+time; else a combined datetime; else date-only.
    if date and time:
        dt = None
    elif dt:
        date = time = None
    elif date:
        time = None
    else:
        raise IngestionError(
            "No timestamp column found. Expected a 'Date'+'Time' pair or a "
            f"single 'Datetime'/'Timestamp' column; file has columns {columns}."
        )

    return ColumnMapping(
        open=resolve("open", hint.open, required=True),
        high=resolve("high", hint.high, required=True),
        low=resolve("low", hint.low, required=True),
        close=resolve("close", hint.close, required=True),
        volume=resolve("volume", hint.volume, required=False) or "",
        datetime=dt, date=date, time=time,
        datetime_format=hint.datetime_format, source_tz=hint.source_tz,
        epoch_unit=hint.epoch_unit,
    )


def positional_mapping(first_row: list[str], hint: ColumnMapping) -> ColumnMapping:
    """Map a *header-less* row positionally (e.g. MT4 exports).

    Leading non-numeric fields are treated as the timestamp (one combined
    ``datetime`` field, or a ``date``+``time`` pair), followed by OHLC and an
    optional volume.
    """
    n = len(first_row)
    lead = 0
    while lead < n and lead < 2 and not _is_floatish(first_row[lead]):
        lead += 1
    if lead == 0:  # first column numeric -> assume a single epoch timestamp
        lead = 1

    cols = [f"column_{i + 1}" for i in range(n)]
    price = cols[lead:]
    if len(price) < 4:
        raise IngestionError(
            f"Header-less file has {n} columns; need a timestamp plus at least "
            "Open/High/Low/Close."
        )
    date = time = dt = None
    if lead == 2:
        date, time = cols[0], cols[1]
    else:
        dt = cols[0]
    volume = price[4] if len(price) >= 5 else ""
    return ColumnMapping(
        open=price[0], high=price[1], low=price[2], close=price[3],
        volume=volume, datetime=dt, date=date, time=time,
        datetime_format=hint.datetime_format, source_tz=hint.source_tz,
        epoch_unit=hint.epoch_unit,
    )


# --- timestamp format detection --------------------------------------------

# Ordered from most to least specific / least ambiguous. ISO and dotted
# (MT4/MT5) formats come before the genuinely ambiguous m/d vs d/m variants.
CANDIDATE_DATETIME_FORMATS: tuple[str, ...] = (
    "%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%d %H:%M:%S%.f",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M",
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
    "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M",
    "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
    "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y",
)


def _py_format(fmt: str) -> str:
    """Translate a Polars/chrono format to a Python strptime one."""
    return fmt.replace("%.f", "%f").replace("T%f", "T").replace(" %f", " ")


def detect_datetime_format(samples: list[str]) -> str | None:
    """Return the first candidate format that parses every sample value.

    ``samples`` should be a handful of non-null timestamp strings. Returns
    ``None`` when nothing matches (caller falls back to Polars inference).
    """
    clean = [s for s in samples if s and s.strip()]
    if not clean:
        return None
    for fmt in CANDIDATE_DATETIME_FORMATS:
        py = _py_format(fmt)
        try:
            for s in clean:
                datetime.strptime(s.strip(), py)
        except (ValueError, TypeError):
            continue
        return fmt
    return None


def epoch_unit_for(value: int) -> str:
    """Infer the epoch time-unit from an integer's magnitude (Polars unit)."""
    v = abs(int(value))
    if v < 10 ** 11:
        return "s"
    if v < 10 ** 14:
        return "ms"
    if v < 10 ** 17:
        return "us"
    return "ns"
