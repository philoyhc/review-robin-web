from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, AuditEvent, ReviewSession
from ._full_matrix import full_matrix_seed_id


def _make_session(
    client: TestClient, db: Session, code: str = "spring-2026"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_roster(
    client: TestClient,
    session_id: int,
    *,
    reviewer_emails: list[str],
    reviewee_idents: list[str],
) -> None:
    reviewer_csv = "ReviewerName,ReviewerEmail\n" + "".join(
        f"R{i},{email}\n" for i, email in enumerate(reviewer_emails)
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={"file": ("r.csv", reviewer_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    reviewee_csv = "RevieweeName,RevieweeEmail\n" + "".join(
        f"E{i},{ident}\n" for i, ident in enumerate(reviewee_idents)
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={"file": ("e.csv", reviewee_csv.encode(), "text/csv")},
        follow_redirects=False,
    )


def test_full_matrix_save_persists_assignments_and_sets_mode(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu", "dan-2026"],
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )
    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert len(rows) == 2
    assert all(r.created_by_mode == "rule_based" for r in rows)

    db.refresh(review_session)
    assert review_session.assignment_mode == "rule_based"

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "assignments.generated")
    ).scalar_one()
    assert event.detail["session_code"] == "spring-2026"
    assert event.detail["counts"] == {
        "new": 2,
        "replaced": 0,
        "pairs": 2,
        "instruments": 1,
    }
    assert event.detail["context"]["mode"] == "rule_based"


def test_full_matrix_fans_pairs_out_per_instrument(
    client: TestClient, db: Session
) -> None:
    """Each (reviewer, reviewee) pair gets one Assignment row per
    instrument. Without the fanout, multi-instrument sessions only
    show the default instrument's table on the reviewer surface
    (since the surface filters by the reviewer's Assignments).

    Regression for: PR #410-era reports of "Next button doesn't show
    on multi-instrument sessions" — full-matrix was pinning every
    pair to the default instrument so `instrument_groups|length`
    stayed at 1.
    """
    from app.db.models import Instrument

    review_session = _make_session(client, db, code="multi-fan")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu", "dan-2026"],
    )
    # Add a second instrument before generating assignments.
    [default_instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add",
        data={"after": str(default_instrument.id)},
        follow_redirects=False,
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    # 2 pairs × 2 instruments = 4 Assignment rows.
    assert len(rows) == 4
    instrument_ids = {r.instrument_id for r in rows}
    assert len(instrument_ids) == 2
    # Each pair appears once per instrument.
    pair_counts: dict[tuple[int, int], int] = {}
    for r in rows:
        key = (r.reviewer_id, r.reviewee_id)
        pair_counts[key] = pair_counts.get(key, 0) + 1
    assert all(count == 2 for count in pair_counts.values())

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "assignments.generated")
    ).scalar_one()
    counts = event.detail["counts"]
    assert counts["new"] == 4
    assert counts["pairs"] == 2
    assert counts["instruments"] == 2


def test_full_matrix_re_save_without_confirm_blocks(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
        follow_redirects=False,
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": ""},
        follow_redirects=False,
    )

    # The rule-based-generate route 303s with the needs_confirm query
    # param; assignments stay untouched until confirm_replace=true.
    assert response.status_code == 303
    assert "rule_based_error=needs_confirm" in response.headers["location"]
    assert (
        len(
            list(
                db.execute(
                    select(Assignment).where(
                        Assignment.session_id == review_session.id
                    )
                ).scalars()
            )
        )
        == 1
    )


def test_full_matrix_re_save_with_confirm_replaces(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
        follow_redirects=False,
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "", "confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    events = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "assignments.generated")
            .order_by(AuditEvent.id.desc())
        ).scalars()
    )
    assert events[0].detail["counts"]["replaced"] == 1


