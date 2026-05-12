"""Integration tests for Segment 13A-1 PR 1 — the new single-card
Rule Builder page (read-only scaffold).

PR 1 ships the new ``GET /operator/sessions/{id}/assignments/rule-
based-editor`` route with a dropdown listing every visible RuleSet
(seeds first, then caller-owned Personal, then a "+ New blank
RuleSet" sentinel) and a card body that renders the selected
RuleSet's rules as sentence-shaped text. Editable Personal
rendering, Copy / Save / Cancel / Delete, and the functional
blank-draft branch land in PRs 2–3.

The four assertions below mirror the test brief in
``guide/segment_13A_1_rule_based_editor_revamp.md``:

1. GET renders; the dropdown lists 5 seeds + 0 personal + 1 sentinel.
2. First-paint loads the first seed read-only (no form inputs in
   the rule body).
3. Switching the dropdown via ``?rule_set_id=`` updates the read-
   only body server-side (no JS in tests).
4. 404 / 403 for unknown sessions and non-operator callers.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import ReviewSession, SessionRuleSet


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RuleBuilder", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_id(db: Session, *, session_id: int, name: str) -> int:
    """Resolve a seeded SessionRuleSet's id by its workspace name.

    Post-15C-Slice-4b the Rule Builder picker reads from
    ``session_rule_sets`` (the per-session copy table) instead of
    ``operator_rule_sets``. The workspace seeds materialise into
    every session via :func:`materialise_seed_rule_sets` at
    session-create time."""
    return db.execute(
        select(SessionRuleSet.id).where(
            SessionRuleSet.session_id == session_id,
            SessionRuleSet.name == name,
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# GET — page renders, dropdown options, default selection
# ---------------------------------------------------------------------------


def test_rule_builder_page_renders_with_breadcrumbs(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-render")

    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    )

    assert response.status_code == 200, response.text
    body = response.text
    assert "Rule Builder" in body
    # Breadcrumb to the session lands on Assignments → Rule Builder.
    assert f"/operator/sessions/{review_session.id}/assignments" in body


def test_dropdown_lists_all_seeds_and_blank_sentinel(
    client: TestClient, db: Session
) -> None:
    """With zero Personal RuleSets, the dropdown carries the five
    seeds (in install order) + the "+ New blank RuleSet" sentinel."""

    review_session = _make_session(client, db, code="rb-dd")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    ).text

    for seed_name in (
        "Full Matrix",
        "Intra-group peer review",
        "Cross-group peer review",
        "Same group, different role",
        "Three reviewers per reviewee",
    ):
        assert seed_name in body, f"missing seed {seed_name!r} in dropdown"
    assert "+ New blank RuleSet" in body


def test_first_paint_loads_first_seed_read_only(
    client: TestClient, db: Session
) -> None:
    """Default selection is the first session RuleSet (Full Matrix
    materialised from the seed via 15C Slice 1). Seeded session
    copies are workspace-locked (mirror of the RTD spec-lock
    model) — the read-only seed banner renders instead of the
    editable form. Operators customise via Copy → Save-As."""

    review_session = _make_session(client, db, code="rb-first")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    ).text

    assert "Full Matrix" in body
    assert 'id="rule-builder-selector"' in body
    # Seed-banner renders because is_seeded=True on the row;
    # editor form does NOT mount.
    assert 'id="rule-builder-seed-banner"' in body
    assert 'id="rule-based-editor-form"' not in body
    # Copy action still available so the operator can clone-then-
    # customise.
    assert 'id="rule-builder-copy-button"' in body


# ---------------------------------------------------------------------------
# Switching the selected RuleSet via ?rule_set_id=
# ---------------------------------------------------------------------------


def test_switching_dropdown_to_another_seed_updates_body(
    client: TestClient, db: Session
) -> None:
    """Server-side render path: passing ``?rule_set_id=`` reloads the
    page with the named session RuleSet in the card body. Tests run
    no JS, so this exercises the GET handler directly."""

    review_session = _make_session(client, db, code="rb-switch")
    intra_id = _seed_id(
        db, session_id=review_session.id, name="Intra-group peer review"
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based-editor?rule_set_id={intra_id}"
    ).text

    # Selected option in the dropdown reflects the new selection.
    assert f'value="{intra_id}"' in body
    assert "Intra-group peer review" in body


def test_blank_sentinel_renders_live_empty_draft(
    client: TestClient, db: Session
) -> None:
    """Selecting the blank sentinel renders the live empty-draft form
    (Segment 13A-1 PR 3): editable form, no rules, default name
    ``New RuleSet``, and a blank-specific banner. Both ``?new=1``
    and ``?rule_set_id=-1`` reach the same branch."""

    review_session = _make_session(client, db, code="rb-blank")

    for query in ("new=1", "rule_set_id=-1"):
        body = client.get(
            f"/operator/sessions/{review_session.id}"
            f"/assignments/rule-based-editor?{query}"
        ).text
        # Blank-specific banner replaced PR 1's placeholder.
        assert 'id="rule-builder-blank-banner"' in body, (
            f"blank banner missing for query={query!r}"
        )
        assert 'id="rule-builder-blank-placeholder"' not in body
        # Editable form renders with the auto-generated default name.
        assert 'id="rule-based-editor-form"' in body
        assert 'value="New RuleSet"' in body
        # Save button starts disabled (≥1 rule gate, locked decision #8).
        assert 'id="rule-builder-save-button"' in body
        assert "disabled" in body


def test_unknown_rule_set_id_falls_back_to_first_seed(
    client: TestClient, db: Session
) -> None:
    """Stale / unknown ids don't 404 — the URL bar is intentionally
    clean of selection state and refresh must always render."""

    review_session = _make_session(client, db, code="rb-stale")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor?rule_set_id=999999"
    ).text

    # Falls back to Full Matrix (the first seed in install order);
    # the selected option in the dropdown carries the title.
    assert "Full Matrix" in body
    assert 'id="rule-builder-selector"' in body


# ---------------------------------------------------------------------------
# Personal RuleSets in the dropdown
# ---------------------------------------------------------------------------


def test_personal_rule_sets_appear_in_dropdown_after_copy(
    client: TestClient, db: Session
) -> None:
    """Operator-authored RuleSets show up in the dropdown alongside
    the seed-originated copies. Post-15C-Slice-4b they all live in
    ``session_rule_sets`` as editable rows."""

    review_session = _make_session(client, db, code="rb-personal")
    intra_id = _seed_id(
        db, session_id=review_session.id, name="Intra-group peer review"
    )

    # Persist a new RuleSet via Save-As from the Intra-group seed.
    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor/save",
        data={
            "source_rule_set_id": intra_id,
            "name": "Team review",
            "combinator": "ALL_OF",
            "rules_json": "[]",
        },
        follow_redirects=False,
    )
    personal = db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "Team review",
        )
    ).scalar_one()

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based-editor?rule_set_id={personal.id}"
    ).text

    assert "Team review" in body
    # Editable form is rendered — every session-tier row is editable
    # post-Slice 4b, so this is a baseline expectation.
    assert 'id="rule-based-editor-form"' in body
    assert 'id="rule-based-editor-rules-json"' in body
    # Action row carries Save / Cancel / Delete + Copy.
    assert 'id="rule-builder-save-button"' in body
    assert 'id="rule-builder-cancel-button"' in body
    assert 'id="rule-builder-delete-button"' in body
    assert 'id="rule-builder-copy-button"' in body


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------


def test_unknown_session_is_rejected(client: TestClient) -> None:
    """Unknown sessions are rejected by the session permission gate
    (403 from ``require_session_operator`` — same as the existing
    rule-based editor surface)."""

    response = client.get(
        "/operator/sessions/999999/assignments/rule-based-editor"
    )
    assert response.status_code in (403, 404)


def test_non_operator_returns_403(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client,  # noqa: ANN001
) -> None:
    """The session permission gate fires for non-operators."""

    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="rb-403")

    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    )
    assert response.status_code == 403
