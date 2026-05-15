# Segment 13F — More DB prep (14C / 16A / 16B / 18A / 18B / 18C ride-along)

**Status:** In flight — **PRs 1 + 2 shipped 2026-05-11**
(migrations `779b90e4b397` + `8003c2be99d8`); **PRs 6 + 7
shipped 2026-05-15** (migrations `2fec0f646bd2` +
`e9277c43b251`) ahead of Segment 18B being picked up; PRs 3-5
deferred until their consumer segments (18A / 14C / 18C) are
picked up, per the "piecemeal, front-load the 16-series work"
sequencing decision. The 16-series schema scaffolding is
now complete — Segment 16A is unblocked to start its PR ladder.
Stub created 2026-05-11; revised 2026-05-11 to fold in the
16-series admin / owner-role requirements after a codebase
audit; revised again 2026-05-11 to add the operator-allowlist
column once Option C became the locked access posture;
revised again 2026-05-11 to reorder PRs so the 16-series work
comes first (PR 1 + PR 2) and the consumer-deferred work
follows (PRs 3-5); revised again 2026-05-15 to add PR 6
(`sessions.display_timezone`) as the schema slot for the 18B
per-session timezone work; revised again 2026-05-15 — after a
fresh sweep of every upcoming segment — to add PR 7
(`users.preferences`) as the per-operator preferences container
for 18B PR 2 and future operator-level display settings.
Mirrors the **Segment 13D** (and 13E) inert-migrations pattern:
pre-position the additive, nullable, no-backfill schema changes
the rest of the active workplan needs, so the downstream feature
segments are pure service / UI / template work.

**Sizing:** ~7 PRs (one per migration; PR-sized).
**Depends on:** none. Lands cleanly after 13D / 13E.
**Unblocks:** 14C (reminder cadence), 16A (Sys Admin auth via
persisted flag instead of env-allowlist), 16B (per-session
owner UI), 18A (session tagging), 18B (per-operator default +
per-session display timezone), 18C (retention exception +
per-session policy).

---

## Goal

Pre-position every additive, nullable, no-backfill schema change
that downstream feature segments need, so that those feature
segments stay pure service / UI / template work. Net effect: a
shorter, safer feature segment per downstream plan, plus one
schema-only segment with a predictable test surface.

The migrations land **inert** — every column is nullable, every
new table starts empty, and no service code reads or writes the
new shape until its owning feature segment lights it up. Mirrors
how **13D** pre-positioned six migrations for 15A / 15B / 15C /
13B / 13C, and how Segment 11C Part 2 pre-positioned the seven
`email_outbox` audit-log columns ahead of Segment 14B Part A.

---

## Final layout (proposed)

```
users.is_sys_admin                        # PR 1: ✅ shipped — 16A sys-admin gate
                                          #       persisted source + lock
                                          #       session_operators.role value-set
                                          #       + flip Python-default to "owner"
                                          #       (migration 779b90e4b397)
users.is_operator                         # PR 2: ✅ shipped — 16A workspace allowlist
                                          #       under Option C access model
                                          #       (strict admit-by-sys-admin)
                                          #       (migration 8003c2be99d8)
session_tags                              # PR 3: 18A per-session free-form tags (pending)
sessions.reminder_settings                # PR 4: 14C reminder cadence (JSON, pending)
sessions.retention_exception              # PR 5: 18C per-session opt-out (Bool, pending)
sessions.retention_overrides              # PR 5: 18C per-session policy (JSON, post-MVP, pending)
sessions.display_timezone                 # PR 6: ✅ shipped — 18B per-session display
                                          #       timezone (String) (migration 2fec0f646bd2)
users.preferences                         # PR 7: ✅ shipped — per-operator preferences
                                          #       container (JSON) (migration e9277c43b251)
```

Seven migrations + one model-only correction across seven PRs.
Every column nullable (PR 1's `is_sys_admin` has a SQL-level
`false` server-default so existing rows backfill safely); every
new table starts empty; no service or web code reads or writes
the new shape until its owning feature segment lights it up.
Inert audit at PR-close time confirms zero hits in
`app/services/` + `app/web/` per PR.