def test_assignments_hub_no_longer_renders_standalone_full_matrix_card(
    client: TestClient, db: Session
) -> None:
    """Segment 13A PR 8 retired the standalone Full Matrix card; 12C-1
    PR 3 deleted the underlying ``/assignments/full-matrix`` route;
    15D PR 6a moved the page to the Operations row and dropped the
    operator-facing manual upload card. Rule Based card remains."""

    review_session = _make_session(client, db)
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text

    # The legacy Full Matrix card heading + URL are both gone.
    assert "<h2>Full Matrix Assignment</h2>" not in body
    assert (
        f'action="/operator/sessions/{review_session.id}'
        '/assignments/full-matrix"'
        not in body
    )
    # Operator-facing manual upload card retired in 15D PR 6a.
    assert 'id="upload-csv"' not in body
    # Rule Based card stays — it IS the Generate path post-15D.
    assert 'id="rule-based-assignment"' in body


def test_assignments_hub_renders_count_and_mode(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    empty = client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert empty.status_code == 200
    # Empty state shows the reviewer/reviewee counts in the chrome status
    # row; the FullMatrix Generate button is rendered inline on the page.
    assert "Reviewers:" in empty.text
    assert ">Generate</button>" in empty.text
    # The chrome strip no longer reports an Assignments slot.
    assert "Assignments:" not in empty.text

    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
        follow_redirects=False,
    )

    populated = client.get(f"/operator/sessions/{review_session.id}/assignments")
    # Populated state surfaces via the Current pairs / Self-reviews
    # cards on the page itself rather than a chrome-strip slot.
    assert "Current pairs" in populated.text
    assert 'id="self-reviews-toggle"' in populated.text


def test_non_operator_gets_403_on_assignments_hub_and_post(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="alice-only")

    bob_client = make_client(bob)
    hub = bob_client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert hub.status_code == 403

    post = bob_client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
        follow_redirects=False,
    )
    assert post.status_code == 403


def test_assignments_hub_truncates_large_pair_list(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=[f"r{i}@example.edu" for i in range(7)],
        reviewee_idents=[f"e{i}@example.edu" for i in range(31)],
    )

    # Save 217 pairs
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": ""},
        follow_redirects=False,
    )

    # The hub hosts the Current pairs preview after save
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert "Showing first 200 of 217" in body
    assert "and 17 more" in body


def test_manual_save_persists_with_include(
    client: TestClient, db: Session
) -> None:
    """15D PR 6b retired the per-row ``context`` JSON column on
    Assignment. The manual-CSV path still saves rows + Include flag;
    the AssignmentContext1/2/3 CSV columns are silently ignored
    (no longer have a destination)."""

    review_session = _make_session(client, db, code="m-save")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu", "bob@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    csv_body = (
        b"ReviewerEmail,RevieweeEmail,IncludeAssignment,"
        b"AssignmentContext1,AssignmentContext2\n"
        b"alice@example.edu,carol@example.edu,true,morning,room-A\n"
        b"bob@example.edu,carol@example.edu,false,,\n"
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={"file": ("manual.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert len(rows) == 2
    by_reviewer = {r.reviewer.email: r for r in rows}
    assert by_reviewer["alice@example.edu"].include is True
    assert by_reviewer["bob@example.edu"].include is False
    assert all(r.created_by_mode == "manual" for r in rows)

    db.refresh(review_session)
    assert review_session.assignment_mode == "manual"

    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "assignments.generated")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["context"]["mode"] == "manual"
    assert event.detail["counts"]["new"] == 2
    assert event.detail["context"]["filename"] == "manual.csv"


def test_manual_import_blocks_unknown_reviewer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="m-bad")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "manual.csv",
                b"ReviewerEmail,RevieweeEmail\nghost@example.edu,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Unknown reviewer" in response.text
    assert (
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).first()
        is None
    )


def test_non_operator_gets_403_on_manual_import(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="m-403")

    bob_client = make_client(bob)
    response = bob_client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "manual.csv",
                b"ReviewerEmail,RevieweeEmail\nfoo@example.edu,bar@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_hub_renders_current_pairs_card_when_assignments_exist(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="hub-pairs")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    empty = client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert "Current pairs" not in empty.text

    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
        follow_redirects=False,
    )

    populated = client.get(f"/operator/sessions/{review_session.id}/assignments")
    body = populated.text
    assert "Current pairs" in body
    assert "alice@example.edu" in body
    assert "carol@example.edu" in body


