# Segment AD2A — Apply Desk: the database, people, operators and audit

**Opened:** 2026-11-21 · **Series:** `applydesk/guide/ad2_series.md` (the first of AD2) · **Rulings:** 72–74 · **Related:** `applydesk/guide/ad2_deferred_findings.md` (AD-43, AD-53), `applydesk/spec/architecture.md`, `applydesk/spec/applications.md`

## Opportunity

Apply Desk has no database. Every page reads `applydesk/sample_data.py` or the per-browser scratch store, so nothing an operator does outlives the tab. Who may see what is a placeholder: `applydesk/gate.py` lets anyone through on a local run and only the platform super-admin when deployed. Every person is an email string (AD-43). Exercise IDs are unique only by luck (AD-53). Nothing is audited. Every later AD2 segment needs a database, a person to point at, a check of who operates an exercise, and an audit trail.

## Decision

1. **Apply Desk's own database**, `applydesk`, laid out as Utilities' (`utilityapps/db.py`, `utilityapps/alembic/`):
   - `applydesk/db.py`: `APPLYDESK_DATABASE_URL`, defaulting to `sqlite:///./applydesk.db`; an engine made on first use, so `/health` opens none; a request-scoped session.
   - `applydesk/models.py`: the models, on Apply Desk's own `Base`.
   - `applydesk/alembic.ini` and `applydesk/alembic/`, version table `applydesk_alembic_version`, `include_name` limited to Apply Desk's tables.
   - `ci-postgres.yml` round-trips the history (`upgrade head`, `downgrade base`, `upgrade head`, `check`), as Utilities'.
2. **Four tables:**
   - `person`: tenant ID, object ID (both null while pending), and snapshots of email, UPN and display name; `bound_at`, `created_at`. Unique on (tenant, object ID) where bound. Pending rows are found by casefolded email.
   - `exercise`: for now only its key, its `public_id` (unique, AD-53) and `created_at`. AD2B adds its settings.
   - `exercise_operator`: (exercise, person) unique, `is_owner`, `added_by`, `added_at`, `removed_at`. At most one current Owner per exercise.
   - `audit_event`: RRW's envelope (event type, actor person, exercise, a payload of changes, snapshot, counts or set changes, and the reason, refs and context slots), checked against an `EVENT_SCHEMAS` allowlist, strict in tests. This is Apply Desk's own copy (`applydesk/audit.py`); packages do not import RRW.
3. **Binding** (`applydesk/people.py`), as Residential's (`residentialapps/docs/residentialapps_email_identity_matching.md`). A signed-in identity is looked up by (tenant, object ID). Failing that, a pending person whose casefolded email matches the identity's UPN or mail is bound and audited. Failing that, a new bound person is made. Once bound, email is a snapshot only. Locally, Cordware's fake identity has a tenant and principal ID (`local-tenant`, `local-dev`), so binding is the same code.
4. **Operators** (`applydesk/operators.py`, ruling 73):
   - An exercise's Owner is one of its operators. Other operators do everything on the exercise; only the Owner adds and removes operators and hands ownership over.
   - The Owner cannot be removed, only replaced by a handover to a current operator.
   - Whoever makes an exercise is its Owner. The platform super-admin reaches every exercise and acts as an Owner.
   - Adding an operator by email makes a pending person if none matches.
5. **The gate becomes a check**: `placeholders_only` gives way to `require_exercise_operator`, a FastAPI dependency answering 404 to a non-operator, as RRW's per-session check (`app/web/deps.py`). The Operator Lobby lists the exercises the viewer operates. `is_operator` reads "operates any exercise, or is the super-admin". Making a scratch exercise also makes its `exercise` row and its Owner. The sample exercises' rows come from the seed.
6. **The seed**, `python -m applydesk.seed`: idempotent; makes the sample exercises' rows and grants Owner of each to the fake identity's person (or to an email given with `--owner`). Refused unless `APP_ENV=local`. Tests seed through the same function.
7. **An *Operators* card on Home**, beside Details: the operators with the Owner marked, *Add operator* (email), *Remove* and *Make owner* for the Owner, read-only for the rest. It lands scaffold-first.

**Alternative rejected:** tables in RRW's database, with Apply Desk reading RRW's `users` and audit. Strategy v1.0 gives each application its own database, and `applydesk` imports nothing of `app` (`applydesk/spec/architecture.md`, "Import boundaries").

