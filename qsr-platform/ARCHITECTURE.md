# Quant Strategy Research Platform — Software Architecture

**Codename:** QSR (Quant Strategy Research)
**Version:** 0.1 (Architecture — awaiting approval)
**Author:** Principal Engineer / System Architect
**Scope:** Local, single-user, historical strategy research. Not a broker. Not live trading. Designed to evolve into a commercial SaaS.

**Locked design inputs (from you):**

- **Market:** Forex / Futures — pip/point sizing, contract value, rollover, session calendars, near-24h trading.
- **Execution model:** Event-driven, bar-by-bar. Highest fidelity, no lookahead bias by construction.
- **Timeframes:** Mixed multi-timeframe — a strategy may consume e.g. 5m + 1h + Daily simultaneously.

---

## 0. Executive Summary

We build a **hexagonal (ports & adapters) monorepo**. A pure Python **domain core** — instruments, market data, orders, the backtest engine, indicators, analytics — has **zero knowledge** of FastAPI, SQLite, or React. Everything external (web API, database, file storage, charts) is an **adapter** plugged into the core through interfaces. This is what makes the SQLite→PostgreSQL migration a config change rather than a rewrite, and what lets Pine Script / a Visual Builder be added later without touching the engine.

The two decisions above create three genuinely hard engineering problems that this architecture is built specifically to solve correctly:

1. **Cross-timeframe lookahead bias.** When the engine is on a 5m bar at 10:05, the 1h bar for 10:00–11:00 is *not closed yet*. A naive resample leaks the future. The architecture forbids this structurally via a **Multi-Timeframe Clock** that only ever exposes *closed* higher-timeframe bars.
2. **Intrabar fill sequencing.** Within one candle we only know O/H/L/C, not the path. If both a stop-loss and take-profit sit inside the same bar, which fills first materially changes results. We make this an **explicit, configurable, conservative assumption** — never a silent guess.
3. **Instrument correctness for forex/futures.** PnL is not `(exit − entry) × qty`. It is driven by **point value, tick size, contract multiplier, and quote currency**. This lives in a first-class `ContractSpec`, not scattered constants.

---

## 1. Architectural Principles

- **Hexagonal / Clean Architecture.** Dependencies point inward. Domain depends on nothing; adapters depend on domain.
- **Determinism & reproducibility.** Given the same dataset + strategy + config, the backtest produces byte-identical results. Any randomness is seeded and recorded in the run manifest.
- **No lookahead, ever.** Enforced by the engine's data-access API, not by strategy-author discipline.
- **Strong typing end to end.** Pydantic v2 at boundaries, typed domain value objects internally, TypeScript on the frontend. `mypy --strict` in CI.
- **Dependency injection at the composition root.** The domain never news-up its dependencies; adapters are wired in one place (`api/deps.py`).
- **One responsibility per module.** UI ≠ API ≠ business logic ≠ storage. Enforced by folder boundaries and an import-linter contract.
- **Extension by addition, not modification (Open/Closed).** New indicator = one new file. New order type, sizing rule, fill model, or exporter = one new class implementing an existing interface + one registry entry.
- **No hardcoded values.** Fees, slippage, tick sizes, session hours, paths — all config or data, never literals in logic.

---

## 2. High-Level Structure (C4 Level 2 — Containers)

```
┌────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js / React / TypeScript)                         │
│  Chart Viewer · Trade Explorer · Strategy Comparison · Reports   │
│  TradingView Lightweight Charts                                  │
└───────────────────────────────┬────────────────────────────────┘
                                 │ HTTP / JSON (REST)
┌───────────────────────────────▼────────────────────────────────┐
│  API Adapter (FastAPI)                                            │
│  Routers · Pydantic DTOs · DI wiring · error mapping             │
│  — thin: no business logic —                                     │
└───────────────────────────────┬────────────────────────────────┘
                                 │ calls
┌───────────────────────────────▼────────────────────────────────┐
│  Application Layer (Use-Cases / Services)                        │
│  ImportDataset · RunBacktest · CompareStrategies · BuildReport   │
│  — orchestration only, no domain rules —                         │
└───────────────────────────────┬────────────────────────────────┘
                                 │ uses (via interfaces / ports)
┌───────────────────────────────▼────────────────────────────────┐
│  DOMAIN CORE (pure Python, no I/O)                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Domain   │ │Indicators│ │ Strategy │ │  Engine  │            │
│  │ Model    │ │ Engine   │ │  Engine  │ │(backtest)│            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│  ┌──────────┐ ┌──────────┐                                       │
│  │Analytics │ │Reporting │                                       │
│  └──────────┘ └──────────┘                                       │
└───────────────────────────────┬────────────────────────────────┘
                                 │ ports (interfaces)
┌───────────────────────────────▼────────────────────────────────┐
│  Infrastructure Adapters                                         │
│  Parquet candle store · SQLite catalog · config · logging        │
│  (swappable: Postgres / TimescaleDB later)                       │
└─────────────────────────────────────────────────────────────────┘
```

