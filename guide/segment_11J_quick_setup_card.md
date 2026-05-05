# Segment 11J — Quick Setup card

Stub. Implementation plan for the Quick Setup card on Session Home.
Replaces the existing `placeholder_card` stub at
`session_detail.html:174` with a real card that lets an operator
bulk-populate or replace a session's setup data — Reviewers,
Reviewees, Assignments — from one place, plus a fourth
**Configuration import** slot that ships as a placeholder and
graduates to the real flow when Segment 12A lands.

The functional spec is **`spec/quick_setup_card_spec.md`**. This
guide is the implementation plan; reference the spec for the slot
contracts, confirmation copy, cascade rules, and lifecycle table.

Catalog item: `unfinished_business.md` #30.

## Status

Planning. Sized as **3 PRs** in dependency order (slots A / B / C +
the configuration-import placeholder folded into PR C).

## Why a thin convenience surface

The card owns no domain logic of its own. Reviewer, reviewee, and
assignment imports already exist on the per-entity Setup pages and
already implement replace semantics with cascade clearance — see
`csv_imports.save_reviewers` / `save_reviewees` and
`assignments.replace_assignments`, both wired through the shared
`_handle_import` helper at `app/web/routes_operator.py:397`. Quick
Setup is a UI affordance that composes the same service helpers
into a single Home-page panel; the parsing, validation, audit, and
`lifecycle.invalidate_if_validated()` calls all stay where they
already are.

That framing also keeps the segment small. The risk surface is
template + thin route plumbing, not new business rules.

## Scope

In:

- New three-slot card on `session_detail.html`, replacing the
  `placeholder_card(id="quick-setup", ...)` block. Renders for
  `draft` and `validated` sessions; renders disabled behind the
  yellow lock card pattern for `ready` and `closed`, matching the
  spec's lifecycle table.
- **Slot 1 — Reviewers.** File input + Submit, current-count
  indicator, inline confirmation when populated, posts to a new
  `/operator/sessions/{id}/quick-setup/reviewers` route that
  delegates to the same `_handle_import` pipeline already used by
  the per-entity Setup page.
- **Slot 2 — Reviewees.** Same shape; delegates to the same
  pipeline with `kind="reviewees"`.
- **Slot 3 — Assignments.** Two interchangeable input modes
  per the spec: a rule selector (default; FullMatrix for now,
  Manual once Segment 13 lands a real rule menu — until then the
  selector renders only FullMatrix and an explanatory note about
  rule expansion) and a CSV upload alternative. Posts to a new
  `/operator/sessions/{id}/quick-setup/assignments` that fans out
  to either `assignments.replace_assignments(mode=FullMatrix)` or
  the existing assignment CSV path. Current-count + active-rule
  indicator.
- **Slot 4 — Configuration import (placeholder).** A fourth slot
  framed identically to the three above, shipping as a
  `.card.placeholder`-styled inner section. Body copy: "Upload a
  session configuration CSV exported from another session to
  restore its setup in one go. Available once Segment 12A ships."
  No file input, no submit; a disabled button with a tooltip
  pointing at `guide/segment_12A.md`. Graduates to a live slot in
  Segment 12A PR 2 (the `POST /operator/sessions/{id}/import-config`
  half) — at which point the placeholder body is swapped for a
  real `<input type="file">` + Submit that posts to the 12A route.
  See "Interaction with Segment 12A" below for the seam.
- Cascade-clearance confirmation copy per spec when reviewers /
  reviewees are replaced on a session that has assignments. The
  underlying cascade is already implemented in
  `csv_imports.save_reviewers` / `save_reviewees`; this segment
  surfaces the cascade in the confirmation prompt.
- **No success flash banner.** Per the operator-page direction
  set on the reviewer surface (Save / Submit retired their flash
  banners — the status pill is the canonical success signal),
  Quick Setup does **not** add a transient "8 reviewers loaded"
  banner on the success 303. The slot's count indicator updates
  in place ("Reviewers (8 currently)" → "Reviewers (47 currently)"),
  which *is* the success signal; the file input clears and the
  submit button greys out until the next file is chosen. One
  fewer ephemeral piece of UI to dismiss.
