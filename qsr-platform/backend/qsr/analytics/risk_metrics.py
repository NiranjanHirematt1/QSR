"""Equity-curve (risk) metrics: drawdown, Sharpe, Sortino, Calmar, recovery,
monthly returns. Input is a chronological sequence of (timestamp, equity)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from statistics import fmean, pstdev
from typing import Sequence

EquitySeries = Sequence[tuple[datetime, float]]


@dataclass(frozen=True, slots=True)
class DrawdownPoint:
    timestamp: datetime
    equity: float
    peak: float
    drawdown_pct: float   # <= 0
    drawdown_abs: float   # <= 0


@dataclass(frozen=True, slots=True)
class RiskMetrics:
    start_equity: float
    end_equity: float
    total_return_pct: float
    cagr_pct: float | None
    max_drawdown_pct: float      # >= 0 (magnitude)
    max_drawdown_abs: float      # >= 0
    recovery_factor: float | None
    sharpe: float | None
    sortino: float | None
    calmar: float | None

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


def drawdown_curve(equity: EquitySeries) -> list[DrawdownPoint]:
    out: list[DrawdownPoint] = []
    peak = -float("inf")
    for ts, eq in equity:
        peak = max(peak, eq)
        dd_abs = eq - peak
        dd_pct = (eq / peak - 1.0) if peak > 0 else 0.0
        out.append(DrawdownPoint(ts, eq, peak, dd_pct, dd_abs))
    return out


def period_returns(equity: EquitySeries) -> list[float]:
    """Simple per-step returns between consecutive equity samples."""
    vals = [e for _, e in equity]
    out = []
    for prev, cur in zip(vals, vals[1:]):
        out.append((cur / prev - 1.0) if prev != 0 else 0.0)
    return out


def sharpe_ratio(returns: Sequence[float], periods_per_year: float,
                 risk_free: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    excess = [r - risk_free / periods_per_year for r in returns]
    sd = pstdev(excess)
    if sd == 0:
        return None
    return (fmean(excess) / sd) * sqrt(periods_per_year)


def sortino_ratio(returns: Sequence[float], periods_per_year: float,
                  target: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    downside = [min(r - target, 0.0) for r in returns]
    dd = sqrt(fmean([d * d for d in downside]))
    if dd == 0:
        return None
    return (fmean(returns) - target) / dd * sqrt(periods_per_year)


def monthly_returns(equity: EquitySeries) -> dict[str, float]:
    """Month-over-month return using each month's last equity value."""
    if not equity:
        return {}
    month_end: dict[str, float] = {}
    for ts, eq in equity:
        month_end[f"{ts.year:04d}-{ts.month:02d}"] = eq  # last write wins (chronological)
    keys = sorted(month_end)
    out: dict[str, float] = {}
    prev = equity[0][1]
    for k in keys:
        cur = month_end[k]
        out[k] = (cur / prev - 1.0) if prev != 0 else 0.0
        prev = cur
    return out


def compute_risk_metrics(equity: EquitySeries, net_profit: float,
                         periods_per_year: float) -> RiskMetrics:
    if len(equity) < 2:
        start = equity[0][1] if equity else 0.0
        return RiskMetrics(start, start, 0.0, None, 0.0, 0.0, None, None, None, None)

    start_eq = equity[0][1]
    end_eq = equity[-1][1]
    total_return = (end_eq / start_eq - 1.0) if start_eq != 0 else 0.0

    dd = drawdown_curve(equity)
    max_dd_pct = -min(p.drawdown_pct for p in dd)   # magnitude
    max_dd_abs = -min(p.drawdown_abs for p in dd)

    rets = period_returns(equity)
    n = len(rets)
    cagr = ((1.0 + total_return) ** (periods_per_year / n) - 1.0) if n > 0 and start_eq > 0 and (1.0 + total_return) > 0 else None
    recovery = (net_profit / max_dd_abs) if max_dd_abs > 0 else None
    calmar = (cagr / max_dd_pct) if (cagr is not None and max_dd_pct > 0) else None

    return RiskMetrics(
        start_equity=start_eq,
        end_equity=end_eq,
        total_return_pct=total_return * 100.0,
        cagr_pct=(cagr * 100.0) if cagr is not None else None,
        max_drawdown_pct=max_dd_pct * 100.0,
        max_drawdown_abs=max_dd_abs,
        recovery_factor=recovery,
        sharpe=sharpe_ratio(rets, periods_per_year),
        sortino=sortino_ratio(rets, periods_per_year),
        calmar=calmar,
    )