**Rule:** arrows only point downward/inward. The Domain Core can be unit-tested with zero web server, zero database, zero files — just objects and in-memory data.

---

## 3. Domain Model (the vocabulary everything shares)

These are immutable value objects and entities. They contain forex/futures correctness so nothing downstream reinvents it.

### 3.1 Instrument & ContractSpec

```
Instrument
  symbol            e.g. "EURUSD", "ES", "GC"
  asset_class       FX | FUTURE
  contract_spec     ContractSpec
  session_calendar  SessionCalendar
  quote_currency    e.g. "USD"

ContractSpec
  tick_size         smallest price increment (e.g. 0.00001 EURUSD, 0.25 ES)
  tick_value        cash value of one tick, in quote currency
  point_value       cash value of a 1.0 price move (= tick_value / tick_size)
  contract_multiplier
  min_qty / qty_step
  margin_per_contract   (informational for research)
  pip_definition        (FX: value of a pip, for reporting in pips)
```

**Why this is first-class:** For ES futures a 1-point move on 1 contract = \$50, tick = 0.25 = \$12.50. For EURUSD, a "pip" ≠ a "point." Correct PnL, R-multiples, slippage-in-ticks, and commission-per-contract all depend on this object. Getting it wrong makes every downstream metric wrong. It is data, loaded per instrument, never hardcoded.

### 3.2 Time, Candle, Timeframe

```
Timeframe        enum-ish: M1, M5, M15, H1, H4, D1 ... (value = seconds)
Candle           open_time (UTC), close_time (UTC), O, H, L, C, Volume, timeframe
Bar (alias)      a Candle presented to the strategy
```

- **All timestamps stored and computed in UTC.** Timezone is a *presentation* concern handled at the edge (import + display).
- `open_time` is the bar's start; `close_time = open_time + timeframe`. A bar is only "closed" once wall-clock (simulated) has passed `close_time`. This single rule is what kills cross-TF lookahead.

### 3.3 Orders, Fills, Positions, Trades

```
OrderType     MARKET | LIMIT | STOP | STOP_LIMIT
OrderSide     BUY | SELL
TimeInForce   GTC | DAY | GTD
Order         id, side, type, qty, limit_price?, stop_price?, tif, reduce_only, tag
Fill          order_id, price, qty, commission, slippage, timestamp
Position      instrument, net_qty (signed), avg_price, unrealized_pnl
Trade         a closed round-trip: entry Fill(s) + exit Fill(s), realized PnL,
              R-multiple, MAE/MFE, entry_reason, exit_reason, duration
```

**SessionCalendar** answers `is_open(ts)`, `next_open(ts)`, `bar_belongs_to_session(...)`, and models futures maintenance breaks and the FX weekend gap. This is why forex/futures is harder than crypto — the calendar is not "always on."

---

## 4. Data Layer (Module 1) — designed in depth

### 4.1 Storage strategy — the key decision

**Candle data → Parquet files. Metadata/catalog → SQLite.** We do **not** put OHLCV rows in SQLite.

Rationale:

- Columnar Parquet + Polars gives fast, memory-mapped, typed reads of millions of rows and trivial timeframe slicing.
- SQLite holds only the **catalog**: datasets, instruments, validation reports, backtest runs, results. Small, relational, transactional.
- **Migration path:** the metadata layer sits behind a `CatalogRepository` interface. Swapping SQLite→PostgreSQL is a new adapter. Candle storage can stay Parquet or later move to TimescaleDB behind the same `CandleRepository` port. Nothing in the domain changes.

Layout on disk:

```
data/
  catalog.sqlite
  datasets/
    <dataset_id>/
      manifest.json           # instrument, source, tz, checksum, row count
      M1.parquet              # canonical base timeframe (highest resolution held)
      validation_report.json
```

### 4.2 Base-timeframe canon + on-demand resampling

We store the **highest-resolution timeframe you import** as the canonical series (e.g. M1), and **derive** M5/H1/D1 by resampling. Benefits: single source of truth, no cross-TF inconsistency, less storage. Derived TFs are cached (memoized to Parquet) on first use.

