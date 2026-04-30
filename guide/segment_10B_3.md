# Segment 10B-3 Implementation Plan — Operator preview route

**Status:** Stub — decisions locked, slice breakdown still to be drafted.
Last of three PR-sized blocks for Segment 10B (display-fields picker
+ operator preview). See `guide/segment_10B.md` for the umbrella stub
that breaks 10B into 10B-1 / 10B-2 / 10B-3, and
`guide/segment_10_instrument_builder_mvp_plan.md` §14 for the
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

## To draft next

This stub locks the decisions for 10B-3. The implementation slice
breakdown (parallel to `segment_10A.md` Slices 1–5: route +
synthetic-row helper → template flag → tests) is **not yet drafted**
and is the next deliverable on this branch.
