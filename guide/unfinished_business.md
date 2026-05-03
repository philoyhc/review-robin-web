# Unfinished business

**Role.** Rolling todo of cross-cutting cleanups carried over
from earlier segments — the unfinished items needed to stabilize
the operator model and engine before new feature segments build
fresh surface on top. Items are not gated to a single segment;
when one ships, tick it and move on. New cleanups identified
during later segments land here too.

This file replaces the former `guide/adhoc_todo.md` (originally
captured during the mid-Segment-10B health review on 2026-04-30)
and the short-lived `guide/archive/segment_10D.md` framing. Items are
ordered by priority given the project's actual workflow: **no
local Python or database; the agent's sandbox is the pre-PR
gate; end-to-end verification happens on the Azure dev slot
after deploy.** That workflow makes CI gaps and hard-to-test
invariants more expensive than they would be on a project with a
human dev loop.

When picking up an item: read its "Why" and "Plan" sections,
confirm the file pointers still match `main`, and land it on its
own branch. Don't bundle multiple items into one PR — the cut
points below are the natural slice sizes. Tick items as they
ship; update `docs/status.md`'s segments-shipped table when the
shipping segment lands.

---

## P1 — CI gaps (no local dev loop magnifies these)

### 1. ~~Wire `ruff check` into CI~~ — ✅ shipped 2026-05-02 · [CI] · small

**Resolution (2026-05-02).** `.github/workflows/ci.yml` now runs
`ruff check .` between dependency install and `pytest`. Lint
failures abort before the slower test job. The 10 pre-existing
findings (8 unused imports across 6 test files + 2 unused locals
in `tests/db/test_models.py:57` and
`tests/integration/test_display_field_routes.py:458`) were
cleaned up in the same PR — auto-fix on the imports, hand-edit
on the locals.

---

### 2. Run pytest against Postgres in CI · [CI] · medium · ✅ shipped 2026-05-02

**Outcome.** The renamed `ci-postgres.yml` workflow (was
`ci-postgres-migration.yml`) now runs `pytest -q` against the
`postgres:16` service container after the Alembic round-trip, on every
PR. The `engine` fixture in `tests/conftest.py` honours
`TEST_DATABASE_URL` / `DATABASE_URL` (default still in-memory SQLite),
drops + recreates `public` before applying migrations on Postgres so
the schema starts clean, and skips the SQLite-only `PRAGMA foreign_keys`
event listener when it sees a Postgres URL. CLAUDE.md / AGENTS.md /
docs/status.md / docs/database.md updated to match.

**Notes / gotchas for future work.**
- The catalog's pre-ship hint that `tests/conftest.py` already honoured
  `DATABASE_URL` was wrong; the fixture had hard-coded
  `sqlite+pysqlite:///:memory:`. Verify-before-assume kicked in.
- `committed_engine` in `tests/integration/conftest.py` was
  deliberately *not* migrated to Postgres. Its purpose is
  commit-vs-rollback semantics (catching routes that forget to
  `db.commit()`), which is dialect-independent — making it
  Postgres-aware would require per-test DB / schema cleanup for no
  added coverage. Only 8 tests use it; they continue to run on
  SQLite even in the Postgres CI job, and that's fine.
- The full 405-test suite passed against Postgres on first try — no
  JSON-coercion / tz-equality / row-ordering divergence surfaced.
  Future Postgres-only failures should be fixed at the root cause
  (add `ORDER BY`, normalise tz at the boundary), not by skipping the
  test.

---

## P2 — Architectural debt to land before Segment 12 (export / audit retention)

### 3. Move `_invalidate_if_validated` policy out of routes · [arch] · medium · ✅ shipped 2026-05-02

**Outcome.** The `validated → draft` invariant now lives at the
service boundary. New public helper
`app/services/session_lifecycle.py::invalidate_if_validated(db, *,
review_session, user, reason, correlation_id=None)` is idempotent
(no-op on draft / ready / etc.) and is called at the top of every
setup-mutating service:

- `csv_imports._save` / `_delete_all` (covers reviewer + reviewee
  imports + delete-all)
- `assignments.replace_assignments` / `delete_all_assignments`
- `sessions.update_session`
- `instruments.create_instrument` / `delete_instrument` /
  `update_instrument_description` / `add_response_field` /
  `add_default_response_field` / `update_response_field` /
  `delete_response_field` / `move_response_field` /
  `bulk_save_fields` / `add_display_field` /
  `update_display_field` / `delete_display_field` /
  `move_display_field` / `add_response_type_definition` /
  `update_response_type_definition` /
  `delete_response_type_definition`

Routes no longer thread the rule. The 23 explicit
`_invalidate_if_validated` calls in `routes_operator.py` and the
route helper at `:789` are gone.

