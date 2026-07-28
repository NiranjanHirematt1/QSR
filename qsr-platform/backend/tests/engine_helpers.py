"""Shared builders for engine tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from qsr.domain.market_data.candle import Candle
from qsr.domain.market_data.timeframe import Timeframe

M5 = Timeframe.from_label("M5")
M1 = Timeframe.from_label("M1")


def bar(ts, o, h, l, c, v=1000.0, tf=M5):
    return Candle(ts, tf, o, h, l, c, v)


def series(specs, start=None, tf=M5):
    """specs: list of (o,h,l,c) or (o,h,l,c,v); returns candles at tf spacing."""
    start = start or datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
    out = []
    for i, s in enumerate(specs):
        o, h, l, c = s[:4]
        v = s[4] if len(s) > 4 else 1000.0
        out.append(Candle(start + i * tf.delta, tf, o, h, l, c, v))
    return out
