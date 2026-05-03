# Segment 10B-3 Implementation Plan — Operator preview route

**Status:** Plan drafted — decisions locked, slice breakdown below.
Last of three PR-sized blocks for Segment 10B (display-fields picker
+ operator preview). See `guide/segment_10B.md` for the umbrella stub
that breaks 10B into 10B-1 / 10B-2 / 10B-3, and
`guide/archive/segment_10_instrument_builder_mvp_plan.md` §14 for the
segment-level split. 10B-3 follows 10B-1 (data-driven render) and
10B-2 (operator builder).

- **10B-1 (shipped before this):** Alembic backfill, reviewer-surface
  refactor to render from `InstrumentDisplayField`, identity column,
  default-label inference. Behavior-preserving.
- **10B-2 (shipped before this):** display-field picker UI + shared
  bulk "field order & visibility" form, invalidation +
  locked-when-ready gating, four new audit events.
- **10B-3 (this doc):** `GET /operator/sessions/{id}/preview` —
  read-only render of the reviewer surface with synthetic rows where
  needed, all inputs disabled, "Preview — not visible to reviewers"
  banner. Operator-only. Bypasses deadline / acceptance gates. Works
  in any session status.

---

## 10B-3 outcome

One PR that ships:

- A new operator route `GET /operator/sessions/{id}/preview` that
  renders the reviewer-surface template with three rows (real
  assignments where possible, synthetic placeholders to fill).
- A small synthetic-row helper that builds plausible placeholder
  values per display-field source.
- A reviewer-surface template branch (or thin wrapper template) that
  disables every input, hides save / submit / clear forms, and
  renders the "Preview — not visible to reviewers" banner.
- Operator chrome / breadcrumbs wired through the preview page (a
  `Sessions / {session} / Preview` trail or equivalent).

No data mutations. No new audit events. No reviewer-facing change.

---

## Decisions locked for 10B-3

### D8 — Preview row population

`GET /operator/sessions/{id}/preview` renders the reviewer surface
template with **three rows**:

- If the session has at least three assignments, use the first three
  by `Assignment.id` ascending.
- If 1–2 assignments exist, use those plus enough synthetic rows to
  reach three.
- If zero assignments exist, render three synthetic rows.

Synthetic row shape: reviewee name `"Sample Reviewee 1"` /
`"Sample Reviewee 2"` / `"Sample Reviewee 3"`, email
`"sample1@example.edu"` etc., display-field cells filled with
plausible placeholder values per source (`"Sample tag value"` for
reviewee tags, `"Sample pair context"` for pair contexts,
`"https://example.edu/sample-profile"` for `profile_link`), response
cells empty.

### D9 — Preview gating

`GET /operator/sessions/{id}/preview` is operator-only (gated on
`require_session_operator`) and works in **any** session status
(`draft` / `validated` / `ready`).

- **Bypasses** the reviewer-surface deadline / acceptance gate.
- All inputs render disabled (`disabled` attribute on every input,
  textarea, select).
- No save / submit / clear forms reachable on the preview surface.
- Renders a "Preview — not visible to reviewers" banner at the top.
- Read-only: does **not** invalidate (no `_invalidate_if_validated`
  call), does **not** emit audit events.

### D9.1 — Reviewer-surface template reuse

The preview page reuses the existing reviewer-surface template. The
"disabled inputs + banner + no forms" mode is driven by a single
template flag (e.g. `preview_mode=True`) passed in the route's
context dict. No template fork. The flag:

- Wraps every form-control element with `disabled` (or skips them
  entirely for save / submit / clear buttons).
- Renders the banner above the per-instrument loop.
- Suppresses the `<form>` wrapper around the table (or wraps it in a
  no-op anchor) so accidental keypresses don't navigate.

The reviewer-surface section heading and per-field help block from
10A keep their existing renders under the flag.

### D9.2 — Preview link entry point

The preview page is reachable from `/operator/sessions/{id}/instruments`
(a "Preview reviewer surface" anchor on the page header) and from
the session detail's Run Session card (alongside Validate / Manage
Invitations / Extract). Both anchors land on the same
`/operator/sessions/{id}/preview` URL; no query-string variants in
10B-3.

---

## Audit events added in 10B-3

