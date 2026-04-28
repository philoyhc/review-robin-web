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
  authenticated user's email matches a `Reviewer` row.
- Review surface at `/reviewer/sessions/{id}` renders all of the
  reviewer's assignments (excluding `include = false`) as a
  plain HTML table. Each row carries the Default Instrument's
  response fields as inputs.
- Three actions: **Save draft**, **Clear all** (with confirm),
  **Submit** (with required-field warn-and-override).
- Per-row completion indicator on the surface.
- Per-session completion indicator on the dashboard.

---

## 2. Branch and PR strategy

**One PR** against `main`: `claude/segment-8-reviewer-surface`.

The dashboard, review surface, save / clear / submit endpoints,
and tests are tightly coupled. Splitting produces awkward partial
states. Estimated ~600–700 LOC.

**Autosave is deferred** to a small follow-on PR (vanilla JS over
the same `/save` endpoint). Reasons in §3.5.

---

## 3. Decisions

### 3.1 Identity matching

The authenticated user is matched to `Reviewer` rows by
case-insensitive email equality. A user can be a reviewer in N
sessions; the dashboard lists all of them.

The new dependency `require_reviewer_in_session(session_id)` —
analogous to `require_session_operator` from 6A — looks up the
`Reviewer` row matching the user's email in that session and
returns `(reviewer, review_session)`. Returns **403** if no
matching reviewer row.

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
visibility lands in Segment 12.

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
     "Dan — `rating`"), and a hidden `acknowledge_missing=true`
     checkbox the reviewer must tick to retry.
3. If all required fields are filled, **or** the form was
   submitted with `acknowledge_missing=true`:
   - All `Response` rows for the reviewer's assignments in this
     session get `submitted_at = now()`.
   - 303 → review surface with `?submitted=ok` toast.
   - Audit event `responses.submitted` with `detail = {count,
     missing_required_count, session_id}`.

After submit, the reviewer can keep editing (Save draft updates
values; re-submit refreshes `submitted_at`). When **per-instrument
closure** lands in Segment 9, save / submit on a *closed*
instrument's fields will be blocked at the route layer. There is
no session-level closure — the response window is owned by each
Instrument, not by the session as a whole, so different
instruments can close on different schedules (relevant once
multi-instrument ships in Segment 12).

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
- Deadline (if set; never enforced — late submission is out of
  scope per parent §3)
- Pill: `not started` (no responses) / `in progress` (some
  responses, none submitted) / `submitted` (all required filled
  and submitted_at set).

Single-session shortcut not implemented (parent §11 §13 mentions
"may take them directly to the review surface" — left as polish
for later).

### 3.9 Default Instrument fields

Per Segment 7's `ensure_default_instrument`:

- `rating` — integer, required, validation `{"min": 1, "max": 5}`.
  Renders as `<input type="number" min="1" max="5">`.
- `comments` — long text, optional. Renders as `<textarea>`.

When operator instrument-builder ships (Segment 12), these become
the seed defaults the operator can rename / replace / extend.

### 3.10 No deadline enforcement

Deadline shows on dashboard for context only. Save / submit
always work regardless of deadline. Late-submission policy is
out of scope per parent §3.

Once Segment 9 ships **per-instrument** open/close, save and
submit on a closed instrument's fields get blocked at the route
layer.

### 3.11 Single instance only

