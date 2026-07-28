"""Correctness tests: every streaming indicator == independent reference at
every bar, plus warmup and no-lookahead invariants."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from qsr.domain.market_data.candle import Candle
from qsr.domain.market_data.timeframe import Timeframe
from qsr.indicators import registry
from qsr.indicators.outputs import ADXValue, BandsValue, MACDValue, SuperTrendValue
from tests import reference as ref

M1 = Timeframe.from_label("M1")
TOL = 1e-9


def _series(n=200, seed=7):
    """Deterministic pseudo-random OHLC walk (no numpy dependency)."""
    start = datetime(2024, 1, 2, tzinfo=timezone.utc)
    candles, O, H, L, C, V = [], [], [], [], [], []
    price = 100.0
    x = seed
    for i in range(n):
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        step = ((x / 0x7FFFFFFF) - 0.5) * 2.0
        o = price
        c = max(1.0, o + step)
        hi = max(o, c) + abs(step) * 0.5 + 0.1
        lo = min(o, c) - abs(step) * 0.5 - 0.1
        vol = 1000 + (x % 500)
        candles.append(Candle(start + timedelta(minutes=i), M1, o, hi, lo, c, float(vol)))
        O.append(o); H.append(hi); L.append(lo); C.append(c); V.append(float(vol))
        price = c
    return candles, O, H, L, C, V


def _stream(name, candles, **params):
    ind = registry.create(name, **params)
    out = []
    for cndl in candles:
        out.append(ind.update(cndl))
    return ind, out


def _first_ready_index(out):
    for i, v in enumerate(out):
        if v is not None:
            return i
    return None


def _assert_scalar(name, ref_vals, params):
    candles, O, H, L, C, V = _series()
    ind, out = _stream(name, candles, **params)
    # warmup matches actual first-ready bar
    assert _first_ready_index(out) == ind.warmup_period - 1, name
    for i in range(len(out)):
        if ref_vals[i] is None:
            assert out[i] is None, f"{name}@{i}: expected None got {out[i]}"
        else:
            assert out[i] == pytest.approx(ref_vals[i], abs=TOL, rel=1e-9), f"{name}@{i}"


def test_sma():
    _, O, H, L, C, V = _series()
    _assert_scalar("sma", ref.sma_ref(C, 14), {"period": 14})


def test_ema():
    _, O, H, L, C, V = _series()
    _assert_scalar("ema", ref.ema_ref(C, 20), {"period": 20})


def test_vwma():
    _, O, H, L, C, V = _series()
    _assert_scalar("vwma", ref.vwma_ref(C, V, 14), {"period": 14})


def test_rsi():
    _, O, H, L, C, V = _series()
    _assert_scalar("rsi", ref.rsi_ref(C, 14), {"period": 14})


def test_atr():
    _, O, H, L, C, V = _series()
    _assert_scalar("atr", ref.atr_ref(H, L, C, 14), {"period": 14})


def test_macd():
    candles, O, H, L, C, V = _series()
    ind, out = _stream("macd", candles, fast=12, slow=26, signal=9)
    r = ref.macd_ref(C, 12, 26, 9)
    assert _first_ready_index(out) == ind.warmup_period - 1
    for i in range(len(out)):
        if r[i][1] is None:
            assert out[i] is None
        else:
            assert isinstance(out[i], MACDValue)
            assert out[i].macd == pytest.approx(r[i][0], abs=TOL)
            assert out[i].signal == pytest.approx(r[i][1], abs=TOL)
            assert out[i].histogram == pytest.approx(r[i][2], abs=TOL)


def test_bollinger():
    candles, O, H, L, C, V = _series()
    ind, out = _stream("bollinger", candles, period=20, k=2.0)
    r = ref.bollinger_ref(C, 20, 2.0)
    for i in range(len(out)):
        if r[i] is None:
            assert out[i] is None
        else:
            assert isinstance(out[i], BandsValue)
            assert out[i].upper == pytest.approx(r[i][0], abs=TOL)
            assert out[i].middle == pytest.approx(r[i][1], abs=TOL)
            assert out[i].lower == pytest.approx(r[i][2], abs=TOL)
            assert out[i].lower <= out[i].middle <= out[i].upper


def test_donchian():
    candles, O, H, L, C, V = _series()
    ind, out = _stream("donchian", candles, period=20)
    r = ref.donchian_ref(H, L, 20)
    for i in range(len(out)):
        if r[i] is None:
            assert out[i] is None
        else:
            assert (out[i].upper, out[i].middle, out[i].lower) == pytest.approx(r[i], abs=TOL)


def test_adx():
    candles, O, H, L, C, V = _series()
    ind, out = _stream("adx", candles, period=14)
    r = ref.adx_ref(H, L, C, 14)
    assert _first_ready_index(out) == ind.warmup_period - 1
    for i in range(len(out)):
        if r[i] is None:
            assert out[i] is None
        else:
            assert isinstance(out[i], ADXValue)
            assert out[i].adx == pytest.approx(r[i][0], abs=1e-7)
            assert out[i].plus_di == pytest.approx(r[i][1], abs=1e-7)
            assert out[i].minus_di == pytest.approx(r[i][2], abs=1e-7)
            assert 0 <= out[i].adx <= 100


def test_supertrend():
    candles, O, H, L, C, V = _series()
    ind, out = _stream("supertrend", candles, period=10, multiplier=3.0)
    r = ref.supertrend_ref(H, L, C, 10, 3.0)
    assert _first_ready_index(out) == ind.warmup_period - 1
    for i in range(len(out)):
        if r[i] is None:
            assert out[i] is None
        else:
            assert isinstance(out[i], SuperTrendValue)
            assert out[i].value == pytest.approx(r[i][0], abs=1e-7)
            assert out[i].direction == r[i][1]
            assert out[i].direction in (-1, 1)


# ---- hand-computed sanity checks (independent of the reference module) -------
def test_sma_hand_value():
    ind = registry.create("sma", period=3)
    vals = [10, 20, 30, 40]
    start = datetime(2024, 1, 2, tzinfo=timezone.utc)
    outs = [ind.update(Candle(start + timedelta(minutes=i), M1, v, v, v, v, 1.0))
            for i, v in enumerate(vals)]
    assert outs[2] == pytest.approx(20.0)   # (10+20+30)/3
    assert outs[3] == pytest.approx(30.0)   # (20+30+40)/3


def test_rsi_all_gains_is_100():
    ind = registry.create("rsi", period=3)
    start = datetime(2024, 1, 2, tzinfo=timezone.utc)
    last = None
    for i, v in enumerate([1, 2, 3, 4, 5, 6]):
        last = ind.update(Candle(start + timedelta(minutes=i), M1, v, v, v, v, 1.0))
    assert last == 100.0  # monotonically rising -> no losses -> RSI 100


def test_no_lookahead_prefix_independence():
    """Value after N bars must equal the value from a fresh run over the first N
    bars — i.e. later bars cannot influence earlier outputs."""
    candles, *_ = _series(120)
    for name in registry.available():
        full_ind, full_out = _stream(name, candles)
        for n in (30, 60, 90):
            _, prefix_out = _stream(name, candles[:n])
            assert prefix_out[n - 1] == full_out[n - 1], f"{name} leaks future @ {n}"
