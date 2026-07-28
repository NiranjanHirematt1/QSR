"""SQLite-backed BacktestResultRepository (metadata + JSON payload)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .models import StoredBacktest

_SCHEMA = """
CREATE TABLE IF NOT EXISTS backtests (
    run_id         TEXT PRIMARY KEY,
    strategy_id    TEXT NOT NULL,
    instrument     TEXT NOT NULL,
    base_timeframe TEXT NOT NULL,
    dataset_id     TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    net_profit     REAL NOT NULL,
    trade_count    INTEGER NOT NULL,
    manifest_json  TEXT NOT NULL,
    result_json    TEXT NOT NULL
);
"""


class SqliteBacktestRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        return con

    def save(self, record: StoredBacktest) -> None:
        with self._connect() as con:
            con.execute(
                """INSERT OR REPLACE INTO backtests VALUES
                   (:run_id,:strategy_id,:instrument,:base_timeframe,:dataset_id,
                    :created_at,:net_profit,:trade_count,:manifest_json,:result_json)""",
                {
                    "run_id": record.run_id,
                    "strategy_id": record.strategy_id,
                    "instrument": record.instrument,
                    "base_timeframe": record.base_timeframe,
                    "dataset_id": record.dataset_id,
                    "created_at": record.created_at.isoformat(),
                    "net_profit": record.net_profit,
                    "trade_count": record.trade_count,
                    "manifest_json": record.manifest_json,
                    "result_json": record.result_json,
                },
            )

    def get(self, run_id: str) -> StoredBacktest | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM backtests WHERE run_id = ?", (run_id,)).fetchone()
        return self._to_model(row) if row else None

    def list_all(self) -> list[StoredBacktest]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM backtests ORDER BY created_at DESC").fetchall()
        return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(row: sqlite3.Row) -> StoredBacktest:
        return StoredBacktest(
            run_id=row["run_id"], strategy_id=row["strategy_id"], instrument=row["instrument"],
            base_timeframe=row["base_timeframe"], dataset_id=row["dataset_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            net_profit=row["net_profit"], trade_count=row["trade_count"],
            manifest_json=row["manifest_json"], result_json=row["result_json"])