Tests: new
`tests/integration/test_invalidation_on_setup_mutation.py` (13
tests) covers the helper's idempotency, one mutating-service
example per category, and the two visibility-services exemption
(item #16 — see below).

**Notes / follow-ups.**
- The instruments-service mutations don't thread `correlation_id`
  through to `invalidate_if_validated` (their existing audit
  events also don't carry it). The `session.invalidated` audit
  event raised from those mutations therefore has a NULL
  correlation_id. That's a small audit-trace regression, not
  worth threading the param through 14 instruments_service
  signatures. If correlation_id continuity becomes important for
  trace-on-export work in Segment 12, fix it then.
- The `mutate_setup` decorator alternative was considered and
  rejected — services have wildly different signatures
  (`instrument`, `field`, `rtd`, `review_session`), so a
  single-shape decorator would have been awkward.

---

### 4. Extract a single reviewer-session-state helper · [arch] · small · ✅ shipped 2026-05-02

**Outcome.** New public helper
`app/services/responses.py::reviewer_session_state(db, *, reviewer,
session_id) -> ReviewerSessionState` walks `assignments → fields →
responses` once and returns
`(total_assignments, completed_count, missing_required_count,
pill_state)`. `session_pill_for_reviewer` is now a thin projection.
`monitoring._reviewer_completion` deleted; `per_reviewer_progress`
calls the new helper once per reviewer (was calling
`_reviewer_completion` *and* `session_pill_for_reviewer` per
reviewer, walking the same data twice). 5 new unit tests
(`test_responses_service.py::test_reviewer_session_state_*`) cover
the 4 pill states + projection equivalence.

**Notes / gotchas surfaced during the refactor.**
- The catalog's pre-ship claim that "both functions now route
  through the same `_reviewer_assignments()` filter" was wrong —
  `monitoring._reviewer_completion` was inlining its own
  `select(Assignment).where(...)` query without the
  `.order_by(Assignment.id)` from the shared filter. Verify-before-
  assume saved a debugging cycle. The new helper centralises the
  filter call, so a future caller can't drift.
- Segment 12 export's "incomplete at deadline" cohort can now
  consume `reviewer_session_state` directly; no third walker
  needed.

---

### 5. Define an audit-event `detail` schema convention · [arch] · medium

**Why now.** Every audit-writing service invents its own `detail`
JSON shape:
- `instrument.field_added` — flat snapshot of every column.
- `instrument.field_updated` — `{"changes": {key: [old, new]}}`.
- `assignments.generated` — `excluded_counts: {...}` map.
- `responses.deleted_all` — `{"deleted_count": N}`.
- `instrument.display_fields_saved` — D11 diff with `added` /
  `removed` / `updated` keys.

`docs/status.md`'s "Audit log" section is the only place these are
reconciled. Segment 12 is "export / audit retention" — the export
consumer will need a stable schema, and defining it after the fact
means rewriting every emitter.

**Where.** All `_write_audit` / `record_audit_event` callsites:
`grep -n "audit_event\|record_audit\|_write_audit" app/services/`.

**Plan.**
- Pick a small set of conventions and document them in
  `spec/architecture.md`:
  - Snapshots go under a `"snapshot"` key.
  - Per-key diffs go under a `"changes": {key: [old, new]}` key.
  - Counts go under named integer keys (`deleted_count`,
    `cascaded_assignment_count`, etc).
  - Generic exclusion maps stay as `excluded_counts: {...}`.
- Migrate emitters incrementally; each migration is one PR. Don't
  rewrite history — old rows keep their old shape; document that.
- Optionally introduce a Pydantic schema per event_type and validate
  on write, so drift is caught at test time.

---

## P3 — Architectural debt to land before Segment 15 (real SMTP)

### 6. Decouple `app/services/invitations.py` from `Request` · [arch] · small

**Why now.** `send_invitation`, `send_reminder`, and
`send_reminders_to_incomplete` take `request: Request` (lines 198,
408, 472) so they can call
`request.url_for("reviewer_invite", ...)` (line 44). Segment 15
likely runs sends from a background worker / scheduler with no live
request. Worth fixing while the surface is small.

**Where.** `app/services/invitations.py:44, 198, 408, 472`.

**Plan.**
- Take a `build_invite_url: Callable[[str], str]` (or a `base_url:
  str`) instead of `Request`.
- Routes pass `request.url_for` closed over the route name.
- Tests build a trivial lambda. Eliminates the `TestClient`-driven
  request fixture pattern in invitation tests.

---

## P4 — Decisions to write down

### 7. Make a deliberate CSRF decision · [doc] · small

**Why now.** `app/main.py` mounts no CSRF middleware; templates have
no token. Easy Auth gives authentication, not CSRF protection. A
logged-in operator's browser is theoretically inducible to POST
`/operator/sessions/{id}/delete` from another origin. Whether that's
acceptable depends on threat model — but it should be an explicit
decision, not an oversight. With no local dev loop, this is the kind
of invariant that's easy to forget exists.

**Where.** `docs/authentication.md`.

**Plan.**
- Decide: rely on Easy Auth + SameSite cookies, or add CSRF tokens.
- Write the decision into `docs/authentication.md` with one
  paragraph of rationale. If the decision is "rely on SameSite",
  verify the cookie attributes Easy Auth sets and document them.
- If the decision is "add tokens", that becomes its own segment of
  work — slot it explicitly.

---

## P5 — Small cleanups

### 8. Fix CSV email-validation drift · [bug] · tiny

**Why now.** `app/services/csv_imports.py:99` and `:189` are
near-duplicates. Reviewer email is regex-validated; reviewee email
is only `@`-checked. A reviewee with a malformed-but-`@`-containing
address (`"foo@"`, `"@bar"`) imports cleanly today and dies later
on send.

**Where.** `app/services/csv_imports.py`, `parse_reviewer_csv` (~99)
vs `parse_reviewee_csv` (~189).

**Plan.**
- Extract a shared `_parse_email(value) -> str | ValidationIssue`
  helper. Use it from both paths.
- Add a regression test in
  `tests/unit/test_csv_imports.py` covering the malformed-reviewee
  case.

---

### 9. Refresh rotted docstring on `get_or_create_default_instrument`
· [doc] · tiny

**Why now.** `app/services/assignments.py:402` calls itself a
"backwards-compatible wrapper", but it's the live path called from
`replace_assignments`. The rotted comment will mislead the next
person reading the assignments service.

**Plan.**
- Replace the docstring with what the function actually does today.
- Either drop the inline reference to `app.services.instruments`
  being "the canonical helper", or genuinely deprecate this function
  with a `warnings.warn(...)` and a removal target.

---

### 10. Thread `correlation_id` into deadline lazy-close · [obs] · small

**Why now.** `app/services/session_lifecycle.py::observe_deadline`
emits `instrument.closed reason=deadline` audit events with
`actor_user_id=None` and no `correlation_id`. With no local dev
loop, debugging "which reviewer's GET tripped the close?" needs the
audit row to carry the request's correlation id. Cheap to add now.

**Where.** `app/services/session_lifecycle.py::observe_deadline`
(grep for the function definition and its callers in
`app/web/routes_reviewer.py` and `app/web/routes_operator.py`).

**Plan.**
- Accept an optional `correlation_id: str | None` parameter.
- Thread it through from each calling route handler. The middleware
  / dependency that mints `correlation_id` per request already
  exists; just pass it down.
- Update the audit-emission site to include it in `detail`.

---

### 11. Extract instruments-index template context to `views.py` · [refactor] · small · ✅ shipped 2026-05-02

**Outcome.** New `build_instruments_context()` in
`app/web/views.py` (next to `build_setup_rows` /
`session_status_pills`). Owns:
- Five idempotent per-request backfills
  (`ensure_locked_display_fields`,
  `prune_unpopulated_display_fields`,
  `seed_display_fields_from_reviewees`,
  `seed_display_fields_from_assignments`,
  `ensure_default_response_type_definitions`) plus the
  `db.commit()` that lands them.
- Editing-state machine (`is_ready` / `editing_instrument_id` /
  `effective_editing_rtd_id` mutual-exclusion).
- Bulk Accepting / Visibility three-state derivation (factored
  into a private `_bulk_state(values)` helper since the two were
  mechanical duplicates).
- URL-driven `rtd_delete_blocked` and `rtd_would_empty` query-param
  packaging.

The route handler shrank from 140 lines → 46 lines (query-param
declarations + `lifecycle.observe_deadline` + 1 view call +
render).

**Notes / catalog corrections surfaced during the refactor.**
- The catalog claim "the same shaping will be reused by the
  preview route" was stale — the preview route uses
  `routes_reviewer.build_preview_context`, a different view
  function shaping the reviewer surface. Motivation reduced to
  "thin the route" per the CLAUDE.md services/routes/views
  split.
- The catalog's "~48 lines" figure was a low estimate; the
  pre-refactor handler was 140 lines (including 14 query params
  + ~70 lines of context shaping + a 50-line return dict). The
  refactor still cuts most of the substance.
- `_bulk_accepting_state` and `_bulk_visibility_state` were
  mechanical duplicates of the same three-state pattern;
  collapsed into one `_bulk_state(values: list[bool])` helper
  inside `views.py`.

---

### 12. Reviewer/Reviewee CSV cross-table identity check · [bug] · small

**Why now.** Carried over from
`guide/archive/segment_10_instrument_builder_mvp_plan.md` §15 as a
deferred follow-up. The upload validators in
`app/services/csv_imports.py` treat reviewers and reviewees as
independent tables; a person who appears in both with the same
email but different names imports cleanly today and surfaces as a
mismatch downstream (assignment-context joins, monitoring email
lookups). Tightening the rules now — while the validator surface
is small — costs less than retrofitting after Segment 12's
export consumes the data.

**Where.** `app/services/csv_imports.py` — `parse_reviewer_csv`
(~99) and `parse_reviewee_csv` (~189). Adjacent to item 8 (email
validation drift) and naturally lands as the next slice on top
of it.

**Plan.** Tighten the validators so that **email is the unique
person-identifier across both reviewer and reviewee tables in
the same session**, while name is treated purely as the
human-facing label. Rules to enforce on upload:

- Every row must have non-empty Name and Email (already
  enforced).
- Within the uploaded CSV, the same email may not appear with
  different names → error. (Same email + same name still
  collapses to a duplicate-row error as today.)
- **Cross-table:** when uploading reviewers, look up each row's
  email in the existing reviewees of the same session — if found
  with a *different* name, error. Same name = allow (the person
  is both reviewer and reviewee, common in peer review). Vice
  versa for reviewee uploads.
- The same name may appear with multiple distinct emails — no
  uniqueness on name.

Out of scope here but adjacent: assignments-CSV emails imply a
person; same cross-table consistency could be checked there in a
later pass.

New tests cover the four cases (intra-CSV same name + same
email, intra-CSV same email + different name, cross-table same
email + same name, cross-table same email + different name).

---

## P0 — Instruments UI ↔ data drift (added 2026-05-01)

A round-3 audit found that the operator's per-instrument
**Display Fields** card and the underlying schema have drifted
apart in 5+ ways. Items 13–14 are the user-facing fixes; item 18
is the related multi-instrument-button decision. See `docs/status.md`
audit-table + `spec/operator_map.md` "Instruments" for the
contracts these items are correcting.

### 13. ~~Fix the Display Fields placeholder (no-persistence + bad sources)~~ ✅ shipped 2026-05-01 · [bug] · small

**Why now.** Two confirmed mismatches between
`app/web/templates/operator/instruments_index.html:227–286` (the
Display Fields placeholder card) and the schema:

- **Mismatch 1**: the operator UI lists rows for `RevieweeName`,
  `RevieweeEmail`, `PhotoLink`, `RevieweeTag1/2/3`, but
  `_VALID_DISPLAY_SOURCES` (`app/services/instruments.py:61–63`)
  only allows `(reviewee, tag_1/2/3 | profile_link)` and
  `(pair_context, 1/2/3)` — there is no `(reviewee, name)` /
  `(reviewee, email)` source. Even if the form POSTed, the
  server would `raise DisplaySourceError`.
- **Mismatch 6**: `lockFields(btn)` (line 544) is JS-only — no
  `fetch()`, no form submit. Friendly-Label edits, the Visible
  checkbox, and the Order column on the Display Fields placeholder
  **persist nothing**. The operator types a label, ticks Save,
  navigates away and back — it's gone. (The Response Fields side
  *does* persist via per-row hidden forms; this is Display Fields
  only.)

User-visible symptom: data-loss-by-illusion. **Risk: high.**

**Plan.** Pick one of:

1. **Label honestly as preview-only** (~30 min). Replace the
   `<details class="display-edit">` interaction with a static
   row, add a "Preview only — display-field persistence ships in
   [next slice]" banner above the card, and remove the Visible
   checkbox from the placeholder rows. The hardcoded 6-row list
   stays as a teaser of what the configurable surface will look
   like. Use this if Display Fields wiring is going to slip
   beyond Segment 12.
2. **Wire to existing routes** (~half day, the right long-term
   move). Extend `_VALID_DISPLAY_SOURCES` and
   `_DEFAULT_DISPLAY_LABELS` (`app/services/instruments.py:47–63`)
   with `(reviewee, name)` and `(reviewee, email_or_identifier)`;
   extend `display_field_value` to resolve them; either delete
   the hardcoded `Reviewee` column from
   `review_surface.html:108–111` or keep it and document that the
   display-field rows for those sources are no-ops on the
   reviewer side. POST every row through the existing
   `/display-fields/{df_id}/edit` and
   `/display-fields/{df_id}/delete` endpoints (already in
   `routes_operator.py`). Adds a `_CSV_COL_TO_SOURCE` mapping
   (e.g. `RevieweeTag1 → ("reviewee", "tag_1")`) — the operator
   UI vocabulary uses CSV column names, the schema uses tuples.

Recommend **option 1 first**, with option 2 scheduled into
Segment 12 or its own 10x slice.

---

### 14. ~~Drop the `pair_context_*` default seed; seed display fields from import data~~ ✅ shipped 2026-05-01 · [bug] · medium

**Why now.** This is the headline data fix.
`ensure_default_instrument` (`app/services/instruments.py:185–197`)
seeds three `InstrumentDisplayField` rows for `pair_context.1/2/3`
on every new session, with `visible=True`. But:

- **Mismatch 5**: `pair_context_*` lives on `Assignment.context`,
  populated *only* by manual assignments CSV. For sessions that
  use full-matrix assignments (the common case), no pair context
  exists — so the reviewer surface renders three blank
  `Pair Context` columns and zero tag columns, even when the
  reviewees CSV has tag data.
- **Mismatch 4**: `parse_reviewee_csv`
  (`app/services/csv_imports.py:271–273`) imports `tag_1/2/3`
  into reviewee rows, but `ensure_default_instrument` does not
  create display fields for them. Tag data lands in the DB and
  is invisible to reviewers unless the operator hand-uses the
  legacy `POST /display-fields` route, which the new template
  doesn't expose.
- **Mismatch 2**: even when pair_context data *is* present, the
  operator can't deselect the seeded columns from the UI (item 13
  blocks that path), so the seed becomes sticky regardless of
  whether it's helpful.

