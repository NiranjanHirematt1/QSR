"""Configurable mapping from arbitrary source columns to the canonical schema.

Real CSVs vary wildly: a combined ``Datetime`` column, or split ``Date`` +
``Time``; epoch seconds/millis or ISO strings; capitalised headers; a source
timezone that is not UTC. All of that variability is captured *declaratively*
here so the readers stay simple and nothing is hardcoded.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColumnMapping:
    """Declarative description of how to read a particular source file.

    Provide either ``datetime`` (a single combined column) OR both ``date`` and
    ``time``. ``source_tz`` names the timezone the source timestamps are in;
    ingestion converts everything to UTC. ``datetime_format`` is an optional
    strptime pattern (omit to let ingestion auto-detect ISO/dotted/epoch).

    All fields are optional. Any left unset are resolved automatically by the
    reader from the file's header (or positionally for header-less files); the
    values here act as *hints* / overrides when auto-detection is not desired.
    Column names supplied for ``open``/``high``/... are used only if they exist
    in the file, otherwise the reader falls back to synonym auto-matching.
    """

    open: str = "Open"
    high: str = "High"
    low: str = "Low"
    close: str = "Close"
    volume: str = "Volume"
    datetime: str | None = None
    date: str | None = None
    time: str | None = None
    datetime_format: str | None = None
    source_tz: str = "UTC"
    epoch_unit: str | None = None  # one of None|"s"|"ms"|"us"|"ns" for epoch timestamps
