# Operator UI concept

> **Status (2026-05-04):** PR 2 of 4 in the docs reorganisation. This file is a concatenation of the (still-live) `spec/ui_concept.md` and `spec/operator_map.md`, brought together for a consolidating revision pass.
>
> - **PR 2 (this commit):** concatenate, no revisions. Both originals remain authoritative until PR 4 retires them.
> - **PR 3:** revise this file for internal consistency and alignment with the higher-tier docs (`spec/audience_and_identity_model.md`, `spec/visual_style_general.md`).
> - **PR 4:** delete `spec/ui_concept.md` and `spec/operator_map.md`; sweep remaining cross-references to point here.

---

# Section A — From `spec/ui_concept.md`


> **Note (2026-05-03):** The chrome description and page taxonomy here
> overlap with `spec/visual_style_rrw.md` (chrome, status strip, page
> headers) and `spec/preview_hub.md` (which retires the "Preview Pages"
> grouping and adds Preview to Operations Pages). Those two files are
> now authoritative for the areas they cover. Where this file disagrees
> with either, the newer spec wins. A reconciliation pass is pending —
> this doc is slated to consolidate with `spec/operator_map.md` into
> `spec/operator_ui_concept.md`.

**Conceptual map of the operator-facing page surface.** Names the
groupings the page set falls into, the navigation principles that
govern movement between them, and the future-direction notes that
have been raised but not yet committed.

This is a level above `spec/operator_map.md` (which describes the
page-level chrome and affordances) and a level below
`spec/architecture.md` (which describes the domain model). When
the chrome (nav bar, breadcrumbs) or page set changes, this is
the first file to update — the chrome decisions in
`operator_map.md` follow from the page taxonomy here.

## Page taxonomy

The operator's pages fall into five active groupings plus one
forward-looking placeholder.

### 1. Operator's Overview

The **top level** for a signed-in operator. Lists every session
the operator has access to. The single launch point for everything
session-scoped — to do anything inside a session, the operator
clicks into it from here.

- `sessions_list.html` — `GET /operator/sessions`.

**Children of the Overview** (not session-scoped, but reached
from this page):

- `session_new.html` — `GET /operator/sessions/new` — the
  Create-Session form.

### 2. Per Session Home / Control Panel

Once an operator is **inside a session**, the Control Panel is
that session's home. It is the **launch point for lifecycle
transitions**, not a control centre for ongoing work.

- `session_detail.html` — `GET /operator/sessions/{id}`.

A session moves through a small, well-defined lifecycle: `draft`
→ `validated` → `ready` → `closed`. Most of the operator's time
is spent doing **phase work** — configuring setup, then
monitoring operations — on the phase pages where that work
belongs. But the **transitions between lifecycle states** are
session-level commits, not phase-level work: validating a setup
is the act of declaring setup done; activating is the act of
going live; closing is the act of ending the run. These belong
to the session itself, so they live on the session's Home page.

Home is therefore visited *at transitions*, not during phase
work. Phase work is decentralised across the phase pages;
lifecycle commits are centralised on Home.

#### What Home's body holds

- **Session identity** — name, code, deadline, lifecycle state.
- **The next transition action**, prominent and contextual to
  lifecycle state: Validate setup (`draft`) → Activate session
  (`validated`) → Close session (`ready`) → Reopen (`closed`).
  One primary button at a time.
- **Setup-readiness summary** — the existing setup-state badges,
  as the at-a-glance answer to *"is the next transition going to
  succeed?"*
- **Pointers into Operations** once running — terse status lines
  (e.g. *"12 invitations sent, 4 responses in"*) that link to
  the Operations pages, not live dashboards.
- **Sub-page links** — Edit Session, Validate detail view.

#### What Home's body does not hold

- Phase launchers in the body (the chrome does that).
- Live operational dashboards.
- Anything the operator would return to mid-phase.

The test for whether something belongs on Home: *is this a
lifecycle transition, or is it phase work?* Lifecycle transitions
belong on Home. Phase work belongs on the phase pages.

#### Sub-pages of Home

- `session_edit.html` — `GET /operator/sessions/{id}/edit` —
  edit form for session metadata (name, code, deadline). Reached
  from a link on Home.
- `session_validate.html` — `GET /operator/sessions/{id}/validate`
  — the read-only Validate detail view. Reached from a link on
  Home; the at-a-glance summary stays inline on Home itself.

### 3. Per Session Setup Pages

The five surfaces where the operator does the work needed to
make the session run properly. Each one has full edit affordance
while the session is `draft` / `validated`, and locks down once
the session is `ready` (yellow lock card pattern).

| Page | Template | URL |
|---|---|---|
| Reviewers | `session_reviewers.html` | `/sessions/{id}/reviewers` |
| Reviewees | `session_reviewees.html` | `/sessions/{id}/reviewees` |
| Assignments | `session_assignments.html` | `/sessions/{id}/assignments` |
| Instruments | `instruments_index.html` | `/sessions/{id}/instruments` |
| Email Template | `session_setupinvite.html` | `/sessions/{id}/setupinvite` |

Note: the URL slug `setupinvite` and the legacy in-code label
"Email Invites" predate the Setup Page / Operations Page split.
The settled name is **Email Template** — this page houses the
email-template editor (Segment 15 work, currently a stub). The
run-time invitation management lives in the Operations Page below.

### 4. Preview Pages

Read-only renderings spun off from one or other Setup Page,
showing what the configured setup will look like to its audience
(reviewers today; future reviewees or other audiences once they
exist).

Today there is one Preview Page:

- The **reviewer-surface preview** at
  `GET /operator/sessions/{id}/preview`, conceptually a child of
  the Instruments Setup Page (it renders what reviewers will see
  for the session's instruments). Reachable from Instruments.

The category is plural because additional Preview Pages are
anticipated (e.g. per-instrument preview integration is open per
`guide/instruments.md` Section D).

### 5. Per Session Operations Pages

Surfaces for running a session and intervening when needed —
sending invitations, monitoring progress, debugging email
delivery. Three pages:

| Page | Template | URL |
|---|---|---|
| Invitations | `session_invitations.html` | `/sessions/{id}/invitations` |
| Monitoring | `session_monitoring.html` | `/sessions/{id}/monitoring` |
| Outbox | `session_outbox.html` | `/sessions/{id}/outbox` |

Validation is *not* an Operations Page — the Validate detail
view is a sub-page of Home (the act of validating is a lifecycle
transition, not phase work).

**Outbox** is a per-session Operations Page **with system
powers** (read raw email-outbox rows, useful for debugging send
paths). Despite the "system" framing it is *not* a cross-session
admin surface — it's per-session. A future cross-session admin
surface would belong to the System Admin group below.

### 6. System Admin / System Setup Pages (placeholder)

A future grouping for **cross-session** admin (operator
permissioning, system-wide settings). Empty today; flagged here
so the taxonomy has a slot for it when the work surfaces. If a
cross-session admin page is added, it sits at the Operator's
Overview level (or above), not inside a session.

## Design principles

### P1 — One session at a time

The operator is always **inside exactly one session, or in the
Overview**. Session-scoped chrome never offers cross-session
navigation; to switch sessions, the operator returns to the
Overview.

### P2 — Both phases always reachable

Within a session, **Setup and Operations are both navigable
from the chrome on every session-scoped page**. The operator is
never required to traverse Home to switch phases.

### P3 — Home is the launch point for lifecycle transitions

Home is the session's **identity** and the place where
**lifecycle-advancing actions** live (Validate, Activate, Close,
Reopen). Phase work happens on the phase pages; Home is visited
*at transitions*, not during phase work.

### P4 — Lifecycle disables, never hides

Pages remain reachable across all session lifecycle states.
Affordances that don't apply to the current state render
disabled (yellow lock card pattern), not removed.

The four-line shape: two principles about *where the operator
can go* (P1, P2), one about *what Home is for* (P3), one about
*what stays reachable* (P4). None of them overlap.

## Navigation model

The chrome that implements the principles above. The page-level
implementation lives in `spec/operator_map.md`; the conceptual
contract is here.

### Chrome layout

A double-height **Home** anchor on the left, two rows of phase
tabs to its right:

```
┌────────┬─ Setup       [Reviewers][Reviewees][Assignments][Instruments][Email Template]
│  Home  │
└────────┴─ Operations  [Invitations][Monitoring][Outbox]
```

- **Home** is double-height to span both rows, signalling that
  it's one level up from the phase tabs rather than a peer of
  any of them. It carries the session's identity (name,
  lifecycle state) compactly, so the chrome itself answers
  *"which session am I in, and where in its life is it?"*
- **Row labels** (`Setup`, `Operations`) sit at the left edge
  of each row. Labels carry the row-identity job; colour tints
  can reinforce but shouldn't be the only signal.
- **Same tab shape across rows.** The labels and rows do the
  grouping work; tabs themselves don't need to differ in shape.
- **Active tab** uses a clear underline (or equivalent),
  independent of which row it's in. The marker uses one
  unified colour — the tab's row already carries the group
  identity; the marker just says *"you are here"*.

The exact tints and marker colour are an `operator_map.md`
concern; see that file for current values.

### Behaviour

- **From any phase page**, both rows are visible and any tab is
  one click away. No traversal through Home is required to
  switch phases — the operator works fluidly within and across
  Setup and Operations as phase work demands.
- **From Home**, the chrome renders the same way, with no tab
  active. The phase rows remain visible and clickable; Home's
  body is what's distinctive, not its chrome.
- **Lifecycle states don't hide pages.** Setup tabs remain
  visible and reachable when the session is `ready` or
  `closed`, but their pages render locked behind the yellow
  lock card. Operations tabs remain visible and reachable when
  the session is `draft` or `validated`, but their actions
  render disabled. The chrome is stable across the lifecycle;
  the page bodies adapt.

### Sub-pages and Preview

- **Sub-pages of Home** (Edit Session, Validate detail): chrome
  renders the two phase rows normally, with no tab active. The
  sub-page identifies itself in the page body.
- **Preview Pages** (child of a Setup page): chrome renders
  normally, with the parent Setup tab active. Preview is
  conceptually inside its parent.

### What the chrome does not do

- It doesn't carry **lifecycle-transition actions**. Validate,
  Activate, and Close are body-level actions on Home, not
  chrome buttons. Putting them in the chrome would make them
  reachable from every page, which contradicts the launch-point
  framing — transitions are deliberate acts the operator
  returns to Home for.
- It doesn't carry **cross-session navigation**. Switching
  sessions means returning to the Overview.
- It doesn't **change shape** based on lifecycle state or
  sysadmin mode. Stability matters; the operator should learn
  the chrome once.

## Out of scope / forward-looking notes

Recorded for visibility; **none are committed**. Capture
additional ideas here as they surface so the taxonomy doesn't
get redesigned to accommodate them later.

- **Central Control and Operations Panel** — a cross-session
  operator surface that aggregates run-state across all of an
  operator's sessions. Conceivable but ROI unclear, and P1
  ("one session at a time") is stronger when the whole app
  respects it. Not on any segment plan.
- **Adjacent capabilities likely to land sooner**: shared
  operator permissions on a session, session duplication (sans
  response data), shared setup data between sessions (e.g.
  reusable reviewer rosters or instrument templates), session
  tagging / grouping. These compose with the Overview surface —
  none would force a redesign of the Setup / Control /
  Operations groupings.