**Resampling rule (must be exact):** a higher-TF bar's `[open_time, close_time)` aggregates all base bars whose `open_time` falls in that window — `open` = first, `high` = max, `low` = min, `close` = last, `volume` = sum. Session boundaries and the calendar define where daily bars break (e.g. futures "day" ≠ midnight UTC). This is the ONLY place resampling logic lives.

### 4.3 Ingestion

`CsvReader`, `ParquetReader` implement a common `CandleSource` port. Column mapping is configurable (your `Date`/`Time` may be split, combined, epoch, or ISO). Output is always a normalized Polars frame in UTC with a validated schema.

### 4.4 Validation (a pipeline of independent checks)

Each validator is a small class implementing `Validator.check(frame, spec) -> list[Issue]`. Adding a check = one file.

- **Missing candles / gaps** — compare actual vs expected grid *from the session calendar* (so weekend/holiday gaps are not false positives; only *in-session* gaps flag).
- **Duplicate timestamps** — exact and near-duplicate detection; configurable resolution (drop / keep-first / error).
- **Invalid OHLC** — enforces `low ≤ open,close ≤ high`, `low ≤ high`, non-negative volume, no NaN/inf.
- **Wrong timeframe** — infers the modal spacing and flags mismatch with the declared timeframe.
- **Timezone problems** — detects DST discontinuities and off-by-hours offsets; requires explicit source-tz declaration, converts to UTC.
- **Monotonicity** — timestamps strictly increasing after dedup.

Output = a structured `ValidationReport` (severity: INFO/WARN/ERROR) persisted to the catalog and surfaced in the UI *before* the dataset is allowed into a backtest.

### 4.5 Multiple datasets

The catalog supports many datasets across many instruments. A backtest run references a dataset + instrument + the set of timeframes the strategy declares.

---

## 5. Indicator Engine (Module 3) — incremental & modular

**Design choice: stateful, incremental (streaming) indicators, O(1) per bar.** This is the natural fit for an event-driven engine and it *cannot* leak the future — an indicator only ever sees bars already delivered.

```
Indicator (interface)
  name / params
  warmup_period            # bars until output is valid
  update(bar) -> value | None
  is_ready -> bool
```

