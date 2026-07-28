"""Registry facade: auto-discovers the indicator library and instantiates by name."""
from __future__ import annotations

import importlib
import pkgutil

from .base import INDICATOR_REGISTRY, Indicator

_DISCOVERED = False


def discover() -> None:
    """Import every module under ``indicators.library`` so their
    ``__init_subclass__`` hooks register the indicators. Idempotent."""
    global _DISCOVERED
    if _DISCOVERED:
        return
    from . import library

    for mod in pkgutil.iter_modules(library.__path__):
        if mod.name.startswith("_"):
            continue  # private helpers (e.g. _smoothing) are not indicators
        importlib.import_module(f"{library.__name__}.{mod.name}")
    _DISCOVERED = True


def available() -> tuple[str, ...]:
    discover()
    return tuple(sorted(INDICATOR_REGISTRY))


def create(name: str, **params: float) -> Indicator:
    """Instantiate a registered indicator by name."""
    discover()
    try:
        cls = INDICATOR_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown indicator {name!r}. Available: {', '.join(available())}"
        ) from exc
    return cls(**params)
