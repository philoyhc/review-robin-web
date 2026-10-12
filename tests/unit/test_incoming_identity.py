"""Roster files uploaded together are checked together.

``guide/quick_setup_update.md`` Item 1, rung 2: the checks Quick Setup
will run before it saves anything. Each uploaded roster file is checked
against the other uploaded files and against the existing rosters it
does not replace (``csv_imports.check_incoming_identity``); a
Relationships file is checked against the uploaded roster files where
they are attached (``relationships.rosters_for_relationships``).
Nothing here saves, and no route calls these yet.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.schemas.imports import (
    ObserverImportRow,
    RevieweeImportRow,
    ReviewerImportRow,
)
from app.services.csv_imports import (
    check_cross_table_identity,
    check_incoming_identity,
)
from app.services.relationships import (
    IncomingReviewee,
    IncomingReviewer,
    parse_relationship_csv,
    rosters_for_relationships,
)

BOB = "bob@example.edu"
ROSTER_PROBLEM = "is already used under a different name in another roster"


def _session(db: Session) -> ReviewSession:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code="incoming-id", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _reviewer(name: str, email: str = BOB, **kw) -> ReviewerImportRow:
    return ReviewerImportRow(name=name, email=email, **kw)


def _reviewee(name: str, identifier: str = BOB, **kw) -> RevieweeImportRow:
    return RevieweeImportRow(name=name, email_or_identifier=identifier, **kw)


def _observer(name: str | None, email: str = BOB) -> ObserverImportRow:
    return ObserverImportRow(email=email, display_name=name)


def _problems(issues) -> list[str | None]:
    return [issue.problem for issue in issues]


# --------------------------------------------------------------------- #
# Identity across uploaded files
# --------------------------------------------------------------------- #


def test_a_rename_across_both_rosters_passes_when_uploaded_together(
    db: Session,
) -> None:
    """The case the item exists for: Bob is "Bob Smith" on both
    rosters, and both new files rename him. Each file replaces its own
    roster, so neither old name holds anything."""
    s = _session(db)
    db.add_all(
        [
            Reviewer(session_id=s.id, name="Bob Smith", email=BOB),
            Reviewee(session_id=s.id, name="Bob Smith", email_or_identifier=BOB),
        ]
    )
    db.flush()

    result = check_incoming_identity(
        db,
        session_id=s.id,
        incoming={
            "reviewers": [_reviewer("Robert Smith")],
            "reviewees": [_reviewee("Robert Smith")],
        },
    )

    assert result == {"reviewers": [], "reviewees": []}


def test_the_same_rename_alone_is_still_refused(db: Session) -> None:
    """One file is today's rule: the reviewers file is checked against
    the reviewees roster it does not replace."""
    s = _session(db)
    db.add(Reviewee(session_id=s.id, name="Bob Smith", email_or_identifier=BOB))
    db.flush()

    issues = check_incoming_identity(
        db, session_id=s.id, incoming={"reviewers": [_reviewer("Robert Smith")]}
    )["reviewers"]

    assert _problems(issues) == [f"ReviewerEmail {ROSTER_PROBLEM}"]


def test_one_file_keeps_check_cross_table_identity_wording(db: Session) -> None:
    """``check_cross_table_identity`` is now the one-kind case, so pin its
    output literally rather than against itself: every single-file path
    keeps its verdict and wording."""
    s = _session(db)
    db.add(Reviewee(session_id=s.id, name="Bob Smith", email_or_identifier=BOB))
    db.flush()

    (issue,) = check_cross_table_identity(
        db,
        session_id=s.id,
        rows=[_reviewer("Bea", email="b@x.edu"), _reviewer("Robert Smith")],
        kind="reviewers",
    )

    assert issue.row_number == 2
    assert issue.field == "ReviewerEmail"
    assert issue.source == "reviewers"
    assert issue.message == (
        f"ReviewerEmail '{BOB}' is already used by reviewee 'Bob Smith' "
        "in this session — names must match (got 'Robert Smith')."
    )
    assert issue.problem == f"ReviewerEmail {ROSTER_PROBLEM}"


def test_an_uploaded_kind_with_no_rows_still_replaces_its_roster(
    db: Session,
) -> None:
    """A kind in ``incoming`` is being replaced even with no rows (a
    blocked file rides in empty), so its old roster holds no name."""
    s = _session(db)
    db.add(Reviewee(session_id=s.id, name="Bob Smith", email_or_identifier=BOB))
    db.flush()

    result = check_incoming_identity(
        db,
        session_id=s.id,
        incoming={"reviewers": [_reviewer("Robert Smith")], "reviewees": []},
    )

    assert result == {"reviewers": [], "reviewees": []}


def test_two_uploaded_files_that_disagree_are_each_refused(db: Session) -> None:
    """A clash between two incoming files gets its own problem, naming
    the other file, on both sides."""
    s = _session(db)

    result = check_incoming_identity(
        db,
        session_id=s.id,
        incoming={
            "reviewers": [_reviewer("Robert Smith")],
            "reviewees": [_reviewee("Bob Smith")],
        },
    )

    assert _problems(result["reviewers"]) == [
        "ReviewerEmail is used under a different name in the uploaded "
        "Reviewees file"
    ]
    assert _problems(result["reviewees"]) == [
        "RevieweeEmail is used under a different name in the uploaded "
        "Reviewers file"
    ]
    issue = result["reviewers"][0]
    assert issue.row_number == 1
    assert issue.field == "ReviewerEmail"
    assert "'Bob Smith'" in issue.message and "'Robert Smith'" in issue.message


def test_a_roster_not_being_replaced_still_holds_its_name(db: Session) -> None:
    """Uploading reviewers and reviewees leaves the observers roster in
    place, so its name still binds both files."""
    s = _session(db)
    db.add(Observer(session_id=s.id, display_name="Bob Smith", email=BOB))
    db.flush()

    result = check_incoming_identity(
        db,
        session_id=s.id,
        incoming={
            "reviewers": [_reviewer("Robert Smith")],
            "reviewees": [_reviewee("Robert Smith")],
        },
    )

    assert _problems(result["reviewers"]) == [f"ReviewerEmail {ROSTER_PROBLEM}"]
    assert _problems(result["reviewees"]) == [f"RevieweeEmail {ROSTER_PROBLEM}"]


def test_an_existing_roster_clash_is_reported_once_ahead_of_a_file_clash(
    db: Session,
) -> None:
    """A row that clashes with both an existing roster and another
    upload gets one issue, the existing roster's."""
    s = _session(db)
    db.add(Observer(session_id=s.id, display_name="Bob S.", email=BOB))
    db.flush()

    issues = check_incoming_identity(
        db,
        session_id=s.id,
        incoming={
            "reviewers": [_reviewer("Robert Smith")],
            "reviewees": [_reviewee("Bob Smith")],
        },
    )["reviewers"]

    assert _problems(issues) == [f"ReviewerEmail {ROSTER_PROBLEM}"]


