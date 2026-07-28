"""Average Directional Index (Wilder), with +DI / -DI.

Directional movement:
    up_move   = high - prev_high
    down_move = prev_low - low
    +DM = up_move   if up_move > down_move and up_move > 0 else 0
    -DM = down_move if down_move > up_move and down_move > 0 else 0
+DM, -DM and True Range are Wilder-smoothed; then
    +DI = 100 * smooth(+DM) / smooth(TR)
    -DI = 100 * smooth(-DM) / smooth(TR)
    DX  = 100 * |+DI - -DI| / (+DI + -DI)
    ADX = Wilder-smoothed DX
"""
from __future__ import annotations

from ...domain.market_data.candle import Candle
from ..base import Indicator
from ..outputs import ADXValue
from ._smoothing import WilderMA
from .atr import true_range


class ADX(Indicator):
    name = "adx"

    def __init__(self, period: int = 14) -> None:
        super().__init__(period=period)
        self._period = int(period)
        self._sm_pdm = WilderMA(self._period)
        self._sm_mdm = WilderMA(self._period)
        self._sm_tr = WilderMA(self._period)
        self._adx = WilderMA(self._period)
        self._ph: float | None = None
        self._pl: float | None = None
        self._pc: float | None = None

    @property
    def warmup_period(self) -> int:
        return 2 * self._period

    def _on_bar(self, candle: Candle) -> ADXValue | None:
        h, l, c = candle.high, candle.low, candle.close
        if self._ph is None:
            self._ph, self._pl, self._pc = h, l, c
            return None

        up_move = h - self._ph
        down_move = self._pl - l
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        tr = true_range(h, l, self._pc)
        self._ph, self._pl, self._pc = h, l, c

        sm_pdm = self._sm_pdm.update(plus_dm)
        sm_mdm = self._sm_mdm.update(minus_dm)
        sm_tr = self._sm_tr.update(tr)
        if sm_pdm is None or sm_mdm is None or sm_tr is None or sm_tr == 0.0:
            return None

        plus_di = 100.0 * sm_pdm / sm_tr
        minus_di = 100.0 * sm_mdm / sm_tr
        di_sum = plus_di + minus_di
        dx = 0.0 if di_sum == 0 else 100.0 * abs(plus_di - minus_di) / di_sum

        adx = self._adx.update(dx)
        if adx is None:
            return None
        return ADXValue(adx=adx, plus_di=plus_di, minus_di=minus_di)
