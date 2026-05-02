# UI concept

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

The operator's pages fall into five active groupings plus two
forward-looking placeholders.

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

### 2. Per Session Control Panel

Once an operator is **inside a session**, the Control Panel is
that session's home. It's the session-level dashboard that names
the session, summarises its setup state, and acts as the launch
point for the session's Setup Pages, Operations Pages, and
supplementary views.

- `session_detail.html` — `GET /operator/sessions/{id}`.

**Child pages of the Control Panel** (session-scoped, supplementary
views or sub-forms of the Control Panel itself):

- `session_edit.html` — `GET /operator/sessions/{id}/edit` —
  edit form for session metadata (name, code, deadline, …).
- `session_validate.html` — `GET /operator/sessions/{id}/validate`
  — read-only setup-readiness view. Also rendered inline on the
  Control Panel via `?validated=1`.

### 3. Per Session Setup Pages

The five surfaces where the operator does the work needed to make
the session run properly. Each one has full edit affordance while
the session is `draft` / `validated`, and locks down once the
session is `ready` (yellow lock card pattern).

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
  for the session's instruments). Reachable from Instruments and
  from the Control Panel's Run Session card.

The category is plural because additional Preview Pages are
anticipated (e.g. per-instrument preview integration is open per
`guide/instruments.md` Section D).

### 5. Per Session Operations Pages

Surfaces for monitoring a running session and intervening when
needed (sending invitations, sending reminders, pulling status).
Conceptually they are siblings of the Control Panel for the
"running session" phase — too much content for a single page, so
they're split out by concern.

| Page | Template | URL |
|---|---|---|
| Invitations | `session_invitations.html` | `/sessions/{id}/invitations` |
| Monitoring | `session_monitoring.html` | `/sessions/{id}/monitoring` |
| Outbox | `session_outbox.html` | `/sessions/{id}/outbox` |

The **Outbox** is a "sysadmin mode enabled" Operations Page —
visible only when dev-mode SMTP is in play (no real outbox once
Segment 15 ships). It's reachable from the other Operations Pages
as a diagnostic affordance, not its own first-class entry point.

### 6. System Admin / System Setup Pages (placeholder)

A future grouping for cross-session admin (operator permissioning,
system-wide settings). Empty today; flagged here so the taxonomy
has a slot for it when the work surfaces.

## Design principles

### P1 — No cross-session navigation between Setup Pages

The operator cannot navigate directly from one session's Setup
Page to another session's Setup Page. To switch sessions while
in setup, they go back to the Operator's Overview and click into
a different session.

This means session-level nav chrome (folder tabs, breadcrumbs)
is **always single-session** — no cross-session selectors live
inside the chrome of a session-scoped page.

### P2 — No cross-session navigation between Control Panel / Operations Pages

Same rule for the running-session phase. From inside session A's
Control Panel or Operations Pages, the operator cannot jump to
session B's equivalent surfaces — they go back to the Overview
first.

The two principles together pin down: **the operator is always
"inside" exactly one session, or in the Overview**. There is no
multi-session view of session-scoped state.

### P3 — No direct navigation between Setup Pages and Operations Pages

Setup and Operations are **separate phases** of working with a
session. To switch phases, the operator goes back through Home
(the Control Panel). There is no nav shortcut from a Setup Page
into an Operations Page or vice versa.

The Control Panel is the **bridge**: it's the single page that
launches both phases. Within each phase, free movement between
sibling pages is fine and expected. Across phases, the path
always goes through Home.

## Navigation model

The chrome that implements the principles above. The page-level
implementation lives in `spec/operator_map.md`; the conceptual
contract is here.

### Home as the universal anchor

The Control Panel is **Home**. Home is reachable from every
session-scoped page via a `Home` tab in the nav chrome — the
single tab that's universally present regardless of which
phase the operator is in.

Home is visually distinct from the other tabs:

- Slightly larger label.
- Offset from the rest of the nav by an extra gap.
  Approximate sizing: the visual width of `[Home]` plus the
  trailing gap equals two normal tab widths. This makes the
  "Home is special" affordance obvious without inventing a new
  shape.

### Phase-specific group nav (alternate slot)

The rest of the nav row carries the **active phase's group tabs**:

- **On a Setup Page:** `[Home]` + Setup group:
  `[Reviewers][Reviewees][Assignments][Instruments][Email Template]`.
- **On an Operations Page:** `[Home]` + Operations group:
  `[Invitations][Monitoring][Outbox]`.

The two groups occupy the **same slot in the nav row** — they
don't co-render. Whichever phase you're in is the only group
visible. To change phase, the operator goes back to Home and
launches the other phase from there.

The two groups are visually distinct via a **subtle color tint**
(one accent per group; same tab shape across both). The tint
signals which phase the operator is in at a glance, before they
read any tab label.

### Home page itself

When the operator is **on Home**, the nav shows only the `Home`
tab (active). The page body — not the chrome — does the
launching into Setup and Operations. Cards in the Control Panel
body name the two phases and link into them.

This keeps Home minimal in the chrome and keeps the chrome's
role consistent: chrome is the "where am I and where can I go
*within this phase*" affordance, not a phase selector. The phase
selector lives in the Control Panel body.

### Sub-pages and Preview Pages

- **Sub-pages of Home** (Edit Session, Validate): nav renders
  `[Home]` only (no group), Home tab active. The sub-page name
  appears as a breadcrumb-like label inside the page body, not
  in the chrome.
- **Preview Pages** (currently the reviewer-surface preview at
  `/preview`, child of Instruments): nav renders the Setup group
  with the parent tab active (e.g. `Instruments` highlighted
  while the operator is on Preview). The Preview surface is
  conceptually still "inside" its parent Setup Page.

### Lifecycle awareness

Operations Pages remain reachable from Home regardless of
session lifecycle (`draft` / `validated` / `ready` / `closed`).
On `draft` / `validated` sessions, Operations Pages render with
their actions disabled (yellow lock card pattern, greyed-out
buttons). Hiding pages until activation surprises the operator
when things appear later; a disabled state is clearer pedagogy
about what activation unlocks.

The same applies in reverse: Setup Pages remain reachable from
Home on `ready` / `closed` sessions, but render locked behind
the existing yellow lock card. The operator must `Revert to
draft` to mutate setup, but the pages themselves don't
disappear.

## Out of scope / forward-looking notes

Recorded for visibility; **none are committed**. Capture additional
ideas here as they surface so the taxonomy doesn't get redesigned
to accommodate them later.

- **Central Control and Operations Panel** — a cross-session
  operator surface that aggregates run-state across all of an
  operator's sessions. Conceivable but ROI unclear, and the
  single-session principles P1 / P2 are stronger when the whole
  app respects them. Not on any segment plan.
- **Adjacent capabilities likely to land sooner**: shared operator
  permissions on a session, session duplication (sans response
  data), shared setup data between sessions (e.g. reusable
  reviewer rosters or instrument templates), session
  tagging / grouping. These compose with the Overview surface —
  none would force a redesign of the Setup / Control / Operations
  groupings.
- **Validate as an Operations Page (alternative placement).** The
  Validate page currently sits as a sub-page of Home. Plausible
  alternative: re-cast it as one of the Operations Pages, since
  validation is the gate the operator crosses to *run* the
  session. Recorded for revisit if the Operations group ever
  feels under-populated or if Validate's "readiness" framing
  reads more naturally next to Invitations / Monitoring than
  next to Edit.

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
