"""Integration coverage for the Setup-Observers page.

The page renders behind the per-session ``observers_enabled``
toggle; this test file pins the route gate (404 off / 200 on),
the four core cards (Upload / Operator actions / preview table /
Danger Zone), CRUD smoke coverage, and the nav-tab visibility
flip.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession


def _make_session(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Obs", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _enable_observers(
    db: Session, review_session: ReviewSession
) -> None:
    review_session.observers_enabled = True
    db.commit()
    db.refresh(review_session)


# ── Route gate ────────────────────────────────────────────────────────


def test_observers_route_404_when_flag_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-off")
    response = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    )
    assert response.status_code == 404


def test_observers_route_200_when_flag_on(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-on")
    _enable_observers(db, review_session)
    response = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    )
    assert response.status_code == 200


# ── Nav tab visibility ───────────────────────────────────────────────


def test_observers_nav_tab_hidden_when_flag_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-nav-off")
    body = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert (
        f'href="/operator/sessions/{review_session.id}/observers"'
        not in body
    )


def test_observers_nav_tab_visible_when_flag_on(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-nav-on")
    _enable_observers(db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert (
        f'href="/operator/sessions/{review_session.id}/observers"'
        in body
    )


# ── Card surface ─────────────────────────────────────────────────────


def test_observers_page_renders_core_cards(
    client: TestClient, db: Session
) -> None:
    """Upload + Operator actions render; preview table empty-state
    sits between them; Danger Zone is hidden until rows exist."""
    review_session = _make_session(client, db, "obs-cards")
    _enable_observers(db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text
    assert 'id="upload-csv"' in body
    assert "Upload Observers" in body
    assert "Operator actions" in body
    # No rows yet → no Danger Zone.
    assert "Delete all observers" not in body
    # Empty-state hint.
    assert "No observers yet." in body


def test_observers_page_danger_zone_shows_when_rows_exist(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-dz")
    _enable_observers(db, review_session)
    db.add(
        Observer(
            session_id=review_session.id,
            email="a@example.org",
            display_name="A",
        )
    )
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text
    assert "Danger Zone" in body
    assert "Delete all observers" in body


def test_observers_page_renders_seeded_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-seeded")
    _enable_observers(db, review_session)
    db.add_all(
        [
            Observer(
                session_id=review_session.id,
                email="zoe@example.org",
                display_name="Zoe",
                tag_1="committee",
            ),
            Observer(
                session_id=review_session.id,
                email="alex@example.org",
                display_name="Alex",
            ),
        ]
    )
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text
    assert "zoe@example.org" in body
    assert "alex@example.org" in body
    assert ">Zoe<" in body
    assert ">committee<" in body
    # Per-row select checkbox renders for each observer.
    assert body.count('class="observer-select"') == 2


# ── CRUD smoke ───────────────────────────────────────────────────────


def test_observer_create_persists_and_redirects(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-create")
    _enable_observers(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/create",
        data={
            "email": "new@example.org",
            "display_name": "New",
            "tag_1": "committee",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.execute(
        select(Observer).where(
            Observer.session_id == review_session.id,
            Observer.email == "new@example.org",
        )
    ).scalar_one()
    assert row.display_name == "New"
    assert row.tag_1 == "committee"
    assert row.status == "active"


def test_observer_create_rejects_duplicate_email(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-dupe")
    _enable_observers(db, review_session)
    db.add(
        Observer(
            session_id=review_session.id,
            email="dupe@example.org",
            display_name="First",
        )
    )
    db.commit()
    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/create",
        data={
            "email": "dupe@example.org",
            "display_name": "Second",
            "tag_1": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "already uses" in response.text


def test_observer_update_changes_fields(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-update")
    _enable_observers(db, review_session)
    observer = Observer(
        session_id=review_session.id,
        email="old@example.org",
        display_name="Old",
        tag_1="committee",
    )
    db.add(observer)
    db.commit()
    db.refresh(observer)
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/observers/{observer.id}/update",
        data={
            "email": "new@example.org",
            "display_name": "New",
            "tag_1": "advisor",
            "status": "inactive",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(observer)
    assert observer.email == "new@example.org"
    assert observer.display_name == "New"
    assert observer.tag_1 == "advisor"
    assert observer.status == "inactive"


def test_observer_bulk_inactivate(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-bulk")
    _enable_observers(db, review_session)
    o1 = Observer(
        session_id=review_session.id,
        email="a@example.org",
        display_name="A",
    )
    o2 = Observer(
        session_id=review_session.id,
        email="b@example.org",
        display_name="B",
    )
    db.add_all([o1, o2])
    db.commit()
    db.refresh(o1)
    db.refresh(o2)
    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/bulk-inactivate",
        data={"observer_ids": [o1.id, o2.id]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(o1)
    db.refresh(o2)
    assert o1.status == "inactive"
    assert o2.status == "inactive"


def test_observer_cohort_rule_save_persists_to_selected(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-cohort-route")
    _enable_observers(db, review_session)
    o1 = Observer(
        session_id=review_session.id, email="a@example.org", display_name="A"
    )
    o2 = Observer(
        session_id=review_session.id, email="b@example.org", display_name="B"
    )
    o3 = Observer(
        session_id=review_session.id, email="c@example.org", display_name="C"
    )
    db.add_all([o1, o2, o3])
    db.commit()
    db.refresh(o1)
    db.refresh(o2)
    db.refresh(o3)

    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/cohort-rule",
        data={
            "observer_ids": [o1.id, o2.id],
            "cohort_combinator": "OR",
            "cohort_rule_field": ["reviewer.tag1"],
            "cohort_rule_op": ["IS"],
            "cohort_rule_operand_tag": [""],
            "cohort_rule_operand_value": ["math"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    db.refresh(o1)
    db.refresh(o2)
    db.refresh(o3)
    expected = {
        "combinator": "OR",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "math",
            }
        ],
    }
    assert o1.cohort_rule == expected
    assert o2.cohort_rule == expected
    assert o3.cohort_rule is None


def test_observer_cohort_rule_save_rejects_empty_selection(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-cohort-empty")
    _enable_observers(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/cohort-rule",
        data={"cohort_combinator": "AND"},
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_observer_cohort_rule_save_drops_blank_rule(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-cohort-blank")
    _enable_observers(db, review_session)
    obs = Observer(
        session_id=review_session.id, email="x@example.org", display_name="X"
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/cohort-rule",
        data={
            "observer_ids": [obs.id],
            "cohort_combinator": "AND",
            "cohort_rule_field": [""],
            "cohort_rule_op": ["IS"],
            "cohort_rule_operand_tag": [""],
            "cohort_rule_operand_value": ["irrelevant"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    db.refresh(obs)
    assert obs.cohort_rule == {"combinator": "AND", "rules": []}


def test_observer_cohort_rule_save_rejects_invalid_payload(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-cohort-bad")
    _enable_observers(db, review_session)
    obs = Observer(
        session_id=review_session.id, email="x@example.org", display_name="X"
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/cohort-rule",
        data={
            "observer_ids": [obs.id],
            "cohort_combinator": "AND",
            "cohort_rule_field": ["reviewer.tag9"],
            "cohort_rule_op": ["IS"],
            "cohort_rule_operand_tag": [""],
            "cohort_rule_operand_value": ["x"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_observer_delete_all_clears_roster(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-delall")
    _enable_observers(db, review_session)
    db.add_all(
        [
            Observer(
                session_id=review_session.id,
                email="a@example.org",
                display_name="A",
            ),
            Observer(
                session_id=review_session.id,
                email="b@example.org",
                display_name="B",
            ),
        ]
    )
    db.commit()
    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    remaining = db.execute(
        select(Observer).where(Observer.session_id == review_session.id)
    ).scalars().all()
    assert remaining == []


def test_observer_csv_import_persists(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-import")
    _enable_observers(db, review_session)
    csv_bytes = (
        b"ObserverEmail,ObserverName,ObserverTag1\n"
        b"x@example.org,Xavier,committee\n"
        b"y@example.org,Yara,\n"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/import",
        files={"file": ("o.csv", csv_bytes, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    rows = db.execute(
        select(Observer)
        .where(Observer.session_id == review_session.id)
        .order_by(Observer.email)
    ).scalars().all()
    assert [(o.email, o.display_name, o.tag_1) for o in rows] == [
        ("x@example.org", "Xavier", "committee"),
        ("y@example.org", "Yara", None),
    ]


def test_observer_csv_import_rejects_missing_email_column(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-bad-csv")
    _enable_observers(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/import",
        files={
            "file": ("o.csv", b"ObserverName\nXavier\n", "text/csv"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Missing required column: ObserverEmail" in response.text


# ── Chrome ───────────────────────────────────────────────────────────


def test_observers_page_marks_observers_nav_tab_active(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-active")
    _enable_observers(db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text
    assert 'class="nav-tab active"' in body
    assert (
        f'class="nav-tab active"\n       href="/operator/sessions/{review_session.id}/observers"'
        in body
    )
