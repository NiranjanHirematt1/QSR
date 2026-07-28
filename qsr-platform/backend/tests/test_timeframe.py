from datetime import datetime, timezone

import pytest

from qsr.domain.market_data.timeframe import Timeframe


@pytest.mark.parametrize("label,secs", [("M1", 60), ("M5", 300), ("H1", 3600), ("D1", 86400)])
def test_from_label(label, secs):
    assert Timeframe.from_label(label).seconds == secs


def test_label_roundtrip():
    assert Timeframe.from_label("H4").label == "H4"


def test_is_multiple_of():
    assert Timeframe.from_label("H1").is_multiple_of(Timeframe.from_label("M5"))
    assert not Timeframe.from_label("H1").is_multiple_of(Timeframe(7 * 60))


def test_floor_anchors_to_epoch():
    tf = Timeframe.from_label("H1")
    ts = datetime(2024, 1, 2, 9, 37, 12, tzinfo=timezone.utc)
    assert tf.floor(ts) == datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)


def test_rejects_naive_datetime():
    with pytest.raises(ValueError):
        Timeframe.from_label("H1").floor(datetime(2024, 1, 2, 9, 0))
