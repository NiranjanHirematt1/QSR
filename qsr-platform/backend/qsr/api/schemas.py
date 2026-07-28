"""Pydantic request/response DTOs. The API speaks these; the domain never does."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    dataset_id: str
    symbol: str
    base_timeframe: str
    row_count: int
    start: str
    end: str


class ImportResponse(BaseModel):
    dataset_id: str
    persisted: bool
    row_count: int
    validation: dict


class StrategyInfo(BaseModel):
    name: str
    params: list[dict]


class BacktestConfigDTO(BaseModel):
    initial_capital: float = 100_000.0
    commission_per_unit: float = 0.0
    slippage_ticks: float = 0.0
    spread_ticks: float = 0.0
    intrabar: str = "PESSIMISTIC"
    close_at_end: bool = True


class RunBacktestRequest(BaseModel):
    dataset_id: str
    symbol: str = Field(examples=["EURUSD", "ES"])
    base_timeframe_seconds: int = 300
    strategy: str
    params: dict = Field(default_factory=dict)
    config: BacktestConfigDTO = Field(default_factory=BacktestConfigDTO)


class BacktestSummary(BaseModel):
    run_id: str
    strategy_id: str
    instrument: str
    base_timeframe: str
    dataset_id: str
    created_at: str
    net_profit: float
    trade_count: int
