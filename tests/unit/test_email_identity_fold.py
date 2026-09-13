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
    maps both to `strasse@`; at the `web/deps.py` gates,
    `auth.roles.is_super_admin`, the dashboard roster match and invite
    acceptance, merging them lets one person reach the other's
    surface. That is the failure direction worth engineering against,
    because it fails open.
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


def test_sqlite_lower_is_ascii_only() -> None:
    """Hazard one: the fold means different things in test and prod.

    SQLite's `lower()` leaves non-ASCII alone; Postgres's does not.
    The suite runs on SQLite and production on Postgres, with
    `ci-postgres` running these same tests against the other dialect —
    so a `func.lower` comparison on a non-ASCII identity means
    different things in the two places, and a test pinning *its result*
    would assert two different things in the two jobs.

    This pins the divergence rather than a fold result, via an explicit
    in-memory SQLite connection, so it is true whichever database the
    suite is pointed at.
    """
    assert _sqlite_lower("ÄÖÜ@x.com") == "ÄÖÜ@x.com"
    assert "ÄÖÜ@x.com".lower() == "äöü@x.com"


def test_python_and_postgres_lower_disagree_on_dotted_capital_i() -> None:
    """Hazard two, and the one the argument did not predict.

    Python and Postgres disagree on `İ` — so the two sides of a
    `func.lower(column) == normalize_email(value)` comparison can
    disagree **in production**, where no test can catch it.

    Measured 2026-09-13 against Postgres 16 (`C.UTF-8`) stood up in the
    sandbox:

        select lower('İstanbul')  ->  'istanbul'   (8 chars, plain i)
        'İstanbul'.lower()        ->  'i̇stanbul'  (9 chars, i + U+0307)

    Only the Python half is assertable here — there is no Postgres in
    the unit suite, and hard-coding the database's answer would be
    asserting a measurement rather than a behaviour. What this test
    pins is the property that makes the disagreement possible: Python's
    fold *adds a combining mark*, which no ASCII-only or
    dot-dropping implementation will reproduce.
    """
    folded = normalize_email("İstanbul@x.com")

    assert folded == "i̇stanbul@x.com"
    assert len(folded.split("@")[0]) == 9, "i + U+0307, not a plain i"
    assert "\u0307" in folded
    assert folded != "istanbul@x.com", (
        "Postgres lower() yields this 8-char form; Python does not"
    )


# --------------------------------------------------------------------- #
# The predicate that rides alongside
# --------------------------------------------------------------------- #


def test_looks_like_email_strips_before_judging() -> None:
    assert looks_like_email("  a@b.com  ")
    assert not looks_like_email("not-an-email")
    assert not looks_like_email(None)


# --------------------------------------------------------------------- #
# The gates that bypassed the fold
# --------------------------------------------------------------------- #
#
# Changing `normalize_email` fixed only the sites that call it. Four
# identity comparisons case-folded *inline* and were untouched by it:
# `auth/roles.py` (super-admin), `routes_reviewer/_dashboard.py` (the
# roster listing), `routes_reviewer/_invite.py` (invite acceptance),
# and two `assignments/_coverage.py` handle filters.
#
# The module docstring on `email_identity` asserted that every
# identity-match site folds through `normalize_email`. It did not, and
# believing it is how the first pass at this item stopped one function
# short of the gates it was written to protect.


def test_super_admin_membership_does_not_merge_eszett() -> None:
    """The worst instance, had it ever been reachable.

    `is_super_admin` case-folded both sides against the configured
    allowlist. An address whose fold collides with an allowlisted one
    — `straße@` against an allowlisted `strasse@` — would have been
    admitted as super-admin.
    """
    from app.auth.roles import is_super_admin
    from app.config import Settings

    settings = Settings(
        super_admin_emails=["strasse@example.edu"],
        allow_fake_auth=False,
    )

    assert is_super_admin("strasse@example.edu", settings)
    assert is_super_admin("  STRASSE@Example.EDU  ", settings), (
        "the fold still has to do its ASCII job"
    )
    assert not is_super_admin("straße@example.edu", settings), (
        "casefold would admit this; it is a different mailbox"
    )


def test_no_identity_gate_folds_inline() -> None:
    """One fold, enforced structurally rather than remembered.

    Every module here decides who someone is. A bare `.casefold()` or
    `.lower()` in one of them is a second fold that `normalize_email`
    cannot reach — which is exactly the gap this item's first pass
    left. Operator-side *filtering* modules (`views/_filters.py`,
    `views/_previews.py`) are deliberately not listed: they narrow
    data the operator is already authorized to see, so a fold there
    changes what is displayed, not who may see it.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2]
    gates = [
        "app/auth/roles.py",
        "app/web/deps.py",
        "app/web/routes_reviewer/_dashboard.py",
        "app/web/routes_reviewer/_invite.py",
        "app/services/participants.py",
        "app/services/assignments/_coverage.py",
    ]

    offenders: list[str] = []
    for rel in gates:
        path = root / rel
        assert path.exists(), f"gate module moved: {rel}"
        lines = path.read_text().splitlines()
        for n, line in enumerate(lines, 1):
            if not re.search(r"\.casefold\(\)", line):
                continue
            if "normalize_email" in line:
                continue
            # A fold that is demonstrably not an identity match may
            # stay, but it has to say so in the comment block directly
            # above it. The marker is the point: it forces the next
            # person adding one to state which kind it is instead of
            # leaving the reader to guess.
            j = n - 2
            marked = False
            while j >= 0 and lines[j].strip().startswith("#"):
                if "not-identity:" in lines[j]:
                    marked = True
                    break
                j -= 1
            if marked:
                continue
            offenders.append(f"{rel}:{n}: {line.strip()}")

    assert not offenders, (
        "identity gates must fold through email_identity.normalize_email, "
        "not inline:\n  " + "\n  ".join(offenders)
    )
