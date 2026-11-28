"""The localhost seed's scenarios (segment AD2X): exercises built the way an
operator builds them, by posting what the pages post to Apply Desk's own
routes, signed in as Cordware's fake identity, Local Operator. So each
scenario runs the pages' checks and leaves the audit trail they leave.

The tests keep `seed.seed()` and its sample exercises; this is localhost's.
A scenario is found by its name among the exercises Local Operator created
and then left alone, so a second run changes nothing; `--reset` starts
again. Refused unless `APP_ENV=local` with fake auth on: the pages need a
signed-in operator, and the samples are never production's (ruling 74).

New capabilities add a scenario here as they land.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, cast
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from applydesk import applications, db, ids, operators, people, sample_data
from applydesk.local_directory import PEOPLE
from applydesk.models import Application, Candidate, Exercise, Person
from cordware.identity import Identity, alternate_identity, is_local
from cordware.settings import IdentitySettings, identity_settings


class _Reply(Protocol):
    status_code: int
    text: str
    headers: Mapping[str, str]


class TestClient(Protocol):
    """What the seed asks of Starlette's test client: the pages' requests."""

    def get(self, url: str) -> _Reply: ...

    def post(
        self,
        url: str,
        *,
        data: dict[str, str] | None = None,
        json: object = None,
        follow_redirects: bool | None = None,
    ) -> _Reply: ...


#: The seed acts as the platform when it admits Local Operator to operate.
_PLATFORM = operators.Actor(None, is_super_admin=True, platform=True)
#: How long the open form stays open from the run (segment AD2X), and how
#: long before the run it opened, so the seeded applications fall inside.
OPEN_FOR = timedelta(days=30)
#: How long before the run the form opened, so the seeded applications,
#: dated up to six days back, fall inside its window (cold read).
OPENED = timedelta(days=10)
#: How many applications Scenario 1 makes.
APPLICANTS = 6

OPEN_FORM = "Community Project Grant 2027"
CREATE_DOSSIERS = "Peer Mentor Nominations 2027"


class LocalSeedRefused(RuntimeError):
    """The scenarios were asked for where they cannot run."""


@dataclass(frozen=True)
class Made:
    """One scenario's exercise: its name, public ID, and whether this run
    made it (False: it was there already)."""

    name: str
    public_id: str
    made: bool


def _fake_identity(settings: IdentitySettings) -> Identity:
    return Identity(
        principal_id=settings.fake_auth_principal_id,
        email=settings.fake_auth_email,
        name=settings.fake_auth_name,
        provider="fake",
        is_fake=True,
        tenant_id=settings.fake_auth_tenant_id.strip() or None,
        upn=settings.fake_auth_upn.strip() or settings.fake_auth_email,
        mail=settings.fake_auth_mail.strip() or settings.fake_auth_email,
    )


def owner(settings: IdentitySettings | None = None) -> Person:
    """Local Operator, bound as a sign-in binds them and admitted to
    operate; committed. Detached, for its ID."""
    settings = settings or identity_settings
    session = db.new_session()
    try:
        person = people.resolve(session, _fake_identity(settings))
        if person is None:
            raise LocalSeedRefused("the fake identity has no tenant or principal ID to bind")
        if not operators.may_operate(person):
            operators.admit(session, _PLATFORM, person)
        session.commit()
        session.refresh(person)
        session.expunge(person)
        return person
    finally:
        session.close()


def _existing(owner_id: int, name: str, complete: Callable[[str], bool]) -> str | None:
    """The scenario's exercise if Local Operator made it already. One left
    half-built by a failed run is refused, never passed off as there: a
    re-run cannot tell what the failure skipped (cold read)."""
    session = db.new_session()
    try:
        found = session.scalar(
            select(Exercise.public_id).where(
                Exercise.created_by_id == owner_id,
                Exercise.name == name,
                Exercise.deleted_at.is_(None),
            )
        )
    finally:
        session.close()
    if found is not None and not complete(found):
        raise LocalSeedRefused(
            f"{name!r} ({found}) is there but not complete, from a run that failed "
            "part-way; `python -m applydesk.seed --reset` builds it again"
        )
    return found


def _count(public_id: str, model: type[Application] | type[Candidate]) -> int:
    session = db.new_session()
    try:
        row = session.scalars(select(Exercise).where(Exercise.public_id == public_id)).one()
        return (
            session.scalar(
                select(func.count()).select_from(model).where(model.exercise_id == row.id)
            )
            or 0
        )
    finally:
        session.close()


def _client() -> TestClient:
    """Apply Desk alone, in process: each request is the fake identity."""
    from fastapi.testclient import TestClient as Starlette

    from applydesk.main import create_app

    # The pages' requests are same-origin; the operator pages refuse others.
    client = Starlette(create_app(), headers={"sec-fetch-site": "same-origin"})
    return cast(TestClient, client)


def _ok(reply: _Reply, what: str) -> _Reply:
    if reply.status_code not in (200, 303):
        raise LocalSeedRefused(f"{what} was refused ({reply.status_code}): {reply.text[:300]}")
    return reply


def _revision(page: str) -> int:
    found = re.search(r'data-revision="(\d+)"', page)
    return int(found.group(1)) if found else 0


def _make(client: TestClient, name: str) -> str:
    reply = _ok(
        client.post("/operator/exercises/new", data={"name": name}, follow_redirects=False),
        f"New exercise {name!r}",
    )
    found = re.search(r"/operator/exercises/(\w+)$", reply.headers["location"])
    if found is None:
        raise LocalSeedRefused(f"New exercise {name!r} went to {reply.headers['location']}")
    return found.group(1)


def _people(start: int, count: int, but: str = "") -> list[tuple[str, str]]:
    """``count`` people of the local directory from ``start``, wrapping,
    leaving out the address ``but`` (the second fake account, a plain
    applicant, sits on no panel and holds no dossier)."""
    out: list[tuple[str, str]] = []
    i = start
    while len(out) < count:
        person = PEOPLE[i % len(PEOPLE)]
        if person[1].lower() != but.strip().lower():
            out.append(person)
        i += 1
    return out


def _panels(
    client: TestClient, public_id: str, operator: tuple[str, str], start: int
) -> tuple[str, str]:
    """Two panels of four, Local Operator on the first; the keys the
    server gave them."""
    base = f"/operator/exercises/{public_id}/panels"
    alternate = identity_settings.fake_auth_alt_email
    picked = _people(start, 7, but=alternate)
    first, second = picked[:3], picked[3:]
    rows: list[dict[str, object]] = [
        {"name": operator[0], "email": operator[1], "note": "", "panels": ["made-1"]},
        *({"name": n, "email": e, "note": "", "panels": ["made-1"]} for n, e in first),
        *({"name": n, "email": e, "note": "", "panels": ["made-2"]} for n, e in second),
    ]
    sent: dict[str, object] = {
        "revision": _revision(client.get(base).text),
        "panels": [{"key": "made-1", "name": "Readers"}, {"key": "made-2", "name": "Mentors"}],
        "people": rows,
    }
    _ok(client.post(base, json=sent), "Panels' Save")
    from applydesk import panels_store

    state = panels_store.stored(public_id)
    if state is None:
        raise LocalSeedRefused("Panels' Save left no panels")
    keys = {p.name: p.key for p in state.panels}
    if "Readers" not in keys or "Mentors" not in keys:
        raise LocalSeedRefused(f"Panels' Save kept {sorted(keys)}, not Readers and Mentors")
    return keys["Readers"], keys["Mentors"]


def _field(label: str, of_type: str = "string", **over: object) -> dict[str, object]:
    card: dict[str, object] = {
        "kind": "field",
        "type": of_type,
        "label": label,
        "help": "",
        "min": "",
        "max": "",
        "step": "",
        "options": "",
        "exclusive": True,
        "required": False,
        "shown": True,
        "pool": "institution",
        "ratio_w": "4",
        "ratio_h": "5",
    }
    card.update(over)
    return card


def _when(at: datetime) -> str:
    return at.strftime("%Y-%m-%dT%H:%M")


def open_form(client: TestClient, owner: Person, settings: IdentitySettings) -> Made:
    """Scenario 1: a published Form, open for 30 days from the run, that
    anyone signed in may apply to; two panels; six applications by people
    of the local directory, four submitted and two drafts. Local Operator
    has not applied: submitting is AD4C's."""
    found = _existing(owner.id, OPEN_FORM, lambda e: _count(e, Application) >= APPLICANTS)
    if found is not None:
        return Made(OPEN_FORM, found, made=False)
    public_id = _make(client, OPEN_FORM)
    base = f"/operator/exercises/{public_id}"
    operator = (settings.fake_auth_name, settings.fake_auth_email)
    _, mentors = _panels(client, public_id, operator, start=0)

    from applydesk import form_store

    cards: list[dict[str, object]] = [
        {"kind": "section", "label": "Your project"},
        _field("Project title", min="1", max="120", required=True),
        _field("Summary", help="What the project does and who it is for.", max="2000"),
        _field(
            "Area",
            "list",
            options="Arts, Community, Environment, Wellbeing",
            required=True,
        ),
        _field("Weeks it will run", "integer", min="1", max="12", step="1"),
        _field("Mentor", "people", help="A mentor from the panel.", min="1", max="1", pool=mentors),
    ]
    form: dict[str, object] = {
        "revision": form_store.revision(public_id),
        "title": "Apply for a community project grant",
        "description": "Tell us about the project you would run in the residence.",
        "cards": cards,
    }
    _ok(client.post(f"{base}/form", json=form), "Form's Save")

    zone = ZoneInfo(sample_data.DEFAULT_TIMEZONE)
    now = datetime.now(zone).replace(second=0, microsecond=0)
    process: dict[str, object] = {
        "revision": _revision(client.get(f"{base}/process").text),
        "who_may_apply": "open",
        "stages": [
            {
                "name": "Applications",
                "from": _when(now - OPENED),
                "to": _when(now + OPEN_FOR),
                "shown": True,
                "published": True,
                "form": {
                    "from": _when(now - OPENED),
                    "to": _when(now + OPEN_FOR),
                    "receipt": True,
                    "reminder": False,
                },
                "gates": [],
                "outcome": None,
            }
        ],
    }
    _ok(client.post(f"{base}/process", json=process), "Process's Save")
    moved = _ok(
        client.post(f"{base}/form/move", data={"to": "open"}, follow_redirects=False),
        "Opening the form",
    )
    # The route names the move it made, or the refusal's key (cold read).
    if not moved.headers.get("location", "").endswith("form_said=open"):
        raise LocalSeedRefused(f"Opening the form was refused: {moved.headers['location']}")
    _applications(public_id, owner, settings)
    return Made(OPEN_FORM, public_id, made=True)


