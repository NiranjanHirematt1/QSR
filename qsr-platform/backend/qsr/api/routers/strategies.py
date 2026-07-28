"""Strategy & instrument discovery endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ...domain.instruments.catalog import available_instruments
from ...indicators import registry as indicator_registry
from ...strategies import registry as strategy_registry
from ..schemas import StrategyInfo

router = APIRouter(tags=["catalog"])


@router.get("/strategies", response_model=list[StrategyInfo])
def list_strategies() -> list[StrategyInfo]:
    return [StrategyInfo(**s) for s in strategy_registry.describe()]


@router.get("/indicators")
def list_indicators() -> list[str]:
    return list(indicator_registry.available())


@router.get("/instruments")
def list_instruments() -> list[str]:
    return list(available_instruments())
