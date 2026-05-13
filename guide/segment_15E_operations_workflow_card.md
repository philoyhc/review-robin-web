# Segment 15E — Operations Workflow Card

**Status:** Planning — stub created 2026-05-10 (as
"15E next-action revamp"); broadened 2026-05-13 to absorb
the Validate-page revisions made necessary by 15B's per-instrument
assignments move; reframed 2026-05-13 as the **Operations Workflow
Card** segment after working through the page-by-page operator
workflow (steps 1–9 in `## Operator workflow` below).

> **Working notes scratchpad** at the bottom — capture decisions,
> scope tweaks, and open questions as they come up. Once the shape
> settles, lift the durable parts into a proper "Goal / Scope / PR
> sequence / Out of scope" structure.

## Goal

Land a single, persistent **Operations workflow** card that renders
identically at the top of every Operations-row chrome page
(Assignments / Validate / Previews / Invitations / Responses), just
below the chrome strip. The card carries the canonical next-action
copy and the row of lifecycle-transition buttons; each Operations
page body focuses purely on its own detail content (status table,
diagnostic list, previews, etc.).

Side benefits that fall out naturally:

1. **Validate page collapses to a pure diagnostic detail surface.**
   No Primary actions on the Validate body itself — the workflow
   card carries Generate / Activate / etc. on every page including
   Validate. New per-instrument validation rules
   (`instruments.no_rule_pinned`, `instruments.stale_generated`,
   `instruments.zero_included`) land here too, registered alongside
   the existing rules; the per-instrument readiness signals 15B
   shipped finally get enforced.

2. **Generate (on the workflow card, click from any Operations
   page) wraps validation.** A Generate click runs setup-gate
   validation → if errors, hard-stop with banner pointing at
   Validate; → else replace assignments → run operations-gate
   validation → render outcome banner (clean / warning / error). The
   operator never has to proactively visit Validate to learn whether
   they can move forward — Validate becomes the detail page the
   banner links into.

3. **Activate fits cleanly.** Lives on the workflow card on every
   Operations page; greyed out until lifecycle state allows it.
   No need to wedge an Activate button into Previews (and rename
   the tab) just because Previews happens to be where the operator
   ends up before activating.

4. **Eventual retirement of the Session Home Next Action card.**
   Once the workflow card is on every Operations page, the Next
   Action card on Session Home is redundant — every action it
   surfaces is one click away from any Operations tab. Session Home
   then refocuses on Setup readiness + data extraction / retention
   concerns. The transition is the final PR in the segment, after
   the card is fully proven across the Operations row.

End-to-end test: an operator should be able to walk Operations
chrome tabs left-to-right (Assignments → Validate → Previews →
Invitations → Responses) **or** stay on any single tab and complete
the entire post-setup workflow without bouncing to Session Home.

## Operator workflow

The nine steps this segment streamlines:

1. Setup rosters, instruments, email template — **Setup-row tabs**
2. Generate assignments — **Assignments** via workflow card Generate
3. Browse validation info, fix issues — **Validate** (diagnostic)
4. Preview emails + reviewer surface — **Previews**
5. Activate session — workflow card Activate (from any Operations
   tab)
6. Send invitation emails — **Invitations** via workflow card Send
7. Monitor responses, send reminders — **Responses**
8. Close session (manual or deadline-driven) — workflow card Close
9. Extract data + delete-in-app — **Session Home** Extracts /
   retention surface (out of 15E scope; lives on home where the
   workflow card retires to)

Setup-row tabs (step 1) are non-linear and lateral; the workflow
card does **not** render there. The card is the marker of "you're
in the linear operations phase."

## Card spec

Exactly three components, in order:

1. **Title.** "Operations workflow"
2. **Next-action line.** One line beginning "Next action: …",
   state-aware (reuses the per-state copy logic from the current
   Session Home Next Action card). If the next action is
   destructive (Pause / Close / Revert-to-draft), the line carries
   an inline checkbox continuation, e.g.
   "Next action: Close session ☐ I confirm closing."
