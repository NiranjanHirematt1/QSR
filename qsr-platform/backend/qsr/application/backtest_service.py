"""BacktestService — run a named strategy on a stored dataset, analyze, persist.

This is the orchestration the API drives: it composes the engine, analytics and
reporting behind one call and stores the result so it can be fetched later.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from ..data.storage.base import BacktestResultRepository, CandleRepository, CatalogRepository
from ..data.storage.models import StoredBacktest
from ..domain.instruments.catalog import instrument_by_symbol
from ..domain.market_data.timeframe import Timeframe
from ..domain.strategy.base import PythonStrategyAdapter
from ..engine.config import BacktestConfig
from ..engine.execution.fill_model import IntrabarAssumption
from ..strategies import registry as strategy_registry
from .analyze_backtest import context_from_result
from .run_backtest import RunBacktest


@dataclass(frozen=True, slots=True)
class BacktestService:
    candles: CandleRepository
    catalog: CatalogRepository
    results: BacktestResultRepository

    def run(self, *, dataset_id: str, symbol: str, base_timeframe_seconds: int,
            strategy_name: str, strategy_params: dict | None,
            config: dict | None) -> StoredBacktest:
        instrument = instrument_by_symbol(symbol)
        base_tf = Timeframe(base_timeframe_seconds)
        strategy = strategy_registry.create(strategy_name, strategy_params)
        cfg = _build_config(config or {})

        result = RunBacktest(self.candles, self.catalog).execute(
            dataset_id, instrument, base_tf, PythonStrategyAdapter(strategy),
            cfg, strategy_id=strategy_name)

        ctx = context_from_result(result, base_tf,
                                  title=f"{strategy_name} · {symbol} · {base_tf.label}")
        record = StoredBacktest(
            run_id=uuid.uuid4().hex,
            strategy_id=strategy_name,
            instrument=symbol,
            base_timeframe=base_tf.label,
            dataset_id=dataset_id,
            created_at=datetime.now(timezone.utc),
            net_profit=result.net_profit,
            trade_count=result.trade_count,
            manifest_json=json.dumps(result.manifest.to_dict()),
            result_json=json.dumps(ctx.to_dict(), default=str),
        )
        self.results.save(record)
        return record


def _build_config(raw: dict) -> BacktestConfig:
    intrabar = raw.get("intrabar", "PESSIMISTIC")
    return BacktestConfig(
        initial_capital=float(raw.get("initial_capital", 100_000.0)),
        commission_per_unit=float(raw.get("commission_per_unit", 0.0)),
        slippage_ticks=float(raw.get("slippage_ticks", 0.0)),
        spread_ticks=float(raw.get("spread_ticks", 0.0)),
        intrabar=IntrabarAssumption(intrabar),
        close_at_end=bool(raw.get("close_at_end", True)),
    )