---

## Codebase audit (2026-05-11)

Before locking the 16-series schema asks, a codebase pass turned
up two findings worth recording:

1. **`session_operators.role` already exists** — `String(32)`,
   NOT NULL, Python-default `"operator"`. An earlier draft of
   13F proposed *adding* this column for a future 16B
   post-MVP slice; that draft was based on a stale read.
   The column has been on the model since the original
   `SessionOperator` definition; `sessions.py` already writes
   `role="owner"` for the session creator at create-time. The
   live default is the only value in production. **No
   migration needed** to support owners / managers; the column
   is already there. The Python-default of `"operator"` is
   dead code (every write specifies `"owner"`) and gets fixed
   to `"owner"` in PR 1 alongside the value-set lock.

2. **`sessions.created_by_user_id`** already exists as the
   immutable creator FK. No code path updates it post-create —
   it's already "creator, cannot be changed". No schema move
   needed; the audit identity is in place.

These findings collapse the 16-series schema ask to **one**
new column (`users.is_sys_admin`) plus the model-only
correction on `session_operators.role`. Both ride in PR 1.

---

## Scope sweep (verified 2026-05-11)

Scanned every non-archive plan under `guide/segment_*.md`. Schema
needs identified for the remaining workplan:

| Source | Change | Why ride along here |
|---|---|---|
| **14C** — Reminders workflow Part 1 | New `sessions.reminder_settings` JSON column (`auto_enabled` / `cadence` / `max_count` / `time_of_day` / `quiet_hours`) | Required by 14C Part 1 (per-session reminder cadence). One column, JSON-shaped (`14C` calls out "columns or JSON blob"; JSON keeps the migration footprint flat). |
| **18A** — Session tagging | New table `session_tags` | Required by 18A Part 2. The plan flags "Tag table vs JSON column" as an open scoping question; we lock the answer here (table — easier per-tag indexing + delete-cascade). |
| **18C** — Retention / deletion workflow Part 2 | New `sessions.retention_exception` Boolean (default `False`, nullable) | Required by 18C Part 2 (per-session opt-out of auto-purge — e.g. legal hold). Minimal cost, large policy value. |
| **18C** — Retention / deletion workflow Part 3 (post-MVP) | New `sessions.retention_overrides` JSON column | Required by 18C Part 3 if it lands. Per-session retention-policy overrides (`response_days` / `audit_days` / `archived_days` keys). NULL means "use deployment default". |
| **18B** — Date and time settings | New `sessions.display_timezone` String column (nullable; IANA zone name) | Required by 18B PR 3 (per-session display-timezone override). One nullable string column; `NULL` means "inherit the operator default timezone". |
| **18B** — Date and time settings | New `users.preferences` JSON column (nullable) | Required by 18B PR 2 (per-operator default timezone). A general per-operator preferences container — first key `display_timezone`, future keys for other operator-level display settings (display sizing, the typography knob). JSON over flat columns: the key set is open-ended — same reasoning as `sessions.reminder_settings`. Added 2026-05-15 after the re-sweep below. |
| **16A** — Sys Admin page + admin user role | New `users.is_sys_admin` Boolean column (server-default `false`) | Required by 16A PR 2 (sys-admin gate). Persisted per-user flag bootstrapped from the existing `SYS_ADMIN_EMAILS` env var on first-sign-in but extensible in-app afterwards via 16A PR 6. |
| **16A** — Workspace operator allowlist (Option C access model) | New `users.is_operator` Boolean column (server-default `false`) | Required by 16A PR 1 (operator-allowlist gate). Locked 2026-05-11: the app is a citizen project with no tech-support promise, so the access model is strict (Option C) — only operators a sys-admin explicitly admits can use operator routes. Bootstrap source on first-sign-in is a new `OPERATOR_EMAILS` env var; persisted column is authoritative thereafter. Sys-admin implies operator (read-path checks `is_operator OR is_sys_admin`). |
| **16B** — Role delegation (owner / manager) | **No schema change.** `session_operators.role` already exists (`String(32)`, NOT NULL). Today's only written value is `"owner"`. PR 1 locks the value-set constant (`SESSION_OPERATOR_ROLES = ("owner", "manager")`) and fixes the dead Python-default from `"operator"` to `"owner"`. | The column lands inert (already written). The value-set lock + default fix ride in PR 1 since they're cohesive with the `users.is_sys_admin` admin-role plumbing. |
| **13D leftovers** | — | All shipped 2026-05-09; nothing rolls over. |
| **15A / 15B / 15C** | none | All schema already shipped in 13D PRs 1 / 2 / 3 / 4. |
| **15E / 15F** | none | UI / service-only segments; no new tables or columns. |
| **16C** — Richer audit views | none | Read-only against existing `audit_events`. |
| **17** — AG Grid replacement | none | UI infrastructure swap; no schema. |
| **18A** — Session cloning | none | Service-layer clone of existing tables; no new shape. |
| **19 / 20** — Spec / docs | none | Documentation-only. |
| **14A** — Production hardening | type migrations only | JSON → JSONB, String(36) → native UUID, JSONB indexes. Postgres-specific, not "additive nullable" — stays in 14A. |
| **14B** — Email infrastructure | none | All schema already shipped in 11C Part 2 (Migration `c4f6a8b0d2e5`). |
| **14C** — Reminders workflow Part 2 (scheduled dispatch) | none | Reads against existing `email_outbox` + `audit_events`. The cadence-settings column from Part 1 is the only schema move. |

