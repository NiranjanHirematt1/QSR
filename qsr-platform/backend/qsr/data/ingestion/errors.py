"""Ingestion-layer errors.

These are raised for problems that make a source file *unreadable* — a missing
required column, an undetectable delimiter, an empty file. They carry a
human-readable message so the API can turn them into an informative ``400``
instead of leaking an opaque ``ColumnNotFoundError`` as a ``500``.

Data-*quality* problems (gaps, duplicates, bad OHLC) are **not** errors here;
those flow through the validation pipeline as :class:`Issue` objects so the
importer can report them without aborting.
"""
from __future__ import annotations


class IngestionError(ValueError):
    """A source file cannot be read into the canonical schema."""
