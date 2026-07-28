"""FastAPI application factory.

Wires the routers into an app. This is a thin HTTP adapter — all behaviour lives
in the application/engine layers it delegates to.
"""
from __future__ import annotations

from fastapi import FastAPI

from .routers import backtests, compare, datasets, strategies


def create_app() -> FastAPI:
    app = FastAPI(
        title="QSR — Quant Strategy Research API",
        version="0.1.0",
        description="Local backtesting research platform (forex/futures, event-driven, multi-timeframe).",
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(strategies.router)
    app.include_router(datasets.router)
    app.include_router(backtests.router)
    app.include_router(compare.router)
    return app


app = create_app()
