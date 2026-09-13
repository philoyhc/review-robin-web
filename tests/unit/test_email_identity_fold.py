"""The identity fold — `normalize_email`, and why it is `lower`.

19N Item 2 / `SC-45`. Before this, `normalize_email` case-*folded*
while a dozen comparisons composed in SQL used `func.lower(column)`,
so the two sides of one expression used different rules. Several
compared a `func.lower` column against an already-casefolded Python
value.

The fix is not "casefold everywhere". Casefold is the Unicode-correct
fold for caseless *search* and the wrong tool for identity: it folds
`ß` to `ss`, merging two different mailboxes into one key. On an
access gate that is a fail-*open*. `lower` keeps them apart, and it is
what SQL is already doing.

These tests exist because `normalize_email` had **no direct coverage
at all** — the convention every identity gate depends on was asserted
only indirectly, through the surfaces that use it.
"""

from __future__ import annotations

import sqlite3

from app.services.email_identity import looks_like_email, normalize_email


# --------------------------------------------------------------------- #
# The fold itself
# --------------------------------------------------------------------- #


def test_case_is_folded() -> None:
    assert normalize_email("John.Smith@Example.COM") == "john.smith@example.com"


def test_surrounding_whitespace_is_stripped() -> None:
    assert normalize_email("  a@b.com \n") == "a@b.com"


def test_none_and_empty_are_the_empty_key() -> None:
    assert normalize_email(None) == ""
    assert normalize_email("   ") == ""


def test_eszett_addresses_stay_distinct() -> None:
    """The reason this is `lower` and not `casefold`.

    `straße@` and `strasse@` are two different mailboxes. Casefold
    maps both to `strasse@`; on `_dashboard.py`'s roster match or
    `participants.roles_held_anywhere`, merging them would let one
    person reach the other's surface. That is the one failure
    direction worth engineering against, because it fails open.
    """
    sharp = normalize_email("straße@example.com")
    double = normalize_email("strasse@example.com")

    assert sharp != double, (
        "casefold would merge these; identity equality is the mail "
        "protocol's, not Unicode's"
    )
    assert sharp == "straße@example.com"
    assert "straße@example.com".casefold() == double, (
        "guard on the premise: casefold really does collapse them"
    )


def test_the_fold_is_idempotent() -> None:
    once = normalize_email("  MiXeD@Example.com ")
    assert normalize_email(once) == once


# --------------------------------------------------------------------- #
# Agreement with the SQL side
# --------------------------------------------------------------------- #


def _sqlite_lower(value: str) -> str:
    conn = sqlite3.connect(":memory:")
    try:
        return conn.execute("select lower(?)", (value,)).fetchone()[0]
    finally:
        conn.close()


def test_python_and_sql_folds_agree_on_ascii_identities() -> None:
    """The property the change actually buys.

    A dozen sites compare `func.lower(column)` against a Python-folded
    value. They agree for every ASCII identity — which is every
    identity this deployment has — and that agreement is what makes
    the SQL-side comparisons correct rather than accidentally correct.
    """
    for raw in (
        "Alice@Example.edu",
        "BOB.jones+tag@sub.example.co.uk",
        "carol@EXAMPLE.ORG",
    ):
        assert normalize_email(raw) == _sqlite_lower(raw.strip())


def test_sql_lower_is_dialect_dependent_outside_ascii() -> None:
    """Why the fold is not attempted inside SQL.

    SQLite's `lower()` is ASCII-only; Postgres's is Unicode-aware. The
    suite runs on SQLite and production on Postgres, with `ci-postgres`
    running these same tests against the other dialect — so a
    `func.lower` comparison on a non-ASCII identity means different
    things in the two places. A test written to pin that behaviour
    would assert two different things in the two CI jobs.

    This test pins the *divergence*, not a fold result, so it is true
    on both dialects: it asserts only what SQLite does.
    """
    assert _sqlite_lower("ÄÖÜ@x.com") == "ÄÖÜ@x.com"
    assert "ÄÖÜ@x.com".lower() == "äöü@x.com"


# --------------------------------------------------------------------- #
# The predicate that rides alongside
# --------------------------------------------------------------------- #


def test_looks_like_email_strips_before_judging() -> None:
    assert looks_like_email("  a@b.com  ")
    assert not looks_like_email("not-an-email")
    assert not looks_like_email(None)
