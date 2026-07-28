"""Timeframe resampling — the single home of OHLCV aggregation.

The canonical base timeframe (finest imported resolution) is the one source of
truth; every higher timeframe is *derived* here. Centralising the rule
guarantees M5 and H1 can never disagree.

Aggregation rule for a target bar spanning ``[t, t + tf)``:
    open   = first base open in the window
    high   = max base high
    low    = min base low
    close  = last base close
    volume = sum base volume

For sub-daily targets, bars are anchored to the Unix epoch. For daily and above,
bars are anchored to the instrument's *session day start* so a futures "day"
breaks at the right boundary rather than at 00:00 UTC.
"""
from __future__ import annotations

import polars as pl

from ...domain.instruments.session_calendar import SessionCalendar
from ...domain.market_data.timeframe import Timeframe
from ..ingestion.schema import CLOSE, HIGH, LOW, OPEN, TS, VOLUME

_ONE_DAY = 86400


class Resampler:
    """Aggregates a canonical (base-timeframe) frame to a higher timeframe."""

    def resample(
        self,
        df: pl.DataFrame,
        base: Timeframe,
        target: Timeframe,
        calendar: SessionCalendar | None = None,
    ) -> pl.DataFrame:
        if target.seconds == base.seconds:
            return df
        if not target.is_multiple_of(base):
            raise ValueError(
                f"Target {target.label} is not an integer multiple of base {base.label}"
            )

        df = df.sort(TS)
        bucket = self._bucket_expr(target, calendar)

        out = (
            df.with_columns(bucket.alias("_bucket"))
            .group_by("_bucket", maintain_order=True)
            .agg(
                pl.col(OPEN).first().alias(OPEN),
                pl.col(HIGH).max().alias(HIGH),
                pl.col(LOW).min().alias(LOW),
                pl.col(CLOSE).last().alias(CLOSE),
                pl.col(VOLUME).sum().alias(VOLUME),
            )
            .rename({"_bucket": TS})
            .sort(TS)
        )
        return out.select(TS, OPEN, HIGH, LOW, CLOSE, VOLUME)

    def _bucket_expr(self, target: Timeframe, calendar: SessionCalendar | None) -> pl.Expr:
        if target.seconds < _ONE_DAY or calendar is None:
            # Epoch-anchored truncation.
            return pl.col(TS).dt.truncate(f"{target.seconds}s")
        # Session-anchored daily+: shift each ts back to its session-day start,
        # truncate at day granularity, aligning to the calendar's day anchor.
        return pl.col(TS).map_elements(
            lambda ts: calendar.session_day_start(ts),
            return_dtype=pl.Datetime(time_unit="us", time_zone="UTC"),
        )
