# Reviewer surface — functional + visual spec

Specification of the reviewer-facing app — the pages a signed-in
reviewer sees when they follow an invitation link or visit `/reviewer`
directly. The response surface (`/reviewer/sessions/{id}/{position}`)
is the page they spend ~all their time on; the dashboard
(`/reviewer`) and invitation-landing (`/reviewer/invite/{token}`)
exist to land them on it.

This spec rewrites the response surface around **multi-instrument
awareness**: the URL carries an explicit instrument segment, the page
renders one instrument at a time, and an action row at the top + bottom
of the surface carries every control — page-level (Save / Discard / Page
N) and review-level (Submit) — in one strip per side, separated by a
vertical divider. Single-instrument sessions are a degenerate case of
the same model.

Cross-references:

- `spec/visual_style_rrw.md` "Response form layout and instrument
  pacing" — the underlying principle (one page per instrument,
  tabular form, pacing via operator instrument design). This spec
  is the implementation contract for that principle on the live
  surface.
- `spec/visual_style_rrw.md` — top-bar / chrome conventions, banner
  family, status-icon classes.
- `spec/visual_style_general.md` — `.card` / `.btn` / `.pill` / form
  primitives.
- `spec/ui_elements.md` — canonical elements (P6 hover-by-fill, P7
  recovery-action color family).
- `spec/preview_hub.md` — operator-side preview entry-point spec; the
  preview page reuses this surface's template.
- `app/web/templates/reviewer/review_surface.html` — current
  implementation (single-form-multi-instrument-stack); this spec is
  the target.

---

## URL pattern

```
GET  /reviewer/sessions/{session_id}/{instrument_position}
POST /reviewer/sessions/{session_id}/{instrument_position}/save
POST /reviewer/sessions/{session_id}/submit
POST /reviewer/sessions/{session_id}/clear
```

`{instrument_position}` is the **1-indexed position** of the instrument
within the session (`Instrument.order`-sorted, then `Instrument.id`).
Position is preferred over the DB id because:

- It produces stable, predictable URLs for the reviewer (Page 1 / Page
  2 / …).
- The "Page N" framing in the UI matches the URL segment.
- Operators rarely reorder instruments after activation; if they do,
  bookmark URLs simply land on whichever instrument now sits at that
  position, which is reasonable behavior.

Single-instrument sessions still carry the segment: the only valid
position is `1`. `GET /reviewer/sessions/{id}` (no position) **303s to
`/reviewer/sessions/{id}/1`** so existing invitation links and dashboard
rows keep working.

Out-of-range positions (e.g. `/reviewer/sessions/5/9` when the session
has only 2 instruments) return **404**.

The reviewer dashboard at `/reviewer` always links each row to position
`1`, since the dashboard summarises the session as a whole and Page 1 is
a safe default landing.

**URL semantics across the four routes.**

- The GET route renders the **whole** surface — every instrument the
  reviewer has assignments on is delivered in one HTML response, with
  the instrument at `{position}` initially visible. Other instruments
  are hidden via CSS until the reviewer clicks a Page button (see
  "Form scope" below).
- The Save POST is **page-scoped** — `{position}` tells the route
  which instrument's response fields to persist. Inputs from other
  pages (which travel in the same form body) are ignored.
- The Submit POST is **session-wide** — no `{position}` segment;
  submits the whole review.
- The Clear POST is **session-wide** — no `{position}` segment;
  wipes everything.

---

## Page anatomy

Top-to-bottom, the page renders:

1. **Top bar (reviewer chrome variant)** — per
   `spec/visual_style_rrw.md` "Reviewer-facing pages → Top bar". "Review
   Robin" identity (no version, no breadcrumb), user menu with "Signed
   in as …" + optional "My Reviews" + "Sign out".
2. **Preview banner** — `body.ui-v2` only (operator preview mode
   reuses this template); rendered as `.banner.banner-info`.
3. **Page header** — `.rs-page-header` flex row carrying the session
   name as H1 plus the deadline inline as `.muted`. The deadline
   renders in the session's resolved zone followed by that zone's
   CLDR display name in parentheses — e.g. `Deadline: 2026-06-02
   07:59 (Australian Eastern Standard Time)` — with the raw IANA id
   as the fallback. (D7 — settled in Segment 11D PR C and adjusted
   post-merge.)
4. **Overview card** — a single full-width `.card.rs-status-panel`
   rolling together, top to bottom:
   - The session **description**, when `session.description` is set.
   - The transient **session-closed banner** — a
     `.banner.banner-warning` shown inline in the card when the
     session is no longer accepting responses; does not push other
     layout around.
   - **Per-page status pills** — one pill per instrument labelled
     e.g. `Page 1: in progress`, `Page 2: complete`. State computed
     server-side from response data (see "Per-page status" below).

   The card is omitted entirely only when there is neither a
   description nor any status pills. (Save / Submit no longer flash
   — the per-page status pills are the canonical signal — and the
   missing-required and invalid-value warnings render as their own
   full-width cards below, not inside this card.)