- **Error / confirmation banners follow the assumptions.md Cancel
  convention.** When a slot needs a banner — parse / validation
  error from the importer, or the cascade-preview confirmation
  before replacing populated data — it renders inside the
  destination slot using the canonical `.banner.banner-error` /
  `.banner.banner-warning` classes, carries the
  `banner-scroll-target` class for auto-scroll, and **always
  includes a `.btn.alert` Cancel button** right-aligned at the
  bottom that links back to a clean Home URL with a
  `#quick-setup-{kind}` fragment. Confirmation banners pair the
  Cancel with a `.btn.danger-solid` "Confirm replacement"; pure
  error banners (parse / validation, no confirm path) make Cancel
  the only button. This is the existing convention — no new
  visual primitive, just consistent reuse.
- Audit events stay where they already are (the existing per-entity
  upload services emit them); no new audit shapes.

Out:

- **Real configuration import.** Segment 12A owns the CSV format,
  the `apply_session_config` service, and the
  `/operator/sessions/{id}/import-config` route. This segment ships
  only the placeholder slot and the seam. See "Interaction with
  Segment 12A".
- **Real rule-builder UI for assignments.** The full rule menu
  (rule types beyond FullMatrix, parameters, preview) is Segment 13.
  Slot 3 ships with FullMatrix-only as the rule-selector default;
  the CSV upload alternative covers the manual case.
- **Per-record edit.** Inline editing of individual reviewers /
  reviewees / assignments stays on the per-entity Manage pages.
- **CSV preview before submission.** Spec §"Out of scope" — current
  count + filename is sufficient.
- **Wizard-style stepping / enforced order across slots.** Slots
  are independent.
- **Cross-entity validation.** That's the Validate page's job; the
  card validates each file individually only.
- **Auto-regeneration of assignments after a reviewer / reviewee
  replacement.** Operator returns to Slot 3.
- **Save-as-template / cross-session reuse.** That's what Segment
  12A's export half delivers; out of scope here.
- **Reskinning the per-entity Manage pages.** Their upload
  affordances stay as-is and behave identically (same pipeline);
  the card is additive, not a replacement.

## Interaction with Segment 12A

12A ships export + import of a session's full configuration as a
3-column CSV. Its PR 2 lands the import route at
`POST /operator/sessions/{id}/import-config` plus a "Import config"
button somewhere on Home (12A's plan calls out the Session Details
card footer as a candidate, but defers the anchor decision to PR
review).

This segment offers the better anchor: the fourth slot of Quick
Setup. The seam:

1. **11J ships first**, with the fourth slot as a placeholder
   pointing at Segment 12A. The placeholder lives inside the same
   card so operators learn its location before the real flow
   exists; when it lights up they don't have to find a new button.
2. **12A PR 2 swaps the placeholder for a live slot** in the same
   `<section class="quick-setup-slot ...">` container. The diff is
   small: replace the disabled-button stub with `<input type="file"
   name="file">` + a submit button that posts to
   `/operator/sessions/{id}/import-config`. The inline-confirmation
   pattern from slots 1-3 reuses cleanly because 12A's import is
   also wipe-and-replace and 12A's lifecycle gate
   (`status in {"draft", "validated"}`) matches Quick Setup's own
   visibility rule.
3. **The export side of 12A (PR 1)** keeps its own anchor decision
   — likely the Session Details card footer — and stays out of the
   Quick Setup card. Quick Setup is for ingestion, not extraction.

Document the seam in 12A's plan when it picks up the anchor
decision in its PR 2; this guide already names it from the 11J
side so the order stays clear.

## Proposed PR sequence

### PR A — Slots 1 + 2 (Reviewers, Reviewees)

**Goal.** Two-slot card on Home that delegates to the existing
per-entity import pipeline. No assignments slot yet; the third and
fourth slots remain `placeholder_card` stubs in this PR.

- New template partial `operator/partials/_quick_setup_card.html`
  with the card chrome + a `quick_setup_slot(...)` Jinja macro that
  renders one slot's file input, submit button, count indicator,
  and inline-confirmation block.
- New view-shape adapter `views.build_quick_setup_context(session)`
  returning per-slot counts and the disabled / enabled state per
  the spec's lifecycle table. Service helpers for the counts
  already exist (`csv_imports.existing_reviewer_count`,
  `existing_reviewee_count`); the adapter assembles them.
