"""Built-in strategy library + registry (Python authoring frontend).

Strategies are selected by name via the API, instantiated with parameters, and
driven by the engine through ``PythonStrategyAdapter`` — the engine never learns
they are Python. Adding a strategy = one new file under ``library/``.
"""
