"""One mailbox, one name — enforced on every path into every roster.

19Q Item 7. `csv_imports.check_cross_table_identity` had the rule right
and only the CSV path could reach it: the Add form wrote the row the CSV
refused, and nothing flagged it afterwards. Measured on the running app
before the fix, same session, same input — CSV **400** and zero rows,
the form **303** and one row.

The parity case below is that measurement turned into an assertion: it
drives both paths with the same input and requires the same verdict. The
rest cover what answering the item's two open questions added —
observers joining (so the check is three-way), and exact name comparison
(which makes a blank name a question the code has to answer).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer

from ._invitation_states import _create_session


def _session(client: TestClient, db: Session, code: str):
    """A session with observers enabled — every observers route is gated
    on `observers_enabled` and 404s without it
    (`_shared.require_observers_enabled_session`)."""
    review_session = _create_session(client, db, code)
    review_session.observers_enabled = True
    db.flush()
    return review_session

EMAIL = "aisha.haddad@example.edu"
ROSTER_FORM = {"profile_link": "", "tag_1": "", "tag_2": "", "tag_3": "", "status": "active"}

#: (roster, create path, the form's identity field, its name field)
ROSTERS = [
    ("reviewers", "reviewers/create", "email", "name"),
    ("reviewees", "reviewees/create", "email_or_identifier", "name"),
    ("observers", "observers/create", "email", "display_name"),
]


def _add(client: TestClient, session_id: int, path: str, **fields: str):
    return client.post(
        f"/operator/sessions/{session_id}/{path}",
        data={**ROSTER_FORM, **fields},
        follow_redirects=False,
    )


def _rows(db: Session, model, session_id: int) -> list:
    return list(
        db.execute(select(model).where(model.session_id == session_id)).scalars()
    )


def test_the_add_form_and_the_csv_reach_the_same_verdict(
    client: TestClient, db: Session
) -> None:
    """The item's whole point, and the measurement that opened it.

    A reviewee holds the mailbox under one name. Both paths are then
    offered a reviewer with that mailbox and a *different* name; before
    19Q Item 7 the CSV refused and the form accepted.
    """
    session = _session(client, db, "xr-parity")
    _add(client, session.id, "reviewees/create",
         name="Aisha Haddadx", email_or_identifier=EMAIL)

    csv = f"ReviewerName,ReviewerEmail\nAisha Haddad,{EMAIL}\n".encode()
    uploaded = client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        files={"file": ("r.csv", csv, "text/csv")},
        follow_redirects=True,
    )
    assert "names must match" in uploaded.text
    assert _rows(db, Reviewer, session.id) == []

    typed = _add(client, session.id, "reviewers/create",
                 name="Aisha Haddad", email=EMAIL)
    assert typed.status_code == 400, (
        "the Add form accepted what the CSV refused — the asymmetry 19Q "
        "Item 7 exists to remove"
    )
    assert _rows(db, Reviewer, session.id) == []


@pytest.mark.parametrize(("roster", "path", "id_field", "name_field"), ROSTERS)
def test_every_roster_refuses_a_mailbox_held_under_another_name(
    client: TestClient, db: Session, roster: str, path: str,
    id_field: str, name_field: str,
) -> None:
    """Three-way since the author's ruling: each roster checks the other
    two. A reviewee holds the mailbox; every roster must refuse a
    differently-named row for it, including the reviewee roster itself
    via the reviewer seeded below."""
    session = _session(client, db, f"xr-{roster}")
    holder_path, holder_id = (
        ("reviewers/create", "email") if roster == "reviewees"
        else ("reviewees/create", "email_or_identifier")
    )
    _add(client, session.id, holder_path, name="Held Name", **{holder_id: EMAIL})

    response = _add(client, session.id, path,
                    **{id_field: EMAIL, name_field: "Different Name"})
    assert response.status_code == 400, f"{roster} accepted a conflicting name"


@pytest.mark.parametrize(("roster", "path", "id_field", "name_field"), ROSTERS)
def test_the_same_name_is_the_legitimate_case_and_still_creates(
    client: TestClient, db: Session, roster: str, path: str,
    id_field: str, name_field: str,
) -> None:
    """The control, and the reason this is a name check and not an email
    check: one person is commonly reviewer and reviewee both, and may
    observe too. Without this the item would have banned self-review."""
    session = _session(client, db, f"xr-same-{roster}")
    holder_path, holder_id = (
        ("reviewers/create", "email") if roster == "reviewees"
        else ("reviewees/create", "email_or_identifier")
    )
    _add(client, session.id, holder_path, name="Aisha Haddad", **{holder_id: EMAIL})

    response = _add(client, session.id, path,
                    **{id_field: EMAIL, name_field: "Aisha Haddad"})
    assert response.status_code == 303, f"{roster} refused the same name"


def test_an_unnamed_observer_does_not_collide(
    client: TestClient, db: Session
) -> None:
    """Where the author's two answers meet.

    `Observer.display_name` is nullable and its CSV column optional,
    where the other two names are not. Under an exact comparison a blank
    name would differ from every real one, so without the skip every
    unnamed observer would collide with the reviewer sharing its
    mailbox.
    """
    session = _session(client, db, "xr-unnamed")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)

    response = _add(client, session.id, "observers/create",
                    email=EMAIL, display_name="")
    assert response.status_code == 303
    assert len(_rows(db, Observer, session.id)) == 1


def test_a_name_only_edit_is_caught(client: TestClient, db: Session) -> None:
    """The within-roster gate fires only on an identifier edit, so
    renaming a row into disagreement is invisible to it. The cross-roster
    guard keys on the resulting pair instead."""
    session = _session(client, db, "xr-rename")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)
    _add(client, session.id, "reviewees/create",
         name="Aisha Haddad", email_or_identifier=EMAIL)
    reviewee = _rows(db, Reviewee, session.id)[0]

    response = client.post(
        f"/operator/sessions/{session.id}/reviewees/{reviewee.id}/update",
        data={**ROSTER_FORM, "name": "Someone Else", "email_or_identifier": EMAIL},
        follow_redirects=False,
    )
    assert response.status_code == 400, (
        "a name-only edit walked past the guard; it must key on the "
        "resulting (identifier, name) pair, not on what changed"
    )


def test_an_unknown_kind_is_loud() -> None:
    """It used to return `[]`, so an observer CSV routed through the
    shared path would have been checked, found nothing, and reported
    success — a guard that passes by not running."""
    from app.services import csv_imports

    with pytest.raises(ValueError, match="unknown kind"):
        csv_imports.check_cross_table_identity(
            None, session_id=1, rows=[], kind="relationships"  # type: ignore[arg-type]
        )


def test_the_single_row_helper_is_loud_too() -> None:
    """Both entry points guard the kind, and both need saying.

    A mutant that reverted only `cross_table_identity_conflict`'s guard
    survived the case above: it asserts on `check_cross_table_identity`,
    and the services call the other function. Two guards, two tests.
    """
    from app.services import csv_imports

    with pytest.raises(ValueError, match="unknown kind"):
        csv_imports.cross_table_identity_conflict(
            None,  # type: ignore[arg-type]
            session_id=1,
            kind="relationships",
            identifier="x@example.edu",
            name="X",
        )


def test_an_unnamed_holder_does_not_block_a_named_row(
    client: TestClient, db: Session
) -> None:
    """The skip runs on both sides of the comparison.

    `test_an_unnamed_observer_does_not_collide` covers the *incoming*
    row being unnamed. This is the mirror — the row already in the
    session is the unnamed one — and a mutant that stopped skipping
    blank holder names survived until it was written.
    """
    session = _session(client, db, "xr-unnamed-holder")
    _add(client, session.id, "observers/create", email=EMAIL, display_name="")

    response = _add(client, session.id, "reviewers/create",
                    name="Aisha Haddad", email=EMAIL)
    assert response.status_code == 303, (
        "an unnamed observer blocked a named reviewer; a missing name "
        "cannot disagree with one, on either side"
    )


def test_the_name_comparison_is_case_sensitive(
    client: TestClient, db: Session
) -> None:
    """The author's ruling of 2026-09-19, which nothing pinned until a
    mutant folded the comparison and every test passed.

    **Case is a difference.** That is the choice, and this is what goes
    red if someone tidies it into a `.lower()`.
    """
    session = _session(client, db, "xr-exact-case")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)
    response = _add(client, session.id, "reviewees/create",
                    name="aisha haddad", email_or_identifier=EMAIL)
    assert response.status_code == 400, (
        "'aisha haddad' was accepted against 'Aisha Haddad' — the "
        "comparison is case-sensitive by ruling, not incidentally"
    )


def test_surrounding_whitespace_is_not_a_difference(
    client: TestClient, db: Session
) -> None:
    """**And this is the half "exact" does not mean.**

    Both paths trim a name long before it reaches the comparison —
    `_cell` on the CSV side, `_normalised_name` in the services — so
    `'Aisha Haddad '` is stored and compared as `'Aisha Haddad'` and
    cannot conflict with it. The plan first claimed a trailing space
    would fail; writing this case is what disproved it.
    """
    session = _session(client, db, "xr-exact-space")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)
    response = _add(client, session.id, "reviewees/create",
                    name="Aisha Haddad ", email_or_identifier=EMAIL)
    assert response.status_code == 303, (
        "a trailing space was treated as a conflict; names are trimmed "
        "upstream, so it never reaches the comparison"
    )


def test_the_observer_csv_import_checks_too(
    client: TestClient, db: Session
) -> None:
    """The call site 19Q Item 7 added, and the one no test reached.

    The observers CSV skipped the cross-table check entirely and said so
    in a docstring — *a person can be both an observer and a reviewer by
    design*. True, and never an argument for the exclusion: the check
    has always allowed one person to hold two roles and blocks only two
    **names**.
    """
    session = _session(client, db, "xr-observer-csv")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)

    csv = f"ObserverName,ObserverEmail\nAisha Haddadx,{EMAIL}\n".encode()
    response = client.post(
        f"/operator/sessions/{session.id}/observers/import",
        files={"file": ("o.csv", csv, "text/csv")},
        follow_redirects=True,
    )
    assert "names must match" in response.text
    assert _rows(db, Observer, session.id) == []


def test_an_unnamed_observer_row_in_a_csv_does_not_collide(
    client: TestClient, db: Session
) -> None:
    """The CSV path has its own blank-name skip, and needs its own case.

    `test_an_unnamed_observer_does_not_collide` drives the Add form,
    which goes through `cross_table_identity_conflict`; the importer
    goes through `check_cross_table_identity`. Two functions, two skips
    — a mutant that removed only the importer's survived until this was
    written. `ObserverName` is an optional column, so a blank cell is a
    real shape, not a contrived one.
    """
    session = _session(client, db, "xr-csv-unnamed")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)

    csv = f"ObserverName,ObserverEmail\n,{EMAIL}\n".encode()
    response = client.post(
        f"/operator/sessions/{session.id}/observers/import",
        files={"file": ("o.csv", csv, "text/csv")},
        follow_redirects=True,
    )
    assert "names must match" not in response.text
    assert len(_rows(db, Observer, session.id)) == 1, (
        "an unnamed observer row was blocked by the reviewer sharing its "
        "mailbox; a missing name cannot disagree with one"
    )


# --------------------------------------------------------------------------- #
# The Validate rules (19Q Item 7 rung 2)
# --------------------------------------------------------------------------- #
#
# Every test below seeds its rows through the ORM rather than a route,
# because the guards above now refuse exactly the input these rules
# exist to report. That is not a shortcut around the services: it *is*
# the scenario — a session that already held the pair when the services
# started refusing it.


def _seed(db: Session, model, **fields):
    row = model(**fields)
    db.add(row)
    db.flush()
    return row


def _issues(db: Session, review_session, rule_key: str) -> list:
    from app.services.validation import validate_session_setup

    return [
        i for i in validate_session_setup(db, review_session)
        if i.rule_key == rule_key
    ]


def test_a_pre_existing_cross_roster_pair_is_reported_on_both_sides(
    client: TestClient, db: Session
) -> None:
    """The rows piece 1 cannot reach, which is why piece 2 exists.

    Both rows are wrong-or-right together and the operator does not yet
    know which, so the finding lands under each roster with that
    roster's own deep link — not once, session-wide, pointing at one of
    them.
    """
    session = _session(client, db, "xr-val-pair")
    reviewer = _seed(db, Reviewer, session_id=session.id,
                     name="Aisha Haddad", email=EMAIL)
    reviewee = _seed(db, Reviewee, session_id=session.id,
                     name="Aisha Hadad", email_or_identifier=EMAIL)

    on_reviewers = _issues(db, session, "reviewers.cross_roster_identity")
    on_reviewees = _issues(db, session, "reviewees.cross_roster_identity")

    assert len(on_reviewers) == 1 and len(on_reviewees) == 1
    assert on_reviewers[0].fix_anchor == f"#reviewer-row-{reviewer.id}"
    assert on_reviewees[0].fix_anchor == f"#reviewee-row-{reviewee.id}"
    assert on_reviewers[0].fix_url.endswith(f"/{session.id}/reviewers")
    assert on_reviewees[0].fix_url.endswith(f"/{session.id}/reviewees")
    # Each side names its own spelling first and the other's second, so
    # the operator can tell the two findings apart at a glance.
    assert "'Aisha Haddad' here" in on_reviewers[0].message
    assert "'Aisha Hadad' as a reviewee" in on_reviewers[0].message
    assert "'Aisha Hadad' here" in on_reviewees[0].message
    assert "'Aisha Haddad' as a reviewer" in on_reviewees[0].message


def test_the_same_name_across_rosters_is_not_a_finding(
    client: TestClient, db: Session
) -> None:
    """The self-review case, which the app has machinery for."""
    session = _session(client, db, "xr-val-self")
    _seed(db, Reviewer, session_id=session.id, name="Aisha Haddad", email=EMAIL)
    _seed(db, Reviewee, session_id=session.id,
          name="Aisha Haddad", email_or_identifier=EMAIL)

    assert _issues(db, session, "reviewers.cross_roster_identity") == []
    assert _issues(db, session, "reviewees.cross_roster_identity") == []


def test_an_observer_joins_the_report(client: TestClient, db: Session) -> None:
    """Three-way on Validate too, not just on the write paths."""
    session = _session(client, db, "xr-val-obs")
    observer = _seed(db, Observer, session_id=session.id,
                     display_name="A. Haddad", email=EMAIL)
    _seed(db, Reviewer, session_id=session.id, name="Aisha Haddad", email=EMAIL)

    found = _issues(db, session, "observers.cross_roster_identity")
    assert len(found) == 1
    assert found[0].fix_anchor == f"#observer-row-{observer.id}"
    assert "'Aisha Haddad' as a reviewer" in found[0].message


def test_an_unnamed_observer_is_not_a_finding(
    client: TestClient, db: Session
) -> None:
    """A missing name cannot disagree with one — the answer exact
    comparison forced (`Semantics`). Without the skip, every unnamed
    observer would collide with the reviewer sharing its mailbox."""
    session = _session(client, db, "xr-val-unnamed")
    _seed(db, Observer, session_id=session.id, display_name=None, email=EMAIL)
    _seed(db, Reviewer, session_id=session.id, name="Aisha Haddad", email=EMAIL)

    assert _issues(db, session, "observers.cross_roster_identity") == []
    assert _issues(db, session, "reviewers.cross_roster_identity") == []


def test_a_non_email_reviewee_identifier_cannot_collide(
    client: TestClient, db: Session
) -> None:
    """An anonymous handle is not a mailbox, so it is skipped here for
    the same reason the write guards skip it."""
    session = _session(client, db, "xr-val-anon")
    _seed(db, Reviewee, session_id=session.id,
          name="Subject 14", email_or_identifier="subject-14")
    _seed(db, Reviewer, session_id=session.id,
          name="Aisha Haddad", email="subject-14")

    assert _issues(db, session, "reviewees.cross_roster_identity") == []
    assert _issues(db, session, "reviewers.cross_roster_identity") == []


def test_the_email_match_is_case_insensitive_and_the_name_match_is_not(
    client: TestClient, db: Session
) -> None:
    """`normalize_email` lowercases; the name comparison is exact
    (open question 2). A capitalisation difference in the name is
    therefore a finding, and one in the email is not a miss."""
    session = _session(client, db, "xr-val-case")
    _seed(db, Reviewer, session_id=session.id,
          name="Aisha Haddad", email=EMAIL.upper())
    _seed(db, Reviewee, session_id=session.id,
          name="aisha haddad", email_or_identifier=EMAIL)

    found = _issues(db, session, "reviewers.cross_roster_identity")
    assert len(found) == 1, "the upper-case mailbox still matched"
    assert "'aisha haddad' as a reviewee" in found[0].message


def test_a_within_roster_duplicate_is_left_to_its_own_rule(
    client: TestClient, db: Session
) -> None:
    """Two reviewers, one mailbox, two names is
    `reviewers.duplicate_email`'s finding and only that one. Reporting
    it twice under one heading would read as two problems."""
    session = _session(client, db, "xr-val-within")
    _seed(db, Reviewer, session_id=session.id, name="Aisha Haddad", email=EMAIL)
    _seed(db, Reviewer, session_id=session.id, name="Aisha Hadad", email=EMAIL)

    assert len(_issues(db, session, "reviewers.duplicate_email")) == 1
    assert _issues(db, session, "reviewers.cross_roster_identity") == []


def test_observers_duplicate_email_is_reported(
    client: TestClient, db: Session
) -> None:
    """Piece 3. The database refuses a second row today, so the only
    way to hold one is to be older than the constraint — seeded here by
    writing the pair the services would reject."""
    session = _session(client, db, "xr-val-obs-dup")
    first = _seed(db, Observer, session_id=session.id,
                  display_name="A. Haddad", email=EMAIL)
    _seed(db, Observer, session_id=session.id,
          display_name="A. Haddad", email=EMAIL.upper())

    found = _issues(db, session, "observers.duplicate_email")
    assert len(found) == 1
    assert found[0].severity.value == "error"
    assert found[0].fix_anchor == f"#observer-row-{first.id}"
    assert found[0].fix_url.endswith(f"/{session.id}/observers")
    assert "(2 rows)" in found[0].message


def test_a_clean_session_raises_neither_new_rule(
    client: TestClient, db: Session
) -> None:
    """The control. A reviewer, a reviewee and an observer who agree —
    including one person holding all three — raise nothing."""
    session = _session(client, db, "xr-val-clean")
    _seed(db, Reviewer, session_id=session.id, name="Aisha Haddad", email=EMAIL)
    _seed(db, Reviewee, session_id=session.id,
          name="Aisha Haddad", email_or_identifier=EMAIL)
    _seed(db, Observer, session_id=session.id,
          display_name="Aisha Haddad", email=EMAIL)
    _seed(db, Observer, session_id=session.id,
          display_name="Bo Lin", email="bo.lin@example.edu")

    for key in (
        "reviewers.cross_roster_identity",
        "reviewees.cross_roster_identity",
        "observers.cross_roster_identity",
        "observers.duplicate_email",
    ):
        assert _issues(db, session, key) == [], key


# --------------------------------------------------------------------------- #
# What the item's cold read found (19Q Item 7 rung 2)
# --------------------------------------------------------------------------- #


def test_the_reviewee_finding_names_the_column_reviewees_have(
    client: TestClient, db: Session
) -> None:
    """`issue.field` is rendered to the operator as a `<code>` chip, and
    the sibling `reviewees.duplicate_id` names `email_or_identifier`.
    One rule in the same section must not name a column the roster does
    not have."""
    session = _session(client, db, "xr-field")
    _seed(db, Reviewer, session_id=session.id, name="Aisha Haddad", email=EMAIL)
    _seed(db, Reviewee, session_id=session.id,
          name="Aisha Hadad", email_or_identifier=EMAIL)

    on_reviewees = _issues(db, session, "reviewees.cross_roster_identity")
    on_reviewers = _issues(db, session, "reviewers.cross_roster_identity")
    assert on_reviewees[0].field == "email_or_identifier"
    assert on_reviewers[0].field == "email"


def test_the_coverage_grid_badges_an_observer_error(
    client: TestClient, db: Session
) -> None:
    """An error source with no coverage row badges nothing on the
    at-a-glance grid (`spec/validate_page.md` §7 step 5). Observers
    became a source with these rules and had no row."""
    from app.services.validation import validate_session_setup
    from app.web.views._validate import build_validate_context

    session = _session(client, db, "xr-grid")
    _seed(db, Observer, session_id=session.id,
          display_name="A. Haddad", email=EMAIL)
    _seed(db, Observer, session_id=session.id,
          display_name="A. Haddad", email=EMAIL.upper())

    context = build_validate_context(
        db, session, validate_session_setup(db, session)
    )
    row = next(r for r in context.setup_coverage if r.label == "Observers")
    assert row.source == "observers", "the anchor link must reach the group"
    assert row.status == "2"
    assert row.error_count >= 1


def test_the_coverage_grid_omits_observers_when_the_flag_is_off(
    client: TestClient, db: Session
) -> None:
    """A session with observers switched off has no roster to summarise,
    and a permanently blank row is one the operator learns to skip."""
    from app.services.validation import validate_session_setup
    from app.web.views._validate import build_validate_context

    session = _session(client, db, "xr-grid-off")
    session.observers_enabled = False
    db.flush()

    context = build_validate_context(
        db, session, validate_session_setup(db, session)
    )
    assert [r for r in context.setup_coverage if r.label == "Observers"] == []


def test_a_matching_name_does_not_slip_past_a_second_disagreeing_holder(
    client: TestClient, db: Session
) -> None:
    """The defect Codex found on #2485, and the reason no holder is
    chosen any more.

    Two reviewers on one mailbox under two names is a state a session
    can hold — neither roster has DB uniqueness on `(session_id, email)`,
    which is why `reviewers.duplicate_email` exists. Collapsing that
    mailbox to one holder let an observer matching *that* name through
    while the other reviewer still disagreed: the rule failing open, on
    exactly the legacy sessions this item exists for.
    """
    session = _session(client, db, "xr-two-holders")
    _seed(db, Reviewer, session_id=session.id, name="Alpha Name", email=EMAIL)
    _seed(db, Reviewer, session_id=session.id, name="Zed Name", email=EMAIL)

    matching = _add(client, session.id, "observers/create",
                    display_name="Zed Name", email=EMAIL)
    assert matching.status_code == 400, (
        "matching one holder is not agreeing with the mailbox"
    )
    assert "Alpha Name" in matching.text, "the 400 cites the row that disagrees"
    assert _rows(db, Observer, session.id) == []


def test_the_cited_holder_is_picked_from_the_values_not_the_query(
    client: TestClient, db: Session
) -> None:
    """Which disagreeing holder a 400 names is roster order, then name —
    never the order the database returned.

    The seeding here is deliberately the reverse: `Zed Name` has the
    lower `id`, so an assertion satisfied by iteration order would name
    it. Pinned any other way this test is a false green, since SQLite
    hands an unordered `SELECT` back in insertion order and Postgres
    does not owe it.
    """
    session = _session(client, db, "xr-order")
    _seed(db, Reviewer, session_id=session.id, name="Zed Name", email=EMAIL)
    _seed(db, Reviewer, session_id=session.id, name="Alpha Name", email=EMAIL)

    refused = _add(client, session.id, "observers/create",
                   display_name="Third Name", email=EMAIL)
    assert refused.status_code == 400
    assert "Alpha Name" in refused.text
    assert "Zed Name" not in refused.text


def test_a_reviewee_holder_is_cited_after_a_reviewer_one(
    client: TestClient, db: Session
) -> None:
    """Roster order beats name order: `_IDENTITY_ROSTERS` runs reviewers,
    reviewees, observers, and the message follows it."""
    session = _session(client, db, "xr-order-roster")
    _seed(db, Reviewer, session_id=session.id, name="Zed Name", email=EMAIL)
    _seed(db, Reviewee, session_id=session.id,
          name="Alpha Name", email_or_identifier=EMAIL)

    refused = _add(client, session.id, "observers/create",
                   display_name="Third Name", email=EMAIL)
    assert refused.status_code == 400
    # Jinja escapes the quotes the message puts round a name, so the
    # roster label and the name are matched apart rather than together.
    assert "reviewer" in refused.text and "Zed Name" in refused.text
    assert "Alpha Name" not in refused.text


def test_one_predicate_decides_membership_on_every_path(
    client: TestClient, db: Session
) -> None:
    """`is_comparable_identity` is called by the single-row guard, the
    CSV row loop and the Validate rule. A mutant that removed only one
    copy survived at rung 1; there is now one copy to remove."""
    from app.services.csv_imports import is_comparable_identity

    assert is_comparable_identity("a@b.example", "A") is True
    assert is_comparable_identity("subject-14", "A") is False
    assert is_comparable_identity("a@b.example", None) is False
    assert is_comparable_identity("a@b.example", "") is False
    assert is_comparable_identity(None, "A") is False
