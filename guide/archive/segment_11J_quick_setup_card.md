# Segment 11J — Quick Setup card

Stub. Implementation plan for wiring up the Quick Setup card on
Session Home — flipping the Reviewers / Reviewees / Assignments
slots from inert (Segment 11H scaffold state) to live, and
unifying the card's status awareness behind the existing
Lock / Unlock toggle so the operator's affordance is the same in
every state.

The fourth slot (**Session settings**, the configuration-import
upload) is **explicitly out of scope for this segment** and lives
as a separate part of the plan; see "Session settings — separate
sub-plan" below.

The functional spec is **`spec/quick_setup_card_spec.md`**. This
guide is the implementation plan; reference the spec for the slot
contracts, confirmation copy, and cascade rules.

Catalog item: `unfinished_business.md` #30.

## Status

Planning. Sized as **2 PRs** in dependency order, both targeting
the three slots whose underlying import pipelines already exist.

- **PR A — Lock / Unlock toggle + slots 1 + 2 (Reviewers,
  Reviewees).** Wires the card's body-greying lock state to a
  real Unlock/Lock toggle that applies in every editable-relevant
  state (including `ready`), and flips the Reviewers /
  Reviewees slots live.
- **PR B — Slot 3 (Assignments).** Wires the rule-mode +
  CSV-mode toggle behind the same lock pattern.

The **Session settings** slot stays inert in 11J. Its graduation
is folded into Segment 12A PR 6 (which already owns the
configuration import/export half) and tracked as a separate
sub-plan in the same `guide/` family — `segment_11J_settings_slot.md`
(stub) or, if 12A absorbs it cleanly, the 12A PR 6 plan. Either
way, no markup changes are needed in 11J's PR set to land that
graduation later — the slot's scaffold seam is already final.

**Depends on Segment 11H PR A** — 11H ships the inert four-slot
scaffold (`_quick_setup_card.html` partial, `quick_setup_slot`
macro, `QuickSetupSlot` dataclass, `QuickSetupContext` with the
`is_locked` / `is_disabled` / `show_lock_toggle` flags, and the
disabled `#quick-setup-lock-toggle` button). 11J's PRs flip
slots from `is_wired=False` to `True`, plug in the `wire_url`,
populate the dormant banner placeholders, and wire the lock
toggle to a real handler. None of 11J's PRs introduce new
markup; every wiring patch is a thin diff against the scaffold's
seam.

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

The visual scaffold (the four-slot layout, body-greying lock
behaviour, DOM IDs / fragment anchors, dormant banner placeholders,
disabled Lock / Unlock toggle) shipped in **Segment 11H PR A**
before 11J's first wiring PR. 11J adds the live POSTs, the
populate-banner-on-error branch, the view-adapter extensions that
propagate `is_wired=True` and `wire_url=…`, and a real handler for
the lock toggle; everything else is already on the page when 11J
starts.

That framing keeps the segment small. The risk surface is thin
route plumbing + adapter extensions + a tiny lock-toggle handler,
not new business rules and not new markup.

## Status awareness — the unified Lock / Unlock pattern

11H ships two greying triggers, currently mutually exclusive:

- `is_disabled` — session is `ready` (Activated). Whole card
  carries `.card.disabled` plain-greying. **The Lock / Unlock
  button does not render** (`show_lock_toggle=False`); the
  operator's path forward was meant to be Pause, not Unlock.
- `is_locked` — session is editable (`draft` / `validated`)
  but the card body is greyed pending an explicit Unlock click.
  Body wrapper carries `.locked`; the Lock / Unlock button sits
  outside the wrapper, vivid.

11J **collapses these into one pattern, modelled on the Extract
Data card's "always reachable, status-aware via greying" approach.**
The Lock / Unlock toggle becomes the single, uniform affordance:

- The card body is **always greyed by default** (`is_locked=True`
  is the fresh-page-load state) on `draft` / `validated` /
  `ready` alike.
- The **Unlock button is rendered in every state where mutations
  are conceivable** — including `ready`. Clicking it reveals the
  interactive controls.
