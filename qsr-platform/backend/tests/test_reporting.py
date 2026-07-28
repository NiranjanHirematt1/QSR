"""Reporting exporter tests (JSON/CSV/HTML/PDF) over a real backtest context."""
from __future__ import annotations

from pathlib import Path

import pytest

from qsr.application.analyze_backtest import context_from_result
from qsr.domain.instruments.catalog import es_future
from qsr.domain.orders.intents import SizeKind, SizeSpec
from qsr.domain.strategy.adapter import StrategyRequirements
from qsr.domain.strategy.base import PythonStrategyAdapter, Strategy
from qsr.engine.backtester import Backtester
from qsr.engine.config import BacktestConfig
from qsr.reporting.csv_exporter import CsvExporter
from qsr.reporting.html_exporter import HtmlExporter
from qsr.reporting.json_exporter import JsonExporter
from tests.engine_helpers import M5, series


class _Flip(Strategy):
    def initialize(self): return StrategyRequirements(timeframes=(M5,))
    def on_bar(self):
        if self.ctx.position_qty == 0:
            self.buy(SizeSpec(SizeKind.FIXED_QTY, 1), reason="in")
            self.set_takeprofit(ticks=20); self.set_stoploss(ticks=20)


@pytest.fixture()
def ctx():
    candles = series([(4000, 4006, 3994, 4000 + (4 if i % 3 else -3)) for i in range(80)])
    res = Backtester(es_future(), M5, BacktestConfig(commission_per_unit=2)).run(
        candles, PythonStrategyAdapter(_Flip()), strategy_id="flip")
    return context_from_result(res, M5, title="Flip Test")


def test_json_export(ctx, tmp_path):
    p = JsonExporter().export(ctx, tmp_path / "r")
    import json
    data = json.loads(p.read_text())
    assert data["title"] == "Flip Test"
    assert "performance" in data and "trades" in data and "equity_curve" in data


def test_csv_export(ctx, tmp_path):
    p = CsvExporter().export(ctx, tmp_path / "r")
    lines = p.read_text().splitlines()
    assert lines[0].startswith("instrument,side,qty")
    assert len(lines) == len(ctx.trades) + 1


def test_html_export_self_contained(ctx, tmp_path):
    p = HtmlExporter().export(ctx, tmp_path / "r")
    html = p.read_text()
    assert html.startswith("<!doctype html>")
    assert "<svg" in html and "Performance" in html
    assert "cdn" not in html.lower()  # no external dependencies


def test_pdf_export(ctx, tmp_path):
    reportlab = pytest.importorskip("reportlab")
    from qsr.reporting.pdf_exporter import PdfExporter
    p = PdfExporter().export(ctx, tmp_path / "r")
    assert p.exists() and p.read_bytes()[:5] == b"%PDF-"


def test_export_stored_roundtrip(tmp_path):
    # exercise the reporting_service path used by the API export endpoint
    import json
    from datetime import datetime, timezone
    from qsr.data.storage.models import StoredBacktest
    from qsr.application.reporting_service import export_stored

    candles = series([(4000, 4006, 3994, 4000 + (4 if i % 3 else -3)) for i in range(60)])
    res = Backtester(es_future(), M5, BacktestConfig()).run(
        candles, PythonStrategyAdapter(_Flip()), strategy_id="flip")
    payload = context_from_result(res, M5, title="T").to_dict()
    rec = StoredBacktest("rid", "flip", "ES", "M5", "ds", datetime.now(timezone.utc),
                         res.net_profit, res.trade_count, "{}", json.dumps(payload, default=str))
    out = export_stored(rec, payload, "html", tmp_path)
    assert out.exists() and out.read_text().startswith("<!doctype html>")