- Two new routes:
  - `POST /operator/sessions/{id}/quick-setup/reviewers`
  - `POST /operator/sessions/{id}/quick-setup/reviewees`
  Both delegate to a thin `_handle_quick_setup_import` wrapper that
  calls the same `_handle_import` core as the per-entity routes,
  but renders Home (via the existing context builders) on
  validation failure instead of the per-entity page. On success:
  303 → Home with **no query flag** — the count indicator on the
  slot updates in place, which is the success signal; no flash
  banner. On parse / validation error: 303 → Home with a
  `?quick_setup_error={kind}` flag so the GET render places a
  `.banner.banner-error` (with mandatory Cancel button) inside
  that slot, and the URL fragment lands on `#quick-setup-{kind}`.
- Lifecycle gate stays where it already is in
  `_handle_import`'s call to `_require_editable`.
- Disabled / lock-card path for `ready` / `closed` reuses the
  existing yellow lock card component; verify by snapshot test
  rather than re-rolling markup.
- Tests:
  - Per-slot golden-path upload (each slot independently) on a
    `draft` session — assert the success render carries **no**
    `.banner` element and the count indicator reflects the new
    value.
  - Replacement confirmation banner fires when count > 0 on
    submit; carries a `.btn.alert` Cancel + `.btn.danger-solid`
    Confirm; second submit (with `confirm_replace=1`) applies.
    Cancel link points at `?` (no flag) with `#quick-setup-{kind}`
    fragment.
  - Cascade-clearance copy renders inside the same confirmation
    banner when assignments exist on a reviewer / reviewee replace.
  - Parse / validation error path: route 303s with
    `?quick_setup_error={kind}`; GET render shows
    `.banner.banner-error` scoped to that slot with the mandatory
    Cancel button; other slots are unaffected.
  - `validated` → re-upload flips the session back to `draft`
    (already covered in `_handle_import`'s underlying tests; one
    additional integration test confirms the route surface
    inherits the behaviour).
  - Lock state on `ready` / `closed` — slots non-interactive,
    counts still render, post is rejected at the service layer.

### PR B — Slot 3 (Assignments)

**Goal.** Add the assignments slot with its rule-selector / CSV
toggle.

- Extend the partial with the rule-selector + CSV-mode toggle.
  Rule menu renders FullMatrix today; an explanatory caption
  ("more rules ship with Segment 13") sits under the selector.
  CSV-mode reuses the file input pattern from slots 1-2.
- New route `POST /operator/sessions/{id}/quick-setup/assignments`:
  - Form contains either `mode=rule` + `rule=FullMatrix` or
    `mode=csv` + `file=...`.
  - Rule mode → `assignments.replace_assignments(mode=FullMatrix,
    user=user)` (the helper is already wired to invalidate +
    audit).
  - CSV mode → the existing assignment CSV upload path.
- Replace-confirmation banner copy per spec: "This will replace
  104 existing assignments. Replace?" — no cascade messaging (per
  spec, assignments are leaf data). Banner uses the same
  `.banner.banner-warning` + Cancel + Confirm shape as slots 1-2.
- Success path: 303 → Home with no flag; the slot's count + rule
  indicator updates in place ("Assignments (104 currently,
  full-matrix rule)"). No flash banner.
- Tests:
  - Rule-mode submission on an empty assignments table generates
    the FullMatrix row count and the slot's count + rule
    indicator reflects it on the next render — assert no
    `.banner` element on the success page.
  - Rule-mode submission on a populated table requires the
    confirmation banner; Cancel returns to a clean URL with the
    `#quick-setup-assignments` fragment.
  - CSV-mode parse-error path renders `.banner.banner-error`
    scoped to slot 3 only with the mandatory Cancel button;
    success path updates the count + "loaded from file"
    indicator without a flash banner.
  - Lock state on `ready` / `closed`.

### PR C — Configuration-import slot (placeholder)

**Goal.** Land the fourth slot as a placeholder framed like the
other three, so its location is stable when Segment 12A goes live.

- Extend `_quick_setup_card.html` with a fourth section using the
  same outer markup as the other slots but with a `.placeholder`
  inner treatment: greyed body, disabled "Import" button, body
  copy explaining the slot graduates with Segment 12A.
- No new route; no new service code. The button's `title`
  attribute points at `guide/segment_12A.md` for the curious.
- One snapshot test confirming the slot renders on `draft` /
  `validated` and renders disabled-with-counts on `ready` /
  `closed` like its siblings.
- `docs/status.md` gains a one-line note that Quick Setup ships
  with the configuration-import slot held back for 12A.

## Implementation pointers

