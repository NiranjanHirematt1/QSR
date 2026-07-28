"""Registered strategy base + registry.

``RegisteredStrategy`` adds auto-registration (by ``name``) on top of the domain
``Strategy`` authoring API, plus a declared parameter schema so the API can list
strategies and validate parameters. The registry lives here (not in the domain)
so the domain stays free of any registry concept.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from ..domain.strategy.base import Strategy

STRATEGY_REGISTRY: dict[str, type["RegisteredStrategy"]] = {}


@dataclass(frozen=True, slots=True)
class ParamSpec:
    name: str
    default: float
    kind: str = "number"
    description: str = ""


class RegisteredStrategy(Strategy):
    """Base for library strategies: sets ``name`` and ``params_schema``."""

    name: ClassVar[str] = ""
    params_schema: ClassVar[tuple[ParamSpec, ...]] = ()

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        key = getattr(cls, "name", "")
        if not key:
            return
        if key in STRATEGY_REGISTRY and STRATEGY_REGISTRY[key] is not cls:
            raise ValueError(f"Duplicate strategy name {key!r}")
        STRATEGY_REGISTRY[key] = cls