User-visible symptom: reviewer sees `[blank][blank][blank]`
instead of `[Group A][Senior][Track 1]`. The "Display Fields"
feature is silently broken for the most common session shape.
**Risk: high.**

**Where.**
- `app/services/instruments.py::ensure_default_instrument`
  (`_DEFAULT_DISPLAY_FIELDS` constant + the seed loop).
- `app/services/csv_imports.py` — reviewee-import path.
- `app/services/assignments.py` — manual-assignment-import path.

**Plan.**
1. Drop `_DEFAULT_DISPLAY_FIELDS`. `ensure_default_instrument`
   creates no display rows at instrument creation time.
2. After a successful reviewee CSV import, idempotently create
   `InstrumentDisplayField` rows for any `tag_N` /
   `profile_link` slot with at least one populated value
   (across the imported reviewees). Use the existing
   `display_source_presence` helper as the source of truth for
   "populated."
3. After a successful manual-assignment CSV import, idempotently
   create `InstrumentDisplayField` rows for any `pair_context_N`
   slot with at least one populated value.
4. Migration: a one-shot patch that, for every existing
   instrument, drops `pair_context_*` rows where the slot is
   unpopulated across that session's assignments. (Deliberately
   destructive within that filter; pair_context labels typed by
   the operator are preserved when slot has data.)
5. Update `spec/architecture.md` "Pair-level vs assignment-level
   context" to reflect the lazy seeding.
6. New tests:
   - Full-matrix session with tag-rich reviewees: reviewer
     surface shows tag columns, no pair-context columns.
   - Manual-assignment session with pair-context CSV: reviewer
     surface shows pair-context columns.
   - Re-import of reviewees doesn't double-seed display fields.
   - Migration round-trip on a session with stale pair_context
     seeds drops them.

**Order:** lands after item 13 (so the operator surface stops
showing the wrong sources before the seed semantics change
underneath it).

---

## P0/P1 — Other findings from the round-3 audit

### 15. ~~Backfill integration tests for shipped 10C functionality~~ — ✅ closed 2026-05-02 · [test] · tiny

**Resolution (2026-05-02).** All four originally-listed surfaces
are now covered:

- ✅ `delete_instrument` — Slice 5
  ([`tests/integration/test_segment_10d_slice_5.py`](../tests/integration/test_segment_10d_slice_5.py)).
- ✅ `bulk_set_visibility` + `instruments.bulk_visibility_when_closed`
  audit event — covered in
  [`tests/integration/test_bulk_visibility.py`](../tests/integration/test_bulk_visibility.py)
  (4 cases: all-on flips mixed state + audit, symmetric all-off,
  idempotency no-op, locked-in "deliberately doesn't invalidate
  `validated`" assertion that will fail loudly when item #16
  ships).
- ✅ `add_default_response_field` — covered by
  [`tests/integration/test_route_persistence.py:272`](../tests/integration/test_route_persistence.py)
  + 5 unit tests in
  [`tests/unit/test_response_type_definitions.py:584-686`](../tests/unit/test_response_type_definitions.py).
- ✅ "Cannot delete the last instrument" 400 guard — Slice 5.

(Original framing preserved below for archaeology.)



**Why now.** Of four 10C-shipped surfaces originally listed as
having no integration test coverage, three are now covered by
work that landed during Segment 10D (re-audited 2026-05-02):

- ✅ `delete_instrument` (route + service + cascade) — covered by
  Slice 5 in `tests/integration/test_segment_10d_slice_5.py` (5
  cases: cascade + repack, last-instrument 400, validated→draft
  invalidation, cross-session 404, ready-state 409).
- ❌ **`bulk_set_visibility`** (`/instruments/visibility/all-on`
  and `/all-off`) and the `instruments.bulk_visibility_when_closed`
  audit event — **still uncovered**.
- ✅ `add_default_response_field` (`/fields/add-row`) — covered
  by `tests/integration/test_route_persistence.py:272`
  (route persistence) plus 5 unit tests in
  `tests/unit/test_response_type_definitions.py:584-686` (Slice
  4c coverage: default args, `rtd_id` wiring, default-RTD
  fallback, blank-label auto-rating key, field_key collision
  handling).
- ✅ "Cannot delete the last instrument" 400 guard — covered by
  Slice 5 (`test_delete_instrument_refuses_last_instrument`).

The upcoming arch refactors (items 3, 11) will touch the
remaining `bulk_set_visibility` route; without tests, regressions
ship silently.

**Plan.** Single small PR adding 3-4 cases for `bulk_set_visibility`:

- Happy path — mixed initial state → `POST /visibility/all-on`
  flips both instruments' `responses_visible_when_closed` to
  True; `instruments.bulk_visibility_when_closed` audit event
  fires with `target=True` and the right `changed_instrument_ids`.
- Symmetric all-off — start all-on → `/all-off` flips back; audit
  event with `target=False`.
- Idempotency — start already-on → `/all-on` writes no audit row
  (the service only emits when `changed` is non-empty).
- (Optional) lock in current "deliberately doesn't invalidate
  `validated → draft`" behaviour as a coupled assertion. When
  item #16 ships and changes the policy, the test fails loudly,
  forcing an explicit decision rather than silent change.

---

### 16. Decide bulk_visibility_when_closed invalidation policy · [arch] · tiny · ✅ shipped 2026-05-02

