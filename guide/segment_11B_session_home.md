# Segment 11B — Session Home rebuild

Implementation plan for bringing `session_detail.html` (the per-session
Control Panel) onto the layout and behaviour described in
`spec/session_home.md`. Absorbs the unfinished `#22` (Home body
rebuild) and `#30` (Quick Setup card on Home) from segment 11A's
Tier 4 bundle.

The functional spec is `spec/session_home.md`. This guide is the
implementation plan against that spec.

## Status

Planning. PRs **A → F** are sized to land in dependency order; each
is independently shippable.

**Recommended sequence after review:**
**A** → (pre-B verification spike) → **E** as a CSS warm-up →
**B** → **C** → **D** → **F**. E is moved earlier because it's
CSS-only and risk-free; running it before B gives the test suite
one less thing to react to when B's bigger sweep lands. The
verification spike (see "Pre-PR-B verification" below) is not a
PR — just findings recorded in PR B's description.

## Scope

In:

- Replace the existing "Run Session" + conditional "Validation
  summary" cards with a single **Contextual primary action card**
  whose contents swap by lifecycle state (Validate Setup → Activate
  Session → Pause Session).
- Add an **Extract Data card** to the left column (placeholder body
  until Segment 12 ships real extraction).
- Wire **Quick Setup** disabled-greyed treatment when the session is
  Activated (no yellow lock card on Home — the action card carries
  the messaging).
- Drop the duplicate "Status:" pill from the Session Details card.
- Retire the two top-of-body lock cards (existing-responses warning,
  lifecycle-locked revert form). Their messaging moves into the
  contextual primary action card.
- Introduce a single **lifecycle display-label mapping** so every
  user-facing surface renders `ready` as "Activated".
- Retire the stale `.pill-lifecycle-closed` v2 CSS rule (no
  canonical "closed" state).
- Update `spec/operator_ui_concept.md` to reflect the new Home
  shape.

Out:

- Real Quick Setup implementation (the placeholder card stays a
  placeholder until the Quick Setup spec is implemented as its own
  segment).
