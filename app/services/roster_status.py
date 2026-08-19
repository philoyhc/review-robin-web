"""Shared roster-status primitives.

The reviewer / reviewee / observer / relationship services each grew
an identical ``_normalised_status`` (same ``{"active", "inactive"}``
allowlist, same default-to-active fold, differing only in the
``*OperationError`` class raised), and the assignments package
open-coded the same "is this row active?" test (audit S6). This is
the single home.

Kept deliberately dependency-light — no ``audit`` / ``session_lifecycle``
imports — so any slice (including the assignments package) can use it
without an import cycle. The heavier ``roster_bulk.bulk_set_status``
orchestrator lives separately.

See ``guide/consistency_audit.md`` (S6).
"""

from __future__ import annotations

#: The status vocabulary every roster row shares. A row defaults to
#: ``"active"`` when its status is unset.
ROSTER_STATUSES: frozenset[str] = frozenset({"active", "inactive"})


def normalise_status(value: str, *, error_cls: type[Exception]) -> str:
    """Fold ``value`` to the canonical lowercase status, defaulting an
    empty / ``None`` value to ``"active"``.

    Raises ``error_cls("invalid_status", ...)`` for anything outside
    :data:`ROSTER_STATUSES`. Each roster service passes its own
    ``*OperationError`` subclass — the one thing that genuinely
    differs between the callers.
    """
    status = (value or "active").strip().lower()
    if status not in ROSTER_STATUSES:
        raise error_cls(
            "invalid_status",
            f"Status must be one of {sorted(ROSTER_STATUSES)}; got {value!r}.",
        )
    return status


def is_active(row: object) -> bool:
    """True iff a roster row is active — ``status`` unset counts as
    active (the roster default). Accepts any row exposing ``status``."""
    return (getattr(row, "status", None) or "active") == "active"
