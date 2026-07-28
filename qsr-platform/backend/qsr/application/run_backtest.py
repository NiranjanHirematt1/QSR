"""RunBacktest use-case — loads a stored dataset and runs the engine on it.

Orchestration only: it converts a stored Polars candle frame into the domain
``Candle`` sequence and delegates to :class:`Backtester`. The engine itself
never touches Polars or storage, preserving the layer boundary.
"""
from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from ..data.ingestion.schema import CLOSE, HIGH, LOW, OPEN, TS, VOLUME
from ..data.storage.base import CandleRepository, CatalogRepository
from ..domain.instruments.instrument import Instrument
from ..domain.market_data.candle import Candle
from ..domain.market_data.timeframe import Timeframe
from ..domain.strategy.adapter import StrategyAdapter
from ..engine.backtester import Backtester
from ..engine.config import BacktestConfig
from ..engine.result import BacktestResult


def frame_to_candles(df: pl.DataFrame, timeframe: Timeframe) -> list[Candle]:
    """Convert a canonical-schema Polars frame into domain candles (UTC)."""
    df = df.sort(TS)
    rows = df.select(TS, OPEN, HIGH, LOW, CLOSE, VOLUME).iter_rows()
    return [Candle(ts, timeframe, o, h, l, c, v) for ts, o, h, l, c, v in rows]


@dataclass(frozen=True, slots=True)
class RunBacktest:
    candles: CandleRepository
    catalog: CatalogRepository

    def execute(self, dataset_id: str, instrument: Instrument, base_timeframe: Timeframe,
                adapter: StrategyAdapter, config: BacktestConfig | None = None,
                strategy_id: str = "strategy") -> BacktestResult:
        meta = self.catalog.get(dataset_id)
        checksum = meta.checksum if meta else ""
        df = self.candles.read(dataset_id)
        candles = frame_to_candles(df, base_timeframe)
        return Backtester(instrument, base_timeframe, config).run(
            candles, adapter, strategy_id=strategy_id, dataset_checksum=checksum)