- **No success flash; count indicator is the signal.** Success
  303s carry no query-string flag. The Home GET render reflects
  the new state directly via the slot's count indicator, the
  cleared file input, and (for assignments) the rule label
  refreshing. This matches the reviewer-surface direction of
  retiring transient post-success banners in favour of canonical
  in-page state. Tests should assert the absence of `.banner` on
  success renders so we don't drift back into flash territory.
- **Banners only when something needs operator attention, and
  always with Cancel.** Two cases need a banner: (a) parse /
  validation error from the importer, (b) cascade-preview
  confirmation before a populated-slot replacement. Both follow
  `spec/assumptions.md` §"Inline error / warning banners":
  - Use `.banner.banner-error` (red) for errors and
    `.banner.banner-warning` (amber) for cascade-preview
    confirmations.
  - Carry the `banner-scroll-target` class plus a unique anchor
    id (`id="quick-setup-{kind}-banner"`) so the page-wide
    auto-scroll script in `base.html` brings the banner into
    view.
  - Right-align a `.btn.alert` **Cancel** button at the bottom
    of every banner. Cancel links to a clean URL (no
    `?quick_setup_error=...` flag) with a
    `#quick-setup-{kind}` fragment that returns the operator to
    the source slot. For confirmation-style banners the Confirm
    button (`.btn.danger-solid`) sits next to Cancel; for pure
    error banners Cancel is the only button.
  - Render the banner **inside the destination slot**, not at
    the top of Home, so it's visually anchored to the action
    that produced it.
- **Cascade copy.** The cascade itself is automatic in the
  existing `save_reviewers` / `save_reviewees` paths; this segment
  only changes the confirmation banner copy. Centralise the
  sentences in a small helper (`views.cascade_message_for_replace(
  kind, counts)`) so the four cases live in one place.
- **Lock card reuse.** `app/web/templates/operator/partials/`
  already has the yellow lock card component used by the Setup
  tabs. Wrap the disabled card in the same partial; do not
  re-roll the markup or copy. Lock-card explanatory text matches
  what the Setup tabs say in the same lifecycle state.
- **Disabled-state non-interactivity.** Beyond visual disabling,
  the routes themselves must reject `ready` / `closed` posts at
  the service layer (the existing `_require_editable` call
  handles this; verify per slot in tests).
- **No new audit shapes.** Every mutation routes through an
  existing service helper that already emits its own audit event;
  do not add a parallel `quick_setup.*` event family. The
  card-level concept doesn't need its own audit trail.
- **Don't touch the per-entity Manage pages.** Their upload UIs
  stay; they share the pipeline with Quick Setup. Removing them
  is a Segment 15 question, not 11J.

## Out of scope (cross-references)

- **Real configuration import / export** — Segment 12A
  (`guide/segment_12A.md`). The placeholder slot here is the seam.
- **Rule-builder beyond FullMatrix** — Segment 13
  (`guide/segment_13_rulebased_assignment_builder_plan.md`).
- **Inline-editable Manage pages** — Segment 15, catalog item #25.
- **Sessions-list per-row Delete** — Segment 15, catalog item #23.
- **Extract Data card** — Segment 11H. Sibling Home-body card; same
  placeholder-graduation pattern but disjoint scope.

## Test impact

- New `tests/integration/test_quick_setup_card.py` covering:
  per-slot golden path, replace-confirmation copy, cascade copy,
  lifecycle gate, scoped error reporting per slot, placeholder slot
  rendering on draft / validated / ready / closed.
- No churn on existing reviewer / reviewee / assignment import
  tests — they cover the underlying pipeline that this segment
  composes onto, and the pipeline doesn't change.
- One small unit test on `views.build_quick_setup_context` pinning
  the disabled-state matrix from the spec's lifecycle table.

## Doc impact

- `guide/todo_master.md` — move 11J from **Upcoming** to **Done**
  once PR C ships; mention the 12A seam in the entry.
- `docs/status.md` — timeline entry per PR.
- `spec/quick_setup_card_spec.md` — no changes expected; the spec
  is the contract this guide implements. If a slot detail proves
  ambiguous in PR review, fix the spec, not the implementation.
- `guide/segment_12A.md` — small follow-on note when 12A's PR 2
  lands: replace its "Anchor: a 'Import config' button on Session
  Home" line with "swap 11J's placeholder slot for the real
  upload form".
