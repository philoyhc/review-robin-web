# Segment 11K — Audit-event `detail` schema convention

Stub. Implementation plan for catalog item `unfinished_business.md`
§5 — pinning the canonical JSON shape of `AuditEvent.detail` so
that:

- Emitters compose by selecting from a small set of named
  envelopes rather than inventing a per-callsite dict shape.
- The Segment 12 (audit retention / export) consumer can read
  `audit_events` as a stable schema rather than the union of
  every emitter's idiosyncrasies.
- New emitters introduced in 11C / 11F / 11G / 11J / 12A
  inherit the convention from day one rather than being
  retrofitted later.

This is the **last sub-segment before Segment 12** per
`guide/todo_master.md` "Notes on the order".

## Status

Planning. Sized as **~8 PRs**: one spec PR, one PR per emitter
family (six families today, see below), and one optional
validation-on-write PR. Each migration PR is small and
independently shippable; the spec PR has to land first.

1. **PR 1 — Spec write-up + audit helpers + one family migrated
   as proof.** Adds the canonical shapes to `spec/architecture.md`,
   ships typed envelope helpers in `app/services/audit.py`, and
   migrates the **session lifecycle** family (`session.created`
   / `.updated` / `.deleted` / `.validated` / `.invalidated` /
   `.activated` / `.reverted_to_draft` / `instrument.opened` /
   `.closed`) to use them.
2. **PRs 2-6 — Migrate the remaining five families**, one PR
   each. Order: instruments → invitations → responses →
   assignments → csv_imports. Each PR rewrites that family's
   emitters to use the helpers and updates the family's tests.
3. **PR 7 — Pydantic write-validation gate.** `audit.write_event`
   gains a per-event-type Pydantic discriminator that asserts
   the emitted detail conforms to its family's shape. Failures
   are loud at test time so drift is caught before deploy.

## Why now

- **Forward-looking emitter sites.** Segments 11C / 11F / 11G /
  11J / 12A all add or extend audit emitters. Pinning the shape
  before they ship is much cheaper than retrofitting after
  five segments.
- **Segment 12 consumer.** Segment 12's audit-export CSV needs a
  predictable column model. Without a canonical shape, the
  export has to special-case every emitter — fragile and noisy.
- **No-history-rewrite cost.** Old `audit_events` rows keep their
  old shape; only new writes produce the canonical shape. The
  spec documents the cutover date so a future reader of old
  rows knows what they're looking at.

## Reference

- `guide/unfinished_business.md` §5 — catalog entry, with the
  "five idiosyncrasies" enumeration this segment fixes.
- `app/db/models/audit_event.py` — the model. `detail` is a
  `Mapped[dict | None]` over a JSON column; the column type
  itself doesn't change in 11K, only the values written.
- `app/services/audit.py` — current `write_event(...)` helper.
  Already accepts `detail: dict | None`; 11K extends that
  signature with typed-helper overloads.
- `docs/status.md` "Audit log" — today's only reconciliation.
  PR 1 promotes the section to `spec/architecture.md` and
  retires the inline copy in `status.md`.

## Canonical shapes

The convention is "**at most one payload envelope per event**,
plus orthogonal identity / reason / refs slots." Emitters pick
the envelope that fits the event's nature; mixing two payload
envelopes in one event is a smell that reads as the event
trying to do two things at once.

### Identity context (almost always present)

Every event detail carries the canonical identity slots so a
human reading the row in isolation can tell what it's about
without joining against the FK columns:

```jsonc
{
  "session_id": <int | null>,
  "session_code": "<str | null>",
  // … plus exactly one payload envelope, see below …
}
```