**Decision.** Visibility-when-closed is **deliberately exempt**
from the `validated → draft` rule — it's a display flag (does
the reviewer see other reviewers' responses after the deadline)
that doesn't change anything captured in the validation snapshot
(assignments, fields, instruments). `docs/status.md:216` had
already documented this; #3's service-layer migration is where
the policy was formally pinned.

Pinned in code at:
- `app/services/instruments.py::bulk_set_visibility` —
  `# #16` comment + deliberate omission of
  `lifecycle.invalidate_if_validated`.
- `app/services/session_lifecycle.py::set_responses_visible_when_closed`
  — same comment + omission.

Pinned in tests at:
- `tests/integration/test_bulk_visibility.py::test_bulk_visibility_does_not_invalidate_validated_session`
  (existed before; docstring updated since the policy is now
  decided rather than provisional).
- `tests/integration/test_invalidation_on_setup_mutation.py::test_bulk_set_visibility_does_not_invalidate`
  and `::test_set_responses_visible_when_closed_does_not_invalidate`
  (new — co-located with the rest of the service-layer invariant
  tests).

---

### 17. ~~Investigate `Assignment.include` filter divergence~~ — ✅ resolved on re-audit 2026-05-02 · [arch] · small

**Resolution (2026-05-02 re-audit).** The cited divergence is
gone. `monitoring._reviewer_completion`
(`app/services/monitoring.py:76`) filters
`Assignment.include.is_(True)`; `responses.session_pill_for_reviewer`
calls `_reviewer_assignments()` at `app/services/responses.py:439`,
which **also** filters `Assignment.include.is_(True)` (same
helper, line 54). Both paths now apply the same inclusion rule.

This unblocks item #4 — consolidating the two functions into a
single helper no longer requires an investigation step first.

(The original concern below remains preserved for archaeology;
historical context for why item #4 was previously sequenced
behind this one.)

**Original framing.** `monitoring._reviewer_completion`
(`app/services/monitoring.py:76`) filters assignments with
`Assignment.include.is_(True)`. `responses.session_pill_for_reviewer`
(`app/services/responses.py:439`) does **not** filter on `include`.
This is the exact drift item 4 (extract a single
reviewer-session-state helper) is meant to catch — but verify
which filter is correct *before* consolidating, or item 4 will
ship the wrong unified rule.

---

### 18. ~~Decide fate of disabled "Add an instrument" button vs live route~~ — ✅ shipped 2026-05-02 as Slice 5 of Segment 10D · [decision] · tiny

**Decision (2026-05-02):** **Enable** the button with a confirm
step. The schema, services, and cascade behaviour are ready
(Segment 10C); Slice 5 of Segment 10D is the implementation
slice — flip the button live, add the JS confirm dialog, and
land the segment-close updates to `docs/status.md`.

**Shipped (2026-05-02):** Both `Add new instrument` and `Delete
this instrument` are now wired through their existing POST routes
(`/instruments/add`, `/instruments/{iid}/delete`). Native
`confirm()` fires on Delete; Add submits directly (it's
reversible). Both buttons share an `is_ready` /
`is_some_instrument_editing` / `is_some_rtd_unlocked` disable gate
matching the per-instrument Edit button; Delete additionally
disables itself when the session has only one instrument.
Integration coverage in
[`tests/integration/test_segment_10d_slice_5.py`](../tests/integration/test_segment_10d_slice_5.py).

**Why now.** `instruments_index.html` ships a
`disabled` Add-an-instrument button with tooltip
"Multi-instrument support is still in progress"; meanwhile
`routes_operator.py` defines a working `POST /instruments/add`
endpoint and `delete_instrument` is wired and tested-via-cascade.
The Slice-4 ladder (RTD card, ODT cascade-delete UX,
mutual-exclusion edit lock, banner conventions) is now shipped,
so the per-instrument-card surface is settled enough that
multi-instrument promotion behaviour can be observed without
bumping into other Slice-4 work.

**Plan.** Slice 5 of Segment 10D — see
[`guide/archive/segment_10D.md`](./archive/segment_10D.md) "Slice 5 — Multi-
instrument enable" for the contract. Tick this item when Slice 5
ships and the segment closes.

---

### 19. ~~Roll session-status top card onto Reviewers / Reviewees / Assignments / Instruments~~ — ✅ shipped 2026-05-02 · [chrome] · small