5. **Action row (top)** — `.rs-action-row.rs-action-row-top`,
   **left-aligned** so it reads as the lead-in to the form (the
   bottom action row is flush right — see §8). The surface's main
   control strip: one row carrying every action, page-level and
   review-level, in this left-to-right order:
   - `Save` (Primary) — persists the current page's dirty inputs.
     Greyed out (`disabled`) when the current page has no unsaved
     edits (see "Save button enabled state" below).
   - `Discard` (Secondary button, `type="button"`) — JS-resets the
     current page's inputs back to their server-saved values.
     Other pages' unsaved edits are untouched.
   - `Page #{N}: {Instrument.short_label}`, one button per
     instrument, Primary style. The label combines the position
     with the operator-set short label so the reviewer sees both
     ordering and context (e.g. `Page #1: Skills` /
     `Page #2: Cultural Fit`). When `short_label` isn't set
     (nullable column; default empty), the button falls back to
     bare `Page #{N}`. Each button is a JS-driven control
     (`type="button"`) — clicking it swaps the visible instrument
     group via CSS class toggle and updates the URL via
     `history.pushState(...)` so the address bar stays truthful
     and Back/Forward work; no server round-trip. The button for
     the current page renders disabled (`aria-disabled="true"`).
   - **Vertical divider** — a `.rs-action-divider` element separating
     the page-level controls (Save / Discard / Page N) from the
     review-level Submit. 1px wide, full button-height,
     `border-default` colored, with horizontal margin to give the
     Submit button breathing room. Hidden when Submit isn't
     rendered (e.g. read-only or operator-preview mode).
   - `Submit` (Primary) — review-session-wide. Commits every saved
     response across every instrument and stamps `submitted_at` on
     every assignment. Sits at the rightmost edge of the row so
     "I'm done" is the visually terminal action. (See "Form scope"
     below.)
6. **Instrument body** — heading, help-text card(s), reviewer table.
   Exactly one instrument's content renders per page.
7. **Missing-required warning card** — `.rs-missing-card`, full-width
   below the overview card, two-column flow. Renders only after a
   blocked Submit attempt; enumerates gaps as `Page N: Reviewee X —
   field Y`. Submit is a **hard gate** (no acknowledge-and-submit-
   anyway path); the reviewer fills the gaps and resubmits.
   `data-rs-errors-card` (same chrome) surfaces server-side numeric
   validation rejections, with the typed value preserved in the
   originating input so the reviewer can correct in place.
8. **Action row (bottom)** — `.rs-action-row`, flush right. Mirrors
   the top action row's buttons, order, and divider exactly; it is
   flush right rather than left-aligned (§5) so it reads as a
   trailing control strip. The repetition lets the reviewer act
   without scrolling back to either end of the table.
9. **Danger zone** — `.card.danger-zone.rs-danger-zone` with the
   Clear-all-responses form. Half-width, flush right, 24px above the
   foot. Review-session-wide; wipes every response across all
   instruments. Only when `any_accepting and not preview_mode`.

Mental model: instruments are **chapters of one review session**, not
standalone editing surfaces. The reviewer fills each page (saving
when they like), then **Submit commits the whole review** in one
action. "Page actions" (Save / Discard / Page buttons) act on the
current page; "Review-level actions" (Submit / Clear all) act on the
entire session. Page navigation is a client-side concern that
preserves in-progress edits across pages so the reviewer can move
freely without losing work; persistence to the database happens only
on explicit Save or Submit.

### How the surface works

The server renders **every instrument the reviewer has assignments
on** in one HTML response. All instrument groups live in the DOM
simultaneously; CSS hides every group except the one matching the
URL position. Clicking a Page button:

1. Toggles the `.rs-active` class so the chosen instrument's group
   becomes visible and the rest hide.
2. Calls `history.pushState(...)` to update the address bar to
   `/reviewer/sessions/{id}/{n}` — bookmarkable, Back/Forward work,
   but no HTTP request.
3. Updates the disabled state on Page / Save / etc. buttons to
   reflect the new "current page".

Because hidden instrument groups stay in the DOM, a reviewer's
typed-but-not-saved values **persist as the reviewer moves between
pages**. They aren't sent to the server until Save or Submit fires.
Refresh / browser-close / window-close still loses them — the
`beforeunload` warning (deferred; see "Designed-for-extensibility")
guards that gap.

### Save / Discard / Page navigation / Submit / Clear all