- On `ready`, the controls become interactive once unlocked, but
  any submit is rejected at the route layer (the same
  `_require_editable` gate the per-entity Setup pages already
  enforce). The rejection renders inside the destination slot's
  `.banner.banner-error` with copy that names the next move
  ("Pause the session before applying setup changes").

The change in plain language: status awareness lives in the
greying ("session is ready, edits aren't expected"), and the
unlock button is the consistent escape hatch for an operator who
genuinely needs to inspect the card or attempt an edit (which the
service layer will safely reject). One pattern, one mental model,
one button — instead of two separate "disabled vs locked"
treatments that diverge on which controls render.

This **does require a small revision to the 11H scaffold's
context-builder**:

- `QuickSetupContext.is_disabled` either retires entirely
  (preferred) or stays as a label-only flag the template uses for
  the state-conditional `description` copy. The card no longer
  applies `.card.disabled` plain-greying as a separate visual
  treatment — the body's `.locked` greying is the single visual
  signal.
- `show_lock_toggle` becomes `True` in every state where the
  toggle should render (i.e. the card itself is reachable). For
  the new-session preview variant
  (`build_new_session_quick_setup_context`) it stays `False`
  (no session row → nothing to lock).
- `is_locked` defaults `True` in `draft` / `validated` / `ready`
  alike on first render; the per-request override lives in a
  query-string flag (see Implementation pointers).

These tweaks land in PR A alongside the toggle wiring, not as a
separate scaffold revision PR — the surface area is small and the
new behaviour is testable end-to-end only with the toggle wired.

The corresponding spec update lands with PR A:
`spec/quick_setup_card_spec.md` lifecycle table currently calls
for `ready` / `closed` to render disabled "behind the existing
yellow lock card pattern"; that line needs to read "behind the
same body-greying as `draft` / `validated`, with the Lock /
Unlock toggle visible in every editable-conceivable state." (The
yellow lock card has already been retired on Home per
`spec/session_home.md` "Disabled treatment on Home is plain
greying-out, not yellow lock cards"; this revision aligns the
Quick Setup spec with that direction.)

## Scope

In:

- **Lock / Unlock toggle wired live.** PR A replaces the disabled
  placeholder button at `#quick-setup-lock-toggle` with a real
  toggle. The toggle posts to `/operator/sessions/{id}/quick-setup/lock`
  (or simply navigates with a `?quick_setup_unlocked=1` query-string
  flag — see Implementation pointers; the form-post path is
  preferred so the toggle's effect survives a back-button refresh
  and matches the rest of the card's POST semantics). The card's
  `is_locked` flips per the operator's last click; default on a
  fresh visit is locked.
- **Slot 1 — Reviewers.** File input + Submit, current-count
  indicator, inline confirmation when populated, posts to a new
  `/operator/sessions/{id}/quick-setup/reviewers` route that
  delegates to the same `_handle_import` pipeline already used by
  the per-entity Setup page.
- **Slot 2 — Reviewees.** Same shape; delegates to the same
  pipeline with `kind="reviewees"`.
- **Slot 3 — Assignments.** Two interchangeable input modes per
  the spec: a rule selector (default; FullMatrix only — Manual
  rule menu lands in Segment 13) and a CSV upload alternative.
  Posts to a new `/operator/sessions/{id}/quick-setup/assignments`
  that fans out to either `assignments.replace_assignments(mode=FullMatrix)`
  or the existing assignment CSV path. Current-count + active-rule
  indicator updates in place on success.
- **Cascade-clearance confirmation copy** per spec when reviewers
  / reviewees are replaced on a session that has assignments. The
  underlying cascade is already implemented in
  `csv_imports.save_reviewers` / `save_reviewees`; this segment
  surfaces the cascade in the confirmation prompt.
- **No success flash banner.** Per the operator-page direction set
  on the reviewer surface, the count indicator is the canonical
  success signal — the slot's count refreshes ("Reviewers (8
  currently)" → "Reviewers (47 currently)"), the file input
  clears, the submit button greys out until the next file is
  chosen.
