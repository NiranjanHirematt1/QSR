"""CSV export of the trade ledger (one row per trade)."""
from __future__ import annotations

import csv
from pathlib import Path

from .context import ReportContext, trade_to_dict

_FIELDS = ["instrument", "side", "qty", "entry_time", "exit_time", "entry_price",
           "exit_price", "pnl", "r_multiple", "commission", "duration_seconds",
           "entry_reason", "exit_reason"]


class CsvExporter:
    extension = "csv"

    def export(self, ctx: ReportContext, path: Path) -> Path:
        path = Path(path).with_suffix(".csv")
        with path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for t in ctx.trades:
                writer.writerow(trade_to_dict(t))
        return path
