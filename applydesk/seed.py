"""The localhost seed (segment AD2A; ruling 74): `python -m applydesk.seed`.

On a fresh checkout, after `alembic -c applydesk/alembic.ini upgrade head`,
it gives every sample exercise its `exercise` row and makes one person
its Owner, allowlisted to operate (ruling 75), so every page works on
localhost. That person is Cordware's fake identity (`FAKE_AUTH_*` in
`.env`), bound by its tenant and principal ID, or the email `--owner`
names, kept pending until it signs in.

It is idempotent: a second run changes nothing. It refuses to run unless
`APP_ENV=local`, since the samples are seeds for localhost and tests,
never production (ruling 74). Tests seed through `seed()`.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import db, sample_data
from applydesk.models import Exercise, ExerciseOperator, Person
from cordware.identity import is_local
from cordware.settings import IdentitySettings, identity_settings


class SeedRefused(RuntimeError):
    """The seed was asked to run outside a local environment."""


@dataclass(frozen=True)
class SeedResult:
    owner_id: int
    exercises_added: int
    grants_added: int


def _fake_owner(session: Session, settings: IdentitySettings) -> Person:
    tenant = settings.fake_auth_tenant_id.strip() or None
    object_id = settings.fake_auth_principal_id.strip() or None
    person = session.scalar(
        select(Person).where(Person.tenant_id == tenant, Person.object_id == object_id)
    )
    if person is None:
        email = settings.fake_auth_email
        person = Person(
            tenant_id=tenant,
            object_id=object_id,
            email=email,
            email_key=email.casefold(),
            upn=settings.fake_auth_upn.strip() or email,
            display_name=settings.fake_auth_name,
            bound_at=datetime.now(UTC),
        )
        session.add(person)
    return person


def _pending_owner(session: Session, email: str) -> Person:
    key = email.strip().casefold()
    person = session.scalar(select(Person).where(Person.email_key == key))
    if person is None:
        person = Person(email=email.strip(), email_key=key)
        session.add(person)
    return person


def seed(
    session: Session,
    owner_email: str | None = None,
    settings: IdentitySettings | None = None,
) -> SeedResult:
    """Give each sample exercise its row and its Owner; commit. Refused
    outside `APP_ENV=local`."""
    settings = settings or identity_settings
    if not is_local(settings):
        raise SeedRefused("the seed runs only with APP_ENV=local (ruling 74)")
    owner = _pending_owner(session, owner_email) if owner_email else _fake_owner(session, settings)
    if not owner.may_operate:
        owner.may_operate = True
        owner.admitted_at = datetime.now(UTC)
        owner.revoked_at = None
    session.flush()
    exercises_added = grants_added = 0
    for sample in sample_data.exercises():
        exercise = session.scalar(select(Exercise).where(Exercise.public_id == sample.public_id))
        if exercise is None:
            exercise = Exercise(public_id=sample.public_id)
            session.add(exercise)
            session.flush()
            exercises_added += 1
        has_owner = session.scalar(
            select(ExerciseOperator.id).where(
                ExerciseOperator.exercise_id == exercise.id,
                ExerciseOperator.is_owner.is_(True),
                ExerciseOperator.removed_at.is_(None),
            )
        )
        if has_owner is None:
            session.add(
                ExerciseOperator(exercise_id=exercise.id, person_id=owner.id, is_owner=True)
            )
            grants_added += 1
    session.commit()
    return SeedResult(owner_id=owner.id, exercises_added=exercises_added, grants_added=grants_added)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m applydesk.seed",
        description="Load Apply Desk's sample exercises into the local database.",
    )
    parser.add_argument(
        "--owner",
        metavar="EMAIL",
        help="make this address the Owner (pending until it signs in) instead of the fake identity",
    )
    args = parser.parse_args(argv)
    session = db.new_session()
    try:
        result = seed(session, owner_email=args.owner)
    except SeedRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    finally:
        session.close()
    print(
        f"seeded: {result.exercises_added} exercises and {result.grants_added} "
        f"Owner grants added (owner person {result.owner_id})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