- One file per indicator under `indicators/library/` (`ema.py`, `rsi.py`, `atr.py`, `supertrend.py`, …). A **registry** auto-discovers them, so "adding an indicator = create one file."
- Composed indicators (MACD = EMA−EMA + signal EMA; SuperTrend uses ATR) depend on other indicators through the same interface — no duplication.
- Each indicator is bound to a **specific timeframe stream**, so `RSI(14)` on H1 and `RSI(14)` on M5 are independent instances fed by the clock (see §7).
- Phase-1 set: EMA, SMA, VWMA, RSI, MACD, ADX, ATR, SuperTrend, Bollinger Bands, Donchian. (Volume Profile later — it's a distribution, not a streaming scalar, so it gets its own interface.)
- **Validation harness:** every indicator ships with a golden-value test vs a reference (vectorized) implementation to guarantee correctness.

### 5a. Module 3 — as implemented (addendum)

Implemented exactly to the interface above, with these concrete decisions locked in:

- **Package placement.** `qsr/indicators/` is its own top-level package that depends only on `qsr.domain` (it consumes `Candle`). A new import-linter contract — *"Indicators depend only on the domain"* — enforces this, alongside the existing domain-purity contract (which now also forbids `qsr.domain` from importing `qsr.indicators`). Three contracts, all green.
- **Streaming interface.** `Indicator` ABC: `update(candle) -> value|None`, `is_ready`, `warmup_period`, `bars_seen`, `canonical_params()`. Subclasses implement `_on_bar`; the base handles the value/count bookkeeping. The only input channel is a closed bar and there is no forward-peeking method, so **no-lookahead is structural** — proven by a prefix-independence property test across all ten indicators.
- **Auto-registration.** `__init_subclass__` registers any subclass that sets a `name`; duplicate names raise at import. `registry.discover()` imports every non-underscore module in `library/`, so a new indicator is genuinely one new file. `_`-prefixed modules (e.g. `_smoothing.py`) are treated as private helpers and skipped.
- **Shared smoothing primitives** (`_smoothing.py`): `Rolling` (O(1) windowed sum), `EmaCore` (SMA-seeded EMA), `WilderMA` (RMA/SMMA). EMA, RSI, ATR, ADX, MACD, SuperTrend all share these, so seeding conventions can never drift between indicators.
- **Seeding conventions (documented and test-locked):** EMA/Wilder are seeded with the SMA of the first `period` inputs; true range requires a prior close (so ATR/SuperTrend/ADX skip bar 0); Bollinger uses **population** standard deviation. These match the corresponding independent reference implementations bar-for-bar to 1e-9.
- **De-duplication (`IndicatorEngine`).** Requests are keyed by `(name, stream, sorted-params)`; identical requests share one streaming instance (verified: 12 requests → 3 instances). Param order is irrelevant; distinct params or streams are distinct instances. A "stream" is an opaque series id (a timeframe label in Phase 1), which is exactly the hook the Multi-Timeframe Clock (§7) will drive in Modules 4/5.
- **Multi-line outputs** are typed value objects (`MACDValue`, `BandsValue`, `ADXValue`, `SuperTrendValue`) — named fields, not positional tuples.

**Design note / improvement flagged:** Bollinger currently recomputes mean+variance over its window each bar (O(period)). Correct but the slowest indicator (~4.6 µs/bar). A running-moments (Welford) upgrade would make it O(1) with no interface change — deferred as a non-blocking optimization.

---

## 6. Strategy Engine (Module 4) — the stable public API

Strategies talk to a **`StrategyContext` facade**, never to engine internals. This is the seam that lets Pine Script / a Visual Builder be added later: they *compile down to the same interface*, so the engine never learns they exist.

```
Strategy (abstract base)
  initialize(ctx)                  # declare instruments, timeframes, indicators, params
  on_bar(ctx)                      # called once per closed base-timeframe bar

StrategyContext (injected facade — the ONLY surface a strategy may touch)
  # data access (no lookahead possible)
  bar(tf)            -> Bar        # latest CLOSED bar for timeframe tf
  history(tf, n)     -> list[Bar]  # last n CLOSED bars
  indicator(name, tf)-> value

  # order intents (declarative — the engine executes them)
  buy(qty|size_spec, type=MARKET, limit=?, stop=?, tag=?)
  sell(...)
  close(tag=?)
  set_stoploss(price | distance)
  set_takeprofit(price | distance)

  # portfolio read-only
  position, equity, cash
  # deterministic clock, logging
  now, log(...)
```

Key properties:

- **Declarative orders.** A strategy expresses *intent*; the broker simulator decides fills. Strategies can never mutate positions directly.
- **No engine internals leak.** `ctx` exposes only closed bars and read-only portfolio state — enforcing no-lookahead at the API boundary.
- Strategies are loaded by a `StrategyLoader` (Python plugin now; other frontends later) and validated against the interface before a run.

---

## 7. The Multi-Timeframe Clock (the crux of correctness)

Because you run mixed timeframes on an event-driven engine, this component is the heart of the system.

```
The engine iterates the CANONICAL BASE timeframe (finest, e.g. M5).
For each base bar B with close_time t:
  1. Deliver B to indicators/streams bound to the base timeframe.
  2. For every higher timeframe H:
       if t == a boundary where an H-bar just CLOSED at or before t:
           finalize that H-bar, feed it to H's indicators,
           and only NOW make it visible via ctx.bar(H).
  3. Fire the broker simulator (pending orders, SL/TP checks) for bar B.
  4. Call strategy.on_bar(ctx)  ← sees only closed bars of every TF.
```

**Guarantee:** at 10:05 on M5, `ctx.bar('H1')` returns the 09:00–10:00 bar (closed), never the still-forming 10:00–11:00 bar. Lookahead across timeframes is *structurally impossible*, not a matter of author care. This is the single most important thing this platform does better than a naive backtester.

---

## 8. Backtesting Engine (Module 5) — one execution engine

A single, deterministic event loop. Components are strategies-of-behavior (interfaces) so nothing is hardcoded.

### 8.1 The loop

Data feed → Clock (§7) → Strategy intents → **Broker Simulator** → Portfolio/Ledger → per-bar equity snapshot.

### 8.2 Broker Simulator (fills)

- **Order types:** MARKET, LIMIT, STOP, STOP_LIMIT. Pending orders live in an order book checked each bar.
- **Fill model (interface).** Default `NextBarOpenFill` for market orders (realistic: signal on close of bar N → fill at open of bar N+1, no same-bar-close cheat). Limit/stop fill when the bar's range touches the trigger.
- **Intrabar sequencing (explicit, configurable).** When SL and TP both lie within one bar's range, path is unknown. Default = **conservative/pessimistic**: assume the adverse level (stop) is hit first. Configurable to optimistic or an OHLC-path heuristic (O→H→L→C for up bars, O→L→H→C for down bars). This assumption is **recorded in the run manifest** so results are interpretable and reproducible.
- **Costs (each an interface, forex/futures-aware):**
  - *Commission* — per-contract / per-lot (from ContractSpec), or bps.
  - *Slippage* — in **ticks** (not %), fixed or volatility-scaled (ATR-based).
  - *Spread* — bid/ask spread applied to entries/exits; FX-appropriate.
- **Partial exits & trailing stops** as first-class order/position operations.

### 8.3 Position Sizing (Strategy pattern — no hardcoding)

`PositionSizer` interface with implementations: `FixedQty`, `FixedCash`, `RiskPercent` (size from stop distance × point_value so risk-per-trade is exact in cash terms), `FixedContracts`. Selected via config; new rule = one class.

### 8.4 Determinism

No wall-clock, no unseeded RNG in the hot path. A **run manifest** records dataset checksum, strategy hash, all config (fees, slippage, sizing, intrabar assumption), and engine version. Re-running reproduces results exactly — essential for research you can trust and for later A/B comparison.

### 8a. Modules 4 & 5 — as implemented (addendum)

Implemented to the interfaces above; concrete decisions locked in:

- **Language-agnostic boundary (Module 4) is real, not aspirational.** The engine (`qsr/engine/`) depends only on the `StrategyAdapter` port and the `OrderIntent` IR — never on any authoring language. `PythonStrategyAdapter` bridges the Python `Strategy` base class today; `PineScriptAdapter` / `VisualBuilderAdapter` / `AIStrategyAdapter` / a cross-process `RemoteStrategyAdapter` are each a single new file emitting the same intents, with zero engine changes. An import-linter contract ("Engine depends only on domain and indicators") enforces the boundary in CI.
- **Read-only context.** `EngineStrategyContext` implements the port: it exposes only closed bars (`bar`, `history`), indicator values (via the shared `IndicatorEngine`), and read-only portfolio state (`position_qty`, `equity`, `cash`). The strategy's sole write channel is `submit(intent)`. There is no method to observe an unclosed bar — verified by an engine-level test asserting every visible higher-TF bar has `close_time <= now`.
- **Multi-Timeframe Clock** derives higher-TF bars from the canonical base stream and emits a higher bar as *closed* only when the first base bar of the next bucket arrives; it then feeds that closed bar to the indicator engine's per-timeframe stream. Sub-daily buckets epoch-anchored, daily+ session-anchored.
- **Broker simulator** (single execution engine): market orders fill at the **next bar's open** (no same-bar-close cheat); limit/stop/stop-limit rest and fill when the bar's range crosses the trigger (gap-through fills at the open). One net position per instrument with signed-qty PnL through `ContractSpec.price_to_cash`.
- **Intrabar sequencing** is a first-class `IntrabarAssumption` (PESSIMISTIC default / OPTIMISTIC / OHLC_PATH), with open-gap precedence, recorded in the run manifest. This is the headline accuracy differentiator and is unit-tested across all three modes.
- **Costs** in ticks: `CommissionModel` (per-unit), `ExecutionCosts` applying slippage + half-spread adverse to the side (slippage on market/stop fills, spread on all; limits pay spread only). Verified that slippage correctly applies to *both* entry and exit.
- **Sizing** (`StandardSizer`): FIXED_QTY, FIXED_CASH, RISK_PERCENT (sizes from stop distance × point_value so cash risk is exact), snapped to `qty_step`. RISK_PERCENT raises if no stop is supplied.
- **Partial exits** (`CloseIntent.qty`) and **trailing stops** (`StopLossIntent.trailing`, ratcheted from each bar's close for use on the *next* bar to avoid same-bar bias) are first-class.
- **Round-trip commission attribution.** A subtle bug was caught in testing: per-trade PnL initially omitted the entry commission (present in cash but not in the trade record), so `sum(trade.pnl)` diverged from the equity change. Fixed by accruing entry commission on the position and prorating it (including partial closes and reversals) onto each closed trade. A reconciliation test now asserts `sum(trade.pnl) == final_equity − initial_capital` exactly.
- **Determinism** verified: identical inputs produce an identical `run_hash` and identical trades/equity.

**Performance:** ~17 µs per base bar for a realistic multi-timeframe run (M5 + H1, three indicators, risk-% sizing, trailing stops) — 200k bars in ~3.3 s, single-threaded pure Python. Accuracy-first as specified; a vectorized pre-filter or Cython hot loop is a future optimization with no interface impact.

---

## 9. Analytics (Module 6) — pure functions over the ledger

Given the immutable **trade ledger** + **equity curve**, analytics are pure, testable functions. No state, no I/O.

Metrics: Net/Gross Profit, Gross Loss, Win Rate, Profit Factor, Avg/Largest Win & Loss, Expectancy, Max Drawdown, Recovery Factor, Sharpe, Sortino, Calmar, consecutive wins/losses, avg holding time, **average R** (uses ContractSpec + stop distance), monthly returns, equity curve, drawdown curve, trade distribution, MAE/MFE.

Risk-metric periodicity (annualization factor) is derived from the strategy's base timeframe and session calendar — not a magic `252`. This matters for near-24h forex/futures.

### 9a. Module 6 — as implemented (addendum)

`qsr/analytics/` is a pure package depending only on `qsr.domain.orders.trade` and stdlib (enforced by the "Analytics depends only on the domain" contract). It takes a sequence of closed `Trade`s and an equity series `[(timestamp, equity)]` — never the engine's types — so it is trivially testable and reusable. `compute_trade_metrics` covers net/gross profit, win rate, profit factor, expectancy, avg/largest win-loss, consecutive-win/loss streaks, avg holding time and avg R; `risk_metrics` covers the drawdown curve, max drawdown (% and cash), recovery factor, Sharpe, Sortino, Calmar, per-step and monthly returns. Annualization comes from a configurable `Periodicity` derived from the base timeframe (default near-24h). `PerformanceReport.build()` aggregates everything with a `to_dict()` ready for JSON/PDF export (Module 9). The application-layer `report_from_result()` bridges a `BacktestResult` to the report. Edge cases (no trades, no losing trades, flat equity, single point) return `None`/zero rather than raising, and a test asserts analytics net profit reconciles with the engine ledger.

---

## 10. UI Modules (2, 7, 8) — frontend

Next.js / React / TypeScript. **TradingView Lightweight Charts** for candles, indicator overlays, and trade markers (entry/exit arrows, SL/TP lines, hover tooltips). The frontend is a *pure adapter*: it renders data from the API and holds no business logic.

- **Chart Viewer (2):** candles, zoom/pan/crosshair, indicator overlays, trade markers.
- **Trade Explorer (7):** click a trade → entry/exit candles, entry/exit reasons (captured from the strategy at signal time), indicator snapshot, PnL/R/R:R, duration, an auto-framed chart screenshot of the trade.
- **Strategy Comparison (8):** run A vs B, compare profit/risk/win-rate/drawdown/trade-count with overlaid equity curves. Backed by the deterministic run manifests so comparisons are apples-to-apples.

### 10a. Frontend — as implemented (addendum)

`frontend/` is a Next.js 14 (App Router) + TypeScript app, a pure adapter over the API (no business logic). A dev-time rewrite proxies `/api/*` to the FastAPI backend, so the browser makes same-origin calls and there is no CORS setup. A single typed client (`lib/api.ts`) mirrors the backend DTOs (`lib/types.ts`).

- **Dashboard** (`app/page.tsx`): import a CSV dataset, run a strategy (dataset/strategy pickers, dynamic parameter inputs from each strategy's declared schema, cost/intrabar config), and list past runs.
- **Chart Viewer + Trade Explorer** (`app/backtests/[id]/page.tsx`): a `CandleChart` (Lightweight Charts) with entry/exit arrow markers coloured by PnL, an `EquityChart`, a `MetricsPanel`, and a `TradesTable` whose rows are clickable — selecting a trade populates the Trade Explorer panel (side, prices, entry/exit reasons captured at signal time, R, duration). Export buttons hit the report endpoints (JSON/CSV/HTML/PDF).
- **Strategy Comparison** (`app/compare/page.tsx`): pick two runs, `POST /compare`, render an A/B metrics table plus overlaid equity curves.

The frontend needs the two candle-serving/compare endpoints added to the API: `GET /datasets/{id}/candles` (UNIX-seconds OHLCV for Lightweight Charts) and `POST /compare`. It is code-complete and structurally verified; the production `npm run build` is run locally (the sandbox that generated it could not complete `npm install`).

## 11. Reporting (Module 9)

`Exporter` interface with `PdfExporter`, `CsvExporter`, `JsonExporter`. Reports bundle charts, statistics, the trade list, and a summary. JSON export doubles as the machine-readable run record.

### 11a. Reporting + API — as implemented (addendum)

- **Reporting (`qsr/reporting/`)** depends only on domain + analytics (enforced contract). An `Exporter` protocol with `JsonExporter`, `CsvExporter`, `HtmlExporter` (self-contained, inline-SVG equity curve, zero CDN/JS deps) and `PdfExporter` (reportlab — a pure-Python local dependency, imported lazily). All consume a `ReportContext` (title, manifest dict, `PerformanceReport`, trades, equity), assembled by the application layer so reporting never sees engine types.
- **API (`qsr/api/`)** is a thin FastAPI adapter — no business logic. Routers: `datasets` (upload/import, list, validation), `backtests` (run, list, get, trades, equity, performance, export), `catalog` (strategies, indicators, instruments). Pydantic DTOs at the boundary; a single DI composition root (`deps.py`) constructs repositories/services from `QSR_DATA_DIR`. The "Nothing imports the API layer" contract keeps it a leaf.
- **Persistence.** A `BacktestResultRepository` (SQLite) stores each run's manifest + a JSON payload (trades, equity, performance). Results survive restarts and back the fetch/export endpoints; the Postgres path is the same repository-swap as the rest of the storage layer.
- **Strategy library + registry (`qsr/strategies/`).** `RegisteredStrategy` adds name-based auto-registration and a declared parameter schema on top of the domain `Strategy` API, so the API can list strategies and validate params. Built-ins: `ema_crossover`, `rsi_reversion`. Adding a strategy = one file. A latent bug was fixed here: the context keyed indicators by `(name, timeframe)` only, so two EMAs of different periods collided — `IndicatorRequest` now carries an optional `alias`.
- **Service orchestration.** `BacktestService.run()` composes strategy-registry → engine → analytics → persistence behind one call; `reporting_service.export_stored()` rebuilds a `ReportContext` from a stored run and exports it, single-sourcing export logic. The whole import→backtest→analyze→report loop is covered by FastAPI `TestClient` integration tests.

---

## 12. Cross-Cutting Concerns

- **Config:** Pydantic-settings, layered (defaults → file → env). No literals in logic.
- **Logging:** structured (structlog), per-run correlation id.
- **Errors:** domain exceptions mapped to HTTP problem-details at the API edge only.
- **Testing:** unit (domain, pure), golden-vector (indicators), property-based (validators, no-lookahead invariants), integration (import→backtest→report), determinism (same inputs ⇒ identical outputs).
- **Quality gates (CI):** `ruff`, `mypy --strict`, `pytest` + coverage, and an **import-linter** contract that fails the build if any adapter import sneaks into the domain (architecture enforced by tooling, not hope).

---

## 13. Folder Structure

```
qsr-platform/
├── docs/
│   ├── ARCHITECTURE.md
│   └── adr/                          # architecture decision records
├── backend/
│   ├── pyproject.toml
│   ├── qsr/
│   │   ├── domain/                   # PURE. no I/O, no frameworks.
│   │   │   ├── instruments/          # Instrument, ContractSpec, SessionCalendar
│   │   │   ├── market_data/          # Candle, Timeframe, value objects
│   │   │   ├── orders/               # Order, Fill, Position, Trade
│   │   │   └── events/               # domain events
│   │   ├── data/                     # ── MODULE 1 ──
│   │   │   ├── ingestion/            # CsvReader, ParquetReader (CandleSource port)
│   │   │   ├── validation/           # one validator per file + ValidationReport
│   │   │   ├── resampling/           # single home of timeframe aggregation
│   │   │   └── storage/              # CandleRepository, CatalogRepository (ports)
│   │   ├── indicators/               # ── MODULE 3 ──
│   │   │   ├── base.py               # Indicator interface + registry
│   │   │   └── library/              # ema.py, rsi.py, atr.py, supertrend.py ...
│   │   ├── strategy/                 # ── MODULE 4 ──
│   │   │   ├── base.py               # Strategy ABC
│   │   │   ├── context.py            # StrategyContext facade
│   │   │   └── loader.py
│   │   ├── engine/                   # ── MODULE 5 ── (single execution engine)
│   │   │   ├── clock/                # MultiTimeframeClock  (§7)
│   │   │   ├── execution/            # fill models, slippage, commission, spread
│   │   │   ├── portfolio/            # positions, ledger, PositionSizer strategies
│   │   │   └── backtester.py
│   │   ├── analytics/                # ── MODULE 6 ── pure metric functions
│   │   ├── reporting/                # ── MODULE 9 ── Exporter impls
│   │   ├── application/              # use-cases: ImportDataset, RunBacktest, Compare
│   │   ├── api/                      # FastAPI ADAPTER (thin)
│   │   │   ├── routers/
│   │   │   ├── schemas/              # Pydantic DTOs
│   │   │   └── deps.py              # DI composition root
│   │   ├── infra/                    # SQLite catalog, Parquet store, logging, config
│   │   └── config/
│   └── tests/                        # unit · golden · property · integration
├── frontend/                         # ── MODULES 2, 7, 8 ──
│   ├── app/                          # Next.js routes
│   ├── components/                   # charts (Lightweight Charts), tables, panels
│   ├── lib/                          # API client, typed DTOs
│   └── styles/
└── data/                             # gitignored: catalog.sqlite + datasets/*.parquet
```

The import-linter contract encodes: `domain` may import nothing else; `application` may import `domain`; `api`/`infra` may import `application`+`domain`; nothing may import `api`.

---

## 14. Implementation Roadmap

**Phase 0 — Skeleton (foundation):** monorepo, tooling (ruff/mypy/pytest/import-linter), CI, empty layered packages, domain value objects (`Candle`, `Timeframe`, `Instrument`, `ContractSpec`, `SessionCalendar`), config. No features yet — just the enforced skeleton.

**Phase 1 — Module 1: Historical Data Manager (build & test first, in isolation):**

1. `CandleSource` port + `CsvReader` / `ParquetReader` with configurable column mapping → normalized UTC Polars frame.
2. Validation pipeline (gaps via calendar, duplicates, invalid OHLC, timeframe inference, timezone/DST, monotonicity) → `ValidationReport`.
3. Resampling module (base-TF canon → derived TFs) with exact aggregation + session-aware daily boundaries.
4. Storage: Parquet candle store + SQLite catalog behind `CandleRepository` / `CatalogRepository` ports; dataset manifest + checksum; multi-dataset support.
5. Application use-case `ImportDataset`; minimal FastAPI routes (`POST /datasets`, `GET /datasets`, `GET /datasets/{id}/validation`).
6. **Tests & acceptance criteria:** golden fixtures for each validator; a deliberately corrupted CSV that must produce the exact expected issue set; round-trip import→store→read equality; resampling verified against an independent reference; property test asserting derived TFs never contain future information. *Module 1 is "done" only when these pass.*

**Phase 2 — Module 3 (Indicator Engine):** interface + registry + Phase-1 indicator set, each with golden-vector tests.

**Phase 3 — Modules 4 + 5 + 7 (the core):** Strategy API + StrategyContext, Multi-Timeframe Clock, broker simulator, portfolio/sizing, deterministic run manifest. Delivered together because they're tightly coupled; validated with a known reference strategy whose trades are hand-verified.

**Phase 4 — Module 6 (Analytics):** metrics over the ledger, with unit tests against hand-computed expected values.

**Phase 5 — Modules 2, 7, 8 (Frontend):** Chart Viewer, Trade Explorer, Strategy Comparison on Lightweight Charts.

**Phase 6 — Module 9 (Reporting):** PDF/CSV/JSON exporters.

We do **not** start Phase 2 until Module 1 is complete and its tests are green.

---

## 15. Where I'm Challenging / Improving Your Spec

1. **Store OHLCV in Parquet, not SQLite.** Your spec says "SQLite initially." I'm scoping SQLite to *metadata/catalog* only and putting candles in Parquet. It's faster, cleaner, and makes the Postgres/TimescaleDB migration you want genuinely trivial. (If you'd rather keep everything in SQLite for simplicity now, say so — but I recommend against it.)
2. **Canonical base-timeframe + derived TFs**, rather than storing every timeframe independently. One source of truth; no chance of M5 and H1 disagreeing.
3. **Intrabar fill sequencing must be an explicit, recorded assumption.** This is the #1 hidden source of over-optimistic backtests and the thing TradingView handles opaquely. Making it visible/configurable is a core differentiator — I've built it in.
4. **`ContractSpec` as a first-class citizen** for forex/futures. PnL, R, slippage-in-ticks, and commission-per-contract all flow from it. Non-negotiable for correctness in your chosen market.
5. **No-lookahead is enforced by the engine API, not strategy discipline.** `ctx` only exposes closed bars. This is structural, and it's what makes the results trustworthy.
6. **Bundle Modules 4+5+7 in one phase.** They're too coupled to build in isolation; forcing a hard boundary between them would create throwaway scaffolding.
7. **Reproducibility via run manifests** — added because "compare strategy versions" (Module 8) is only meaningful if runs are deterministic and their exact config is captured.

---

## 16. Open Questions Before Implementation

1. **Storage:** OK to scope SQLite to catalog-only and use Parquet for candles? (My strong recommendation — item 15.1.)
2. **Base timeframe:** what is the finest resolution you'll import (M1? tick-derived M1?) — this sets the canonical series.
3. **Session calendars:** which specific instruments first (e.g. EURUSD spot FX, or CME ES/GC futures)? Their calendars differ and I'll model the first ones concretely.
4. **Intrabar default:** conservative/pessimistic as the default assumption — agreed?
5. **API shape:** REST is assumed. Fine, or do you want WebSocket streaming of backtest progress for long runs?

---

*Next step per your workflow: review this architecture. On approval (and answers to §16), I begin **Phase 0 skeleton + Module 1 only**, fully tested, before anything else.*
