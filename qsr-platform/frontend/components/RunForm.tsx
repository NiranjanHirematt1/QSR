"use client";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { DatasetSummary, StrategyInfo } from "@/lib/types";

const TF_SECONDS: Record<string, number> = { M1: 60, M5: 300, M15: 900, H1: 3600, H4: 14400, D1: 86400 };

export default function RunForm(
  { datasets, strategies, onDone }:
  { datasets: DatasetSummary[]; strategies: StrategyInfo[]; onDone: () => void }
) {
  const [datasetId, setDatasetId] = useState(datasets[0]?.dataset_id ?? "");
  const [strategyName, setStrategyName] = useState(strategies[0]?.name ?? "");
  const [params, setParams] = useState<Record<string, number>>({});
  const [commission, setCommission] = useState(2);
  const [slippage, setSlippage] = useState(1);
  const [intrabar, setIntrabar] = useState("PESSIMISTIC");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const dataset = useMemo(() => datasets.find((d) => d.dataset_id === datasetId), [datasets, datasetId]);
  const strategy = useMemo(() => strategies.find((s) => s.name === strategyName), [strategies, strategyName]);

  function setParam(k: string, v: number) { setParams((p) => ({ ...p, [k]: v })); }

  async function run() {
    if (!dataset || !strategy) return;
    const tfSecs = TF_SECONDS[dataset.base_timeframe] ?? 300;
    const merged: Record<string, number> = { timeframe_seconds: tfSecs };
    for (const p of strategy.params) merged[p.name] = params[p.name] ?? p.default;
    setBusy(true); setErr(null);
    try {
      await api.run({
        dataset_id: dataset.dataset_id, symbol: dataset.symbol,
        base_timeframe_seconds: tfSecs, strategy: strategy.name, params: merged,
        config: { commission_per_unit: commission, slippage_ticks: slippage, intrabar },
      });
      onDone();
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  }

  if (!datasets.length) return <div className="panel"><h2>Run backtest</h2><p className="k">Import a dataset first.</p></div>;

  return (
    <div className="panel">
      <h2>Run backtest</h2>
      <div className="row">
        <label>Dataset
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            {datasets.map((d) => <option key={d.dataset_id} value={d.dataset_id}>
              {d.symbol} · {d.base_timeframe} · {d.row_count} bars</option>)}
          </select>
        </label>
        <label>Strategy
          <select value={strategyName} onChange={(e) => { setStrategyName(e.target.value); setParams({}); }}>
            {strategies.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </label>
        <label>Commission<input type="number" value={commission} step={0.5}
          onChange={(e) => setCommission(Number(e.target.value))} /></label>
        <label>Slippage (ticks)<input type="number" value={slippage} step={1}
          onChange={(e) => setSlippage(Number(e.target.value))} /></label>
        <label>Intrabar
          <select value={intrabar} onChange={(e) => setIntrabar(e.target.value)}>
            <option>PESSIMISTIC</option><option>OPTIMISTIC</option><option>OHLC_PATH</option>
          </select>
        </label>
      </div>
      {strategy && strategy.params.filter((p) => p.name !== "timeframe_seconds").length > 0 && (
        <div className="row" style={{ marginTop: 10 }}>
          {strategy.params.filter((p) => p.name !== "timeframe_seconds").map((p) => (
            <label key={p.name} title={p.description}>{p.name}
              <input type="number" defaultValue={p.default}
                onChange={(e) => setParam(p.name, Number(e.target.value))} /></label>
          ))}
        </div>
      )}
      <div style={{ marginTop: 12 }}>
        <button className="primary" disabled={busy} onClick={run}>{busy ? "Running…" : "Run backtest"}</button>
      </div>
      {err && <p className="err">{err}</p>}
    </div>
  );
}
