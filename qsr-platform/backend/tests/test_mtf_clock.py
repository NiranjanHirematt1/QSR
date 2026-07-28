from datetime import datetime, timedelta, timezone

from qsr.domain.instruments.session_calendar import ContinuousCalendar
from qsr.domain.market_data.timeframe import Timeframe
from qsr.engine.clock.multi_timeframe_clock import MultiTimeframeClock
from tests.engine_helpers import M5

M15 = Timeframe.from_label("M15")
H1 = Timeframe.from_label("H1")


def _m5(start_min, o, h, l, c):
    ts = datetime(2024, 1, 2, 14, start_min, tzinfo=timezone.utc)
    from qsr.domain.market_data.candle import Candle
    return Candle(ts, M5, o, h, l, c, 100.0)


def test_m5_to_m15_aggregation_and_delay():
    clock = MultiTimeframeClock(M5, (M15,), ContinuousCalendar())
    bars = [_m5(0, 10, 12, 9, 11), _m5(5, 11, 15, 10, 14), _m5(10, 14, 16, 8, 9),
            _m5(15, 9, 9, 9, 9)]  # 4th bar opens the next M15 bucket
    emitted = []
    for b in bars:
        emitted.extend(clock.advance(b))
    # The first M15 bar (14:00-14:15) is emitted only when the 14:15 bar arrives.
    assert len(emitted) == 1
    tf, bar15 = emitted[0]
    assert tf == M15
    assert bar15.open == 10 and bar15.high == 16 and bar15.low == 8 and bar15.close == 9
    assert bar15.open_time == datetime(2024, 1, 2, 14, 0, tzinfo=timezone.utc)


def test_no_higher_bar_emitted_within_open_bucket():
    clock = MultiTimeframeClock(M5, (M15,), ContinuousCalendar())
    assert clock.advance(_m5(0, 1, 2, 0.5, 1.5)) == []   # bucket forming
    assert clock.advance(_m5(5, 1, 2, 0.5, 1.5)) == []   # still forming
    assert clock.advance(_m5(10, 1, 2, 0.5, 1.5)) == []  # still forming (closes at :15)


def test_rejects_non_multiple_timeframe():
    import pytest
    with pytest.raises(ValueError):
        MultiTimeframeClock(M5, (Timeframe(7 * 60),), ContinuousCalendar())
