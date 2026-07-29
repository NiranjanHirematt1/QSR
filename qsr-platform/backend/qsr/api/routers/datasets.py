"""Dataset import & listing endpoints."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ...application.import_dataset import ImportDataset, ImportRequest
from ...data.ingestion.column_mapping import ColumnMapping
from ...data.ingestion.errors import IngestionError
from ...data.ingestion.readers import CsvReader, ParquetReader
from ...domain.instruments.catalog import instrument_by_symbol
from ...domain.market_data.timeframe import Timeframe
from ..deps import candle_repo, catalog_repo
from ..schemas import DatasetSummary, ImportResponse

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetSummary])
def list_datasets() -> list[DatasetSummary]:
    return [
        DatasetSummary(dataset_id=m.dataset_id, symbol=m.symbol,
                       base_timeframe=m.base_timeframe, row_count=m.row_count,
                       start=m.start.isoformat(), end=m.end.isoformat())
        for m in catalog_repo().list_all()
    ]


@router.get("/{dataset_id}/validation")
def dataset_validation(dataset_id: str) -> dict:
    meta = catalog_repo().get(dataset_id)
    if meta is None:
        raise HTTPException(404, f"dataset {dataset_id} not found")
    return json.loads(meta.validation_json)


@router.get("/{dataset_id}/candles")
def dataset_candles(dataset_id: str, limit: int = 5000) -> list[dict]:
    """OHLCV candles for charting. `time` is UNIX seconds (UTC), the format
    TradingView Lightweight Charts expects."""
    from ...data.ingestion.schema import CLOSE, HIGH, LOW, OPEN, TS, VOLUME
    if catalog_repo().get(dataset_id) is None:
        raise HTTPException(404, f"dataset {dataset_id} not found")
    df = candle_repo().read(dataset_id).sort(TS).tail(max(1, min(limit, 50000)))
    rows = df.select(TS, OPEN, HIGH, LOW, CLOSE, VOLUME).iter_rows()
    return [{"time": int(ts.timestamp()), "open": o, "high": h, "low": l,
             "close": c, "volume": v} for ts, o, h, l, c, v in rows]


@router.post("", response_model=ImportResponse)
async def import_dataset(
    file: UploadFile = File(...),
    symbol: str = Form(...),
    base_timeframe_seconds: int = Form(300),
    source_format: str = Form("csv"),
    # All mapping fields are optional overrides. Left unset, the reader
    # auto-detects delimiter, header, columns and timestamp format — so
    # standard CSV, TSV, MT4 and MT5 exports import without configuration.
    datetime_col: str | None = Form(None),
    date_col: str | None = Form(None),
    time_col: str | None = Form(None),
    datetime_format: str | None = Form(None),
    source_tz: str = Form("UTC"),
    epoch_unit: str | None = Form(None),
) -> ImportResponse:
    try:
        instrument = instrument_by_symbol(symbol)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc

    if base_timeframe_seconds <= 0:
        raise HTTPException(400, "base_timeframe_seconds must be a positive integer")
    if source_format not in ("csv", "parquet"):
        raise HTTPException(400, f"Unsupported source_format {source_format!r}; use 'csv' or 'parquet'")

    tmp_dir = Path(tempfile.mkdtemp())
    tmp = tmp_dir / (file.filename or "upload")
    try:
        with tmp.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)

        mapping = ColumnMapping(datetime=datetime_col, date=date_col, time=time_col,
                                datetime_format=datetime_format, source_tz=source_tz,
                                epoch_unit=epoch_unit)
        uc = ImportDataset(reader_for={"csv": CsvReader(), "parquet": ParquetReader()},
                           candles=candle_repo(), catalog=catalog_repo())
        try:
            result = uc.execute(ImportRequest(
                tmp, instrument, Timeframe(base_timeframe_seconds), mapping, source_format))
        except IngestionError as exc:
            # File cannot be read into the canonical schema — a client error,
            # reported as an informative 400 rather than an opaque 500.
            raise HTTPException(400, str(exc)) from exc
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return ImportResponse(dataset_id=result.dataset_id, persisted=result.persisted,
                          row_count=result.row_count, validation=result.report.to_dict())
