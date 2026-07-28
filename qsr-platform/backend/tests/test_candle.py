from datetime import datetime, timezone

import pytest

from qsr.domain.market_data.candle import Candle
from qsr.domain.market_data.timeframe import Timeframe


def _c(o, h, low, c):
    return Candle(datetime(2024, 1, 2, tzinfo=timezone.utc), Timeframe.from_label("M1"), o, h, low, c, 1.0)


def test_valid_candle():
    assert _c(10, 11, 9, 10.5).close_time.minute == 1


@pytest.mark.parametrize("args", [(10, 9, 9, 10), (10, 11, 9, 12), (10, 11, 10.5, 9)])
def test_invalid_ohlc_rejected(args):
    with pytest.raises(ValueError):
        _c(*args)
