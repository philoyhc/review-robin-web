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
   greyed out / disabled per lifecycle state. Provisional set:
   Generate · Activate · Send invitations · Pause/Resume · Close.
   Lock down during PR 3 scoping.

No tabs, no expanders, no nested status — the card delegates detail
to the page body the operator is currently looking at (the status
table on Assignments, the diagnostic list on Validate, the previews
on Previews, etc.).

### Next-action state table (provisional)

| Lifecycle state | Next-action line | Primary button (un-greyed) |
|---|---|---|
| `draft`, setup incomplete | "Next action: complete setup — go to Setup tabs" | none (workflow buttons all greyed) |
| `draft`, setup complete, never generated | "Next action: Generate assignments" | Generate |
| `draft`, generated, setup-gate errors | "Next action: fix setup errors — see Validate" | Generate (greyed) |
| `draft`, generated, operations-gate errors | "Next action: fix readiness errors — see Validate" | Generate (re-runs) |
| `draft`, generated, clean | "Next action: preview, then Activate session" | Activate |
| `draft`, generated, warnings | "Next action: review warnings, then Activate session ☐ I acknowledge warnings" | Activate |
| `validated` | "Next action: Activate session" | Activate |
| `ready`, invitations not sent | "Next action: Send invitations" | Send invitations |
| `ready`, invitations partially sent | "Next action: Send remaining invitations" | Send invitations |
| `ready`, invitations fully sent, responses open | "Next action: Monitor responses" | (none — Responses tab) |
| `ready`, deadline passed | "Next action: Close session ☐ I confirm closing" | Close |
| `paused` | "Next action: Resume session" | Resume |
| `closed` | "Next action: Extract data — go to Session Home" | (none — card may itself fade) |

Refine during PR 3 scoping.

## Validate page revamp (lands ahead of card work)

The page today (Segment 11G) registers a `ValidationRule` registry,
runs every rule against the session, and renders one issue list
with severity-chip filters + per-issue fix-here deep-links.
Post-15B the picture is per-instrument; the page needs new rules to
surface what's already in the model.

- **New validation rules** (registered in `validation.py`):
  - `instruments.no_rule_pinned` — error if any instrument has
    `rule_set_id IS NULL` while the session has reviewers /
    reviewees. Fix link: the Instruments page card.
  - `instruments.stale_generated` — warning if any pinned
    instrument's eligible count diverges from its generated
    count (operator hasn't regenerated since a roster / rule
    change). Fix link: Generate via workflow card.
  - `instruments.zero_included` — warning if any instrument has
    `generated_count > 0` but `included_count == 0` (every row
    deactivated). Fix link: the Assignments status table.
  - Re-frame the existing session-wide `assignments.no_pairs` →
    tighter "no included pairs across any instrument" (since the
    per-instrument visibility is in the new rules above).
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

## PR sequence (provisional)

1. **PR 1 — New per-instrument validation rules.** Register
   `instruments.no_rule_pinned`, `instruments.stale_generated`,
   `instruments.zero_included` in `validation.py`. Refine
   `assignments.no_pairs` to "no included pairs across any
   instrument." Tests + fix-link wiring. No UI surface change to
   Operations pages yet; rules slot into the existing Validate
   issue list.
2. **PR 2 — Validate page section grouping + diagnostic framing.**
   View adapter splits issues into Setup gate vs. Operations gate
   sections. Setup-coverage matrix retained. Page-body Primary
   action affordances (if any) audited — Validate stays
   action-free.
3. **PR 3 — Operations workflow card v1, Assignments only.**
   Build the card template + view adapter + endpoint. Render on
   Assignments as the beachhead. Wire Generate-wraps-validation
   logic. State-aware next-action line + button row + greying. New
   tests for state-table copy + state-table button-enabled matrix.
4. **PR 4 — Workflow card on remaining Operations pages.** Render
   on Validate, Previews, Invitations, Responses. Strip duplicate
   Primary action buttons from page bodies (Generate from
   Assignments body if not already moved in PR 3; Send-invitations
   from Invitations body; etc.).
5. **PR 5 — Retire Session Home Next Action card.** Once workflow
   card is on every Operations page, Session Home drops the action
   card. Refocus Session Home on Setup readiness card + Data
   extraction / retention (step 9). Cross-link to `docs/status.md`
   chronology + `spec/session_home.md`.

Slice sizes per PR are deliberately conservative — PRs 1–2 are
self-contained pre-work; PR 3 is the main beachhead; PRs 4–5 are
mechanical extensions / cleanups.

## Out of scope

- **State machine refactor.** Lifecycle is `draft / validated /
  ready / paused / closed`; workflow card composes existing
  transitions rather than introducing new ones.
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

## Working notes / open questions

- Exact button set in the row — does it include Pause and Close, or
  do those move into an overflow menu? Lock down in PR 3.
- Acknowledge-warnings affordance — checkbox in the next-action
  line vs. modal vs. separate banner. Per spec above, checkbox
  inline; revisit if it feels cramped.
- State table edge cases — warnings-acknowledged-but-not-yet-
  activated state; mid-batch invitation send (partial); paused +
  invitations-fully-sent. Audit during PR 3.
- Visual treatment — narrow strip-style card vs. fat card? Sticky
  on scroll? Probably non-sticky, compact one-line-of-buttons
  height.
- Setup-row pages: card does **not** render there. Confirmed in
  spec above.
- Session Home transition timing — wait for PR 4 to ship before
  starting PR 5 (don't strand operators on a half-replaced
  surface).
- Validate page section grouping (PR 2) — display-only split, or
  do we also split the underlying issues list in the view-context
  dataclass? Probably the latter (cleaner for tests).
- Single endpoint per workflow-card action vs. polymorphic
  endpoint with a `?action=generate/activate/send` form param?
  Lean single endpoints — easier audit-event story.
- Reuse from existing Next Action card: the state-aware copy logic
  and lifecycle predicates (`is_draft` / `is_validated` /
  `is_ready` etc.) lift directly; the card chrome / button row is
  new template work.
- "Operations workflow" title vs. "Workflow" vs. "Next steps" —
  lock down in PR 3 mockup.

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
