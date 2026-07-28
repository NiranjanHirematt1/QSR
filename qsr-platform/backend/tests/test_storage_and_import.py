from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl
import pytest

from qsr.application.import_dataset import ImportDataset, ImportRequest
from qsr.data.ingestion.column_mapping import ColumnMapping
from qsr.data.ingestion.readers import CsvReader, ParquetReader
from qsr.data.storage.parquet_store import ParquetCandleRepository
from qsr.data.storage.sqlite_catalog import SqliteCatalogRepository
from qsr.domain.instruments.catalog import eurusd
from qsr.domain.market_data.timeframe import Timeframe

M1 = Timeframe.from_label("M1")


def _write_csv(path: Path, minutes: int, gap_at: int | None = None) -> None:
    start = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    lines = ["Date,Time,Open,High,Low,Close,Volume"]
    for i in range(minutes):
        if gap_at is not None and i == gap_at:
            continue
        t = start + timedelta(minutes=i)
        lines.append(f"{t:%Y-%m-%d},{t:%H:%M},1.1000,1.1005,1.0995,1.1002,{100+i}")
    path.write_text("\n".join(lines))


def test_parquet_roundtrip(tmp_path, clean_m1):
    repo = ParquetCandleRepository(tmp_path)
    repo.write("ds1", clean_m1)
    back = repo.read("ds1")
    assert back.equals(clean_m1.select(back.columns))


def test_sqlite_catalog_roundtrip(tmp_path):
    from qsr.data.storage.models import DatasetMeta
    cat = SqliteCatalogRepository(tmp_path / "catalog.sqlite")
    meta = DatasetMeta("ds1", "EURUSD", "M1", "csv", 10,
                       datetime(2024, 1, 2, tzinfo=timezone.utc),
                       datetime(2024, 1, 2, 1, tzinfo=timezone.utc),
                       "abc", datetime.now(timezone.utc), "{}")
    cat.save(meta)
    assert cat.get("ds1").symbol == "EURUSD"
    assert len(cat.list_all()) == 1


def test_import_clean_dataset_persists(tmp_path):
    csv = tmp_path / "eurusd.csv"
    _write_csv(csv, minutes=30)
    uc = ImportDataset(
        reader_for={"csv": CsvReader(), "parquet": ParquetReader()},
        candles=ParquetCandleRepository(tmp_path / "data"),
        catalog=SqliteCatalogRepository(tmp_path / "catalog.sqlite"),
    )
    req = ImportRequest(csv, eurusd(), M1,
                        ColumnMapping(date="Date", time="Time", datetime_format="%Y-%m-%d %H:%M"),
                        "csv")
    result = uc.execute(req)
    assert result.persisted
    assert result.row_count == 30
    assert result.report.is_clean, result.report.to_dict()


def test_import_rejects_dataset_with_errors(tmp_path):
    csv = tmp_path / "dupes.csv"
    # two identical timestamps -> duplicate ERROR -> must not persist
    csv.write_text(
        "Date,Time,Open,High,Low,Close,Volume\n"
        "2024-01-02,09:00,1.1,1.2,1.0,1.15,10\n"
        "2024-01-02,09:00,1.1,1.2,1.0,1.15,10\n"
    )
    catalog = SqliteCatalogRepository(tmp_path / "catalog.sqlite")
    uc = ImportDataset(
        reader_for={"csv": CsvReader()},
        candles=ParquetCandleRepository(tmp_path / "data"),
        catalog=catalog,
    )
    req = ImportRequest(csv, eurusd(), M1,
                        ColumnMapping(date="Date", time="Time", datetime_format="%Y-%m-%d %H:%M"),
                        "csv")
    result = uc.execute(req)
    assert not result.persisted
    assert result.report.has_errors
    assert catalog.list_all() == []
