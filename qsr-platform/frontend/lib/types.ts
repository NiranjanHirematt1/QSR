// Shared API types (mirror the backend Pydantic DTOs).
export interface StrategyInfo {
  name: string;
  params: { name: string; default: number; kind: string; description: string }[];
}

export interface DatasetSummary {
  dataset_id: string;
  symbol: string;
  base_timeframe: string;
  row_count: number;
  start: string;
  end: string;
}

export interface BacktestSummary {
  run_id: string;
  strategy_id: string;
  instrument: string;
  base_timeframe: string;
  dataset_id: string;
  created_at: string;
  net_profit: number;
  trade_count: number;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Trade {
  side: string;
  qty: number;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  r_multiple: number | null;
  entry_reason: string | null;
  exit_reason: string | null;
  duration_seconds: number;
}

export interface Performance {
  trades: Record<string, number | null>;
  risk: Record<string, number | null>;
  monthly_returns: Record<string, number>;
  distribution: { low: number; high: number; count: number }[];
}

export type EquityPoint = [string, number];
