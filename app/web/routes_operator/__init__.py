"""Operator route package.

Owns the ``/operator`` URL prefix and the ``operator`` OpenAPI tag.
Currently mounts a single legacy container holding every operator
route; the ``major_refactor`` ladder (``guide/major_refactor.md``)
peels feature areas out into sibling ``_<area>.py`` modules across
PRs 1-10. Each slice module exposes its own unprefixed
``router`` and is included here.

External imports of the package — only ``app.main`` — pin to the
``router`` symbol exported below; that name stays stable across the
ladder.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    _assignments,
    _legacy,
    _lobby,
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
router.include_router(_legacy.router)
