"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { BacktestSummary, Candle, EquityPoint, Performance, Trade } from "@/lib/types";
import CandleChart from "@/components/CandleChart";
import EquityChart from "@/components/EquityChart";
import MetricsPanel from "@/components/MetricsPanel";
import TradesTable from "@/components/TradesTable";

export default function BacktestDetail() {
  const { id } = useParams<{ id: string }>();
  const [summary, setSummary] = useState<BacktestSummary | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [perf, setPerf] = useState<Performance | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [sel, setSel] = useState<number | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [list, tr, pf, eq] = await Promise.all([
          api.backtests(), api.trades(id), api.performance(id), api.equity(id)]);
        const s = list.find((r) => r.run_id === id) ?? null;
        setSummary(s); setTrades(tr); setPerf(pf); setEquity(eq);
        if (s) setCandles(await api.candles(s.dataset_id));
      } catch (e) { setErr(String(e)); }
    })();
  }, [id]);

  const selected = sel !== undefined ? trades[sel] : undefined;

  return (
    <main className="container grid" style={{ gap: 18 }}>
      <h1>{summary ? `${summary.strategy_id} · ${summary.instrument}` : "Backtest"}</h1>
      {err && <p className="err">{err}</p>}
      <div className="row">
        {(["json", "csv", "html", "pdf"] as const).map((f) => (
          <a key={f} className="pill" href={api.exportUrl(id, f)} target="_blank" rel="noreferrer">
            export {f.toUpperCase()}</a>
        ))}
      </div>

      {perf && <MetricsPanel perf={perf} />}

      <div className="panel">
        <h2>Price & trades</h2>
        {candles.length ? <CandleChart candles={candles} trades={trades} />
                        : <p className="k">Loading candles…</p>}
      </div>

      <div className="panel">
        <h2>Equity curve</h2>
        {equity.length ? <EquityChart series={[{ name: "equity", color: "#4fd1c5", data: equity }]} />
                       : <p className="k">Loading…</p>}
      </div>

      <div className="grid cols-2">
        <div>
          <h2>Trades ({trades.length}) — click to inspect</h2>
          <TradesTable trades={trades} onSelect={(_, i) => setSel(i)} selected={sel} />
        </div>
        <div>
          <h2>Trade explorer</h2>
          <div className="panel">
            {selected ? (
              <div className="grid" style={{ gap: 6 }}>
                <div className="metric"><span className="v">{selected.pnl.toFixed(2)}</span><span className="k">PnL</span></div>
                <p><span className="pill">{selected.side}</span> qty {selected.qty}</p>
                <p className="k">Entry {selected.entry_price} @ {new Date(selected.entry_time).toLocaleString()}</p>
                <p className="k">Exit {selected.exit_price} @ {new Date(selected.exit_time).toLocaleString()}</p>
                <p>R: {selected.r_multiple === null ? "—" : selected.r_multiple.toFixed(2)} ·
                   Duration: {(selected.duration_seconds / 3600).toFixed(1)}h</p>
                <p>Why in: <b>{selected.entry_reason ?? "—"}</b></p>
                <p>Why out: <b>{selected.exit_reason ?? "—"}</b></p>
              </div>
            ) : <p className="k">Select a trade to see entry/exit reasons, R and duration.</p>}
          </div>
        </div>
      </div>
    </main>
  );
}
