"""Operator route package.

Owns the ``/operator`` URL prefix and the ``operator`` OpenAPI tag.
Each feature area is a sibling ``_<area>.py`` sub-module exposing
its own unprefixed ``router``; this package mounts them all.

External imports of the package — only ``app.main`` — pin to the
``router`` symbol exported below.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    _assignments,
    _extracts,
    _instruments,
    _lobby,
    _operations,
    _quick_setup,
    _rule_builder,
    _session_home,
    _settings,
    _setup_invite,
    _setup_rosters,
)

router = APIRouter(prefix="/operator", tags=["operator"])
router.include_router(_lobby.router)
router.include_router(_settings.router)
router.include_router(_session_home.router)
router.include_router(_quick_setup.router)
router.include_router(_setup_rosters.router)
router.include_router(_setup_invite.router)
router.include_router(_assignments.router)
router.include_router(_rule_builder.router)
router.include_router(_operations.router)
router.include_router(_instruments.router)
router.include_router(_extracts.router)