---

## Scope re-sweep (2026-05-15)

Re-ran the sweep across every current `guide/segment_*.md` plan
plus `deferred_until_pilot_feedback.md`, cross-checked against
the live ORM in `app/db/models/`. The 16-/15-series segments
that drove the original sweep have since shipped; the question
was whether the *remaining* upcoming work surfaces any new
additive schema need.

**Findings:**

- **One new rideable addition — `users.preferences` JSON**
  (PR 7). 18B's per-operator default timezone needs a persisted,
  operator-editable home; rather than a one-column-per-setting
  accretion on `users`, it lands as a general per-operator
  preferences JSON container (first key `display_timezone`;
  future keys for display sizing / the typography knob). 18B PR 2
  consumes it. *(The earlier 18B sketch floated a workspace-
  singleton `workspace_settings` table; the per-operator JSON
  container was chosen instead 2026-05-15 — it fits the existing
  `users`-tied grain and is open-ended.)*
- **Everything else is already covered** — `session_tags`
  (PR 3), `sessions.reminder_settings` (PR 4),
  `sessions.retention_*` (PR 5), `sessions.display_timezone`
  (PR 6) — or needs no schema (14B reads existing `email_outbox`
  columns; 17A's "value_version" is the existing
  `Response.version`; 17B / 19 / 20 are UI / docs; 18A cloning +
  18D import/export are service-layer-only; 18C's retention
  policy is env-var config).
- **14A type migrations stay out of 13F.** 14A's JSON→`JSONB`,
  `String(36)`→native `UUID`, `String`→DB `ENUM`, and GIN /
  partial indexes are Postgres-only and destructive — they break
  13F's "same migration runs on SQLite and Postgres" contract.
  They remain 14A's own, gated on real query plans.
- **Flagged, not actionable here — 13C stale plan.** `segment_13C`
  builds group fanout on `Assignment.context` JSON, a column
  **retired in 15D PR 6b**. 13C needs a re-scope to relocate its
  group-fanout metadata before any of its schema can be
  pre-positioned; the column name / shape is undefined, so it is
  **not** a 13F candidate now. Raise with whoever picks up 13C.

---

## PRs

PRs land in two waves: the **16-series wave** (PR 1 + PR 2)
pre-positions the admin / allowlist plumbing for Segment 16A;
the **consumer-deferred wave** (PRs 3-6) pre-positions the
remaining tables and columns when their consumer segments
(18A / 14C / 18C / 18B) are ready to be picked up.

