"""Validation issue + report value objects."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class IssueCode(str, Enum):
    MISSING_CANDLES = "MISSING_CANDLES"
    DUPLICATE_TIMESTAMP = "DUPLICATE_TIMESTAMP"
    INVALID_OHLC = "INVALID_OHLC"
    WRONG_TIMEFRAME = "WRONG_TIMEFRAME"
    TIMEZONE_ANOMALY = "TIMEZONE_ANOMALY"
    NON_MONOTONIC = "NON_MONOTONIC"
    EMPTY_DATASET = "EMPTY_DATASET"
    NULL_TIMESTAMP = "NULL_TIMESTAMP"


@dataclass(frozen=True, slots=True)
class Issue:
    code: IssueCode
    severity: Severity
    message: str
    count: int = 1
    sample_timestamps: tuple[datetime, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[Issue, ...]

    @property
    def has_errors(self) -> bool:
        return any(i.severity is Severity.ERROR for i in self.issues)

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    def by_code(self, code: IssueCode) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.code == code)

    def to_dict(self) -> dict:
        return {
            "has_errors": self.has_errors,
            "issues": [
                {
                    "code": i.code.value,
                    "severity": i.severity.value,
                    "message": i.message,
                    "count": i.count,
                    "sample_timestamps": [ts.isoformat() for ts in i.sample_timestamps],
                }
                for i in self.issues
            ],
        }
