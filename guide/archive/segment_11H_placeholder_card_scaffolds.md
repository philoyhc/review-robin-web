# Segment 11H — Placeholder card scaffolds (Quick Setup + Extract Data)

Stub. Implementation plan for replacing the two
`placeholder_card(...)` stubs on Session Home with their
**inert-but-fully-rendered** real shapes — every slot / row /
button visible and laid out, but every interactive control
disabled until Segments 11J and 12A wire them up.

The two stubs today, both at
`app/web/templates/operator/session_detail.html`:
- `placeholder_card(id="quick-setup", …)` at line 174
- `placeholder_card(id="extract-data", …)` at line 187

11H ships the **visual + DOM contract** for both cards. Segment
**11J** then wires Quick Setup's four slots to live POSTs;
Segment **12A** PR 6 wires Extract Data's five downloads + zip
bundle to live GETs. Splitting the visual scaffold into 11H
means:

- The card layout, accessibility, lifecycle behaviour, mobile
  collapse, and DOM IDs / fragment anchors all settle in one
  PR set, before any service-layer wiring debates.
- 11J / 12A's PRs become thin wiring diffs (flip a
  `is_wired=True` flag on a slot or row, plug a `wire_url`)
  rather than "build slot from scratch + wire it." Each slot
  ships independently.
- Operators see an honest preview of what's coming on Home,
  in the right shape, instead of a single big "Set up" /
  "Extract" button that obscures the eventual complexity.

Catalog item: this segment was previously listed in
`guide/todo_master.md` "Upcoming" as "Segment 11H — Extract
Data" with a different scope (which folded into 12A by PR
#473). Restoring 11H with this scaffolding scope is a
re-purpose, not a revival.

## Status

Planning. Sized as **2 PRs**, independent and parallelizable
(they touch disjoint `placeholder_card(...)` sites):

1. **PR A — Quick Setup scaffold.** Replaces
   `placeholder_card(id="quick-setup", …)` with the four-slot
   layout from `spec/quick_setup_card_spec.md`. All controls
   disabled.
2. **PR B — Extract Data scaffold.** Replaces
   `placeholder_card(id="extract-data", …)` with the
   five-download + zip layout from
   `guide/segment_12A_export_and_import.md`. All controls disabled.

## Why a scaffold-only segment

Three reasons the scaffold is worth its own segment rather than
being PR A of 11J / PR 6 of 12A:

- **Visual review without service-layer noise.** The card
  layout, mobile collapse, lifecycle / lock-card behaviour,
  empty-state copy, and DOM IDs are reviewable in isolation.
  Bundling them into a wiring PR forces the reviewer to read
  the markup diff *and* the route handler / service helper /
  audit emitter at the same time.
- **Stable seams for 11J / 12A.** Once 11H ships, every fragment
  anchor (`#quick-setup-reviewers`,
  `#extract-data-responses`), every slot's wire-target marker,
  every count-indicator placement is final. 11J / 12A
  consumers don't have to worry that their wiring patch will
  collide with someone else's markup tweak.
- **Stand-alone review of the operator-facing message.** The
  current `placeholder_card` macro renders one disabled button
  with a tooltip — that's it. Operators don't see the eventual
  shape until the real implementation lands. 11H gets the
  shape on screen sooner, with copy that says "wired in 11J /
  12A" rather than "lands in Segment 15"-style vagueness.

The cost is small: each card is one Jinja partial + one
view-shape adapter + a Storybook-style snapshot test. No
service-layer code, no new routes, no audit events, no
migrations.

## Scope

In:

### Quick Setup card scaffold (PR A)