### PR 1 — `users.is_sys_admin` Boolean + lock `session_operators.role` value-set + default fix (16A / 16B ride-along) — ✅ **shipped 2026-05-11**

**Outcome.** Migration `779b90e4b397` adds `users.is_sys_admin`
(Boolean, NOT NULL, `server_default false`). `SessionOperator`
gains the `SESSION_OPERATOR_ROLES = ("owner", "manager")`
module-level constant; the Python-default flips from
`"operator"` to `"owner"`. 5 new tests
(`tests/integration/test_users_is_sys_admin_schema.py`) round-
trip the column on both dialects and pin the value-set + the
new default. Inert audit at PR close: zero hits for
`is_sys_admin` / `SESSION_OPERATOR_ROLES` in `app/services/` +
`app/web/` — light-up lives in 16A PR 2 (column read) +
16B PR 1 (role write-path validation).

**Why this PR is structured this way.** The codebase audit
above showed `session_operators.role` already exists, so this
PR doesn't add it — it locks the value-set + fixes the dead
Python-default. The only actual schema move is one new column
on `users`. Both changes are cohesive (admin / owner role
plumbing) and land together.

#### Part A — Add `users.is_sys_admin` Boolean

```python
# app/db/models/user.py
is_sys_admin: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False, server_default=text("false"),
)
```

`server_default=text("false")` backfills every existing `users`
row to `False` at migration time so the NOT NULL constraint
holds. New rows default to `False` (Python-side `default=False`
for ORM-issued inserts).

**Bootstrap source.** On user-create / first-sign-in
(`deps.get_or_create_user`), 16A PR 1 sets `is_sys_admin=True`
if the principal's email is in `SYS_ADMIN_EMAILS` (the existing
env var, kept as a bootstrap mechanism rather than the live
source). After first sign-in, the persisted column is the
source of truth — removing an email from the env var does
**not** auto-demote that operator. Promotion / demotion of
later operators happens via 16A PR 6's UI.

This is what makes the admin list "extensible without
redeployment": the env var seeds, the DB column persists, the
UI manages.

#### Part B — Lock `session_operators.role` value-set + fix Python-default

**No migration.** Pure model edit:

```python
# app/db/models/session_operator.py
role: Mapped[str] = mapped_column(
    String(32), default="owner", nullable=False
)
```

(`default` flipped from `"operator"` to `"owner"` — the dead
default the codebase audit surfaced.)

**Plus a new value-set constant** alongside the existing
`EMAIL_OUTBOX_STATUSES` / `EMAIL_OUTBOX_KINDS` precedents:

```python
# app/db/models/session_operator.py (module-level)
SESSION_OPERATOR_ROLES: tuple[str, ...] = ("owner", "manager")
```

- `"owner"` — today's only value. Full per-session rights:
  delete, change setup, manage session, access details. The
  session creator is auto-inserted with this role at
  create-time (existing behaviour from `sessions.py:30-36`,
  unchanged).
- `"manager"` — **reserved future value** (less rights than
  owner; specifics TBD when 16B introduces the role). Lives
  in the tuple so a future addition is a deliberate Python
  edit, not a free-form string drift.

**Service-layer enforcement.** Write-path validates `role`
against the tuple; no DB CHECK constraint (matches the
existing `EMAIL_OUTBOX_*` precedent). The DB column stays
schema-stable across future value-set widening.

#### Why creator + owner don't need new schema

- **`sessions.created_by_user_id`** is already the immutable
  creator FK; no code path overwrites it (audit identity).
- **`session_operators(session_id, user_id, role="owner")`**
  is the editable per-session owner list.

The two concerns are already cleanly separated in the existing
schema. Adding owners = `INSERT` a `session_operators` row.
Removing an owner = `DELETE`. Demoting the creator from owner
status is allowed at the service layer **only if ≥1 other
owner exists** — invariant lives in 16B PR 1's `remove_owner`
helper, not in a DB CHECK.

