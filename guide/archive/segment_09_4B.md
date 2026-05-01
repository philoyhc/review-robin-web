# Segment 9.4B Implementation Plan — Session detail four-card restructure + inline validate-summary + Delete Data

**Status:** Draft in progress — locked decisions recorded, slice plan not yet written. Second of three PR-sized blocks for Segment 9.4 (operator UI restructure to the target page map). Sits between 9.4A (shipped) and 9.4C (not yet drafted).

- **9.4A (shipped):** chrome, breadcrumbs, `/about`, sessions list reshape.
- **9.4B (this doc):** session detail four-card restructure + inline validate-summary card + `Delete Data`.
- **9.4C (next):** reviewers / reviewees / assignments Manage page reshapes, instruments index, `/setupinvite` + `/extract` stubs, closing-segment doc + spec refresh.

See `segment_09_4_operator_ui_restructure_plan.md` for the segment-level plan and `spec/target_operator_map.md` for the design target.

---

## Decisions locked for 9.4B

1. **Setup table helper lives in `app/web/views.py`** (new module, view-shape adapter co-located with the route). Returns the row tuples `[(label, count_or_status, manage_url, optional_delete_url, ...)]` consumed by `session_detail.html`. Service modules stay business-logic-only.
2. **Setup table rows for 9.4C-only surfaces render disabled.** Both **Instruments** (collapsed → `/instruments` index) and **Set up invites** (`/setupinvite`) render in the table now, with their Manage buttons disabled and a "lands in 9.4C" tooltip. Preserves the visual shape so 9.4C is purely additive lighting-up of buttons.
3. **Validate-on-session-detail = query-param branch on the existing `GET /operator/sessions/{id}?validated=1`.** The Validate Session Setup button on the Run Session card is a plain anchor to that URL; the GET re-runs validation when `validated` is truthy and renders the inline summary card above the Run Session card. No new route. Sticky for that response only — refresh without the param loses the card. The existing `/validate` GET stays unchanged (its only edit in 9.4B is removing the activate form, see #4).
4. **`/validate` becomes read-only.** The activate form is removed from `session_validate.html`; the page stays as the "View detailed validation" deep-dive target. Activation is single-source: only on the inline summary card.
5. **Danger zone = one card, two stacked confirm-checkbox forms.** Delete data form sits above Delete session form inside the existing Danger zone card. Default button label: **Delete data** (matches plan wording). Audit event: `responses.deleted_all` with `detail = {"deleted_count": N}`. Allowed in any session status (including ready).
6. **Edit-lock semantics in 9.4B = unchanged from today.** Setup-card Manage links stay clickable when `status="ready"` (read-only nav, today's behaviour). **Edit details** on the Session card is hidden when ready. **Revert to draft** appears as a contextual button on the Session card when ready. **Delete Session** in Danger zone is disabled when ready (today's "deletion locked while ready" message). **Delete Data** is allowed in any status, including ready. The richer lifecycle (a new stored `validated` state between `draft` and `ready`) is deferred to its own segment — see "Deferred to Segment 9.5" below.

---

## Deferred to Segment 9.5 — Setup-readiness lifecycle states

Locked here so 9.4B's UI doesn't paint itself into a corner. **Not implemented in 9.4B.** Segment 9.5 will add a new stored state `validated` to the existing `SessionStatus` enum and rewire the activation flow against it.

- **D1 — `validated` is a stored state**, not derived. Sticky across renders so the inline summary card has a real home (rather than one-shot per validate POST).
- **D2 — Invalidation triggers (`validated → draft`):** every setup-mutating route that can affect validation outcome. Today's set: reviewer import + delete-all, reviewee import + delete-all, assignment generate + delete-all, session edit (name/code/description/deadline). Instrument open/close/visibility do **not** invalidate (they don't change validation results).
- **D3 — Acknowledge-warnings is implicit in `validated`.** Entering the `validated` state means "no blocking conditions" — warnings, if any, are acknowledged at the moment of transition. No separate `warnings_acknowledged_at` column.
- **D4 — Revert from `ready` lands on `draft`**, not `validated`. Forces the operator to re-run validation before the next activation.
- **D5 — "Locked but invalid" is unreachable.** Activation requires `can_activate` (no errors); revert always drops to `draft`. No transition reaches "locked + invalid."
- **D6 — Scope split.** 9.4B ships against today's two-state semantics (`draft`/`ready`); 9.5 introduces `validated` and rewrites every mutating route's invalidation hook. Keeps 9.4B's diff focused on UI restructure.

Full-state target after 9.5: `draft` → `validated` → `ready` → `expired` (Segment 9.3+) → `archived` (Segment 11+).

---

## Implementation slices

### Slice 1 — Setup-table view helper + four-card session detail shell

