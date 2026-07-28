# QSR Frontend (Next.js + TypeScript)

Web UI for the QSR research platform: dataset import, backtest runs, chart viewer
with trade markers, trade explorer, and A/B strategy comparison. Talks to the
FastAPI backend via a dev proxy (`/api/*` → `http://localhost:8000`).

## Requirements
- Node.js 18+ (tested on Node 22)
- The backend running on port 8000 (`cd ../backend && bash scripts/run_api.sh`)

## Setup & run
```bash
npm install
cp .env.local.example .env.local     # set QSR_API_BASE if backend isn't on :8000
npm run dev                          # http://localhost:3000
```

## Verify
```bash
npm run typecheck    # tsc --noEmit (strict)
npm run build        # production build
```

## Structure
- `app/page.tsx` — dashboard: import dataset, run backtest, list runs.
- `app/backtests/[id]/page.tsx` — **Module 2 Chart Viewer** (candles + indicator/trade
  markers) + metrics + equity curve + **Module 7 Trade Explorer** (click a trade).
- `app/compare/page.tsx` — **Module 8** A/B comparison (metrics table + overlaid equity).
- `components/` — `CandleChart`, `EquityChart` (TradingView Lightweight Charts),
  `MetricsPanel`, `TradesTable`, `RunForm`, `UploadForm`.
- `lib/api.ts` — typed API client; `lib/types.ts` — DTOs mirroring the backend.
