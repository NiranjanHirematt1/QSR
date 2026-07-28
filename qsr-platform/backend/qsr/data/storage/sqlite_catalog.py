"""SQLite-backed CatalogRepository.

Holds only metadata — small, relational, transactional. Swapping to PostgreSQL
means writing a sibling class against the same CatalogRepository Protocol; no
caller changes.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import DatasetMeta

_SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id      TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    base_timeframe  TEXT NOT NULL,
    source_format   TEXT NOT NULL,
    row_count       INTEGER NOT NULL,
    start_ts        TEXT NOT NULL,
    end_ts          TEXT NOT NULL,
    checksum        TEXT NOT NULL,
    imported_at     TEXT NOT NULL,
    validation_json TEXT NOT NULL
);
"""


class SqliteCatalogRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        return con

    def save(self, meta: DatasetMeta) -> None:
        with self._connect() as con:
            con.execute(
                """INSERT OR REPLACE INTO datasets VALUES
                   (:dataset_id,:symbol,:base_timeframe,:source_format,:row_count,
                    :start_ts,:end_ts,:checksum,:imported_at,:validation_json)""",
                {
                    "dataset_id": meta.dataset_id,
                    "symbol": meta.symbol,
                    "base_timeframe": meta.base_timeframe,
                    "source_format": meta.source_format,
                    "row_count": meta.row_count,
                    "start_ts": meta.start.isoformat(),
                    "end_ts": meta.end.isoformat(),
                    "checksum": meta.checksum,
                    "imported_at": meta.imported_at.isoformat(),
                    "validation_json": meta.validation_json,
                },
            )

    def get(self, dataset_id: str) -> DatasetMeta | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
        return self._row_to_meta(row) if row else None

    def list_all(self) -> list[DatasetMeta]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM datasets ORDER BY imported_at DESC").fetchall()
        return [self._row_to_meta(r) for r in rows]

    @staticmethod
    def _row_to_meta(row: sqlite3.Row) -> DatasetMeta:
        return DatasetMeta(
            dataset_id=row["dataset_id"],
            symbol=row["symbol"],
            base_timeframe=row["base_timeframe"],
            source_format=row["source_format"],
            row_count=row["row_count"],
            start=datetime.fromisoformat(row["start_ts"]),
            end=datetime.fromisoformat(row["end_ts"]),
            checksum=row["checksum"],
            imported_at=datetime.fromisoformat(row["imported_at"]),
            validation_json=row["validation_json"],
        )
