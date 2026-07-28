"""ImportDataset use-case — orchestrates Module 1 end to end.

Read source -> normalise -> validate -> (reject on ERROR) -> persist candles +
catalog metadata. This layer contains *orchestration only*; all rules live in
the domain/data layers it composes. Dependencies are injected, so the use-case
is trivially testable with in-memory or temp-dir repositories.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from ..data.ingestion.base import CandleSource
from ..data.ingestion.column_mapping import ColumnMapping
from ..data.ingestion.schema import TS
from ..data.storage.base import CandleRepository, CatalogRepository
from ..data.storage.models import DatasetMeta
from ..data.validation.base import ValidationContext
from ..data.validation.pipeline import ValidationPipeline
from ..data.validation.report import ValidationReport
from ..domain.instruments.instrument import Instrument
from ..domain.market_data.timeframe import Timeframe


@dataclass(frozen=True, slots=True)
class ImportRequest:
    path: Path
    instrument: Instrument
    base_timeframe: Timeframe
    mapping: ColumnMapping
    source_format: str  # "csv" | "parquet"


@dataclass(frozen=True, slots=True)
class ImportResult:
    dataset_id: str
    report: ValidationReport
    persisted: bool
    row_count: int


class ImportDataset:
    def __init__(
        self,
        reader_for: dict[str, CandleSource],
        candles: CandleRepository,
        catalog: CatalogRepository,
        pipeline: ValidationPipeline | None = None,
    ) -> None:
        self._reader_for = reader_for
        self._candles = candles
        self._catalog = catalog
        self._pipeline = pipeline or ValidationPipeline()

    def execute(self, req: ImportRequest) -> ImportResult:
        reader = self._reader_for.get(req.source_format)
        if reader is None:
            raise ValueError(f"No reader registered for format {req.source_format!r}")

        df = reader.read(req.path, req.mapping)

        ctx = ValidationContext(req.base_timeframe, req.instrument.calendar)
        report = self._pipeline.run(df, ctx)

        dataset_id = uuid.uuid4().hex
        # Fail closed: never persist a dataset with hard errors into research.
        if report.has_errors:
            return ImportResult(dataset_id, report, persisted=False, row_count=df.height)

        self._candles.write(dataset_id, df)
        self._catalog.save(self._build_meta(dataset_id, req, df, report))
        return ImportResult(dataset_id, report, persisted=True, row_count=df.height)

    @staticmethod
    def _build_meta(
        dataset_id: str, req: ImportRequest, df: pl.DataFrame, report: ValidationReport
    ) -> DatasetMeta:
        import json

        checksum = hashlib.sha256(df.write_csv().encode()).hexdigest()
        ts = df.get_column(TS)
        return DatasetMeta(
            dataset_id=dataset_id,
            symbol=req.instrument.symbol,
            base_timeframe=req.base_timeframe.label,
            source_format=req.source_format,
            row_count=df.height,
            start=ts.min(),  # type: ignore[arg-type]
            end=ts.max(),    # type: ignore[arg-type]
            checksum=checksum,
            imported_at=datetime.now(timezone.utc),
            validation_json=json.dumps(report.to_dict()),
        )