def _applications(public_id: str, owner: Person, settings: IdentitySettings) -> int:
    """Six applications: the second fake account's first, submitted, so
    switching to it shows one; then five more, two of them drafts."""
    alternate = settings.fake_auth_alt_email.strip().lower()
    head = [(settings.fake_auth_alt_name, alternate)] if alternate else []
    chosen = head + _people(10, APPLICANTS - len(head), but=alternate)
    titles = (
        "Herb garden on the roof",
        "Late-night study café",
        "Mural for the dining hall",
        "Weekend cycling club",
        "Language exchange evenings",
        "Mindfulness mornings",
    )
    states = ("Submitted", "Submitted", "Submitted", "Submitted", "Draft", "Draft")
    today = datetime.now(ZoneInfo(sample_data.DEFAULT_TIMEZONE)).date()
    rows = tuple(
        sample_data.Application(
            public_id=ids.generate_public_id(),
            exercise_id=public_id,
            applicant=name,
            email=email,
            title=titles[i],
            state=states[i],
            submitted=f"{(today - timedelta(days=6 - i)).day} "
            f"{(today - timedelta(days=6 - i)):%b %Y}",
            dossier_id="",
        )
        for i, (name, email) in enumerate(chosen)
    )
    session = db.new_session()
    try:
        exercise = session.scalars(select(Exercise).where(Exercise.public_id == public_id)).one()
        actor = session.get(Person, owner.id)
        added = applications.record_samples(session, exercise, rows, actor)
        # The second account's application is its own person's (Codex on
        # #4279): resolving it as a sign-in does binds the pending person
        # just recorded, or finds the one already bound if it has signed in
        # before, and the application moves to that person.
        signed = alternate_identity(settings)
        if signed is not None and alternate and rows:
            person = people.resolve(session, signed)
            mine = session.scalars(
                select(Application).where(Application.public_id == rows[0].public_id)
            ).one()
            if person is not None and mine.person_id != person.id:
                mine.person_id = person.id
        session.commit()
        return added
    finally:
        session.close()