def test_hub_renders_per_slot_columns_with_visibility_toggles(
    client: TestClient, db: Session
) -> None:
    """15D PR 6b: pair_context columns now read from the relationships
    table, not the retired ``Assignment.context`` JSON. Assignment-
    context (a1/a2/a3) columns retired entirely. Reviewer / reviewee
    tag toggles + Pair toggles still drive visibility."""

    review_session = _make_session(client, db, code="hub-cols")
    reviewer_csv = (
        "ReviewerName,ReviewerEmail,ReviewerTag1\n"
        "Alice,alice@example.edu,senior\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", reviewer_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    reviewee_csv = (
        "RevieweeName,RevieweeEmail,RevieweeTag2\n"
        "Carol,carol@example.edu,cohort-a\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": ("e.csv", reviewee_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    rel_csv = (
        "ReviewerEmail,RevieweeEmail,PairContextTag1\n"
        "alice@example.edu,carol@example.edu,bench-a\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={"file": ("rel.csv", rel_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    asgn_csv = (
        "ReviewerEmail,RevieweeEmail,IncludeAssignment\n"
        "alice@example.edu,carol@example.edu,yes\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={"file": ("a.csv", asgn_csv.encode(), "text/csv")},
        follow_redirects=False,
    )

    body = client.get(f"/operator/sessions/{review_session.id}/assignments").text

    # Header carries every per-slot column even when the data is sparse;
    # JS hides the empty ones via the toggle row. AssignmentContext
    # (a1/a2/a3) retired in 15D PR 6b.
    assert '<th class="assignment-col col-rt1">Tag1</th>' in body
    assert '<th class="assignment-col col-et2">Tag2</th>' in body
    assert '<th class="assignment-col col-p1">Pair1</th>' in body
    assert "col-a3" not in body
    assert "<th>Reviewer</th>" in body
    assert "<th>Reviewee</th>" in body
    assert "<th>Include</th>" in body

    # Per-slot cells render values from rosters + relationships.
    assert ">senior</td>" in body
    assert ">cohort-a</td>" in body
    assert ">bench-a</td>" in body

    # Toggle initial state — only the slots that have data are ticked,
    # and slots without data render disabled with a tooltip.
    assert 'data-col-toggle="rt1"\n                       checked' in body
    assert 'data-col-toggle="et2"\n                       checked' in body
    assert 'data-col-toggle="p1"\n                       checked' in body
    assert 'data-col-toggle="rt2"\n                       checked' not in body
    assert 'data-col-toggle="p3"\n                       checked' not in body
    assert (
        'data-col-toggle="rt2"\n                       '
        'disabled aria-disabled="true" title="No data in this column"'
    ) in body
    assert (
        'data-col-toggle="p3"\n                       '
        'disabled aria-disabled="true" title="No data in this column"'
    ) in body
    # Ticked toggles are NOT disabled.
    assert 'data-col-toggle="rt1"\n                       disabled' not in body


def test_manual_setup_page_shows_saved_pair_after_import(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="m-names")
    reviewer_csv = (
        "ReviewerName,ReviewerEmail\n"
        "Alice Example,alice@example.edu\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", reviewer_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    reviewee_csv = (
        "RevieweeName,RevieweeEmail\n"
        "Carol Example,carol@example.edu\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": ("e.csv", reviewee_csv.encode(), "text/csv")},
        follow_redirects=False,
    )

    save = client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "manual.csv",
                b"ReviewerEmail,RevieweeEmail\nalice@example.edu,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert "Alice Example" in body
    assert "Carol Example" in body


def test_manual_save_silently_ignores_pair_and_assignment_context_columns(
    client: TestClient, db: Session
) -> None:
    """15D PR 6b: ``Assignment.context`` retired. The
    ``PairContext1/2/3`` and ``AssignmentContext1/2/3`` CSV columns
    on a manual upload are silently ignored — pair_context lives on
    the relationships table now (uploaded separately), and
    assignment_context retired entirely."""

    review_session = _make_session(client, db, code="m-context")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    csv_body = (
        b"ReviewerEmail,RevieweeEmail,PairContext1,AssignmentContext1\n"
        b"alice@example.edu,carol@example.edu,room-A,panel-1\n"
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={"file": ("manual.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    # The Assignment row exists; the extra CSV columns are dropped
    # silently. ``context`` no longer exists on the Assignment model.
    assert not hasattr(assignment, "context")