3. **Button row.** Same set of buttons on every Operations page;
   greyed out / disabled per lifecycle state. Locked set:
   **Generate · Activate · Send invitations · Send reminders ·
   Pause**. "Pause" is the friendly label for the existing
   revert-to-draft transition (`POST /operator/sessions/{id}/revert`,
   `session_lifecycle.revert_session_to_draft`) — keeps operator
   muscle memory from today's Session Home Pause button. **Close**
   is intentionally omitted: there is no `close_session()` lifecycle
   transition today (close happens by deadline expiry) and adding
   one is out of scope for 15E. A future segment introduces real
   Pause / Close states if needed.

No tabs, no expanders, no nested status — the card delegates detail
to the page body the operator is currently looking at (the status
table on Assignments, the diagnostic list on Validate, the previews
on Previews, etc.).

### Next-action state table

| Lifecycle state | Next-action line | Primary button (un-greyed) |
|---|---|---|
| `draft`, setup incomplete | "Next action: complete setup — go to Setup tabs" | none (workflow buttons all greyed) |
| `draft`, setup complete, never generated | "Next action: Generate assignments" | Generate |
| `draft`, generated, setup-gate errors | "Next action: fix setup errors — see Validate" | Generate (greyed; banner links to Validate) |
| `draft`, generated, operations-gate errors | "Next action: fix readiness errors — see Validate" | Generate (re-runs) |
| `draft`, generated, clean | "Next action: preview, then Activate session" | Activate |
| `draft`, generated, warnings | "Next action: review warnings, then Activate session ☐ I acknowledge warnings" | Activate |
| `validated` | "Next action: Activate session" | Activate |
| `ready`, invitations not sent | "Next action: Send invitations" | Send invitations |
| `ready`, invitations partially sent | "Next action: Send remaining invitations" | Send invitations |
| `ready`, all sent, responses incomplete | "Next action: Monitor responses; Send reminders if needed" | Send reminders (Secondary) |
| `ready`, deadline passed | "Next action: Extract data — go to Session Home" | (none — close-by-expiry, no Close button in 15E) |
| `draft` after Pause | "Next action: complete setup or re-generate" | Generate (resumes the natural draft flow) |

Refine edge cases during PR 3 scoping.

## Validate page revamp (lands ahead of card work)

The page today (Segment 11G) registers a `ValidationRule` registry,
runs every rule against the session, and renders one issue list
with severity-chip filters + per-issue fix-here deep-links.
Post-15B the picture is per-instrument; the page needs new rules to
surface what's already in the model.

- **New validation rules** (registered in
  `app/services/validation.py` `REGISTERED_RULES`, lines 466–647):
  - `instruments.no_rule_pinned` — **error** if any instrument has
    `rule_set_id IS NULL` while the session has reviewers /
    reviewees. Fix link:
    `/operator/sessions/{id}/instruments`.
  - `instruments.stale_generated` — **warning** if any pinned
    instrument has `is_stale=True` (i.e. eligible_count !=
    generated_count — operator hasn't regenerated since a roster /
    rule change). Fix link:
    `/operator/sessions/{id}/assignments` (where the operator
    re-Generates via the workflow card).
  - `instruments.zero_included` — **warning** if any instrument has
    `generated_count > 0` but `included_count == 0` (every row
    deactivated). Fix link:
    `/operator/sessions/{id}/assignments` status table.
  - **Replace** the existing session-wide `assignments.no_mode`
    (validation.py lines 200–211 + registry entry 560–572) with
    `assignments.no_included_pairs` — **warning** when
    `sum(included_count_per_instrument(...)) == 0` (zero included
    rows across every instrument). Catches the "all-deactivated"
    case that the new per-instrument `zero_included` rule wouldn't
    flag at session-wide severity. Fix link:
    `/operator/sessions/{id}/assignments`.
- **Section grouping on Validate.** View adapter splits issues into
  two read-only sections — Setup gate (structural rules) vs.
  Operations gate (per-instrument readiness rules + session-wide
  pair-count rules). Same flat-list renderer underneath; the split
  is presentation-only. The setup-coverage matrix at the top of the
  page stays.
