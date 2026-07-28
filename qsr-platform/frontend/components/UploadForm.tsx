"use client";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";

export default function UploadForm({ onDone }: { onDone: () => void }) {
  const [symbol, setSymbol] = useState("ES");
  const [tf, setTf] = useState(300);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const input = (e.currentTarget.elements.namedItem("file") as HTMLInputElement);
    if (!input.files?.[0]) { setErr("Choose a CSV file"); return; }
    const fd = new FormData();
    fd.append("file", input.files[0]);
    fd.append("symbol", symbol);
    fd.append("base_timeframe_seconds", String(tf));
    fd.append("source_format", "csv");
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await api.upload(fd);
      setMsg(r.persisted ? `Imported ${r.row_count} rows (${r.dataset_id.slice(0, 8)})`
                         : `Rejected: validation errors`);
      onDone();
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Import dataset (CSV)</h2>
      <div className="row">
        <label>File<input type="file" name="file" accept=".csv" /></label>
        <label>Symbol
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
            <option>ES</option><option>EURUSD</option>
          </select>
        </label>
        <label>Timeframe
          <select value={tf} onChange={(e) => setTf(Number(e.target.value))}>
            <option value={60}>M1</option><option value={300}>M5</option>
            <option value={900}>M15</option><option value={3600}>H1</option>
          </select>
        </label>
        <button className="primary" disabled={busy} type="submit">{busy ? "Importing…" : "Import"}</button>
      </div>
      {msg && <p className="pill" style={{ marginTop: 10 }}>{msg}</p>}
      {err && <p className="err">{err}</p>}
    </form>
  );
}
