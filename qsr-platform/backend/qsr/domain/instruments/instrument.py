"""Instrument entity — binds a symbol to its economics and trading calendar."""
from __future__ import annotations

from dataclasses import dataclass

from .contract_spec import ContractSpec
from .session_calendar import SessionCalendar


@dataclass(frozen=True, slots=True)
class Instrument:
    """A tradable instrument: a symbol plus its :class:`ContractSpec` and
    :class:`SessionCalendar`. This is the object strategies and the engine key
    off; nothing hardcodes instrument behaviour."""

    symbol: str
    spec: ContractSpec
    calendar: SessionCalendar

    @property
    def quote_currency(self) -> str:
        return self.spec.quote_currency
