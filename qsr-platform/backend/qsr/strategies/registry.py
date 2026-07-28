"""Strategy registry facade: discovery + instantiation by name."""
from __future__ import annotations

import importlib
import pkgutil

from .base import STRATEGY_REGISTRY, RegisteredStrategy

_DISCOVERED = False


def discover() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    from . import library
    for mod in pkgutil.iter_modules(library.__path__):
        if not mod.name.startswith("_"):
            importlib.import_module(f"{library.__name__}.{mod.name}")
    _DISCOVERED = True


def available() -> tuple[str, ...]:
    discover()
    return tuple(sorted(STRATEGY_REGISTRY))


def describe() -> list[dict]:
    discover()
    return [
        {
            "name": name,
            "params": [
                {"name": p.name, "default": p.default, "kind": p.kind, "description": p.description}
                for p in cls.params_schema
            ],
        }
        for name, cls in sorted(STRATEGY_REGISTRY.items())
    ]


def create(name: str, params: dict | None = None) -> RegisteredStrategy:
    discover()
    try:
        cls = STRATEGY_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown strategy {name!r}. Available: {', '.join(available())}") from exc
    return cls(**(params or {}))
