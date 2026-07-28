// Typed API client. All requests go through the Next.js rewrite proxy at /api,
// which forwards to the FastAPI backend (see next.config.mjs).
import type {
  BacktestSummary, Candle, DatasetSummary, EquityPoint, Performance,
  StrategyInfo, Trade,
} from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}: ${await r.text()}`);
  return r.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${path} -> ${r.status}: ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  strategies: () => get<StrategyInfo[]>("/strategies"),
  instruments: () => get<string[]>("/instruments"),
  datasets: () => get<DatasetSummary[]>("/datasets"),
  candles: (id: string, limit = 3000) =>
    get<Candle[]>(`/datasets/${id}/candles?limit=${limit}`),
  backtests: () => get<BacktestSummary[]>("/backtests"),
  backtest: (id: string) => get<{ title: string; manifest: Record<string, unknown> }>(`/backtests/${id}`),
  performance: (id: string) => get<Performance>(`/backtests/${id}/performance`),
  trades: (id: string) => get<Trade[]>(`/backtests/${id}/trades`),
  equity: (id: string) => get<EquityPoint[]>(`/backtests/${id}/equity`),
  run: (body: RunBody) => post<BacktestSummary>("/backtests", body),
  compare: (run_ids: string[]) => post<CompareResult>("/compare", { run_ids }),
  exportUrl: (id: string, fmt: string) => `${BASE}/backtests/${id}/export?fmt=${fmt}`,
  async upload(form: FormData): Promise<{ dataset_id: string; persisted: boolean; row_count: number; validation: unknown }> {
    const r = await fetch(`${BASE}/datasets`, { method: "POST", body: form });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
};

export interface RunBody {
  dataset_id: string;
  symbol: string;
  base_timeframe_seconds: number;
  strategy: string;
  params: Record<string, number>;
  config: Record<string, number | string | boolean>;
}

export interface CompareResult {
  metric_keys: string[];
  runs: {
    run_id: string;
    strategy_id: string;
    instrument: string;
    trade_count: number;
    metrics: Record<string, number | null>;
    equity_curve: EquityPoint[];
  }[];
}
