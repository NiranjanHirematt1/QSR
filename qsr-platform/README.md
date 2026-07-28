# QSR — Quant Strategy Research Platform

A local, single-user **backtesting research platform** for forex/futures strategies.
Event-driven, multi-timeframe, accuracy-first. Not a broker; not live trading —
historical strategy research only.

- **Backend:** Python · FastAPI · Polars · NumPy · Pydantic · SQLite + Parquet
- **Frontend:** Next.js · React · TypeScript · TradingView Lightweight Charts
- **Architecture:** hexagonal (ports & adapters); a pure domain core with the web,
  storage, and UI as swappable adapters. Boundaries enforced in CI by `import-linter`.

Full design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · Status: [`docs/STATUS.md`](docs/STATUS.md)

---

## Quick start (one command)

Requirements: **Python 3.11+** and **Node.js 18+**.

```bash
bash run_dev.sh
```

This installs dependencies on first run, then starts:

- Backend API → http://localhost:8000  (interactive docs at `/docs`)
- Frontend UI → http://localhost:3000

Then, in the UI: **Import** `backend/sample_data/ES_M5_sample.csv` (symbol `ES`, M5) →
**Run** the `ema_crossover` strategy on it → **Open** the run to see the price chart with
trade markers, the metrics panel, the equity curve, and the Trade Explorer → **Export**
a PDF/HTML/CSV/JSON report → run a second strategy and open **Compare**.

## Manual start (two terminals)

```bash
# Terminal 1 — backend
cd backend
pip install -e ".[dev]"
bash scripts/run_api.sh              # http://localhost:8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                          # http://localhost:3000
```

## Verify

```bash
# Backend: 108 tests + architecture contracts
cd backend && pytest -q && lint-imports

# Frontend: type-check + production build
cd frontend && npm run build

# Headless end-to-end demo (no UI): backtest + HTML report
cd backend && PYTHONPATH=. python examples/ema_crossover.py
```

## Project layout

```
qsr-platform/
├── run_dev.sh              # one-command launcher (backend + frontend)
├── README.md               # this file
├── docs/                   # ARCHITECTURE.md, STATUS.md
├── backend/                # Python: FastAPI + engine + analytics + reporting
│   ├── qsr/                # the package (domain, data, indicators, engine,
│   │                       #   analytics, reporting, strategies, application, api)
│   ├── tests/              # 108 tests (unit, golden, property, integration, API)
│   ├── examples/           # runnable end-to-end demo
│   ├── sample_data/        # ES_M5_sample.csv to import immediately
│   └── scripts/run_api.sh
└── frontend/               # Next.js + TypeScript UI (dashboard, chart viewer,
                            #   trade explorer, comparison)
```

## What it does

Import OHLCV data → run a strategy through a deterministic, event-driven engine with
realistic costs (commission, slippage, spread), position sizing (fixed / cash / risk-%),
stop-loss / take-profit / trailing / partial exits, and an **explicit intrabar fill
assumption** → get a full trade ledger, equity curve, and analytics (win rate, profit
factor, expectancy, avg R, drawdown, Sharpe/Sortino/Calmar, monthly returns) → explore
every trade visually → compare strategies A/B → export reports.

Strategies are authored against a **language-agnostic** boundary (`StrategyAdapter` +
`OrderIntent` IR), so Pine Script, a visual builder, or an AI author can be added later
as adapters without touching the engine.