- **Error / confirmation banners follow the domain_assumptions.md Cancel
  convention.** When a slot needs a banner — parse / validation
  error, cascade-preview confirmation, or `ready`-state lifecycle
  rejection — it renders inside the destination slot using the
  canonical `.banner.banner-error` / `.banner.banner-warning`
  classes, carries the `banner-scroll-target` class, and **always
  includes a `.btn.alert` Cancel button** right-aligned at the
  bottom that links back to a clean Home URL with a
  `#quick-setup-{kind}` fragment. Confirmation banners pair the
  Cancel with a `.btn.danger-solid` "Confirm replacement"; pure
  error banners (parse / validation / lifecycle-rejection) make
  Cancel the only button.
- **Audit events stay where they already are** (the existing
  per-entity upload services emit them); no new audit shapes.
- **Lock-toggle audit.** Toggling the lock is operator UI state,
  not domain state — no audit event. (If the team later decides
  the toggle is worth tracking, that's a separate small addition;
  the default here is no event.)

Out:

- **Slot 4 — Session settings.** The configuration-import slot's
  wiring is **out of scope for 11J**. It stays inert per 11H, and
  its graduation lands in Segment 12A PR 6 as already documented
  in `guide/segment_12A_export_and_import.md`. See "Session settings — separate
  sub-plan" below.
- **Real configuration import format / service.** Segment 12A owns
  the CSV format, the `apply_session_config` service, and the
  `/operator/sessions/{id}/import-config` route.
- **Real rule-builder UI for assignments.** The full rule menu
  beyond FullMatrix is Segment 13. Slot 3 ships with FullMatrix-
  only as the rule-selector default; the CSV upload alternative
  covers the manual case.
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

## Session settings — separate sub-plan

Slot 4 is **left inert in 11J** for two reasons:

1. The underlying capability does not exist yet. Reviewers,
   Reviewees, and Assignments all have working import pipelines
   that 11J merely composes onto Home. Session settings (the
   3-column configuration CSV) is a Segment 12A deliverable; its
   `apply_session_config` service ships in 12A PR 2.
2. Bundling slot 4's wiring into 11J would couple 11J's review
   surface (composition + lock-toggle) to 12A's review surface
   (config CSV format + service-layer correctness). Keeping them
   separate keeps each PR small.

The seam stays as 11H pinned it: when 12A PR 6 lands, it flips
slot 4's `is_wired=False` to `True` and supplies
`wire_url="/operator/sessions/{id}/import-config"`; no template
or macro changes needed. 11J's PR sequence does not touch slot 4
at all.

The "separate sub-plan" framing is mostly a doc one — 12A already
owns the route + the service + the format. The only 11J-flavoured
work that remains around slot 4 is whatever banner / error-flow
parity it needs with slots 1-3 once it goes live, and that's
naturally part of 12A PR 6's review.

## Interaction with Segment 12A

12A ships export + import of a session's full configuration as a
3-column CSV. Its PR 2 lands the import service; PR 6 lands the
`POST /operator/sessions/{id}/import-config` route + the slot 4
wiring on Quick Setup.

The seam:

1. **11J ships first**, with slot 4 left inert (the 11H scaffold's
   state). Slots 1-3 are live; the Lock / Unlock toggle is wired
   uniformly across the card.
2. **12A PR 6 swaps slot 4 from inert to live** in the same
   `<section class="quick-setup-slot ...">` container that 11H
   shipped. The diff is small: replace the disabled-button stub
   with `<input type="file" name="file">` + a submit button that
   posts to `/operator/sessions/{id}/import-config`, set
   `is_wired=True` and `wire_url=…` on the slot's adapter entry.
   The inline-confirmation pattern from slots 1-3 reuses cleanly
   because 12A's import is also wipe-and-replace, and the
   lifecycle gate matches (12A enforces `_require_editable` the
   same way the per-entity importers do, so the unlocked-on-`ready`
   rejection banner reuses without modification).
3. **The export side of 12A (PR 1)** keeps its own anchor decision
   — likely the Session Details card footer — and stays out of
   the Quick Setup card. Quick Setup is for ingestion, not
   extraction.

Document the seam in 12A's plan when it picks up the anchor
decision in its PR 6; this guide already names it from the 11J
side so the order stays clear.

## Proposed PR sequence

### PR A — Lock / Unlock toggle + slots 1 + 2 (Reviewers, Reviewees)