- New module `app/web/views.py` with `build_setup_rows(session, db) -> list[SetupRow]` returning a row per setup target. Today's rows:
  - `Reviewers` — count, Manage → `/operator/sessions/{id}/reviewers`, enabled.
  - `Reviewees` — count, Manage → `/operator/sessions/{id}/reviewees`, enabled.
  - `Instruments` — collapsed status (single instrument's `accepting_responses` pill), Manage → `/operator/sessions/{id}/instruments`, **disabled** with tooltip "Lands in 9.4C" per Decision 2.
  - `Assignments` — count, Manage → `/operator/sessions/{id}/assignments`, enabled.
  - `Set up invites` — fixed status text, Manage → `/operator/sessions/{id}/setupinvite`, **disabled** with tooltip "Lands in 9.4C".
- `routes_operator.py` session-detail GET adds `setup_rows` to the template context. Existing context (session, can_activate, edit-lock flags, etc.) is preserved.
- Rewrite `session_detail.html` body into four cards stacked vertically:
  1. **Session** — name, code, deadline, description, status pill. **Edit details** button hidden when `status="ready"` (Decision 6). **Revert to draft** contextual button rendered when `status="ready"`.
  2. **Session setup** — table fed by `setup_rows`. Disabled Manage buttons render as `<a class="btn disabled" aria-disabled="true" title="Lands in 9.4C">` so a click is a no-op (see risk notes).
  3. **Run Session** — three buttons: **Validate Session Setup** (anchor to `/operator/sessions/{id}?validated=1`), **Manage Invitations** (anchor to existing `/invitations`), **Extract Data** (disabled, tooltip "Extract Data — Segment 11").
  4. **Danger zone** — placeholder card with `id="danger-zone"` retained from 9.4A; the two stacked confirm-checkbox forms land in Slice 3.
- Drop the legacy ad-hoc layout from `session_detail.html`: the standalone "Run setup validation" link, the inline "Validate & activate" form, the inline View-outbox link (already removed by 9.3 / 9.4A precedent), and the per-instrument bullet list (Instruments are collapsed into the setup row now).

### Slice 2 — Inline validate-summary card via `?validated=1`

- `routes_operator.py` session-detail GET reads `validated: bool = Query(False)`. When truthy, calls the existing setup-validation service and passes `validation_summary` (errors / warnings / info counts, blocking-readiness verdict, warnings list, `can_activate`) into the template; otherwise `validation_summary=None`.
- `session_detail.html`: when `validation_summary` is set, render a new inline summary card immediately above the **Run Session** card with:
  - Counts row (errors / warnings / info).
  - Readiness verdict line.
  - **View detailed validation** button → `/operator/sessions/{id}/validate`.
  - **Activate session** form when `can_activate` is true, reusing the existing `acknowledge_warnings` checkbox path.
- `session_validate.html`: remove the `<form action=".../activate">` block (the page becomes the read-only "View detailed validation" target per Decision 4). Keep the per-check rows + counts table. Grep for any other template that links to `/activate` directly before landing — Activate is single-source on the inline summary card.

### Slice 3 — Delete Data + Danger zone wiring

- New service function `responses_service.delete_all_for_session(db, session_id) -> int` doing a single-transaction bulk delete of every `Response` row for the session. Returns deleted count. Preserves reviewers / reviewees / assignments / instruments / invitations.
- New route `POST /operator/sessions/{id}/delete-data`:
  - Form requires `confirm_delete=on`; missing or unchecked → re-render session detail with a flash error, no delete.
  - Calls `delete_all_for_session`, emits one `responses.deleted_all` audit event with `detail = {"deleted_count": N}`.
  - 303-redirect to `/operator/sessions/{id}` with a flash success message.
  - Allowed in any session status, including `ready` (Decisions 5 + 6). No edit-lock guard.
- `session_detail.html` Danger-zone card now stacks two confirm-checkbox forms:
  - **Delete data** form (top) — POSTs to `/delete-data`. Always enabled. Default button label per Decision 5.
  - **Delete session** form (bottom) — existing `/delete` endpoint, unchanged. Submit button disabled when `status="ready"` per today's "deletion locked while ready" UX (Decision 6).

### Slice 4 — Tests (~10) in `tests/integration/test_session_detail_restructure.py`

1. **Setup helper.** `build_setup_rows(session, db)` returns rows for Reviewers / Reviewees / Instruments / Assignments / Set up invites with the right URLs; Instruments and Set up invites flagged disabled with the "Lands in 9.4C" tooltip.
2. **Four-card render.** `GET /operator/sessions/{id}` body contains the four card headings (Session, Session setup, Run Session, Danger zone); legacy "Run setup validation" / inline "Validate & activate" markup is gone.
3. **Validate-summary absent by default.** `GET /operator/sessions/{id}` (no query) does not render the validation summary card.
4. **Validate-summary present with `?validated=1`.** Renders counts row, readiness verdict, **View detailed validation** button targeting `/operator/sessions/{id}/validate`, and the **Activate session** form when seed data passes validation.
5. **Refresh loses summary card.** Following a `?validated=1` GET with a no-query GET to the same URL renders without the summary card.
6. **`/validate` activate-form removed.** `GET /operator/sessions/{id}/validate` body no longer contains a `<form action=".../activate">` element.
7. **Delete data wipes responses, preserves setup.** Seed reviewers + reviewees + assignments + responses; POST `/delete-data` with `confirm_delete=on`. Assert `Response` rows for the session are gone, reviewers / reviewees / assignments / instruments untouched, audit row `responses.deleted_all` with `detail={"deleted_count": N}`.
8. **Delete data confirm required.** POST `/delete-data` without `confirm_delete=on` re-renders with an error flash; no rows deleted; no audit row written.
9. **Delete data allowed in `ready`.** Same as #7 with the session pre-activated to `ready` succeeds.
10. **Edit-lock visibility on Session card.** With `status="ready"`: **Edit details** button absent, **Revert to draft** button present, **Delete session** form button disabled, **Delete data** form button enabled.

---

## Out of scope (explicitly deferred)

- **Stored `validated` state and invalidation hooks.** 9.4B keeps today's two-state semantics (`draft` / `ready`); Segment 9.5 introduces `validated` and rewires every setup-mutating route's invalidation hook (see "Deferred to Segment 9.5" above and `segment_09_5A.md`).
- **Manage-page reshapes** for reviewers / reviewees / assignments — Upload-CSV anchored card, disabled **Edit** buttons, **Assign by Rules** toggleable card. → 9.4C.
- **`/instruments` index page** + `/setupinvite` + `/extract` stub pages. → 9.4C. The 9.4B Setup table renders Manage buttons disabled for the Instruments and Set up invites rows so the visual shape matches the target now.
- **Inline-edit affordances** on the Setup table itself — buttons are Manage-page links, not in-table editors.
- **Sticky validate-summary across refresh.** The query-param branch is one-shot per render by design; durable summary lands when `validated` becomes a stored state in 9.5.
- **`spec/operator_map.md` regen** — single regen at the end of 9.4C per 9.4A Decision 6.
- **`spec/target_operator_map.md` edits** — already synced; only touch if a verify-pass surfaces stale wording on the four-card detail or Danger-zone shape.

---

## Docs to update at PR time

- `docs/status.md`:
  - Timeline row: `2026-MM-DD | Segment 9.4B shipped (session detail four-card restructure + inline validate-summary + Delete Data)`.
  - Segments-shipped row: `9.4B | Session detail four cards (Session / Setup / Run Session / Danger zone), inline validate-summary on session detail via ?validated=1, Delete Data action with responses.deleted_all audit event | <date>`.
  - Operator URL table: add `POST /operator/sessions/{id}/delete-data`. The `?validated=1` branch is documented under the existing `GET /operator/sessions/{id}` row, not as a new route.
  - Audit-event table: add `responses.deleted_all` with `detail = {"deleted_count": N}`. Note the deliberate asymmetry: allowed in `ready` (vs. session-delete which is locked while ready).
  - Operator UI section: update the session-detail bullet to describe the four-card layout and the inline summary card; note that Activate is single-source on the inline card and `/validate` is now a read-only deep-dive.
- `AGENTS.md`: bump "Current stage" summary to mention 9.4B.
- `spec/target_operator_map.md`: only if a verify-pass surfaces stale wording.
- `spec/operator_map.md`: do **not** touch in 9.4B; deferred to 9.4C.

---

## Risk notes

- **`session_detail.html` is the highest blast-radius template in the segment.** Today it carries activate, revert, edit-lock banners, invitations link, response-loss banners, and the per-instrument list. The four-card restructure rewrites it. Snapshot existing user flows in tests first (activate-with-warnings, revert-to-draft, edit-lock banner), then re-run them after the restructure.
- **Validate-summary is one-shot per render.** A refresh without `?validated=1` loses the card. Acceptable for 9.4B because the operator's flow is "click Validate → review → activate" in one sitting; the durable `validated` state in 9.5 makes the card sticky. Don't paper over the limitation with a session cookie or flash — it's the lever 9.5 needs to move.
- **`responses.deleted_all` allowed in `ready`** is a deliberate asymmetry vs. today's "deletion locked while ready" on session delete. Call it out in `docs/status.md`'s audit notes; the only safety net is the confirm checkbox, and there is no undo (a re-import requires reviewers to re-submit).
- **Disabled Manage buttons must not be `<button disabled>` inside a `<form>`** — they're `<a class="btn disabled" aria-disabled="true">` styled to look disabled with a tooltip. A real `<button disabled>` inside the wrong form would silently submit to the wrong endpoint when re-enabled later.
- **Activate flow moves onto the inline summary card** in the same slice that strips the form from `session_validate.html`. Grep for `action=".../activate"` across `app/web/templates/` before landing to make sure no other template still posts there.
- **Setup-table helper count queries.** `build_setup_rows` will issue a count query per row. Today's volumes are tiny so N+1 is fine; if it surfaces later, the helper is the single place to introduce a batched count without touching templates.
- **Spec/code drift if 9.4B lands without 9.4C.** The Setup table renders disabled Manage links to `/instruments` and `/setupinvite`, both of which 404 today. Tooltip ("Lands in 9.4C") + disabled state are the contract; if 9.4C slips, the disabled buttons keep the operator out of the 404 path.