If the same reviewer opens two browser tabs and saves
concurrently, last-write-wins on each `(assignment, field)`
cell. We accept this for MVP per parent §3 ("autosave conflict
handling out of scope"). Will revisit if a real conflict
materialises.

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

  web/
    deps.py                              # MODIFIED: add
                                         # require_reviewer_in_session
    routes_reviewer.py                   # NEW: /reviewer dashboard,
                                         # /reviewer/sessions/{id} surface,
                                         # save / clear / submit
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
  integration/
    test_reviewer_response_flow.py       # NEW
```

### Modified

```text
ARCHITECTURE.md                          # corrected line on
                                         # AssignmentContext visibility
docs/status.md                           # add reviewer surface to URL
                                         # table; new audit event types
```

---

## 5. Routes

| Method | Path                                       | Auth          | What it does |
|--------|--------------------------------------------|---------------|--------------|
| GET    | `/reviewer`                                | reviewer      | Dashboard listing sessions where user is a reviewer |
| GET    | `/reviewer/sessions/{id}`                  | reviewer in session | Review surface (table) |
| POST   | `/reviewer/sessions/{id}/save`             | reviewer in session | Upsert draft responses; 303 → surface with `?saved=ok` |
| POST   | `/reviewer/sessions/{id}/submit`           | reviewer in session | Upsert + validate + (warn or set submitted_at); 400 on missing-without-acknowledge, else 303 → surface with `?submitted=ok` |
| POST   | `/reviewer/sessions/{id}/clear`            | reviewer in session | Delete all responses in this session for this reviewer; 303 → surface |

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

Parent plan §10 lists 8 tests. This expands to ~14, with explicit
coverage of warn-and-override, clear, post-submit edit, and
access-control URL hacking.

### Unit (`tests/unit/test_responses.py`)

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

### Integration (`tests/integration/test_reviewer_response_flow.py`)

7. Dashboard scoped to user's email — only sessions where a
   `Reviewer.email` matches show up.
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
17. Reviewer in Session A cannot view Session B's surface (URL
    hack returns 403).
18. Operator-only user (not a reviewer in this session) gets
    403 on the surface.

That's 18 tests. Parent plan §10 calls for 8; the extras
exercise the new clear flow, the warn-and-override path, the
post-submit-edit invariant, and access-control corners.

---

## 8. Documentation

- `ARCHITECTURE.md`: correct the line about
  AssignmentContext visibility (was "stays invisible to
  reviewers"; should be "can be reviewer-visible if the
  operator opts in via `InstrumentDisplayField`").
- `docs/status.md`: add reviewer surface to capability list and
  URL table; add the three new audit event types to the audit
  table; note autosave is a planned follow-on.

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
| Operator-controlled `InstrumentDisplayField` (which of the 9 fields show) | Segment 12 |
| AG Grid replacement of the plain table | Possible Segment 8 follow-on; not blocking |
| Single-session redirect from `/reviewer` | Polish, no specific segment |
| Per-instrument response window (open / close) and post-close edit lock — closure is per-Instrument, never per-session | Segment 9 |
| Per-instrument tabs on the reviewer surface | Segment 12 |
| Pre-submit "preview my answers" page | Not planned; the warn-and-override surface already renders the form state |

---

## 10. Verification checklist

- [ ] `pytest` green locally (101 existing + ~17 new = 118 minimum).
- [ ] CI: `test`, `postgres-migration`.
- [ ] After merge: signed-in reviewer (email matches a `Reviewer`
  row) lands on `/reviewer` and sees their session(s).
- [ ] Click into a session: surface renders rows for assigned
  reviewees with rating + comments inputs; pair_context shown
  if set.
- [ ] Save draft → reload → values still there.
- [ ] Submit with required missing → warning + acknowledge
  checkbox; tick + resubmit → marks submitted, dashboard shows
  "submitted" pill.
- [ ] Edit + re-submit → `submitted_at` refreshes (visible in
  audit log).
- [ ] Clear all (with confirm) → all rows wiped; dashboard shows
  "not started".
- [ ] A reviewer in Session A typing Session B's URL gets 403.
- [ ] An operator-only user (no `Reviewer` row in any session)
  gets `/reviewer` showing the empty state.

---

## 11. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Reviewer's saved values collide with another tab's saved values | Last-write-wins per `(assignment, field)`. Out of scope for proper conflict handling per parent §3. |
| Submit fires accidentally without acknowledging missing required | Warn-and-override pattern matches the operator replace guardrail. The acknowledge checkbox is a hard requirement. |
| A reviewer is in many sessions and the dashboard becomes long | Sessions list ordered by `updated_at desc`. No pagination yet; revisit if a real reviewer hits 50+ sessions. |
| Schema change in the placeholder Default Instrument breaks loaded forms mid-session | Segment 8 doesn't ship instrument editing; the seed fields are stable. Segment 12 will need to handle field add/remove against existing responses. |
| `pair_context` containing HTML / control characters renders unsafely | Jinja2 auto-escapes by default; we don't bypass it. |
| Autosave silently drops a save on network failure | Autosave is deferred entirely to a follow-on PR; the explicit Save Draft button is the canonical mechanism. |
| Reviewer matching by email mismatches across capitalization | `casefold()` comparison both ways (already the convention in `parse_manual_csv`). |

---

## 12. Done when

- Reviewer dashboard lists user's sessions with completion pills.
- Review surface renders rows with editable response fields.
- Save draft persists; reload shows saved values.
- Submit with all required filled marks every response submitted
  and writes audit.
- Submit with missing required: 400 on first try; succeeds with
  acknowledge checkbox.
- Clear all wipes responses with confirm.
- All 18 tests pass; CI green.

Next segment after this PR merges: **Segment 9 — Invitation,
monitoring, and reminder MVP**.
