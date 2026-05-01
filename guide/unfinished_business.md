# Unfinished business

**Role.** Rolling todo of cross-cutting cleanups carried over
from earlier segments — the unfinished items needed to stabilize
the operator model and engine before new feature segments build
fresh surface on top. Items are not gated to a single segment;
when one ships, tick it and move on. New cleanups identified
during later segments land here too.

This file replaces the former `guide/adhoc_todo.md` (originally
captured during the mid-Segment-10B health review on 2026-04-30)
and the short-lived `guide/segment_10D.md` framing. Items are
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

### 1. Wire `ruff check` into CI · [CI] · small

**Why now.** `ruff` is in `pyproject.toml`'s dev deps and listed under
"Tooling" in AGENTS.md, but no workflow runs it. With no human dev
loop, CI is the only place lint will ever execute. 5-minute change,
permanent signal.

**Where.** `.github/workflows/ci.yml` — single pytest step today,
add a `ruff check .` step before it (or as a separate job). Fail the
build on lint errors.

**Plan.**
- Add `ruff check .` step in `ci.yml` after `pip install -e .[dev]`
  and before `pytest`.
- Run locally first (in the agent sandbox) to fix any pre-existing
  ruff findings the codebase has accumulated. Land those fixes in
  the same PR or a precursor PR — don't merge a CI step that is
  already red.

---

### 2. Run pytest against Postgres in CI · [CI] · medium

**Why now.** The `ci-postgres-migration` job only does
`alembic upgrade head` / `downgrade base` / `upgrade head`. It never
imports `app/` and never runs a test. SQLite-only test runs hide
real divergence (JSON coercion, datetime tz handling, dialect
functions) until the dev-slot deploy, which is the only place the
human can observe failures. A second pytest job against a Postgres
service container collapses that feedback loop.

**Where.** `.github/workflows/ci-postgres-migration.yml` — add a
pytest step after the migration round-trip, with the `DATABASE_URL`
already pointing at the service container. Or a sibling
`ci-postgres-tests.yml`. Reuse the `postgres:16` service container
config that's already there.

**Plan.**
- Decide whether tests run with `DATABASE_URL=postgresql+psycopg://...`
  injected, or via a pytest marker. The simpler route is the env var
  — `tests/conftest.py` already honours `DATABASE_URL` for the
  engine fixture (verify before assuming).
- Run the full suite. Triage and fix any tests that pass on SQLite
  but fail on Postgres. Likely candidates: anything that compares
  datetime equality, anything that relies on lexicographic ordering
  of inserted rows.

---

## P2 — Architectural debt to land before Segment 11 (export / audit retention)

### 3. Move `_invalidate_if_validated` policy out of routes · [arch] · medium

**Why now.** The `validated → draft` invariant is enforced by a
helper defined in `app/web/routes_operator.py:785` and called from
~16 sites in the same file (193, 310, 416, 498, 616, 694, 724, 754,
1140, 1188, 1252, 1291, 1329, 1360, 1400, 1427, 1478). The
corresponding service functions in `app/services/instruments.py` and
`app/services/csv_imports.py` know nothing about the rule. With no
local dev loop and a thin pytest gate, a new route that forgets the
wrapper silently breaks the invariant and ships. Segment 11 will add
more setup-mutation surfaces (export config, retention rules); the
fragility compounds.

**Where.**
- Caller list: `grep -n _invalidate_if_validated
  app/web/routes_operator.py`.
- Helper definition: `app/web/routes_operator.py:785`.
- Lifecycle service: `app/services/session_lifecycle.py` (the
  `invalidate_session(...)` it ultimately calls).

**Plan.**
- Push the policy into the service layer: each mutating service
  function takes the `review_session` and `actor_user` it already
  touches and decides for itself whether to invalidate. The status.md
  table is the source of truth for which mutations invalidate vs
  don't (e.g. instrument open/close deliberately doesn't).
- Or: a single decorator / context-manager applied at the service
  boundary that observes whether the function ran a mutating
  side-effect and invalidates if so.
- Keep the route helper as a thin shim during migration. Delete it
  once all callsites resolve through the service.
- Update tests to assert the invariant via the service, not via the
  route — drives the abstraction in the right direction.

---

### 4. Extract a single reviewer-session-state helper · [arch] · small

**Why now.** Two functions independently walk `assignments → fields
→ responses` to compute the same state with subtly different rules:
- `app/services/responses.py:435` — `session_pill_for_reviewer`
  (returns `not started` / `in progress` / `submitted`; checks
  `Response.submitted_at` on required fields at line 474).
- `app/services/monitoring.py:67` — `_reviewer_completion`
  (returns `(assignment_count, completed_count,
  missing_required_count)`).

They will drift. Segment 11 export will want a third copy for
"incomplete at deadline" cohorts. Consolidate before that lands.

**Where.** `app/services/responses.py:435–495` and
`app/services/monitoring.py:67–115`.

**Plan.**
- Define one private helper that returns a richer dataclass:
  per-assignment status + required-field coverage + submitted-at
  state. Both existing public functions become thin projections of
  it.
- Tests already cover the two existing call paths
  (`tests/integration/test_monitoring.py`,
  `tests/integration/test_reviewer_response_flow.py`). Add a unit
  test for the new helper directly.

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
reconciled. Segment 11 is "export / audit retention" — the export
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