- **No Primary actions on the page itself.** Fix-here deep-links
  stay as today (each issue points at the page to fix on); workflow
  card carries all lifecycle actions, including Generate (which is
  the in-place auto-fix for stale_generated).
- **Severity chip strip stays.** Filter / count pattern unchanged.

## Generate wraps validation (workflow card Generate)

Generate button click flow (single endpoint, same logic regardless
of which Operations page the click originates on):

1. Run **setup-gate** validation. If any errors, hard-stop with
   banner "Can't generate — N setup issues. See Validate ↗" and
   return. No assignment rows written.
2. Else: run `replace_assignments(...)` (existing service entry
   point).
3. Run **operations-gate** validation. Render outcome banner:
   - Clean → green "Generated N rows. Next: preview & activate."
   - Warnings → yellow "Generated N rows with W warnings. See
     Validate ↗"
   - Errors-but-rows-wrote → red "Generated with E errors. See
     Validate ↗"
4. Operator stays on whichever Operations page they clicked from;
   the page body re-renders with fresh data.

Activate button click flow:

1. Run operations-gate validation only. Errors block; warnings
   require the inline `☐ I acknowledge warnings` checkbox in the
   next-action line.
2. Call existing `lifecycle.activate_session(...)`.

No new schema, no new audit events — each underlying step emits
its own existing event.

## PR sequence

Slice sizes are deliberately conservative — PRs 1–2 are
self-contained pre-work; PR 3 is the main beachhead; PRs 4–5 are
mechanical extensions / cleanups.

### PR 1 — Per-instrument validation rules + lift `is_stale` to service

**Scope.** Land the four new / changed validation rules with no UI
surface changes; surface them in the existing Validate issue list.
Smallest first slice; proves the rules work end-to-end before any
workflow-card scaffolding.

**Service changes** — `app/services/assignments.py`:
- Lift the inline `is_stale` computation out of
  `app/web/views/_assignments.py:167-170` into a pure helper
  `compute_staleness(rule_id, eligible_count, generated_count) ->
  bool` so the validation rule and the view share one source of
  truth. View adapter updated to call the helper.

**Validation changes** — `app/services/validation.py`:
- Add four `check_*` functions before line 466 (the
  `REGISTERED_RULES` definition):
  - `_check_instruments_no_rule_pinned` — iterates session
    instruments, yields an error per instrument with
    `rule_set_id IS NULL` (only if session has at least one
    reviewer + one reviewee).
  - `_check_instruments_stale_generated` — iterates pinned
    instruments, calls
    `evaluate_session_rule_eligibility(...)` once + maps
    rule_set_id → eligible_count, joins with
    `existing_count_per_instrument(...)`, yields a warning per
    stale instrument via the new `compute_staleness()` helper.
  - `_check_instruments_zero_included` — yields a warning per
    instrument where `existing_count > 0` and
    `included_count == 0`. Reuses
    `included_count_per_instrument(...)`.
  - `_check_assignments_no_included_pairs` — yields a warning
    when `sum(included_count_per_instrument(...).values()) == 0`.
    Replaces `_check_assignments_no_mode` (lines 200–211).
- Register the rules in `REGISTERED_RULES` (lines 466–647). Remove
  the existing `assignments.no_mode` entry (lines 560–572).
- Each rule uses `fix_url` callables matching today's pattern
  (existing examples: `_session_edit_url`, the
  `/operator/sessions/{id}/instruments` helpers).

**Tests** — `tests/integration/`:
- New `test_validation_per_instrument_rules.py`:
  - One positive + one negative test per new rule.
  - Test that pinning a rule on an instrument clears
    `no_rule_pinned`.
  - Test that regenerating an instrument clears `stale_generated`.
  - Test that toggling include=True on at least one row clears
    `zero_included`.
- Update any tests asserting on `assignments.no_mode` to expect
  `assignments.no_included_pairs` instead. Grep:
  `grep -rln "assignments.no_mode" tests/`.