| Button | Scope | HTTP | Behavior |
|---|---|---|---|
| **Save** | Page | POST `…/{position}/save` | Persist the **current page's** dirty inputs to the database. The form body carries inputs from every page (since they all live in the DOM); the route filters by `{position}` and ignores inputs that don't belong to that page's instrument. Greys out when the current page has no dirty inputs. On success: 303 → `…/{position}` (no flash; the page-status pill in the overview card is the canonical save indicator). On invalid numeric value: re-render with the `data-rs-errors-card` warning card and the typed value preserved in the input. |
| **Discard** | Page | none — JS only | Reset every input on the current page to its **server-saved value** (a per-input baseline that the server renders into the page; the JS handler reads it and writes it back on click). No HTTP request, no database write, no audit. Other pages' unsaved edits are untouched. |
| **Page N** | Page | none — JS only | Swap which instrument group is visible (CSS class toggle); update the URL via `pushState`. No HTTP request. Reviewer's typed-but-not-saved values on the previously-visible page stay in the DOM. The button for the current page is disabled. |
| **Submit** | Review-session | POST `/reviewer/sessions/{id}/submit` | First persist the dirty inputs across **every** page (an implicit save of the whole review), then validate required fields across every instrument and stamp `submitted_at` on every assignment in the session. Submit is a **hard gate** on missing required (no acknowledge-and-submit-anyway path): on missing-required, 400 + re-render the surface with the full-width `.rs-missing-card` enumerating gaps. On invalid numeric value: 400 + re-render with the `data-rs-errors-card` (validation gate fires before missing-required). On success: 303 → `…/{position}` (no flash; the per-page pill flips to `submitted` and the per-row submitted-timestamp surfaces in the status column). |
| **Clear all** | Review-session | POST `/reviewer/sessions/{id}/clear` | Wipe every response across every instrument (confirmation checkbox required). Clears any submitted state. Lives in the half-width-flush-right Danger Zone card at the foot of the surface, not in the action rows. |

### Why Submit is session-wide

Conceptually a review is one document spread across multiple pages.
Per-page submit would require the reviewer to remember to submit
each page individually, which invites missed submissions. The single
review-session-wide Submit affordance — surfaced at the top *and*
bottom of every page — makes "I'm done" a single click no matter
which page the reviewer is on. Submit also implicit-saves every
dirty input across every page first, so unsaved work is never lost
to a Submit click.

### Save button enabled state

The Save button reflects whether the current page has unsaved edits:

- On initial page load: `disabled`. No inputs are dirty yet.
- On the first input event in any input belonging to the current
  page's instrument: enable.
- On Save success (303 round-trip): the page is re-rendered, every
  input matches its saved value, the button is `disabled` again.
- When the reviewer switches to a different page (Page N click): the
  Save button's enabled state recomputes for the new current page —
  enabled iff any input in the new page's instrument is dirty.

JS implementation: a per-page dirty flag, recomputed on `input`
events and on Page button clicks. The same dirty-tracking feeds the
deferred `beforeunload` warning (see "Designed-for-extensibility").

### Form HTML mechanics

The whole editing surface lives inside a single `<form>` whose
default `action` is `…/{position}/save` and `method="post"`. Save
submits to that default action; Submit overrides via
`formaction="/reviewer/sessions/{id}/submit"`. Both buttons send
the **entire** form body — every input across every instrument
group, since they're all in the DOM. The route distinguishes:

- Save filters the incoming form to inputs whose `name` matches
  response fields belonging to `{position}`'s instrument and
  persists those, ignoring everything else.
- Submit accepts the entire form body, persists every value, then
  applies the session-wide submission semantics.

### Persistence semantics

- **Save** upserts `Response` rows in `(assignment_id,
  response_field_id)` shape. An empty submitted value **deletes**
  the matching `Response` row (so absence == empty answer); a
  non-empty value upserts. Save never touches `submitted_at`. The
  filter-by-position keeps Save from accidentally touching another
  page's saved values when only the current page should change.
- **Submit** persists pending writes session-wide (treating the
  whole form body as a session-wide save), then validates required
  fields across every instrument. With acknowledge (or no missing
  required), it stamps `submitted_at` on every Response row in the
  session and writes a `responses.submitted` audit event. Editing a
  previously-submitted required field to empty deletes its
  `Response` row (including the `submitted_at` stamp), which flips
  the dashboard pill back to `in progress` on next render — no
  per-row resubmit required.
- **Clear all** deletes every `Response` row for this reviewer in
  this session, across every instrument. No partial undo. Writes a
  `responses.cleared` audit event.
- **Discard** is JS-only — no DB write, no audit. Resets the
  current page's inputs to the server-rendered baseline.

**"Submitted" status on the dashboard.** Once Submit succeeds, every
assignment in the session has `submitted_at` set. The dashboard's
session-level pill ("submitted" / "in progress" / "not started")
follows the same rule it does today (every assignment submitted →
"submitted"). With session-wide Submit, the rollup is always
all-or-nothing rather than "submitted on some pages but not others".

---

## Per-page status

The overview card renders one status pill per instrument,
positioned immediately above any transient flash banners that may
land. Status is computed **server-side from saved response data**;
client-side dirty edits don't shift a pill until the reviewer
clicks Save (and the page re-renders).

