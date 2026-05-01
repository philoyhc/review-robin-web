# Segment 8A — Reviewer Review-Surface MVP (Agreed Plan)

**Project:** Review Robin Web
**Repository:** <https://github.com/philoyhc/review-robin-web>
**Parent plan:** `guide/segment_08_reviewer_surface_mvp_plan.md`
**Purpose:** Lock in implementation choices for Segment 8 — the
reviewer's review surface — so the implementation session can ship
without re-litigating design.

This document is a **delta** on the parent plan. The parent plan
governs scope, success criteria, and out-of-scope items.

---

## 1. Scope

The first reviewer-facing workflow:

- Reviewer dashboard at `/reviewer` lists sessions where the
  authenticated user's email matches an **active** `Reviewer` row.
- Review surface at `/reviewer/sessions/{id}` renders all of the
  reviewer's assignments (excluding `include = false`) as a
  plain HTML table. Each row carries the Default Instrument's
  response fields as inputs.
- Four actions: **Save draft**, **Cancel** (revert in-progress
  edits to last-saved values), **Clear all** (with confirm),
  **Submit** (with required-field warn-and-override).
- Per-row completion indicator on the surface.
- Per-session completion indicator on the dashboard.

This segment also retrofits a roster-status filter onto
existing assignment generation (FullMatrix + Manual CSV import)
so inactive `Reviewer` / `Reviewee` rows are excluded — a
small Segment 7 fix-up bundled here because it shares the rule
the dashboard depends on. See §3.13.

---

## 2. Branch and PR strategy

**One PR** against `main`: `claude/segment-8-reviewer-surface`.

The dashboard, review surface, save / cancel / clear / submit
endpoints, the roster-status retrofit, and tests are tightly
coupled. Splitting produces awkward partial states. Estimated
~800–950 LOC including the §3.13 retrofit and its tests.

**Autosave is deferred** to a small follow-on PR (vanilla JS over
the same `/save` endpoint). Reasons in §3.5.

---

## 3. Decisions

### 3.1 Identity matching

The authenticated user is matched to `Reviewer` rows by
case-insensitive email equality (`casefold()` both sides — the
same convention as `parse_manual_csv`). Only `Reviewer` rows
with `status == "active"` count; non-active rows are filtered
out at query time everywhere a reviewer's identity is resolved.
A user can be an active reviewer in N sessions; the dashboard
lists all of them.

The new dependency `require_reviewer_in_session(session_id)` —
analogous to `require_session_operator` from 6A — looks up the
active `Reviewer` row matching the user's email in that session
and returns `(reviewer, review_session)`. Returns **403** if no
matching active reviewer row.

### 3.2 What the reviewer sees on the surface

