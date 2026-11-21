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

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import db, operators, people, sample_data
from applydesk.models import Exercise
from cordware.identity import Identity, is_local
from cordware.settings import IdentitySettings, identity_settings

#: The seed acts as the platform: the super-admin with no person row.
_PLATFORM = operators.Actor(None, is_super_admin=True)


class SeedRefused(RuntimeError):
    """The seed was asked to run outside a local environment."""


@dataclass(frozen=True)
class SeedResult:
    owner_id: int
    exercises_added: int
    grants_added: int


def _fake_identity(settings: IdentitySettings) -> Identity:
    """Cordware's fake identity, as its host builds it (`cordware/identity.py`)."""
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


def seed(
    session: Session,
    owner_email: str | None = None,
    settings: IdentitySettings | None = None,
) -> SeedResult:
    """Give each sample exercise its row and its Owner; commit. Refused
    outside `APP_ENV=local`. Everything goes through `people` and
    `operators`, so seeded rows are matched and audited as any others
    (cold read): the person is bound as a sign-in would bind them, or kept
    pending by address; admitted by no one (the seed acts as the
    platform); each exercise made with them its Owner."""
    settings = settings or identity_settings
    if not is_local(settings):
        raise SeedRefused("the seed runs only with APP_ENV=local (ruling 74)")
    if owner_email:
        owner = people.pending(session, owner_email, actor=None)
    else:
        found = people.resolve(session, _fake_identity(settings))
        if found is None:
            raise SeedRefused("the fake identity has no tenant or principal ID to bind")
        owner = found
    if not operators.may_operate(owner):
        operators.admit(session, _PLATFORM, owner)
    exercises_added = grants_added = 0
    for sample in sample_data.exercises():
        exercise = session.scalar(select(Exercise).where(Exercise.public_id == sample.public_id))
        if exercise is None:
            operators.create_exercise(session, operators.Actor(owner), sample.public_id)
            exercises_added += 1
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
