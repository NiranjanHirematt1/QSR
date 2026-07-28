"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { BacktestSummary, DatasetSummary, StrategyInfo } from "@/lib/types";
import UploadForm from "@/components/UploadForm";
import RunForm from "@/components/RunForm";

export default function Dashboard() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [runs, setRuns] = useState<BacktestSummary[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [d, s, b] = await Promise.all([api.datasets(), api.strategies(), api.backtests()]);
      setDatasets(d); setStrategies(s); setRuns(b);
    } catch (e) { setErr(String(e)); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <main className="container grid" style={{ gap: 20 }}>
      <h1>Strategy Research Dashboard</h1>
      {err && <p className="err">{err} — is the API running on :8000?</p>}
      <UploadForm onDone={refresh} />
      <RunForm datasets={datasets} strategies={strategies} onDone={refresh} />
      <div className="panel">
        <h2>Backtests</h2>
        {runs.length === 0 ? <p className="k">No runs yet.</p> : (
          <table>
            <thead><tr><th>Strategy</th><th>Instrument</th><th>Trades</th>
              <th>Net profit</th><th>When</th><th></th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id} className={r.net_profit >= 0 ? "win" : "loss"}>
                  <td>{r.strategy_id}</td><td>{r.instrument}</td><td>{r.trade_count}</td>
                  <td className="pnl">{r.net_profit.toFixed(2)}</td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td><Link href={`/backtests/${r.run_id}`}>open →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
