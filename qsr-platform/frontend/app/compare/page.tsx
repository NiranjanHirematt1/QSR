"use client";
import { useEffect, useState } from "react";
import { api, type CompareResult } from "@/lib/api";
import type { BacktestSummary } from "@/lib/types";
import EquityChart from "@/components/EquityChart";

const COLORS = ["#4fd1c5", "#f6ad55"];

export default function ComparePage() {
  const [runs, setRuns] = useState<BacktestSummary[]>([]);
  const [a, setA] = useState(""); const [b, setB] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { api.backtests().then((r) => {
    setRuns(r); if (r[0]) setA(r[0].run_id); if (r[1]) setB(r[1].run_id);
  }).catch((e) => setErr(String(e))); }, []);

  async function compare() {
    setErr(null);
    try { setResult(await api.compare([a, b])); } catch (e) { setErr(String(e)); }
  }

  return (
    <main className="container grid" style={{ gap: 18 }}>
      <h1>Strategy comparison</h1>
      {err && <p className="err">{err}</p>}
      <div className="panel row">
        <label>A<select value={a} onChange={(e) => setA(e.target.value)}>
          {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.strategy_id} · {r.instrument} · {r.run_id.slice(0, 6)}</option>)}
        </select></label>
        <label>B<select value={b} onChange={(e) => setB(e.target.value)}>
          {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.strategy_id} · {r.instrument} · {r.run_id.slice(0, 6)}</option>)}
        </select></label>
        <button className="primary" onClick={compare} disabled={!a || !b || a === b}>Compare</button>
      </div>

      {result && (
        <>
          <div className="panel">
            <h2>Metrics</h2>
            <table>
              <thead><tr><th>Metric</th>{result.runs.map((r) =>
                <th key={r.run_id}>{r.strategy_id} ({r.run_id.slice(0, 6)})</th>)}</tr></thead>
              <tbody>
                {result.metric_keys.map((k) => (
                  <tr key={k}><td>{k}</td>{result.runs.map((r) => (
                    <td key={r.run_id}>{r.metrics[k] === null || r.metrics[k] === undefined
                      ? "—" : (r.metrics[k] as number).toFixed(2)}</td>
                  ))}</tr>
                ))}
                <tr><td>trades</td>{result.runs.map((r) => <td key={r.run_id}>{r.trade_count}</td>)}</tr>
              </tbody>
            </table>
          </div>
          <div className="panel">
            <h2>Equity curves</h2>
            <EquityChart height={320} series={result.runs.map((r, i) => ({
              name: r.strategy_id, color: COLORS[i % COLORS.length], data: r.equity_curve }))} />
          </div>
        </>
      )}
    </main>
  );
}
