"""The roster upload's countdown (segment 20H Item 6): ``directory-keys``
names the file's addresses still to look up, ``directory-lookup`` looks
a batch up and keeps each answer for fifteen minutes, and the upload
reads what was kept rather than asking Graph again. Only answers the
server fetched are kept; the page posts none."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cordware.graph import FakeDirectory, GraphError
from app.db.models import DirectoryLookup, Reviewer
from app.services import directory_lookups
from app.web.routes_operator import _shared

from ._invitation_states import _create_session

CSV = (
    "ReviewerName,ReviewerEmail\n"
    "Jane,E0123456@example.edu\nOffice,office@example.edu\nNobody,nobody@example.edu\n"
).encode()
KEYS = ["e0123456@example.edu", "office@example.edu", "nobody@example.edu"]


class _Counting(FakeDirectory):
    """The fake directory, counting the addresses it was asked."""

    def __init__(self) -> None:
        super().__init__()
        self.asked: list[str] = []
        self.refuse: str | None = None

    def find_users(self, address: str):
        self.asked.append(address)
        if self.refuse:
            raise GraphError(self.refuse, 401)
        return super().find_users(address)


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> _Counting:
    fake = _Counting()
    monkeypatch.setattr(_shared, "directory_for", lambda request, *a, **k: fake)
    return fake


def _base(client: TestClient, db: Session, code: str) -> tuple[str, int]:
    review_session = _create_session(client, db, code)
    review_session.observers_enabled = True
    db.flush()
    return f"/operator/sessions/{review_session.public_id}", review_session.id


def _keys(client: TestClient, base: str, roster: str = "reviewers", content: bytes = CSV):
    return client.post(
        f"{base}/directory-keys",
        data={"roster": roster},
        files={"file": ("r.csv", content, "text/csv")},
    )


def _look_up(client: TestClient, base: str, keys: list[str]):
    return client.post(f"{base}/directory-lookup", json={"keys": keys})


def test_the_keys_are_the_files_addresses_still_to_look_up(
    client: TestClient, db: Session, directory: _Counting
) -> None:
    base, _ = _base(client, db, "cd-keys")
    answer = _keys(client, base)
    assert answer.status_code == 200 and answer.json() == {"keys": KEYS}
    assert directory.asked == []  # naming the keys asks nothing
    _look_up(client, base, KEYS[:2])
    assert _keys(client, base).json() == {"keys": KEYS[2:]}


def test_a_file_that_does_not_parse_has_no_keys(
    client: TestClient, db: Session, directory: _Counting
) -> None:
    base, _ = _base(client, db, "cd-blocked")
    assert _keys(client, base, content=b"Nonsense\nx\n").json() == {"keys": []}
    assert _keys(client, base, roster="relationships").status_code == 404


def test_each_roster_reads_its_own_columns(
    client: TestClient, db: Session, directory: _Counting
) -> None:
    base, _ = _base(client, db, "cd-rosters")
    reviewees = b"RevieweeName,RevieweeEmail\nAnon,STU-0001\nJane,jane.tan@example.edu\n"
    assert _keys(client, base, "reviewees", reviewees).json() == {"keys": ["jane.tan@example.edu"]}
    observers = b"ObserverName,ObserverEmail\nOffice,Office@Example.edu\n"
    assert _keys(client, base, "observers", observers).json() == {"keys": ["office@example.edu"]}


def test_a_lookup_answers_status_only_and_keeps_the_answers(
    client: TestClient, db: Session, directory: _Counting
) -> None:
    base, session_id = _base(client, db, "cd-lookup")
    answer = _look_up(client, base, KEYS)
    assert answer.status_code == 200
    outcomes = answer.json()["outcomes"]
    assert set(outcomes) == set(KEYS)
    assert outcomes["nobody@example.edu"] == {"status": "NOT_FOUND", "error_kind": ""}
    assert all(set(o) == {"status", "error_kind"} for o in outcomes.values())  # no account
    kept = db.execute(
        select(DirectoryLookup.key).where(DirectoryLookup.session_id == session_id)
    ).scalars().all()
    assert sorted(kept) == sorted(KEYS)


def test_the_upload_reads_the_kept_answers(
    client: TestClient, db: Session, directory: _Counting
) -> None:
    base, session_id = _base(client, db, "cd-upload")
    _look_up(client, base, KEYS[:2])
    directory.asked.clear()
    client.post(f"{base}/reviewers/import", files={"file": ("r.csv", CSV, "text/csv")})
    assert directory.asked == ["nobody@example.edu"]  # only what was not kept
    jane = db.execute(
        select(Reviewer).where(Reviewer.session_id == session_id, Reviewer.name == "Jane")
    ).scalar_one()
    assert jane.directory_upn == "e0123456@example.edu"  # bound from the kept answer


def test_a_failed_lookup_is_not_kept(
    client: TestClient, db: Session, directory: _Counting
) -> None:
    base, session_id = _base(client, db, "cd-failed")
    directory.refuse = "unauthorized"
    outcomes = _look_up(client, base, KEYS[:1]).json()["outcomes"]
    assert outcomes[KEYS[0]] == {"status": "ERROR", "error_kind": "unauthorized"}
    assert db.execute(
        select(DirectoryLookup).where(DirectoryLookup.session_id == session_id)
    ).first() is None
    # The upload asks again, and an expired token stops it (20G).
    response = client.post(f"{base}/reviewers/import", files={"file": ("r.csv", CSV, "text/csv")})
    assert response.status_code == 400


def test_a_stale_answer_is_asked_again_and_swept(
    client: TestClient, db: Session, directory: _Counting
) -> None:
    base, session_id = _base(client, db, "cd-stale")
    _look_up(client, base, KEYS)
    stale = datetime.now(timezone.utc) - directory_lookups.CACHE_TTL - timedelta(seconds=1)
    for row in db.execute(select(DirectoryLookup)).scalars():
        row.fetched_at = stale
    db.flush()
    assert _keys(client, base).json() == {"keys": KEYS}
    assert db.execute(select(DirectoryLookup)).first() is None  # swept


def test_the_answers_are_the_operators_and_the_sessions(
    client: TestClient, db: Session, make_client, bob, directory: _Counting
) -> None:
    base, _ = _base(client, db, "cd-scope")
    other, _ = _base(client, db, "cd-scope-other")
    _look_up(client, base, KEYS)
    assert _keys(client, other).json() == {"keys": KEYS}
    # Another workspace user is not this session's operator.
    assert _look_up(make_client(bob), base, KEYS).status_code in (403, 404)


@pytest.mark.parametrize(
    ("body", "status", "error"),
    [
        ({"keys": []}, 400, "bad_keys"),
        ({"keys": ["Not@Folded.example"]}, 400, "bad_keys"),
        ({"keys": ["a@example.edu"] * 26}, 400, "bad_keys"),
        ({"nope": 1}, 400, "bad_keys"),
    ],
)
def test_a_bad_batch_is_refused(
    client: TestClient, db: Session, directory: _Counting, body, status, error
) -> None:
    base, _ = _base(client, db, f"cd-bad-{status}-{len(str(body))}")
    answer = client.post(f"{base}/directory-lookup", json=body)
    assert (answer.status_code, answer.json()) == (status, {"error": error})
    assert directory.asked == []


def test_a_lookup_is_json_only_and_needs_the_directory(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    base, _ = _base(client, db, "cd-json")
    form = client.post(f"{base}/directory-lookup", data={"keys": KEYS[0]})
    assert form.status_code == 415

    def no_token(request, *a, **k):
        raise GraphError("no_token")

    monkeypatch.setattr(_shared, "directory_for", no_token)
    assert _look_up(client, base, KEYS[:1]).json() == {"error": "no_graph"}