- New template partial
  `app/web/templates/operator/partials/_quick_setup_card.html`
  with the four-slot layout from `spec/quick_setup_card_spec.md`:
  - Slot 1 — Reviewers (`<input type="file" disabled>` + Submit
    `disabled` + count indicator).
  - Slot 2 — Reviewees (same shape).
  - Slot 3 — Assignments (rule selector + CSV upload toggle,
    both disabled; count + active-rule indicator).
  - Slot 4 — Configuration import (placeholder per current
    11J PR C — disabled file input + Submit, "Wired in
    Segment 12A PR 6" copy).
- A `quick_setup_slot(slot)` Jinja macro that takes a
  `QuickSetupSlot` dataclass and renders one slot. Macro
  signature is the wire seam — 11J's PRs flip
  `slot.is_wired=True` and pass `slot.wire_url=…` to enable a
  slot, no markup churn.
- New view-shape adapter
  `views.build_quick_setup_context(session)` returning a
  dataclass with four `QuickSetupSlot` instances. Each slot
  carries:
  ```python
  @dataclass(frozen=True)
  class QuickSetupSlot:
      key: str               # "reviewers" / "reviewees" / "assignments" / "settings"
      label: str             # "Reviewers"
      count: int             # current population
      count_summary: str     # "8 currently" / "none yet"
      mode: SlotMode         # FILE_UPLOAD / RULE_OR_CSV (slot 3)
      is_wired: bool         # 11H ships everything False
      wire_url: str | None   # 11J / 12A populate
      coming_in: str | None  # "Wired in Segment 11J PR A" while is_wired=False
      lock_state: LockState  # NORMAL / LOCKED (yellow lock card behind it)
  ```
- Per-slot DOM contract — finalised in this PR, never changes:
  - `<section class="quick-setup-slot" id="quick-setup-{key}">`
    so URL fragments scroll directly to a slot.
  - `data-wire-target="quick-setup-{key}"` on the inner form
    placeholder so 11J's wiring PRs can locate the slot
    without a CSS-selector contract.
  - Replacement-confirmation banner placeholder per
    `spec/domain_assumptions.md` — empty `<div class="banner
    banner-warning banner-scroll-target"
    id="quick-setup-{key}-banner" hidden>` so 11J's PRs
    populate it without re-rolling the markup. (The `hidden`
    attribute is the inert state; 11J flips it via the
    server-side render condition.)
  - Same dormant placeholder for the parse-error banner.
- Lifecycle behaviour wired even with controls disabled:
  - `draft` / `validated`: slots interactive in the visual
    sense (controls visible, hover states, focus rings) but
    `disabled` so submit doesn't do anything yet.
  - `ready` / `closed`: the existing yellow lock card wraps
    the entire Quick Setup card, hiding the slot details
    behind the "Setup edits are paused" copy. This matches
    `spec/quick_setup_card_spec.md` §"Lifecycle and state
    behavior summary".
- Empty-state copy on each disabled slot's count indicator:
  "0 reviewers · wired in Segment 11J PR A" while
  `is_wired=False`. 11J flips the suffix off when the slot
  goes live.
- `placeholder_card(id="quick-setup", …)` block at
  `session_detail.html:174` is **deleted** — replaced by the
  new partial include.
- Tests (snapshot-style, since there's no behaviour to drive):
  - Card renders all four slots on a `draft` session with
    the right counts.
  - Lock state on `ready` / `closed` wraps the card with
    the yellow lock-card partial and hides the slot
    details (snapshot the rendered DOM).
  - Mobile-collapse (`<800px`) reorders slots in DOM order.
  - DOM IDs / fragment anchors (`#quick-setup-reviewers`
    etc.) match the spec contract — pin each via direct
    selector lookup.
  - All interactive controls carry `disabled` and a `title`
    attribute naming the wiring PR.

### Extract Data card scaffold (PR B)

- New template partial
  `app/web/templates/operator/partials/_extract_data_card.html`
  with the five-row + zip-bundle layout from
  `guide/segment_12A_export_and_import.md` PR 6:
  - Row 1 — Session settings (`session-{code}-settings.csv`).
  - Row 2 — Reviewers (`session-{code}-reviewers.csv`).
  - Row 3 — Reviewees (`session-{code}-reviewees.csv`).
  - Row 4 — Assignments (`session-{code}-assignments.csv`).
  - Row 5 — Responses (`session-{code}-responses.csv`).
  - Footer — "Download all" zip bundle button.
- An `extract_data_row(row)` macro consuming an
  `ExtractDataRow` dataclass:
  ```python
  @dataclass(frozen=True)
  class ExtractDataRow:
      key: str               # "settings" / "reviewers" / …
      label: str             # "Session settings"
      filename: str          # "session-{code}-{key}.csv"
      count: int             # row count for the count summary
      count_summary: str     # "8 reviewers" / "104 responses"
      is_wired: bool         # 11H ships all False
      download_url: str | None  # 12A PR 6 populates
      coming_in: str | None  # "Wired in Segment 12A PR 3-5"
                             # for per-entity rows; "Wired in
                             # Segment 12A PR 1" for settings;
                             # "Wired in Segment 12A PR 5" for
                             # responses
  ```
- New view-shape adapter
  `views.build_extract_data_context(session)` returning the
  five rows + the zip-bundle row. Reuses existing count
  helpers (`csv_imports.existing_reviewer_count`,
  `existing_reviewee_count`,
  `existing_assignment_count`, plus a new
  `responses.session_response_count(session)` one-liner —
  the only service-layer addition in this segment).
- Per-row DOM contract — finalised in this PR:
  - `<section class="extract-data-row"
    id="extract-data-{key}">`.
  - `data-wire-target="extract-data-{key}"` on the row's
    button placeholder.
  - Disabled `<a class="btn primary-outline" aria-disabled="true"
    title="Wired in Segment 12A PR …">Download</a>` for each
    per-entity row. 12A's PRs swap `aria-disabled` for a
    real `href`.
- "Download all" footer button — disabled, same copy
  treatment.
- **No lifecycle gate** per
  `guide/segment_12A_export_and_import.md` "Data extraction (PRs 3-6)" — the
  card stays visible and interactive in every lifecycle
  state. Extraction is read-only and useful at any state.
  Once 12A's PRs wire the buttons, they remain clickable
  even on `ready` / `closed`.
- `placeholder_card(id="extract-data", …)` block at
  `session_detail.html:187` is **deleted** — replaced by the
  new partial include.
- Tests:
  - Card renders all five rows + footer on a populated
    `draft` session with the right counts.
  - Empty session: header rows render with "0
    reviewers" / "0 responses" copy without breaking
    layout.
  - Card stays visible in `ready` / `closed` (no lock-card
    wrap).
  - DOM IDs match the spec contract.
  - All buttons carry `aria-disabled="true"` and a `title`
    naming the wiring PR.

Out:

- **All wiring.** No new routes, no new service-layer code
  (other than the one `responses.session_response_count`
  helper for the count adapter), no audit events. The card
  is purely visual.
- **All forms / submit handlers.** The slot-3 rule selector
  is rendered with its dropdown options visible (a
  `<select disabled>` so operators can see the eventual
  rule menu) but no POST endpoint exists.
- **The Quick Setup configuration-import slot's eventual
  graduation step.** That belongs to 12A PR 6, which swaps
  the placeholder copy for the live PR 2 form.
- **Replace-confirmation logic.** The dormant banner
  containers exist; the populate-confirmation-banner-on-
  submit branch lands in 11J PRs A-B with the actual
  service-layer cascade copy.
- **Cascade-clearance copy and helper
  (`views.cascade_message_for_replace`).** 11J ships it
  with the live wiring; 11H's banner placeholder is empty.
- **Audit events.** None — extraction is read-only and
  Quick Setup's audit emitters fire from the underlying
  service helpers (see 11J).

## Wiring contract for 11J and 12A

The seams 11H pins down — final, will not move:

### Quick Setup (consumed by 11J)

- Partial path:
  `operator/partials/_quick_setup_card.html`.
- Macro: `quick_setup_slot(slot)`. 11J's PRs change which
  `QuickSetupSlot.is_wired=True` and what `wire_url` they
  carry; markup unchanged.
- DOM IDs: `quick-setup-{key}` per slot,
  `quick-setup-{key}-banner` per dormant banner. URL
  fragments and Cancel-return anchors per
  `spec/domain_assumptions.md` resolve against these.
- View adapter: `views.build_quick_setup_context(session)`.
  Returns a dataclass that holds the four slots + the
  card-level `lock_state`. 11J's PRs extend the adapter
  with the wire-up details (URL, audit-event handle, etc.)
  but the dataclass shape is stable.
- Lifecycle behaviour is finalised here. 11J doesn't
  re-derive lock state.

### Extract Data (consumed by 12A)

- Partial path:
  `operator/partials/_extract_data_card.html`.
- Macro: `extract_data_row(row)`.
- DOM IDs: `extract-data-{key}` per row.
- View adapter:
  `views.build_extract_data_context(session)`.
- The "Download all" zip-bundle button has its own DOM ID
  `extract-data-bundle` and its own `ExtractDataRow`-shaped
  context entry; 12A PR 6 wires it the same way.

## Proposed PR sequence

### PR A — Quick Setup card scaffold

**Goal.** Card on Home renders all four slots with the right
counts and DOM contract; every control is inert.

- New `_quick_setup_card.html` + `quick_setup_slot` macro.
- New `QuickSetupSlot` dataclass + `LockState` /
  `SlotMode` enums in `app/web/views.py`.
- New `views.build_quick_setup_context(session)` adapter.
- Replace the `placeholder_card(id="quick-setup", …)`
  include in `session_detail.html` with `{% include
  "operator/partials/_quick_setup_card.html" %}` plus
  the context-builder call.
- Snapshot tests under
  `tests/integration/test_quick_setup_scaffold.py` (the
  test file 11J's PRs will extend with behavioural
  coverage; renaming will preserve git history of both).
- No service-layer changes.

### PR B — Extract Data card scaffold

**Goal.** Card on Home renders all five rows + the zip
bundle footer with the right counts; every download is
inert.

- New `_extract_data_card.html` + `extract_data_row` macro.
- New `ExtractDataRow` dataclass in `app/web/views.py`.
- New `views.build_extract_data_context(session)` adapter.
- New `responses.session_response_count(session) -> int`
  helper — the only service-layer addition. Backed by a
  single `select(func.count())` query.
- Replace the `placeholder_card(id="extract-data", …)`
  include in `session_detail.html` with the new partial.
- Snapshot tests under
  `tests/integration/test_extract_data_scaffold.py`.
- No new routes, no audit events.

## Implementation pointers

- **`disabled` vs `aria-disabled`.** Form controls (`<input>`,
  `<button type="submit">`, `<select>`) get the native
  `disabled` attribute — it removes them from form
  submission and the keyboard tab order, which is correct
  for an inert scaffold. Anchor links (`<a>`) get
  `aria-disabled="true"` plus a missing `href` (or
  `href="#"` with a `preventDefault` not needed since
  there's no JS) — anchors don't honour native `disabled`.
  PR B's "Download" buttons are anchors today (per
  `guide/segment_12A_export_and_import.md` PR 6 → `<a class="btn ...">`
  with `Content-Disposition` header), so they get the
  `aria-disabled` treatment.
- **Tooltip wording.** Each disabled control's `title`
  attribute names the **specific PR** that wires it, not
  the segment. "Wired in Segment 11J PR A" tells an
  operator (and a contributor) more than "Coming in 11J".
  When 11J PRs land, they remove the `title` attribute on
  the slot they wire (since it's no longer accurate); the
  scaffold's adapter checks `is_wired` and only emits the
  `title` when `False`.
- **Snapshot-test fixture sessions.** Both PRs benefit from
  one fixture each: a draft session populated with
  realistic counts (8 reviewers, 13 reviewees, 2
  instruments, 104 assignments, 50 responses). Lives in
  `tests/conftest.py` as a session-scoped fixture so
  later 11J / 12A tests reuse it.
- **Don't pre-emit anything.** It's tempting to write a
  `data-quick-setup-form-action` attribute that 11J's PRs
  fill in, but if 11J ends up using a `<form action="…">`
  with a different attribute name, the scaffold's
  unused attribute becomes vestigial. Keep the scaffold
  to what it actually renders today.
- **No JS.** Both cards are static markup until 11J / 12A
  add forms + server-side handlers. Keeps the scaffold
  cheap to review and aligns with the rest of the app's
  no-JS-build-step convention.
- **Wire-up order independence.** PR A and PR B touch
  disjoint placeholder sites. They can land in either
  order or in parallel.

## Out of scope (cross-references)

- **Quick Setup wiring** — Segment 11J. Each of 11J's three
  PRs flips one of the four slots from `is_wired=False` to
  `True` and supplies a `wire_url`. (Slot 4 graduates with
  Segment 12A PR 6 instead.)
- **Extract Data wiring** — Segment 12A. Specifically:
  - PRs 1, 3, 4, 5 ship the per-entity extract routes
    (settings, reviewers, reviewees, assignments,
    responses). Each makes its row in 11H's scaffold
    live.
  - PR 6 wires the "Download all" zip bundle and the
    Configuration-import slot in Quick Setup, retiring
    the temporary "Download config" button on Session
    Details.
- **Quick Setup card spec** — `spec/quick_setup_card_spec.md`
  is the contract this scaffold implements. If the
  scaffold reveals a layout / copy inconsistency, fix the
  spec, not the scaffold.
- **Service-layer counts.** The
  `responses.session_response_count` helper PR B adds is
  the smallest addition that lets the scaffold show
  honest counts; richer aggregations (per-instrument,
  per-reviewer) belong to 12A PR 5 (Responses extract)
  and Segment 11C (Operations consolidation).
- **Audit events for previewing the placeholder.**
  Rendering an inert card needs no audit; this isn't a
  read worth tracking.

## Test impact

- New
  `tests/integration/test_quick_setup_scaffold.py` (PR A)
  and
  `tests/integration/test_extract_data_scaffold.py` (PR B)
  covering snapshot DOM, lifecycle states, mobile collapse,
  empty / populated sessions, and the disabled-control
  contract.
- No churn on existing tests — the
  `placeholder_card(id="quick-setup", …)` /
  `placeholder_card(id="extract-data", …)` stubs they
  asserted against are replaced; tests touching those IDs
  in their old shape get updated assertions.
- Two new fixture sessions
  (`populated_draft_session`, `empty_draft_session`) in
  `tests/conftest.py` reused by 11J / 12A test files.

## Doc impact

- `guide/todo_master.md` — restore an 11H entry under
  **Upcoming** between 11J and 11K, with this guide as
  the plan. Note the depend-on order: 11H → 11J → 12A
  PR 6 (lit-up final shape). Resolves the "previously
  retired" wording from the earlier cleanup pass.
- `docs/status.md` — timeline entry per PR.
- `guide/segment_11J_quick_setup_card.md` — each PR's
  scope shrinks: "build the slot from scratch" becomes
  "wire the slot 11H scaffolds." Cross-reference 11H as
  the visual prerequisite. The PR scope details (wire URL,
  audit emit, banner population, lifecycle gate enforced
  at the route layer) all stay; only the markup-creation
  bullets move to 11H.
- `guide/segment_12A_export_and_import.md` — PR 6's scope shrinks the same
  way: the markup-creation bullets move to 11H, leaving
  PR 6 as a thin "wire the rows" diff plus the zip
  bundle (which is genuinely new code) plus the
  Configuration-import slot graduation.
- `spec/quick_setup_card_spec.md` — no changes expected.
  This guide implements the existing spec.
- No new spec doc — this guide doubles as the spec for the
  scaffold's DOM contract until 11J + 12A converge it
  with the full-fidelity rendered card.