- **Operations row consolidation.** If a future iteration folds
  Invitations + Monitoring into a single page, the Operations
  row could shrink to one or two tabs. At which point the
  two-row chrome could collapse to a **single row** (Setup tabs
  only, with the residual Operations tab(s) appended). This is
  a possible future, not a plan.
- **Cross-session System Admin** — when added, sits at
  Operator's Overview level (or above), not inside a session.
  Implies its own chrome (different from the per-session
  two-row nav). Not a per-session Operations Page.

## Cross-references

- `spec/operator_map.md` — page-level chrome + per-page layout
  contracts. Reads downstream from this file.
- `spec/architecture.md` — domain entities + layering. Reads
  upstream of this file.
- `spec/functional_spec.md` — technology-neutral functional
  spec.
- `guide/instruments.md` — Section D (preview integration) —
  pending decision that will refine the Preview Pages section
  above.

---

# Section B — From `spec/operator_map.md`


> **Note (2026-05-03):** This file overlaps with three newer specs that
> are now authoritative for the areas they cover:
> - `spec/visual_style_general.md` and `spec/visual_style_rrw.md` —
>   chrome, status strip, lock card, button styles, page headers
>   (general visual vocabulary in the first; Review-Robin chrome
>   instantiation in the second).
> - `spec/preview_hub.md` — folds the standalone
>   `/operator/sessions/{id}/preview` page into a new Operations hub
>   at `/sessions/{id}/preview`.
> - `spec/quick_setup_card_spec.md` — new card on Session Home not yet
>   reflected in this file's Home layout.
>
> Where this file disagrees with any of them, the newer spec wins.
> A reconciliation pass is pending.

Specification of the operator-facing page surface. Most sections
describe what currently ships; placeholder sections explicitly call
out deferred work. For per-route detail with template paths, form
field schemas, and audit events, see `docs/status.md`'s operator URL
table. For the segment-by-segment implementation history, see
`docs/status.md`'s "Segments shipped" table. For the
reviewer-facing surface (dashboard, review surface, invitation
landing), see `spec/reviewer_map.md`.

## Cross-page conventions

Every page (operator and reviewer) renders the same chrome before
its body:

- **App identity (top left).** The text "Review Robin Web App
  (version {num})" rendered small (not large heading), as a link to
  `/about`. (Operators reach the sessions list via the breadcrumb,
  not via the app-identity text.)
- **User card (top right).** A small card with "Signed in as
  {user name}" and a **Sign out** button. The Sign out button posts /
  links to `/.auth/logout`.
- **Breadcrumb trail (top left, just below the app identity).**
  Reflects the page's position in the surface hierarchy. Each
  segment except the current page is a link to that ancestor page.
  The current page renders as a plain non-link label. Breadcrumbs
  replace per-page back-link buttons, so individual page specs
  below do not list a separate back link, and individual page specs
  do not list a separate Sign out control either.
  - **Operator root.** The operator's perceived home is the
    sessions list; breadcrumbs start at `Sessions` →
    `/operator/sessions`. On `/operator/sessions` itself, the trail
    is the single non-link label `Sessions`.
  - **Reviewer root.** The reviewer's perceived home is the list of
    sessions they are invited to (the page at `/reviewer`);
    breadcrumbs start at `Reviewer` → `/reviewer`. On `/reviewer`
    itself, the trail is the single non-link label `Reviewer`.
- **Page title.** The page's H1, rendered below the breadcrumb.

### Session top nav

Every session-scoped operator page (Home, Setup Pages, Operations
Pages, and their sub-pages) renders a **session top nav** at the
top of the page. The top nav implements the navigation model
spec'd in [`spec/ui_concept.md`](./ui_concept.md) "Navigation
model" — both phase rows (Setup, Operations) always visible, Home
as a double-height anchor on the left.

#### Layout

```
┌────────┬──────────┬──────────────────────────────────────────────────────────┐
│        │   Setup ▶│ [Reviewers][Reviewees][Assignments][Instruments][Email Template] │
│  HOME  ├──────────┼──────────────────────────────────────────────────────────┤
│        │  Ops ▶   │ [Invitations][Monitoring][Outbox]                        │
└────────┴──────────┴──────────────────────────────────────────────────────────┘
```

CSS grid (in `base.html`, class `.session-nav-grid`) with three
columns:

1. **Home anchor** — `minmax(180px, 220px)`, spans both rows. Blue
   tint (`#eff6ff`). Carries a small `HOME` caption + the session
   name (allowed to wrap to two lines via
   `-webkit-line-clamp: 2`). The session lifecycle is shown as the
   first pill in the status row below, **not** inside the anchor.
   `.session-home-anchor`.
2. **Row labels** — auto-width column. Both row-label cells share
   the same column track, so the column sizes to the wider label
   (`OPERATIONS`); inside each cell, text is right-aligned via
   `justify-content: flex-end` so the shorter `SETUP` label sits
   flush against the first tab. Each label is followed by a
   CSS-drawn right-pointing triangle (`::after` with `border-left`
   trick, sized in `em` so it matches cap-height) pointing toward
   the tabs. Default text colour `#9ca3af`; triangle colour
   `#cbd5e1`. `.row-label` + `.setup-row` / `.ops-row`.
3. **Tab strip** — `1fr` column. Each row of tabs gets a subtle
   group tint (`.tab-strip-setup` = grey `#f3f4f6`,
   `.tab-strip-ops` = light green `#f0fdf4`). Tabs (`.nav-tab`)
   are equal-width (`flex: 1 1 0`), text-only, padded `12px 14px`,
   colour `#4b5563`. Same shape across both rows.

