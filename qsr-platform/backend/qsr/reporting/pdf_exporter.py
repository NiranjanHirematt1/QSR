"""PDF export via reportlab — a summary page with key metrics and the trade list.

reportlab is a pure-Python, local dependency (no system libraries), consistent
with the 'local application, no heavy infra' constraint. Imported lazily so the
rest of the reporting package works even if reportlab is absent.
"""
from __future__ import annotations

from pathlib import Path

from .context import ReportContext


class PdfExporter:
    extension = "pdf"

    def export(self, ctx: ReportContext, path: Path) -> Path:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)

        path = Path(path).with_suffix(".pdf")
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(str(path), pagesize=A4,
                                title=ctx.title, leftMargin=18 * mm, rightMargin=18 * mm)
        t, r = ctx.report.trades, ctx.report.risk
        story = [
            Paragraph(ctx.title, styles["Title"]),
            Paragraph(f"{ctx.manifest.get('instrument','')} · "
                      f"{ctx.manifest.get('base_timeframe','')} · "
                      f"run {ctx.manifest.get('run_hash','')[:16]}", styles["Normal"]),
            Spacer(1, 8 * mm),
            Paragraph("Performance", styles["Heading2"]),
        ]
        metrics = [
            ["Net profit", f"{t.net_profit:,.2f}"],
            ["Trades", str(t.count)],
            ["Win rate", f"{t.win_rate*100:.1f}%"],
            ["Profit factor", "n/a" if t.profit_factor is None else f"{t.profit_factor:.2f}"],
            ["Expectancy", f"{t.expectancy:,.2f}"],
            ["Avg R", "n/a" if t.avg_r is None else f"{t.avg_r:.2f}"],
            ["Max drawdown", f"{r.max_drawdown_pct:.2f}% ({r.max_drawdown_abs:,.2f})"],
            ["Sharpe", "n/a" if r.sharpe is None else f"{r.sharpe:.2f}"],
            ["Sortino", "n/a" if r.sortino is None else f"{r.sortino:.2f}"],
            ["Calmar", "n/a" if r.calmar is None else f"{r.calmar:.2f}"],
        ]
        mt = Table(metrics, colWidths=[70 * mm, 70 * mm])
        mt.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ]))
        story += [mt, Spacer(1, 8 * mm), Paragraph("Trades (first 40)", styles["Heading2"])]

        head = ["#", "Side", "Qty", "Entry", "Exit", "PnL", "R", "Exit reason"]
        rows = [head]
        for i, tr in enumerate(ctx.trades[:40], 1):
            rows.append([str(i), tr.side.value, f"{tr.qty:g}", f"{tr.entry_price:g}",
                         f"{tr.exit_price:g}", f"{tr.pnl:,.2f}",
                         "" if tr.r_multiple is None else f"{tr.r_multiple:.2f}",
                         (tr.exit_reason or "")[:18]])
        tt = Table(rows, repeatRows=1)
        tt.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(tt)
        doc.build(story)
        return path