def test_status_does_not_matter_on_either_side(db: Session) -> None:
    """An inactive row holds its name like an active one — today's rule
    (Codex on #2998), for existing rows and uploaded ones alike."""
    s = _session(db)
    db.add(
        Observer(
            session_id=s.id, display_name="Bob Smith", email=BOB, status="inactive"
        )
    )
    db.flush()

    existing = check_incoming_identity(
        db, session_id=s.id, incoming={"reviewers": [_reviewer("Robert Smith")]}
    )["reviewers"]
    uploaded = check_incoming_identity(
        db,
        session_id=s.id,
        incoming={
            "reviewers": [_reviewer("Robert Smith", status="inactive")],
            "reviewees": [_reviewee("Rob Smith", status="inactive")],
        },
    )

    assert _problems(existing) == [f"ReviewerEmail {ROSTER_PROBLEM}"]
    # The observer roster stays and disagrees with both files.
    assert len(uploaded["reviewers"]) == 1
    assert len(uploaded["reviewees"]) == 1


def test_rows_that_cannot_disagree_are_skipped(db: Session) -> None:
    """A non-email identifier and an unnamed observer are skipped, as
    ``is_comparable_identity`` skips them for one file."""
    s = _session(db)

    result = check_incoming_identity(
        db,
        session_id=s.id,
        incoming={
            "reviewers": [_reviewer("Robert Smith")],
            "reviewees": [_reviewee("Anon", identifier="anon-2026")],
            "observers": [_observer(None)],
        },
    )

    assert result == {"reviewers": [], "reviewees": [], "observers": []}


def test_a_file_is_not_checked_against_itself(db: Session) -> None:
    """Two names for one email inside one file are the parser's own
    duplicate check, not a cross-roster clash."""
    s = _session(db)

    result = check_incoming_identity(
        db,
        session_id=s.id,
        incoming={"reviewers": [_reviewer("Bob"), _reviewer("Robert")]},
    )

    assert result == {"reviewers": []}


def test_the_cited_upload_is_picked_by_roster_order(db: Session) -> None:
    """Two uploaded files both disagree with a reviewer row: the message
    names the reviewees file, first in roster order, every time."""
    s = _session(db)

    issue = check_incoming_identity(
        db,
        session_id=s.id,
        incoming={
            "observers": [_observer("B. Smith")],
            "reviewees": [_reviewee("Bob Smith")],
            "reviewers": [_reviewer("Robert Smith")],
        },
    )["reviewers"][0]

    assert issue.problem.endswith("in the uploaded Reviewees file")


