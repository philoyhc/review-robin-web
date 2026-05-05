# Segment 11F — Previews page (pre-flight reviewer experience hub)

Stub. Implementation plan for the Operations-row **Previews** tab
(`/operator/sessions/{id}/previews`), today a placeholder at
`app/web/routes_operator.py:1273` and `session_previews.html`.
Builds out the read-only pre-flight hub the operator uses to
eyeball what each reviewer will see before activating the
session.

The functional spec is **`spec/preview_hub.md`**. This guide
narrows the spec's four-artifact scope to the two pre-flight
blockers — **invitation email** and **reviewer surface** — and
proposes a concrete reviewer-picker UI. The two deferred
artifacts (reminder email, responses-received email) are not
pre-flight concerns and ride along with later segments.

Catalog item: `guide/todo_master.md` "Upcoming" item 2
(Segment 11F).

## Status

Planning. Sized as **5 PRs** in dependency order, each
independently shippable:

1. **PR A — Page chrome + reviewer picker.** No artifact cards
   yet; the body renders the picker and an empty-state stub
   below it.
2. **PR B — Invitation email card.** Renders through
   `email_templates.render_invitation` verbatim.
3. **PR C — Reviewer surface card.** Folds in the existing
   `/preview` (singular) form-only preview as a hub card and
   retires the standalone route.
4. **PR D — Reminder email card.** Renders through
   `email_templates.render_reminder` verbatim. Smaller than
   PR B because it reuses every primitive PR B introduced
   (registry, render adapter shape, missing-data path).
5. **PR E — Responses-received email card.** Coordinates with
   Segment 11E PR 6, which adds `render_responses_received`
   and proposes landing the registry append itself; whichever
   ships first carries the work, the other plan strikes
   through its corresponding scope item. See "PR E" below.

Send-test affordances per artifact (spec §"Send-test") are
**deferred** to either a small 11F follow-on or to Segment 11C
PR F (which already wires `EmailTransport` into per-row + bulk
send on Manage Invitations). Folding them into 11C is the
cleaner option — same transport seam, one set of tests — and
keeps 11F itself small.

## Why this scope

The spec defines four reviewer-facing artifacts (invitation,
response form, reminder, responses-received). All four ship in
11F now that 11E's follow-on planning (`render_responses_received`,
PR 6) gives the fourth artifact a render path. The original
2-card sizing carved off the two pre-flight blockers —
**invitation** and **reviewer surface** — so PR B / PR C could
land before reminder / responses-received UX questions settled.
Those questions have settled enough to ship, so the deferred
two slot into PR D / PR E on top of the same hub structure.

## Scope

In:

- Replace the `session_previews.html` placeholder body with the
  real hub: reviewer picker top, then a list of artifact cards.
- **Reviewer picker** as proposed below ("Reviewer picker UI").
  URL state via `?reviewer_email={email}` so the selected
  reviewer is bookmarkable / shareable; default = first
  reviewer in the session's reviewer list (alphabetical, the
  same order the Reviewers Setup page uses).
- **Invitation email card.** Renders subject + from / to / body
  via `email_templates.render_invitation(session, reviewer)`
  — the same call the live invitation flow uses (Segment 11E).
  No bespoke "preview mode" rendering.
- **Reviewer surface card.** Renders the reviewer's form via
  the existing `routes_reviewer.build_preview_context`. Folds in
  the standalone `/preview` (singular) route by retiring it and
  embedding its template output as a card body inside the hub.
- **Reminder email card.** Renders through
  `email_templates.render_reminder(session, reviewer)` — same
  call shape as the invitation card; same canonical-five
  merge-tag set. Card description: "Sent against an active
  session past the configured reminder threshold."
- **Responses-received email card.** Renders through
  `email_templates.render_responses_received(session, reviewer)`,
  the helper Segment 11E PR 6 introduces. Four-tag merge-set
  per 11E (drops `$invite_url`, optional `$submitted_at`).
  Card description: "Sent the moment the reviewer submits
  their review." See PR E below for the cross-segment seam
  with 11E.
