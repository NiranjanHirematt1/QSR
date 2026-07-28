from datetime import datetime, timedelta, timezone

from qsr.data.ingestion.schema import CLOSE, HIGH, LOW, OPEN, TS, VOLUME
from qsr.data.resampling.resampler import Resampler
from qsr.domain.market_data.timeframe import Timeframe
from tests.conftest import make_frame

M1 = Timeframe.from_label("M1")
M5 = Timeframe.from_label("M5")


def _series():
    start = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(10):  # 10 x M1 -> 2 x M5
        o = 100 + i
        rows.append((start + timedelta(minutes=i), o, o + 2, o - 2, o + 0.5, 100 + i))
    return make_frame(rows)


def test_m1_to_m5_aggregation():
    out = Resampler().resample(_series(), M1, M5).sort(TS)
    assert out.height == 2
    first = out.row(0, named=True)
    # first M5 bar aggregates minutes 0..4 (o=100..104)
    assert first[OPEN] == 100.0            # first open
    assert first[CLOSE] == 104.5           # last close of the window
    assert first[HIGH] == 106.0            # max high (104+2)
    assert first[LOW] == 98.0              # min low  (100-2)
    assert first[VOLUME] == sum(range(100, 105))


def test_no_lookahead_close_time_within_window():
    """A derived bar must never incorporate data past its own close_time."""
    out = Resampler().resample(_series(), M1, M5).sort(TS)
    open_time = out.row(0, named=True)[TS]
    # The M5 bar opening 09:00 closes 09:05; its close must equal the M1 close
    # at 09:04 (last bar strictly before close_time) — not anything at/after.
    assert out.row(0, named=True)[CLOSE] == 104.5
    assert open_time == datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