**Out of scope.** No template / view changes beyond the
`is_stale` lift. No new fix-link copy work — fix-here links use
the existing Validate-page deep-link rendering.

---

### PR 2 — Validate page Setup-gate / Operations-gate section split

**Scope.** Display-only split of the Validate page issue list into
two gate-labelled sections. The setup-coverage matrix at the top
stays. No Primary actions on the page.

**View-adapter changes** — `app/web/views/_validate.py`:
- Add a `Gate = Literal["setup", "operations"]` type and a
  module-level `_RULE_KEY_GATE: dict[str, Gate]` mapping (or
  derive from `rule.source`: session / reviewers / reviewees /
  instruments / email_template → "setup"; assignments + the new
  per-instrument rules → "operations"). The simpler derivation
  is preferable.
- Extend `IssueSourceGroup` (lines 64–71) with `gate: Gate` field.
- Update `build_validate_context()` (lines 275–375):
  - After existing source-grouping (lines 350–360), tag each
    group with its gate.
  - Sort groups so all setup-gate groups precede all
    operations-gate groups within `issue_groups`.
- Add `gate_summary` dict on `ValidateContext` if templates need
  per-gate count strings (e.g. "Setup gate: 2 errors, 1 warning"
  vs. "Operations gate: 1 warning").

**Template changes** —
`app/web/templates/operator/partials/validation_results.html`
(lines 22–49):
- Insert gate `<h2>` heading before each gate's first group
  (use a `loop.first` / `loop.changed(group.gate)` Jinja pattern).
- Severity-chip filter strip (currently on `session_validate.html`
  lines 90–101) stays unchanged.

**Tests:**
- Pin the gate-mapping for every existing rule key in a
  test (`test_validate_view_gate_split.py`).
- Snapshot test that the rendered Validate page contains both
  "Setup gate" and "Operations gate" headings under the right
  conditions.

**Out of scope.** Any action-button changes on the Validate page
itself (Validate stays action-free; lifecycle actions wait for the
workflow card in PR 3).

---

### PR 3 — Operations Workflow Card v1, Assignments page

The beachhead. Largest PR in the segment.

**Scope.** Build the workflow card (template + view adapter +
service helpers as needed) and render it on the Assignments page
only. Wire Generate-wraps-validation. State-aware copy + button
matrix. Activate / Pause flows work end-to-end from the card.

**View-adapter — new file** `app/web/views/_workflow_card.py`:
- `WorkflowButton` dataclass: `label` (str), `endpoint` (str),
  `method` ("post"), `enabled` (bool), `is_primary` (bool),
  `confirm_checkbox_name` (str | None — e.g.
  `acknowledge_warnings` or `confirm_pause`).
- `WorkflowCardContext` dataclass:
  `title="Operations workflow"`, `next_action_line` (str),
  `acknowledge_inline` (bool, with `checkbox_label` + form-field
  name when True), `buttons: list[WorkflowButton]`.
- `build_workflow_card_context(db, review_session,
  readiness_report) -> WorkflowCardContext` — consumes lifecycle
  predicates (`is_draft` / `is_validated` / `is_ready` from
  `session_lifecycle.py:43-57`) + readiness signals
  (`ReadinessReport` from
  `lifecycle.build_readiness_report(...)`) + per-state copy
  derived from the next-action state table above.
- Re-use the per-state copy logic from current Next Action card
  (Session Home `session_detail.html:27-170` is the source).
  Wholesale lift not necessary; copy the strings and predicates
  but build them via the new context dataclass.

**Template — new partial**
`app/web/templates/operator/partials/operations_workflow_card.html`:
- Renders the three-component card: title `<h2>`, next-action
  `<p>` (with inline `<input type="checkbox">` continuation when
  `acknowledge_inline=True`), and a `<div class="card-action-row">`
  iterating `card.buttons`.
- Each button is either a `<form method="post">` (for actions)
  or an `<a class="btn">` (for navigation-only buttons, e.g.
  "see Validate" surfaced in error banners). Greyed buttons
  render `disabled` attribute.
