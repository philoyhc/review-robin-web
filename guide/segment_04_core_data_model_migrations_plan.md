# Segment 4 Plan — Core Data Model and Migrations

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 4 of the low-intensity workplan  
**Purpose:** Establish the relational database foundation for Review Robin Web

> **See also:** `guide/segment_04A.md` — agreed implementation plan with
> decisions made (model class names, migrations-in-tests strategy, type
> portability rules, deferrals into later segments). Read this parent plan
> for scope and intent; read 04A for the implementation contract.

---

## 1. Segment goal

Segment 4 creates the database backbone of the application.

By the end of this segment, the repository should contain SQLAlchemy 2.x models, Alembic migrations, database session handling, and tests proving that the main Review Robin entities can be created and related correctly.

This segment is not about building the UI. It is about defining the shape of the data with enough clarity that later segments can build confidently on it.

---

## 2. Success criteria

Segment 4 is complete when:

1. SQLAlchemy 2.x is installed and configured.
2. Alembic is installed and initialized.
3. A local development database connection pattern exists.
4. Initial database models exist for the core domain.
5. An initial migration can be generated and applied.
6. Tests can create sessions, reviewers, reviewees, instruments, assignments, responses, invitations, and audit events.
7. The schema supports the first end-to-end milestone.
8. Documentation explains how to run migrations locally.

---

## 3. What this segment deliberately does not do

Do not include:

- operator UI;
- CSV import UI;
- reviewer grid;
- email sending;
- Azure PostgreSQL production setup beyond connection preparation;
- full role-management screens;
- RuleBased engine;
- export generation;
- retention jobs.

Segment 4 creates the data foundation only.

---

## 4. Recommended branch strategy

```bash
git checkout -b segment-4-core-data-model
```

Suggested PR title:

```text
Segment 4: Add core database models and migrations
```

---

## 5. Dependencies to add

Add:

```toml
"sqlalchemy>=2.0",
"alembic>=1.13",
"psycopg[binary]>=3.2",
```

Development/test additions may include:

```toml
"pytest>=8.2",
"httpx>=0.27",
```

SQLite may be used for early local tests, but PostgreSQL compatibility should remain in mind from the beginning.

---

## 6. Proposed folders to add

```text
app/
  db/
    __init__.py
    base.py
    session.py
    models/
      __init__.py
      user.py
      session.py
      reviewer.py
      reviewee.py
      instrument.py
      assignment.py
      response.py
      invitation.py
      audit.py
      export.py
      retention.py

alembic/
  env.py
  script.py.mako
  versions/

tests/
  db/
    test_models.py
```

---

## 7. Initial model set

### 7.1 User

Represents a person known to the app.

Fields:

- id;
- email;
- display name;
- external principal id, if available;
- created at;
- updated at.

Do not overbuild roles yet. Keep role relationships separate.

### 7.2 Session

Represents a review cycle.

Fields:

- id;
- session name;
- session code;
- description;
- status;
- deadline;
- created by;
- created at;
- updated at.

### 7.3 SessionOperator

Links users to sessions they can operate.

Fields:

- id;
- session id;
- user id;
- role within session;
- created at.

### 7.4 Reviewer

Session-scoped reviewer record.

Fields:

- id;
- session id;
- reviewer name;
- reviewer email;
- optional status fields;
- created at;
- updated at.

### 7.5 Reviewee

Session-scoped reviewee record.

Fields:

- id;
- session id;
- reviewee name;
- reviewee email or identifier;
- optional profile link;
- optional status fields;
- created at;
- updated at.

### 7.6 Instrument

A review form/question set within a session.

Fields:

- id;
- session id;
- name;
- description;
- order;
- created at;
- updated at.

### 7.7 InstrumentDisplayField

Defines fields shown to reviewers about each reviewee or assignment.

Fields:

- id;
- instrument id;
- label;
- source type;
- source field;
- order;
- visible flag.

### 7.8 InstrumentResponseField

Defines response columns.

Fields:

- id;
- instrument id;
- field key;
- label;
- response type;
- required flag;
- order;
- validation configuration.

### 7.9 Assignment

One reviewer-reviewee-instrument assignment.

Fields:

