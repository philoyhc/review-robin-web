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
from app.db.models import ReviewSession, RuleSet


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


def _seed_id(db: Session, name: str) -> int:
    return db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True), RuleSet.name == name
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
    """Default selection is the first seed (Full Matrix). The body
    renders read-only — no form inputs inside the rule list, no
    Copy / Save / Cancel / Delete affordance yet."""

    review_session = _make_session(client, db, code="rb-first")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    ).text

    # Default selection is Full Matrix, the first seed in install
    # order. The name is rendered inside the card heading.
    assert 'id="rule-builder-name"' in body
    assert "Full Matrix" in body
    # Seeded read-only banner is the load-bearing signal that this
    # is not editable yet — PR 2 will branch on Personal to render
    # an editable form instead.
    assert 'id="rule-builder-seed-banner"' in body
    # No form inputs inside the rendered rule list. The dropdown
    # itself is a <select>, but the rule body must not carry any.
    rules_marker = 'id="rule-builder-rules"'
    if rules_marker in body:
        rules_block_start = body.index(rules_marker)
        rules_block = body[rules_block_start : rules_block_start + 4000]
        for tag in ("<input", "<textarea"):
            assert tag not in rules_block, (
                f"rule body should be read-only but contains {tag!r}"
            )


# ---------------------------------------------------------------------------
# Switching the selected RuleSet via ?rule_set_id=
# ---------------------------------------------------------------------------


def test_switching_dropdown_to_another_seed_updates_body(
    client: TestClient, db: Session
) -> None:
    """Server-side render path: passing ``?rule_set_id=`` reloads the
    page with the named seed in the card body. Tests run no JS, so
    this exercises the GET handler directly."""

    review_session = _make_session(client, db, code="rb-switch")
    intra_id = _seed_id(db, "Intra-group peer review")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based-editor?rule_set_id={intra_id}"
    ).text

    # Heading reflects the new selection.
    assert 'id="rule-builder-name"' in body
    name_block_start = body.index('id="rule-builder-name"')
    name_block = body[name_block_start : name_block_start + 200]
    assert "Intra-group peer review" in name_block
    # The seed body renders the canonical Match sentence for this
    # seed: ``reviewer.tag1 same_as reviewee.tag1`` flattens to
    # "reviewer tag1 is the same as reviewee tag1" (PR 5a renderer).
    assert "reviewer tag1 is the same as reviewee tag1" in body


def test_blank_sentinel_renders_pr3_placeholder(
    client: TestClient, db: Session
) -> None:
    """Selecting the blank sentinel in PR 1 surfaces a placeholder
    pointing at PR 3 — the functional blank-draft branch lands then.
    Tests both ``?new=1`` and the sentinel id directly."""

    review_session = _make_session(client, db, code="rb-blank")

    for query in ("new=1", "rule_set_id=-1"):
        body = client.get(
            f"/operator/sessions/{review_session.id}"
            f"/assignments/rule-based-editor?{query}"
        ).text
        assert 'id="rule-builder-blank-placeholder"' in body, (
            f"blank placeholder missing for query={query!r}"
        )
        # No seeded card heading on the blank branch.
        assert 'id="rule-builder-name"' not in body


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

    assert 'id="rule-builder-name"' in body
    assert "Full Matrix" in body


# ---------------------------------------------------------------------------
# Personal RuleSets in the dropdown
# ---------------------------------------------------------------------------


def test_personal_rule_sets_appear_in_dropdown_after_copy(
    client: TestClient, db: Session
) -> None:
    """Personal RuleSets owned by the caller show up below the seeds
    in the dropdown. PR 1 still renders them read-only; the editable
    form lands in PR 2."""

    review_session = _make_session(client, db, code="rb-personal")
    intra_id = _seed_id(db, "Intra-group peer review")

    # Reuse the existing Segment 13A copy route to seed a Personal
    # RuleSet without depending on PR 2's new POST handler.
    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "Team review"},
        follow_redirects=False,
    )
    personal = db.execute(
        select(RuleSet).where(RuleSet.name == "Team review")
    ).scalar_one()

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based-editor?rule_set_id={personal.id}"
    ).text

    # Personal RuleSet name appears in the dropdown options and as
    # the card heading.
    assert "Team review" in body
    # Editable form is rendered (PR 2) — the PR 5b/5c indent-stack
    # form's marker IDs are present.
    assert 'id="rule-based-editor-form"' in body
    assert 'id="rule-based-editor-rules-json"' in body
    # No seeded banner on a Personal selection.
    assert 'id="rule-builder-seed-banner"' not in body
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