**Tests.**

- Migration round-trip on SQLite + `ci-postgres`. Existing
  `users` rows backfill to `is_sys_admin=False`.
- NOT NULL holds after backfill on both dialects.
- New `users` rows default to `is_sys_admin=False` (Python
  default) when not specified explicitly.
- `session_operators` rows created via the model default land
  with `role="owner"` (regression on the Python-default fix).
- `SESSION_OPERATOR_ROLES` tuple is importable from
  `app.db.models.session_operator`; unit test pins membership.
- Inert audit: `grep -rn "is_sys_admin\|SESSION_OPERATOR_ROLES"
  app/services/ app/web/` returns zero hits at PR close (light-up
  happens in 16A PR 2 / 16B PR 1).

### PR 2 — `users.is_operator` Boolean (16A ride-along, Option C access model) — ✅ **shipped 2026-05-11**

**Outcome.** Migration `8003c2be99d8` adds `users.is_operator`
(Boolean, NOT NULL, `server_default false`). 4 new tests
(`tests/integration/test_users_is_operator_schema.py`)
round-trip the column on both dialects and pin the two flags'
independence at the column level. Inert audit at PR close:
zero hits for `is_operator` in `app/services/` + `app/web/` —
light-up happens in 16A PR 1 (`require_operator` dependency +
`OPERATOR_EMAILS` env-var bootstrap read in `get_or_create_user`).

