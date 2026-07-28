"""Backtester — the single deterministic event loop tying Modules 3, 4 and 5.

Per base bar, in strict order:
  1. Clock: deliver the base bar and any just-closed higher-TF bars to the
     indicator engine and the strategy's history (closed bars only).
  2. Broker: process pending/resting orders and stop/target exits on this bar.
  3. Strategy: on_bar() emits intents against a read-only context.
  4. Broker: resolve those intents into orders (sized, protective levels attached).
  5. Record an equity point.
No wall-clock or RNG is used, so a run is fully reproducible from its manifest.
"""
from __future__ import annotations

from ..domain.instruments.instrument import Instrument
from ..domain.market_data.candle import Candle
from ..domain.market_data.timeframe import Timeframe
from ..domain.strategy.adapter import StrategyAdapter
from ..indicators.engine import IndicatorEngine
from .clock.multi_timeframe_clock import MultiTimeframeClock
from .config import BacktestConfig
from .context import EngineStrategyContext
from .execution.broker import BrokerSimulator
from .execution.costs import CommissionModel, ExecutionCosts
from .manifest import RunManifest
from .portfolio.ledger import EquityPoint, Ledger
from .result import BacktestResult


class Backtester:
    def __init__(self, instrument: Instrument, base_timeframe: Timeframe,
                 config: BacktestConfig | None = None) -> None:
        self._inst = instrument
        self._base = base_timeframe
        self._config = config or BacktestConfig()

    def run(self, candles: list[Candle], adapter: StrategyAdapter,
            *, strategy_id: str = "strategy", dataset_checksum: str = "") -> BacktestResult:
        cfg = self._config
        ledger = Ledger()
        broker = BrokerSimulator(
            instrument=self._inst,
            initial_capital=cfg.initial_capital,
            commission=CommissionModel(cfg.commission_per_unit),
            costs=ExecutionCosts(self._inst.spec, cfg.slippage_ticks, cfg.spread_ticks),
            intrabar=cfg.intrabar,
            ledger=ledger,
        )
        engine = IndicatorEngine()
        ctx = EngineStrategyContext(broker)

        # --- initialize: declare timeframes + indicators before any bar -----
        reqs = adapter.initialize(ctx)
        for ind in reqs.indicators:
            handle = engine.request(ind.name, ind.timeframe.label, **dict(ind.params))
            ctx.register_indicator(ind.handle, ind.timeframe, handle)
        higher = tuple(tf for tf in reqs.timeframes if tf.seconds > self._base.seconds)
        clock = MultiTimeframeClock(self._base, higher, self._inst.calendar)

        # --- event loop ------------------------------------------------------
        last: Candle | None = None
        for base_bar in candles:
            closed_higher = clock.advance(base_bar)

            engine.on_bar(self._base.label, base_bar)
            ctx.push_bar(self._base, base_bar)
            for tf, hbar in closed_higher:
                engine.on_bar(tf.label, hbar)
                ctx.push_bar(tf, hbar)

            broker.process_bar(base_bar)

            ctx.set_clock(base_bar.close_time, base_bar.close)
            adapter.on_bar(ctx)
            broker.submit_intents(ctx.drain_intents(), ref_bar=base_bar)

            ledger.record_equity(EquityPoint(
                timestamp=base_bar.close_time,
                equity=broker.equity(base_bar.close),
                cash=broker.realized_cash,
                position_qty=broker.position.qty,
            ))
            last = base_bar

        if cfg.close_at_end and last is not None:
            broker.close_all(last)
            ledger.record_equity(EquityPoint(
                timestamp=last.close_time,
                equity=broker.equity(last.close),
                cash=broker.realized_cash,
                position_qty=broker.position.qty,
            ))

        manifest = RunManifest(
            strategy_id=strategy_id,
            instrument=self._inst.symbol,
            base_timeframe=self._base.label,
            dataset_checksum=dataset_checksum,
            config={
                "initial_capital": cfg.initial_capital,
                "commission_per_unit": cfg.commission_per_unit,
                "slippage_ticks": cfg.slippage_ticks,
                "spread_ticks": cfg.spread_ticks,
                "intrabar": cfg.intrabar.value,
                "close_at_end": cfg.close_at_end,
            },
        )
        return BacktestResult(manifest, ledger)