The Setup row gets a 1px bottom border (via `.row-setup`) to
separate visually from the Operations row.

#### Active tab marker

The tab corresponding to the current page renders with:

- White background (`#fff`), overriding the row's tint.
- Bolder text (`font-weight: 500`) and the accent colour `#1e40af`.
- A short understated underline `4px` tall, inset `18px` from each
  edge so it doesn't span the full tab width. The colour is the
  CSS custom property `--tab-marker-color` (default `#93c5fd`,
  defined on `.session-nav-grid`); future variants can override
  the property to recolour the marker without redefining the
  rule.

Sub-pages of Home (Edit Session, Validate detail) render the nav
with **no tab active** — the home anchor visually owns the chrome
on those pages but doesn't get the tab-active treatment. Preview
Pages render with the **parent Setup tab active** (e.g. on
`/preview`, the Instruments tab is highlighted).

#### Active-group emphasis

The `SETUP ▶` / `OPERATIONS ▶` row label darkens to the
session-name colour (`#111827`) when:

- the operator is on a page in that group (the partial sets an
  `.active-group` class on the matching label based on
  `current_page`), or
- the mouse is hovering any tab in that group's strip (handled
  via `:has(.tab-strip-setup .nav-tab:hover)` /
  `:has(.tab-strip-ops .nav-tab:hover)` on the grid).

The same emphasised colour applies to the label text and its
triangle (the `::after` rule recolours `border-left-color`).

#### Status row

Below the nav grid, the partial `session_setup_status_row.html`
renders the at-a-glance session status. Same content on every
session-scoped page: lifecycle pill first, then the setup-todo
counts.

```
Session: DRAFT · Reviewers: 8 · Reviewees: 13 · Assignments: NONE · Instruments: 1 · Email Template: NOT SET UP
```

The whole nav grid + status row sit inside a `.session-nav-card`
wrapper (1px border, 8px radius). The page title is **not**
rendered as a separate `<h1>` — the active tab already names the
page; an additional title is redundant. (Sub-pages without an
active tab — Edit, Validate detail — name themselves in the page
body.)

#### Partials

- `operator/partials/session_top_nav.html` — the grid (Home anchor
  + row labels + both tab strips). Takes `current_page` (one of
  the 9 page names). Sub-pages of Home pass `"Home"`; Preview
  pages pass their parent Setup name.
- `operator/partials/session_setup_status_row.html` — the status
  row. Takes `session` and `status_pills`.

### "Session ongoing" yellow lock card

Whenever a session is `ready`, every page that exposes setup
mutations renders a yellow lock card just below the session top
nav + status row. The card explains that the page can't be edited
while the session is ongoing and offers a confirm-checkbox +
`Revert to draft` button that posts to
`POST /operator/sessions/{id}/revert`. The form includes a hidden
`return_to` field so the operator lands back on the same page
after the round-trip; the route allowlists `reviewers`,
`reviewees`, `assignments`, `instruments` (the session detail's
revert form omits the field and lands on session detail).

While the lock card is shown, each page is responsible for hiding
its own mutation affordances (upload cards, Danger Zone, Edit /
Save buttons) per the per-page specs below. The session-detail
lock card sits above the `.page-grid`.

Per P4 ("lifecycle disables, never hides") in
`spec/ui_concept.md`: the **tabs themselves stay clickable** in
every lifecycle state — operations tabs on a `draft` session,
setup tabs on a `ready` session. Lifecycle disabling lives inside
the destination page (yellow lock card + greyed buttons), not on
the chrome.

### Page layout — two-column option

For pages whose content naturally splits into two parallel groupings
(e.g. session detail's *Session Details + Run Session* alongside
*Session Setup*), the default layout is a two-column CSS grid via
`.page-grid` in `base.html`:

- Two equal-width columns (`grid-template-columns: 1fr 1fr`,
  `gap: 20px`, `align-items: stretch`) so the columns share the
  page's full width and end at the same vertical position.
- Cards are direct grid children, with explicit placement classes:
  `.card-tl` (col 1, row 1), `.card-r` (col 2, spanning rows 1-2),
  `.card-bl` (col 1, row 2). The right card spans both rows so its
  top and bottom are flush with the top of the top-left card and
  the bottom of the bottom-left card.
- DOM order is `tl` → `r` → `bl`, which is also the desired mobile
  stacking order. Below 800px viewport the grid collapses to a
  single column with `grid-row: auto`, and cards stack in DOM
  order — top-left card first, right card second, bottom-left card
  third.
- For pages that also need a *bottom row* of paired cards
  (e.g. context-sensitive message stack on the left, a pinned
  danger zone on the right), use the companion `.bottom-grid`
  pattern after the `.page-grid`:
  - `.bottom-grid` is a 2-column grid (`1fr 1fr`, 20px gap) with
    `align-items: start` so each side keeps its natural height
    (no stretch to match the taller column).
  - Inside the left column, wrap stacking cards in
    `.bottom-left` (a vertical flex stack with 20px gap).
  - The right column holds the persistent card (e.g. danger
    zone) directly.
  - On mobile (≤800px), the bottom grid collapses to a single
    column; cards stack in DOM order — message cards first,
    danger zone last.

This is one valid default; pages whose body is a single linear flow
(forms, list/detail tables) keep their existing single-column
layout.

## `/operator/sessions` — Sessions list

- Table of sessions, one row per session. Columns: **Name**,
  **Code**, **Status**, **Deadline**, **Created**, **Created by**,
  plus two per-row buttons that hug the right edge via `.col-shrink`:
  - **Access** — replaces the previous Name link; opens the session
    detail.
  - **Delete**
- Below the table:
  - **Create new session** button.

## `/operator/sessions/{id}` — Session detail