| Pill state | Pill class | Condition |
|---|---|---|
| `not started` | `.pill.pill-empty` | No saved Response rows for any of this page's assignments. |
| `in progress` | `.pill.pill-warning` | Some Response rows saved, but at least one required field empty across this page's assignments. |
| `complete` | `.pill.pill-success` | Every required field on every assignment in this page has a saved value. |
| `submitted` | `.pill.pill-success` | Every assignment in this page has `submitted_at` set (i.e. the session has been submitted; all pages flip together). |

Pill copy: `Page #1: in progress`, `Page #2: complete`, etc.
Single-instrument sessions still show one pill (`Page #1: …`),
since the overview card renders whenever there are status pills. Pill copy uses bare
`Page #{N}` rather than `Page #{N}: {short_label}` to keep the
panel compact — short labels live on the Page button labels and
on the per-instrument H2 above each table, where the reviewer
needs them to navigate or orient.

The route threads a `page_statuses: list[PageStatus]` into context
(`PageStatus = {position: int, label: str, state: Literal[…]}`),
populated for every instrument regardless of how many there are. The
template iterates and renders one pill per entry.

---

## Per-instrument table

Each page renders **one tabular response artifact** for the current
instrument: every assignment the reviewer has on that instrument is
one row, with response fields as columns. Wrapped in
`.table-scroll` so very wide instruments scroll horizontally instead
of forcing the surrounding layout to grow.

Reviewer-table rows use a **tighter vertical cell padding** than the
standard v2 table — half the global row gap, same horizontal
padding — since the table is one input per cell and can run to
hundreds of reviewees, so the denser rows keep vertical scrolling
down. The rule is scoped to the reviewer surface; operator tables
keep the standard spacing.

### Above the table — heading + help block

The per-instrument heading is a `.rs-instrument-heading` flex row
carrying a title (H2) and an optional subtitle on the same baseline,
styled like the page header (H1 + deadline). Title and subtitle
content comes from `Instrument.short_label` and
`Instrument.description` respectively, with composition rules driven
by how many instruments the reviewer is assigned on:

| Case | Title (H2) | Subtitle (`.muted`, body-weight) |
|---|---|---|
| Multi-instrument, `short_label` set | `Page #{N}: {short_label}` | `description` if set, else nothing |
| Multi-instrument, `short_label` empty | `Page #{N}` (bare) | `description` if set, else nothing |
| Single-instrument, `short_label` set | `{short_label}` (no `Page #1:` prefix) | `description` if set, else nothing |
| Single-instrument, both empty | none — no heading row renders | n/a |
| Single-instrument, only `description` set | none — no heading row renders | n/a (description shown elsewhere) |

The `Page #{N}` prefix is the safety-net default for multi-instrument
sessions: even with `short_label` unset, the reviewer still gets
"which page am I on" context. Single-instrument sessions don't need
the `Page #1` prefix; the H1 (session name) at the top of the surface
already establishes "this is the review."

The view-shape returned by `_surface_context` exposes a structured
heading dict per instrument group:

```python
@dataclass(frozen=True)
class InstrumentHeading:
    title: str | None      # rendered as <h2>; absent when None
    subtitle: str | None   # rendered as a body-weight muted span; absent when None
```

The template renders the row only when `heading.title` is truthy.

- **Help block** above the table (below the heading row), listing each
  response field that has both `help_text` set and
  `help_text_visible=true`. Two variants:
  - Multiple visible help items → `.rs-help-grid` (responsive grid
    of `.rs-help-card` items).
  - Exactly one visible help item → `.rs-help-card.rs-help-card-solo`
    (full-width single-card variant).

Single-instrument sessions with both `short_label` and `description`
empty render no H2 at all (regression-tested; see
`test_surface_single_instrument_no_description_renders_no_heading`,
which gets renamed once the multi-instrument-rewrite PR γ adds the
`instrument_heading(...)` helper).

### Columns

In rendered order:

1. **Reviewee** (always first, mandatory; class `.rs-reviewee`):
   reviewee `name` in **bold**, `email_or_identifier` in `<code>`
   beneath. Both are sourced from the `Reviewee` row pointed at by
   the assignment.
