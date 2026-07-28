"""Exporter protocol — one method, one responsibility."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .context import ReportContext


@runtime_checkable
class Exporter(Protocol):
    extension: str
    def export(self, ctx: ReportContext, path: Path) -> Path: ...
