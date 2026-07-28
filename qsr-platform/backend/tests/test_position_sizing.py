from qsr.domain.instruments.catalog import es_future, eurusd
from qsr.domain.orders.intents import Side, SizeKind, SizeSpec
from qsr.engine.portfolio.position import Position
from qsr.engine.portfolio.sizing import StandardSizer


def test_fixed_qty():
    s = StandardSizer()
    q = s.resolve(SizeSpec(SizeKind.FIXED_QTY, 3), price=4000, equity=1e5,
                  contract=es_future().spec, stop_distance=None)
    assert q == 3


def test_risk_percent_sizing():
    # ES point_value=50. Risk 1% of 100k = $1000. Stop distance 10 points -> risk/pt=500 -> 2 contracts.
    s = StandardSizer()
    q = s.resolve(SizeSpec(SizeKind.RISK_PERCENT, 1.0), price=4000, equity=100_000,
                  contract=es_future().spec, stop_distance=10.0)
    assert q == 2  # 1000 / (10 * 50)


def test_risk_percent_requires_stop():
    import pytest
    s = StandardSizer()
    with pytest.raises(ValueError):
        s.resolve(SizeSpec(SizeKind.RISK_PERCENT, 1.0), price=4000, equity=1e5,
                  contract=es_future().spec, stop_distance=None)


def test_fixed_cash_sizing():
    # notional per FX lot = price*point_value = 1.10 * 100000 = 110000; cash 220000 -> 2 lots
    s = StandardSizer()
    q = s.resolve(SizeSpec(SizeKind.FIXED_CASH, 220_000), price=1.10, equity=1e6,
                  contract=eurusd().spec, stop_distance=None)
    assert round(q, 2) == 2.0


def test_position_pnl_long_and_short():
    spec = es_future().spec
    p = Position(spec)
    p.apply_fill(Side.BUY, 4000, 2)           # long 2 @ 4000
    assert p.qty == 2 and p.avg_price == 4000
    assert p.unrealized(4010) == 2 * 10 * 50  # +$1000
    realized = p.apply_fill(Side.SELL, 4010, 2)  # close
    assert realized == 1000.0 and p.qty == 0


def test_position_reversal():
    spec = es_future().spec
    p = Position(spec)
    p.apply_fill(Side.BUY, 100, 1)
    realized = p.apply_fill(Side.SELL, 110, 3)  # close 1 (+? ) then open short 2
    assert realized == (110 - 100) * 50 * 1     # only the closed unit realizes
    assert p.qty == -2 and p.avg_price == 110
