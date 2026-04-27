# Segment 4A — Core Data Model and Migrations (Agreed Plan)

**Project:** Review Robin Web
**Repository:** <https://github.com/philoyhc/review-robin-web>
**Parent plan:** `guide/segment_04_core_data_model_migrations_plan.md`
**Purpose:** Lock in the implementation choices for Segment 4 with decisions
made, so the next session can implement without re-litigating the design.

This document is a **delta** on the parent plan. The parent plan still
governs scope, success criteria, and out-of-scope items.

---

## 1. Scope (unchanged from parent plan)

Schema only. SQLAlchemy 2.x models, Alembic migrations, tests proving the
core entity graph can be created. No UI, no DB-backed routes, no business
logic, no Azure PostgreSQL provisioning.

---

## 2. Branch

```text
claude/segment-4-core-data-model
```

Off `main`. Single PR.

Suggested PR title: `Segment 4: Add core database models and migrations`.

---

## 3. Dependencies

Add to **both** `pyproject.toml` and `requirements.txt`:

- `sqlalchemy>=2.0`
- `alembic>=1.13`
- `psycopg[binary]>=3.2`

Rationale: keeping the two files in sync now avoids deployment surprises
later, even though the running app won't open a DB connection at import time
in this segment.

---

## 4. File and folder layout

```text
app/db/
  __init__.py
  base.py              # DeclarativeBase
  session.py           # engine, sessionmaker, get_db() FastAPI dependency
  models/
    __init__.py        # imports every model so Alembic autogenerate sees them
    user.py
    review_session.py
    session_operator.py
    reviewer.py
    reviewee.py
    instrument.py
    instrument_field.py    # InstrumentDisplayField + InstrumentResponseField
    assignment.py
    response.py
    invitation.py
    audit_event.py

alembic.ini
alembic/
  env.py
  script.py.mako
  versions/
    <hash>_initial_schema.py

tests/db/
  __init__.py
  conftest.py          # in-memory SQLite engine + applied Alembic migrations + session fixture
  test_models.py       # 8 tests per parent plan §9

docs/
  database.md          # local dev setup, how to run migrations, SQLite vs Postgres notes
```

---

## 5. Decisions

### 5.1 "Session" naming overload

The parent plan calls the review-cycle entity `Session`. SQLAlchemy's
`Session` is the DB-session class — overloading the name causes confusion in
imports and type hints.

**Decision:** the Python class is `ReviewSession`. The database table name
is `sessions` (so the parent plan's prose still reads correctly when
referring to "session" the domain entity). All other model class names
follow the parent plan exactly.

### 5.2 Migrations in tests

**Decision:** the test fixture runs `alembic upgrade head` against an
in-memory SQLite engine, not `Base.metadata.create_all()`.

Why: exercises the migration on every test run, catching drift between
models and migrations early. Cost: ~50ms per test session. Acceptable.

### 5.3 `requirements.txt` sync

**Decision:** add the three new dependencies to `requirements.txt` now, even
though the deployed app doesn't import them at startup yet. Keeps the two
dependency files symmetric and avoids a "but it works locally" surprise on
the deploy after Segment 5.

### 5.4 Local development DB

**Decision:** SQLite is the only local DB introduced in this segment.
Default `database_url` is `sqlite:///./review_robin_web.db`.

Local Postgres (Docker, or Azure-side) is deferred to **Segment 5**, where
the first feature actually persists data and we'll want to test against the
deployment target.

### 5.5 `get_db()` FastAPI dependency

**Decision:** add `app/db/session.py::get_db()` now, even though no route in
this segment uses it. Three lines, lets Segment 5 wire routes immediately.

### 5.6 CI

**Decision:** existing `ci.yml` is unchanged. Tests use SQLite, so no
Postgres-against-Docker job is needed in this segment. A Postgres CI job is
deferred to **Segment 13** (production hardening), where it joins the
broader hardening pass.

---

## 6. Type portability rules

To keep one migration that runs on both SQLite (tests) and PostgreSQL
(deployed), all column types must be cross-dialect:

| Need               | Use in Segment 4                         | Deferred to             |
|--------------------|------------------------------------------|-------------------------|
| JSON blob          | `sqlalchemy.JSON`                        | `JSONB` migration in S13|
| UUID column        | `String(36)` (or autoincrement integer)  | native `UUID` in S13    |
| Case-insensitive text | plain `String` + lowercased on write  | `CITEXT` if ever needed |
| Array / set       | normalized child table                    | Postgres `ARRAY` only if justified |
| Datetime          | `DateTime(timezone=True)` with `func.now()` default | n/a       |
| Enum              | `String` + Python `Enum` validation in app code | DB-level enum optional in S13 |