**Resolution (2026-05-02).** Original literal scope shipped:
all four pages (Reviewers, Reviewees, Assignments, Instruments)
now use the new chrome, alongside Session detail and Email
Template. Actual scope grew well beyond the original framing —
the legacy `session_status_card.html` partial was scrapped in
favour of an entirely new chrome system (two-row folder tabs
with double-height Home anchor + status row), spec'd through
[PR #272](https://github.com/philoyhc/review-robin-web/pull/272)
/ [PR #279](https://github.com/philoyhc/review-robin-web/pull/279)
/ [PR #286](https://github.com/philoyhc/review-robin-web/pull/286)
and implemented through PRs #280–#290. Live on all six
session-scoped pages with the chrome.

Two follow-on items spun off from this work and are tracked
separately: #20 (chrome rollout to the remaining Operations
Pages + Home sub-pages) and #22 (Home body rebuild + Option F
relocation of parked sub-cards).

(Original framing preserved below for archaeology.)

**Why now.** PR
[#252](https://github.com/philoyhc/review-robin-web/pull/252)
shipped the shared
`operator/partials/session_status_card.html` partial — three
rows of pills (reviewer / reviewee / assignment counts;
instrument count + Email Invites Set up / Not set up; setup-nav)
— and rolled it onto Session detail and Email Invites. The
remaining four session-scoped operator pages (Reviewers,
Reviewees, Assignments, Instruments) still hand-roll their own
top cards. Consolidating onto the partial is pure chrome
cleanup but the four pages currently drift in subtle ways
(pill phrasing, layout, what counts they show) — collapsing
them onto the partial settles the visual contract.

**Where.**
- Templates: `app/web/templates/operator/session_reviewers.html`,
  `session_reviewees.html`, `session_assignments.html`,
  `instruments_index.html` (the last one keeps its
  instrument-specific second-row pills + the
  "Actions for All Instruments" card below).
- Routes: each GET handler builds + passes
  `views.session_status_pills(db, session)` to the template.

**Plan.**
- Land per-page so each PR has a small surface area.
- Reviewers / Reviewees / Assignments are straightforward swap-
  outs. Instruments needs more care because its top card has
  two extra instrument-specific status rows (deadline,
  accepting/not, visibility-when-closed) — those stay; the
  partial replaces only the nav row + maybe the count rows.

---

### 20. ~~Complete chrome rollout to remaining session-scoped pages~~ — ✅ Operations Pages shipped 2026-05-02; Home sub-pages deferred · [chrome] · small

**Resolution (2026-05-02).** The three Operations Pages
(Invitations, Monitoring, Outbox) now render the new chrome
with their own tab active. P2 ("both phases always reachable")
holds across the Operations side.

The two Home sub-pages (Edit Session, Validate detail) are
**deferred** — their status, function, and location in the
session-scoped page taxonomy are being rethought as part of the
Home body rebuild (item #22). Adopting the new chrome on those
two pages now would lock in placement decisions that the
rethink might overturn. They'll get the chrome when their fate
settles, as part of #22 or a successor item.

(Original framing preserved below for archaeology.)

**Why now.** The new two-row session top nav (item #19) is live
on Home, the 5 Setup Pages, and Email Template. Per **P2** in
[`spec/ui_concept.md`](./ui_concept.md) (*"both phases always
reachable"*), the chrome should also appear on:

- **The three Operations Pages** (Invitations, Monitoring,
  Outbox) — currently render with no top chrome at all. Each
  should adopt the chrome with its own tab active.
- **The two Home sub-pages** (Edit Session, Validate detail) —
  should adopt the chrome and render with **no tab active** per
  the spec's "Sub-pages and Preview Pages" section.

Until this lands, P2 is partially violated for those five
pages: the chrome is missing on Operations Pages, and Home
sub-pages still carry stale chrome.

**Where.**
- Templates: `session_invitations.html`, `session_monitoring.html`,
  `session_outbox.html`, `session_edit.html`,
  `session_validate.html`.
- Routes: each GET handler needs to thread `status_pills` if it
  doesn't already
  (`grep -n session_status_pills app/web/routes_operator.py`).

**Plan.** Per-page like #19. Adopt the chrome wrapper, drop the
redundant page `<h1>` (active tab carries the title), keep page
body otherwise unchanged. For Operations Pages, pass
`current_page` matching ("Invitations" / "Monitoring" /
"Outbox"). For Home sub-pages, pass `current_page = "Home"` (no
tab active). Tests will need their `<h1>X</h1>` assertions
softened.

---

### 21. UI consistency updates aligning with the new chrome · [chrome] · varied

**Why now.** The new two-row session top nav (item #19) sets a
refined visual baseline — understated tints, soft accents,
modern inset underlines, hover states that lighten rather than
darken. Against that baseline, the rest of the operator
surface now reads as inconsistent in places.

This is the **umbrella item** for follow-on UI cleanups that
align the surface with the new chrome's visual language.
Capture additional sub-tasks here as they surface during
subsequent PRs (e.g. during the Home rebuild in #22) rather
than spinning a new catalog item per cleanup.

**Sub-tasks queued so far:**

1. **Restyle the six canonical button modifiers.** The buttons
   defined in
   [`spec/assumptions.md`](../spec/assumptions.md) (Primary,
   Primary Outline, Alert, Alert Outline, Danger, Danger
   Outline) now read as jarringly contrastive against the
   chrome — saturated solid fills, hard borders, full-strength
   colours throughout. The new chrome's vocabulary is
   understated tints + softer accents + lighten-on-hover.
   Move the canonical buttons to a more understated modern
   look matching the chrome:
   - Lighter / more transparent fills.
   - Less saturated colours (especially on Alert and Danger
     solids — currently shouty oranges and reds).
   - Hover affordances that lighten rather than darken (matches
     the chrome's `.session-home-anchor:hover` and
     `.nav-tab:hover` direction).
   - Smaller / less prominent in default state, with the
     accent only fully visible on hover or active.
   - Update `spec/assumptions.md` with the new visuals once the
     restyle settles on the dev slot.

(Other UI-consistency items will be appended below as they
surface.)

**Where.** `app/web/templates/base.html` (`.btn` / `.btn.secondary` /
`.btn.danger` / `.btn.danger-solid` / `.btn.alert` /
`.btn.alert-solid` rules) plus `spec/assumptions.md`. Visual
review touches every page that uses these buttons (i.e. all of
them).

**Plan.**

- First PR — button restyle. Iterate on dev slot until the
  new visual reads well across the chrome'd pages.
- Second PR — update `spec/assumptions.md` with the settled
  values + rationale.
- Subsequent PRs — fold in any other UI inconsistencies that
  surface as the chrome rolls into more pages or as #22 lands.

---

### 22. Home body rebuild + Option F relocation · [feature/chrome] · medium

**Why now.** PR
[#287](https://github.com/philoyhc/review-robin-web/pull/287)
left two cleanups deferred:

1. **Option F relocation.** Page-specific status content
   (Reviewers / Reviewees `fields_with_data`, Assignments
   self-review breakdown + fields-with-data, Instruments
   deadline + accepting/visibility breakdowns) is currently
   parked in a small standalone card directly below the chrome.
   Per the design discussion, this content should live next to
   the action it relates to — `fields_with_data` next to the
   Upload card; self-review breakdown in the Current pairs
   section; instrument breakdowns in the *Actions for All
   Instruments* card.
2. **Home body rebuild around the launch-point framing.** Per
   [`spec/ui_concept.md`](./ui_concept.md) "Per Session Home /
   Control Panel", Home should hold: session identity (now in
   chrome anchor), the next lifecycle-transition action
   (Validate / Activate / Close / Reopen — one primary button
   at a time, contextual to lifecycle state), setup-readiness
   summary, terse Operations pointers (e.g. *"12 invitations
   sent, 4 responses in"*), sub-page links (Edit, Validate
   detail). Today's Home body still has the old four-card
   layout from before the spec rewrite.

Bundling because both touch the body of session-scoped pages
and are downstream of the chrome work in #19/#20.

**Where.**
- Templates: `session_detail.html` (Home rebuild),
  `session_reviewers.html` / `session_reviewees.html` /
  `session_assignments.html` / `instruments_index.html` (Option
  F relocation, four pages).
- Routes: `session_detail` handler likely needs additional
  context (Operations-pointer counts, lifecycle-transition
  affordance state).

**Plan.** Likely 4–6 small PRs:

- One Option F relocation per page (4 PRs).
- One Home body restructure PR (drop the four-card grid; add
  identity row, lifecycle-transition primary button section,
  Operations-pointer terse status, sub-page link block).
- One Home wiring PR for the lifecycle-transition button (or
  fold into the body restructure).

Done before Segment 12 starts so the operator surface is
settled.

---

### 23. Sessions-list Delete button doesn't actually delete · [bug/UX] · small · officially deferred

**Status.** Officially deferred (2026-05-03) to **Segment 15**
alongside the rest of the `/operator/sessions` surface UI work
(no segment plans that surface specifically until then). The
fix is small and the route is in place — picking it up earlier
is fine if anything else nudges the sessions-list template
first. Catalogued here so the deferral isn't mistaken for a
silent drop.

**Why now (originally).** The Delete button on every row of
`/operator/sessions` reads as a one-click delete affordance
(red `danger-solid` button labeled "Delete") but is actually
just an anchor to `/operator/sessions/{id}#danger-zone`. The
operator clicks it, lands on the session's Home page with the
fragment scroll, then has to find and tick a confirm checkbox
+ click another "Delete session" button to actually delete.

From a user's perspective, the first click *looks* like it
did nothing — the session is still in their sessions list
when they navigate back. Reads as broken wiring.

**Where.**

- Template: `app/web/templates/operator/sessions_list.html:29` —
  the `<a class="btn danger-solid" href=".../#danger-zone">Delete</a>`.
- Route: `app/web/routes_operator.py:662` — the existing
  `POST /operator/sessions/{session_id}/delete` handler is
  fine; just call it directly.
- Reference pattern: per-instrument Delete on the Instruments
  page (PR #265) — `<form method="post" action=".../delete"
  onsubmit="return confirm(...)">` with a `confirm=true`
  hidden input.

**Plan.**

- Convert each row's Delete `<a>` to a `<form>` posting to
  `/operator/sessions/{id}/delete` with `confirm=true` hidden
  input + native `onsubmit="return confirm(...)"`.
- Confirm copy includes the session name + code so the
  operator knows what they're deleting.
- For sessions in `ready` state (where the route 409s via
  `_require_editable`), render the Delete button disabled
  with a tooltip pointing at "Revert to draft first" —
  mirrors the per-instrument-Delete `is_ready` lock pattern.
- Drop the `#danger-zone` fragment from the URL since it's
  no longer needed.
- Tests: integration test that POSTing the row's Delete form
  (with confirm checked) deletes the session and 303s back to
  `/operator/sessions`; render test that confirms the button
  renders disabled on `ready` sessions.

The Home page's own "Delete session" form (inside the Danger
Zone card on `session_detail.html`) stays — operators on Home
who want to delete can still do it there. This item only
fixes the sessions-list-button surprise.

---

### 24. Operator-editable email template editor · [feature] · medium

**Why now.** The operator-side email surface today is two
hardcoded `_email_body` / `_reminder_body` helpers (each a
two-line plain-text string with the session name + invite URL
spliced in inline) plus a stub `/operator/sessions/{id}/setupinvite`
page that says "lands in Segment 15." The audit in
`guide/archive/segment_1-10_unfinished.md` (2026-05-03) flagged this
as `[tracked-status]` "owned by Segment 15," but the editor
itself is **independent of real SMTP** — it just shapes the body
that the dev outbox already renders. Pulling it back into
unfinished business so it can be picked up before Segment 15.

The workplan §12 work item #5 specified merge fields for
"reviewer name, session name, deadline, **help contact**, and
review link." Today's bodies only carry session name + invite
URL — no reviewer name, no deadline, no help contact. Operators
who run pilots end up writing follow-up emails by hand to
supply the missing context. The friction compounds with the
fact that `/setupinvite` is in the six-button setup nav, so
operators click it expecting an editor and get a stub.

**Where.**

- Stub page: `app/web/templates/operator/session_setupinvite.html`
- Stub route: `app/web/routes_operator.py::setupinvite_stub`
- Hardcoded bodies: `app/services/invitations.py:48` (`_email_body`),
  `app/services/invitations.py:386` (`_reminder_body`)
- Send sites that consume those bodies:
  `invitations.py::send_invitation` (~`:201`),
  `invitations.py::send_reminder` (~`:436`),
  `invitations.py::send_reminders_to_incomplete` (~`:467`)
- Setup-nav button hardcoded label: search `base.html` /
  `_partials/session_top_nav.html` for `setupinvite`

**Open question (must settle before the editor lands).** The
"help contact" merge field needs a source. Three plausible
shapes:

1. **Per-session field** on `ReviewSession` (operator types it
   in alongside name / code / description / deadline). Most
   flexible; one extra column on the create / edit form.
2. **Per-operator field** on `User` (set once, applies to every
   session that operator owns). Lighter UX; awkward when
   multiple operators share a session.
3. **Global env var** (`HELP_CONTACT_EMAIL` in `app.config`).
   Cheapest; assumes one help contact for the whole installation.
   Reasonable for a single-tenant pilot.

Recommend (1) for parity with the workplan's "merge field"
framing, but (3) is a defensible scope-cut if the editor is
otherwise simple. Decide before coding.

**Plan.**

- Decide help-contact source (above).
- Add an `EmailTemplate` model OR a JSON column on `ReviewSession`.
  Prefer the JSON column since templates are 1:1 with sessions
  and no separate lifecycle is needed; schema column called
  `email_template_overrides` carrying
  `{invitation_subject, invitation_body, reminder_subject,
  reminder_body}`. Defaults live in code; `NULL` / missing keys
  fall through to the default. This avoids a new table and a new
  migration concern.
- Build the editor at `/operator/sessions/{id}/setupinvite`:
  textarea per field with merge-field hint copy
  (`{{reviewer_name}}`, `{{session_name}}`, `{{deadline}}`,
  `{{help_contact}}`, `{{invite_url}}`), Save / Cancel buttons,
  a "Reset to default" link per field, and a "Preview as Rae
  Reviewer" panel rendering the merged body.
- Refactor `_email_body` / `_reminder_body` to read the override
  + render with `string.Template` (or Jinja `from_string` with a
  fixed env). Reviewer-row context (name, email) injected at
  send time from the `Invitation.reviewer` row.
- Update audit events: `email_template.updated` with a `changes`
  diff (mirroring `session.updated`).
- The `/setupinvite` stub page swap is the operator-visible
  delivery; once the editor is in place, the row in `docs/status.md`
  for `/setupinvite` flips from "stub" to its real description.
- Tests: editor-page render (loads defaults), save round-trip
  (override persists), reset-to-default (override clears),
  send-invitation uses the override, fall-through (NULL key
  uses default), preview-mode merge.

**Sequencing.** Bundles naturally with **#6** (decouple
`invitations.py` from `Request`). The Request coupling lives
in the URL-builder used by both `_email_body` and the editor's
preview pane; settling that helper first means the template
work doesn't spawn a third caller of the broken pattern.

**Out of scope.** Real SMTP / Azure email backend stays
**Segment 15**. This item is the editor + merge-field rendering
only — it lands the operator-facing surface that the existing
dev outbox will then carry into Segment 15 unchanged.

---

### 25. Inline-editable rows on reviewers / reviewees / assignments Manage pages · [feature] · medium · officially deferred

**Status.** Officially deferred from `guide/segment_11_*.md` §2.5
(originally surfaced in 10E before Segment 11 was renamed).
Slated for **Segment 15** (operator polish + documentation) since
it needs a design pass before code, and the polish segment is the
right home for that pass. Catalogued here so a future operator
runbook update or workplan revision doesn't lose track of it.

**Why now (originally).** The disabled "Edit Reviewers / Reviewees /
Assignments" buttons render as placeholders on all three Manage
pages today (Segment 9.4 deferred scope). Whatever pattern lands
here will likely apply to all three; design once, reuse three
times.

**Where.**

- `app/web/templates/operator/reviewers_list.html` —
  Edit Reviewers button (currently `<a class="btn disabled"
  aria-disabled="true">`).
- `app/web/templates/operator/reviewees_list.html` — same
  shape.
- `app/web/templates/operator/assignments_list.html` — same
  shape.
- `docs/status.md` "What's deliberately not yet there" entry
  — links here.

**Plan.** Design pass before code:
- Decide the editing pattern: inline-row toggle (HTMX-style
  `<details>`-per-row?), modal per row, or dedicated `/edit`
  page per row?
- Decide the conflict model: optimistic (last-write-wins) or
  pessimistic (lock the row while editing)?
- Decide the validation surface: same as CSV import (re-run
  the validators on save), or per-field?
- Decide whether editing is allowed in `validated` / `ready`
  states or only `draft`.
- Once decided, ship the pattern on Reviewers first, then
  rinse and repeat on Reviewees + Assignments.

**Cross-ref.** Mirror entry in `docs/status.md` "What's
deliberately not yet there" pointing here.

---

### 26. Local Postgres docker-compose for dev · [dev-loop] · small · officially deferred

**Status.** Officially deferred from `guide/segment_11_*.md` §2.7
(originally surfaced in 10E before Segment 11 was renamed).
Slated for **Segment 15** (developer setup guide work item) since
the developer-setup-guide work in §18 is the natural place for the
Postgres-vs-SQLite local-dev story to settle. Catalogued here so
the deferral isn't mistaken for a silent drop.

**Why now (originally).** `segment_05A.md` §3.5 deferred local
Postgres in favour of SQLite + the `ci-postgres` job + migration-
on-deploy as the parity story. The reasoning held through Segments
6–10 and the `ci-postgres` job (PR #297) closed the dialect-coverage
gap. Local Postgres still has occasional value for Postgres-only
debugging, but it has stayed deferred because the workflow gap
hasn't bitten anyone hard.

**Where.**

- `segment_05A.md` §3.5 — original deferral reasoning.
- `docs/database.md` — currently says "install your own Postgres
  only when a Postgres-only bug demands it." That stance stays
  unless this item lands.
- Reference: the `ci-postgres.yml` workflow that already
  provisions `postgres:16` as a service container — the
  docker-compose form would mirror that config.

**Plan.** When (or if) this lands:
- Add `docker-compose.yml` at repo root with the
  `postgres:16` image + `rrw_app` user + `rrw` database (mirror
  the CI job).
- Add `make pg-up` / `make pg-down` shortcuts (or just document
  `docker compose up -d postgres`).
- Update `docs/database.md` and the developer setup guide
  (Segment 15 §18 work item #8) to point at it as an option,
  with SQLite still the default.
- No code changes; the existing dialect-detecting `engine`
  fixture in `tests/conftest.py` already honours `DATABASE_URL`.

**Likely fate.** Probably never lands; the developer-setup-guide
work in Segment 15 may decide "won't fix" and update the workplan
+ `docs/status.md` accordingly. Catalogued so the decision is
explicit either way.

---

### 27. FullMatrix generation: per-instrument target picker · [feature] · small

**Status.** Carried over from the now-superseded
`guide/archive/segment_13_multi_instrument_sessions_superseded.md`
§7.1. The success criterion "FullMatrix can generate assignments
by instrument" never landed; the rest of multi-instrument support
shipped in Segment 10D Slice 5.

**Why now.** `assignments.replace_assignments` at
`app/services/assignments.py:561` calls
`get_or_create_default_instrument(...)` and assigns every generated
pair to one instrument. On a session with two instruments, the
operator has no way to ask "generate FullMatrix for instrument 2";
they get the default. Mostly invisible today because operators
running multi-instrument sessions tend to use Manual import — but
the moment a real pilot uses FullMatrix on a 2-instrument session,
the gap surfaces.

**Where.**

- `app/services/assignments.py:561` — `replace_assignments`
  hardcodes `instrument = get_or_create_default_instrument(...)`.
- `app/web/routes_operator.py::assignments_full_matrix_generate`
  (~`:412`) — POST handler; needs a target-instrument form
  field.
- `app/web/templates/operator/assignments_list.html` — the
  FullMatrix form lives here; needs an instrument picker when
  more than one instrument exists.

**Plan.**

- Decide UX shape: single-target picker (one instrument per
  generation; operator runs once per instrument they want to
  populate) or multi-select (one POST creates assignments
  across N instruments). Single-target is simpler and matches
  Manual's pattern (one CSV per intent).
- Add `target_instrument_id` form field to the FullMatrix form;
  default to the only instrument when there's just one (and
  hide the picker).
- `replace_assignments(... target_instrument_id=...)` — when
  None, fall back to `get_or_create_default_instrument` (current
  behaviour).
- Audit detail: include `target_instrument_id` in
  `assignments.generated`.
- Tests: 2-instrument session with FullMatrix targeting
  instrument 1 leaves instrument 2 untouched.

---

### 28. ManualAssignment CSV: `Instrument` column · [feature] · small

**Status.** Carried over from the now-superseded
`guide/archive/segment_13_multi_instrument_sessions_superseded.md`
§7.2.

**Why now.** `ManualAssignmentRow` at
`app/schemas/assignments.py:14` carries `reviewer_id`,
`reviewee_id`, `include`, `pair_context_*`, and
`assignment_context_*` — but no `instrument`. On a multi-instrument
session, the manual CSV importer routes every row to the default
instrument (same shape as #27). Same invisible-today / gap-on-pilot
dynamic.

**Where.**

- `app/schemas/assignments.py:14` — `ManualAssignmentRow` schema.
- `app/services/assignments.py::parse_manual_csv` (~`:300`) — CSV
  parser; needs to read an optional `Instrument` column.
- `app/services/assignments.py::manual_rows_to_pairs` (~`:480`)
  — needs to thread `instrument_id` per row.
- `app/services/assignments.py::replace_assignments` —
  `Assignment.instrument_id` should come from the parsed row,
  not the default.
- `docs/imports.md` — Manual CSV format spec; needs the new
  column.

**Plan.**

- Add optional `Instrument` column to the manual CSV format.
- Validation rules:
  - If session has exactly one instrument: column optional;
    missing rows get the default; populated rows must match.
  - If session has >1 instrument: column required; blocking
    error when missing or unknown.
- Match instruments by `Instrument.name` (the system handle —
  mostly `Default`, plus operator-added like `Instrument 2`)
  case-insensitive.
- Audit detail on `assignments.generated` includes a
  `per_instrument_count: {instrument_id: count}` map.
- Tests: 2-instrument session imports rows targeting both;
  rows with unknown instrument blocked; missing-column blocked
  on multi-instrument.

---

### 29. Reviewer dashboard: per-instrument grouping · [feature] · small

**Status.** Carried over from the now-superseded
`guide/archive/segment_13_multi_instrument_sessions_superseded.md`
§8 (success criterion 6).

**Why now.** `app/web/templates/reviewer/dashboard.html` shows one
row per session with a single per-session pill (`not started` /
`in progress` / `submitted`). On a 2-instrument session a reviewer
who's submitted instrument 1 but not started instrument 2 sees
"in progress" with no breakdown — they have to open the surface
to learn which instrument is which. The surface itself already
groups by instrument (`instrument_groups` template loop in
`review_surface.html` since 10A); the dashboard never picked up
the same shape.

**Where.**

- `app/web/templates/reviewer/dashboard.html` — single per-session
  row + pill.
- `app/web/routes_reviewer.py::dashboard` — the handler;
  currently calls `responses_service.session_pill_for_reviewer`
  which collapses across instruments.
- Reuse: `responses_service.reviewer_session_state(...)` (added
  in PR #298) — extend to per-instrument projection, or wrap
  with a new `reviewer_instrument_state(...)` helper.

**Plan.**

- Add `reviewer_instrument_state()` helper returning a list of
  per-instrument `(instrument_id, instrument_name,
  pill_state, completed_count, total_count)` tuples.
- Dashboard renders a sub-row per instrument under each session
  row when the session has >1 instrument; collapses to the
  current single-pill shape when there's exactly one.
- Tests: dashboard render for single-instrument session
  (unchanged); 2-instrument session with mixed completion
  shows two pills.

---

### 30. Quick Setup card on Session Home · [feature] · medium

**Why now.** Operators bulk-loading a session today have to
navigate three separate pages (Reviewers, Reviewees, Assignments)
in sequence. Each carries its own upload card, its own confirm
flow, and its own status indicator. The Quick Setup card unifies
all three into a single Home-body element — three independent
slots (Reviewers / Reviewees / Assignments-or-rule) with shared
confirm + cascade + lifecycle-lock semantics. The full spec lives
at `spec/quick_setup_card_spec.md` (PR #307).

This is genuinely new operator-surface scope — not from the
segments-1–10 audit. Filed in Segment 11 because it bundles with
**#22** (Home body rebuild + Option F relocation): both
restructure Home's body, both share CSS primitives, both depend
on the chrome-button restyle (#21) settling first. Doing them in
the same pass avoids touching Home twice. The card is also
pre-Segment-12 (export) work — it settles the operator surface
before the heavier feature segments.

**Where.**

- Spec: `spec/quick_setup_card_spec.md` (full functional spec).
- Template surface: `app/web/templates/operator/session_detail.html`
  — the Home page; the card lands in the body alongside #22's
  rebuild work.
- Reuses, per the spec's "Implementation pointers":
  - Existing per-entity CSV parsers in `app/services/csv_imports.py`
    + `app/services/assignments.py` (`save_reviewers`,
    `save_reviewees`, `parse_manual_csv`).
  - Existing `replace_assignments` for the rule path (with #27
    if FullMatrix per-instrument target picker has shipped by
    then).
  - Cascading-clearance pattern that already runs inside the
    CSV-import services (`_count_assignments`,
    delete-on-replace).
  - Lifecycle-lock pattern from the yellow lock card (Segment
    10C `.field-builder.locked`).
  - Confirmation pattern from Edit Session / per-instrument
    Delete inline confirms.

**Plan.**

- Sequence after **#21** (button restyle settles the visual
  vocabulary the card uses) and **bundle with #22** (Home body
  rebuild — same template surface, same restructure pass).
- Probably 3–4 PRs: (a) data-and-counts shape (the passive
  indicators pull from existing `csv_imports.existing_*_count` /
  `assignments.existing_count` — wire them into a Home view
  function); (b) Slot 1 + Slot 2 (Reviewers + Reviewees, simpler
  pair); (c) Slot 3 (Assignments — rule selector + CSV upload
  toggle); (d) confirmation + cascade copy + lifecycle-lock
  polish.
- Settle one open question early: where the Slot 3 rule selector
  lives once **#28** (Manual CSV `Instrument` column) and
  **#27** (FullMatrix per-instrument target picker) ship — does
  the Quick Setup rule selector pick a single instrument, all
  instruments, or expose the same picker the per-entity page
  exposes? Probably "single instrument with default-only when
  N=1, picker when N>1" to match #27.
- Tests: per-slot success + parse-error + validation-error
  paths, cascade clearance copy, lifecycle-lock states, and
  re-uploading on a `validated` session re-invalidates back to
  `draft` (matches existing per-entity behaviour).

**Out of scope.** All the explicit out-of-scope items in
`spec/quick_setup_card_spec.md` (per-record editing, CSV preview,
wizard stepping, cross-entity validation, auto-regeneration of
assignments after a roster replacement, undo, save-as-template).

---

### 31. Sort by reviewee on the reviewer surface · [feature] · medium · target Segment 13

**Status.** Promoted from Segment 11 §2.6 sketch (2026-05-03).
Full design spec at `guide/sort_by_reviewee.md`. Target segment:
**13** (RuleBased assignment builder) — the natural touch-up of
the per-instrument card during that segment's work.

**Why now (originally).** The reviewer surface table renders
rows in implicit insertion order; the operator has no way to
set a deliberate default, and the reviewer has no way to re-sort
during their working flow. Segment 10D flagged the sort
affordance as "semantics not yet decided" and it never landed.

**Where (high-level).** Operator side: a new Sort column on the
per-instrument card's Display Fields table (no new card).
Reviewer side: clickable column headers on the review-surface
table for live, non-persisted override.

**Spec.** See `guide/sort_by_reviewee.md` for the full design —
storage shape, click semantics on the operator widget, reviewer-
side override behaviour, cascade rules, audit event,
lifecycle-invalidation, out-of-scope items, and implementation
pointers.

**Cross-ref.** Mirror entry in `docs/status.md` "What's
deliberately not yet there" pointing here and at the spec.

---

### 32. Further refinement of the reviewer surface · [polish] · varied · target Segment 15

**Status.** Forward-looking catch-all for reviewer-surface polish
beyond the Segment 11 Tier 1 batch (PRs #319 → #324). Target
**Segment 15** (operator polish + documentation) — same theme,
naturally absorbs reviewer-side polish alongside the operator-side
polish items already slated there (#23, #25, #26).

**Why now (originally).** The Segment 11 Tier 1 closeout shipped six
reviewer-surface tweaks surfaced from a single local-run inspection
(heading mismatch, position-based heading, help-text inline list,
Reviewee column dedup, Photo "View" link, column-width hints,
trailing-status-column hide-when-empty, card framing experiment +
revert, help-text indentation fix). Pilot use will surface more of
the same kind of low-priority-but-high-impact polish. This entry is
the bucket those land in.

**Known sub-items.**

- **Multi-instrument preview** — `build_preview_context` in
  `app/web/routes_reviewer.py` is single-instrument-only today
  (picks an "anchor" instrument and pads to 3 rows; other
  instruments are skipped at render). Plan was sketched on
  2026-05-03 and explicitly deferred from the Segment 11 Tier 1
  batch. Approach: iterate the full ordered `instruments` list,
  synthesize ~2 rows per instrument, build `instrument_groups`
  with one entry per instrument. ~50–80 line restructure plus 2
  integration tests. Carries the column-width hints and card
  framing decisions from the Tier 1 batch through unchanged.
- **Pilot-feedback-driven polish** — placeholder. Specific
  refinements added here as they surface from real operator use.

**Where (high-level).** `app/web/routes_reviewer.py`,
`app/web/templates/reviewer/review_surface.html`, `app/web/views.py`
(reviewer_instrument_heading and any new helpers), and
`app/web/templates/base.html` for any new shared CSS primitives.

**Sequencing notes.** This sits alongside but doesn't depend on
**#31** (sort by reviewee, target Segment 13 — see
`guide/sort_by_reviewee.md`). The sort feature implements its own
reviewer-surface changes (clickable column headers, server-side
default sort) and lands in Segment 13; this catch-all picks up
everything else.

**Cross-ref.** Mirror entry in `docs/status.md` "What's
deliberately not yet there" pointing here.

---

### 33. AG Grid replacement of the reviewer-surface table · [feature] · medium · target Segment 15

**Status.** Filed 2026-05-03 from the Segment 11 Tier 2 §2.1
"AG Grid fate" decision — target **Segment 15** (operator polish +
documentation). Picks up the second half of workplan §11 / archived
Segment 8 plan that never landed.

**Why now (originally).** Workplan §11 was explicit:

> "Implement a simple tabular review page first with ordinary HTML
> inputs before introducing AG Grid. … Now replace the simple table
> with AG Grid while keeping the same save endpoint."

The first half shipped (plain HTML table with `<input>` / `<textarea>`
/ `<select>` per cell + form-based save/submit). The second half —
AG Grid replacement — was never done. `docs/status.md` didn't list
it as deferred, so for ten segments it sat in an in-between state
("are we still doing this, or is the plain HTML the design?"). The
decision: **still on the roadmap, target Segment 15**.

**Where.**
- Template to replace:
  `app/web/templates/reviewer/review_surface.html` — the
  per-instrument-group table-and-inputs surface.
- Save endpoint stays:
  `app/web/routes_reviewer.py` — `/reviewer/sessions/{id}/save` is
  the contract AG Grid integrates against. No backend change needed.
- Per-cell render branch (today's `data_type` switch in the
  template): becomes AG Grid column-type configuration.

**Plan.**
- Replace the plain HTML table with AG Grid, keeping the existing
  `/save` endpoint as the persistence target. Per workplan: "do not
  add new business rules."
- Preserve current behaviours:
  - Per-instrument grouping (one grid per instrument, or one grid
    with instrument grouping — design call).
  - Display-field columns (Reviewee identity always first; dedup of
    `(reviewee, name)` / `(reviewee, email_or_identifier)` per
    PR #320).
  - Response-field column types (Long_text textarea, Numeric input,
    List dropdown, Yes/No, Grade — all driven by the RTD's
    `data_type` + `validation`).
  - Required-field validation with warn-and-acknowledge override.
  - Lifecycle locks (closed instruments render disabled).
  - `submitted_at` / completion-status indicators (the trailing
    ✓/⚠ column shipped via PR #322 — likely an AG Grid render
    callback).
- Naturally bundles with **#2** (vanilla-JS autosave on `/save`),
  which is currently parked behind this decision in Segment 11
  Tier 4 — autosave folds into AG Grid's cell-edit lifecycle
  rather than landing as a standalone debounce.

**Sequencing notes.**
- Lands after **#31** (sort by reviewee, Segment 13) only if the
  sort spec's clickable-column-header override is meant to migrate
  to AG Grid's native multi-column sort. If sort-spec is
  AG-Grid-aware from the outset, #31 + this can bundle in
  Segment 15. Most likely: AG Grid lands first in Segment 15, and
  the sort spec's reviewer-side override is implemented as
  AG Grid configuration rather than custom JS.
- Lands together with or replaces **#32** (further refinement of
  the reviewer surface). The "multi-instrument preview" sub-item
  of #32 is moot if AG Grid's grouping handles it; pilot polish
  targets the AG Grid surface rather than the plain HTML one.

**Out of scope.** All workplan §11 "keep deliberately out of
scope" items — polished spreadsheet UX beyond AG Grid defaults,
multi-tab multi-instrument review, complex autosave conflict
handling, reminder emails (Segment 9), export generation
(Segment 12).

**Cross-ref.** Mirror entry in `docs/status.md` "What's
deliberately not yet there" pointing here.

---

### 34. Queue-based batch invitation sending · [feature] · medium · target Segment 15

**Status.** Filed 2026-05-03 from the Segment 11 Tier 2 §2.3
"Queue-based batch invitation sending" decision — target
**Segment 15** (operator polish + documentation), bundled with
real SMTP. Picks up workplan §12 work item #7 ("Add queue-based
batch sending") that was named but never implemented.

**Why now (originally).** `POST /operator/sessions/{id}/invitations/send-all`
(`app/web/routes_operator.py:2121`) and the parallel reminder
endpoint loop through every eligible reviewer and call
`send_invitation()` / `send_reminder()` synchronously inside the
HTTP request handler. With the dev outbox (today) each call is a
~1ms DB insert — even a 200-reviewer batch finishes in 1–2s and
the synchronous loop is fine.

With **real SMTP** (Segment 15) each call becomes a 100–500ms
network round-trip plus provider rate-limiting (Microsoft Graph
throttles ~30 sends/sec). A 200-reviewer batch becomes 1–2 minutes,
which exceeds typical reverse-proxy timeouts (30s–2min); the
operator's browser hangs; partial-failure recovery has no
mechanism; transient SMTP failures aren't retried.

**Where.**
- Synchronous send loops:
  `app/web/routes_operator.py::invitations_send_all` (~`:2121`),
  parallel reminder endpoint.
- Send service:
  `app/services/invitations.py::send_invitation` and
  `send_reminders_to_incomplete`.
- Prerequisite refactor: **#6** (decouple `invitations.py` from
  `Request`) — a background worker has no live request, so
  `send_invitation(request=...)` needs a `build_invite_url`
  callable instead.

**Plan (sketch — full design lands in Segment 15 with real-SMTP
work).**
- Job table: `email_send_job(id, session_id, kind, status='pending'
  | 'in_progress' | 'done' | 'failed', created_at, ...)`. Per-row
  state for individual invitation sends, or one parent row + child
  per-invitation rows — design call.
- Operator action: "Send all" writes the parent job row + 303s to
  a status page (no synchronous wait).
- Worker: Azure WebJob / Functions Timer Trigger / dedicated worker
  dyno polls the job table, processes pending rows one at a time
  with rate-limiting + retry-on-transient-failure.
- Operator UI: invitations page polls or refreshes to show
  per-invitation status (already wired for the synchronous case).

**Sequencing.**
- Lands as part of Segment 15 real-SMTP work; one infrastructure
  decision (worker setup + job table) covers both real-SMTP and
  batch queueing.
- Depends on **#6** (decouple `invitations.py` from `Request`)
  shipping first — currently scheduled in Segment 11 Tier 3.

**Out of scope.** Polished job-status UI beyond
"in-progress / done / failed" indicators, retry policy
configuration, multi-tenant rate-limit tuning.

**Cross-ref.** Mirror entry in `docs/status.md` "What's
deliberately not yet there" pointing here.

---

## Items deliberately not on this list

- Anything in `docs/status.md` "What's deliberately not yet there"
  — those are owned by their assigned segments, not by this list.
- `routes_operator.py` overall size: 1849 lines of mostly thin
  handlers is fine. Item 11 is the one carve-out worth doing now.
- `bulk_save_fields` (`app/services/instruments.py:407–554`) — long
  but stable; revisit if Segment 13 (RuleBased) forces changes to it.
