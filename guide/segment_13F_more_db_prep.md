# Segment 13F — More DB prep (14C / 16B / 18B / 18C ride-along)

**Status:** Planning — stub created 2026-05-11. Mirrors the
**Segment 13D** (and 13E) inert-migrations pattern: pre-position
the additive, nullable, no-backfill schema changes the rest of the
active workplan needs, so the downstream feature segments are
pure service / UI / template work.

**Sizing:** ~4 PRs (one per migration; PR-sized).
**Depends on:** none. Lands cleanly after 13D / 13E.
**Unblocks:** 14C (reminder cadence), 18B (session tagging),
18C (retention exception + per-session policy), 16B PR 4
(post-MVP role granularity).

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
session_tags                              # PR 1: 18B per-session free-form tags
sessions.reminder_settings                # PR 2: 14C reminder cadence (JSON)
sessions.retention_exception              # PR 3: 18C per-session opt-out (Bool)
sessions.retention_overrides              # PR 3: 18C per-session policy (JSON, post-MVP)
session_operators.role                    # PR 4: 16B PR 4 post-MVP role granularity
```

Five migrations, four PRs (PR 3 lands two columns on `sessions`
in one migration since they're tightly coupled). Every column
nullable; every new table starts empty; no service or web code
reads or writes the new shape until its owning feature segment
lights it up. Inert audit at PR-close time confirms zero hits in
`app/services/` + `app/web/` per PR.

---

## Scope sweep (verified 2026-05-11)

Scanned every non-archive plan under `guide/segment_*.md`. Schema
needs identified for the remaining workplan:

| Source | Change | Why ride along here |
|---|---|---|
| **14C** — Reminders workflow Part 1 | New `sessions.reminder_settings` JSON column (`auto_enabled` / `cadence` / `max_count` / `time_of_day` / `quiet_hours`) | Required by 14C Part 1 (per-session reminder cadence). One column, JSON-shaped (`14C` calls out "columns or JSON blob"; JSON keeps the migration footprint flat). |
| **18B** — Session tagging | New table `session_tags` | Required by 18B Part 2. The plan flags "Tag table vs JSON column" as an open scoping question; we lock the answer here (table — easier per-tag indexing + delete-cascade). |
| **18C** — Retention / deletion workflow Part 2 | New `sessions.retention_exception` Boolean (default `False`, nullable) | Required by 18C Part 2 (per-session opt-out of auto-purge — e.g. legal hold). Minimal cost, large policy value. |
| **18C** — Retention / deletion workflow Part 3 (post-MVP) | New `sessions.retention_overrides` JSON column | Required by 18C Part 3 if it lands. Per-session retention-policy overrides (`response_days` / `audit_days` / `archived_days` keys). NULL means "use deployment default". |
| **16B** — Role delegation PR 4 (post-MVP) | New `session_operators.role` String(32) column, default `"operator"` | Required by 16B PR 4 if pilot feedback flips it. Default backfill across existing rows is `"operator"` (matches today's binary semantics). |
| **13D leftovers** | — | All shipped 2026-05-09; nothing rolls over. |
| **15A / 15B / 15C** | none | All schema already shipped in 13D PRs 1 / 2 / 3 / 4. |
| **15E / 15F** | none | UI / service-only segments; no new tables or columns. |
| **16A** — Sys Admin page + admin user role | none (Option C MVP) | Option C env-allowlist lives in `app/config.py`, not in the DB. **If** 16A later migrates to Option B (per-user flag), `users.is_sys_admin` is a one-column add that lands at that migration time — not pre-positioned here, since Option C is the MVP recommendation. |
| **16C** — Richer audit views | none | Read-only against existing `audit_events`. |
| **17** — AG Grid replacement | none | UI infrastructure swap; no schema. |
| **18A** — Session cloning | none | Service-layer clone of existing tables; no new shape. |
| **19 / 20** — Spec / docs | none | Documentation-only. |
| **14A** — Production hardening | type migrations only | JSON → JSONB, String(36) → native UUID, JSONB indexes. Postgres-specific, not "additive nullable" — stays in 14A. |
| **14B** — Email infrastructure | none | All schema already shipped in 11C Part 2 (Migration `c4f6a8b0d2e5`). |
| **14C** — Reminders workflow Part 2 (scheduled dispatch) | none | Reads against existing `email_outbox` + `audit_events`. The cadence-settings column from Part 1 is the only schema move. |

---

## PRs

### PR 1 — New table `session_tags` (18B ride-along)

**Why first.** Smallest blast radius (new empty table; no
existing rows to interact with). Pure additive. Lets PR 4's
`session_operators.role` land later without table-name clashes
in the sweep.

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

### PR 2 — New column `sessions.reminder_settings` JSON (14C ride-along)

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

### PR 3 — Two columns on `sessions`: `retention_exception` + `retention_overrides` (18C ride-along)

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

### PR 4 — New column `session_operators.role` (16B PR 4 ride-along, post-MVP)

**Scope.** One nullable column on `session_operators`, with a
default backfill of `"operator"` for every existing row so the
read path can treat NULL ≡ "operator" without special-casing:

```python
# app/db/models/session_operator.py
role: Mapped[str | None] = mapped_column(
    String(32), nullable=True, server_default=text("'operator'"),
)
```

`server_default` is the cheap one-shot backfill — every existing
row gets `"operator"` from the migration; new rows inherit the
same default until 16B PR 4 starts setting other values.

**Tests.** Migration round-trip on both dialects. Existing
`session_operators` rows backfill to `"operator"`. New rows
default to `"operator"`. The application-layer enum constant
(`SESSION_OPERATOR_ROLES = ("operator", "viewer", "deputy")`)
lives next to `EMAIL_OUTBOX_STATUSES` as a Python value-set
constant — not a DB CHECK; the gate is at the service-layer
write-path.

**Why this is the lowest priority PR.** 16B PR 4 is post-MVP and
may never land if pilot feedback says the binary model is fine.
But the migration is cheap (one nullable column with a
server-default backfill), and landing it inert here means 16B
PR 4 is pure service / UI work when / if it does land.

---

## Sequencing

PR 1 → PR 2 → PR 3 → PR 4. Each PR is independent and
self-contained; no inter-PR ordering constraints beyond
landing them in numeric order for tidy migration history. Any
PR can ship in isolation if the others slip.

The schema-only PRs are deliberately small (~50-100 LOC each
including the migration, model edit, and the round-trip test).
A reviewer can model the whole contract in one sitting per PR.

---

## Risks + open questions

- **Migration safety.** Every change is additive + nullable; no
  backfill except PR 4's server-default. SQLite + Postgres
  parity is exercised by the existing `ci-postgres` job.
- **JSON shape commitments.** PR 2's `reminder_settings` and
  PR 3's `retention_overrides` are JSON; the actual key schema
  is locked by 14C Part 1 and 18C Part 2-3 respectively. Until
  then, the columns are inert containers. Worth a short note
  in each PR description naming where the shape will be
  pinned.
- **`session_operators.role` default semantics.** The
  `server_default` ('operator') is a SQL-level default
  applied at row-insert time. Today's `session_operators` row
  creation path (`create_session` + 16B PR 1's `add_operator`)
  doesn't set `role` post-PR-4 until 16B PR 4 starts to —
  every new row will land with `"operator"` via the default,
  which is the right behaviour. Confirm during PR scoping
  that the default actually fires for INSERTs that don't
  mention the column on both dialects.
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

- New: `app/db/models/session_tag.py`, four Alembic migrations.
- Touched: `app/db/models/review_session.py` (PR 2 + PR 3),
  `app/db/models/session_operator.py` (PR 4).
- Inert audit at every PR-close: `grep -rn "reminder_settings\|retention_exception\|retention_overrides\|session_tags\|session_operators.role" app/services/ app/web/` should return nothing until the owning feature segment lights up.

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
- Owning feature plans (14C / 16B / 18B / 18C) updated to
  reference "schema pre-positioned in 13F PR N" instead of
  "new column / new table".
- `guide/codebase_assessment_*` next snapshot picks up the
  "Schema landed inert" entry for 13F.
