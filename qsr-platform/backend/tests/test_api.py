"""End-to-end API tests via FastAPI TestClient: import -> run -> fetch -> export."""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("QSR_DATA_DIR", str(tmp_path / "data"))
    # deps use lru_cache; clear so the temp data dir takes effect per test
    from qsr.api import deps
    for fn in (deps._data_root, deps.candle_repo, deps.catalog_repo,
               deps.backtest_repo, deps.backtest_service):
        fn.cache_clear()
    from qsr.api.main import create_app
    return TestClient(create_app())


def _csv_bytes(n=400):
    start = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
    lines = ["Date,Time,Open,High,Low,Close,Volume"]
    import math
    for i in range(n):
        t = start + timedelta(minutes=5 * i)
        p = 4000 + 40 * math.sin(i / 30)
        o, c = p, p + math.sin(i)
        h, l = max(o, c) + 1, min(o, c) - 1
        lines.append(f"{t:%Y-%m-%d},{t:%H:%M},{o:.2f},{h:.2f},{l:.2f},{c:.2f},1000")
    return "\n".join(lines).encode()


def _import(client) -> str:
    files = {"file": ("es.csv", io.BytesIO(_csv_bytes()), "text/csv")}
    data = {"symbol": "ES", "base_timeframe_seconds": "300", "source_format": "csv"}
    r = client.post("/datasets", files=files, data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["persisted"] and body["row_count"] == 400
    return body["dataset_id"]


def test_health_and_catalog(client):
    assert client.get("/health").json()["status"] == "ok"
    strategies = client.get("/strategies").json()
    names = {s["name"] for s in strategies}
    assert {"ema_crossover", "rsi_reversion"} <= names
    assert "ema" in client.get("/indicators").json()
    assert "ES" in client.get("/instruments").json()


def test_import_list_validation(client):
    ds = _import(client)
    listed = client.get("/datasets").json()
    assert any(d["dataset_id"] == ds for d in listed)
    v = client.get(f"/datasets/{ds}/validation").json()
    assert v["has_errors"] is False


def test_run_backtest_and_fetch(client):
    ds = _import(client)
    req = {"dataset_id": ds, "symbol": "ES", "base_timeframe_seconds": 300,
           "strategy": "ema_crossover", "params": {"fast": 10, "slow": 30},
           "config": {"commission_per_unit": 2.0, "slippage_ticks": 1}}
    r = client.post("/backtests", json=req)
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    assert r.json()["trade_count"] >= 1

    perf = client.get(f"/backtests/{run_id}/performance").json()
    assert "trades" in perf and "risk" in perf
    trades = client.get(f"/backtests/{run_id}/trades").json()
    assert len(trades) == r.json()["trade_count"]
    equity = client.get(f"/backtests/{run_id}/equity").json()
    assert len(equity) > 100
    assert any(b["run_id"] == run_id for b in client.get("/backtests").json())


def test_exports(client):
    ds = _import(client)
    req = {"dataset_id": ds, "symbol": "ES", "strategy": "rsi_reversion", "params": {}}
    run_id = client.post("/backtests", json=req).json()["run_id"]
    for fmt, sig in [("json", b"{"), ("csv", b"instrument"), ("html", b"<!doctype html")]:
        r = client.get(f"/backtests/{run_id}/export", params={"fmt": fmt})
        assert r.status_code == 200, (fmt, r.text)
        assert r.content[:20].lower().startswith(sig[:10].lower()) or sig in r.content[:64]


def test_errors(client):
    assert client.get("/backtests/nope/performance").status_code == 404
    bad = {"dataset_id": "x", "symbol": "ES", "strategy": "does_not_exist"}
    assert client.post("/backtests", json=bad).status_code == 400


def test_compare_two_runs(client):
    ds = _import(client)
    ids = []
    for strat in ("ema_crossover", "rsi_reversion"):
        r = client.post("/backtests", json={"dataset_id": ds, "symbol": "ES",
                                            "strategy": strat, "params": {}})
        ids.append(r.json()["run_id"])
    r = client.post("/compare", json={"run_ids": ids})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["runs"]) == 2
    assert {run["run_id"] for run in body["runs"]} == set(ids)
    assert "net_profit" in body["runs"][0]["metrics"]
    assert len(body["runs"][0]["equity_curve"]) > 10


def test_compare_needs_two(client):
    assert client.post("/compare", json={"run_ids": ["only-one"]}).status_code == 400


def test_dataset_candles(client):
    ds = _import(client)
    candles = client.get(f"/datasets/{ds}/candles", params={"limit": 100}).json()
    assert len(candles) == 100
    c0 = candles[0]
    assert {"time", "open", "high", "low", "close", "volume"} <= set(c0)
    assert isinstance(c0["time"], int)