**Why this PR exists.** The 2026-05-11 access-model discussion
locked the workspace access posture as **Option C — strict
allowlist**: only operators a sys-admin explicitly admits can
use operator routes. This is the citizen-project posture
("can't really promise much in terms of technical support, a
stricter user list is probably necessary") rather than
Option A (open) or Option B (tenant-restricted via Easy Auth).

The persisted source of truth for the allowlist is one
column on `users`, mirroring PR 1's `is_sys_admin` shape.

**Scope.** One NOT NULL Boolean column on `users` with a
SQL-level server-default so existing rows backfill safely:

```python
# app/db/models/user.py
is_operator: Mapped[bool] = mapped_column(
    Boolean, default=False, server_default=text("false"), nullable=False
)
```

**Bootstrap source.** On user-create / first-sign-in
(`deps.get_or_create_user`), 16A PR 1 sets `is_operator=True`
if the principal's email is in a new `OPERATOR_EMAILS` env var
(parallels the `SYS_ADMIN_EMAILS` pattern from PR 1). The
persisted column is authoritative after first sign-in —
removing an email from the env var does **not** auto-revoke;
revocation happens via 16A PR 6's workspace UI.

**Read-path semantics (light-up in 16A PR 1).** Operator routes
gate on `is_operator OR is_sys_admin` — sys-admin implies
operator, so promoting someone to sys-admin (`is_sys_admin=True`)
auto-grants operator access without also having to flip
`is_operator`. The workspace UI shows both flags independently
for transparency.

**Tests.**

- Migration round-trip on SQLite + `ci-postgres`. Existing
  `users` rows backfill to `is_operator=False`.
- NOT NULL holds after backfill on both dialects.
- New `users` rows default to `is_operator=False` (Python
  default) when not specified explicitly.
- Toggle: `True → False → True` round-trips persist correctly.
- Inert audit: `grep -rn "is_operator" app/services/ app/web/`
  returns zero hits at PR close (light-up happens in
  16A PR 1).

**Why a separate PR from PR 1.** Could have ridden as Part C of
PR 1 in principle. Kept separate because (a) PR 1 already
shipped, (b) the access-model decision came after PR 1 landed,
(c) one migration per PR is the 13D / 13E precedent.

### PR 3 — New table `session_tags` (18A ride-along)

**Scope.** SQL + model only. New table:

```python
# app/db/models/session_tag.py (new)
class SessionTag(Base):
    __tablename__ = "session_tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tag: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("session_id", "tag", name="uq_session_tag_session_tag"),
    )
```

**Tests.** Migration round-trip on SQLite + `ci-postgres`.
`(session_id, tag)` uniqueness pinned. Cascade-on-session-delete
pinned. Inert audit: zero service / web references at PR close.

### PR 4 — New column `sessions.reminder_settings` JSON (14C ride-along)

**Scope.** One nullable JSON column on `sessions`. The JSON
shape gets locked in 14C Part 1; this PR just opens the slot.

```python
# app/db/models/review_session.py
reminder_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Why JSON over flat columns: the cadence vocabulary (named policy
enum / cron-ish expression / etc.) is still in scoping (14C
"Working notes"). JSON keeps the migration flat — when 14C Part
1 locks the shape, no new migration is needed; the JSON keys
acquire meaning.

**Tests.** Migration round-trip on both dialects. Round-trips a
fixture JSON blob (the actual shape lives in 14C tests). Inert
audit: zero service / web references at PR close.

### PR 5 — Two columns on `sessions`: `retention_exception` + `retention_overrides` (18C ride-along)

**Scope.** Two nullable columns on `sessions`, landed together
because they're tightly coupled (one is the "opt out entirely"
flag; the other is the "override the deployment defaults" JSON):

```python
# app/db/models/review_session.py
retention_exception: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
retention_overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

`retention_exception=NULL` and `=False` both mean "no exception"
(18C Part 2 will normalise read-path). `retention_overrides=NULL`
means "use the deployment retention defaults" (18C Part 2's env
vars).

**Tests.** Migration round-trip on both dialects. Default reads
back as `NULL` for both columns; mutating one doesn't affect the
other. Inert audit: zero service / web references at PR close.

### PR 6 — New column `sessions.display_timezone` String (18B ride-along) — ✅ **shipped 2026-05-15**

**Outcome.** Migration `2fec0f646bd2` adds `sessions.display_timezone`
(`String(64)`, nullable). 3 new tests
(`tests/integration/test_session_display_timezone_schema.py`)
round-trip the column on both dialects (default `NULL`, an IANA
name string, set/clear flip). Inert audit at PR close: zero
hits for `display_timezone` in `app/services/` + `app/web/` —
light-up lives in 18B PR 3.

**Scope.** One nullable string column on `sessions`. Holds an
IANA timezone name (e.g. `Asia/Singapore`); `NULL` means
"inherit the creating operator's default timezone".

```python
# app/db/models/review_session.py
display_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

Why nullable rather than NOT NULL with a default: the
`NULL`-means-inherit semantics are load-bearing in 18B's
resolution order (session override → operator default → UTC).
18B PR 3 stamps new sessions with the creating operator's
resolved default at create-time, but the column stays nullable
so "inherit" remains expressible (e.g. for sessions created
before the operator set a default, or if 18B later adds an
explicit "revert to default" affordance).

`String(64)` comfortably fits every IANA zone name (the longest
is well under 40 chars). No CHECK constraint — validity is
enforced at the service layer against `zoneinfo.available_timezones()`
when 18B PR 3 lights the column up.

**Tests.** Migration round-trip on SQLite + `ci-postgres`.
Default reads back as `NULL`. Round-trips an IANA name string
(`Asia/Singapore`). Inert audit: zero service / web references
at PR close — light-up lives in 18B PR 3 (per-session timezone
card + create-time stamping).

### PR 7 — New column `users.preferences` JSON (18B ride-along) — ✅ **shipped 2026-05-15**

**Outcome.** Migration `e9277c43b251` adds `users.preferences`
(`JSON`, nullable). 3 new tests
(`tests/integration/test_user_preferences_schema.py`) round-trip
the column on both dialects (default `NULL`, a fixture dict,
replace/clear mutation). Inert audit at PR close: zero hits for
`preferences` in `app/services/` + `app/web/` — light-up lives
in 18B PR 2.

**Scope.** One nullable JSON column on `users` — a general
per-operator preferences container.

```python
# app/db/models/user.py
preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

The column holds a JSON object whose keys are individual
operator-level preferences. **First consumer:** 18B PR 2 reads /
writes the `display_timezone` key (the operator's default
timezone for sessions they create). The container is
deliberately general — future operator-level display settings
(a display-sizing knob, the typography knob from
`spec/domain_assumptions.md`) become **new keys, not new
migrations**.

`NULL` (or an absent key) means "no preference set" — the
consumer falls through to its in-code default (`UTC` for the
timezone key). JSON over a column-per-setting: the key set is
open-ended, and operator UI preferences are read on render,
never queried or filtered — the same reasoning that put
`sessions.reminder_settings` (PR 4) in JSON. The per-key shape
is owned by each consuming segment, not pinned here; PR 7 just
opens the container.

This is a per-operator setting, not workspace-wide — it joins
the existing `users`-tied operator config (SMTP credentials,
the `is_operator` / `is_sys_admin` flags, the RTD / RuleSet
library `owner_user_id` rows). No workspace-singleton table is
introduced.

**Tests.** Migration round-trip on SQLite + `ci-postgres`.
Default reads back as `NULL`. Round-trips a fixture dict
(e.g. `{"display_timezone": "Asia/Singapore"}`). Inert audit:
zero service / web references at PR close — light-up lives in
18B PR 2.

---

## Sequencing

**16-series wave first** (PR 1 → PR 2), then the
**consumer-deferred wave** (PRs 3-7 ride with their owning
feature segments when those are picked up). Each PR is
independent and self-contained; no inter-PR ordering
constraints beyond landing them in numeric order for tidy
migration history.

- **PR 1** — ✅ shipped 2026-05-11 (migration `779b90e4b397`).
  Unblocks 16A PR 2 (sys-admin gate read) + 16B PR 1 (owner
  role write-path).
- **PR 2** — ✅ shipped 2026-05-11 (migration `8003c2be99d8`).
  Unblocks 16A PR 1 (operator-allowlist gate read) + 16A PR 6
  (workspace admit/revoke surface) + 16B PR 1 + 2
  (admitted-pool query).
- **PR 3** — defer until 18A (session tagging + archiving)
  is picked up.
- **PR 4** — defer until 14C (reminders workflow) is picked
  up. Specifically Part 1 (per-session cadence settings)
  is the consumer.
- **PR 5** — defer until 18C (retention / deletion workflow)
  is picked up. Specifically Part 2 (per-deployment retention
  policy) is the first consumer; Part 3 (per-session policy
  overrides) is the second.
- **PR 6** — ✅ shipped 2026-05-15 (migration `2fec0f646bd2`).
  Unblocks 18B PR 3 (per-session display-timezone override +
  Session Edit card).
- **PR 7** — ✅ shipped 2026-05-15 (migration `e9277c43b251`).
  Unblocks 18B PR 2 (per-operator default timezone +
  `/operator/settings` card).

The schema-only PRs are deliberately small (~50-100 LOC each
including the migration, model edit, and the round-trip test).
A reviewer can model the whole contract in one sitting per PR.

---

## Risks + open questions

- **Migration safety.** Every change is additive + nullable; no
  backfill except PR 1's server-default. SQLite + Postgres
  parity is exercised by the existing `ci-postgres` job.
- **JSON shape commitments.** PR 4's `reminder_settings`,
  PR 5's `retention_overrides`, and PR 7's `users.preferences`
  are JSON; the actual key schema is locked by 14C Part 1,
  18C Part 2-3, and 18B PR 2 respectively. Until then, the
  columns are inert containers. Worth a short note in each PR
  description naming where the shape will be pinned.
- **`session_operators.role` Python-default flip.** PR 1
  changes the model's `default="operator"` to
  `default="owner"`. This affects ORM `SessionOperator(...)`
  constructions that don't pass `role` explicitly. **Today's
  only such call site is `sessions.py:30-36` which already
  writes `"owner"` explicitly** — so behaviour is unchanged
  for existing code. Future call sites added in 16B PR 1's
  `permissions.add_owner` will continue to pass an
  explicit role; the default is the safety net, not the
  load-bearing path.
- **`users.is_sys_admin` / `users.is_operator` bootstrap
  semantics.** First-sign-in reads `SYS_ADMIN_EMAILS` /
  `OPERATOR_EMAILS`; subsequent sign-ins do not. Worth a
  one-line note in the 16A PR 1 description so operators who
  get added to either env var after first sign-in know they
  also need a UI-side admit / promote via 16A PR 6 (or a
  one-off manual DB poke for the bootstrap operator). Same
  pattern, two flags — the read path lives in one place
  (`get_or_create_user`).
- **Sys-admin implies operator.** Read-path gate is
  `is_operator OR is_sys_admin`. Demoting someone from
  sys-admin does **not** flip `is_operator` (the two flags
  are independent for transparency); revoking operator status
  is a separate UI action.
- **`session_tags` cascade-on-delete.** PR 1's
  `ON DELETE CASCADE` matches the pattern every other
  per-session join table uses (`session_operators`,
  `session_rule_sets`, etc.). Confirm no surprise from the
  Sessions Danger Zone delete path (which already deletes
  per-session rows in service code anyway).
- **Postgres-specific upgrades deferred.** The JSON columns
  PRs 2 / 3 land use cross-dialect `JSON`, not `JSONB`. The
  `JSON → JSONB` migration for indexability is Segment 14A's
  concern (and inherits from the existing
  `AuditEvent.detail` / `email_template_overrides` precedents
  — same upgrade story).

---

## Critical files

- New: `app/db/models/session_tag.py` (PR 3), seven Alembic
  migrations (PR 1 adds one migration for `users.is_sys_admin`
  plus a model-only edit on `session_operator.py`; PR 2 adds
  one migration for `users.is_operator`; PRs 3 / 4 / 5 / 6 / 7
  each add one migration for the table or column they
  introduce).
- Touched: `app/db/models/user.py` (PR 1 Part A + PR 2 + PR 7),
  `app/db/models/session_operator.py` (PR 1 Part B —
  Python-default fix + `SESSION_OPERATOR_ROLES` constant),
  `app/db/models/review_session.py` (PR 4 + PR 5 + PR 6).
- Inert audit at every PR-close: `grep -rn "reminder_settings\|retention_exception\|retention_overrides\|session_tags\|is_sys_admin\|is_operator\|SESSION_OPERATOR_ROLES\|display_timezone\|\.preferences" app/services/ app/web/` should return nothing until the owning feature segment lights up.

---

## Verification

- `pytest -q` green on SQLite + `ci-postgres` after each PR.
- `ruff check .` green.
- Migration round-trip test per PR (`tests/integration/test_*_schema.py`
  shape — mirrors 11C Part 2's
  `test_email_outbox_schema.py` precedent).
- Inert audit: `grep` for the new identifiers across
  `app/services/` + `app/web/` returns zero hits at every PR
  close. Light-up happens in the owning feature segment.
- LOC budget: ~80-100 LOC of production code per PR (model +
  migration); ~120-150 LOC of tests per PR (round-trip +
  uniqueness pin + cascade pin). Total: ~400 LOC production /
  ~600 LOC tests across the segment.

---

## Doc impact

When PRs ship:

- `docs/status.md` timeline entry per PR landed.
- `guide/todo_master.md` Done list updated.
- `spec/settings_inventory.md` — new columns + table added to
  the relevant per-session settings sections (each marked
  **Inert** until the owning feature segment lights it up,
  mirroring the post-13D entries).
- Owning feature plans (14C / 16A / 16B / 18A / 18B / 18C)
  updated to reference "schema pre-positioned in 13F PR N"
  instead of "new column / new table". In particular 16A flips from
  Option C (env-allowlist) to Option B (persisted flag with
  env-bootstrap); 16B PR 3 becomes unconditional MVP scope
  rather than conditional-on-future-migration.
- `guide/codebase_assessment_*` next snapshot picks up the
  "Schema landed inert" entry for 13F.