- **Source-of-truth footer** on each card per spec ("Rendered
  from Email Template (Setup) and Reviewers (Setup).") — names
  what to edit if the operator dislikes what they see, with
  links to those Setup pages.
- **Per-card missing-data handling** per spec §"Missing-data
  handling": email-template-not-set / reviewer-has-no-assignments
  / instruments-not-configured each render a scoped error inside
  the card with a link to the relevant Setup page. Errors are
  scoped per card; one missing dependency does not block the
  other card.
- **Lifecycle behaviour** per spec §"Lifecycle behavior":
  renders in all states (`draft` / `validated` / `ready` /
  `closed`). Send-test (when it lands) is the only thing that
  gates lifecycle; the previews themselves are read-only and
  always inspectable.
- **Artifact registry seam.** The page iterates over a small
  registry tuple list at `app/web/views.py` (something like
  `PREVIEW_ARTIFACTS: list[ArtifactSpec]`); each card is one
  registry entry. The registry order pins the rendered order
  on the page (per spec §"Page layout": invitation → form →
  reminder → responses-received, matching the chronological
  arc of the reviewer experience). Per spec §"Forward-looking"
  — the registry's `audience` field is also where the future
  Reviewee Experience Preview filters.

Out:

- **Send-test affordances.** Per "Status" above, fold into
  Segment 11C PR F (which already builds the transport seam
  for per-row + bulk + test sends on Manage Invitations) so
  there's one place that wires `EmailTransport` rather than
  two.
- **Editing artifacts.** Per spec §"Out of scope" — strictly
  read-only; edits stay on the Setup pages.
- **A/B comparison across multiple reviewers, exportable
  previews, history of past sends.** Per spec §"Out of scope".
- **Reviewee Experience Preview hub.** Per spec
  §"Forward-looking" — the registry seam keeps the door open
  but the parallel hub itself is a future segment.
- **URL slug change to `/preview` (singular).** The spec
  proposes `/preview`; the existing chrome tab + placeholder
  route is `/previews` (plural). Keeping the plural matches the
  shipped chrome and saves a redirect; flag the spec
  inconsistency for a one-line fix in the spec, not a slug
  migration here.

## Reviewer picker UI

The picker is the spine of the page. It controls every artifact
card's render. Three concrete forms make sense; the proposed
shape combines all three.

### Proposed shape — native select + step buttons + count

```
┌────────────────────────────────────────────────────────────────┐
│ Previewing as:                                                 │
│ ┌──────────────────────────────────────────────────────┐  ← →  │
│ │ Alice Smith (alice@x.edu) — 5 reviewees assigned   ▾ │       │
│ └──────────────────────────────────────────────────────┘ Random│
│                                                                │
│ Reviewer 3 of 47 · 5 reviewees: Bob Jones, Carol Lee, …  more  │
└────────────────────────────────────────────────────────────────┘
```

The picker contains:

1. **Primary control: a native `<select>`** listing every
   reviewer as
   `"{name} ({email}) — {n} reviewees assigned"`. Native
   `<select>` over a custom combobox because:
   - Zero JS for the core flow; the form auto-submits via one
     inline `onchange` line.
   - The browser's native search-by-typing covers the
     "find a specific reviewer fast" case without a JS combobox.
   - Accessibility free (screen readers know what a `<select>`
     is).
   For sessions with thousands of reviewers a native select
   stays usable; if it ever proves too unwieldy, a future
   progressive enhancement swaps in a `<datalist>` filter
   without changing the URL or render path.
2. **Step buttons: "← Previous" / "Next →"** flanking the
   select. The natural verb for pre-flight inspection is
   "spot-check every reviewer's surface looks right" — paging
   through the list is the operator's actual mental model, and
   step buttons make it a one-click action per reviewer rather
   than a re-open-the-dropdown round-trip. Wraps at the ends
   (Next on the last reviewer wraps to the first) with a quiet
   visual cue (the count flash) so the operator notices.
3. **Random button.** Picks a reviewer at random from the list.
   Useful for sampling on a 500-reviewer session — the operator
   won't page through all 500, but spot-checking 5 random ones
   catches most setup drift. One click.
4. **Count indicator: "Reviewer N of M".** Below the controls,
   right-aligned. Tells the operator the scale of the session
   at a glance, and disambiguates step-button wrap-around.

### Below the picker — passive context strip

Per spec §"Reviewer picker (top of page)": a short strip
naming the current selection's key attributes — name, email,
reviewee count, and the first ~3 reviewee names with a "more"
disclosure for the rest. This is the "previewing for" header
that grounds what the operator is about to see in each artifact
card below.

The disclosure is a `<details>` element (native, no JS). When
the operator opens it, the full reviewee list renders. Default
collapsed.

### URL state

`?reviewer_email=alice@x.edu` is the canonical query parameter.
Why email and not `id`:
- Reviewer email is a stable identifier the operator can read
  and reason about.
- Bookmarks survive a full-cohort re-upload (which assigns new
  PK ids to the same email).
- The send-test affordance, when it lands, takes a `to=` email
  too — keeping the picker's identifier in the same vocabulary
  is one fewer mental shift.

If the param is missing or matches no reviewer, default to the
first reviewer alphabetically. If the session has no reviewers,
the picker renders **disabled** with the empty-state copy from
spec §"Empty state" and the cards below show their respective
empty states.

### Non-mechanics

- **Default ordering** matches the Reviewers Setup page.
  Whatever sort `app/web/routes_operator.py` reviewers index
  uses, the picker reuses — no second mental model.
- **Step buttons preserve ordering**, so "Next" advances by
  one in the picker's list order, not by reviewer-id order.
- **No JS framework.** The auto-submit-on-change is one line
  of inline JS in the template, matching the rest of the app
  (per `CLAUDE.md` — targeted progressive enhancement, no
  build step). Step / Random submit a tiny `<form>` with the
  precomputed target `reviewer_email` in a hidden input.

### Why not these alternatives

- **Searchable combobox (custom JS).** Heavier, accessibility
  to redo, no real benefit over native `<select>` until the
  list is in the tens of thousands.
- **Reviewer table with radio-select.** Renders the full list
  inline, but at 500 reviewers the table dwarfs the artifact
  cards below, defeating the page's purpose. Step buttons get
  the "page through reviewers" verb without the table cost.
- **Modal picker dialog.** Matches no other pattern in the app
  and adds a click before each preview switch. Inline picker
  wins on directness.

## Proposed PR sequence

### PR A — Page chrome + reviewer picker

**Goal.** A real `session_previews.html` body with the picker
working end-to-end, a context strip below it, and a placeholder
"Artifact previews land here" stub where the cards will appear.
No artifact rendering yet.

- Replace the placeholder body of `session_previews.html`. New
  template partial `operator/partials/_preview_picker.html`
  rendering the select + step buttons + Random + count + context
  strip.
- New view-shape adapter `views.build_preview_picker_context(
  session, reviewer_email)` returning:
  - the ordered reviewer list (for the `<select>` options),
  - the current reviewer (or `None` if empty / unmatched),
  - prev / next reviewer emails for the step-button hidden
    inputs,
  - the count `(index, total)`,
  - the context-strip data (assigned-reviewees list capped at
    a configured `PREVIEW_PICKER_REVIEWEE_PEEK_COUNT = 3` plus
    the disclosure tail).
- Update `previews_stub` (or rename to `previews_index`) at
  `routes_operator.py:1273` to read `?reviewer_email=` from the
  request, hydrate via the adapter, and render. No new POST
  routes — the picker is GET-only via query parameter.
- The body below the picker renders one stub `.card.placeholder`
  with copy "Artifact previews — invitation email and reviewer
  surface — land in PR B / PR C." Same placeholder treatment as
  Quick Setup / Extract Data on Home, retired by PR B + C.
- **Empty state**: if `len(reviewers) == 0`, the picker
  renders disabled with the spec's copy ("No reviewers
  configured. Add reviewers via the Reviewers Setup page or
  the Quick Setup card on Home.") and the placeholder body
  picks up the same explanatory tone.
- Tests:
  - First-load (no `?reviewer_email`) defaults to the first
    reviewer alphabetically; Reviewer 1 of N.
  - `?reviewer_email=alice@x.edu` selects Alice; Prev wraps
    to last, Next advances to next.
  - Random click 303s with a `?reviewer_email=` param drawn
    from the reviewer set; never selects out-of-set.
  - Unknown email param falls through to first reviewer
    (graceful degradation, no 404).
  - Empty session renders the disabled picker + empty-state
    copy.

### PR B — Invitation email card

**Goal.** Render the invitation email the selected reviewer
would actually receive, using the production render path.

- New artifact registry seam in `app/web/views.py`:
  ```python
  @dataclass(frozen=True)
  class PreviewArtifactSpec:
      key: str               # "invitation_email"
      label: str             # "Invitation email"
      audience: str          # "reviewer" — future-proof for
                             # the Reviewee hub
      render: Callable[[ReviewSession, Reviewer], CardBody]
      source_pages: list[tuple[str, str]]  # (label, url) pairs
                                            # for the footer
  ```
  Plus a module-level `PREVIEW_ARTIFACTS: list[PreviewArtifactSpec]`
  the page iterates over. PR B appends one entry; PR C appends
  the second.
- New template partial `_preview_card.html` rendering one
  artifact card: title, one-line description, body (artifact
  output or scoped missing-data error), source-of-truth footer.
- **Invitation render adapter** in
  `app/web/views.py` calling
  `email_templates.render_invitation(session, reviewer)` and
  packaging the rendered subject + from / to / body into a
  `CardBody` dataclass the partial consumes. Subject + headers
  styled approximately as the reviewer's email client would
  show them (basic envelope; not a faux-Outlook chrome — this
  is a render preview, not a costume).
- **Missing-data handling**: if `session.email_template_overrides
  is None` *and* the seeded default for invitations is also
  unset (which currently can't happen since seeded defaults
  always exist, but the check is cheap and forward-compatible
  for Segment 11M), render the spec's
  "Invitation email template not set up. Configure on the
  Email Template Setup page." stub with a link to
  `/operator/sessions/{id}/setupinvite?template=invitation`.
- Tests:
  - Selected reviewer's invitation renders with subject + body
    populated; merge tags (`$reviewer_name`, `$session_name`,
    `$deadline`, `$help_contact`, `$invite_url`) are
    substituted.
  - Switching reviewers via the picker swaps the rendered
    name / `invite_url` (different reviewer ⇒ different
    one-time-use token) — pin via integration test snapshot.
  - Email-template-not-set path renders the missing-data
    stub with the configured Setup-page link.
  - Source-of-truth footer renders Email Template + Reviewers
    Setup-page links.

### PR C — Reviewer surface card + retire `/preview` route

**Goal.** Render the form the selected reviewer would land on
after clicking the invitation, using the production
`build_preview_context`. Retire the standalone `/preview`
(singular) route now that its content lives in the hub.

- Append a second `PreviewArtifactSpec` entry for the reviewer
  surface, with a render adapter that calls
  `routes_reviewer.build_preview_context(db, user,
  review_session, target_reviewer=reviewer)`. The existing
  `build_preview_context` already pads with up to three
  synthetic rows when fewer real assignments exist (per
  Segment 10B-3); thread the selected reviewer's identity
  through so the synthetic-row rendering surfaces *that
  reviewer's* assignments rather than the operator-as-reviewer
  fallback.
- Render the reviewer-surface artifact inline as an `<iframe
  srcdoc="…">` of the rendered `reviewer/review_surface.html`
  with `preview_mode=True`. Iframe rather than direct embed
  because the reviewer surface ships its own `body.ui-v2
  reviewer` chrome and CSS scope; embedding inline would leak
  the reviewer top-bar and styling into the operator page.
  An iframe is the smallest tool that gets the spec's
  "production parity" guarantee — the reviewer sees the same
  bytes — without a separate "preview mode" template fork.
- **Missing-data handling**: per spec, if the reviewer has no
  assignments → "This reviewer has no reviewees assigned.
  Configure assignments on the Assignments Setup page."; if
  `session.instruments` is empty → "No instruments configured.
  Configure on the Instruments Setup page." Errors scoped to
  this card only; the invitation card above keeps rendering.
- **Retire `/sessions/{id}/preview` (singular).** The
  standalone route at `routes_operator.py:1300` and its breadcrumb
  / link references go. Replace its inbound link from the
  Session Home Next Action card ("See previews" link at
  `session_detail.html:153`) with a link to the hub plus a
  fragment to the reviewer-surface card
  (`/operator/sessions/{id}/previews#reviewer-surface`). One
  redirect from `/preview` → `/previews` for any stragglers
  (bookmarks, external links from the Sessions list, etc.); a
  permanent 308 keeps SEO / browser caching honest.
- Tests:
  - Reviewer-surface card renders the selected reviewer's
    assigned reviewees in the iframe.
  - Switching reviewers via the picker swaps which reviewees
    surface in the iframe.
  - Missing-assignments path renders the missing-data stub
    without breaking the invitation card above it.
  - `/preview` → `/previews` redirect is a 308 with the
    fragment preserved.
  - Session Home "See previews" link points at the hub.

### PR D — Reminder email card

**Goal.** Render the reminder email the selected reviewer
would receive, using the production render path. Smaller than
PR B because the registry, the card partial, and the
missing-data path are all already in place.

- Append a third `PreviewArtifactSpec` entry to
  `views.PREVIEW_ARTIFACTS` for the reminder. Render adapter
  calls `email_templates.render_reminder(session, reviewer)`
  and packages the rendered subject + from / to / body into
  the existing `CardBody` dataclass PR B introduced.
- **Position in registry.** Insert between the reviewer-
  surface card and (eventually) the responses-received card,
  matching the chronological arc the reviewer experiences
  (invitation arrives → reviewer opens the form → reminder
  arrives if they don't act → responses-received arrives on
  submit).
- **Card description.** "Sent against an active session past
  the configured reminder threshold. Operators trigger
  reminders from the consolidated Manage Invitations page
  (Segment 11C)." This grounds the operator in the live
  send-side affordance without duplicating it here.
- **Source-of-truth footer.** Reuses the Setup-page links the
  invitation card uses (Email Template + Reviewers); the
  reminder body lives in the same `email_template_overrides`
  JSON column the invitation does, edited from the same
  `/setupinvite` page (different `?template=reminder` tab).
- **Missing-data handling.** Same shape as the invitation
  card: if `session.email_template_overrides` lacks reminder
  keys *and* the seeded reminder default is unset (cannot
  happen today; cheap forward-compatible check), render the
  "Reminder template not set up. Configure on the Email
  Template Setup page." stub with a
  `?template=reminder`-anchored link.
- **No new lifecycle gating.** Card renders in all session
  states like its siblings.
- Tests:
  - Selected reviewer's reminder renders with subject + body
    populated; canonical-five merge tags substitute.
  - Switching reviewers via the picker swaps the rendered
    name / `$invite_url` (the reminder still carries the
    sign-in link until the reviewer submits).
  - Reminder-template-not-set path renders the missing-data
    stub with the configured Setup-page link.
  - Card sits between the reviewer-surface card (PR C) and
    the responses-received card (PR E) in the rendered DOM
    order — pin via integration test.

### PR E — Responses-received email card

**Goal.** Render the confirmation email the reviewer receives
on submit, using the `render_responses_received` helper
Segment 11E PR 6 introduces.

**Cross-segment seam.** Segment 11E PR 6's scope already
calls out a "Preview hub registry append" for this artifact
("lands here, not in 11F"). Both plans converge on the same
one-line registry append + render adapter; only one of the
two PRs ships the work, the other strikes its corresponding
scope item:

- If **11E PR 6 ships first** — the registry entry, render
  adapter, and Preview hub integration land there. PR E in
  this guide collapses to a strikethrough note ("shipped
  with 11E PR 6") and the segment is sized at 4 PRs (A-D)
  rather than 5.
- If **11F PR D ships first** (i.e., we land the reminder
  card, then come back for responses-received before 11E
  PR 6 lands) — PR E lands the registry append here, and
  11E PR 6's scope drops the registry-append bullet.
- The render adapter shape is identical in both cases:
  call `render_responses_received(session, reviewer)`, return
  a `CardBody` with the rendered subject / from / to / body.
  Whichever plan owns the work, the other references it.

Scope assuming PR E ships the work (the conservative case
this guide covers; flip if the order resolves the other way):

- Append a fourth `PreviewArtifactSpec` to
  `views.PREVIEW_ARTIFACTS` after the reminder. Render
  adapter calls `render_responses_received(session,
  reviewer)`.
- **Card description.** "Sent the moment the reviewer
  submits their review."
- **Source-of-truth footer.** Email Template
  (`?template=responses_received` per 11E PR 6) + Reviewers.
- **Merge-tag set.** Four tags per 11E PR 6 — drops
  `$invite_url`, includes optional `$submitted_at`. The
  `$submitted_at` resolution path is owned by 11E PR 6's
  helper; the preview adapter calls through to it without
  knowing the implementation.
- **Pre-submit preview rendering.** When the picker-selected
  reviewer has not yet submitted any assignments (the common
  pre-flight case), `$submitted_at` falls back to the
  "(not yet submitted)" placeholder per 11E PR 6's helper
  contract. The card surfaces a one-line note above the
  rendered body — "Previewing pre-submit; `$submitted_at`
  shows a placeholder." — so the operator isn't surprised
  the date field doesn't carry a real value.
- **Missing-data handling.** Same template-not-set / no-help-
  contact paths as the other email cards.
- Tests:
  - Card renders with `$submitted_at` populated when the
    selected reviewer has submitted assignments (use a
    fixture that pre-stamps `submitted_at`).
  - Card renders with the placeholder + the explanatory note
    on a reviewer with no submitted assignments.
  - Card sits last in the rendered DOM order
    (invitation → reviewer-surface → reminder →
    responses-received).
  - Cross-segment seam: integration test passes regardless of
    whether 11E PR 6's registry append landed here or there
    (the test asserts the rendered DOM, not which file
    introduced the registry entry).

## Implementation pointers

- **Production parity is non-negotiable** (spec §"Rendering").
  Don't add a "preview mode" branch in
  `email_templates.render_invitation` — call the function
  exactly as the live send path does. The reviewer surface
  already has a `preview_mode` template flag from Segment
  10B-3, but that flag suppresses *write paths* (the form
  doesn't submit), not *rendering* — keep it.
- **Iframe sandboxing.** The reviewer-surface iframe should
  carry `sandbox="allow-same-origin"` (no `allow-forms`, no
  `allow-scripts`) so a reviewer template that ever picks up
  client-side JS can't fire inside the operator's preview
  page. The reviewer surface today has no JS submit anyway, so
  this is a forward-compatibility belt.
- **Picker prev/next state encoding.** Compute prev / next
  emails server-side (in the view adapter), not client-side.
  Avoids a JS list of all reviewer emails leaking into
  every preview page render. The buttons are tiny GET forms
  (or links with `?reviewer_email=…`) carrying the precomputed
  target.
- **No new audit shapes.** Previewing is read-only operator
  inspection; emit no audit events. Send-test (when it lands
  in 11C) is the audit point for outbound-from-the-hub
  actions.
- **Artifact registry placement.** Keep `PREVIEW_ARTIFACTS`
  in `app/web/views.py`, not a new module. The list is small,
  the page is the only consumer, and `views.py` already owns
  the page-shape adapters that bridge services to templates.
  Move to its own module only if the registry grows past ~5
  entries.

## Out of scope (cross-references)

- **Send-test affordance** — Segment 11C PR F. Same
  `EmailTransport` interface; one wiring point on the
  consolidated Manage Invitations page covers per-row, bulk,
  and per-artifact test sends.
- **Reviewee Experience Preview hub** — the artifact registry's
  `audience` field is the seam; the parallel hub itself is a
  future segment.
- **AG Grid-style interactive form preview** — Segment 15 / #33.
  The static iframe snapshot is the right primitive for
  pre-flight inspection.
- **Real reviewer submission state** — Monitoring's job, not
  the preview hub's. Segment 11C surfaces this on the
  consolidated Responses page.

## Test impact

- New `tests/integration/test_session_previews.py` covering:
  picker default / param / step / random / wrap; per-card
  render for selected reviewer; missing-data scoped errors per
  card; lifecycle render in `draft` / `validated` / `ready` /
  `closed` (assert no lock card around the cards themselves);
  `/preview` → `/previews` redirect.
- New `tests/unit/test_preview_picker_context.py` pinning the
  view adapter's prev / next / count math (especially the
  wrap-around edge cases and the empty-session degenerate
  state).
- One snapshot fixture per artifact under
  `tests/fixtures/previews/` — the rendered invitation email
  body for a populated session, and the reviewer-surface
  iframe-srcdoc trimmed to its `<main>` block. Future contract
  changes to either render path have to deliberately update
  the fixture.
- No churn on the existing email-template or reviewer-surface
  test suites — those cover the underlying render paths the
  hub composes.

## Doc impact

- `guide/todo_master.md` — move 11F from **Upcoming** to
  **Done** once PR C ships; mention the deferred reminder /
  responses-received artifacts and the send-test fold into 11C.
- `docs/status.md` — timeline entry per PR.
- `spec/preview_hub.md` — reconcile two small drift points with
  what 11F ships:
  - URL slug `/preview` (singular) in the spec vs. `/previews`
    (plural) in the chrome and the shipped placeholder. Plural
    wins; spec edit is a one-liner.
  - The four-artifact list narrows to two for 11F; spec gains a
    "shipped in 11F" / "deferred to follow-on" annotation per
    artifact rather than rewriting the list.
- `spec/operator_ui_concept.md` — verify the Operations row
  tab order matches what 11F leaves in the chrome
  (`Validate / Previews / Invitations / Monitoring / Outbox`
  is the current shipped order; spec preview uses `Preview /
  Invitations / Monitoring / Outbox`). Tab-order reconciliation
  is a Segment 11C concern (it owns the Operations row sweep);
  flag it in 11C's plan rather than fix here.
