"""Run manifest — captures everything needed to reproduce a backtest exactly.

The engine uses no wall-clock and no unseeded randomness, so a run is fully
determined by (dataset, strategy, config, engine version). Recording them makes
results reproducible and strategy-vs-strategy comparison (Module 8) meaningful.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

ENGINE_VERSION = "0.1.0"


@dataclass(frozen=True, slots=True)
class RunManifest:
    strategy_id: str
    instrument: str
    base_timeframe: str
    dataset_checksum: str
    config: dict
    engine_version: str = ENGINE_VERSION
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def run_hash(self) -> str:
        payload = json.dumps(
            {
                "strategy_id": self.strategy_id,
                "instrument": self.instrument,
                "base_timeframe": self.base_timeframe,
                "dataset_checksum": self.dataset_checksum,
                "config": self.config,
                "engine_version": self.engine_version,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "instrument": self.instrument,
            "base_timeframe": self.base_timeframe,
            "dataset_checksum": self.dataset_checksum,
            "config": self.config,
            "engine_version": self.engine_version,
            "created_at": self.created_at.isoformat(),
            "run_hash": self.run_hash,
        }