- Real Extract Data implementation (Segment 12).
- Per-entity setup-page warnings when responses exist (the
  existing-responses warning currently on Home is retired here; the
  surface warnings should land on the per-entity setup pages but
  that's tracked separately).
- Renaming the `ready` enum to `activated` at the database / API
  layer. The divergence is handled at the display layer per spec.

## Gap against the spec

| Spec requirement | Current state | Action |
|---|---|---|
| Two-column body (left = run, right = metadata + danger) | Two `.bottom-left` flex columns inside `.bottom-grid` | ✓ already correct |
| Left col — Contextual primary action card (state-conditional) | Two cards: "Run Session" 4-CTA card + "Validation summary" conditional card | **Major rebuild** — collapse into one state-aware card |
| Left col — Quick Setup card (disabled-greyed when Activated) | Placeholder card; no disabled treatment | Add disabled state when `is_ready` |
| Left col — Extract Data card (state-conditional) | One disabled CTA labelled "Extract Data" inside Run Session | Promote to its own card |
| Right col — Session Details (no inline status pill) | Has a duplicate "Status: ..." pill inside the card | Drop the inline pill; Edit button stays |
| Right col — Danger Zone (Delete Session disabled when Activated) | Suppresses the form when `is_ready` | Already correct; small polish |
| Top-of-body lock cards | Two `.card.lock` rendered above the grid | Retire — action card carries the messaging |
| Pause Session (Activated → Draft) | `Revert to draft` form inside the lock card; underlying route exists | Reuse; relabel as "Pause Session" with new confirmation copy |
| Lifecycle display mapping (`ready` → "Activated") | Templates render bare enum value; CSS uppercases | Add helper + thread through every UI surface |
| `.pill-lifecycle-closed` retired | Rule still in v2 CSS | Remove |
| Doc updates (`operator_ui_concept.md`) | Reflects old layout | Update |

## Proposed PR sequence

**PR A — Lifecycle display mapping (foundation).** Prepare every
template that renders `session.status` to use a display label.

- New helper: `lifecycle_display_label(status: str) -> str` in a
  new `app/services/lifecycle_display.py` module. (The plan
  originally allowed `app/services/session_lifecycle.py` as the
  home with promotion to its own module "if it grows" — taking
  the dedicated module up front since multiple call sites and
  tests will reach for it, and keeping it out of
  `session_lifecycle.py` avoids muddling lifecycle *transitions*
  with lifecycle *display*.) Keep it tiny:

  ```python
  DISPLAY_LABELS = {"ready": "Activated"}
  def lifecycle_display_label(status: str) -> str:
      return DISPLAY_LABELS.get(status, status.capitalize())
  ```

- Expose as a Jinja global / filter so templates do
  `{{ session.status | lifecycle_label }}`.
- Sweep templates that render the bare enum in user-visible copy
  (status pill, page header, prose, button labels, confirmations).
- Visible change: `READY` → `ACTIVATED` everywhere the lifecycle
  state appears in user-facing copy. Other states unchanged.
- Enum stays for slugs / API / log messages / database / CSS class
  names.

**Pre-PR-B verification spike** (not a PR — record findings in PR
B's description). Two cheap checks that determine PR B's shape:

1. **`/revert` route coverage.** Grep the route handler + tests to
   confirm whether `POST /operator/sessions/{id}/revert` accepts
   both `validated → draft` (current "invalidate") and `ready →
   draft` (current "revert"). If both work via the same endpoint,
   PR B is "relabel a button + new confirmation copy." If
   `validated → draft` requires a separate `invalidate` endpoint,
   PR B either wires up the new endpoint or points the supporting
   "Revert to Draft" link at it.
2. **Test sweep size.** Grep templates and tests for `Run Session`,
   `Validation summary`, `Revert to draft`, `READY`, and `ready` as
   user-visible body text. Note the hit count in PR B's
   description so the reviewer knows the sweep was bounded, not
   missed.

**PR B — Contextual primary action card (biggest visual change).**
Replace the existing Run Session + Validation summary cards with a
single state-aware card.

- **Inline first, partial later.** Write the if/elif/else inline
  in `session_detail.html` for the first cut. Only refactor to
  `_partials/contextual_action.html` (and a `ContextualAction`
  view-shape dataclass in `app/web/views.py` alongside
  `build_setup_rows`) if the inline version exceeds ~50 lines or
  the conditional logic gets gnarly. Don't over-engineer the
  first pass.
- Per-state contents:

  | State | Primary button | Supporting links | Readiness summary |
  |---|---|---|---|
  | `draft` | **Validate Setup** (link to `?validated=1`) | View validation detail (Operations → Validate) | Five Setup entity badges |
  | `validated` | **Activate Session** (existing `/activate` form + acknowledge-warnings checkbox per current Validation summary card) | View validation detail · Preview reviewer surface · Revert to Draft | "Setup validated" + entity badges |
  | `ready` | **Pause Session** (POSTs to existing `/revert`) | Manage invitations · Monitor responses · Preview reviewer surface | Operations pointers (terse counts with links) |

- Pause confirmation copy: *"Pausing returns the session to Draft.
  Reviewers will not be able to access forms while paused. Existing
  responses are preserved."*
- Retire both top-of-body lock cards (existing-responses warning +
  revert form) — the action card carries that messaging now.
- **Verify** the existing `/revert` route accepts both `validated →
  draft` (currently `invalidate`) and `ready → draft` (currently
  `revert`); add the `validated` path or wire a separate endpoint
  if not.
- The "operations pointers" counts in the Activated readiness
  summary may need a new helper — invitations / monitoring counts
  are already computable; "reminders due" can be a placeholder
  string until Segment 9.3 polish lands.

**PR C — Extract Data card.** Promote from a CTA inside Run Session
to its own card.

- New left-column card, third position (after Quick Setup).
- Placeholder body since real extraction lands in Segment 12:
  - One-line description.
  - Disabled `.btn` Extract action with a tooltip noting "lands
    in Segment 12".
  - Optional `.form-help` line with a terse counts summary.
- State-conditional disabled: greyed in Draft / Validated. In
  Activated, the card visually enables but the button stays
  disabled (Segment 12 placeholder).
- Removes the "Extract Data" CTA from the now-deleted Run Session
  card (already gone after PR B).

**PR D — Right column polish + Quick Setup disabled state.**

- ~~Drop the duplicate `Status:` pill from the Session Details
  card.~~ **Already shipped** (PR #375 / commits 2a36607, 6c59215).
  This item is removed from D's scope.
- Quick Setup gets a disabled-greyed treatment when `is_ready`
  (no yellow lock card per spec). Likely a small `.card.disabled`
  helper class on the v2 block, or a `.disabled` modifier on
  `.card`. Add the rule to `base.html` v2 block alongside the
  other card variants.
- **Danger Zone Delete Session — behavior change, not just
  polish.** Current code *hides* the Delete Session form when
  `is_ready` (`session_detail.html:170-187`). Spec says the
  affordance stays visible but greyed-disabled with an
  explanation. Render the form's button as disabled with a
  short note ("Pause the session first to enable deletion.")
  rather than suppressing the form entirely. Flag this in the
  PR description as the one behavior change in D — the rest is
  pure styling.

If the Danger Zone change feels load-bearing in review, splitting
D into D1 (Quick Setup disabled, CSS-only) and D2 (Danger Zone
visible-disabled, behavior change) is fine. Default to keeping
them together since both are small.

**PR E — Stale `.pill-lifecycle-closed` cleanup.** CSS-only.

- Remove the `body.ui-v2 .pill-lifecycle-closed` rule from
  `base.html` v2 block.
- Grep for any `pill-lifecycle-closed` template usage; should be
  zero.

Land this **before PR B** as a warm-up. It's CSS-only, risk-free,
and gets one stale rule out of the way before B's bigger sweep.

**PR F — Doc impact.**

- Update `spec/operator_ui_concept.md`: retire the "Run Session
  four-button" pattern, reference the contextual primary action
  card, reflect the two-column Home body, and drop any stale
  "closed" lifecycle mentions. (Largely already done by the docs
  reorg PRs #360-#363; verify against the final layout once it
  ships.)
- Tick `session_detail.html` against the new spec in
  `guide/ui_checklist.md`.

Land **after** B/C/D have been seen on the Azure dev slot — doc
updates should reflect what actually shipped, not what was
planned. If post-deploy verification surfaces a small visual
deviation from the spec, capture it in F (or fold the spec
update into a follow-up) rather than rewriting docs that the
implementation already moved past.

## Implementation pointers

**Action-card component shape.** First cut: a Jinja partial with
big if/elif/else by state. Once the shape settles, refactor to a
`ContextualAction` view-shape dataclass in `app/web/views.py`
(alongside `build_setup_rows`) that the route fills, with a single
dumb partial rendering it. Don't over-engineer the first pass.

**Pause Session reuses existing transitions.** No new state-machine
code. The existing `POST /operator/sessions/{id}/revert` route
already implements `ready → draft`; just relabel the button and
update the confirmation copy. Verify whether the same route or a
separate `invalidate` endpoint handles `validated → draft` and
adjust the "Revert to Draft" link target accordingly.

**Lifecycle display mapping** stays a one-function helper. Expose
as a Jinja filter so templates do `{{ session.status |
lifecycle_label }}`. Don't add a model field or change the database.

**Operations pointers** in the Activated readiness summary
(invitations sent / responses received / reminders due) — first cut
can use placeholder strings or whatever the cheapest helper
returns. Tighten the wording once the page is on the dev slot and
we see what reads well.

**No new button variants** for this work. Reuse Primary / Secondary
/ Destructive / Outline-amber per `spec/visual_style_general.md` and
`spec/ui_elements.md`.

**Responsive collapse** is the existing single-column behaviour
below 800px — no extra work needed beyond what the current
`.bottom-grid` mobile rule provides.

## Out of scope (cross-references)

- **Quick Setup full implementation** — `spec/quick_setup_card_spec.md`,
  `unfinished_business.md` #30. Tracked separately; this segment
  ships the placeholder card on Home and wires its disabled state.
- **Real Extract Data** — Segment 12 (export / audit retention MVP).
- **Operator-editable email template editor** — Segment 11A
  remaining item, `unfinished_business.md` #24. Independent of Home.
- **Per-entity setup-page warnings** when responses exist — the
  existing-responses warning currently on Home is being retired here;
  per-entity surfaces should carry the warning instead. Track as a
  follow-up; not gating this segment.
- **Renaming the `ready` enum value to `activated`** at the
  database / API layer. The display divergence is handled at the
  display layer per spec.

## Test impact

PR B is the most testing-intensive: every test that asserts on
Home's body markup (e.g. `<h2>Run Session</h2>`,
`<h2>Validation summary</h2>`) needs updating. Search hits include
`tests/integration/test_session_detail_restructure.py` and
`tests/integration/test_validation_routes.py`. Plan to update or
delete those assertions in the same PR.

PR A may shift assertions that look for `READY` / `ready` literals
in body text. Sweep with a grep before submitting.