2. **Display fields** (in operator-configured `InstrumentDisplayField.order`):
   one column per visible row in `display_fields_by_instrument`.
   Filtered to exclude duplicates of the always-rendered Reviewee
   identity column (i.e. `reviewee.name` /
   `reviewee.email_or_identifier` display fields are suppressed even
   if the operator added them, because they'd duplicate column 1).
   Each cell renders per the field's source:
   - `reviewee.profile_link` → `<a href="{value}">View</a>` when the
     value is non-empty; empty otherwise (no broken anchor).
   - `pair_context.{n}` and the rest → plain text.
   Header carries `class="rs-narrow"` for `profile_link` (URL
   columns are kept narrow); other display headers have no width
   modifier.
3. **Response fields** (in stored `InstrumentResponseField.order`):
   one column per response field. Header text is the field label;
   required fields get a trailing `*`. Header column-width hint is
   driven by the field's RTD `data_type`:
   - `Integer` / `Decimal` → `class="rs-narrow"` (numbers are short).
   - `String` with `validation.max_length > 100` → `class="rs-textlong"`.
   - everything else → no width modifier.
4. **Status indicator** (trailing, narrow): only renders when
   `group.show_status_col` is true (i.e. when at least one row has
   `submitted_at` set or `show_acknowledge` is true after a
   missing-required Submit attempt). Cell content:
   - `<span class="status-icon-complete" title="Complete">✓</span>`
     when the row's required fields are all filled.
   - `<span class="status-icon-incomplete" title="N required field
     missing">⚠</span>` when any required field is empty.
   - Plus a small `.muted` line below the icon: `submitted YYYY-MM-DD HH:MM`
     when `submitted_at` is set.

### Cell renderers

Response field input markup is driven by the RTD's `data_type`
(per Slice 4a; pre-Slice-4a code branched on legacy literal type
names):

| `data_type` | Render |
|---|---|
| `String` with `validation.max_length > 100` | `<textarea rows="2">` (with `min-height: 44px`); preserves stored value. |
| `String` with `validation.max_length ≤ 100` | `<input type="text">`; the `maxlength` attribute reflects `validation.max_length`. |
| `Integer`, `Decimal` | `<input type="number">`; `min` / `max` / `step` reflect `validation`. |
| `List` | `<select>` over `validation.choices`, with an empty leading option (`value=""`) representing "no answer". |
| anything else | `<input type="text">` (defensive fallback). |

When the assignment isn't accepting (deadline closed or operator-
paused), every input renders `disabled`.

Stored values are read from `Response` rows keyed by
`(assignment_id, response_field_id)` and rendered as the input's
`value` (or selected `<option>` for `List`, or textarea body for the
long `String` variant).

### View shape

The route builds the table data in `_surface_context` (and its
operator-side mirror `build_preview_context`) as
`instrument_groups: list[InstrumentGroup]` where each group has:

```python
{
  "instrument": Instrument,
  "heading": str,
  "rows": [
    {
      "assignment": Assignment,
      "cells": [{"field": InstrumentResponseField, "value": str}, …],
      "display_cells": [{"field": …, "label": …, "value": …, "is_profile_link": bool}, …],
      "is_complete": bool,
      "missing_count": int,
      "submitted_at": datetime | None,
      "accepting": bool,
      "show_values": bool,
    },
    …
  ],
  "help_block_items": [InstrumentResponseField, …],
  "display_fields": [{"field": …, "label": …, "is_profile_link": bool}, …],
  "show_status_col": bool,
}
```

Keep this dict shape stable — the large-table ergonomics work
(see "Large-table ergonomics" below) builds on the same
payload, and it would also feed a future JS-driven grid
unchanged should one ever be adopted.

---

## Missing required flow

Submit is a **hard gate** on missing required, session-wide. There is
no acknowledge-and-submit-anyway path; the reviewer must fill (or the
operator must loosen the `required` constraint on) every required
field before the submit lands.

1. Reviewer hits Submit on any page with at least one required field
   blank anywhere in the session.
2. Server returns 400 + re-renders the page they were on (whichever
   `{position}` they submitted from) with the full-width
   `.rs-missing-card` below the overview card, enumerating the gaps as
   `Page N: Reviewee X — field Y` so the reviewer knows where to
   navigate.
3. The reviewer fills the gaps (using the per-page navigation
   to reach each one) and re-clicks Submit. There is no checkbox,
   no `show_acknowledge` template flag, and no
   `acknowledged_missing` audit detail.

The card carries a Cancel link back to the originating instrument
page so the reviewer can also dismiss the warning without scrolling
through the form (URL bar leaves the POST-only `/submit` endpoint
behind).

---

## Lifecycle gating

A reviewer can only mutate state (Save / Submit / Clear) when **all
three** of the following hold:

1. `ReviewSession.status == "ready"` (operator has activated the
   session).
2. The assignment's `Instrument.accepting_responses == true` (the
   per-instrument acceptance switch hasn't been turned off).
3. `now() < ReviewSession.deadline` (deadline hasn't passed; null
   deadline counts as open).

Failing any of those three returns **HTTP 403** on Save / Submit /
Clear POSTs.

GET requests don't 403 — the page still renders so the reviewer can
read prior state. When the gate is closed, the editing surface
degrades to read-only:

- Every input renders `disabled`.
- In both action rows: Save / Discard / Submit hide, plus the
  vertical divider that separated them. The Page N buttons stay so
  the reviewer can walk through their other instruments (which may
  or may not also be closed).
- The Danger Zone card hides (no Clear all).
- A `.banner.banner-warning` lands inline in the overview card
  explaining the state, e.g. "This session is no longer accepting
  responses." Two variants depending on the operator's per-
  instrument visibility flag:
  - "Your previously saved values remain visible below in read-only
    form." (operator left `responses_visible_when_closed=true`).
  - "Your previously saved values are hidden by the operator's
    visibility setting." (operator set `responses_visible_when_closed=false`).

