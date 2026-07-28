"use client";
import type { Trade } from "@/lib/types";

export default function TradesTable(
  { trades, onSelect, selected }:
  { trades: Trade[]; onSelect?: (t: Trade, i: number) => void; selected?: number }
) {
  return (
    <div className="panel" style={{ overflowX: "auto", maxHeight: 420, overflowY: "auto" }}>
      <table>
        <thead><tr>
          <th>#</th><th>Side</th><th>Qty</th><th>Entry</th><th>Exit</th>
          <th>PnL</th><th>R</th><th>Why in</th><th>Why out</th>
        </tr></thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={i} className={t.pnl >= 0 ? "win" : "loss"}
                onClick={() => onSelect?.(t, i)}
                style={{ cursor: onSelect ? "pointer" : "default",
                         outline: selected === i ? "1px solid var(--accent)" : "none" }}>
              <td>{i + 1}</td><td>{t.side}</td><td>{t.qty}</td>
              <td>{t.entry_price}</td><td>{t.exit_price}</td>
              <td className="pnl">{t.pnl.toFixed(2)}</td>
              <td>{t.r_multiple === null ? "—" : t.r_multiple.toFixed(2)}</td>
              <td>{t.entry_reason ?? ""}</td><td>{t.exit_reason ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
