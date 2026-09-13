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
# Reading a source file as code, not as prose
# --------------------------------------------------------------------- #


def _code_lines(path) -> list[str]:
    """Return the file's lines with every string literal and comment
    blanked out, so a scan matches what the module *does* rather than
    what it says about itself.

    Added by the third pass. Widening the fold regex to catch the
    bound-method spelling (``key=str.casefold``) immediately made it
    match two docstrings that *describe* the convention — including
    ``deps.py``'s, which says the fold is ``str.lower``. A scanner that
    trips on its own documentation teaches people to stop writing it.

    ``tokenize`` rather than a regex, because the literals that matter
    here are triple-quoted and span lines.
    """
    import io
    import tokenize

    src = path.read_text()
    rows = [list(line) for line in src.splitlines()]
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type not in (tokenize.STRING, tokenize.COMMENT):
            continue
        (r1, c1), (r2, c2) = tok.start, tok.end
        for r in range(r1, r2 + 1):
            if r - 1 >= len(rows):
                break
            row = rows[r - 1]
            lo = c1 if r == r1 else 0
            hi = c2 if r == r2 else len(row)
            for c in range(lo, min(hi, len(row))):
                row[c] = " "
    return ["".join(row) for row in rows]


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
        # Added after the first version of this test missed them: both
        # resolve "does this email identify an existing User", which is
        # deciding who someone is, not filtering what a viewer sees.
        "app/services/users.py",
        "app/web/routes_operator/_session_home.py",
        # Added by the third pass. None of these were violating —
        # they were simply never listed, which is the point: the list
        # only protects what someone remembered to add to it. The
        # column-scoped test below is what closes that gap; this list
        # remains as the stricter rule for modules that decide access.
        "app/services/reviewers.py",
        "app/services/observers.py",
        "app/services/reviewees.py",
        "app/services/relationships.py",
        "app/services/csv_imports.py",
        "app/services/rules/engine.py",
        "app/services/assignments/_self_review.py",
    ]

    # Both folds, three spellings. The first version matched only
    # ``.casefold()`` and so could not see ``deps.py``'s sign-in
    # resolution folding with a bare ``.lower()`` — the single most
    # consequential identity comparison in the app, inside a module
    # already on this list. The second matched ``str.casefold(`` but
    # required the paren, so the bound-method form ``key=str.casefold``
    # — already in use in ``views/_filters.py`` — would have slipped
    # past. ``func.lower(col)`` is still not matched: the method forms
    # require empty parens, and the ``str.`` form requires the
    # ``str.`` prefix.
    INLINE_FOLD = re.compile(r"\.(casefold|lower)\(\)|\bstr\.(casefold|lower)\b")

    offenders: list[str] = []
    for rel in gates:
        path = root / rel
        assert path.exists(), f"gate module moved: {rel}"
        lines = path.read_text().splitlines()
        code = _code_lines(path)
        for n, line in enumerate(lines, 1):
            if not INLINE_FOLD.search(code[n - 1]):
                continue
            if "normalize_email" in code[n - 1]:
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


# --------------------------------------------------------------------- #
# The gap the module list could not close
# --------------------------------------------------------------------- #
#
# Three verification passes, three sets of misses, one root cause: the
# test above protects a list someone has to remember to extend. Pass
# one missed four gates; pass two missed three more, one of them in a
# module already on the list; pass three found none — but only because
# it read every file by hand, which is not a gate.
#
# This one starts from the columns instead. The identity-bearing
# attributes are a closed set of two names, so a comparison or a fold
# against one can be found without knowing which module it lives in.
# Measured cost of the inversion: 10 sites needing a marker, against
# the 67 that marking every ``.lower()`` in ``app/`` would have
# required — which would have made the marker mean "I touched a fold"
# rather than "I touched an identity comparison".


def test_identity_columns_are_compared_through_the_fold() -> None:
    """Every comparison against an email column folds, or says why not.

    Scans all of ``app/`` — no allowlist — for a line that both names
    an identity-bearing attribute (``.email`` / ``.email_or_identifier``)
    and compares or folds it. Such a line passes if ``normalize_email``
    appears on it or anywhere in its enclosing function (the common
    shape is a ``normalized = normalize_email(...)`` local compared
    against ``func.lower(column)`` a few lines down), or if a
    ``# not-identity:`` comment appears above it inside that same
    function.

    Function scope rather than the line-above scope used by the test
    above, because these are function-level decisions: a picker filter
    or a dirty check is wholly one or the other, and one marker per
    function says that more honestly than five identical ones.

    Matching runs against ``_code_lines`` — string literals and
    comments blanked — so a dict key or a sort key naming a column
    (``views/_sort.py``) is not a hit, and neither is prose about the
    convention.
    """
    import ast
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2]
    IDENT_ATTR = re.compile(r"\.(email|email_or_identifier)\b")
    COMPARE = re.compile(r"==|!=|\.lower\(\)|\.casefold\(\)")

    offenders: list[str] = []
    scanned = 0
    for path in sorted(root.glob("app/**/*.py")):
        src = path.read_text()
        lines = src.splitlines()
        code = _code_lines(path)
        tree = ast.parse(src, filename=str(path))
        funcs = [
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for n, line in enumerate(lines, 1):
            bare = code[n - 1]
            if not IDENT_ATTR.search(bare) or not COMPARE.search(bare):
                continue
            scanned += 1
            # Both exemptions read ``code``, never ``lines``: a comment
            # or docstring that merely *mentions* ``normalize_email``
            # must not excuse a comparison that does not call it. Only
            # the marker lookup below reads raw lines, because a marker
            # is a comment.
            if "normalize_email" in code[n - 1]:
                continue
            enclosing = [f for f in funcs if f.lineno <= n <= (f.end_lineno or n)]
            if any(
                "normalize_email" in "\n".join(code[f.lineno - 1 : f.end_lineno])
                for f in enclosing
            ):
                continue
            start = min((f.lineno for f in enclosing), default=1)
            above = "\n".join(lines[start - 1 : n - 1])
            if "not-identity:" in above:
                continue
            rel = path.relative_to(root)
            offenders.append(f"{rel}:{n}: {line.strip()}")

    assert scanned >= 20, (
        "the scan found almost nothing — the attribute pattern has "
        f"probably gone stale (matched {scanned} lines)"
    )
    assert not offenders, (
        "a comparison against an identity column neither folds through "
        "normalize_email nor carries a '# not-identity:' marker:\n  "
        + "\n  ".join(offenders)
    )
