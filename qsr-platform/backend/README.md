# QSR Backend — Phase 0 + Module 1

Local quantitative strategy research platform. Forex/futures, event-driven, multi-timeframe.
Hexagonal architecture: the `qsr.domain` core is pure Python (no I/O, no frameworks);
everything else is an adapter.

## Status

- **Phase 0 (skeleton):** domain value objects, layered packages, tooling, enforced boundaries — done.
- **Module 1 (Historical Data Manager):** ingestion, validation, resampling, storage, import use-case — done and tested.
- **Language-agnostic strategy seam:** `StrategyAdapter` / `StrategyContext` ports + `OrderIntent` IR — defined and tested. Pine Script / Visual Builder / AI plug in as adapters without engine changes.
- **Module 3 (Indicator Engine):** 10 incremental indicators (SMA, EMA, VWMA, RSI, MACD, ATR, ADX, SuperTrend, Bollinger, Donchian), auto-registering registry, de-duplicating `IndicatorEngine` — done and tested (97% coverage).
- **Modules 4 & 5 (Strategy + Backtesting Engine):** language-agnostic `StrategyAdapter` boundary, multi-timeframe clock, broker simulator (market/limit/stop, SL/TP, trailing, partial exits), explicit intrabar sequencing, commission/slippage/spread, risk-based sizing, deterministic run manifest — done and tested (engine coverage 93–100%).
- **Module 6 (Analytics):** pure metrics over the ledger/equity curve — net/gross, win rate, profit factor, expectancy, streaks, avg R, drawdown, Sharpe/Sortino/Calmar, recovery, monthly returns, distribution — done and tested (96% coverage).
- **Module 9 (Reporting):** JSON / CSV / self-contained HTML / PDF exporters over a report context — done and tested.
- **Strategy library + registry:** `ema_crossover`, `rsi_reversion`, selectable by name with parameter schemas.
- **HTTP API (FastAPI):** dataset import, backtest run/fetch, trades/equity/performance, file exports — done and tested (TestClient).

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest -q            # 105 tests
lint-imports         # verifies architecture boundaries (domain purity)
```

## Run the API

```bash
bash scripts/run_api.sh          # http://localhost:8000  (docs at /docs)
```

Endpoints: `POST /datasets` (upload CSV/Parquet), `GET /strategies`, `POST /backtests`,
`GET /backtests/{id}/performance|trades|equity`, `GET /backtests/{id}/export?fmt=json|csv|html|pdf`.

## What Module 1 does

```python
from qsr.application.import_dataset import ImportDataset, ImportRequest
from qsr.data.ingestion.column_mapping import ColumnMapping
from qsr.data.ingestion.readers import CsvReader, ParquetReader
from qsr.data.storage.parquet_store import ParquetCandleRepository
from qsr.data.storage.sqlite_catalog import SqliteCatalogRepository
from qsr.domain.instruments.catalog import eurusd
from qsr.domain.market_data.timeframe import Timeframe

uc = ImportDataset(
    reader_for={"csv": CsvReader(), "parquet": ParquetReader()},
    candles=ParquetCandleRepository("data/datasets"),
    catalog=SqliteCatalogRepository("data/catalog.sqlite"),
)
req = ImportRequest(
    path="eurusd_m1.csv",
    instrument=eurusd(),
    base_timeframe=Timeframe.from_label("M1"),
    mapping=ColumnMapping(date="Date", time="Time", datetime_format="%Y-%m-%d %H:%M"),
    source_format="csv",
)
result = uc.execute(req)   # validates; persists only if no ERROR-level issues
```

Pipeline: **read → normalise to UTC canonical schema → validate → reject on ERROR → persist candles (Parquet) + metadata (SQLite)**.

Validators (each one file, extend by adding a class): empty dataset, non-monotonic timestamps,
duplicate timestamps, invalid OHLC, wrong timeframe, missing in-session candles (session-calendar
aware so weekend/maintenance gaps are not false positives).

Candle storage is Parquet; only metadata lives in SQLite — swapping to PostgreSQL/TimescaleDB is a
new adapter behind `CatalogRepository` / `CandleRepository`, no caller changes.

## Not yet built (per roadmap)

Indicator engine (Module 3), the multi-timeframe clock + backtest engine + broker simulator
(Modules 4/5), analytics, frontend, reporting. The public interfaces they depend on are already
defined so they slot in without reworking Module 1.
```