No `from sqlalchemy.dialects.postgresql import ...` in Segment 4.

---

## 7. Models — quick field reference

The parent plan §7 lists all fields. Segment 4A adds these implementation
notes only:

- All tables get `id` (integer primary key, autoincrement) and
  `created_at`/`updated_at` (timezone-aware) unless the parent plan says
  otherwise.
- Foreign keys use `ON DELETE` defaults; cascade behavior is **not**
  configured in Segment 4 — picked per relationship in Segment 5+ when use
  cases clarify.
- Indexes: at minimum, every foreign key column gets an index. Email
  columns on `User`, `Reviewer`, `Reviewee` are indexed. `Session.code` is
  unique-indexed.
- `AuditEvent.detail` is `JSON` (cross-dialect). `severity` and
  `event_type` are `String` with enum validation in Python.

---

## 8. Tests (per parent plan §9)

`tests/db/test_models.py`, eight tests minimum:

1. Create a `User`.
2. Create a `ReviewSession` owned by a user.
3. Add a `Reviewer` and a `Reviewee` to a session.
4. Add an `Instrument` with display fields and response fields.
5. Create an `Assignment` linking reviewer / reviewee / instrument.
6. Create a `Response` for an assignment + response field.
7. Create an `Invitation` for a reviewer.
8. Write an `AuditEvent`.

The fixture in `tests/db/conftest.py`:

```python
@pytest.fixture(scope="session")
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    # run alembic upgrade head against this engine
    ...
    yield engine

@pytest.fixture
def db(engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
```

Every test runs in a transaction that rolls back, so tests don't pollute
each other.

---

## 9. Documentation

`docs/database.md` covers:

- How to run migrations locally.
- How to generate a new migration (and that autogenerate output must always
  be reviewed by a human).
- SQLite vs PostgreSQL — what works on both, what doesn't.
- Where the `database_url` setting comes from.
- Pointer that Azure Postgres provisioning is in Segment 5.

`README.md` gets a one-paragraph addition under "Local development" telling
contributors to run `alembic upgrade head` after `pip install`.

`AGENTS.md` gets a one-line addition under conventions: "Use SQLAlchemy 2.x
declarative style with `Mapped[]` and `mapped_column`."

---

## 10. Out of scope (per parent plan §3 + new deferrals)

Carried over from parent plan:

- Operator UI, CSV import, reviewer grid, email, full role-management UI,
  RuleBased engine, exports, retention jobs.

Newly deferred to specific later segments:

| Item                                          | Deferred to |
|-----------------------------------------------|-------------|
| Azure PostgreSQL Flexible Server provisioning | Segment 5   |
| Local Postgres development setup (Docker etc.)| Segment 5   |
| `JSONB`, native `UUID`, dialect-specific types | Segment 13 |
| Postgres-against-Docker CI job                | Segment 13  |

---

## 11. Verification checklist

- [ ] `pip install -e .[dev]` succeeds.
- [ ] `alembic upgrade head` against local SQLite succeeds.
- [ ] `alembic downgrade -1` then `alembic upgrade head` round-trips cleanly.
- [ ] `pytest` green locally (existing 16 tests + 8 new = 24 minimum).
- [ ] CI passes on PR.
- [ ] No SQLAlchemy v1 patterns (`Column(...)` outside `mapped_column`,
  `db.Model`, etc.).
- [ ] No Postgres-specific imports in `app/db/models/`.
- [ ] `docs/database.md` exists and explains the local workflow.

---

## 12. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Migration runs on SQLite but breaks on Postgres in S5 | Type portability rules in §6; first deploy of S5 will smoke-test the migration on real Postgres. |
| Schema needs major changes once S5 wires real routes | Accept it. Generate a follow-up migration; the schema is meant to be a living thing in early segments. |
| In-memory SQLite tests hide concurrency or locking bugs | Out of scope for S4 — concurrency hardening is part of S13. |
| `ReviewSession` rename creates inconsistency with parent plan prose | Parent plan still uses "session" for the domain entity, which matches the table name. Class name is documented as `ReviewSession` here and in `docs/database.md`. |

---

## 13. Done when

- All 12 models exist under `app/db/models/`.
- One Alembic migration in `alembic/versions/` creates all 12 tables.
- 8 model tests pass.
- `docs/database.md` exists.
- PR merged.

Next segment: **Segment 5 — Operator session setup MVP** (which provisions
Azure Postgres and wires the first DB-backed routes).
