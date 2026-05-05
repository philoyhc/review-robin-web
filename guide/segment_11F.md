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

Planning. Sized as **3 PRs** in dependency order, each
independently shippable:

1. **PR A — Page chrome + reviewer picker.** No artifact cards
   yet; the body renders the picker and an empty-state stub
   below it.
2. **PR B — Invitation email card.** Renders through
   `email_templates.render_invitation` verbatim.
3. **PR C — Reviewer surface card.** Folds in the existing
   `/preview` (singular) form-only preview as a hub card and
   retires the standalone route.

Send-test affordances per artifact (spec §"Send-test") are
**deferred** to either a small 11F follow-on or to Segment 11C
PR F (which already wires `EmailTransport` into per-row + bulk
send on Manage Invitations). Folding them into 11C is the
cleaner option — same transport seam, one set of tests — and
keeps 11F itself small.

## Why this scope

The spec defines four artifacts (invitation, response form,
reminder, responses-received). Two of those four are mid /
post-flight communications:

- **Reminder email** is sent against an active session past a
  threshold; previewing it pre-flight is useful but not
  blocking.
- **Responses-received email** doesn't have a render path yet
  (`app/services/email_templates.py` has `render_invitation` and
  `render_reminder`, but no responses-received template). Adding
  one is a separate scope.

The two artifacts the operator must inspect *before* activating
the session are the **invitation email** (the message that
goes out the moment they hit Activate) and the **reviewer
surface** (what the reviewer lands on after clicking the link).
These are the pre-flight blockers; 11F ships them and pins the
hub structure so reminder + responses-received drop in as new
registry entries later without touching the page chrome.

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
- **Artifact registry seam.** Even with only two artifacts in
  PR B / PR C, the page iterates over a small registry tuple
  list at `app/web/views.py` (something like
  `PREVIEW_ARTIFACTS: list[ArtifactSpec]`) so registering the
  reminder / responses-received cards later is a one-line
  append, not a template rewrite. Per spec §"Forward-looking" —
  the registry is also where the future Reviewee Experience
  Preview filters by audience.

Out:

- **Reminder email card.** Render path exists
  (`render_reminder`) but reminder previewing is not pre-flight
  blocking. Lands as a follow-on registry append once the spec
  is reconciled with the Segment 11C consolidated reminder
  flow.
- **Responses-received email card.** No render path yet; adding
  one is its own scope. Defer with the rest of post-submit
  comms (likely Segment 11M / 15).
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

- **Reminder email artifact** — render path exists
  (`email_templates.render_reminder`) but lands as a follow-on
  registry append once Segment 11C's consolidated reminder flow
  settles. The reminder UX makes more sense to preview when the
  preview surface and the live send surface (Manage
  Invitations) share their reminder vocabulary.
- **Responses-received email artifact** — no render path
  exists. Add the render path *and* the registry entry as one
  scope; not 11F.
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
