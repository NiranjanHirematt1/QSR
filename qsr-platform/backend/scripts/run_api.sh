#!/usr/bin/env bash
# Launch the QSR research API locally.
set -euo pipefail
export QSR_DATA_DIR="${QSR_DATA_DIR:-./data}"
exec uvicorn qsr.api.main:app --reload --port 8000