Lays out three primary cards in a `.page-grid` (Session Details
top-left, Session Setup right-spans-two-rows, Run Session
bottom-left), with Danger Zone in a separate `.bottom-grid` below.
The yellow lock card sits above the `.page-grid` when the session
is `ready`. The session-detail lock card omits `return_to` and
lands on session detail. While locked, the Run Session card's
buttons stay visible (the session is meant to be running).

- **Session Details** card (top-left, `.card-tl`): deadline, **Created
  by**, description, and a status pill (`draft` / `validated` /
  `ready`) on a `.session-status-row`. The right side of that row
  carries an **Edit** button (Primary Outline) → `…/edit`. The
  inline revert form is gone — when `ready`, the yellow lock card
  above the page-grid replaces it.
- **Session Setup** card (right column, `.card-r`): a 4-column
  `.setup-grid` with one row per setup surface. Each row is a CTA
  Manage button (`.btn-cta`) on the left and the surface's current
  state on the right. Rows, in DOM order:
  - **Reviewers** → `/operator/sessions/{id}/reviewers`.
  - **Reviewees** → `/operator/sessions/{id}/reviewees`.
  - **Assignments** → `/operator/sessions/{id}/assignments`.
  - **Instruments** → `/operator/sessions/{id}/instruments`.
  - **Email Invites** → `/operator/sessions/{id}/setupinvite`.

  Manage CTAs render as `.btn-cta.disabled` with a tooltip
  explaining why when a surface isn't actionable yet. View-shape
  for the rows is built in `app/web/views.py:build_setup_rows`.
- **Run Session** card (bottom-left, `.card-bl`): a 4-up
  `.btn-row` of CTA buttons:
  - **Validate Session Setup** → `/operator/sessions/{id}?validated=1`.
    Re-runs setup validation server-side and surfaces an inline
    summary card on the session detail (error / warning / info
    counts plus the activate-readiness verdict). The summary card
    includes a **View detailed validation** link →
    `/operator/sessions/{id}/validate` for the full per-issue
    breakdown.
  - **Preview Reviewer Surface** → `/operator/sessions/{id}/preview`
    (operator-only read-only render of what reviewers will see;
    bypasses session-status / deadline / acceptance gates). This
    is the **only** working preview entry point — the same-named
    button on the Instruments page is currently disabled.
  - **Manage Invitations** → `/operator/sessions/{id}/invitations`.
  - **Extract Data** — disabled until Segment 12.
- **Danger Zone** card (in `.bottom-grid`):
  - **Delete Data** button — wipes collected response data only;
    setup items (reviewers, reviewees, instruments, assignments,
    invitations) stay.
  - **Delete Session** button — removes everything for the session.

## `/operator/sessions/new` — Create new session

