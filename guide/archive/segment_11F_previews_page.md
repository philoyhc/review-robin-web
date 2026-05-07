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

**Done. All 5 planned PRs shipped:**

- **PRs A / B / C** ✅ shipped 2026-05-06 (#517 / #520 / #521 /
  #522 / #523 plus follow-ups).
- **PR D** ✅ shipped 2026-05-07 — wires the reminder tab's
  render adapter to `email_templates.render_reminder` (with
  `PREVIEW_INVITE_URL_PLACEHOLDER` for `$invite_url`); flips
  `EMAIL_PREVIEW_TABS["reminder"].is_shipped=True`. Same shape
  as the responses-received activation in PR 6.
- **PR E** ✅ shipped 2026-05-07 via Segment 11E PR 6 (#532) —
  the registry mutation + render-adapter dispatch branch rode
  along with the editor third tab on the same
  `render_responses_received` helper.

After PR D ships, **11F retires** — the plan moves to
`guide/archive/`. Send-test affordances (originally deferred
to "either a small 11F follow-on or to Segment 11C PR F") now
live in **Segment 14-1 Part A** as part of the wider email
send-activation work.

1. **PR A — Page chrome + reviewer picker.** ✅ Shipped. No
   artifact regions yet; the body renders the picker and a
   single combined empty-state card below it ("Pick a reviewer
   above to preview their experience.").
2. **PR B — Email previews region (tabbed) + invitation
   card.** Introduces the artifact registry seam, the email
   region's three-tab strip (Invitation / Reminder /
   Responses-received), the active-tab body wired through
   `email_templates.render_invitation`, the `<hr>` separator
   below it, and a stub where PR C's surface card will land.
   Reminder + Responses-received tabs render disabled until
   PRs D/E enable them.
3. **PR C — Reviewer surface card.** Fills the placeholder
   below the `<hr>`. Folds in the existing `/preview`
   (singular) form-only preview as a hub card and retires the
   standalone route. Independent of the email region.
4. **PR D — Enable Reminder tab.** Wires the Reminder entry
   in PR B's `EMAIL_PREVIEW_TABS` registry to a real render
   adapter; the previously-disabled Reminder tab in PR B's
   strip lights up and renders through
   `email_templates.render_reminder`.
5. ~~**PR E — Enable Responses-received tab.**~~ Shipped
   2026-05-07 via Segment 11E PR 6 (#532) — the registry
   mutation + render-adapter dispatch branch rode along with
   the editor third tab on the same `render_responses_received`
   helper. See "~~PR E~~" below.

Send-test affordances per artifact (spec §"Send-test") are
**deferred** to **Segment 14-1 Part A** (which wires
`EmailTransport` into per-row + bulk + test sends on Manage
Invitations as the first call site of the transport interface).
Folding them into 14-1 is the cleaner option — same transport
seam, one set of tests — and keeps 11F itself small.

## Why this scope

The spec defines four reviewer-facing artifacts (invitation,
response form, reminder, responses-received). All four ship in
11F now that 11E PR 6 has shipped `render_responses_received`
(and the responses-received tab activation rode along with it).
The original 2-card sizing carved off the two pre-flight
blockers — **invitation** and **reviewer surface** — so PR B /
PR C could land before reminder / responses-received UX
questions settled. Those questions have settled enough to ship,
so the deferred two slot in: PR E shipped via 11E PR 6, PR D
remains for the Reminder tab.

## Scope

In:

- Replace the `session_previews.html` placeholder body with the
  real hub: reviewer picker top, then a list of artifact cards.
- **Reviewer picker** as proposed below ("Reviewer picker UI").
  URL state via `?reviewer_email={email}` so the selected
  reviewer is bookmarkable / shareable; default = no reviewer
  selected (operator must pick explicitly), so the cards below
  stay in a single combined empty state until then.
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
  the helper Segment 11E PR 6 ships. Five-tag merge-set per 11E
  (drops `$invite_url`, adds `$submitted_at`). Card description:
  "Sent the moment the reviewer submits their review." Activated
  via 11E PR 6 (the registry mutation + dispatch branch landed
  there alongside the editor third tab); see "~~PR E~~" below.
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
- **Email-tab registry seam.** The email region's tab strip
  iterates over a small registry list at `app/web/views.py`
  (`EMAIL_PREVIEW_TABS: list[EmailPreviewTab]`); each tab is
  one entry. The list order pins the rendered tab order
  (invitation → reminder → responses-received, the
  chronological arc the reviewer experiences). PR B seeds all
  three entries with `render=None` for the unshipped two,
  flipping them on as PRs D / E land. The reviewer surface is
  not in this registry — it's a structurally different artifact
  (iframe, not subject + body) and lives in its own card below
  the `<hr>` separator.

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

## Page layout

Three vertically-stacked regions:

```
┌─────────────────────────────────────────────┐
│ Reviewer picker (half-width card)           │  ← PR A, shipped
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ [Invitation] [Reminder] [Responses-recv]    │  ← PR B (tabs);
│                                             │    only one body
│  Subject: …                                 │    rendered at a time
│  From: …  To: …                             │
│  ─────────────────────────────────────────  │
│  …rendered email body…                      │
│                                             │
│  Rendered from Email Template (Setup) …     │
└─────────────────────────────────────────────┘

──────────────────────────────────────────────  ← <hr>

┌─────────────────────────────────────────────┐
│ Reviewer surface (iframe srcdoc)            │  ← PR C
└─────────────────────────────────────────────┘
```

**Email previews region — tabbed.** The three reviewer-facing
emails (invitation, reminder, responses-received) share one
full-width card with a `.btn-pair` tab strip at the top. Only
one email body renders at a time. URL state extends to
`?reviewer_email=…&email={invitation|reminder|responses_received}`;
default `email=invitation` when the param is absent. The tab
pattern mirrors the existing Email Template (Setup) page
(`session_setupinvite.html:18-27`): active tab as a disabled
`<button class="btn">` (reads as the current view); inactive
tabs as `<a class="btn secondary" href="?email=…">`. Tabs
whose render adapter hasn't shipped yet (PR D / PR E) render
**disabled** with `aria-disabled="true"`.

This drifts from `spec/preview_hub.md` §"Page layout", which
proposes four full-width cards stacked vertically. The tabbed
email region collapses three of those four cards into one
slot; the fourth (reviewer surface) stays its own card below
the `<hr>`. Rationale: the three emails share an identical
shape (subject + from / to / body) and are visually
redundant when stacked. The reviewer surface is structurally
different (iframe of the live form) and warrants its own
card. The spec gets a one-line note flagging this drift; see
"Doc impact" below.

**Reviewer surface region — full-width card.** The card sits
below an `<hr>` separator and renders an `<iframe srcdoc="…">`
of the rendered `reviewer/review_surface.html` so it inherits
the reviewer chrome verbatim. Iframe carries
`sandbox="allow-same-origin"` per the implementation pointers
below.

**Empty state composition.** When no reviewer is yet picked,
the artifact regions collapse to one combined empty-state
card ("Pick a reviewer above to preview their experience.")
above where the email region + `<hr>` + surface card would
sit. Already in place from PR A; PR B and PR C each move
their respective region from this combined card to its own
real card once a reviewer is selected.

## Reviewer picker UI

The picker is the spine of the page. It controls every artifact
card's render.

### Proposed shape — typeahead + step buttons + count

```
┌──────────────────────────────────────────────────────────────┐
│ Previewing as:                                               │
│ ┌────────────────────────────────────────────────────┐       │
│ │ Search reviewer name or email...                   │ Apply │
│ └────────────────────────────────────────────────────┘       │
│  ← Previous   Next →   Random                                │
│                                                              │
│ Reviewer 3 of 47 · Alice Smith (alice@x.edu) · 5 reviewees   │
│ assigned: Bob Jones, Carol Lee, …  more                      │
└──────────────────────────────────────────────────────────────┘
```

When no reviewer is yet selected:

```
┌──────────────────────────────────────────────────────────────┐
│ Previewing as:                                               │
│ ┌────────────────────────────────────────────────────┐       │
│ │ Search reviewer name or email...                   │ Apply │
│ └────────────────────────────────────────────────────┘       │
│  ← Previous (disabled)   Next → (disabled)   Random          │
│                                                              │
│ 47 reviewers in this session. Pick one to preview the        │
│ invitation, surface, reminder, and confirmation they'd see.  │
└──────────────────────────────────────────────────────────────┘
```

The picker contains:

1. **Primary control: a typeahead `<input list="…">` paired
   with a `<datalist>`.** The datalist holds one option per
   reviewer (`<option value="alice@x.edu">Alice Smith
   (alice@x.edu)</option>`). Native HTML5 — the browser shows
   matching suggestions as the operator types, accessibility is
   free, no JS for the typeahead itself.
   - Why datalist over a native `<select>`: a `<select>`
     forces the operator to scan in dropdown order. A typeahead
     lets them type "ali" and see only Alice / Aliyah / Aliza.
     For sessions with hundreds of reviewers this is the
     difference between scrolling and finding.
   - Why datalist over a custom JS combobox: zero JS, no
     accessibility re-implementation, no build step. The
     styling limits (the browser owns the suggestion panel's
     font and chrome) don't matter here — the operator only
     needs to see names and emails. If a future need surfaces
     (e.g. inline submission-status badges in suggestions),
     swap to a small inline JS combobox without changing the
     URL contract.
   - **Pattern is reusable.** Manage Invitations and Manage
     Responses both have a free-text search box with the same
     intent. If the datalist typeahead lands cleanly here, lift
     it into those pages as a separate slice — out of scope
     for 11F, worth flagging.

2. **Apply button.** Submits the form. The server parses the
   typed value: an exact email match selects that reviewer;
   `"Name (email)"` format extracts the email; an unmatched
   value renders a "No reviewer matched 'foo'." note below the
   input and leaves the picker in unselected state.

3. **Step buttons: "← Previous" / "Next →"** flanking the
   input. Operate over the full reviewer list (alphabetical by
   email, the same order the Reviewers Setup page uses). Wrap
   at the ends with a quiet visual cue (the count flash) so the
   operator notices. **Disabled when no reviewer is yet
   selected** — stepping needs a starting point.

4. **Random button.** Picks a reviewer uniformly at random
   from the full reviewer list. One click. Useful for spot-
   sampling on a 500-reviewer session — the operator won't
   page through all 500, but spot-checking 5 random ones
   catches most setup drift. Available even when no reviewer
   is yet selected (it's a valid first action).

5. **Count indicator: "Reviewer N of M".** Below the controls,
   alongside the selected reviewer's name + email + reviewee
   preview. Becomes "M reviewers in this session. Pick one…"
   when nothing is selected.

### Below the picker — passive context strip

When a reviewer is selected: a short strip naming the current
selection's key attributes — name, email, reviewee count, and
the first ~3 reviewee names with a "more" disclosure for the
rest. The disclosure is a `<details>` element (native, no JS),
default collapsed.

When no reviewer is selected: the strip collapses to the one-
line empty state shown in the second mockup above, directing
the operator to the picker as their next action.

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

**Default behavior is no reviewer selected** — explicit
operator pick is the only path to an artifact render. This is
a deliberate change from earlier shapes that defaulted to the
first reviewer alphabetically: defaulting hides the "you need
to pick someone" affordance behind a populated render that
looks like it's already showing the right answer. With no
default, the operator's first interaction is intentional.

If `?reviewer_email=` is present but matches no reviewer, the
picker surfaces the "No reviewer matched" note and stays in
unselected state — no 404, no fallback to first. If the
session has no reviewers at all, the picker renders disabled
with the empty-state copy from spec §"Empty state" and the
body below picks up the same explanatory tone.

### Non-mechanics

- **Default ordering** for the datalist and Prev/Next/Random
  matches the Reviewers Setup page (alphabetical by email).
  Whatever sort `app/web/routes_operator.py` reviewers index
  uses, the picker reuses — no second mental model.
- **Step buttons preserve ordering**, so "Next" advances by
  one in the picker's list order, not by reviewer-id order.
- **Random selection happens server-side**, via
  `secrets.choice` over the reviewer list. The button is a
  tiny POST (or a GET to a redirector) that 303s to
  `?reviewer_email=…`. No reviewer-email list leaks into
  client-side JS this way.
- **No JS framework.** One inline `onchange` line on the input
  optionally auto-submits when the operator picks a datalist
  suggestion; everything else is plain `<form method="get">`.
  Step buttons submit tiny `<form>`s carrying the precomputed
  target `reviewer_email` in a hidden input.

### Why not these alternatives

- **Native `<select>` only.** Forces scanning a long list in
  dropdown order. Datalist gives the same zero-JS guarantee
  plus substring filtering for free.
- **Custom JS combobox.** Heavier, accessibility to redo,
  build-step temptation. No real benefit over datalist unless
  suggestions need custom inline content (status badges, etc.).
- **Reviewer table with radio-select.** Renders the full list
  inline; at 500 reviewers the table dwarfs the artifact cards
  below, defeating the page's purpose. Step buttons get the
  "page through reviewers" verb without the table cost.
- **Modal picker dialog.** Matches no other pattern in the app
  and adds a click before each preview switch. Inline picker
  wins on directness.
- **Default-to-first-reviewer.** Hides the "you need to pick"
  affordance behind a render that looks done. Explicit pick is
  part of the UX intent.

## Proposed PR sequence

### PR A — Page chrome + reviewer picker ✅ Shipped (PR #517 / #520)

**Goal.** A real `session_previews.html` body with the
typeahead picker working end-to-end, a context strip below it,
and a placeholder "Artifact previews land here" stub where the
cards will appear. No artifact rendering yet.

- Replace the placeholder body of `session_previews.html`. New
  template partial `operator/partials/_preview_picker.html`
  rendering the search input + `<datalist>` + Apply + step
  buttons + Random + count + context strip.
- New view-shape adapter `views.build_preview_picker_context(
  session, reviewer_query)` returning:
  - the ordered reviewer list (for the `<datalist>` options),
  - the resolved current reviewer (or `None` if unselected /
    unmatched),
  - prev / next reviewer emails for the step-button hidden
    inputs (or `None` when no current reviewer),
  - the count `(index, total)` when a reviewer is selected;
    just `total` otherwise,
  - the context-strip data (assigned-reviewees list capped at
    a configured `PREVIEW_PICKER_REVIEWEE_PEEK_COUNT = 3` plus
    the disclosure tail),
  - a "no match" indicator + the operator's typed value, when
    the submitted `reviewer_email` didn't resolve.
- Update `previews_stub` (rename to `previews_index`) at
  `routes_operator.py:1318` to read `?reviewer_email=` from the
  request, hydrate via the adapter, and render. Add a tiny
  `POST /sessions/{id}/previews/random` route that picks a
  reviewer via `secrets.choice` and 303s to `?reviewer_email=…`
  — the Random button posts to it. Step buttons stay GET (they
  carry the precomputed target in hidden inputs). Apply submits
  the search form as GET with the typed value mapped onto
  `?reviewer_email=`.
- The body below the picker renders a single empty-state card
  when no reviewer is selected ("Pick a reviewer above to
  preview their experience."); otherwise PR A renders one
  `.card.placeholder` stub ("Artifact previews — invitation
  email, reviewer surface, reminder, and confirmation — land
  in PR B–E."), retired card-by-card as PR B–E ship.
- **Empty-session state**: if `len(reviewers) == 0`, the picker
  renders disabled with the spec's copy ("No reviewers
  configured. Add reviewers via the Reviewers Setup page or
  the Quick Setup card on Home.") and the placeholder body
  picks up the same explanatory tone.
- Tests:
  - First-load (no `?reviewer_email`) renders the picker with
    no reviewer selected; artifact body shows the "Pick a
    reviewer" empty state; Prev/Next are disabled.
  - `?reviewer_email=alice@x.edu` selects Alice; Prev wraps to
    last, Next advances; count reads "Reviewer N of M".
  - `?reviewer_email=ghost@x.edu` (not in session) renders the
    "No reviewer matched" note and stays in unselected state —
    does not 404, does not fall back to first reviewer.
  - Apply with `"Alice Smith (alice@x.edu)"` typed in (the
    datalist label format) resolves to Alice — the adapter
    extracts the email from the parens.
  - Random POST 303s to a `?reviewer_email=` param drawn from
    the reviewer set; never selects out-of-set.
  - Empty session (zero reviewers) renders the disabled picker
    + empty-state copy.
  - The `<datalist>` contains one `<option>` per reviewer in
    the session (integration test counts options).

### PR B — Email previews region (tabbed) + invitation card

**Goal.** Stand up the email previews region — a single full-
width card with a three-tab strip (Invitation / Reminder /
Responses-received) that renders the active email's subject +
from / to / body. Wire only the Invitation tab to a real render
adapter; Reminder + Responses-received tabs render disabled
until PRs D / E activate them. Add the `<hr>` separator and a
placeholder where PR C's surface card will land.

- New email-tab registry seam in `app/web/views.py`:
  ```python
  @dataclass(frozen=True)
  class EmailPreviewTab:
      key: str         # "invitation" / "reminder" /
                       # "responses_received"
      label: str       # "Invitation" / "Reminder" / etc.
      render: Callable[[ReviewSession, Reviewer], EmailBody] | None
      """``None`` until the corresponding PR D / PR E lands;
      a None render means the tab renders disabled."""
      source_pages: list[tuple[str, str]]
      """``(label, url)`` pairs for the source-of-truth footer.
      Email Template (Setup) deep-links to the matching
      ``?template=`` tab; Reviewers (Setup) is constant."""
      template_setup_param: str
      """The ``?template=`` value the Setup deep-link uses,
      e.g. ``"invitation"`` or ``"reminder"``."""
  ```
  Plus a module-level
  ``EMAIL_PREVIEW_TABS: list[EmailPreviewTab]`` ordered
  invitation → reminder → responses-received (the
  chronological arc the reviewer experiences). PR B seeds all
  three entries but only the invitation entry has a non-`None`
  render; PRs D / E swap the others to non-`None`.
- New template partial `_email_preview_region.html` rendering:
  - The `.btn-pair` tab strip — active tab is a disabled
    `<button class="btn">` (matches `session_setupinvite.html`
    line 21); inactive *and shipped* tabs are
    `<a class="btn secondary" href="?…">`; inactive *and
    unshipped* tabs render as `<button class="btn secondary"
    disabled aria-disabled="true">` with the label suffixed
    "(coming soon)" so the operator knows the tab is wired.
  - The active email's body (subject + from / to / body) when
    its render adapter is non-`None`, or a "Coming in PR D /
    PR E" placeholder when the disabled-tab branch somehow
    became active (shouldn't happen via the tab strip; only
    via a hand-edited URL).
  - Source-of-truth footer ("Rendered from Email Template
    (Setup) and Reviewers (Setup).") with the deep-linked
    Setup-page anchors per the active tab's `source_pages`.
- **Invitation render adapter** in `app/web/views.py` calling
  `email_templates.render_invitation(session, reviewer)` and
  packaging the rendered subject + from / to / body into the
  `EmailBody` dataclass the partial consumes. Subject + headers
  styled approximately as the reviewer's email client would
  show them (basic envelope; not a faux-Outlook chrome — this
  is a render preview, not a costume).
- Update `previews_index` route to read `?email=` (default
  `"invitation"`) and resolve to one of the
  `EMAIL_PREVIEW_TABS` entries; an unknown / unshipped value
  falls back to `"invitation"` rather than 404. URL state is
  now ``?reviewer_email=…&email=invitation``.
- Below the email card, render an `<hr>` separator followed by
  a placeholder card ("Reviewer surface preview lands in PR C
  of segment 11F.") that PR C replaces. The combined "Pick a
  reviewer above" empty state PR A introduced still renders
  before either region when no reviewer is selected (the
  email card and `<hr>` and surface placeholder don't render
  in that branch).
- **Missing-data handling**: if the invitation-template seeded
  default is unset *and* the session has no overrides for it
  (cannot happen today; cheap forward-compatible check for
  Segment 11M), render the spec's "Invitation email template
  not set up. Configure on the Email Template Setup page."
  stub with a link to
  ``/operator/sessions/{id}/setupinvite?template=invitation``.
- Tests:
  - Selected reviewer's invitation renders with subject + body
    populated; merge tags (`$reviewer_name`, `$session_name`,
    `$deadline`, `$help_contact`, `$invite_url`) are
    substituted.
  - Tab strip renders three tabs in order; the Invitation tab
    is the disabled-button "current view" indicator on first
    load (no `?email=` param); the other two render disabled
    with `aria-disabled="true"` and the "(coming soon)" suffix.
  - `?email=reminder` (an unshipped tab) falls back to the
    invitation render — no 404, no broken page.
  - `?email=` mid-page-redirect preserves `?reviewer_email=`.
  - Switching reviewers via the picker swaps the rendered
    name / `invite_url` in the active tab (different reviewer
    ⇒ different one-time-use token) — pin via integration
    snapshot.
  - Email-template-not-set path renders the missing-data
    stub with the configured Setup-page link.
  - Source-of-truth footer renders the Email Template
    (`?template=invitation`) + Reviewers Setup-page links.
  - Empty-session path: when no reviewer is selected, the
    email card + `<hr>` + surface placeholder are not in the
    DOM; only the combined "Pick a reviewer" card is.

### PR C — Reviewer surface card + retire `/preview` route

**Goal.** Replace PR B's surface placeholder card (below the
`<hr>`) with the real surface preview — an iframe srcdoc of
the rendered reviewer surface for the picker-selected
reviewer. Retire the standalone `/preview` (singular) route
now that its content lives in the hub. Independent of the
email region — does not touch `EMAIL_PREVIEW_TABS` or the tab
strip.

- New template partial `_surface_preview_card.html` rendering
  the surface card: title ("Reviewer surface"), one-line
  description ("The form the reviewer would see after clicking
  the invitation."), the iframe, and a source-of-truth footer
  pointing at the Reviewers + Assignments + Instruments Setup
  pages.
- New view-shape adapter in `app/web/views.py` —
  `build_surface_preview_context(db, user, session, reviewer)`
  — that calls
  `routes_reviewer.build_preview_context(db, user,
  review_session, target_reviewer=reviewer)` and packages the
  result into a small dataclass the partial consumes. The
  existing `build_preview_context` already pads with up to
  three synthetic rows when fewer real assignments exist (per
  Segment 10B-3); thread the selected reviewer's identity
  through so synthetic-row rendering surfaces *that
  reviewer's* assignments rather than the operator-as-reviewer
  fallback.
- Render the surface artifact inline as an `<iframe
  srcdoc="…">` of `reviewer/review_surface.html` rendered with
  `preview_mode=True`. Iframe rather than direct embed because
  the reviewer surface ships its own `body.ui-v2 reviewer`
  chrome and CSS scope; embedding inline would leak the
  reviewer top-bar and styling into the operator page. The
  iframe carries `sandbox="allow-same-origin"` (no
  `allow-scripts`, no `allow-forms`) per implementation
  pointers below.
- **Why not the registry?** The surface render produces an
  iframe srcdoc, not a subject + from / to / body envelope; it
  doesn't share the email tab's `EmailBody` shape. Keeping it
  outside `EMAIL_PREVIEW_TABS` keeps the tab strip
  semantically about emails and the surface as the page's
  second, structurally different region.
- **Missing-data handling**: per spec, if the reviewer has no
  assignments → "This reviewer has no reviewees assigned.
  Configure assignments on the Assignments Setup page."; if
  `session.instruments` is empty → "No instruments configured.
  Configure on the Instruments Setup page." Errors are scoped
  to the surface card only; the email region above the `<hr>`
  keeps rendering.
- **Retire `/sessions/{id}/preview` (singular).** The
  standalone route and its breadcrumb / link references go.
  Replace its inbound link from the Session Home Next Action
  card ("See previews" link in `session_detail.html`) with a
  link to the hub plus a fragment to the reviewer-surface card
  (`/operator/sessions/{id}/previews#reviewer-surface`). One
  permanent 308 redirect from `/preview` → `/previews` for any
  stragglers (bookmarks, external links from the Sessions
  list).
- Tests:
  - Surface card renders the selected reviewer's assigned
    reviewees in the iframe.
  - Switching reviewers via the picker swaps which reviewees
    surface in the iframe.
  - Missing-assignments path renders the missing-data stub
    without breaking the email region above the `<hr>`.
  - The `<hr>` separator sits between the email card and the
    surface card in the rendered DOM order — pin via
    integration test.
  - `/preview` → `/previews` redirect is a 308 with the
    fragment preserved.
  - Session Home "See previews" link points at the hub
    (`/previews#reviewer-surface`).

### PR D — Activate Reminder tab

**Goal.** Light up the previously-disabled Reminder tab in
PR B's strip by attaching a real render adapter. Tiny PR — one
render adapter, one registry mutation, one set of tests.

- Update the Reminder entry in
  `views.EMAIL_PREVIEW_TABS` so its `render` field points at a
  new adapter that calls
  `email_templates.render_reminder(session, reviewer)` and
  returns the same `EmailBody` shape PR B introduced.
- Update the tab-strip partial's "shipped vs. unshipped" check
  is automatic — it keys off `render is not None` — so the
  Reminder tab flips from disabled-with-"(coming soon)" to a
  live `<a class="btn secondary">` link with no template
  change.
- **Card description (rendered below the tab strip when
  Reminder is active).** "Sent against an active session past
  the configured reminder threshold. Operators trigger
  reminders from the consolidated Manage Invitations page
  (Segment 11C)." Grounds the operator in the live send-side
  affordance without duplicating it here.
- **Source-of-truth footer.** Email Template
  (`?template=reminder`) + Reviewers. The reminder body lives
  in the same `email_template_overrides` JSON column the
  invitation does, edited from the same `/setupinvite` page
  (different `?template=reminder` tab).
- **Missing-data handling.** Same shape as the invitation
  card: if the reminder template has no override *and* its
  seeded default is unset (cannot happen today; cheap forward-
  compatible check), render the "Reminder template not set up.
  Configure on the Email Template Setup page." stub with a
  `?template=reminder`-anchored link.
- **No new lifecycle gating.** Card renders in all session
  states like its siblings.
- Tests:
  - Reminder tab renders as a live `<a>` link in the strip,
    not a disabled button (the contrast against PR B's test
    is the contract here).
  - `?email=reminder` activates the tab and renders the
    reminder body with subject + canonical-five merge tags
    substituted.
  - Switching reviewers via the picker swaps the rendered
    name / `$invite_url` (the reminder still carries the
    sign-in link until the reviewer submits).
  - Reminder-template-not-set path renders the missing-data
    stub with the configured Setup-page link.
  - Tab order in the strip stays
    invitation → reminder → responses-received.

### ~~PR E — Activate Responses-received tab~~ — shipped 2026-05-07 via Segment 11E PR 6 (#532)

The cross-segment seam this section described resolved with 11E
PR 6 shipping first — the registry mutation + render adapter
landed there alongside the editor third tab, since both
depended on the same `render_responses_received` helper.

What shipped (in 11E PR 6):

- `views.EMAIL_PREVIEW_TABS` responses-received entry flipped
  to `is_shipped=True`.
- `views.build_email_preview_body` picked up a dispatch branch
  calling `email_templates.render_responses_received(session,
  reviewer)`.
- The card description and operator-facing copy ("Sent the
  moment the reviewer submits their review.") came along on
  the existing tab metadata.
- `$submitted_at` resolves via `_latest_submitted_at` (queries
  the reviewer's responses through `Session.object_session`);
  pre-submit falls back to the `"(not yet submitted)"`
  placeholder.
- New tests in `tests/integration/test_session_previews.py`
  cover the activated tab + placeholder behaviour.

The "previewing pre-submit; `$submitted_at` shows a
placeholder" explanatory note this section originally proposed
was not shipped — the placeholder text itself reads clearly
enough on its own. If a reviewer-side complaint comes in about
operators getting confused by the placeholder, the note can
land as a small `views.py` follow-up.

11F Part 2 collapses to **PR D only** (Reminder tab); 11F as a
whole now sizes at 4 PRs (A → D) rather than 5.

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
- **Registry placement.** Keep `EMAIL_PREVIEW_TABS` (and the
  surface adapter PR C adds) in `app/web/views.py`, not a new
  module. The list is small, the page is the only consumer, and
  `views.py` already owns the page-shape adapters that bridge
  services to templates. Move to its own module only if the
  registry grows past ~5 entries.

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

- `tests/integration/test_session_previews.py` (created in
  PR A) gains coverage for: tab strip default / disabled-tab /
  shipped-tab transition / unknown `?email=` fallback (PR B);
  per-tab body render for selected reviewer (PR B / D / E);
  missing-data scoped errors per tab; the `<hr>` separator's
  position between email card and surface card (PR C); the
  iframe srcdoc carrying the right reviewer's assignments
  (PR C); lifecycle render in `draft` / `validated` /
  `ready` / `closed` (assert no lock card around the cards
  themselves); `/preview` → `/previews` redirect (PR C).
- `tests/unit/test_preview_picker_context.py` (PR A) stays as
  is; new unit tests for any non-trivial render-adapter logic
  (e.g. PR E's pre-submit `$submitted_at` placeholder) live in
  the same file or a sibling.
- One snapshot fixture per email tab under
  `tests/fixtures/previews/` — the rendered invitation /
  reminder / responses-received bodies for a populated
  session, and the reviewer-surface iframe-srcdoc trimmed to
  its `<main>` block. Future contract changes to either
  render path have to deliberately update the fixture.
- No churn on the existing email-template or reviewer-surface
  test suites — those cover the underlying render paths the
  hub composes.

## Doc impact

- `guide/todo_master.md` — move 11F from **Upcoming** to
  **Done** once PR C ships; mention the deferred reminder /
  responses-received artifacts and the send-test fold into 11C.
- `docs/status.md` — timeline entry per PR.
- `spec/preview_hub.md` — reconcile three drift points with
  what 11F ships:
  - URL slug `/preview` (singular) in the spec vs. `/previews`
    (plural) in the chrome and the shipped placeholder. Plural
    wins; spec edit is a one-liner.
  - The four-artifact list narrows to two for 11F; spec gains a
    "shipped in 11F" / "deferred to follow-on" annotation per
    artifact rather than rewriting the list.
  - **Tabbed email region** — the spec proposes four full-width
    cards stacked vertically. 11F collapses the three email
    cards (invitation, reminder, responses-received) into one
    full-width card with a tab strip and renders the surface
    card separately below an `<hr>` separator. Spec gains a
    "Page layout (as built)" subsection or a footnote on the
    "Page layout" section noting this. Two emails would be
    visually redundant when stacked; the tabbed region cuts
    vertical scroll without losing per-artifact addressability
    (each email tab is bookmarkable via
    `?email=invitation|reminder|responses_received`).
- `spec/operator_ui_concept.md` — verify the Operations row
  tab order matches what 11F leaves in the chrome
  (`Validate / Previews / Invitations / Monitoring / Outbox`
  is the current shipped order; spec preview uses `Preview /
  Invitations / Monitoring / Outbox`). Tab-order reconciliation
  is a Segment 11C concern (it owns the Operations row sweep);
  flag it in 11C's plan rather than fix here.
