"""Fast SQLite schema build for the test suite.

The migration chain is replayed only on the ``ci-postgres`` job; the
SQLite test path builds its schema directly from the ORM metadata
(``Base.metadata.create_all``) and replays data-only migrations
separately. Shared by the session-scoped ``engine`` fixture
(``tests/conftest.py``) and the per-test ``committed_engine`` fixture
(``tests/integration/conftest.py``).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Engine
from sqlalchemy.orm import Session


def _install_seed_rule_sets(eng: Engine) -> None:
    """Install the workspace-shipped seed RuleSet library.

    The ``create_all`` path skips the migration chain, so the data-only
    seed-install migration (Segment 13A PR 3) does not run. Replay its
    net effect here from the same ``SEEDED_RULE_SETS`` source of truth,
    using the current ORM models. The Postgres CI job still exercises
    the real migration, so ``test_rule_set_seeds_install.py`` keeps
    guarding migration drift there.
    """
    from app.db.models import RuleSet, RuleSetRevision
    from app.services.rules.seeds import SEEDED_RULE_SETS

    now = datetime.now(timezone.utc)
    with Session(bind=eng, expire_on_commit=False) as session:
        for seed in SEEDED_RULE_SETS:
            rule_set = RuleSet(
                name=seed.name,
                description=seed.description,
                scope="seed",
                owner_user_id=None,
                is_seed=True,
            )
            session.add(rule_set)
            session.flush()
            revision = RuleSetRevision(
                rule_set_id=rule_set.id,
                revision_no=1,
                combinator=seed.combinator.value,
                exclude_self_reviews=seed.options.excludeSelfReviews,
                seed=seed.options.seed,
                rules_json=[rule.model_dump(mode="json") for rule in seed.rules],
                created_at=now,
                created_by_user_id=None,
            )
            session.add(revision)
            session.flush()
            rule_set.current_revision_id = revision.id
        session.commit()


def build_sqlite_schema(eng: Engine) -> None:
    """Build the full schema on a SQLite engine directly from ORM metadata.

    Importing ``app.db.models`` registers every mapped class on
    ``Base.metadata``; ``create_all`` then builds the schema in one pass,
    skipping the migration replay. Data-only migrations are replayed
    separately (see ``_install_seed_rule_sets``).
    """
    from app.db.base import Base
    import app.db.models  # noqa: F401  -- registers all tables on Base.metadata

    Base.metadata.create_all(eng)
    _install_seed_rule_sets(eng)