Single-page form. No setup nav (the session doesn't exist yet);
breadcrumb reads `Sessions → Create New Session`.

- **Two-column form** in a `.page-grid`:
  - **Left column** (`.card-tl` slot, plain `<div>`): Name
    (required, max 255), Code (required, max 64; unique per
    operator), Deadline (optional, `datetime-local`).
  - **Right column** (`.fill-col`): Description textarea
    (optional, max 2000), grows to fill column height.
- **Action row** (`.btn-pair` below the grid): **Create
  session** (Primary) submits to `POST /operator/sessions` →
  inserts the session + a `SessionOperator` row + a
  `session.created` audit event + 303 to `/operator/sessions/{id}`.
  **Cancel** (Primary Outline) → `/operator/sessions`.

## `/operator/sessions/{id}/edit` — Edit session

Same shape as the create form, with pre-populated values; no
setup nav (the page doesn't fit the per-session setup-mutation
pattern — it's the meta-edit). Breadcrumb is
`Sessions → {session.name} → Edit Session`.

- Same 4 fields as create (Name, Code, Deadline, Description),
  pre-filled from the session.
- **Action row**: **Save changes** (Primary) submits to
  `POST /operator/sessions/{id}/edit` → emits a `session.updated`
  audit event with `changes: {field: [old, new]}` for each
  changed field, invalidates `validated → draft`, and 303 back to
  session detail. **Cancel** (Primary Outline) → session detail.

The route returns **HTTP 409** when the session is `ready` —
operators must revert to draft first via the lock card on
session detail.

## `/operator/sessions/{id}/validate` — Setup validation deep-dive

Read-only deep-dive of every setup issue. The lightweight inline
summary card on session detail (triggered by
`?validated=1`) is the primary entry point for the activate
decision; this page is the click-through for full per-issue
detail. No setup nav (it's a read-only side page); breadcrumb is
`Sessions → {session.name} → Setup validation`.

- **Page intro** (muted text): "Read-only view of setup
  readiness for this session. Errors must be cleared before
  activation. Warnings can be acknowledged and overridden.
  Activate from the inline summary card on the session detail
  page."
- **Severity counts** (three pills inline): error / warning /
  info counts.
- **Per-issue list** (rendered via the
  `operator/partials/validation_results.html` partial) — one
  entry per issue, with severity pill, source (e.g.
  "Reviewers", "Assignments"), and human description.

There is no Activate button on this page; activation lives only
in the inline summary card on session detail (so the activate
contract — "no errors, warnings acknowledged" — is enforced at a
single place).

## Reviewers / Reviewees / Assignments — shared info-card pattern

The three setup-roster pages (Reviewers, Reviewees, Assignments)
share an identical chrome shape:

1. Setup nav header card.
2. Yellow lock card when `ready` (with `return_to=reviewers` /
   `reviewees` / `assignments` so the operator returns here after
   reverting).
3. **Info card** with the page heading and two stacked status rows
   on the left:
   - `Number of {reviewers / reviewees / N · M assignments}: {pill}`.
   - `Fields with data: {pill, pill, …}` listing the actual CSV
     column names (`ReviewerName`, `RevieweeEmail`, `PhotoLink`,
     `RevieweeTag1..3`, `PairContext1..3`,
     `AssignmentContext1..3`, `IncludeAssignment`) for fields with
     at least one non-empty value. These strings come from
     `assignments.reviewer_fields_with_data` /
     `reviewee_fields_with_data` / `assignment_fields_with_data`.
4. **Upload CSV** card — anchored at `#upload-csv`, hosts the
   import form. Hidden when the lock card is shown.
5. Browseable data-preview table of the saved rows (always
   visible, even while locked).
6. **Danger Zone** card with the **Delete all** confirm-checkbox
   form. Hidden when the lock card is shown.

The **Edit Reviewers / Reviewees / Assignments** affordance for
inline-editable rows is not yet implemented; today these pages
expose only the bulk Upload-CSV / Delete-all flow.

The Assignments page additionally carries an anchored
`#rules` "Assign by Rules" placeholder card (Rules editor —
Segment 13) with a Cancel anchor that drops the fragment.

## `/operator/sessions/{id}/instruments` — Instruments

> **Snapshot note.** The detailed per-section description below
> reflects the **end-of-Segment-10C** surface (live preview
> table, `<details>` inline label edits, hardcoded Display Fields
> placeholder, etc.). Segment 10D Slices 1-4 (Display + Response
> Fields + Help, Response Type Definitions card with operator
> add/edit/delete + cascade-confirm + would-empty guard, plus the
> mutual-exclusion edit lock and the zero-RF save guard) have
> since rebuilt the per-instrument card around a single bulk-
> save form (`dfsave-{iid}`) and a `?editing={iid}` URL state
> machine. Polish sequence:
> [#235](https://github.com/philoyhc/review-robin-web/pull/235)
> -[#238](https://github.com/philoyhc/review-robin-web/pull/238)
> on Slices 1-3; the Slice 4 ladder runs from
> [#242](https://github.com/philoyhc/review-robin-web/pull/242)
> (4a) through
> [#257](https://github.com/philoyhc/review-robin-web/pull/257)
> (4d) and the banner-convention follow-ups
> [#258](https://github.com/philoyhc/review-robin-web/pull/258)-[#259](https://github.com/philoyhc/review-robin-web/pull/259).
> The locked spec for the rebuilt surface lives in
> [`guide/instruments.md`](../guide/instruments.md). This file
> will be reconciled on Segment 10D close (i.e. when Slice 5
> ships).

A single consolidated page for everything per-instrument:
session-wide status + bulk toggles, then one card per instrument
with in-place editing for description, response fields, and
display fields, ending with a live Preview Instrument table. The
schema and service surface are fully multi-instrument-aware;
multi-instrument **UI** is intentionally deferred (the
`Add an instrument` button is rendered disabled), so today every
session renders exactly one per-instrument card.

Page sections, in DOM order:

1. Setup nav header card.
2. Yellow lock card when `ready` (`return_to=instruments`). While
   locked, every input/select on every per-instrument card is
   `disabled`, the inline label-edit affordances are suppressed,
   and the per-card Save button is replaced by Edit (which itself
   is disabled — the lock card is the only path back to draft).
3. **All Instrument Status** card (session-wide, full width).
   Reports three pill rows:
   - Session deadline (auto-close): `{deadline.isoformat()}` info
     pill, or `not set` warning pill.
   - Instrument count + accepting breakdown:
     `N instruments` info pill, then `{accepting} accepting` info
     pill and `{not_accepting} not accepting` warning pill.
   - Visibility-when-closed: `{showing} showing` info pill and
     `{not_showing} not showing` warning pill.

   Bottom-right action row carries (in this order):
   - **Open all instruments** / **Close all instruments** —
     mutually exclusive; only renders when the session is `ready`.
     Posts to `/instruments/accepting/all-on` or `/all-off`.
   - **Show all when closed** / **Don't show any when closed** —
     mutually exclusive; visible regardless of session status.
     Posts to `/instruments/visibility/all-on` or `/all-off`.
   - **Preview reviewer surface** — disabled with "Coming soon"
     tooltip. Working preview lives on the session detail's Run
     Session card.

   Bulk-accepting and bulk-visibility toggles deliberately do
   **not** invalidate `validated → draft`.
4. **One per-instrument card** per instrument, identified by
   `id="instrument-{id}"` and tinted from a 6-colour pastel
   palette cycled by `loop.index0 % 6`
   (sky-blue / mint / lavender / peach / rose / amber). Each card
   renders, in DOM order:

   1. **Top `.bottom-grid`** with two halves:
      - **Left half** (transparent, no border): `Instrument #N`
        H2, the friendly description (`Instrument.description`,
        falling back to `(no description)`), and an inline Edit
        affordance — a `<details>` whose summary is an Alert-solid
        `Edit` button and whose body is a textarea + Cancel /
        Save buttons posting to `…/edit`.
      - **Right half** (white background): "This Instrument's
        Status" sub-card. Shows the per-instrument accepting and
        visibility-when-closed pills, the deadline-closed-at
        timestamp when present, and bottom-right
        **Open this Instrument** / **Close this instrument**
        (ready-only, mutually exclusive) plus
        **Show when closed** / **Don't show when closed** (always
        available).

   2. **Field-builder `.bottom-grid.field-builder`** with two
      transparent half-cards side-by-side:
      - **Display Fields** table — *placeholder* shape today.
        Iterates a hardcoded list of six CSV-named rows
        (`RevieweeName`, `RevieweeEmail`, `PhotoLink`,
        `RevieweeTag1..3`); rows are skipped when the
        corresponding CSV column has no data and the row is not
        mandatory (`RevieweeName` / `RevieweeEmail` are mandatory
        and render an `always` muted pill in the Visible column).
        Friendly Label is editable inline via the
        `<details class="display-edit">` tick/cross pattern but
        does **not** persist yet — see "Deferred" below. Order /
        Sort columns are visual placeholders. The schema-level
        display-field routes
        (`POST …/display-fields`,
        `…/display-fields/{df_id}/edit|delete`,
        `…/fields/save`) still exist server-side from Segment
        10B-2 but are **not reachable** from this template.
      - **Response Fields** table — fully wired. Columns:
        system `Key`, inline-editable `Friendly Label` (same
        `<details>` tick/cross pattern), `Type` (read-only
        `<select>` showing the human label), `Required` checkbox
        (auto-submits onchange), numeric `Order` (read-only), and
        an Action column with a row-level delete (✗) and add-row
        (➕) button. Per-row hidden forms placed outside the
        `<table>` via the HTML5 `form=` attribute let cells in
        different `<td>` elements submit together. Add-row posts
        to `…/fields/add-row` with `after={field_id}` and seeds a
        new field with a default key/label/type. Delete posts to
        `…/fields/{field_id}/delete` with a `confirm()` JS guard;
        the cascade-confirm flow for fields whose responses
        already exist still re-renders inline as a danger banner.
        The Type cell is intentionally read-only — changing a
        response type after data exists requires data migration
        and is out of scope.

   3. **Preview Instrument #N** — a live client-rendered table
      below an `<hr>`. Columns are the visible Display Fields (in
      DOM order, Friendly Label as the column header) followed by
      every Response Field in DOM order. Three rows of mock data
      seeded per source/type from `DISPLAY_MOCK` / `RESPONSE_MOCK`
      in the page's inline JS. `PhotoLink` cells render as
      `<a target="_blank">View</a>`; `long_text` columns get
      `min-width: 240px`. The preview re-renders on Display Fields
      Visible-checkbox toggle, Response Fields Type / Required
      changes, Friendly Label save (tick) on either table, and
      add / delete Response Fields row (post-redirect render at
      DOMContentLoaded).

   4. **Bottom button row** (right-aligned), in this order:
      1. **Back** (Primary) — smooth-scrolls to top.
      2. **Save** (Primary) / **Edit** (Alert-solid). One of the
         pair is `hidden` at a time. Save runs `lockFields(card)`
         which closes any open inline editors (resetting their
         input value to the displayed label first), disables every
         `input/select` inside `.field-builder`, and adds
         `.field-builder.locked`. Edit runs `unlockFields(card)`
         to reverse both. Pure client-side state — does not POST.
      3. **Add an instrument** (Alert-solid) — disabled
         system-wide with the tooltip "Multi-instrument support is
         still in progress; coming back later." Posts to
         `/instruments/add` with optional `after={instrument_id}`
         once the UI flag is lifted.
      4. **Delete** (Danger-solid) — only rendered when
         `instruments | length > 1`. Posts to
         `/instruments/{id}/delete` behind a `confirm()` JS guard.

Description / response-field / display-field mutations and the
shared bulk fields-save flip a `validated` session back to
`draft` (and 409 when `ready`). The per-instrument and bulk
acceptance / visibility toggles deliberately do **not**
invalidate. Instrument create / delete invalidate `validated →
draft` (`reason=instrument_added` / `instrument_deleted`).

The legacy per-instrument page at
`/operator/sessions/{id}/instruments/{instrument_id}` 303s to the
consolidated index for back-compat.

**Deferred on this page (not yet wired):**

- Display Fields persistence on the placeholder rows. Friendly
  Label edits, Visible checkbox, and Order columns do not POST.
  Wiring them up requires extending `_VALID_DISPLAY_SOURCES` /
  `_DEFAULT_DISPLAY_LABELS` with `("reviewee", "name")` and
  `("reviewee", "email_or_identifier")`, extending
  `display_field_value` and the reviewer-surface render path to
  resolve them, seeding the six reviewee display fields per
  instrument in `ensure_default_instrument` /
  `create_instrument`, and pointing the placeholder cells at the
  existing `display-fields/{df_id}/edit` route. See
  `guide/archive/segment_10C.md` §5.
- Response Fields type change. Out of scope; type-change is a
  data-migration concern (no segment owner today).

## `/operator/sessions/{id}/preview` — Preview reviewer surface

Operator-only, read-only render of the reviewer surface. Reachable
from the **Preview Reviewer Surface** CTA on the session detail's
Run Session card. The same-named button on the Instruments page's
All Instrument Status card is currently disabled with a "Coming
soon" tooltip.

- **"Preview — not visible to reviewers" banner** at the top.
  Calls out that the page bypasses session-status / deadline /
  acceptance gates and is operator-only.
- Renders **three rows**: real assignments first (by
  `Assignment.id` ascending; up to three), padded with synthetic
  placeholders (`Sample Reviewee 1/2/3`, `sample1@example.edu`,
  per-source sample values for display cells) when fewer real
  assignments exist.
- Every input renders disabled. The Save / Submit / Clear / Cancel
  forms are suppressed (the `<form>` wrapper is replaced with a
  plain `<div>` so no `formaction=` can re-target a write
  endpoint).
- Works in any session status (`draft` / `validated` / `ready`).
- Read-only: does not invalidate, emits no audit events, and
  deliberately skips the lazy deadline-observation side effect.

## `/operator/sessions/{id}/setupinvite` — Set up invites

_Placeholder — to be specified. Own page (rather than inline on the
session detail) because the email-template editor is heavier than
the rest of session setup. Hosts the invitation email template.
Reached from the **Set up invites** row's Manage button on the
session detail._

## `/operator/sessions/{id}/invitations` — Manage invitations

The operator's invitation control panel — generate invitations for
assigned reviewers, send the pending ones, and rotate tokens. No
setup nav (the page is post-activation, not part of setup mutation);
breadcrumb is `Sessions → {session.name} → Invitations`. Reached
from the **Manage Invitations** button on the session detail's Run
Session card.

- **Not-ready banner** (yellow card) when the session isn't
  `ready`: "Invitations can only be issued while the session is
  **ready**. Activate the session from the validation page to
  enable these actions." All POST actions on this page require
  ready (409 otherwise).
- **Summary card** (3 inline counts): eligible reviewers (active +
  at least one assignment), uninvited count, pending-send count.
  Action row:
  - **Generate invitations** (Primary) →
    `POST /…/invitations/generate`. Bulk-creates one invitation
    per uninvited eligible reviewer. Idempotent. Disabled when
    `uninvited_count == 0` or session not ready. Audit:
    `invitations.generated`.
  - **Send all pending** (Primary Outline) →
    `POST /…/invitations/send-all`. Writes one outbox row per
    pending invitation; flips them to `sent`. Disabled when
    `pending_count == 0` or not ready. Audit: one
    `invitation.sent` per row.
  - **View outbox** (Primary Outline) →
    `/…/outbox`.
  - Muted footnote: "Each Send rotates the token (the previous
    URL becomes stale) and writes a fresh row to the dev outbox.
    Reviewers must sign in with their work email to follow the
    link."
- **Per-reviewer table** (always rendered when invitations
  exist). Columns:
  - **Reviewer** — name in bold, email in `<code>`.
  - **Status** — pill (`pending` warning / `sent` info /
    `opened` info).
  - **Sent** — ISO timestamp or `—`.
  - **Opened** — ISO timestamp or `—`.
  - **Actions** (right-aligned, no header):
    **Send** (Primary Outline) → `POST /…/invitations/{iid}/send`
    rotates the token + writes outbox + flips to `sent`.
    **Regenerate** (Primary Outline) →
    `POST /…/invitations/{iid}/regenerate` rotates the token +
    resets to `pending` (`invitation.regenerated`).
- **Empty state** — "No invitations yet. Click *Generate
  invitations* above to create one row per assigned active
  reviewer."

## `/operator/sessions/{id}/monitoring` — Monitoring

Per-reviewer progress + reminder actions for the live session.
No setup nav; breadcrumb is
`Sessions → {session.name} → Monitoring`. Reminder actions
require ready; the page itself renders in any status (so an
operator can review counts post-deadline).

- **Not-ready banner** (yellow card) when the session isn't
  `ready`: "Reminder actions require the session to be **ready**.
  Activate the session from the validation page first."
- **Summary card** (5 inline pills): assigned / invited / opened
  / submitted (info) and incomplete (warning) counts. Action row:
  - **Send reminders to N incomplete reviewer(s)** (Primary) →
    `POST /…/monitoring/remind-incomplete`. Bulk reminder to
    every reviewer whose pill is anything other than `submitted`.
    Disabled when not ready or when `incomplete == 0`. Audit:
    one `reminders.sent` event with `count` + `invitation_ids`
    + `reviewer_ids` + `fell_back_count`.
  - **View outbox** (Primary Outline) → `/…/outbox`.
  - Muted footnote explains the reminder reuse semantics:
    reminders reuse the URL from the most recent invitation send
    so the reviewer's existing link keeps working; if a reviewer
    has never been sent the original invitation, the reminder
    action mints a fresh token and writes an `invitation`-kind
    outbox row.
- **Per-reviewer table** (rendered when at least one assignment
  exists). Columns:
  - **Reviewer** — name in bold, email in `<code>`.
  - **Invitation** — pill (`opened` / `sent` info; `pending` /
    `no invitation` warning).
  - **Progress** — pill (`submitted` info / `in progress` /
    `not started` warning) plus muted `(completed/assignments)`
    count.
  - **Missing required** — integer count of required fields
    without a saved response.
  - **Last reminder** — ISO timestamp or `—`.
  - **Actions** (right-aligned, no header): **Send reminder**
    (Primary Outline) → `POST /…/invitations/{iid}/remind`.
    Disabled when not ready or when the reviewer is not
    incomplete.
- **Empty state** — "No assigned reviewers yet — generate
  assignments before activating the session."

A reviewer is **incomplete** iff their session pill is anything
other than `submitted` (i.e. "never opened", "opened but not
submitted", or "submitted-with-warn-override that still has
missing required" all classify them as incomplete).

## `/operator/sessions/{id}/outbox` — Email outbox

Dev-mode email outbox view for the session. Read-only; no actions
on this page. Breadcrumb is
`Sessions → {session.name} → Outbox`. Reached from the **View
outbox** button on the Invitations and Monitoring pages.

- **Page intro** (muted text): "Dev-mode email outbox for this
  session. No real SMTP backend is wired up; rows are flipped
  `queued → sent` synchronously when an operator clicks *Send*.
  The rendered body includes the raw invitation URL so you can
  copy it into a real client."
- **Per-row card** (one card per outbox row, newest first):
  header line shows kind (`invitation` / `reminder`), recipient
  email in `<code>`, status pill (`sent` info or `queued`/other
  warning), and sent-at timestamp. Then the rendered email
  subject and body (`<pre>` block, `white-space: pre-wrap`).
- **Empty state** — "No outbox rows yet for this session."

Real SMTP / production email is **deferred to Segment 15**; the
outbox table itself stays useful for debugging in any environment.

## `/about` — About

_Placeholder — to be specified. Reached from the app-identity text
at the top left of every operator page._
