"""Reference instrument definitions (data, not logic).

These are convenience factory functions for common forex/futures instruments so
tests and examples don't fabricate specs inline. Real deployments load these
from a config file or database; the point is that the numbers live in *data*,
never inside engine logic.
"""
from __future__ import annotations

from .contract_spec import AssetClass, ContractSpec
from .instrument import Instrument
from .session_calendar import ForexWeekendCalendar


def eurusd() -> Instrument:
    """EUR/USD spot FX, standard lot (100k), 5-digit pricing."""
    spec = ContractSpec(
        symbol="EURUSD",
        asset_class=AssetClass.FX,
        tick_size=0.00001,
        tick_value=1.0,          # $1 per 0.00001 move on a 100k lot
        contract_multiplier=100_000,
        quote_currency="USD",
        min_qty=0.01,            # micro lot
        qty_step=0.01,
        pip_size=0.0001,
    )
    return Instrument("EURUSD", spec, ForexWeekendCalendar())


def es_future() -> Instrument:
    """E-mini S&P 500 future: tick 0.25 = $12.50, point value $50."""
    spec = ContractSpec(
        symbol="ES",
        asset_class=AssetClass.FUTURE,
        tick_size=0.25,
        tick_value=12.5,
        contract_multiplier=50,
        quote_currency="USD",
        min_qty=1,
        qty_step=1,
    )
    # CME index futures ~23h; the FX-weekend calendar is a reasonable Phase-1
    # approximation. A CME-specific calendar is a future drop-in adapter.
    return Instrument("ES", spec, ForexWeekendCalendar(day_anchor=__import__("datetime").time(22, 0)))


def instrument_by_symbol(symbol: str):
    """Look up a reference instrument by symbol. Raises KeyError if unknown."""
    factories = {"EURUSD": eurusd, "ES": es_future}
    key = symbol.upper()
    if key not in factories:
        raise KeyError(f"Unknown instrument {symbol!r}. Known: {', '.join(factories)}")
    return factories[key]()


def available_instruments() -> tuple[str, ...]:
    return ("EURUSD", "ES")
