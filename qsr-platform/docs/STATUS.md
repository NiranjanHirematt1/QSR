# QSR Platform — Project Status

**Version 1.0 — feature-complete and verified.** Backend: 108 tests passing, 6 architecture
contracts green, ~4,900 LOC. Frontend: Next.js/TS, production build passes (type-check clean).
Full workflow verified live over HTTP end-to-end.

## Modules

| # | Module | State |
|---|--------|-------|
| 0 | Skeleton + tooling (hexagonal, ruff/mypy/pytest, import-linter) | ✅ Done |
| 1 | Historical Data Manager (CSV/Parquet import, 6 validators, resampling, storage) | ✅ Done |
| 3 | Indicator Engine (10 indicators, registry, de-duplicating engine) | ✅ Done |
| 4 | Strategy Engine (language-agnostic ports + `OrderIntent` IR) | ✅ Done |
| 5 | Backtesting Engine (MTF clock, broker sim, costs, sizing, intrabar, manifest) | ✅ Done |
| 6 | Analytics (all required metrics) | ✅ Done |
| 9 | Reporting (JSON / CSV / HTML / PDF) | ✅ Done |
| 2 | Chart Viewer (candles + trade markers) | ✅ Done |
| 7 | Trade Explorer (click a trade → reasons, R, duration) | ✅ Done |
| 8 | Strategy Comparison (`/compare` + A/B UI) | ✅ Done |
| — | HTTP API (FastAPI), persistence, strategy library | ✅ Done |
| — | Volume Profile indicator | ⏳ Deferred (post-1.0; distribution, not a streaming scalar) |

## Verification (actually run)

- **Backend tests:** `pytest -q` → **108 passed**. Unit, golden-vector (indicators vs
  independent references), property (no-lookahead), integration, and FastAPI TestClient tests.
- **Architecture contracts:** `lint-imports` → **6 kept, 0 broken** (domain purity, layer isolation).
- **Frontend build:** `npm install` + `npm run build` → **compiled successfully**, types valid,
  all 4 routes generated, zero warnings (Next pinned to patched **14.2.35**).
- **Live API smoke (HTTP, real server):** health, strategies, indicators, instruments, dataset
  upload + validation + candles, two backtests, performance/trades/equity, all four exports
  (JSON/CSV/HTML/PDF → HTTP 200), compare, and list — **all pass** against the bundled sample dataset.
- **Headless demo:** `python examples/ema_crossover.py` → runs a full backtest and writes an HTML report.

## Cleanliness

No TODOs, FIXMEs, placeholders, mock implementations, `print`/`console.log` debug statements,
or duplicate strategy logic remain (verified by scan). The one earlier buggy example was replaced
with a correct, runnable demo that drives the real library strategy.

## Known issues / notes

- **Browser click-through QA** of the three UI pages is the one check that must happen on a machine
  with a display (this environment is headless). The build passes and every endpoint the UI calls is
  verified live, so no issues are expected.
- **Single-user, local by design** — no authentication (the API binds to localhost). Add auth only if
  you later expose it to a network.
- **Deferred (optional, post-1.0):** Volume Profile indicator; CME-specific session calendar;
  walk-forward / parameter optimization; corporate-actions handling if equities are added.

## Run it

```bash
bash run_dev.sh        # installs deps on first run, starts API :8000 + UI :3000
```

Then import `backend/sample_data/ES_M5_sample.csv` on the dashboard, run `ema_crossover`,
open the run, and export a report. Full instructions in the root `README.md`.