None. Preview is read-only by D9.

---

## Out of scope for 10B-3 (explicitly deferred)

- Alembic backfill, reviewer-surface refactor, identity column,
  default-label inference → already shipped in 10B-1 (prerequisite).
- Display-field picker UI, row-level / bulk POSTs, audit events,
  invalidation + locked-when-ready gating → already shipped in 10B-2
  (prerequisite).
- Anonymous / shareable preview link — preview is operator-only and
  gated on `require_session_operator`.
- Synthetic-row sample data customization (operator-controlled
  placeholder values) — fixed strings per D8.
- Print / PDF preview, "open in new tab as a reviewer" simulation
  with a logged-in reviewer identity — out of scope.
- `spec/target_operator_map.md` rewrite → separate post-10B PR per
  10B D12.

---

## Implementation slices

### Slice 1 — Synthetic-row helper + preview view-shape builder

New module-level additions to `app/web/routes_reviewer.py` (or a
small split-out `app/web/preview.py` if the route file gets too
busy — pick at implementation time; the helper is pure-Python view
shaping and doesn't touch service modules):

- `_SYNTHETIC_VALUES_BY_SOURCE: dict[tuple[str, str], str]` — a
  module-level constant mapping each of the seven D6 source pairs
  to its sample placeholder per D8:
  - `("reviewee", "tag_1" | "tag_2" | "tag_3")` → `"Sample tag value"`.
  - `("reviewee", "profile_link")` → `"https://example.edu/sample-profile"`.
  - `("pair_context", "1" | "2" | "3")` → `"Sample pair context"`.
- `_make_synthetic_row(*, instrument, index, response_fields,
  display_fields)` — builds the same row dict shape that
  `_surface_context` produces for a real assignment, using
  `types.SimpleNamespace` to mimic attribute access on the
  `assignment` / `assignment.reviewee` references the template
  reads:
  - `assignment.id = -(index + 1)` (negative IDs to guarantee no
    collision with real `Assignment.id`s; the IDs are decorative
    in preview because the form wrapper is suppressed in Slice 3,
    but template references like `row.assignment.id` still need
    *something* hashable).
  - `assignment.reviewee.name = f"Sample Reviewee {index + 1}"`,
    `email_or_identifier = f"sample{index + 1}@example.edu"`.
  - `display_cells` populated by looking up
    `_SYNTHETIC_VALUES_BY_SOURCE[(df.source_type, df.source_field)]`
    for each visible display field on the instrument. `is_profile_link`
    follows the existing predicate from Slice 3 of 10B-1.
  - `cells` (response cells) set with `value=""` for every response
    field on the instrument — empty drafts.
  - `accepting=False` so the existing template branch on
    `disabled_attr = "" if row.accepting else "disabled"`
    automatically renders every `<input>` / `<textarea>` /
    `<select>` with the `disabled` attribute. This means **no new
    template logic for input disabling** — Slice 3 only needs the
    banner + hide save/submit/clear/cancel forms.
  - `is_complete=False`, `missing_count=0`, `submitted_at=None`,
    `show_values=True`.
- `build_preview_context(*, db, user, review_session,
  request_path) -> dict` — the operator-side mirror of
  `_surface_context`. Steps:
  1. Resolve the session's instruments via the existing
     `_instruments_for_session` helper (reuses the eager-load and
     query shape from 10B-1).
  2. For each instrument, eager-load `display_fields` (visible
     only, `order ASC`) and `response_fields` (`order ASC`)
     mirroring `_surface_context`'s queries.
  3. Pull up to **three real assignments** for the session (across
     all instruments, ordered by `Assignment.id ASC`,
     `include=True`). Use the existing
     `_load_assignments_with_relations`-style query but **drop the
     `reviewer_id` filter** (operator preview is reviewer-agnostic).
  4. For each real assignment: build the row dict using the
     **same** loop body as `_surface_context` — pull the matching
     `display_cells` via `instruments_service.display_field_value` /
     `display_field_label`, build empty `cells` (no `Response`
     lookup; preview is read-only and operator-side) — and
     **force `accepting=False`** so inputs render disabled per D9.
  5. If fewer than three real rows, pad with
     `_make_synthetic_row(...)` calls for the remaining slots,
     anchored to the first / only instrument (single-instrument
     today; multi-instrument is Segment 13). Synthetic rows attach
     to whichever instrument hosts the first real row, or to the
     session's first instrument when no real assignments exist.
  6. Build `instrument_groups` from the merged real + synthetic
     rows, mirroring `_surface_context`'s `heading` /
     `help_block_items` / `display_fields` shape.
  7. Return the full context dict including a new `preview_mode:
     True` flag, a `breadcrumbs` trail
     (`operator_session_child(review_session, "Preview")`), and
     **explicit `False` values** for `any_accepting` / `saved` /
     `submitted` / `show_acknowledge` so the existing template
     branches that gate save / submit / acknowledge UIs stay
     hidden by construction (Slice 3 wraps them anyway, but two
     belts beats one).

The helper is pure-Python — no DB writes, no audit. Per D9 it does
**not** call `_invalidate_if_validated` and does **not** observe the
deadline. (`lifecycle.observe_deadline` would side-effect the DB on
a deadline crossing, which preview must not do.)

### Slice 2 — Operator preview route

In `app/web/routes_operator.py`:

- New route
  ```python
  @router.get("/sessions/{session_id}/preview", response_class=HTMLResponse)
  def session_preview(
      request: Request,
      review_session: ReviewSession = Depends(require_session_operator),
      user: User = Depends(get_or_create_user),
      db: Session = Depends(get_db),
  ) -> HTMLResponse:
  ```
  Imports `build_preview_context` from `routes_reviewer.py` (or
  the new `preview.py` if extracted). Renders
  `reviewer/review_surface.html` directly — the template is
  shared between reviewer and preview surfaces, gated only by the
  `preview_mode` flag.
- `breadcrumbs.operator_session_child(review_session, "Preview")`
  for the trail.
- **No** `lifecycle.observe_deadline` call (D9: bypass deadline).
- **No** reviewer-identity check (D9: operator-only via
  `require_session_operator`).
- Operator URL surface: this is the only new route in 10B-3.

Two operator-side anchors per D9.2:

- `app/web/templates/operator/instruments_index.html` — page
  header gains an inline link
  `<a href="/operator/sessions/{id}/preview" class="btn secondary">
  Preview reviewer surface</a>`. Always enabled (operator-only,
  works in any status).
- `app/web/templates/operator/session_detail.html` — Run Session
  card gains a fourth anchor alongside Validate / Manage
  Invitations / Extract. Same enabled-in-any-status semantics.

Both anchors land on the same URL; no query-string variants.

### Slice 3 — Template flag + banner + form suppression

Edit `app/web/templates/reviewer/review_surface.html` to thread
the `preview_mode` flag through the existing template:

- **Banner.** At the very top of the `{% block content %}` body,
  before the `<h1>`:
  ```jinja
  {% if preview_mode %}
    <div class="warning-banner" style="background: #dbeafe; border-color: #2563eb; color: #1e3a8a;">
      <strong>Preview</strong> — not visible to reviewers.
      This page is operator-only and bypasses session-status /
      deadline / acceptance gates.
    </div>
  {% endif %}
  ```
  Reuses the existing `.warning-banner` class with an info-style
  override. No new CSS rule required.
- **Form suppression.** Wrap each of the four reviewer write-path
  affordances in `{% if not preview_mode %}…{% endif %}`:
  - The Save / Submit `<button>`s + acknowledge checkbox.
  - The `<form action=".../save">` itself (so neither button can
    be re-targeted via `formaction`).
  - The "Clear all responses" card.
  - The "Cancel — discard unsaved edits" anchor.
  Note: the existing template **already** wraps Save / Submit /
  Cancel / Clear in `{% if any_accepting %}` branches; the
  preview helper (Slice 1) sets `any_accepting=False`, so those
  branches are already skipped. The `{% if not preview_mode %}`
  wrapper is a redundant safety belt against a future edit that
  decouples those flags (e.g. Segment 14 might surface a
  "preview-with-real-state" mode).
- **Existing input disabling.** Each `<input>` / `<textarea>` /
  `<select>` already renders with `disabled_attr` derived from
  `row.accepting`. Slice 1 sets `accepting=False` on every
  preview row, so this works without further template changes.
  No need to add `{% if preview_mode %}disabled{% endif %}`
  attributes per input — D9.1's "single template flag" stays a
  single flag.
- **Reviewer-side regression check.** Add an integration test
  case (Slice 4 #6) asserting that the existing reviewer surface
  (`GET /reviewer/sessions/{id}` from a real reviewer) still
  shows the Save / Submit buttons under `any_accepting=True`,
  with no `preview_mode` flag set in context.

### Slice 4 — Tests

Aim for ~6 cases in one new file plus targeted add-ons. Unit-test
the synthetic-row helper in isolation; integration-test the route
end-to-end.

**Unit (`tests/unit/test_preview_helper.py`)**

1. `_make_synthetic_row(index=0, …)` returns a row whose
   `assignment.reviewee.name == "Sample Reviewee 1"`, `email ==
   "sample1@example.edu"`, `display_cells` filled with the per-
   source placeholder strings, `cells` empty-valued, and
   `accepting=False`.
2. `build_preview_context` on a session with **zero** assignments
   returns a context whose `instrument_groups[0].rows` has length
   3 and every row is synthetic (negative `assignment.id`).
3. `build_preview_context` on a session with **one** real
   assignment returns one real row (positive `assignment.id`)
   followed by two synthetic rows.
4. `build_preview_context` on a session with **five** real
   assignments returns three rows, all real, ordered by
   `Assignment.id ASC`. Padding is not used.

**Integration (`tests/integration/test_preview_route.py`)**

5. `GET /operator/sessions/{id}/preview` returns 200 for the
   session operator; the body contains the banner text
   "Preview — not visible to reviewers" and the page heading
   `<h1>{{ session.name }}</h1>`. Works with the session in
   `draft` status (assert before any activate call).
6. `GET /operator/sessions/{id}/preview` works in `validated` and
   `ready` status too (D9 — works in any session status). For
   the `ready` case, no `instrument.opened` audit event is
   emitted (preview is read-only).
7. `GET /operator/sessions/{id}/preview` returns **403** for a
   non-operator user (existing `require_session_operator` gate).
8. The preview body contains **zero** `<form action=` references
   to the reviewer write-path endpoints (`/save`, `/submit`,
   `/clear`) regardless of `any_accepting` — guards against a
   future template edit dropping the suppression.
9. Every `<input>`, `<textarea>`, and `<select>` in the preview
   body carries the `disabled` attribute. (Use a regex grep on
   the response body: every input-like element should match
   `\s+disabled\b`.)
10. Reviewer-side regression: `GET /reviewer/sessions/{id}` from
    the assigned reviewer on a `ready` session still shows the
    Save / Submit buttons and zero "Preview — not visible to
    reviewers" banner text. (Pairs with Slice 3's note about
    keeping the reviewer-side write-path intact.)

`tests/integration/test_preview_route.py` reuses the
`_make_session` / `_populate_rosters` / `_generate_full_matrix`
helpers from `test_display_field_routes.py` — **factor them into a
shared `tests/integration/_helpers.py`** at this slice point if
the duplication count crosses ~3 files (10A's
`test_instrument_builder_routes.py`, 10B-2's
`test_display_field_routes.py`, and 10B-3's new test file would be
the third). Otherwise inline the copies and clean up later.

---

## Docs to update at PR time

- `docs/status.md`:
  - Timeline row: `2026-04-NN | Segment 10B-3 shipped (operator
    preview route)`. After this row lands, **mark Segment 10B as
    a whole complete** by adding a final 10B summary row in the
    Segments-shipped table that names all three sub-segments.
    The "As of:" header bumps to "end of Segment 10B".
  - Segments-shipped row: `10B-3 | New
    GET /operator/sessions/{id}/preview route renders the reviewer
    surface in operator-only preview mode — pads with up to three
    synthetic rows when fewer real assignments exist; bypasses
    deadline / acceptance / status gates; all inputs render
    disabled; save / submit / clear / cancel forms suppressed;
    "Preview — not visible to reviewers" banner at the top. Two
    operator-side entry-point anchors: instruments page header and
    session detail's Run Session card. No new audit events
    (read-only). | <date>`.
  - Operator URL table: add `GET /operator/sessions/{id}/preview`.
  - "What's deliberately not yet there": remove the 10B-3 preview
    row entirely.
  - Audit table: no change (preview is read-only).
- `AGENTS.md`: bump "Current segment" pointer from 10B-3
  (planned) to a post-10B state — natural choice is naming
  Segment 11 (export / audit retention) as the next plan-target,
  or leaving the pointer empty until the next segment is picked.
  Pick at PR time.
- `spec/target_operator_map.md`: per umbrella D12, the rewrite
  lands as a **separate post-10B PR** after 10B-3 merges. **Not
  edited here.**
- `spec/operator_map.md` (as-is map): refresh to add the preview
  route alongside the existing `/instruments` page. Per the
  10B-2 PR's deferred-doc note, this regen lands here at the end
  of 10B (the only sub-PR that hadn't yet refreshed it).
- `README.md`: only if a tooling / dependency change ships in
  10B-3 (none expected — pure-Python view shaping + template
  flag).

---

## Risk notes

- **`SimpleNamespace` vs ORM divergence.** The synthetic rows use
  `types.SimpleNamespace` to mimic attribute access on
  `assignment.reviewee.name` etc. The template currently reads
  only a small fixed set of attributes (name, email_or_identifier,
  id), so this is safe — but a future template edit that adds a
  new reference (e.g. `row.assignment.reviewer.name`) would
  silently `AttributeError` only on synthetic rows. Mitigation:
  add a comment on `_make_synthetic_row` listing the attributes
  the synthetic shape exposes; Slice 4 #5 + #2 catch any drift
  on the next test run.
- **Deadline-observation side-effects.** `_surface_context` calls
  `lifecycle.observe_deadline` which **mutates the DB** on a
  deadline crossing (closes instruments, stamps
  `deadline_closed_at`, audits `instrument.closed
  reason=deadline`). The preview helper deliberately skips this
  call (D9 — bypass deadline). Document the omission in the
  helper's docstring; otherwise a casual reader copy-pasting from
  `_surface_context` could re-introduce the side-effect.
- **Synthetic IDs colliding with real ones.** Negative
  `assignment.id`s avoid collisions with real `Assignment.id`s
  (which are positive autoincrement integers). The template uses
  the id only in form input names like
  `name="response[{{ row.assignment.id }}][...]"` — preview
  suppresses the form wrapper so these inputs are never
  submittable, but the markup still renders. Negative ids in
  form-name strings are valid HTML; the only risk is a future
  parser reading these names. Lock at implementation time and
  document.
- **Two operator anchors, one URL.** D9.2 wires anchors on both
  `/instruments` and `session_detail`. If a user bookmarks one
  and the other moves (Segment 13's multi-instrument might
  rearrange the page header), the URL stays stable — the helper
  is on a per-session path, not a per-instrument path. No risk
  beyond docs lag.
- **Reviewer-side regression.** Slice 3 wraps four template
  blocks in `{% if not preview_mode %}…{% endif %}`. Slice 4
  case #10 explicitly asserts the reviewer-side path still
  renders Save / Submit / Clear / Cancel — without that guard,
  a missing closing `{% endif %}` could silently strip the
  reviewer write-path on `ready` sessions and the test suite
  would still pass on the reviewer flow tests in
  `test_reviewer_response_flow.py` only if those don't check
  every form. Add the regression test even though it sits
  outside the new file.
- **Eager-load count.** `build_preview_context` queries
  instruments + display_fields + response_fields + up-to-3
  assignments for the session. Today's session has N=1
  instrument so the load count is ~4 queries — fine. Multi-
  instrument support (Segment 13) raises this; the eager-load
  shape mirrors `_surface_context`'s already-acceptable cost.
- **Preview link entry points may be invisible until the docs
  refresh.** Slice 2 adds anchors on two operator pages; the
  `/instruments` page anchor lands in this PR's diff but the
  `session_detail.html` anchor sits inside the four-card
  Run Session bullet list, where Slices have varied edits over
  9.4B / 9.4C / 10A / 10B-2. Verify the anchor placement against
  the current `session_detail.html` shape in the implementation
  PR; the slice plan may need a small re-aim if the Run Session
  card has reshaped further.