### Lazy deadline-close

Deadline expiration is observed lazily, not via a scheduled job.
Every reviewer GET / POST and every operator instruments-page GET
runs `lifecycle.observe_deadline(...)` before reading state. The
first observer past the deadline:

- Flips `Instrument.accepting_responses` to `false` on every
  instrument in the session.
- Stamps `Instrument.deadline_closed_at = now()`.
- Emits one `instrument.closed` audit event per instrument with
  `detail.reason = "deadline"`.

The lazy-close is idempotent — subsequent observers see
`deadline_closed_at` already set and skip the side-effect.

---

## Identity matching

A signed-in user is matched to `Reviewer` rows by **case-insensitive
email equality** (`casefold()` both sides). Only `Reviewer` rows
with `status == "active"` grant access; inactive / removed reviewers
are invisible.

Both rules live in `app/services/responses.py` (and the per-session
lookup that drives the surface route). The reviewer dashboard, the
session surface, and the invitation-landing email-match check all
use the same rule.

A user can have at most one active `Reviewer` row per session. A
session can have multiple reviewers, each tied to a distinct user.

---

## Operator preview mode

The Previews-hub surface card at `/operator/sessions/{id}/previews`
(Segment 11F PR C) renders this template into an iframe `srcdoc`
via `build_preview_context`. The legacy standalone
`/operator/sessions/{id}/preview` (singular) is a permanent (308)
redirect to `/previews#reviewer-surface` and no longer renders the
template directly. In preview mode:

- The chrome `top_bar` block calls `super()` so the operator chrome
  (with breadcrumb back to the session) renders instead of the
  reviewer top bar variant.
- `body_class` drops the `reviewer` modifier (stays `body.ui-v2`).
- The preview-mode banner (`.banner.banner-info`) renders at the top
  of the body: "**Preview** — not visible to reviewers. This page
  is operator-only and bypasses session-status / deadline /
  acceptance gates."
