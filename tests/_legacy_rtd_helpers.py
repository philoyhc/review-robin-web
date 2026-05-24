"""Test-only helpers for the Segment 18J Wave 2 PR iii-b2 RTD
retirement.

The pre-iii-b2 seeded RTD set (10 names) is gone in production —
``SEEDED_RESPONSE_TYPE_DEFINITIONS`` is now empty and no row gets
auto-created by ``ensure_default_response_type_definitions``. Many
pre-existing test fixtures look those rows up by name; instead of
rewriting each one, they switch to one of these helpers:

- :func:`make_legacy_rtd` — creates an operator-authored (i.e.
  ``is_seeded=False``) RTD with the well-known shape of one of the
  retired seeded rows. Use when a test needs an RTD instance to
  point at (e.g. exercises FK behaviour, RTD CRUD, library
  workflow before iii-b3 retires it).

- :func:`inline_kwargs_legacy` — returns the inline-bound kwargs
  to splat into an ``InstrumentResponseField`` constructor.
  Use when a test only needed the bounds + data_type + response_type
  on a directly-constructed field (the most common pre-iii-b2
  pattern).

- :func:`make_default_seeded_rtd_set` — back-compat shim: lazily
  creates all ten legacy-shaped RTDs on a session and returns the
  ``name -> RTD`` dict. Use when a test asks for "the seeded
  catalogue" wholesale. Each row is ``is_seeded=False`` (since
  iii-b2 deleted the seeded ones).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ResponseTypeDefinition

# Pre-iii-b2 seeded RTD specs. Kept in this test helper so the
# production seed list can shrink to empty without losing the
# fixture-replay vocabulary tests depend on.
_LEGACY_SEEDED_RTDS: dict[str, dict[str, Any]] = {
    "Long_text":  {"data_type": "String",  "min": 0,    "max": 2000, "step": None, "list_csv": None},
    "Short_text": {"data_type": "String",  "min": 0,    "max": 100,  "step": None, "list_csv": None},
    "Yes_no":     {"data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "Yes, No"},
    "Grade":      {"data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "A+, A, A-, B+, B, B-, C+, C, D+, D, F"},
    "Likert5":    {"data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "Strongly Agree, Agree, Neutral, Disagree, Strongly Disagree"},
    "100int":     {"data_type": "Integer", "min": 0,    "max": 100,  "step": 1,    "list_csv": None},
    "0-to-2int":  {"data_type": "Integer", "min": 0,    "max": 2,    "step": 1,    "list_csv": None},
    "1-to-5int":  {"data_type": "Integer", "min": 1,    "max": 5,    "step": 1,    "list_csv": None},
    "1-to-5half": {"data_type": "Decimal", "min": 1.0,  "max": 5.0,  "step": 0.5,  "list_csv": None},
    "1-to-5dec":  {"data_type": "Decimal", "min": 1.0,  "max": 5.0,  "step": 0.1,  "list_csv": None},
}


def make_legacy_rtd(
    db: Session,
    *,
    session_id: int,
    name: str,
    seed_order: int = 0,
) -> ResponseTypeDefinition:
    """Create + flush a "seeded" RTD with the shape of one of the
    retired seeded rows. Caller is responsible for ``commit``.

    The production seed list is empty post-iii-b2; this helper
    re-creates each row with ``is_seeded=True`` so tests that
    check the locked-seeded-row behaviour pass unchanged."""
    spec = _LEGACY_SEEDED_RTDS[name]
    rtd = ResponseTypeDefinition(
        session_id=session_id,
        response_type=name,
        data_type=spec["data_type"],
        min=spec["min"],
        max=spec["max"],
        step=spec["step"],
        list_csv=spec["list_csv"],
        is_seeded=True,
        seed_order=seed_order,
    )
    db.add(rtd)
    db.flush()
    return rtd


def make_default_seeded_rtd_set(
    db: Session, *, session_id: int
) -> dict[str, ResponseTypeDefinition]:
    """Create + flush all ten legacy-shaped RTDs on a session and
    return them keyed by ``response_type``. ``seed_order`` follows
    the same iteration order as the pre-iii-b2 seed list."""
    out: dict[str, ResponseTypeDefinition] = {}
    for index, name in enumerate(_LEGACY_SEEDED_RTDS):
        out[name] = make_legacy_rtd(
            db, session_id=session_id, name=name, seed_order=index
        )
    return out


def inline_kwargs_legacy(name: str) -> dict[str, Any]:
    """Inline-bound kwargs for an ``InstrumentResponseField`` row
    with the shape of a retired seeded RTD. Splat with ``**`` into
    the constructor."""
    spec = _LEGACY_SEEDED_RTDS[name]
    return {
        "_inline_data_type": spec["data_type"],
        "_inline_response_type": name,
        "_inline_min": spec["min"],
        "_inline_max": spec["max"],
        "_inline_step": spec["step"],
        "_inline_list_csv": spec["list_csv"],
    }


def validation_block_legacy(name: str) -> dict[str, Any] | None:
    """Validation JSON block for a field carrying the retired
    seeded RTD's bounds. Mirrors
    :func:`app.services.instruments._rtds.validation_block_for_rtd`
    but reads from :data:`_LEGACY_SEEDED_RTDS`."""
    spec = _LEGACY_SEEDED_RTDS[name]
    data_type = spec["data_type"]
    if data_type == "List":
        list_csv = spec.get("list_csv")
        if not list_csv:
            return {"choices": []}
        return {
            "choices": [
                item.strip() for item in list_csv.split(",") if item.strip()
            ]
        }
    if data_type == "String":
        block: dict[str, Any] = {}
        if spec.get("min") is not None:
            block["min_length"] = int(spec["min"])
        if spec.get("max") is not None:
            block["max_length"] = int(spec["max"])
        return block or None
    if data_type in ("Integer", "Decimal"):
        cast = int if data_type == "Integer" else float
        block = {}
        if spec.get("min") is not None:
            block["min"] = cast(spec["min"])
        if spec.get("max") is not None:
            block["max"] = cast(spec["max"])
        if spec.get("step") is not None:
            block["step"] = cast(spec["step"])
        return block or None
    return None
