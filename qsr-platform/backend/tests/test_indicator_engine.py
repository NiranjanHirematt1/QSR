"""Integration tests for the registry and the de-duplicating IndicatorEngine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from qsr.domain.market_data.candle import Candle
from qsr.domain.market_data.timeframe import Timeframe
from qsr.indicators import registry
from qsr.indicators.engine import IndicatorEngine

M1 = Timeframe.from_label("M1")


def _candles(n=60):
    start = datetime(2024, 1, 2, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        p = 100 + (i % 7)
        out.append(Candle(start + timedelta(minutes=i), M1, p, p + 1, p - 1, p + 0.5, 1000.0 + i))
    return out


# ---- registry -----------------------------------------------------------
def test_registry_discovers_all_ten():
    assert set(registry.available()) == {
        "sma", "ema", "vwma", "rsi", "macd", "atr", "adx", "supertrend",
        "bollinger", "donchian",
    }


def test_registry_unknown_name_raises():
    with pytest.raises(KeyError):
        registry.create("does_not_exist")


def test_discover_is_idempotent():
    a = registry.available()
    registry.discover()
    assert registry.available() == a


def test_duplicate_name_rejected():
    from qsr.indicators.base import Indicator

    with pytest.raises(ValueError):
        class _Dupe(Indicator):
            name = "sma"  # collides with the real SMA

            @property
            def warmup_period(self) -> int:
                return 1

            def _on_bar(self, candle):
                return None


# ---- engine de-duplication ----------------------------------------------
def test_identical_requests_share_instance():
    eng = IndicatorEngine()
    h1 = eng.request("ema", "H1", period=200)
    h2 = eng.request("ema", "H1", period=200)
    assert eng.instance(h1) is eng.instance(h2)
    assert eng.instance_count == 1


def test_param_and_stream_variants_are_distinct():
    eng = IndicatorEngine()
    eng.request("ema", "H1", period=200)
    eng.request("ema", "H1", period=50)     # different params
    eng.request("ema", "M5", period=200)    # different stream
    assert eng.instance_count == 3


def test_param_order_does_not_matter():
    eng = IndicatorEngine()
    a = eng.request("bollinger", "H1", period=20, k=2.0)
    b = eng.request("bollinger", "H1", k=2.0, period=20)
    assert eng.instance(a) is eng.instance(b)
    assert eng.instance_count == 1


def test_engine_feeds_each_stream_once_and_values_update():
    eng = IndicatorEngine()
    sma = eng.request("sma", "M1", period=5)
    other = eng.request("sma", "M5", period=5)  # different stream, must stay empty
    for c in _candles(20):
        eng.on_bar("M1", c)
    assert sma.is_ready
    assert sma.value is not None
    assert not other.is_ready  # never received bars


def test_shared_instance_computed_once():
    """Two handles to the same indicator reflect one shared computation."""
    eng = IndicatorEngine()
    h1 = eng.request("rsi", "M1", period=14)
    h2 = eng.request("rsi", "M1", period=14)
    for c in _candles(40):
        eng.on_bar("M1", c)
    assert h1.value == h2.value
    assert eng.instance_count == 1
    assert eng.streams() == ("M1",)
