"""Rebuild a ReportContext from a persisted backtest and export it.

Reconstructs domain Trades and the equity series from the stored JSON, recomputes
the analytics report (reusing the analytics package), and hands the result to an
exporter. Keeps export logic single-sourced rather than duplicated per format.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..analytics.report import PerformanceReport
from ..data.storage.models import StoredBacktest
from ..domain.market_data.timeframe import Timeframe
from ..domain.orders.intents import Side
from ..domain.orders.trade import Trade
from ..reporting.context import ReportContext
from ..reporting.csv_exporter import CsvExporter
from ..reporting.html_exporter import HtmlExporter
from ..reporting.json_exporter import JsonExporter

_EXPORTERS = {"json": JsonExporter, "csv": CsvExporter, "html": HtmlExporter}


def _trade_from_dict(d: dict) -> Trade:
    return Trade(
        instrument=d["instrument"], side=Side(d["side"]), qty=d["qty"],
        entry_time=datetime.fromisoformat(d["entry_time"]),
        exit_time=datetime.fromisoformat(d["exit_time"]),
        entry_price=d["entry_price"], exit_price=d["exit_price"], pnl=d["pnl"],
        r_multiple=d["r_multiple"], commission=d["commission"],
        entry_reason=d["entry_reason"], exit_reason=d["exit_reason"],
        tags=tuple(d.get("tags", ())))


def context_from_stored(record: StoredBacktest, payload: dict) -> ReportContext:
    trades = [_trade_from_dict(t) for t in payload["trades"]]
    equity = [(datetime.fromisoformat(ts), eq) for ts, eq in payload["equity_curve"]]
    tf = Timeframe.from_label(record.base_timeframe)
    report = PerformanceReport.build(trades, equity, tf.seconds)
    return ReportContext(title=payload.get("title", record.run_id),
                         manifest=payload.get("manifest", {}),
                         report=report, trades=trades, equity=equity)


def export_stored(record: StoredBacktest, payload: dict, fmt: str, out_dir: Path) -> Path:
    if fmt == "pdf":
        from ..reporting.pdf_exporter import PdfExporter  # lazy: optional dependency
        exporter = PdfExporter()
    else:
        try:
            exporter = _EXPORTERS[fmt]()
        except KeyError as exc:
            raise ValueError(f"Unknown export format {fmt!r}") from exc
    ctx = context_from_stored(record, payload)
    return exporter.export(ctx, Path(out_dir) / f"{record.run_id}")
