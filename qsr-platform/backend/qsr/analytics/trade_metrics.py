"""Trade-ledger metrics — computed purely from a sequence of closed trades."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from ..domain.orders.trade import Trade


@dataclass(frozen=True, slots=True)
class TradeMetrics:
    count: int
    wins: int
    losses: int
    net_profit: float
    gross_profit: float
    gross_loss: float          # <= 0
    win_rate: float            # 0..1
    profit_factor: float | None  # None when there are no losing trades
    avg_win: float | None
    avg_loss: float | None
    largest_win: float | None
    largest_loss: float | None
    expectancy: float          # mean PnL per trade
    avg_r: float | None
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_holding_seconds: float | None

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


def _max_streak(flags: list[bool], value: bool) -> int:
    best = cur = 0
    for f in flags:
        if f is value:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def compute_trade_metrics(trades: Sequence[Trade]) -> TradeMetrics:
    n = len(trades)
    if n == 0:
        return TradeMetrics(0, 0, 0, 0.0, 0.0, 0.0, 0.0, None, None, None, None, None,
                            0.0, None, 0, 0, None)

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    rs = [t.r_multiple for t in trades if t.r_multiple is not None]
    win_flags = [t.is_win for t in trades]

    return TradeMetrics(
        count=n,
        wins=len(wins),
        losses=len(losses),
        net_profit=sum(pnls),
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        win_rate=len(wins) / n,
        profit_factor=(gross_profit / abs(gross_loss)) if gross_loss != 0 else None,
        avg_win=fmean(wins) if wins else None,
        avg_loss=fmean(losses) if losses else None,
        largest_win=max(pnls) if wins else None,
        largest_loss=min(pnls) if losses else None,
        expectancy=fmean(pnls),
        avg_r=fmean(rs) if rs else None,
        max_consecutive_wins=_max_streak(win_flags, True),
        max_consecutive_losses=_max_streak(win_flags, False),
        avg_holding_seconds=fmean([t.duration_seconds for t in trades]),
    )


def pnl_distribution(trades: Sequence[Trade], bins: int = 10) -> list[dict]:
    """Histogram of trade PnL into ``bins`` equal-width buckets."""
    if not trades:
        return []
    pnls = [t.pnl for t in trades]
    lo, hi = min(pnls), max(pnls)
    if lo == hi:
        return [{"low": lo, "high": hi, "count": len(pnls)}]
    width = (hi - lo) / bins
    counts = [0] * bins
    for p in pnls:
        idx = min(int((p - lo) / width), bins - 1)
        counts[idx] += 1
    return [{"low": lo + i * width, "high": lo + (i + 1) * width, "count": c}
            for i, c in enumerate(counts)]
