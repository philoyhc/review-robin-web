"""Reviewer route package.

Owns the ``/reviewer`` URL prefix and the ``reviewer`` OpenAPI
tag. Each concern is a sibling sub-module exposing its own
``router`` (each carries the ``/reviewer`` prefix — the dashboard
route is the bare prefix root, so the prefix can't live only on
the parent); this package mounts them all. Split out of the
single-file ``routes_reviewer.py`` in Segment 17B PR 1.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.web.routes_reviewer import _dashboard, _invite, _summary, _surface

router = APIRouter(tags=["reviewer"])
router.include_router(_dashboard.router)
router.include_router(_summary.router)
router.include_router(_surface.router)
router.include_router(_invite.router)

__all__ = ["router"]
