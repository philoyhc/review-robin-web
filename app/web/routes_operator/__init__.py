"""Operator route package.

Owns the ``/operator`` URL prefix and the ``operator`` OpenAPI tag.
Each feature area is a sibling ``_<area>.py`` sub-module exposing
its own unprefixed ``router``; this package mounts them all.

External imports of the package — only ``app.main`` — pin to the
``router`` symbol exported below.

The parent ``APIRouter`` carries the Segment 16A PR 1 operator
allowlist gate (``require_operator``) so every route mounted
underneath gates uniformly on
``is_operator OR is_sys_admin``. Non-operators are bounced to
``/request-access`` via the ``OperatorAllowlistDenied`` exception
handler in ``app/main.py``. Per-session permission checks
(``require_session_operator``) continue to compose on top.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.web.deps import require_operator

from . import (
    _assignments,
    _extracts,
    _instruments,
    _lobby,
    _operations,
    _quick_setup,
    _response_types,
    _rule_builder,
    _session_home,
    _settings,
    _setup_invite,
    _setup_relationships,
    _setup_reviewees,
    _setup_reviewers,
    _sys_admin,
    _workflow,
)

router = APIRouter(
    prefix="/operator",
    tags=["operator"],
    dependencies=[Depends(require_operator)],
)
router.include_router(_lobby.router)
router.include_router(_settings.router)
router.include_router(_session_home.router)
router.include_router(_quick_setup.router)
router.include_router(_setup_reviewers.router)
router.include_router(_setup_reviewees.router)
router.include_router(_setup_relationships.router)
router.include_router(_setup_invite.router)
router.include_router(_assignments.router)
router.include_router(_rule_builder.router)
router.include_router(_operations.router)
router.include_router(_instruments.router)
router.include_router(_response_types.router)
router.include_router(_extracts.router)
router.include_router(_sys_admin.router)
router.include_router(_workflow.router)
