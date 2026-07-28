import type { Performance } from "@/lib/types";

const fmt = (v: number | null | undefined, d = 2, suffix = "") =>
  v === null || v === undefined ? "—" : `${v.toFixed(d)}${suffix}`;
const money = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 0 });

function Metric({ k, v }: { k: string; v: string }) {
  return (<div className="metric"><span className="v">{v}</span><span className="k">{k}</span></div>);
}

export default function MetricsPanel({ perf }: { perf: Performance }) {
  const t = perf.trades, r = perf.risk;
  return (
    <div className="grid cols-3">
      <div className="panel"><Metric k="Net profit" v={money(t.net_profit)} /></div>
      <div className="panel"><Metric k="Trades" v={String(t.count ?? 0)} /></div>
      <div className="panel"><Metric k="Win rate" v={fmt((t.win_rate ?? 0) * 100, 1, "%")} /></div>
      <div className="panel"><Metric k="Profit factor" v={fmt(t.profit_factor)} /></div>
      <div className="panel"><Metric k="Expectancy" v={money(t.expectancy)} /></div>
      <div className="panel"><Metric k="Avg R" v={fmt(t.avg_r)} /></div>
      <div className="panel"><Metric k="Max drawdown" v={fmt(r.max_drawdown_pct, 2, "%")} /></div>
      <div className="panel"><Metric k="Sharpe" v={fmt(r.sharpe)} /></div>
      <div className="panel"><Metric k="Sortino" v={fmt(r.sortino)} /></div>
      <div className="panel"><Metric k="Calmar" v={fmt(r.calmar)} /></div>
      <div className="panel"><Metric k="Recovery factor" v={fmt(r.recovery_factor)} /></div>
      <div className="panel"><Metric k="Max consec. losses" v={String(t.max_consecutive_losses ?? 0)} /></div>
    </div>
  );
}