## Semantics

- **The sample data stays the source** of everything but who operates an exercise: AD2A stores grants, people and audit only. `sample_data.py` still answers the rest until AD2B onward.
- **An exercise with no current Owner** cannot exist: making one grants its Owner in the same transaction, and a handover is one transaction. A service refusal names the rule.
- **The Owner adding themself**, or adding a current operator again: refused, *already an operator*. Re-adding a removed operator clears `removed_at` and audits it.
- **A pending person** has no access until bound: the check runs on the signed-in person, and binding happens at sign-in.
- **Two people with one email**, a bound row and a pending one: binding takes the pending row only when no bound row holds that identity; the pending row is never merged into a bound one silently.
- **Deployed with no database URL set**, Apply Desk falls back to its SQLite default. The Cordware import must not ship until the App Setting exists; that ordering is the provisioning PR's to state.

## Judgment calls — decided

- `exercise` lands in AD2A with only its key and ID, so grants have a target; AD2B fills it.
- The audit table copies RRW's envelope rather than inventing a lighter one (ruling 74): the shape is known and its strict check is cheap.
- The Operators card sits on Home, not on a page of its own: it is one short list per exercise.

## Blast radius (measured)

Taken 2026-11-21 at `64f0c5c6e`.
- `placeholders_only` and `is_operator` call sites outside `gate.py`: `grep -rn "placeholders_only\|is_operator" applydesk/*.py | grep -v "^applydesk/gate.py"` → 10.
- Modules reading `sample_data`: `grep -rln "sample_data\." applydesk/*.py` → 13 (109 references). Unchanged in AD2A.
- `applydesk/tests/`: 30 files; the host fixture `applydesk/tests/_host.py` gains the database.
- CI: `.github/workflows/ci-postgres.yml` (the round-trip, as Utilities' at l.111–121); `tools/ci_lanes.py` already lists `applydesk/`.

## PR ladder

1. **The series overview, this plan and rulings 72–74.** Prose only.
2. **The database**: `db.py`, `models.py` with the four tables, the history's first migration, the `ci-postgres.yml` round-trip, the seed command, and the README and local-setup lines. No page changes.
3. **People, operators and audit**: `people.py`, `operators.py`, `audit.py` with `EVENT_SCHEMAS`; unit tests for binding, the Owner rules and strict audit.
4. **The check**: `require_exercise_operator` replaces `placeholders_only`, the lobby lists granted exercises, and a scratch exercise gets its row and Owner; tests that a non-operator gets 404.
5. **The Operators card, scaffold**: static copy and layout on Home, controls inert.
6. **The Operators card, wired**: add, remove and hand over, each audited. The last build rung: the cumulative cold read runs here from rung 2's base.
7. **Cordware**, in the private repository: the `applydesk` database workflow and the App Setting, after Utilities'. The author dispatches.
8. **Close.**

## Definition of done

- On a fresh checkout: `alembic -c applydesk/alembic.ini upgrade head`, `python -m applydesk.seed`, `uvicorn cordware.main:app` reach every Apply Desk page as the fake operator.
- `ci-postgres.yml` round-trips Apply Desk's history.
- A non-operator gets 404 on every operator route, by a test walking them.
- AD-43 and AD-53 struck in `applydesk/guide/ad2_deferred_findings.md` with their PRs.
- `## Doc impact` section present and current
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row

## Open questions

- How an Owner finds a colleague to add: by email only in AD2A, or a directory search from the start (`_directory_js.html` exists for Panels)? The author, before rung 5.

## Out of scope

- Every exercise setting, Process, the form, panels, dossiers and pairs: AD2B–AD2F.
- Operator settings (the default help contact and time zone): AD2B.
- Removing the scratch store: AD2G.

## Doc impact

- `applydesk/spec/architecture.md` — the database, its history and settings, the new modules, the layering now in force (rungs 2–4).
- `applydesk/spec/applications.md` — who reaches the pages (the check, the lobby's list), the Operators card (rungs 4–6).
- `applydesk/README.md` — building the database locally and the seed (rung 2).
- `applydesk/guide/ad2_deferred_findings.md` — AD-43 and AD-53 struck (at close).
- `applydesk/guide/todo_master.md` — rulings 72–74; the AD2 roadmap row points to the series (rung 1).
- `applydesk/guide/archive/README.md` — the plan's index row (at close).
