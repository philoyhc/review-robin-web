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

Two flags (segment AD2G): `--reset` empties Apply Desk's local database
first (its Alembic history down to base and up to head, Apply Desk's own
tables only), and `--blank N` adds N blank drafts, ordinary exercises
Owned by the same person, as *New exercise* makes them.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import make_url, select, text
from sqlalchemy.orm import Session

from applydesk import db, exercises, operators, people, sample_data
from applydesk.models import Exercise, Person
from cordware.identity import Identity, is_local
from cordware.settings import IdentitySettings, identity_settings

#: The seed acts as the platform: the super-admin with no person row.
_PLATFORM = operators.Actor(None, is_super_admin=True, platform=True)


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
    *,
    record_settings: bool = True,
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
    for sample in sample_data.EXERCISES:  # the samples only, never an ordinary row (AD2G)
        exercise = session.scalar(select(Exercise).where(Exercise.public_id == sample.public_id))
        if exercise is None:
            exercise = operators.create_exercise(session, operators.Actor(owner), sample.public_id)
            exercises_added += 1
            grants_added += 1
        # Its settings too (segment AD2B), once: a later save is kept.
        if record_settings:
            exercises.record_sample(session, exercise, sample, owner)
    session.commit()
    return SeedResult(owner_id=owner.id, exercises_added=exercises_added, grants_added=grants_added)


def reset(settings: IdentitySettings | None = None) -> None:
    """Empty Apply Desk's database: its own tables (its models' and its
    Alembic version table) dropped, then its history run up to head, so
    no other application's tables are touched. Not a downgrade, which
    would have to satisfy each old constraint against live data (Codex on
    #4188: two Owners of one exercise stop `ad2m2`'s downgrade). Refused
    outside `APP_ENV=local`, as the seed is."""
    from alembic import command
    from alembic.config import Config

    if not is_local(settings or identity_settings):
        raise SeedRefused("--reset runs only with APP_ENV=local (ruling 74)")
    # It destroys data, so the database must be local too, not only the
    # environment: SQLite, or a server on this machine (cold read).
    url = make_url(db.ApplyDeskSettings().database_url)
    if not (url.get_backend_name() == "sqlite" or url.host in ("localhost", "127.0.0.1", "::1")):
        raise SeedRefused("--reset empties only a SQLite file or a database on localhost")
    from applydesk import models

    engine = db.engine()
    engine.dispose()  # no pooled connection holds a table it drops
    models.Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text(f'DROP TABLE IF EXISTS "{db.VERSION_TABLE}"'))
    engine.dispose()
    config = Config(str(Path(__file__).resolve().parent / "alembic.ini"))
    command.upgrade(config, "head")


def blank(session: Session, owner_id: int, count: int) -> list[str]:
    """Add `count` blank drafts Owned by the person `owner_id`, named
    *Blank exercise 1*… after the ones already there; commit. Their
    public IDs, newest last. *New exercise*'s cap holds."""
    owner = session.get(Person, owner_id)
    if owner is None:
        raise SeedRefused("the seed's Owner is not on record")
    actor = operators.Actor(owner)
    taken = {
        name
        for name in session.scalars(select(Exercise.name).where(Exercise.created_by_id == owner_id))
        if name
    }
    made: list[str] = []
    n = 0
    while len(made) < count:
        n += 1
        name = f"Blank exercise {n}"
        if name in taken:
            continue
        try:
            made.append(exercises.make(session, actor, name).public_id)
        except exercises.Refused as why:
            session.rollback()
            raise SeedRefused(str(why)) from None
    session.commit()
    return made


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
    parser.add_argument(
        "--reset",
        action="store_true",
        help="empty Apply Desk's local database first (down to base, up to head)",
    )
    parser.add_argument(
        "--blank",
        metavar="N",
        type=int,
        default=0,
        help=f"add N blank drafts Owned by the same person (at most {exercises.MOST_MADE})",
    )
    args = parser.parse_args(argv)
    if not 0 <= args.blank <= exercises.MOST_MADE:
        parser.error(f"--blank takes 0 to {exercises.MOST_MADE}")
    try:
        if args.reset:
            reset()
        session = db.new_session()
        try:
            result = seed(session, owner_email=args.owner)
            made = blank(session, result.owner_id, args.blank) if args.blank else []
        finally:
            session.close()
    except SeedRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    print(
        ("reset, then " if args.reset else "")
        + f"seeded: {result.exercises_added} exercises and {result.grants_added} "
        f"Owner grants added (owner person {result.owner_id})"
        + (f"; {len(made)} blank drafts added" if made else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
