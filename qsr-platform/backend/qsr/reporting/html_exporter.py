"""Self-contained HTML report with an inline SVG equity curve (no JS/CDN deps)."""
from __future__ import annotations

from html import escape
from pathlib import Path

from .context import ReportContext


def _svg_equity(equity, width=900, height=260, pad=30) -> str:
    if len(equity) < 2:
        return "<p>Not enough data for an equity curve.</p>"
    vals = [e for _, e in equity]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = pad + (width - 2 * pad) * i / (n - 1)
        y = height - pad - (height - 2 * pad) * (v - lo) / rng
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#0e1117"/>'
        f'<polyline fill="none" stroke="#4fd1c5" stroke-width="2" points="{poly}"/>'
        f'<text x="{pad}" y="18" fill="#9aa" font-size="12">equity {lo:.0f} .. {hi:.0f}</text>'
        f"</svg>"
    )


def _metrics_table(ctx: ReportContext) -> str:
    t = ctx.report.trades
    r = ctx.report.risk
    rows = [
        ("Net profit", f"{t.net_profit:,.2f}"),
        ("Trades", t.count),
        ("Win rate", f"{t.win_rate*100:.1f}%"),
        ("Profit factor", "n/a" if t.profit_factor is None else f"{t.profit_factor:.2f}"),
        ("Expectancy", f"{t.expectancy:,.2f}"),
        ("Avg R", "n/a" if t.avg_r is None else f"{t.avg_r:.2f}"),
        ("Max consecutive losses", t.max_consecutive_losses),
        ("Max drawdown", f"{r.max_drawdown_pct:.2f}% ({r.max_drawdown_abs:,.2f})"),
        ("Recovery factor", "n/a" if r.recovery_factor is None else f"{r.recovery_factor:.2f}"),
        ("Sharpe", "n/a" if r.sharpe is None else f"{r.sharpe:.2f}"),
        ("Sortino", "n/a" if r.sortino is None else f"{r.sortino:.2f}"),
        ("Calmar", "n/a" if r.calmar is None else f"{r.calmar:.2f}"),
    ]
    body = "".join(f"<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>" for k, v in rows)
    return f"<table class='metrics'>{body}</table>"


def _trades_table(ctx: ReportContext, limit=200) -> str:
    head = ("<tr><th>#</th><th>Side</th><th>Qty</th><th>Entry</th><th>Exit</th>"
            "<th>PnL</th><th>R</th><th>Why in</th><th>Why out</th></tr>")
    rows = []
    for i, t in enumerate(ctx.trades[:limit], 1):
        r = "" if t.r_multiple is None else f"{t.r_multiple:.2f}"
        cls = "win" if t.pnl > 0 else "loss"
        rows.append(
            f"<tr class='{cls}'><td>{i}</td><td>{t.side.value}</td><td>{t.qty:g}</td>"
            f"<td>{t.entry_price:g}</td><td>{t.exit_price:g}</td><td>{t.pnl:,.2f}</td>"
            f"<td>{r}</td><td>{escape(t.entry_reason or '')}</td><td>{escape(t.exit_reason or '')}</td></tr>")
    return f"<table class='trades'>{head}{''.join(rows)}</table>"


_CSS = """
body{font-family:system-ui,Arial,sans-serif;background:#0b0d12;color:#e6e6e6;margin:0;padding:24px}
h1{font-size:20px}h2{font-size:15px;margin-top:28px;color:#9aa}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}
td,th{border:1px solid #222;padding:6px 8px;text-align:left}
.metrics td:first-child{color:#9aa;width:240px}
tr.win td:nth-child(6){color:#4fd1c5}tr.loss td:nth-child(6){color:#f56565}
"""


class HtmlExporter:
    extension = "html"

    def export(self, ctx: ReportContext, path: Path) -> Path:
        path = Path(path).with_suffix(".html")
        path.write_text(self.to_html(ctx))
        return path

    def to_html(self, ctx: ReportContext) -> str:
        return (
            f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{escape(ctx.title)}</title><style>{_CSS}</style></head><body>"
            f"<h1>{escape(ctx.title)}</h1>"
            f"<p>Run {escape(ctx.manifest.get('run_hash','')[:16])} · "
            f"{escape(str(ctx.manifest.get('instrument','')))} · "
            f"{escape(str(ctx.manifest.get('base_timeframe','')))}</p>"
            f"<h2>Equity curve</h2>{_svg_equity(ctx.equity)}"
            f"<h2>Performance</h2>{_metrics_table(ctx)}"
            f"<h2>Trades</h2>{_trades_table(ctx)}"
            f"</body></html>"
        )
