"""Cordware: the stateless host that mounts the configured applications.

v0.8 §3 (`docs/cordware_repository_strategy_v0.8.md`). Cordware owns `/`
and `/health` and imports an application only through its factory, named
in `cordware.main.REGISTRY`.
"""
