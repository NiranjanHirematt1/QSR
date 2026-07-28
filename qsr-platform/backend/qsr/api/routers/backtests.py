"""Backtest run, fetch, trades, equity, and export endpoints."""
from __future__ import annotations

import json
from pathlib import Path

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...application.reporting_service import export_stored
from ..deps import backtest_repo, backtest_service
from ..schemas import BacktestSummary, RunBacktestRequest

_MEDIA = {"json": "application/json", "csv": "text/csv",
          "html": "text/html", "pdf": "application/pdf"}

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _summary(rec) -> BacktestSummary:
    return BacktestSummary(
        run_id=rec.run_id, strategy_id=rec.strategy_id, instrument=rec.instrument,
        base_timeframe=rec.base_timeframe, dataset_id=rec.dataset_id,
        created_at=rec.created_at.isoformat(), net_profit=rec.net_profit,
        trade_count=rec.trade_count)


@router.post("", response_model=BacktestSummary)
def run_backtest(req: RunBacktestRequest) -> BacktestSummary:
    try:
        rec = backtest_service().run(
            dataset_id=req.dataset_id, symbol=req.symbol,
            base_timeframe_seconds=req.base_timeframe_seconds,
            strategy_name=req.strategy, strategy_params=req.params,
            config=req.config.model_dump())
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return _summary(rec)


@router.get("", response_model=list[BacktestSummary])
def list_backtests() -> list[BacktestSummary]:
    return [_summary(r) for r in backtest_repo().list_all()]


def _load(run_id: str) -> dict:
    rec = backtest_repo().get(run_id)
    if rec is None:
        raise HTTPException(404, f"backtest {run_id} not found")
    return json.loads(rec.result_json)


@router.get("/{run_id}")
def get_backtest(run_id: str) -> dict:
    return _load(run_id)


@router.get("/{run_id}/trades")
def get_trades(run_id: str) -> list[dict]:
    return _load(run_id)["trades"]


@router.get("/{run_id}/equity")
def get_equity(run_id: str) -> list:
    return _load(run_id)["equity_curve"]


@router.get("/{run_id}/performance")
def get_performance(run_id: str) -> dict:
    return _load(run_id)["performance"]


@router.get("/{run_id}/export")
def export_backtest(run_id: str, fmt: str = "json") -> FileResponse:
    rec = backtest_repo().get(run_id)
    if rec is None:
        raise HTTPException(404, f"backtest {run_id} not found")
    if fmt not in _MEDIA:
        raise HTTPException(400, f"unsupported format {fmt!r}; use one of {list(_MEDIA)}")
    payload = json.loads(rec.result_json)
    out_dir = Path(tempfile.mkdtemp())
    try:
        path = export_stored(rec, payload, fmt, out_dir)
    except RuntimeError as exc:  # e.g. reportlab missing for pdf
        raise HTTPException(503, f"exporter unavailable: {exc}") from exc
    return FileResponse(path, media_type=_MEDIA[fmt], filename=path.name)
