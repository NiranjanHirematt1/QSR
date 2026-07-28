from datetime import datetime, timezone

from qsr.engine.execution.fill_model import (
    ExitReason,
    IntrabarAssumption,
    resolve_exit,
)
from tests.engine_helpers import bar

TS = datetime(2024, 1, 2, tzinfo=timezone.utc)


def _b(o, h, l, c):
    return bar(TS, o, h, l, c)


def test_long_stop_only():
    r = resolve_exit(True, _b(100, 101, 94, 96), stop=95, target=110,
                     assumption=IntrabarAssumption.PESSIMISTIC)
    assert r == (95, ExitReason.STOP)


def test_long_target_only():
    r = resolve_exit(True, _b(100, 111, 99, 108), stop=90, target=110,
                     assumption=IntrabarAssumption.PESSIMISTIC)
    assert r == (110, ExitReason.TARGET)


def test_both_hit_pessimistic_takes_stop():
    r = resolve_exit(True, _b(100, 111, 94, 100), stop=95, target=110,
                     assumption=IntrabarAssumption.PESSIMISTIC)
    assert r[1] is ExitReason.STOP


def test_both_hit_optimistic_takes_target():
    r = resolve_exit(True, _b(100, 111, 94, 100), stop=95, target=110,
                     assumption=IntrabarAssumption.OPTIMISTIC)
    assert r[1] is ExitReason.TARGET


def test_ohlc_path_up_bar_takes_target_for_long():
    # up bar (close>open) travels O->H->L->C, so the high-side target is first.
    r = resolve_exit(True, _b(100, 111, 94, 108), stop=95, target=110,
                     assumption=IntrabarAssumption.OHLC_PATH)
    assert r[1] is ExitReason.TARGET


def test_ohlc_path_down_bar_takes_stop_for_long():
    r = resolve_exit(True, _b(100, 111, 94, 96), stop=95, target=110,
                     assumption=IntrabarAssumption.OHLC_PATH)
    assert r[1] is ExitReason.STOP


def test_gap_down_through_stop_fills_at_open():
    # open gaps below the stop -> filled at open (worse than the stop price)
    r = resolve_exit(True, _b(90, 92, 88, 91), stop=95, target=110,
                     assumption=IntrabarAssumption.OPTIMISTIC)
    assert r == (90, ExitReason.STOP)  # open precedence beats optimistic


def test_short_stop_above():
    r = resolve_exit(False, _b(100, 106, 99, 104), stop=105, target=90,
                     assumption=IntrabarAssumption.PESSIMISTIC)
    assert r == (105, ExitReason.STOP)


def test_no_exit_when_untouched():
    assert resolve_exit(True, _b(100, 101, 99, 100), stop=95, target=110,
                        assumption=IntrabarAssumption.PESSIMISTIC) is None
