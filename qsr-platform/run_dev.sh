#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# QSR — one-command local launcher.
# Starts the FastAPI backend (:8000) and the Next.js frontend (:3000),
# auto-installing dependencies on first run. Ctrl-C stops both.
#
#   Usage:  bash run_dev.sh
# Requirements: Python 3.11+, Node.js 18+.
# ---------------------------------------------------------------------------
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
export QSR_DATA_DIR="${QSR_DATA_DIR:-$here/backend/data}"

echo "==> QSR local launcher"

# --- Backend dependencies ---------------------------------------------------
if ! python -c "import qsr" >/dev/null 2>&1; then
  echo "==> Installing backend (pip install -e .) ..."
  ( cd "$here/backend" && pip install -e ".[dev]" >/dev/null )
fi

# --- Frontend dependencies --------------------------------------------------
if [ ! -x "$here/frontend/node_modules/.bin/next" ]; then
  echo "==> Installing frontend (npm install) ..."
  ( cd "$here/frontend" && npm install --no-fund --no-audit )
fi

# --- Launch both ------------------------------------------------------------
( cd "$here/backend" && python -m uvicorn qsr.api.main:app --port 8000 ) &
back=$!
( cd "$here/frontend" && npm run dev ) &
front=$!
trap 'echo; echo "==> Stopping..."; kill $back $front 2>/dev/null || true' EXIT INT TERM

echo ""
echo "  Backend  API   -> http://localhost:8000        (docs: http://localhost:8000/docs)"
echo "  Frontend UI    -> http://localhost:3000"
echo "  Sample data    -> backend/sample_data/
ES_M5_sample.csv (import it on the dashboard)"
echo ""
wait
