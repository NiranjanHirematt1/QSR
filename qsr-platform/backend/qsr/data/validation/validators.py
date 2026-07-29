"""Concrete validators. Each is independent and side-effect free."""
from __future__ import annotations

import polars as pl

from ..ingestion.schema import CLOSE, HIGH, LOW, OPEN, TS, VOLUME
from .base import ValidationContext
from .report import Issue, IssueCode, Severity

_MAX_SAMPLES = 10


def _samples(df: pl.DataFrame) -> tuple:
    return tuple(df.get_column(TS).drop_nulls().head(_MAX_SAMPLES).to_list())


def _with_valid_ts(df: pl.DataFrame) -> pl.DataFrame:
    """Rows with a parseable timestamp. Null timestamps are reported separately
    by :class:`NullTimestampValidator`; the spacing/order checks must skip them
    so they neither crash nor double-count."""
    return df.filter(pl.col(TS).is_not_null())


class EmptyDatasetValidator:
    def check(self, df: pl.DataFrame, ctx: ValidationContext) -> list[Issue]:
        if df.height == 0:
            return [Issue(IssueCode.EMPTY_DATASET, Severity.ERROR, "Dataset has no rows")]
        return []


class NullTimestampValidator:
    """Flags rows whose timestamp failed to parse (became null).

    ``strptime``/epoch parsing is non-strict so a few bad rows don't abort the
    import, but a null ``open_time`` is meaningless for a time series — most
    often it means the declared ``datetime_format`` did not match the file.
    Reporting it as an ERROR guarantees such data can never silently persist.
    """

    def check(self, df: pl.DataFrame, ctx: ValidationContext) -> list[Issue]:
        nulls = df.get_column(TS).null_count()
        if nulls:
            return [Issue(
                IssueCode.NULL_TIMESTAMP, Severity.ERROR,
                f"{nulls} row(s) have an unparseable timestamp (null open_time). "
                "Check the datetime format / column mapping.",
                nulls,
            )]
        return []


class MonotonicTimestampValidator:
    def check(self, df: pl.DataFrame, ctx: ValidationContext) -> list[Issue]:
        df = _with_valid_ts(df)
        if df.height < 2:
            return []
        ts = df.get_column(TS)
        # After ingestion the frame is sorted; a non-monotonic result means
        # duplicates or reordering slipped through and must be surfaced.
        diffs = ts.diff().dt.total_seconds()
        bad = df.filter(diffs <= 0)
        if bad.height:
            return [Issue(IssueCode.NON_MONOTONIC, Severity.ERROR,
                          f"{bad.height} timestamps are not strictly increasing",
                          bad.height, _samples(bad))]
        return []


class DuplicateTimestampValidator:
    def check(self, df: pl.DataFrame, ctx: ValidationContext) -> list[Issue]:
        df = _with_valid_ts(df)
        dupes = df.filter(df.get_column(TS).is_duplicated())
        if dupes.height:
            uniq = dupes.get_column(TS).unique()
            return [Issue(IssueCode.DUPLICATE_TIMESTAMP, Severity.ERROR,
                          f"{uniq.len()} timestamp(s) appear more than once",
                          dupes.height, tuple(uniq.head(_MAX_SAMPLES).to_list()))]
        return []


class OhlcSanityValidator:
    def check(self, df: pl.DataFrame, ctx: ValidationContext) -> list[Issue]:
        lo, hi = pl.col(LOW), pl.col(HIGH)
        invalid = df.filter(
            (lo > hi)
            | (pl.col(OPEN) < lo) | (pl.col(OPEN) > hi)
            | (pl.col(CLOSE) < lo) | (pl.col(CLOSE) > hi)
            | (pl.col(VOLUME) < 0)
            | pl.any_horizontal(pl.col(OPEN, HIGH, LOW, CLOSE).is_nan())
            | pl.any_horizontal(pl.col(OPEN, HIGH, LOW, CLOSE).is_null())
        )
        if invalid.height:
            return [Issue(IssueCode.INVALID_OHLC, Severity.ERROR,
                          f"{invalid.height} bars violate OHLC constraints",
                          invalid.height, _samples(invalid))]
        return []


class TimeframeConsistencyValidator:
    """Infers the modal bar spacing and flags a mismatch with the declared
    timeframe. Uses the mode so occasional session gaps don't cause false
    positives."""

    def check(self, df: pl.DataFrame, ctx: ValidationContext) -> list[Issue]:
        df = _with_valid_ts(df)
        if df.height < 3:
            return []
        deltas = df.get_column(TS).diff().dt.total_seconds().drop_nulls()
        modal = int(deltas.mode().min())  # smallest of the modal spacings
        declared = ctx.declared_timeframe.seconds
        if modal != declared:
            return [Issue(IssueCode.WRONG_TIMEFRAME, Severity.WARN,
                          f"Inferred spacing {modal}s != declared "
                          f"{declared}s ({ctx.declared_timeframe.label})")]
        return []


class MissingCandleValidator:
    """Flags in-session gaps. A gap is only reported when the *entire* expected
    interval between two consecutive bars is inside trading hours, so weekend /
    maintenance closures are not mistaken for missing data."""

    def check(self, df: pl.DataFrame, ctx: ValidationContext) -> list[Issue]:
        df = _with_valid_ts(df)
        if df.height < 2:
            return []
        step = ctx.declared_timeframe.seconds
        ts = df.get_column(TS).to_list()
        missing: list = []
        for prev, cur in zip(ts, ts[1:]):
            gap = int((cur - prev).total_seconds())
            if gap <= step:
                continue
            # Walk the expected grid; count only slots that are in-session.
            expected = prev
            for _ in range(gap // step - 1):
                expected = expected.__class__.fromtimestamp(
                    expected.timestamp() + step, tz=expected.tzinfo)
                if ctx.calendar.is_open(expected):
                    missing.append(expected)
        if missing:
            return [Issue(IssueCode.MISSING_CANDLES, Severity.WARN,
                          f"{len(missing)} in-session candle(s) missing",
                          len(missing), tuple(missing[:_MAX_SAMPLES]))]
        return []
