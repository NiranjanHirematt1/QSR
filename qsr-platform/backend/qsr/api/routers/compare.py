"""Strategy comparison (Module 8): combine two persisted runs into one payload."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import backtest_repo

router = APIRouter(prefix="/compare", tags=["compare"])


class CompareRequest(BaseModel):
    run_ids: list[str]


_METRIC_KEYS = ("net_profit", "win_rate", "profit_factor", "expectancy",
                "max_drawdown_pct", "sharpe", "sortino", "calmar")


def _one(run_id: str) -> dict:
    rec = backtest_repo().get(run_id)
    if rec is None:
        raise HTTPException(404, f"backtest {run_id} not found")
    payload = json.loads(rec.result_json)
    perf = payload["performance"]
    flat = {**perf["trades"], **perf["risk"]}
    return {
        "run_id": rec.run_id,
        "strategy_id": rec.strategy_id,
        "instrument": rec.instrument,
        "trade_count": rec.trade_count,
        "metrics": {k: flat.get(k) for k in _METRIC_KEYS},
        "equity_curve": payload["equity_curve"],
    }


@router.post("")
def compare(req: CompareRequest) -> dict:
    if len(req.run_ids) < 2:
        raise HTTPException(400, "provide at least two run_ids to compare")
    runs = [_one(rid) for rid in req.run_ids]
    return {"runs": runs, "metric_keys": list(_METRIC_KEYS)}
