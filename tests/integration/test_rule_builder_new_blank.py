"""Integration tests for Segment 13A-1 PR 3 — the live "+ New blank
RuleSet" sentinel.

Replaces the PR 1/PR 2 placeholder branch — selecting the sentinel
now renders an editable form with zero rules, default combinator
``ALL_OF``, and the auto-generated name ``"New RuleSet"``. Save is
gated server-side until at least one rule exists; the Save button
is also gated client-side via inline JS in
``_rule_builder_card.html``.

Mirrors the PR 3 test brief in
``guide/segment_13A_1_rule_based_editor_revamp.md``:

1. Sentinel selectable; renders empty rules list with combinator
   picker.
2. Save with zero rules returns ``303`` with ``?error=empty_rules``.
3. Save with one rule succeeds and creates a Personal "New RuleSet".
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, RuleSet


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RBPR3", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _builder_url(session_id: int, *parts: str) -> str:
    base = (
        f"/operator/sessions/{session_id}"
        "/assignments/rule-based-editor"
    )
    return base if not parts else base + "/" + "/".join(parts)


# ---------------------------------------------------------------------------
# Sentinel renders the live empty-draft form
# ---------------------------------------------------------------------------


def test_blank_sentinel_renders_empty_form_with_combinator_picker(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pr3-blank")

    body = client.get(
        _builder_url(review_session.id) + "?new=1"
    ).text

    # Editable form with the empty rule list.
    assert 'id="rule-based-editor-form"' in body
    assert 'id="rule-based-editor-rule-list"' in body
    # Combinator picker is present and defaults to ALL_OF.
    assert 'id="rule-based-editor-combinator"' in body
    assert 'value="ALL_OF"' in body
    # Auto-generated name pre-populates the input.
    assert 'value="New RuleSet"' in body
    # Hidden marker so the route can identify the blank-draft branch.
    assert 'name="is_blank_draft"' in body
    assert 'value="true"' in body
    # No source provenance is rendered (this is from-scratch, not Copy).
    assert 'name="source_rule_set_id"' not in body
    # Save button is rendered but disabled (zero rules).
    assert 'id="rule-builder-save-button"' in body
    assert "disabled" in body
    # Cancel link goes back to the bare URL (defaults to first seed).
    cancel_url = _builder_url(review_session.id)
    assert (
        f'href="{cancel_url}"' in body
        or f"href='{cancel_url}'" in body
    )


# ---------------------------------------------------------------------------
# Save gate — zero rules → 303 with error=empty_rules
# ---------------------------------------------------------------------------


def test_save_with_zero_rules_returns_empty_rules_error(
    client: TestClient, db: Session
) -> None:
    """Server-side gate fires for crafted POSTs / no-JS clients that
    submit the blank draft form with an empty rules list."""

    review_session = _make_session(client, db, code="pr3-empty")

    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "is_blank_draft": "true",
            "name": "New RuleSet",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers.get("location") or ""
    assert "error=empty_rules" in location
    # Redirect lands back on the blank-draft branch so the operator
    # can keep editing without losing context.
    assert "new=1" in location

    # No Personal RuleSet was created.
    saved = db.execute(
        select(RuleSet).where(
            RuleSet.name == "New RuleSet",
            RuleSet.is_seed.is_(False),
        )
    ).scalar_one_or_none()
    assert saved is None


# ---------------------------------------------------------------------------
# Save with one rule succeeds — creates Personal "New RuleSet"
# ---------------------------------------------------------------------------


def test_save_with_one_rule_creates_personal_new_ruleset(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pr3-one-rule")

    rules = [
        {
            "id": uuid.uuid4().hex,
            "kind": "MATCH",
            "enabled": True,
            "predicate": {
                "field": "reviewer.tag1",
                "operator": "same_as",
                "operand": "reviewee.tag1",
            },
        }
    ]

    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "is_blank_draft": "true",
            "name": "New RuleSet",
            "combinator": "ALL_OF",
            "rules_json": json.dumps(rules),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    location = response.headers.get("location") or ""
    assert "saved=1" in location

    saved = db.execute(
        select(RuleSet).where(
            RuleSet.name == "New RuleSet",
            RuleSet.is_seed.is_(False),
        )
    ).scalar_one()
    # Provenance refs are empty — this RuleSet wasn't copied from
    # any source, it was authored from scratch.
    assert saved.deleted_at is None
    assert saved.is_seed is False


def test_blank_save_auto_suffixes_collision_with_default_name(
    client: TestClient, db: Session
) -> None:
    """The blank-draft default name ``"New RuleSet"`` auto-suffixes
    on collision (mirrors the Copy flow's locked decision #5
    convenience)."""

    review_session = _make_session(client, db, code="pr3-suffix")
    rules = [
        {
            "id": uuid.uuid4().hex,
            "kind": "MATCH",
            "enabled": True,
            "predicate": {
                "field": "reviewer.tag1",
                "operator": "same_as",
                "operand": "reviewee.tag1",
            },
        }
    ]

    payload = {
        "is_blank_draft": "true",
        "name": "New RuleSet",
        "combinator": "ALL_OF",
        "rules_json": json.dumps(rules),
    }

    # First Save → "New RuleSet".
    client.post(
        _builder_url(review_session.id, "save"),
        data=payload,
        follow_redirects=False,
    )
    # Second Save with the same default → auto-suffix to "(2)".
    response = client.post(
        _builder_url(review_session.id, "save"),
        data=payload,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "saved=1" in (response.headers.get("location") or "")

    suffixed = db.execute(
        select(RuleSet).where(RuleSet.name == "New RuleSet (2)")
    ).scalar_one_or_none()
    assert suffixed is not None