### 11. Extract instruments-index template context to `views.py`
· [refactor] · small

**Why now.** `app/web/routes_operator.py:956–1056` (~100 lines)
builds display-field + response-field row context for the
instruments index inline. It's the only operator handler that does
meaningful template-context shaping in the route. The same shaping
will be reused by the preview route; pulling it into `views.py`
sets up the reuse.

**Order dependency:** land **after** items 13 and 14 (Display
Fields placeholder fix + default-seed rework) — those will reshape
exactly the context this handler builds today (the new
`merged_rows_by_instrument` and `available_sources_by_instrument`
keys may go away or change shape). Doing 11 first means the
extracted helper gets ripped up.

**Where.** `app/web/routes_operator.py:956–1056`. Move into
`app/web/views.py` next to the existing `build_setup_rows` helper.

**Plan.**
- Define `build_instruments_context(db, review_session) -> dict[...]`
  in `views.py`.
- Replace the inline body of the instruments-index handler with a
  single call.
- No behavioural change — existing tests should pass without edits.

---

### 12. Reviewer/Reviewee CSV cross-table identity check · [bug] · small

**Why now.** Carried over from
`guide/segment_10_instrument_builder_mvp_plan.md` §15 as a
deferred follow-up. The upload validators in
`app/services/csv_imports.py` treat reviewers and reviewees as
independent tables; a person who appears in both with the same
email but different names imports cleanly today and surfaces as a
mismatch downstream (assignment-context joins, monitoring email
lookups). Tightening the rules now — while the validator surface
is small — costs less than retrofitting after Segment 11's
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

### 13. Fix the Display Fields placeholder (no-persistence + bad sources) · [bug] · small

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
   beyond Segment 11.
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
Segment 11 or its own 10x slice.

---

### 14. Drop the `pair_context_*` default seed; seed display fields from import data · [bug] · medium

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

### 15. Backfill integration tests for shipped 10C functionality · [test] · small

**Why now.** Four 10C-shipped surfaces have no integration test
coverage:
- `delete_instrument` (route + service + cascade).
- `bulk_set_visibility` (`/instruments/visibility/all-on` and
  `/all-off`) and the `instruments.bulk_visibility_when_closed`
  audit event.
- `add_default_response_field` (`/fields/add-row`).
- "Cannot delete the last instrument" 400 guard.

The upcoming arch refactors (items 3, 11) will touch this code;
without tests, regressions ship silently.

**Plan.** One PR per surface, mirroring existing
`tests/integration/test_*` patterns. Cap each test at the
happy path + one boundary (e.g. for delete: "delete the last
instrument 400s"; for bulk: "no-op when already at target").

---

### 16. Decide bulk_visibility_when_closed invalidation policy · [arch] · tiny

**Why now.** `instruments_bulk_visibility_on/off`
(`routes_operator.py:1621–1642`) is the only bulk instrument
mutation that does **not** call `_invalidate_if_validated`
— compare to `bulk_set_accepting`. Visibility-when-closed isn't
structural so this may be intentional, but it's inconsistent and
undocumented. Naturally bundles with item 3 (move
`_invalidate_if_validated` to the service layer).

**Plan.** Either add the invalidation call (matching
`bulk_set_accepting`) or add a one-line comment + status.md note
explaining why it's deliberately exempt. Decide and document.

---

### 17. Investigate `Assignment.include` filter divergence · [arch] · small

**Why now.** `monitoring._reviewer_completion`
(`app/services/monitoring.py:76`) filters assignments with
`Assignment.include.is_(True)`. `responses.session_pill_for_reviewer`
(`app/services/responses.py:439`) does **not** filter on `include`.
This is the exact drift item 4 (extract a single
reviewer-session-state helper) is meant to catch — but verify
which filter is correct *before* consolidating, or item 4 will
ship the wrong unified rule.

**Plan.** Trace one reviewer through both paths in a test session
with `include=False` rows; document the intended semantics; pick
one and align both. Then proceed with item 4.

---

### 18. Decide fate of disabled "Add an instrument" button vs live route · [decision] · tiny

**Why now.** `instruments_index.html:418–419` ships a
`disabled` Add-an-instrument button with tooltip
"Multi-instrument support is still in progress"; meanwhile
`routes_operator.py:1530` defines a working `POST /instruments/add`
endpoint and `delete_instrument` is wired and tested-via-cascade.
Item 11 (extract template context) will trip over this
inconsistency.

**Plan.** Pick one:
- **Enable the button** with a confirm step. The schema and
  services are ready; the only missing piece was a UI design
  decision and that's now mostly defined by the per-instrument
  card layout.
- **Delete the route** (and `instruments_add` handler) until
  Segment 13 actually wants it. Reduces dead surface area; route
  comes back when the multi-instrument UI lands.

Decide before item 11.

---

## Items deliberately not on this list

- Anything in `docs/status.md` "What's deliberately not yet there"
  — those are owned by their assigned segments, not by this list.
- `routes_operator.py` overall size: 1849 lines of mostly thin
  handlers is fine. Item 11 is the one carve-out worth doing now.
- `bulk_save_fields` (`app/services/instruments.py:407–554`) — long
  but stable; revisit if Segment 12/13 force changes to it.