def test_an_unknown_kind_raises(db: Session) -> None:
    s = _session(db)
    with pytest.raises(ValueError, match="unknown kind"):
        check_incoming_identity(
            db, session_id=s.id, incoming={"relationships": []}
        )


# --------------------------------------------------------------------- #
# Relationships against uploaded rosters
# --------------------------------------------------------------------- #


def _relationships_csv(*pairs: tuple[str, str]) -> bytes:
    lines = ["ReviewerEmail,RevieweeEmail"]
    lines += [f"{reviewer},{reviewee}" for reviewer, reviewee in pairs]
    return ("\n".join(lines) + "\n").encode()


def test_without_uploads_the_current_rosters_are_used(db: Session) -> None:
    s = _session(db)
    reviewer = Reviewer(session_id=s.id, name="Al", email="al@x.edu")
    reviewee = Reviewee(session_id=s.id, name="Cy", email_or_identifier="cy@x.edu")
    db.add_all([reviewer, reviewee])
    db.flush()

    reviewers, reviewees = rosters_for_relationships(db, s.id)

    assert reviewers == [reviewer]
    assert reviewees == [reviewee]


def test_an_uploaded_reviewers_file_replaces_the_current_roster(
    db: Session,
) -> None:
    """A relationship to a reviewer only in the new file parses; one to
    a reviewer only on the roster being replaced is refused, naming the
    uploaded file."""
    s = _session(db)
    db.add_all(
        [
            Reviewer(session_id=s.id, name="Old", email="old@x.edu"),
            Reviewee(session_id=s.id, name="Cy", email_or_identifier="cy@x.edu"),
        ]
    )
    db.flush()

    reviewers, reviewees = rosters_for_relationships(
        db, s.id, incoming_reviewers=[_reviewer("New", email="new@x.edu")]
    )
    result = parse_relationship_csv(
        _relationships_csv(("new@x.edu", "cy@x.edu"), ("old@x.edu", "cy@x.edu")),
        reviewers=reviewers,
        reviewees=reviewees,
        reviewers_uploaded=True,
    )

    assert len(result.rows) == 1
    assert _problems(result.issues) == [
        "ReviewerEmail is not in the uploaded Reviewers file"
    ]
    assert "not in the uploaded Reviewers file" in result.issues[0].message


def test_both_uploaded_rosters_are_used_and_ids_are_stand_ins(
    db: Session,
) -> None:
    """With both files attached nothing is read from the session, and
    the stand-in ids are negative, so a parse against them can never be
    saved as if they were real."""
    s = _session(db)

    reviewers, reviewees = rosters_for_relationships(
        db,
        s.id,
        incoming_reviewers=[_reviewer("Al", email="al@x.edu")],
        incoming_reviewees=[_reviewee("Cy", identifier="cy@x.edu")],
    )
    result = parse_relationship_csv(
        _relationships_csv(("AL@x.edu", "cy@x.edu")),
        reviewers=reviewers,
        reviewees=reviewees,
        reviewers_uploaded=True,
        reviewees_uploaded=True,
    )

    assert reviewers == [IncomingReviewer(id=-1, email="al@x.edu")]
    assert reviewees == [IncomingReviewee(id=-1, email_or_identifier="cy@x.edu")]
    assert result.issues == []
    assert (result.rows[0].reviewer_id, result.rows[0].reviewee_id) == (-1, -1)


def test_a_duplicate_pair_is_still_caught_against_uploaded_rosters(
    db: Session,
) -> None:
    s = _session(db)
    reviewers, reviewees = rosters_for_relationships(
        db,
        s.id,
        incoming_reviewers=[_reviewer("Al", email="al@x.edu")],
        incoming_reviewees=[_reviewee("Cy", identifier="cy@x.edu")],
    )

    result = parse_relationship_csv(
        _relationships_csv(("al@x.edu", "cy@x.edu"), ("al@x.edu", "cy@x.edu")),
        reviewers=reviewers,
        reviewees=reviewees,
        reviewers_uploaded=True,
        reviewees_uploaded=True,
    )

    assert _problems(result.issues) == [
        "A reviewer–reviewee pair appears on more than one row"
    ]


def test_an_uploaded_reviewees_file_names_itself_when_missing(
    db: Session,
) -> None:
    s = _session(db)
    db.add(Reviewer(session_id=s.id, name="Al", email="al@x.edu"))
    db.flush()

    reviewers, reviewees = rosters_for_relationships(
        db, s.id, incoming_reviewees=[_reviewee("Cy", identifier="cy@x.edu")]
    )
    result = parse_relationship_csv(
        _relationships_csv(("al@x.edu", "dee@x.edu")),
        reviewers=reviewers,
        reviewees=reviewees,
        reviewees_uploaded=True,
    )

    assert _problems(result.issues) == [
        "RevieweeEmail is not in the uploaded Reviewees file"
    ]
