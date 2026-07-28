import pytest

from qsr.domain.instruments.catalog import es_future, eurusd


def test_es_point_value_and_pnl():
    es = es_future().spec
    # tick 0.25 worth $12.50 -> a 1.0 point move = $50 per contract.
    assert es.point_value == 50.0
    # long 2 contracts, +4 points => 2 * 4 * 50 = $400
    assert es.price_to_cash(price_delta=4.0, qty=2) == 400.0


def test_eurusd_pnl():
    fx = eurusd().spec
    # 100k lot, point_value = tick_value/tick_size = 1/0.00001 = 100000
    # (float representation of 1e-5 makes this exact only to tolerance)
    assert fx.point_value == pytest.approx(100_000)
    # +0.0010 (10 pips) on 1 lot => 100 USD
    assert round(fx.price_to_cash(0.0010, 1), 6) == 100.0


def test_round_to_tick():
    es = es_future().spec
    assert es.round_to_tick(4001.11) == 4001.0
    assert es.round_to_tick(4001.13) == 4001.25
