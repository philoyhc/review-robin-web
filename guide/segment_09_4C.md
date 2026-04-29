# Segment 9.4C Implementation Plan — Manage-page reshapes + instruments index + `/setupinvite` stub + segment close-out

**Status:** Stub with decisions locked. Implementation slices not yet drafted. Last of three PR-sized blocks for Segment 9.4 (operator UI restructure to the target page map). Sits after 9.4B (shipped).

- **9.4A (shipped):** chrome, breadcrumbs, `/about`, sessions list reshape.
- **9.4B (shipped):** session detail four-card restructure + inline validate-summary + Delete Data.
- **9.4C (this doc):** reviewers / reviewees / assignments Manage page reshapes, instruments index, `/setupinvite` stub, re-enabling the 9.4B-disabled Manage buttons, closing-segment doc + spec refresh.

See `segment_09_4_operator_ui_restructure_plan.md` for the segment-level plan and `spec/target_operator_map.md` for the design target.

---

## Decisions locked for 9.4C

1. **Inline Upload-CSV uses the no-JS anchored-card pattern.** The **Upload CSV** button on each Manage page (reviewers / reviewees / assignments-manual) is an `<a href="#upload-csv">` link. An always-rendered `<section id="upload-csv">` card sits below the table with the existing form (file input + replace-warning checkbox). The POST endpoint is unchanged (`…/reviewers/import`, `…/reviewees/import`, `…/assignments/manual/import` etc.). No JS toggle, no `<details>`, no query-param branch.
2. **Standalone `…/import` GET routes are removed.** `GET /operator/sessions/{id}/reviewers/import` and `GET /operator/sessions/{id}/reviewees/import` are deleted. Any external bookmark / direct link 404s; today these GETs are only linked from the Manage page, so safe to drop. `docs/status.md`'s operator URL table loses both rows. The corresponding `…/import.html` templates are deleted.
3. **Assign by Rules also uses the anchored-card pattern.** `<a href="#rules">` → always-rendered `<section id="rules">` placeholder card containing only the "Rule editor — Segment 12" notice and a **Cancel** anchor (`<a href="/operator/sessions/{id}/assignments">` — drops the `#rules` anchor). No JS, no query param. Card has no POST yet.
4. **No `/extract` stub page in 9.4C.** Extract Data, when implemented (Segment 11), will trigger the browser's normal file-save dialog directly — no separate page. The **Extract Data** button on the Run Session card stays disabled in 9.4C with the existing "Extract Data — Segment 11" tooltip (no change from 9.4B). The original 9.4 segment plan's `GET /extract` stub is dropped from scope.
5. **Per-instrument detail breadcrumb stays as today.** `/operator/sessions/{id}/instruments/{instrument_id}` keeps its current crumb trail (`Sessions / {session} / {instrument label}`); 9.4C does not insert `Instruments` as an extra step. The new `/instruments` index is the consolidating hub for management actions; the per-instrument page remains addressable directly without forcing the trail through the index.
6. **`/setupinvite` is a pure GET stub.** H1 "Set up invites", one short paragraph noting the email-template editor lands in Segment 15, breadcrumb back via the chrome. No forms, no POST routes, no behaviour.
7. **9.4B-disabled Manage buttons flip to enabled.** `app/web/views.build_setup_rows` re-enables the **Instruments** row (links to `/operator/sessions/{id}/instruments`) and the **Set up invites** row (links to `/operator/sessions/{id}/setupinvite`). Tooltips ("Lands in 9.4C") removed. Extract Data on the Run Session card stays disabled per Decision 4.
8. **Docs follow the per-sub-PR precedent.** `docs/status.md` gets a single 9.4C timeline row + a single 9.4C Segments-shipped row (matching 9.4A/B). `AGENTS.md`'s "Current stage" gets a 9.4C bullet alongside the existing 9.4A/B bullets — no rollup into a single "Segment 9.4 complete" bullet. Spec sync: `spec/operator_map.md` (the as-is map) is regenerated once at the end of 9.4C, the only sub-PR in 9.4 that touches it.
9. **Single test file.** All 9.4C integration tests land in `tests/integration/test_segment_9_4c.py` (or a similarly named single file). Splitting across `test_manage_pages_reshape.py` + `test_instruments_index.py` is rejected — the surface is small enough to keep in one file and read together.
10. **Edit Reviewers / Reviewees / Assignments buttons render disabled.** `<a class="btn disabled" aria-disabled="true" title="Inline editing — coming soon">` per the 9.4B convention for disabled affordances; never a `<button disabled>` inside a form. No new endpoints.
11. **Instruments index Add / Delete buttons render disabled** with the tooltip "Multi-instrument — Segment 13" per the 9.4 plan. Single-instrument sessions render exactly one card. The lone instrument is not deletable today regardless (target spec note).