For each non-excluded assignment (one per reviewee, since today
there's one Default Instrument):

- **Reviewee name** (always)
- **Reviewee identifier** (always)
- **Non-null `pair_context_1/2/3`** (informational, per
  ARCHITECTURE.md "Pair-level vs assignment-level context")
- **One input per `InstrumentResponseField`** in the Default
  Instrument: today that's `rating` (integer 1–5, required) and
  `comments` (long text, optional).

Hidden by default in this segment: `RevieweeTag1/2/3`,
`AssignmentContext1/2/3`. The schema for showing them already
exists (`InstrumentDisplayField`); operator-controlled
visibility lands in Segment 13.

Excluded assignments (`Assignment.include = false`) are filtered
out at query time and never reach the surface.

### 3.3 Save draft

Explicit **Save draft** button at the bottom of the form.

- `POST /reviewer/sessions/{id}/save`
- Form fields are named `response[<assignment_id>][<field_key>]`.
- Server upserts `Response` rows: one per `(assignment_id,
  response_field_id)`. Existing rows update; new rows insert.
- **Empty values delete the response row** (so the row's absence =
  empty answer, no ambiguous empty-string state).
- `submitted_at` is **never set or modified** by Save draft.
- Returns 303 → review surface, with a transient `?saved=ok` query
  param that the surface uses to render a "Saved" toast.
- Audit event `responses.saved` with `detail = {count, session_id}`.

### 3.4 Submit

**Submit** button at the bottom, alongside Save draft.

Two-step warn-and-override (matches the operator flows' replace
guardrail):

1. `POST /reviewer/sessions/{id}/submit` — server first persists
   any draft changes (same logic as Save draft), then validates
   required fields across the whole grid.
2. If any required field is empty:
   - The page re-renders with HTTP **400**, a yellow warning card
     listing the missing-required positions ("Carol — `rating`",
     "Dan — `rating`"), and an `acknowledge_missing` checkbox
     (rendered only on the warning re-render) the reviewer must
     tick to retry.
3. If all required fields are filled, **or** the form was
   submitted with `acknowledge_missing=true`:
   - All `Response` rows for the reviewer's assignments in this
     session get `submitted_at = now()`.
   - 303 → review surface with `?submitted=ok` toast.
   - Audit event `responses.submitted` with `detail = {count,
     missing_required_count, session_id}`.

After submit, the reviewer can keep editing (Save draft updates
values; re-submit refreshes `submitted_at`). Editing a required
field down to empty deletes the row including its `submitted_at`,
so the next submit attempt re-fires the missing-required warning
normally. The Cancel button (§3.12) lets a reviewer abandon
in-progress edits without writing anything.

Per-Instrument open/close (the operator-controlled state where
an instrument stops accepting new responses) lands in Segment 9.
Save / submit on a not-accepting instrument's fields will be
blocked at the route layer there. The response window is owned
by each Instrument, not by the session as a whole, so different
instruments can close on different schedules (relevant once
multi-instrument ships in Segment 13).

### 3.5 Clear all

**Clear all** button at the top of the form, separated from the
primary actions visually.

- `POST /reviewer/sessions/{id}/clear`
- Confirm checkbox required (`confirm=true`); 400 without it.
- Deletes every `Response` row for the reviewer's assignments in
  this session. `submitted_at` goes with the rows (no zombie
  submitted state).
- Audit event `responses.cleared` with `detail = {deleted_count,
  session_id}`.
- 303 → review surface.

### 3.6 Autosave (deferred to follow-on PR)

Vanilla JS layered on top of `/save`. On `input` blur of any
form field, debounce 500 ms and POST the form silently. Show a
"Saved at HH:MM" timestamp; on failure, show a red banner
prompting the reviewer to use the manual Save Draft button.

Deferred reasons:

- Adds a JS dependency to a so-far-server-rendered codebase.
  Worth keeping isolated so the response-model PR stays focused.
- Parent plan §6.3 explicitly defers ("form post first, JSON
  autosave later").
- The MVP is usable without autosave; it's an enhancement.

### 3.7 Per-row completion indicator

Each reviewee row on the surface gets a small badge:

- **`✓ complete`** (green) — all required fields for this row
  have a non-empty saved value.
- **`N missing`** (amber) — at least one required field is empty.
- **`submitted at <time>`** suffix when the row's responses have
  `submitted_at` set.

Computed server-side at render time. No effect on save / submit
behaviour; it's purely informational.

### 3.8 Per-session dashboard indicator

`GET /reviewer` lists the user's reviewer-sessions. Each shows:

- Session name
- Deadline (if set; never enforced in this segment — late
  submission is out of scope per parent §3, and the operator
  open/close gate lands in Segment 9)
- Pill, computed from the reviewer's `Response` rows in that
  session:
  - `not started` — no `Response` rows.
  - `in progress` — at least one `Response` row, but at least
    one required-field row missing OR at least one row without
    `submitted_at`.
  - `submitted` — every required field across every visible
    assignment has a `Response` row with `submitted_at` set.

Editing a submitted required field down to empty (which deletes
the row, per §3.3) flips the pill back to `in progress` next
time the dashboard renders. That's the intended consequence of
making submission an attribute of `Response` rather than a
separate object.

Single-session shortcut not implemented (parent §11 §13 mentions
"may take them directly to the review surface" — left as polish
for later).

### 3.9 Default Instrument fields

Per Segment 7's `ensure_default_instrument`:

- `rating` — integer, required, validation `{"min": 1, "max": 5}`.
  Renders as `<input type="number" min="1" max="5">`.
- `comments` — long text, optional. Renders as `<textarea>`.

When operator instrument-builder ships (Segment 13), these become
the seed defaults the operator can rename / replace / extend.

### 3.10 No deadline enforcement

Deadline shows on dashboard for context only. Save / submit
always work regardless of deadline in this segment.
Late-submission policy is out of scope per parent §3. The
operator-controlled "stop accepting responses" gate lands in
Segment 9 (per-Instrument, not per-session).

### 3.11 Single instance only

If the same reviewer opens two browser tabs and saves
concurrently, last-write-wins on each `(assignment, field)`
cell. We accept this for MVP per parent §3 ("autosave conflict
handling out of scope"). Will revisit if a real conflict
materialises.

### 3.12 Cancel (revert in-progress edits)

A **Cancel** button sits next to Save draft. It is a no-op on
the server: it triggers a `GET` redirect back to the surface,
re-fetching the last-saved values from the DB. Any unsaved
changes in the inputs are discarded.

Implemented as a plain link (`<a href="/reviewer/sessions/{id}">Cancel</a>`),
not a form button — there's no state to mutate. No audit event;
nothing was written.

The button addresses a workflow gap: once a reviewer has
submitted, opening the surface and editing values dirties the
form even if they didn't intend to change anything. Cancel lets
them back out without having to remember the original values.

### 3.13 Roster status filter retrofit

`Reviewer` and `Reviewee` rows already carry a
`status: String(32)` defaulting to `"active"`. Today's
assignment generation does not filter on status — see
`app/services/assignments.py` `generate_full_matrix` and the
Manual CSV reference resolver. This segment adds:

- **FullMatrix generation** filters reviewers and reviewees on
  `status == "active"` before building pairs. Inactive rows
  are silently excluded; the audit detail's `excluded_counts`
  gains an `inactive_reviewer` / `inactive_reviewee` key when
  any are skipped.
- **Manual CSV import** treats a reference to an inactive
  reviewer or reviewee as an error (same shape as a reference
  to a missing row), so operators don't accidentally bring
  inactive participants back via CSV.
- **Reviewer dashboard** and `require_reviewer_in_session`
  filter on `status == "active"` (per §3.1).

There is no operator UI in this segment to flip a row's status —
status is always `"active"` today since CSV imports default to
it and there's no edit-row form. The filter is therefore
defensive against future operator actions (a roster-edit UI is
not yet planned). Tests assert the filter behaviour by setting
`status = "inactive"` directly in test fixtures.

---

## 4. File and folder layout

### Added in this PR

```text
app/
  schemas/
    responses.py                         # NEW: ResponseUpsert pydantic model

  services/
    responses.py                         # NEW: save / submit / clear /
                                         #      compute_row_completion
    assignments.py                       # MODIFIED: filter active rosters
                                         # in FullMatrix; treat inactive
                                         # refs as errors in Manual CSV

  web/
    deps.py                              # MODIFIED: add
                                         # require_reviewer_in_session
                                         # (active-only)
    routes_reviewer.py                   # NEW: /reviewer dashboard,
                                         # /reviewer/sessions/{id} surface,
                                         # save / cancel / clear / submit
    templates/
      reviewer/
        dashboard.html                   # NEW
        review_surface.html              # NEW
        review_submit_warning.html       # NEW (warn-and-override re-render
                                         #      can also live as a partial
                                         #      inside review_surface.html;
                                         #      decide during impl)

app/main.py                              # MODIFIED: include reviewer router

tests/
  unit/
    test_responses.py                    # NEW
    test_assignments_full_matrix.py      # MODIFIED: status-filter cases
    test_assignments_manual.py           # MODIFIED: inactive-ref error cases
  integration/
    test_reviewer_response_flow.py       # NEW
```

### Modified

```text
ARCHITECTURE.md                          # corrected line on
                                         # AssignmentContext visibility
docs/status.md                           # add reviewer surface to URL
                                         # table; new audit event types;
                                         # add PairContext1/2/3 to the
                                         # Manual CSV bullet
```

---

## 5. Routes

| Method | Path                                       | Auth          | What it does |
|--------|--------------------------------------------|---------------|--------------|
| GET    | `/reviewer`                                | reviewer      | Dashboard listing sessions where user is an active reviewer |
| GET    | `/reviewer/sessions/{id}`                  | active reviewer in session | Review surface (table). Cancel is a plain link back to this URL. |
| POST   | `/reviewer/sessions/{id}/save`             | active reviewer in session | Upsert draft responses; 303 → surface with `?saved=ok` |
| POST   | `/reviewer/sessions/{id}/submit`           | active reviewer in session | Upsert + validate + (warn or set submitted_at); 400 on missing-without-acknowledge, else 303 → surface with `?submitted=ok` |
| POST   | `/reviewer/sessions/{id}/clear`            | active reviewer in session | Delete all responses in this session for this reviewer; 303 → surface |

Form field names on save / submit: `response[<assignment_id>][<field_key>]`. The save service parses these into upserts.

---

## 6. Audit event shapes

```python
# Save draft (every successful save)
AuditEvent(
    event_type="responses.saved",
    severity="info",
    summary=f"Saved {count} responses (draft)",
    actor_user_id=user.id,
    session_id=session.id,
    detail={"session_id": session.id, "count": count, "reviewer_id": reviewer.id},
)

# Submit (every successful submit; whether or not warning was shown)
AuditEvent(
    event_type="responses.submitted",
    severity="info",
    summary=f"Submitted {count} responses ({missing} missing)",
    actor_user_id=user.id,
    session_id=session.id,
    detail={
        "session_id": session.id,
        "count": count,
        "missing_required_count": missing,
        "acknowledged_missing": bool(missing),  # true when override was used
        "reviewer_id": reviewer.id,
    },
)

# Clear all
AuditEvent(
    event_type="responses.cleared",
    severity="info",
    summary=f"Cleared {deleted_count} responses",
    actor_user_id=user.id,
    session_id=session.id,
    detail={"session_id": session.id, "deleted_count": deleted_count, "reviewer_id": reviewer.id},
)
```

Failed validation that returns 400 without saving = no audit
event (consistent with operator import flow's "failed parse
writes nothing").

---

## 7. Tests

Parent plan §10 lists 8 tests. This expands to 19 reviewer-flow
tests (with explicit coverage of warn-and-override, clear,
cancel, post-submit edit, and access-control URL hacking) plus
~4 retrofit tests in the existing assignment-generation suites.

### Unit (`tests/unit/test_responses.py`) — 6 tests

1. Empty form payload yields zero upserts.
2. Form payload with values upserts cleanly into new `Response`
   rows.
3. Re-saving the same form updates existing `Response` rows
   (no duplicates).
4. Empty value on a previously-saved field deletes the row.
5. `compute_row_completion` returns "complete" when all required
   filled, "N missing" otherwise.
6. Required-field validation returns the missing positions list
   with assignment id and field key.

### Integration (`tests/integration/test_reviewer_response_flow.py`) — 13 tests

7. Dashboard scoped to user's email — only sessions where an
   active `Reviewer.email` matches show up; inactive reviewer
   rows do not.
8. Surface renders assigned reviewees and Default Instrument
   fields; pair_context shown when set; tags/assignment_context
   hidden.
9. Surface filters out `Assignment.include = false` rows.
10. Save draft persists responses; reload shows them.
11. Submit with all required filled: succeeds, sets
    `submitted_at`, audit event written.
12. Submit with required missing and no acknowledge: 400 with
    re-rendered surface + warning card; nothing marked
    submitted; no audit event.
13. Submit with `acknowledge_missing=true`: succeeds; audit
    event records `missing_required_count > 0`.
14. Clear all with confirm: deletes all responses; audit.
15. Clear all without confirm: 400; nothing deleted.
16. Re-submit after edits refreshes `submitted_at`.
17. Cancel — `GET /reviewer/sessions/{id}` after dirtying inputs
    in another tab still renders last-saved values; no DB
    change; no audit.
18. Reviewer in Session A cannot view Session B's surface (URL
    hack returns 403).
19. Operator-only user (not an active reviewer in this session)
    gets 403 on the surface; an inactive `Reviewer` row also
    gets 403.

### Retrofit (existing files) — ~4 tests

20. (`tests/unit/test_assignments_full_matrix.py`) FullMatrix
    skips inactive reviewers; audit detail's
    `excluded_counts` includes `inactive_reviewer`.
21. (`tests/unit/test_assignments_full_matrix.py`) FullMatrix
    skips inactive reviewees; same audit shape.
22. (`tests/unit/test_assignments_manual.py`) Manual CSV
    referencing an inactive reviewer reports a row error
    (same shape as missing-roster-row).
23. (`tests/unit/test_assignments_manual.py`) Manual CSV
    referencing an inactive reviewee reports a row error.

That's 23 tests added by this PR. Parent plan §10 calls for 8.

---

## 8. Documentation

- `ARCHITECTURE.md`: correct the line about
  AssignmentContext visibility (was "stays invisible to
  reviewers"; should be "can be reviewer-visible if the
  operator opts in via `InstrumentDisplayField`").
- `docs/status.md`:
  - Add reviewer surface to capability list and URL table.
  - Add the three new audit event types (`responses.saved`,
    `responses.submitted`, `responses.cleared`) to the audit
    table.
  - Note autosave is a planned follow-on.
  - Add `PairContext1/2/3` to the Manual CSV bullet (drift fix
    — code and `docs/imports.md` already document it).
  - Note the active-only roster filter now applied to FullMatrix
    and Manual generation.

A new `docs/reviewer_surface.md` is **not** added in this
segment — the route table in §5 plus inline template comments
suffice. A user-facing reviewer guide can land alongside Segment
9 (invitations).

---

## 9. Out of scope (per parent plan §3 + new deferrals)

Carried over from parent plan:

- Polished AG Grid, multi-instrument tabs, autosave conflict
  handling, reminder emails, export generation, anonymous
  public access, complex late-submission policies.

Newly clarified deferrals:

| Item | Lands in |
|------|----------|
| Vanilla-JS autosave on top of `/save` | Follow-on PR after Segment 8 lands |
| `Response.saved_at` updated on each upsert (drives "last saved at HH:MM" UI) | Lands with autosave |
| Operator-controlled `InstrumentDisplayField` (which of the 9 fields show) | Segment 13 |
| AG Grid replacement of the plain table | Possible Segment 8 follow-on; not blocking |
| Single-session redirect from `/reviewer` | Polish, no specific segment |
| Operator-controlled per-Instrument open/close (the "stop accepting responses" gate, deadline-driven or manual) — per-Instrument, never per-session | Segment 9 |
| Operator UI to flip `Reviewer.status` / `Reviewee.status` | Not yet planned (filter in §3.13 is defensive) |
| Per-instrument tabs on the reviewer surface | Segment 13 |
| Pre-submit "preview my answers" page | Not planned; the warn-and-override surface already renders the form state |
| Explicit submission record (one per reviewer-session) instead of inferring from per-`Response.submitted_at` | Not planned; per §3.8 the inferred-pill behaviour is the intended contract |

---

## 10. Verification checklist

- [ ] `pytest` green locally (full suite, 23 new tests added by
  this PR).
- [ ] CI: `test`, `postgres-migration`.
- [ ] After merge: signed-in reviewer (email matches an active
  `Reviewer` row) lands on `/reviewer` and sees their session(s).
- [ ] Click into a session: surface renders rows for assigned
  reviewees with rating + comments inputs; pair_context shown
  if set.
- [ ] Save draft → reload → values still there.
- [ ] Cancel → discards in-progress edits; reload shows
  last-saved values.
- [ ] Submit with required missing → warning + acknowledge
  checkbox; tick + resubmit → marks submitted, dashboard shows
  "submitted" pill.
- [ ] Edit + re-submit → `submitted_at` refreshes (visible in
  audit log).
- [ ] Edit a submitted required field down to empty → row
  deletes; dashboard pill returns to "in progress".
- [ ] Clear all (with confirm) → all rows wiped; dashboard shows
  "not started".
- [ ] FullMatrix run with an inactive reviewer / reviewee in the
  roster excludes that participant; audit `excluded_counts`
  reflects it.
- [ ] Manual CSV referencing an inactive participant reports a
  row error.
- [ ] A reviewer in Session A typing Session B's URL gets 403.
- [ ] An operator-only user (no active `Reviewer` row in any
  session) gets `/reviewer` showing the empty state.

---

## 11. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Reviewer's saved values collide with another tab's saved values | Last-write-wins per `(assignment, field)`. Out of scope for proper conflict handling per parent §3. |
| Submit fires accidentally without acknowledging missing required | Warn-and-override pattern matches the operator replace guardrail. The acknowledge checkbox is a hard requirement. |
| A reviewer is in many sessions and the dashboard becomes long | Sessions list ordered by `updated_at desc`. No pagination yet; revisit if a real reviewer hits 50+ sessions. |
| Schema change in the placeholder Default Instrument breaks loaded forms mid-session | Segment 8 doesn't ship instrument editing; the seed fields are stable. Segment 13 will need to handle field add/remove against existing responses. |
| `pair_context` containing HTML / control characters renders unsafely | Jinja2 auto-escapes by default; we don't bypass it. |
| Autosave silently drops a save on network failure | Autosave is deferred entirely to a follow-on PR; the explicit Save Draft button is the canonical mechanism. |
| Reviewer matching by email mismatches across capitalization | `casefold()` comparison both ways (already the convention in `parse_manual_csv`). |

---

## 12. Done when

- Reviewer dashboard lists user's active-reviewer sessions with
  completion pills.
- Review surface renders rows with editable response fields.
- Save draft persists; reload shows saved values.
- Cancel reverts in-progress edits without writing.
- Submit with all required filled marks every response submitted
  and writes audit.
- Submit with missing required: 400 on first try; succeeds with
  acknowledge checkbox.
- Clear all wipes responses with confirm.
- FullMatrix and Manual generation respect roster `status`.
- All 23 new tests pass; full suite green.

Next segment after this PR merges: **Segment 9 — Activation,
invitations, monitoring, reminders, and per-Instrument
open/close**.