- The reviewer write-path forms are suppressed (no Save / Submit /
  Discard / Clear). The `<form>` wrapper is replaced by a plain
  `<div>` so no `formaction=` can re-target a write endpoint. The
  Page N buttons still render in their slot so the operator can
  walk through every instrument to verify setup — clicking them
  toggles visibility client-side exactly as on the reviewer
  surface. With Save / Discard / Submit gone, both action rows
  collapse to just the Page N buttons (no vertical divider, since
  there's nothing to separate). Danger zone doesn't render.
- Inputs render disabled.
- The overview card renders without the per-page status
  pills (preview is read-only and synthetic; per-page state is
  moot).
- **Synthetic-row padding.** Up to three real assignments render
  first (sorted by `Assignment.id` ascending). When there are fewer
  than three, the table is padded with synthetic placeholders
  (`Sample Reviewee 1/2/3` / `sample{n}@example.edu` / per-source
  sample values) so the operator always has something to look at.
  Synthetic rows expose only the attributes the template actually
  reads (`assignment.id` negative to avoid colliding with real
  autoincrement ids; `reviewee.name` / `email_or_identifier`); a
  unit test guards the exposed shape against silent
  AttributeErrors when a future template edit adds a new attribute
  reference.
- **Read-only side-effects.** The preview GET emits no audit
  events and **does not** call
  `lifecycle.observe_deadline(...)` — opening a preview must never
  flip `accepting_responses=false` even if the session deadline
  has lapsed.

The Previews-hub surface card lives at
`/operator/sessions/{id}/previews?reviewer_email=…#reviewer-surface`
(Segment 11F PR C). The picker-selected reviewer is the only state
the URL carries; Page #N navigation inside the iframe runs through
the existing reviewer-surface page-toggle JS (the iframe's
`sandbox="allow-scripts"` keeps it alive). The retired
`/preview` (singular) 308-redirects there for bookmarks /
external links.

---

## Dashboard (`/reviewer`)

The reviewer's lobby — where they land when signing in directly
(without an invitation token) or clicking "My Reviews" from the
chrome on a session surface. Lists every session the signed-in user
is an active reviewer on, with a per-session progress pill.

- **H1** — "Your reviews".
- **Body** — single `.card` containing a `<table>` (one row per
  session). Columns:
  - **Session** — `<a>` to `/reviewer/sessions/{id}/1` (always
    lands on Page 1; the surface itself handles which page is
    "current").
  - **Deadline** — the canonical `YYYY-MM-DD HH:MM` timestamp in
    that session's own resolved zone, followed by the zone's CLDR
    display name in parentheses (raw IANA id as fallback); or
    `<span class="muted">—</span>` when null.
  - **Status** — pill (`not started` / `in progress` /
    `submitted`) computed from the reviewer's `Response` rows; plus
    a muted `(completed_rows / total_assignments)` count alongside.
- **Empty state** — when the user has no active reviewer rows in
  any session: a single `.card` with `.muted` text "You have no
  pending reviews ({user.email})."

### Pill state machine

Computed by `app/services/responses.py::session_pill_for_reviewer`:

| Pill | `pill-success` / `pill-warning` / `pill-info` | Condition |
|---|---|---|
| `submitted` | `pill-success` | Every required field on every assignment in the session has a `Response.submitted_at` timestamp. |
| `in progress` | `pill-warning` | At least one `Response` row exists, but the `submitted` rule doesn't hold. |
| `not started` | `pill-info` | No `Response` rows exist for this reviewer in this session. |

The "Edit / Re-submit" affordance lives on the surface itself —
hitting Submit once doesn't lock the form. Submitting again replays
the same logic and re-stamps `submitted_at`.

---

## Invitation landing (`/reviewer/invite/{token}`)

Token redemption + identity check. Lookup is by SHA-256 hash; the
raw token is never persisted, only mailed.

Behaviour:

1. Easy Auth must be signed in (otherwise the platform redirects to
   sign-in and back).
2. Look up the invitation by `sha256(token)`. Not found → **404**.
3. **Email match check** — case-insensitive comparison of the
   signed-in email (`casefold()`) against `Invitation.reviewer_email`.
   On mismatch, render `invite_mismatch.html` (HTTP 403; see
   "Invitation-mismatch page" below).
4. On match, stamp `Invitation.opened_at` once (idempotent on
   subsequent visits — only the first call writes), emit one
   `invitation.opened` audit event on first open, and 303 →
   `/reviewer/sessions/{id}/1`.

### Invitation-mismatch page

A single `.banner.banner-warning` explaining the email mismatch,
followed by a `.btn-pair` with two Secondary anchors:

- **Sign-in details** → `/me/debug` (so the reviewer can confirm
  which account they're signed in as).
- **Your reviewer dashboard** → `/reviewer`.

The remedy is to sign out and sign back in with the invited
account. This is the only reviewer-side page that returns a non-200
status under normal flow (HTTP 403).

The mismatch page renders with the reviewer chrome variant
(`body.ui-v2 reviewer`) so the operator's identity is suppressed
from the top bar.

---

## Button labels

| Where | Old label | New label |
|---|---|---|
| Action row (page-level slot) | `Save draft` | `Save` |
| Action row (page-level slot) | `Cancel — discard unsaved edits` | `Discard` |
| Action row (page-level slot) | n/a | `Page #{N}: {Instrument.short_label}` when the operator has set a short label; bare `Page #{N}` otherwise |
| Action row (review-level slot, after divider) | `Submit` | `Submit` (unchanged) |
| Danger Zone | `Clear all` | `Clear all` (unchanged; copy explains "every response across every page") |

Other labels (`Sign out`, `My Reviews`) are unchanged.

### Friendly short label vs. long description

The operator authors **two distinct strings** per instrument, both
optional:

- **`Instrument.short_label`** (`String(32) | None`, nullable) — the
  operator's reviewer-facing framing. Lands on Page button labels
  (`Page #{N}: {short_label}`) and as the per-instrument H2 title.
  Capped at 32 characters at the schema layer so button rows don't
  wrap on typical viewports.
- **`Instrument.description`** (`String(2000) | None`, nullable —
  unchanged from today) — the longer per-instrument blurb. Lands
  as the subtitle next to the H2 title above each table.

The system handle `Instrument.name` (`String(255)`, auto-generated
as `instrument_N` on instrument create) is **not** reviewer-facing.
It carries audit-event copy and is otherwise invisible.

The 32-char ceiling on `short_label` is a **Setup-side concern** —
this surface trusts the value it's given. The Instruments Setup
page enforces it at create / edit time (see
`guide/archive/segment_11L_instrument_short_label.md` for the single-PR
plan that adds the column + Setup-side editor). The reviewer
surface still ships a defensive
`max-width: 16em; text-overflow: ellipsis` rule on Page buttons
as belt-and-suspenders against pre-existing oddities.

---

## Out of scope

The following are deliberately deferred. They are not implemented
today but the surface is designed so they can be added later without
re-architecting; see "Designed-for-extensibility" below.

- **`beforeunload` warning** when the form is dirty.
- **Standalone submission-confirmation page** ("thank you" surface).
  Today the post-submit signal is the per-page `submitted` pill in
  the overview card and the per-row submitted-timestamp in
  the status column.
- **Large-table ergonomics** (cell autosave, sticky headers,
  return-to-place, visible progress, filter-to-incomplete) —
  Segment 17B, as targeted progressive enhancement. A wholesale
  JS data-grid swap (AG Grid or equivalent) is *not* planned —
  judged overkill; recorded as an aspirational possibility in
  `guide/future_possibilities.md`. See "Large-table ergonomics"
  below.

---

## Designed-for-extensibility

Notes on how this surface keeps the three deferred features above
non-risky to add later. Each item lists the design call this spec
makes today + the small follow-on the deferred work needs.

### beforeunload warning

- **Today.** Clicking `Page N` or `Discard` doesn't lose unsaved
  edits — Page navigation is purely client-side and the dirty
  buffer survives, and Discard is an explicit "drop my edits"
  control. The remaining gap is **browser-close**, **tab-close**,
  **typing a new URL into the address bar**, and **clicking the
  chrome's `My Reviews` link** — any of these throw away the dirty
  buffer with no prompt.
- **Design call.** The editing form carries a stable id
  (`id="rs-form"` or similar). The same dirty-tracking that drives
  the Save button's enabled state (see "Save button enabled
  state") also feeds a future `beforeunload` listener: when the
  form is dirty, the listener prompts; when clean, it doesn't.
  Intentional-discard controls (`Discard` button + chrome
  `My Reviews` link) carry a `data-discards-edits` attribute the
  listener reads to skip the prompt; Page N buttons don't need
  the marker because they don't trigger a real navigation.
- **What lands later.** A small addition to the existing inline
  `<script>` block — adds a `beforeunload` handler to the dirty-
  tracking machinery already in place. No template restructuring
  needed.

### Standalone submission-confirmation page

- **Today.** `POST /reviewer/sessions/{id}/submit` 303s to
  `…/{position}` (no flash). The reviewer reads the post-submit
  signal off the per-page `submitted` pill in the overview card
  and the per-row submitted-timestamp in the status column.
- **Design call.** The submit route's redirect target is computed via
  a small helper (`submit_redirect_url(review_session, position)`)
  rather than inlined. Today the helper returns
  `f"/reviewer/sessions/{id}/{position}"`. Tomorrow it can return
  `f"/reviewer/sessions/{id}/submitted"` (session-level thank-you)
  without touching any other code path.
- **What lands later.** A new template (`reviewer/submitted.html` or
  similar) plus the helper change. The surface itself doesn't move.

### Large-table ergonomics

`spec/visual_style_rrw.md` "Response form layout and instrument
pacing → Large-table ergonomics" pins the following as first-class
requirements (since the app's positioning depends on tabular review
artifacts at scale): auto-save, return-to-place, visible progress,
sticky column headers, filter-to-incomplete, keyboard navigation,
and column-type ergonomics. **Segment 17B owns these**, pursued as
targeted progressive enhancement (debounced `fetch` to `POST /save`,
CSS `position: sticky`, small inline scripts) — *not* a JS
data-grid framework. A wholesale grid swap (AG Grid or equivalent)
was considered and taken off the roadmap as overkill; it is
recorded as an aspirational possibility in
`guide/future_possibilities.md`. Notes on how the surface stays
compatible either way:

- **Today.** Per-instrument rows render as a plain `<table>` inside
  `.table-scroll`. Column-width hint classes (`.rs-narrow` /
  `.rs-reviewee` / `.rs-textlong`) on `<th>` / `<td>` carry the
  responsive sizing. The data driving each row is built in
  `_surface_context` as a list of dicts with stable, serializable
  keys (`assignment`, `cells`, `display_cells`, `is_complete`,
  `missing_count`, `submitted_at`, `accepting`, `show_values`).
- **Design call.** Keep all table-specific markup confined to
  `review_surface.html`; route handlers and view-shape adapters never
  emit HTML. Field metadata (label / data_type / validation) ships
  alongside the row data, so the ergonomics work needs no route or
  view-adapter change — and the same payload would also feed a
  JS-driven grid unchanged, should one ever be adopted.
- **What lands later (Segment 17B).** The ergonomics arrive
  incrementally as progressive enhancement on the existing
  `<table>` — autosave wired to `POST /save`, `position: sticky`
  headers, a progress indicator, a filter-to-incomplete toggle —
  each a small independent PR. They are *not* treated as one
  all-or-nothing bundle gated on a grid library; that bundling was
  the AG-Grid framing, now off the roadmap.

---

## Migration notes

The URL change from `/reviewer/sessions/{id}` to
`/reviewer/sessions/{id}/{position}` is a breaking change for:

- **Existing invitation emails** — already-sent invitation emails
  embed the old token URL (`/reviewer/invite/{token}`), which redirects
  via `/reviewer/sessions/{id}` after Easy Auth resolves. The
  bare-session URL must 303 to `/reviewer/sessions/{id}/1` to keep old
  invitation links working.
- **Reviewer dashboard rows** — link generation in
  `reviewer/dashboard.html` updates to point at position `1`.
- **Bookmarks / returning reviewers** — same 303 covers them.

The 303 fallback covers all known callers; no data migration is
needed. The fanout fix shipped in PR #418 ensures that
multi-instrument sessions actually have multiple `instrument_groups`
visible to each reviewer, which is the precondition for the page
selector to render at all.