---

## Implementation slices

_Not yet drafted. Sketch:_

- **Slice 1** — Manage-page reshape for reviewers + reviewees (anchored Upload-CSV card, disabled Edit button, remove `…/import` GETs and templates, update `build_setup_rows` Reviewers / Reviewees rows if needed).
- **Slice 2** — Assignments page reshape (anchored Upload-CSV card for the manual flow, anchored Assign-by-Rules placeholder card with Cancel anchor, disabled Edit Assignments button).
- **Slice 3** — Instruments index page + per-instrument breadcrumb adjustments per Decision 5 (no change). Re-enable Instruments row in `build_setup_rows`.
- **Slice 4** — `/setupinvite` stub page. Re-enable Set up invites row in `build_setup_rows`.
- **Slice 5** — Tests (single file) + docs (`docs/status.md`, `AGENTS.md`, `spec/operator_map.md` regen).

---

## Out of scope (explicitly deferred)

- **Inline-editable tables** for reviewers / reviewees / assignments — buttons render disabled per Decision 10. Inline-edit pattern lands in a follow-on UX PR that designs the affordance once and reuses it across all three.
- **`/assignments/rules` rule engine** — anchored card placeholder only per Decision 3; Segment 12 lights it up.
- **`/setupinvite` email template editor** — stub page only per Decision 6; Segment 15.
- **`/extract` data export** — no page at all per Decision 4; Segment 11 triggers a file-save dialog directly from the Run Session button.
- **Add / delete instruments** — disabled per Decision 11; Segment 13 (multi-instrument).
- **Sticky validate-summary across refresh** — query-param branch from 9.4B is one-shot by design; durable summary lands when `validated` becomes a stored state in Segment 9.5.
- **`spec/target_operator_map.md` edits** — already synced; only touch if a verify-pass surfaces stale wording.

---

## Docs to update at PR time

- `docs/status.md`:
  - Timeline row: `2026-MM-DD | Segment 9.4C shipped (Manage-page reshapes + instruments index + /setupinvite stub)`.
  - Segments-shipped row: `9.4C | Reviewers / reviewees / assignments Manage pages with anchored Upload-CSV cards and disabled Edit buttons; Assign by Rules placeholder card; /operator/sessions/{id}/instruments index page; /operator/sessions/{id}/setupinvite stub; setup-table Manage buttons for Instruments and Set up invites enabled | <date>`.
  - Operator URL table: drop `GET …/reviewers/import` and `GET …/reviewees/import` rows. Add `GET /operator/sessions/{id}/instruments` and `GET /operator/sessions/{id}/setupinvite`.
  - UI section: short paragraph on the Manage-page reshape and the new index/stub pages.
- `AGENTS.md`: add 9.4C bullet to "Current stage" alongside 9.4A/9.4B.
- `spec/operator_map.md`: regenerate end-to-end so the as-is map matches 9.4A + 9.4B + 9.4C combined.
- `spec/target_operator_map.md`: only if a verify-pass surfaces stale wording.

---

## Risk notes

- **Removing `…/import` GETs is a backwards-incompatible URL change.** Any external bookmark to `/operator/sessions/{id}/reviewers/import` 404s. The only in-app linker is the Manage page, which 9.4C rewrites to use the anchored card. Flag in `docs/status.md`.
- **Anchored-card pattern is no-JS but stateful via the URL fragment.** A page refresh keeps the `#upload-csv` anchor and re-scrolls; that's fine. Cancel anchors (`<a href=".../assignments">`) drop the fragment so the placeholder card is no longer scrolled-to.
- **Disabled buttons must be `<a class="btn disabled" aria-disabled="true">` not `<button disabled>`** per the 9.4B convention. A real `<button disabled>` inside the wrong form would silently submit to the wrong endpoint when re-enabled later.
- **Instruments row in `build_setup_rows`** currently shows the lone instrument's `accepting_responses` pill as a "collapsed status" string. After 9.4C the row links to a real index page; the count/status copy on the row should still match what's visible on the index card (avoid divergent labels).
- **Single-instrument invariant is unchanged.** The index page must render correctly with exactly one instrument and Add/Delete disabled — no empty-state copy for "no instruments" because that state is unreachable today.
- **`spec/operator_map.md` regen is the segment's exit condition.** If 9.4C lands without the regen, the as-is map is stale across all three sub-PRs. Block the PR on the regen, not the other way around.
