"""Canonical email-identity primitives.

One home for the three things the roster services and participant
gates used to each re-derive:

- the email-shape regex (was duplicated five times — audit S4);
- the "is this an email?" predicate (was split between a strict
  ``fullmatch`` and a ``"@" in value`` heuristic — audit S3);
- the case-folding convention used to compare email identities (was a
  three-way split between ``str.casefold``, SQL ``lower``, and
  ``str.lower`` — audit S2).

Every identity-match site — roster uniqueness gates, participant
access gates, CSV dedup — now folds through :func:`normalize_email`,
so write-time and read-time comparisons can never disagree.

See ``guide/segment_19B_consistency.md`` (S2–S4).
"""

from __future__ import annotations

import re

# Deliberately permissive: a single ``@``-free domain label with a dot.
# Kept identical to the five copies it replaces so classification does
# not shift; tighten here (in one place) if the policy ever changes.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def looks_like_email(value: str | None) -> bool:
    """Return True iff ``value`` (after stripping) is a well-formed
    email address per :data:`EMAIL_RE`."""
    return bool(EMAIL_RE.fullmatch((value or "").strip()))


def normalize_email(value: str | None) -> str:
    """Return the canonical case-insensitive comparison key for an
    email or email-shaped identifier: stripped and case-folded.

    ``str.casefold`` (not ``str.lower``) is the Unicode-correct fold.
    Handles ``None`` so callers can pass a possibly-empty column
    value directly. Use this at *every* identity-comparison site so
    the uniqueness gate that rejects a duplicate on write and the
    access gate that grants a surface on read use one convention.
    """
    return (value or "").strip().casefold()
