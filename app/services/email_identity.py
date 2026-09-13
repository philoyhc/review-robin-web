"""Canonical email-identity primitives.

One home for the three things the roster services and participant
gates used to each re-derive:

- the email-shape regex (was duplicated five times — audit S4);
- the "is this an email?" predicate (was split between a strict
  ``fullmatch`` and a ``"@" in value`` heuristic — audit S3);
- the case-folding convention used to compare email identities (was a
  three-way split between ``str.casefold``, SQL ``lower``, and
  ``str.lower`` — audit S2).

Every identity gate folds through :func:`normalize_email` — and that
sentence was false for three years' worth of call sites until 19N
Item 2 checked it. ``auth/roles.py``, the reviewer dashboard, invite
acceptance and two coverage filters case-folded **inline**, so they
were untouched by any change to this function.
``tests/unit/test_email_identity_fold.py::test_no_identity_gate_folds_inline``
now enforces it rather than asserting it: a bare ``.casefold()`` in a
gate module fails unless the comment above it says ``not-identity:``
and why.

**Comparisons composed in SQL still do not fold through here** — 13
code sites compare ``func.lower(column)`` against a Python-folded
value, and until Item 2 the two sides used different rules. Aligning
this function on ``str.lower`` makes them agree on every ASCII
identity, which is every identity this deployment has.

The fold cannot be made trustworthy *inside* SQL here, and that is
why it is not attempted: **SQLite's ``lower()`` is ASCII-only while
Postgres's is Unicode-aware**, so ``func.lower`` means one thing in
the test suite and another in production. A non-ASCII identity is
therefore out of scope by construction rather than by neglect; see
19N Item 2 for the stored-column design that would put it back in.

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
    """Return the canonical comparison key for an email or
    email-shaped identifier: stripped and lower-cased.

    **``str.lower``, deliberately, not ``str.casefold``** (19N Item 2).
    Casefold is the Unicode-correct fold for caseless *search*, and it
    is the wrong tool for identity: it folds ``ß`` to ``ss``, so
    ``straße@example.com`` and ``strasse@example.com`` — two different
    mailboxes — collapse to one key. On an access gate that merges two
    people, which fails *open*. Email equality is defined by the mail
    protocol, not by Unicode's notion of sameness, so the fold stops
    at case.

    ASCII-lower-casing the local part is itself over-permissive —
    RFC 5321 makes local parts case-sensitive — but every mail system
    treats them case-insensitively and users expect that. A deliberate
    concession, recorded in ``docs/security_posture.md``.

    Handles ``None`` so callers can pass a possibly-empty column value
    directly.
    """
    return (value or "").strip().lower()
