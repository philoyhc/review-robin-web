"""Reviewer route package.

Owns the ``/me`` URL prefix and the ``reviewer`` OpenAPI tag
(folder name stays ``routes_reviewer`` for now —
``guide/archive/url_remodel.md`` discusses the folder rename
as optional polish). Each concern is a sibling sub-module
exposing its own ``router`` (each carries the ``/me`` prefix
— the dashboard route is the bare prefix root, so the
prefix can't live only on the parent); this package mounts
them all. Split out of the single-file ``routes_reviewer.py``
in Segment 17B PR 1.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.web.routes_reviewer import (
    _collation,
    _dashboard,
    _invite,
    _results,
    _summary,
    _surface,
)

router = APIRouter(tags=["reviewer"])
router.include_router(_dashboard.router)
router.include_router(_summary.router)
# Results / collation must be mounted before ``_surface`` — the
# surface's ``/sessions/{id}/{page_n}`` swallows any second
# path segment, so the literal ``/results`` and ``/collation``
# routes need to register first for FastAPI's in-order match.
router.include_router(_results.router)
router.include_router(_collation.router)
router.include_router(_surface.router)
router.include_router(_invite.router)

__all__ = ["router"]