def create_dossiers(client: TestClient, owner: Person, settings: IdentitySettings) -> Made:
    """Scenario 2: a *Create dossiers* stage alone, published, two dossiers
    a person; five people, Local Operator among them, each holding two
    titled dossiers, ten in all, so the Dossiers page is populated; two
    panels. The author adds the Form."""
    found = _existing(owner.id, CREATE_DOSSIERS, lambda e: _count(e, Candidate) >= 10)
    if found is not None:
        return Made(CREATE_DOSSIERS, found, made=False)
    public_id = _make(client, CREATE_DOSSIERS)
    base = f"/operator/exercises/{public_id}"
    operator = (settings.fake_auth_name, settings.fake_auth_email)
    _panels(client, public_id, operator, start=20)
    process: dict[str, object] = {
        "revision": _revision(client.get(f"{base}/process").text),
        "per_person": 2,
        "stages": [
            {
                "name": "Nominations",
                "from": "",
                "to": "",
                "shown": True,
                "published": True,
                "form": None,
                "candidates": True,
                "gates": [],
                "outcome": None,
            }
        ],
    }
    _ok(client.post(f"{base}/process", json=process), "Process's Save")
    holders = [operator, *_people(30, 4, but=settings.fake_auth_alt_email)]
    # Written by the csv module, so a configured name with a comma stays
    # one field (Codex on #4280).
    import csv
    import io

    out = io.StringIO()
    rows = csv.writer(out, lineterminator="\n")
    rows.writerow(["Name", "Email", "Title"])
    for name, email in holders:
        for term in ("Semester 1", "Semester 2"):
            rows.writerow([name, email, f"Peer mentor · {term}"])
    sent = {"action": "csv", "text": out.getvalue()}
    reply = _ok(client.post(f"{base}/candidates", json=sent), "Create dossiers' CSV")
    import json

    bad: list[object] = list(json.loads(reply.text).get("bad") or ())
    if bad:
        raise LocalSeedRefused(f"Create dossiers' CSV refused rows: {bad}")
    return Made(CREATE_DOSSIERS, public_id, made=True)


#: Each scenario, in the order the seed builds them.
SCENARIOS: Sequence[Callable[[TestClient, Person, IdentitySettings], Made]] = (
    open_form,
    create_dossiers,
)


def seed_local() -> tuple[Made, ...]:
    """Build every scenario not already there. Refused unless
    `APP_ENV=local` with fake auth on. Always the host's identity settings:
    the pages' requests resolve their identity from those, so the Owner the
    seed binds and the one its requests make are one person (Codex on
    #4279)."""
    cfg = identity_settings
    if not is_local(cfg) or not cfg.allow_fake_auth:
        raise LocalSeedRefused(
            "the scenarios need APP_ENV=local and ALLOW_FAKE_AUTH=true (ruling 74)"
        )
    found = owner(cfg)
    client = _client()
    return tuple(scenario(client, found, cfg) for scenario in SCENARIOS)
