"""Reporting (Module 9): export a backtest into JSON / CSV / HTML / PDF.

Exporters consume a :class:`ReportContext` assembled from domain trades, the
equity series, the run manifest, and an analytics ``PerformanceReport`` — never
engine types — so the package depends only on domain + analytics.
"""
