"""Validation pipeline: runs every registered validator and aggregates issues."""
from __future__ import annotations

import polars as pl

from .base import ValidationContext, Validator
from .report import ValidationReport
from .validators import (
    DuplicateTimestampValidator,
    EmptyDatasetValidator,
    MissingCandleValidator,
    MonotonicTimestampValidator,
    NullTimestampValidator,
    OhlcSanityValidator,
    TimeframeConsistencyValidator,
)

# Default registry. Extending validation = append one entry here.
DEFAULT_VALIDATORS: tuple[Validator, ...] = (
    EmptyDatasetValidator(),
    NullTimestampValidator(),
    MonotonicTimestampValidator(),
    DuplicateTimestampValidator(),
    OhlcSanityValidator(),
    TimeframeConsistencyValidator(),
    MissingCandleValidator(),
)


class ValidationPipeline:
    def __init__(self, validators: tuple[Validator, ...] = DEFAULT_VALIDATORS) -> None:
        self._validators = validators

    def run(self, df: pl.DataFrame, ctx: ValidationContext) -> ValidationReport:
        issues: list = []
        for validator in self._validators:
            issues.extend(validator.check(df, ctx))
        return ValidationReport(tuple(issues))
