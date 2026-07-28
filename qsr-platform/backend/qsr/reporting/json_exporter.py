"""JSON export — the machine-readable run record."""
from __future__ import annotations

import json
from pathlib import Path

from .context import ReportContext


class JsonExporter:
    extension = "json"

    def export(self, ctx: ReportContext, path: Path) -> Path:
        path = Path(path).with_suffix(".json")
        path.write_text(json.dumps(ctx.to_dict(), indent=2, default=str))
        return path

    def to_json(self, ctx: ReportContext) -> str:
        return json.dumps(ctx.to_dict(), indent=2, default=str)