- Use canonical `.btn` modifier classes per
  `spec/domain_assumptions.md`. Pause / Revert renders
  `btn-alert-outline`.

**Wiring on Assignments** —
`app/web/templates/operator/session_assignments.html`:
- Include the partial near the top, after the chrome strip
  but before the per-instrument status card. Pass
  `workflow_card=...` as a template variable.
- The page body's existing per-instrument status table + preview
  stays unchanged; this PR doesn't strip any Assignments-page
  primaries (no in-body Generate button to strip; Generate today
  is on Session Home's Next Action card).

**Route changes** —
`app/web/routes_operator/_assignments.py:192-234` (Generate route):
- Before `replace_assignments(...)`:
  1. Call `validation.validate_session_setup(...)`, filter to
     setup-gate sources via the same mapping from PR 2.
  2. If errors, return early with redirect to Assignments + flash
     banner naming setup blockers + linking to Validate.
- Call `replace_assignments(...)` as today.
- After:
  3. Re-run validation, filter to operations-gate sources, render
     outcome banner via flash (`?generated=clean|warnings|errors`).
- All other behaviour preserved (audit events, lifecycle
  invalidation).

**Activate from card** — POSTs to existing
`/operator/sessions/{id}/activate` route. No route changes; the
existing `acknowledge_warnings` form-field name maps directly to
the card's inline checkbox.

**Pause from card** — POSTs to existing
`/operator/sessions/{id}/revert`. Form field
`confirm_revert=on` already exists per `session_detail.html:120`.

**Tests** — `tests/integration/`:
- `test_workflow_card_state_table.py` — for each of ~10 lifecycle
  states in the state table, set up the session, fetch
  `/operator/sessions/{id}/assignments`, assert the rendered
  next-action copy + which buttons render `disabled`.
- `test_assignments_generate_wraps_validation.py`:
  - Setup-gate error blocks Generate (no rows written, banner
    points to Validate).
  - Operations-gate warnings produce yellow banner; rows still
    written.
  - Clean generation produces green banner.
- New audit-event assertions are unnecessary — Generate emits the
  same `assignments.generated` events as before; only the
  pre-/post-validation calls are new.

**Out of scope.** Card on other Operations pages (PR 4); Send
buttons (PR 4); Session Home Next Action card retirement (PR 5).

---

### PR 4 — Workflow card on remaining Operations pages

**Scope.** Render the same workflow card on Validate, Previews,
Invitations, Responses. Retire the Validate page `?activate=1`
detour. Move Send invitations + Send reminders into the workflow
card. Keep detail-level actions on page bodies.

**Template includes** — add the workflow card partial to:
- `app/web/templates/operator/session_validate.html` (just below
  chrome, above the setup-coverage matrix).
- `app/web/templates/operator/session_previews.html` (just below
  chrome, above the preview picker).
- `app/web/templates/operator/session_invitations.html` (just
  below chrome).
- `app/web/templates/operator/session_responses.html` (just below
  chrome).
- Each route handler builds `workflow_card_context` and passes it
  to its template.

**Validate page Activate detour retirement** —
`session_validate.html:14-58`:
- Drop the `activate_banner` block (route stops handling
  `?activate=1` and stops setting `activate_banner`).
- Acknowledge-warnings UX now lives entirely on the workflow
  card's inline checkbox continuation.
- `routes_operator/_operations.py:43-108` (Validate route):
  remove `activate=1` branch; redirect `?activate=1` requests to
  the canonical Validate URL for graceful URL backward-compat.

**Send button wraps Generate+Send** —
`app/services/invitations.py` (or equivalent):
- The workflow card's Send button posts to a single endpoint
  (e.g. `POST /operator/sessions/{id}/invitations/dispatch`) that
  calls `generate_invitations()` then `send_all_pending()` in one
  request. If generation fails, no send.
- Existing Invitations-page detail buttons stay:
  Generate invitations, Regenerate all, Send all pending,
  Send reminders (the last two become duplicates of the workflow
  card buttons; remove from the Invitations page body —
  `session_invitations.html:47-80`).

**Send reminders dedup** —
- Move from `session_invitations.html:72-79` and
  `session_responses.html:40-47` into the workflow card.
- Both page bodies retire their Send reminders button.

**Tests:**
- Each Operations template renders the workflow card.
- `?activate=1` URL redirects to canonical Validate (no
  `activate_banner` content rendered).
- `POST /invitations/dispatch` calls generate then send; if
  generate fails, send is not called.
- Invitations + Responses page bodies no longer contain the
  Send-reminders button.

**Out of scope.** Visual polish on narrow viewports (mobile
deferred); Session Home changes (PR 5).

---

### PR 5 — Retire Session Home Next Action card

**Scope.** With the workflow card live on every Operations page,
Session Home no longer needs the Next Action card. Drop it; leave
the rest of Session Home unchanged.

**Template changes** —
`app/web/templates/operator/session_detail.html`:
- Drop lines 27–170 (Next Action card).
- Keep: Extract Data card (line 177), Danger Zone card (lines
  179–227), Session Details card (line 237+), Quick Setup column.

**View-adapter cleanup** — `app/web/views/_session_home.py` (or
the file the Next Action context-builder lives in): remove the
per-state copy + button-list helpers that are now unused. (The
copy logic was already lifted into `_workflow_card.py` in PR 3,
so this is just dead-code removal.)

**Spec / docs updates:**
- `spec/session_home.md` — strip the Next Action card section;
  add note pointing operators to the Operations workflow card for
  lifecycle actions.
- `docs/status.md` — chronology row for 15E completion.
- `guide/todo_master.md` — move 15E from Upcoming → Done.

**Tests:**
- Assert Session Home no longer renders an `<h2>` containing
  "Next Action".
- Assert Extract Data + Danger Zone + Session Details + Quick
  Setup still render (regression check).
- Assert operators landing on Session Home in any lifecycle state
  do not see a 500 (covers all states the retired card
  handled).

**Out of scope.** Adding a new Setup readiness card to Session
Home — Setup readiness continues to live on Validate page +
the setup-status row in the chrome. A polish PR can add a
Home-side surface if pilot feedback wants it.

## Out of scope

- **State machine refactor.** Today's lifecycle is
  `draft / validated / ready` (paused is not a separate state —
  Pause = revert-to-draft; close happens via deadline expiry).
  Workflow card composes existing transitions rather than
  introducing new ones. Real Pause / Close states wait for a
  future segment.
- **Email-notification chain.** Send-invitations remains its own
  step; no fold-in of email composition into Activate.
- **Multi-session bulk operations.** Lobby-page bulk actions are a
  different shape and not in scope.
- **Data extraction / retention surface on Session Home.** Step 9
  becomes Session Home's responsibility after PR 5, but the actual
  redesign of the extraction surface is its own segment.
- **Setup-row workflow indicator.** Setup is non-linear; no
  workflow card there.
- **Mobile-specific layout work.** Card sized for desktop /
  tablet-landscape; narrow viewports defer to a later pass.
- **Re-Generate on idempotent paths.** Generate re-runs even when
  the assignments table is already populated and matches.
  Acceptable: Generate is fast and idempotent.
- **New Setup readiness card on Session Home.** PR 5 only retires
  the Next Action card; Setup readiness continues to live on
  Validate page + the chrome status row. A polish PR can add a
  Home-side surface if pilot feedback wants it.

## Decisions locked

Captured in the 2026-05-13 scoping conversation (PR #945 follow-up):

- **Button row:** Generate · Activate · Send invitations · Send
  reminders · Pause. "Pause" maps to existing revert-to-draft;
  Close is omitted (no `close_session()` lifecycle today).
- **Send wraps Generate-invitations + Send-all-pending.** Symmetric
  with Generate wrapping setup-gate + replace_assignments +
  operations-gate validation.
- **`assignments.no_mode` retired, replaced by
  `assignments.no_included_pairs`** (warning when
  `sum(included_count_per_instrument) == 0`).
- **Page-body detail actions stay** (e.g. Invitations page keeps
  Generate-invitations + Regenerate-all). Workflow card carries
  only the canonical lifecycle action.
- **`is_stale` lifted** from `_assignments.py:167-170` into a
  `compute_staleness()` service helper in PR 1 so the validation
  rule and the view share one source of truth.
- **Revert-to-draft (= Pause)** lives on the workflow card as a
  Secondary, not in Danger Zone.
- **Setup readiness card on Session Home is out of scope** for
  PR 5. Setup readiness continues to live on Validate page + the
  chrome status row.
- **Send reminders** lives on the workflow card; the duplicate
  Send-reminders buttons on Invitations + Responses page bodies
  retire in PR 4.
- **Validate page section split** is presentation-only — extend
  `IssueSourceGroup` with a `gate` field and let the template
  insert headings; no schema or service-layer churn.
- **Single endpoint per workflow-card action.** Polymorphic
  routing (`?action=...`) rejected for cleaner audit-event story.

## Working notes / open questions

- Acknowledge-warnings affordance — inline checkbox in the
  next-action line. Revisit if it feels cramped during PR 3
  layout.
- State table edge cases — warnings-acknowledged-but-not-yet-
  activated; mid-batch invitation send (partial); paused +
  invitations-fully-sent. Audit during PR 3.
- Visual treatment — narrow strip-style card vs. fat card? Sticky
  on scroll? Lean non-sticky, compact one-line-of-buttons.
- Session Home transition timing — wait for PR 4 to ship before
  starting PR 5 (don't strand operators on a half-replaced
  surface).
- "Operations workflow" card title vs. alternatives — lock down
  in PR 3 mockup.
- Send-wrap endpoint name: `POST .../invitations/dispatch` vs.
  `.../invitations/generate-and-send` — preference for the
  shorter form, but decide during PR 4.
- Whether to keep the `?activate=1` URL redirecting (graceful
  backward-compat) or 404 it. Probably redirect; cheap.

## Related context

- **Segment 15B — per-instrument assignments**
  (`guide/archive/segment_15B_per_instrument_assignments.md`). The
  per-instrument readiness signals 15E enforces via new rules
  (`Instrument.rule_set_id`, `InstrumentStatusBlock.is_stale`,
  per-instrument include / self-review state) all shipped here.
- **Segment 15D — Assignments revamp**
  (`guide/archive/segment_15D_assignments_revamp.md`). Original
  "super buttons" framing in PR 8; carved out into 15E and
  reframed here as the Operations workflow card.
- **Segment 11G — Validate page rebuild**
  (`guide/archive/segment_11G_validate_page.md`). Shipped the
  `ValidationRule` registry + per-issue fix-here deep-links 15E
  extends.
- **Validation service**
  (`app/services/validation.py`). `REGISTERED_RULES` is the slot
  for the new per-instrument rules (PR 1).
- **Session Home spec** (`spec/session_home.md`) — current Next
  Action card behaviour. 15E retires the card from Session Home in
  PR 5 and refocuses the page on Setup readiness + data
  extraction.
- **Next Action card template + view logic**
  (`app/web/templates/operator/session_detail.html`,
  `app/web/views/_session_home.py` or equivalent). Source of the
  state-aware next-action copy 15E lifts into the workflow card.
- **Lifecycle service**
  (`app/services/session_lifecycle.py`). The transitions workflow
  buttons compose (`is_draft` / `is_validated` / `is_ready` /
  `activate_session` / `mark_validated` / `invalidate_session`)
  live here; 15E doesn't touch the state machine, just chains and
  surfaces existing primitives.
- **Operations chrome strip**
  (`app/web/templates/operator/partials/session_top_nav.html`).
  Workflow card renders below this on Operations-row pages.
- **Assignments page**
  (`app/web/templates/operator/session_assignments.html`,
  `app/web/views/_assignments.py`). PR 3 beachhead; the per-
  instrument status table stays on the page body, the Primary
  Generate moves into the workflow card.
- **Previews tab** stays "Previews" (no rename) — Activate
  reaches it through the universal workflow card, not through a
  Previews-only button.
