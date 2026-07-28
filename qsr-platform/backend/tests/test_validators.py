from datetime import datetime, timedelta, timezone

from qsr.data.validation.base import ValidationContext
from qsr.data.validation.pipeline import ValidationPipeline
from qsr.data.validation.report import IssueCode
from qsr.data.validation.validators import (
    DuplicateTimestampValidator,
    MissingCandleValidator,
    OhlcSanityValidator,
    TimeframeConsistencyValidator,
)
from qsr.domain.instruments.session_calendar import ForexWeekendCalendar
from qsr.domain.market_data.timeframe import Timeframe
from tests.conftest import make_frame

M1 = Timeframe.from_label("M1")
CTX = ValidationContext(M1, ForexWeekendCalendar())


def _utc(h, mi):
    return datetime(2024, 1, 2, h, mi, tzinfo=timezone.utc)


def test_clean_data_has_no_issues(clean_m1):
    report = ValidationPipeline().run(clean_m1, CTX)
    assert report.is_clean, report.to_dict()


def test_detects_duplicates():
    df = make_frame([(_utc(9, 0), 1, 2, 0.5, 1.5, 10),
                     (_utc(9, 0), 1, 2, 0.5, 1.5, 10),
                     (_utc(9, 1), 1, 2, 0.5, 1.5, 10)])
    issues = DuplicateTimestampValidator().check(df, CTX)
    assert issues and issues[0].code is IssueCode.DUPLICATE_TIMESTAMP


def test_detects_invalid_ohlc():
    # low(3) > high(2) is impossible; build frame without Candle validation.
    df = make_frame([(_utc(9, 0), 1, 2, 3, 1.5, 10)])
    issues = OhlcSanityValidator().check(df, CTX)
    assert issues and issues[0].code is IssueCode.INVALID_OHLC


def test_detects_wrong_timeframe():
    # 5-minute spacing declared as M1.
    df = make_frame([(_utc(9, 0), 1, 2, 0.5, 1.5, 10),
                     (_utc(9, 5), 1, 2, 0.5, 1.5, 10),
                     (_utc(9, 10), 1, 2, 0.5, 1.5, 10)])
    issues = TimeframeConsistencyValidator().check(df, CTX)
    assert issues and issues[0].code is IssueCode.WRONG_TIMEFRAME


def test_missing_in_session_candle_flagged():
    # 9:00, 9:01, then jump to 9:05 -> 3 missing in-session bars (9:02,9:03,9:04)
    df = make_frame([(_utc(9, 0), 1, 2, 0.5, 1.5, 10),
                     (_utc(9, 1), 1, 2, 0.5, 1.5, 10),
                     (_utc(9, 5), 1, 2, 0.5, 1.5, 10)])
    issues = MissingCandleValidator().check(df, CTX)
    assert issues and issues[0].count == 3


def test_weekend_gap_not_flagged_as_missing():
    # Fri 21:59 close -> Sun 22:00 reopen (the correct first bar). The weekend
    # closure is expected, so nothing in-session is missing.
    fri = datetime(2024, 1, 5, 21, 59, tzinfo=timezone.utc)
    sun = datetime(2024, 1, 7, 22, 0, tzinfo=timezone.utc)
    df = make_frame([(fri, 1, 2, 0.5, 1.5, 10), (sun, 1, 2, 0.5, 1.5, 10)])
    issues = MissingCandleValidator().check(df, CTX)
    assert issues == []