`session_id` mirrors the FK column; including it in `detail`
costs ~6 bytes per row and saves the audit-export consumer a
join. `session_code` is the operator-typed stable identifier;
including it stabilises bookmarks and search ("show me every
event for code 'CS101'") without joining against `sessions`,
which is invaluable once Segment 12 supports cross-session
audit views.

For events with no session FK (today: nothing — every event is
session-scoped), both fields are `null`.

### Payload envelopes (pick one)

#### `changes` — scalar-key updates

```jsonc
{
  "changes": {
    "name": ["old", "new"],
    "deadline": ["2026-05-01T00:00:00+00:00", "2026-05-15T00:00:00+00:00"],
    "help_contact": [null, "support@x.edu"]
  }
}
```

For `session.updated`, `instrument.field_updated`,
`email_template.updated`, `operator_email_settings.updated`.
Each value is a `[old, new]` two-tuple; `null` is allowed on
either side. No nested keys (use `set_changes` if you're
mutating a collection).

#### `snapshot` — full-state capture

```jsonc
{
  "snapshot": {
    "id": 17,
    "name": "Final Review",
    "code": "FR2026",
    "deadline": "2026-06-01T00:00:00+00:00",
    "status": "draft"
    // … every column at the moment of the event …
  }
}
```

For `session.deleted`, `instrument.deleted`, `reviewer.deleted`,
etc. — events where the row is about to disappear and we want
the post-mortem state captured. Snapshot keys mirror DB column
names; nested objects are allowed (e.g. `snapshot.instruments`
on `session.deleted`).

#### `counts` — aggregate ops

```jsonc
{
  "counts": {
    "reviewers": 8,
    "reviewees": 13,
    "assignments": 104
  }
}
```

For bulk operations — `assignments.generated`,
`reviewers.imported`, `reviewees.imported`, `responses.deleted_all`,
`responses.cleared`, the new 12A `session.{kind}_extracted`
events, the Quick Setup `session.config_imported` event. All
values are non-negative integers.

#### `set_changes` — collection mutations (added / removed / updated)

```jsonc
{
  "set_changes": {
    "added":   [{ "key": "tag_1", "label": "Department" }, …],
    "removed": [{ "key": "tag_old", "label": "Legacy" }],
    "updated": [{ "key": "tag_2", "changes": { "label": ["A", "B"] }}]
  }
}
```

For events that mutate a collection of children — D11's
`instrument.display_fields_saved`, the future
`instrument.response_fields_saved`. Each entry in `added` /
`removed` is a flat dict (no nested envelopes). `updated`
entries carry their own `changes` sub-dict (same shape as the
top-level `changes` envelope; one level of nesting only).

### Orthogonal slots (combine freely with any envelope)

#### `reason` — top-level string

```jsonc
{ "reason": "operator_revert", "snapshot": { … } }
```

For events triggered by a known cause: invalidation
(`reason: "setup_mutation"`), revert
(`reason: "operator_revert"`), cascade close
(`reason: "deadline"` / `"manual"`). Free-form `str`; emitters
pick from a small documented set per event family rather than
typing freely.

#### `refs` — cross-entity reference IDs

```jsonc
{ "refs": { "instrument_id": 7, "reviewer_id": 42 } }
```

For events whose subject isn't the session itself — when an
event scoped to a session is *about* a child entity (an
instrument, a reviewer, a response field). Keys end in `_id`
and values are integer PKs. The audit-export consumer reads
this to thread cross-entity rows together without re-joining
through every event's bespoke detail shape.

### Empty-detail case

For events that need no payload (rare but legal, e.g. a
"viewed" event), `detail = None` is correct. Don't write
`detail = {}` — the model column is nullable; `None` is the
canonical "no payload" marker. The migration PR enforces this.

### Worked examples

| Event type | Envelope(s) | Today (sample) | Canonical |
|---|---|---|---|
| `session.created` | `snapshot` + `refs` | `{"session_id": ..., "code": ..., "name": ...}` | `{"session_id": 17, "session_code": "CS101", "snapshot": {…}}` |
| `session.updated` | `changes` | `{"session_id": ..., "code": ..., "changes": {…}}` | `{"session_id": 17, "session_code": "CS101", "changes": {…}}` (already canonical, just adds `session_code`) |
| `session.invalidated` | `reason` (no payload) | `{"session_id": ..., "reason": "..."}` | `{"session_id": 17, "session_code": "CS101", "reason": "setup_mutation"}` |
| `instrument.closed` | `reason` + `refs` | `{"instrument_id": ..., "reason": "..."}` | `{"session_id": 17, "session_code": "CS101", "refs": {"instrument_id": 7}, "reason": "deadline"}` |
| `assignments.generated` | `counts` | `{"mode": ..., "reviewers": N, "reviewees": M, "excluded_counts": {…}}` | `{"session_id": 17, "session_code": "CS101", "counts": {"assignments": 104, "reviewers": 8, "reviewees": 13, **excluded_counts}}` (flatten the excluded counts into `counts`) |
| `responses.saved` | `refs` + `counts` | `{"assignment_id": ..., "field_count": N}` | `{"session_id": 17, "session_code": "CS101", "refs": {"assignment_id": 99}, "counts": {"fields": N}}` |
| `instrument.display_fields_saved` | `set_changes` + `refs` | `{"instrument_id": ..., "added": [...], "removed": [...], "updated": [...]}` | `{"session_id": 17, "session_code": "CS101", "refs": {"instrument_id": 7}, "set_changes": {…}}` |

## Helper API (PR 1)

Type-safe constructors in `app/services/audit.py` that emitters
call instead of building dicts by hand:

```python
def write_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    actor_user_id: int | None = None,
    session: ReviewSession | None = None,   # NEW: superseding session_id
    severity: str = "info",
    payload: AuditPayload | None = None,    # NEW: typed envelope
    reason: str | None = None,
    refs: dict[str, int] | None = None,
    correlation_id: str | None = None,
) -> AuditEvent: ...
```

Emitters compose their detail via:

```python
from app.services import audit

audit.write_event(
    db,
    event_type="session.updated",
    summary=f"Session {session.code} updated",
    actor_user_id=user.id,
    session=session,
    payload=audit.changes({
        "name": [old.name, new.name],
        "deadline": [old.deadline, new.deadline],
    }),
    correlation_id=correlation_id,
)
```

Helper signatures:

```python
def changes(d: dict[str, list[Any]]) -> ChangesPayload: ...
def snapshot(d: dict[str, Any]) -> SnapshotPayload: ...
def counts(**kw: int) -> CountsPayload: ...
def set_changes(*, added=(), removed=(), updated=()) -> SetChangesPayload: ...
```

Each helper returns a small dataclass that knows how to render
itself into the `detail` JSON shape. `write_event` packs
identity context (`session_id`, `session_code` from the passed
`session` row) + the payload's `to_dict()` + `reason` / `refs`
into one dict and writes it.

The signature stays back-compat: passing `detail=` directly is
still legal during the migration window — it bypasses the
helpers and writes whatever the caller passes. PR 7's
validation gate later enforces the canonical shape, which
catches lingering raw `detail=` callsites.

## Proposed PR sequence

### PR 1 — Spec + helpers + session-lifecycle migration

**Goal.** Spec is in place and one family demonstrates the
shape end-to-end.

- New section in `spec/architecture.md` documenting the
  envelopes, identity slots, orthogonal slots, and the
  empty-detail case. Worked examples mirror the table above.
- New code in `app/services/audit.py`: `AuditPayload`
  base + `ChangesPayload` / `SnapshotPayload` / `CountsPayload`
  / `SetChangesPayload` dataclasses + the four constructor
  helpers. `write_event` accepts the new `session=` /
  `payload=` / `reason=` / `refs=` kwargs. Old `detail=`
  kwarg stays callable for the migration window with a
  `DeprecationWarning` in test mode (not in production —
  warnings in audit emitters would be too noisy).
- Migrate every `session_lifecycle.py` emitter
  (`session.validated` / `.invalidated` / `.activated` /
  `.reverted_to_draft` / `instrument.opened` /
  `instrument.closed`) plus `sessions.py`'s
  `session.created` / `.updated` / `.deleted`.
- Update the affected unit tests' expected `detail` shapes.
  Existing `test_*_audit*.py` files give a known scope.
- `docs/status.md` "Audit log" section gains a one-line
  pointer to the new spec section and notes the migration
  cutover date.
- Tests:
  - Each migrated emitter writes a row whose `detail` shape
    matches the worked-example table.
  - `audit.changes(...)`, `audit.snapshot(...)`,
    `audit.counts(...)`, `audit.set_changes(...)` produce
    the right dicts in isolation (unit tests on the helpers
    themselves).
  - Old `detail=` kwarg path still works (one regression
    test that confirms back-compat).

### PRs 2-6 — Migrate remaining families (one PR each)

Same shape per PR: rewrite emitters in one service module,
update the family's tests, ship. No spec changes after PR 1.

| PR | Family | Files touched | Events migrated |
|---|---|---|---|
| **PR 2** | Instruments | `app/services/instruments.py` | `instrument.field_added` / `.field_updated` / `.field_deleted` / `instrument.display_fields_saved` / `instrument.response_fields_saved` (+ any RTD events) |
| **PR 3** | Invitations | `app/services/invitations.py` | `invitations.generated` / `invitation.regenerated` / `invitation.sent` / `invitation.opened` / `reminders.sent` |
| **PR 4** | Responses | `app/services/responses.py` | `responses.saved` / `.submitted` / `.cleared` / `.deleted_all` |
| **PR 5** | Assignments | `app/services/assignments.py` | `assignments.generated` / `.deleted_all` (folds the historical `excluded_counts` into the `counts` envelope) |
| **PR 6** | CSV imports + operator settings | `app/services/csv_imports.py`, `app/services/operator_settings.py` | `reviewers.imported` / `.deleted_all`, `reviewees.imported` / `.deleted_all`, `instruments.bulk_visibility_when_closed`, `operator_email_settings.updated` / `.cleared` |

Each PR is small (typically 5-15 emitters in one file),
independently shippable, and self-contained for review.

PRs 2-6 can land in parallel **only if PR 1 has shipped** —
they don't conflict with each other on the migration paths
(each owns its own service module). They also don't conflict
with the forward-looking emitter sites in 11C / 11F / 11G /
11J / 12A: those new emitters can be written in canonical
shape from day one as long as PR 1 is live.

### PR 7 — Pydantic validation on write

**Goal.** Catch drift back into the old idiosyncratic shapes.

- Per-event-type Pydantic discriminator. Each event type maps
  to a model that asserts the detail matches one of the
  canonical envelope shapes plus the right combination of
  orthogonal slots.
- `audit.write_event` validates `detail` before writing.
  Failures raise `AuditDetailValidationError` (a new
  `ValueError` subclass) with the offending event_type and
  the validation error.
- **Test-mode strict, production lenient.** In tests
  (`pytest`), validation failures bubble up and fail the
  test. In production, validation failures log a structured
  warning and allow the write to proceed — auditing is
  observability, and dropping audit events because of a
  shape bug would hide the very mutations we're auditing.
  This split is set via a `settings.audit_strict_mode: bool`
  Pydantic-settings flag, default `False`, flipped to `True`
  in `tests/conftest.py`.
- Tests:
  - Strict-mode fails-loud on a deliberate shape violation.
  - Lenient-mode logs and writes the row anyway.
  - Every event_type the codebase emits today has a
    Pydantic model registered (test iterates over a
    fixture list of known event types, asserts a model is
    registered for each).

## Implementation pointers

- **Don't rewrite history.** Old `audit_events` rows keep
  their old shapes. The spec section in `architecture.md`
  carries a "Cutover" note: "rows written before
  {YYYY-MM-DD} use legacy shapes; see git history for the
  pre-canonical schemas." A cheap `migration_marker` row
  (a single `event_type="audit.schema_v1"` row written by
  the PR 1 migration) makes the cutover boundary
  searchable in the audit log itself.
- **Keep `event_type` strings stable.** This segment changes
  the *shape* of `detail`; it never changes existing
  `event_type` strings or summaries. Renaming events is its
  own follow-on (catalog item in `unfinished_business.md`
  if it ever becomes useful).
- **Per-family PR scope.** Don't bundle two families into one
  PR. Even though the migration is mechanical, each family
  has its own test fixture set and its own audit-readers
  in tests; one-family-per-PR keeps blast radius small.
- **No new spec doc.** This guide doubles as the migration
  plan; the canonical-shape spec lives in
  `spec/architecture.md`'s new section, where the architecture
  for the audit log already sits.
- **No new model column.** `AuditEvent.detail` stays
  `Mapped[dict | None]` over `JSON`. Per-event-type
  discriminator is enforced at write time, not by the
  database — Postgres JSON validation is too coarse for
  this use case and fragments the spec across two places
  (column constraint + Python schema).

## Out of scope (cross-references)

- **Rewriting historical rows** to the new shape. Append-only
  log, never rewritten.
- **Renaming `event_type` strings.** Out — pure rename is its
  own follow-on if needed.
- **Audit-export CSV / retention policy.** Segment 12. 11K is
  the schema; Segment 12 is the consumer + the retention
  rules.
- **Audit log UI / browser.** Out — there's no operator-facing
  audit-browser today, and 11K doesn't add one. If a future
  segment ships one, the canonical shape makes the column
  model trivial.
- **Cross-session audit views.** Out — depends on Segment 12's
  export aggregation. The `session_code` slot makes it cheap
  later.
- **Correlation-ID conventions.** Already pinned for
  invitation and reminder send paths via Segment 11A's
  thread-`correlation_id`-into-deadline-lazy-close work
  (`unfinished_business.md` §10, shipped). 11K leaves
  `correlation_id` semantics unchanged; the column lives on
  `AuditEvent` directly, not in `detail`.

## Test impact

- Existing audit-tests (mostly `tests/integration/test_*_audit.py`)
  update to expect the canonical shape per family. Each
  migration PR carries its own test churn — one file's worth
  per PR.
- New `tests/unit/test_audit_helpers.py` covering the four
  helper constructors and `write_event`'s new kwargs.
- New `tests/unit/test_audit_detail_schema.py` (lands in PR
  7) covering the Pydantic discriminator: every emitted
  `event_type` has a registered model, and roundtripping
  each model through JSON is byte-stable.

## Doc impact

- `spec/architecture.md` — new "Audit-event detail schema"
  section under the existing audit-log discussion. Contains
  the full canonical-shape reference, worked examples, and
  the cutover-date note.
- `docs/status.md` "Audit log" — retire the inline
  reconciliation paragraph and replace with a one-line
  pointer to the new spec section.
- `guide/unfinished_business.md` §5 — strikethrough closure
  once PR 7 ships, naming the merge PRs.
- `guide/todo_master.md` — move 11K from **Upcoming** to
  **Done** once PR 7 ships; cross-reference Segment 12
  (which can now begin).
- `guide/archive/segment_11C_operations_consolidation.md`,
  `guide/segment_11F_previews_page.md`,
  `guide/archive/segment_11G_validate_page.md`,
  `guide/archive/segment_11J_quick_setup_card.md`,
  `guide/segment_12A.md` — each plan has emitter scope that
  inherits the canonical shape automatically once PR 1 lands.
  No edits to those plans required; the canonical shape
  becomes the default they pick up at implementation time.
- No new spec doc — the convention lives in `architecture.md`
  alongside the rest of the audit-log architecture.