- id;
- session id;
- reviewer id;
- reviewee id;
- instrument id;
- include flag;
- assignment context fields;
- created by mode;
- created at.

### 7.10 Response

One response value for one assignment and response field.

Fields:

- id;
- assignment id;
- response field id;
- value;
- saved at;
- submitted at, nullable;
- version number, optional but recommended.

### 7.11 Invitation

Tracks reviewer access/invitation state.

Fields:

- id;
- session id;
- reviewer id;
- token hash or access key reference;
- invitation status;
- sent at;
- opened at;
- last reminder at;
- created at.

### 7.12 AuditEvent

Append-oriented record of important actions.

Fields:

- id;
- session id, nullable;
- actor user id, nullable;
- event type;
- severity;
- summary;
- detail JSON;
- correlation id;
- created at.

---

## 8. Modeling principles

1. Keep the schema normalized enough to support long-format export.
2. Do not store reviewer response data only as large JSON blobs.
3. Add indexes for common lookups.
4. Use foreign keys for core relationships.
5. Keep audit events append-oriented.
6. Keep session-scoped data clearly tied to a session.
7. Do not implement complex permissions until Segment 5 and beyond.

---

## 9. Tests to add

Minimum tests:

1. Can create a user.
2. Can create a session owned by a user.
3. Can add reviewer and reviewee to a session.
4. Can add an instrument with response fields.
5. Can create an assignment linking reviewer, reviewee, and instrument.
6. Can create a response for an assignment and response field.
7. Can create an invitation for a reviewer.
8. Can write an audit event.

These are not business tests yet. They prove the schema can support the business tests later.

---

## 10. AI-assisted prompts

### Initial schema prompt

```text
Implement Segment 4 core data model.

Use SQLAlchemy 2.x declarative style with Mapped[] and mapped_column.
Add models for:
- User
- Session
- SessionOperator
- Reviewer
- Reviewee
- Instrument
- InstrumentDisplayField
- InstrumentResponseField
- Assignment
- Response
- Invitation
- AuditEvent

Also add Alembic setup and basic tests proving the relationships work.

Do not add UI, imports, authentication roles, or Review Robin features yet.
```

### Schema review prompt

```text
Review this SQLAlchemy schema for Review Robin Web.

Check:
- SQLAlchemy 2.x style consistency
- missing foreign keys
- missing indexes for common lookup paths
- whether long-format export is possible
- whether reviewer access can later be enforced
- whether response values are too loosely modeled
```

---

## 11. Suggested GitHub issues

### Issue 1 — Add SQLAlchemy and database session setup

Acceptance criteria:

- SQLAlchemy configured;
- database session dependency exists;
- tests can use a test database.

### Issue 2 — Add core models

Acceptance criteria:

- models defined;
- relationships work;
- schema supports session/reviewer/reviewee/instrument/assignment/response.

### Issue 3 — Add Alembic initial migration

Acceptance criteria:

- migration generated;
- migration applies cleanly;
- migration committed.

### Issue 4 — Add model tests

Acceptance criteria:

- tests create the core object graph;
- tests pass in CI.

---

## 12. Common mistakes to avoid

### 12.1 Mixing SQLAlchemy styles

Use SQLAlchemy 2.x style consistently.

### 12.2 Overusing JSON

JSON is useful for optional details, but core response data should be queryable.

### 12.3 Building roles too early

Define enough to support later permissions, but do not build full role-management UI.

### 12.4 Ignoring exports

Check that the schema can produce long and wide exports later.

---

## 13. Completion note template

```markdown
## Segment 4 completion note

Completed:
- SQLAlchemy setup
- Alembic setup
- initial models
- initial migration
- model relationship tests

Verified:
- migration applies
- tests pass
- core object graph can be created

Deferred:
- UI
- imports
- authorization screens
- reviewer surface
- email
- exports

Notes:
- [database choice for local dev]
- [migration filename]
```

---

## 14. Final checkpoint

- [ ] SQLAlchemy configured.
- [ ] Alembic configured.
- [ ] Initial migration committed.
- [ ] Core models exist.
- [ ] Model tests pass.
- [ ] Database setup is documented.
- [ ] No UI or business workflow was added prematurely.

Next segment: **Operator session setup MVP**.