**Goal.** Wire the unified lock toggle and flip the Reviewers and
Reviewees slots from inert (11H scaffold state) to live. Slot 3
(Assignments) and slot 4 (Settings) stay inert.

- **No new template / partial / macro.** 11H's
  `_quick_setup_card.html` and `quick_setup_slot(slot)` macro
  already render the slots and the lock toggle. PR A only
  changes:
  - `views.build_quick_setup_context(session, …)` — accept the
    operator's last toggle action (via query-string flag, see
    Implementation pointers), retire `is_disabled` as a separate
    visual flag, set `show_lock_toggle=True` in every editable-
    conceivable state, and set `is_wired=True` /
    `wire_url=…` on the Reviewers and Reviewees slot entries.
  - The dormant banner population (un-hide + populate inner
    HTML) on error / replacement-confirmation render via the new
    `views.cascade_message_for_replace(kind, counts)` helper.
- **No new dataclass.** `QuickSetupSlot` and `QuickSetupContext`
  stay as 11H ships them; the `is_disabled` field can stay as a
  label-only signal for the description copy or retire entirely
  (PR A's call). `is_locked` becomes the single visual lock
  signal.
- Three new routes:
  - `POST /operator/sessions/{id}/quick-setup/reviewers`
  - `POST /operator/sessions/{id}/quick-setup/reviewees`
  - `POST /operator/sessions/{id}/quick-setup/lock` (the toggle)
  The first two delegate to a thin `_handle_quick_setup_import`
  wrapper that calls the same `_handle_import` core as the per-
  entity routes, but renders Home (via the existing context
  builders) on validation failure instead of the per-entity
  page. On success: 303 → Home with **no query flag** — the
  count indicator on the slot updates in place; no flash banner.
  On parse / validation error: 303 → Home with a
  `?quick_setup_error={kind}` flag so the GET render places a
  `.banner.banner-error` (with mandatory Cancel button) inside
  that slot, and the URL fragment lands on `#quick-setup-{kind}`.
  On `ready`-state rejection from `_require_editable`: 303 → Home
  with `?quick_setup_error={kind}&quick_setup_reason=lifecycle`
  so the banner copy is the lifecycle-specific "Pause first"
  message.
- The toggle route flips a per-session, per-operator UI flag —
  cleanest implementation is a server-side cookie (`Set-Cookie:
  qsu_{session_id}=1; Path=/operator/sessions/{id}; HttpOnly`)
  that the context-builder reads to determine `is_locked` on the
  next render. Alternative: a query-string flag echoed on the
  redirect target (`?qs_unlocked=1`) — simpler but doesn't survive
  a same-tab refresh of Home. Pick the cookie path for parity
  with Instruments page's lock state, which already uses
  cookie-backed UI state.
- Lifecycle gate stays where it already is in `_handle_import`'s
  call to `_require_editable`. Lock state is purely visual; the
  service layer is the source of truth for "can this mutate
  right now."
- **Banner population.** 11H's scaffold ships dormant banner
  containers (`<div class="banner banner-warning ..." hidden>`).
  On error / replacement-confirmation render, the context-builder
  un-hides the right banner and populates its body via the new
  `views.cascade_message_for_replace(kind, counts)` helper.
  Markup unchanged from 11H.
- Tests:
  - **Lock toggle.** Initial render on `draft` shows
    `is_locked=True`; clicking Unlock 303s to a render with
    `is_locked=False` (cookie set); clicking Lock 303s back.
    Toggle is rendered on `ready` too; unlocking on `ready` is
    permitted (visual unlock only). Cookie scoped per-session.
  - **Per-slot golden-path upload** (each slot independently) on
    a `draft` session — assert the success render carries **no**
    `.banner` element and the count indicator reflects the new
    value.
  - **Replacement confirmation banner** fires when count > 0 on
    submit; carries a `.btn.alert` Cancel + `.btn.danger-solid`
    Confirm; second submit (with `confirm_replace=1`) applies.
    Cancel link points at `?` (no flag) with `#quick-setup-{kind}`
    fragment.
  - **Cascade-clearance copy** renders inside the same
    confirmation banner when assignments exist on a reviewer /
    reviewee replace.
  - **Parse / validation error path:** route 303s with
    `?quick_setup_error={kind}`; GET render shows
    `.banner.banner-error` scoped to that slot with the mandatory
    Cancel button; other slots are unaffected.
  - **Lifecycle-rejection path** (the new state-aware behaviour):
    on a `ready` session, with the card unlocked, a submit is
    rejected at the service layer; route 303s with
    `?quick_setup_error={kind}&quick_setup_reason=lifecycle`; GET
    render shows the `.banner.banner-error` with the
    "Pause the session before applying setup changes" copy.
  - **Validated → re-upload** flips the session back to `draft`
    (already covered in `_handle_import`'s underlying tests; one
    additional integration test confirms the route surface
    inherits the behaviour).

### PR B — Wire slot 3 (Assignments)

**Goal.** Flip slot 3 from inert (11H scaffold state) to live.
The rule-selector and CSV-mode toggle markup already render in
11H; PR B wires them. Lock toggle behaviour from PR A applies
unchanged.

- **No partial / macro extension.** 11H ships the rule-selector
  + CSV-mode toggle (rule menu rendered with the
  `<select disabled>` showing FullMatrix and the
  "more rules ship with Segment 13" caption). PR B's adapter
  flips `is_wired=True` and supplies
  `wire_url="/operator/sessions/{id}/quick-setup/assignments"`.
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
  - **Rule-mode submission** on an empty assignments table
    generates the FullMatrix row count and the slot's count +
    rule indicator reflects it on the next render — assert no
    `.banner` element on the success page.
  - **Rule-mode submission** on a populated table requires the
    confirmation banner; Cancel returns to a clean URL with the
    `#quick-setup-assignments` fragment.
  - **CSV-mode parse-error path** renders `.banner.banner-error`
    scoped to slot 3 only with the mandatory Cancel button;
    success path updates the count + "loaded from file"
    indicator without a flash banner.
  - **Lifecycle-rejection path on `ready`** — same shape as in
    PR A; assert the rejection banner appears scoped to slot 3.

## Implementation pointers

- **No success flash; count indicator is the signal.** Success
  303s carry no query-string flag. The Home GET render reflects
  the new state directly via the slot's count indicator, the
  cleared file input, and (for assignments) the rule label
  refreshing. Tests should assert the absence of `.banner` on
  success renders so we don't drift back into flash territory.
- **Banners only when something needs operator attention, and
  always with Cancel.** Three cases need a banner: (a) parse /
  validation error from the importer, (b) cascade-preview
  confirmation before a populated-slot replacement, (c)
  lifecycle-rejection when an unlocked submit hits `ready`. All
  follow `spec/domain_assumptions.md` §"Inline error / warning banners":
  - Use `.banner.banner-error` for errors and lifecycle-
    rejections; `.banner.banner-warning` for cascade-preview
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
    error / lifecycle-rejection banners Cancel is the only
    button.
  - Render the banner **inside the destination slot**, not at
    the top of Home, so it's visually anchored to the action
    that produced it.
- **Cascade copy.** The cascade itself is automatic in the
  existing `save_reviewers` / `save_reviewees` paths; this segment
  only changes the confirmation banner copy. Centralise the
  sentences in a small helper
  (`views.cascade_message_for_replace(kind, counts)`) so the
  cases live in one place.
- **Lock-toggle state lives in a per-session cookie.** Cookie
  name `qsu_{session_id}` (Quick-Setup-Unlocked). Set by the
  `POST .../quick-setup/lock` handler; read by
  `views.build_quick_setup_context` to decide `is_locked`.
  Cookies are scoped to `/operator/sessions/{id}` so they don't
  leak across sessions. `HttpOnly` for safety (no JS reads it
  back). The cookie is opt-in greying off; absence ⇒ default
  locked. Alternative implementation: a `?qs_unlocked=1`
  query-string flag — simpler but doesn't survive a same-tab
  refresh; pick the cookie path for parity with the Instruments
  page's lock state.
- **Service-layer is the source of truth for mutation
  permission.** The lock toggle is *visual only* — it does not
  bypass `_require_editable`. On `ready` the toggle cosmetically
  unlocks the card; the importer still rejects the post. The
  rejection renders as the `.banner.banner-error` with copy that
  names the next move. This is the whole point of "status
  awareness": the visual state and the actual permission state
  are deliberately decoupled, with the visual one being the soft
  guard and the service one being the hard gate.
- **Don't touch the per-entity Manage pages.** Their upload UIs
  stay; they share the pipeline with Quick Setup. Removing them
  is a Segment 15 question, not 11J.
- **No new audit shapes.** Every mutation routes through an
  existing service helper that already emits its own audit event;
  do not add a parallel `quick_setup.*` event family. The
  card-level concept doesn't need its own audit trail. The lock
  toggle is operator UI state and is not audited.
- **Do touch the 11H scaffold's context-builder.** Retiring
  `is_disabled` as a separate visual treatment, and making
  `show_lock_toggle=True` on `ready`, are scaffold-level changes
  that PR A lands alongside the toggle wiring. The scaffold's
  snapshot tests need updates accordingly; the snapshot delta
  is the lock toggle's now-rendering on `ready` and the body
  greying applying via `.locked` only (no separate
  `.card.disabled`).

## Out of scope (cross-references)

- **Slot 4 (Session settings) wiring** — Segment 12A PR 6.
  Tracked separately per "Session settings — separate sub-plan"
  above.
- **Real configuration import format / service / route** —
  Segment 12A.
- **Rule-builder beyond FullMatrix** — Segment 13
  (`guide/segment_13_rulebased_assignment_builder_plan.md`).
- **Inline-editable Manage pages** — Segment 15, catalog item #25.
- **Sessions-list per-row Delete** — Segment 15, catalog item #23.
- **Extract Data card** — Segment 11H. Sibling Home-body card; the
  status-awareness model 11J unifies on is borrowed from this
  card's "always reachable, status-aware via greying" approach.

## Test impact

- New `tests/integration/test_quick_setup_card.py` covering:
  per-slot golden path (slots 1, 2, 3 only — slot 4 stays in the
  scaffold tests), replace-confirmation copy, cascade copy,
  lock-toggle behaviour across `draft` / `validated` / `ready`,
  scoped error reporting per slot, lifecycle-rejection banner on
  `ready` with the card unlocked.
- Updates to `tests/integration/test_quick_setup_scaffold.py`
  (the 11H snapshot file): the `ready` snapshot now renders the
  lock toggle and uses `.locked` greying instead of
  `.card.disabled`. The slot-4 inert snapshot is unchanged.
- No churn on existing reviewer / reviewee / assignment import
  tests — they cover the underlying pipeline that this segment
  composes onto, and the pipeline doesn't change.
- One small unit test on `views.build_quick_setup_context` pinning
  the new lock-toggle visibility matrix (toggle visible on
  `draft` / `validated` / `ready`; suppressed only in the
  new-session preview variant).

## Doc impact

- `guide/todo_master.md` — move 11J from **Upcoming** to **Done**
  once PR B ships; mention the slot-4-deferral and the 12A seam
  in the entry.
- `docs/status.md` — timeline entry per PR.
- `spec/quick_setup_card_spec.md` — small revision in PR A: the
  lifecycle table line for `ready` / `closed` changes from
  "Disabled behind yellow lock card" to "Greyed via the same
  body-greying as `draft` / `validated`; Lock / Unlock toggle
  visible." The card's state-conditional copy section in
  `spec/session_home.md` §"Quick Setup card" updates the same
  way: the `ready` description "The Lock / Unlock button does
  not render in this state" line is removed; the "Pause the
  session to re-enable bulk setup" copy stays as the description.
- `guide/segment_12A_export_and_import.md` — small follow-on note when 12A's PR 6
  lands: replace its "Anchor: a 'Import config' button on Session
  Home" line (or equivalent) with "swap 11J's slot-4 placeholder
  for the real upload form, reusing the lock-toggle pattern PR A
  established."
- No new spec doc — this guide doubles as the spec for the new
  status-awareness model. If a slot detail proves ambiguous in PR
  review, fix `spec/quick_setup_card_spec.md`, not the
  implementation.
