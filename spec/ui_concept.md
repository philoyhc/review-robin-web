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
that session's home. It's the session-level dashboard that names
the session, summarises its setup state, and provides the
session's identity and short-form session-metadata edit.

- `session_detail.html` — `GET /operator/sessions/{id}`.

Home has **no child pages of its own** — affordances that would
have lived as separate pages (the Edit Session form, the
short-form readiness summary) render inline in the Control Panel
body. Pages that belong to the session but cover specific work
or run-time concerns are children of a Setup Page or an
Operations Page (P5).

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
  from the Control Panel.

The category is plural because additional Preview Pages are
anticipated (e.g. per-instrument preview integration is open per
`guide/instruments.md` Section D).

### 5. Per Session Operations Pages

Surfaces for running a session and intervening when needed —
gating activation, sending invitations, monitoring progress,
debugging email delivery. The set is currently four pages:

| Page | Template | URL |
|---|---|---|
| Validate | `session_validate.html` | `/sessions/{id}/validate` |
| Invitations | `session_invitations.html` | `/sessions/{id}/invitations` |
| Monitoring | `session_monitoring.html` | `/sessions/{id}/monitoring` |
| Outbox | `session_outbox.html` | `/sessions/{id}/outbox` |

Notes:

- **Validate** is the gate the operator crosses to *run* the
  session — sits next to Invitations / Monitoring rather than
  next to session metadata. The short-form readiness summary
  also renders inline on Home (via the existing `?validated=1`
  branch on the Control Panel).
- **Outbox** is a per-session Operations Page **with system
  powers** (read raw email-outbox rows, useful for debugging
  send paths). Despite the "system" framing it is *not* a
  cross-session admin surface — it's per-session. A future
  cross-session admin surface would belong to the System Admin
  group below.

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

### P3 — Home is the anchor, not a gate

Home (the Control Panel) is **the session's identity and
dashboard**. It is reachable from every session-scoped page,
but it is not on the path between phases.

### P4 — Lifecycle disables, never hides

**Pages remain reachable across all session lifecycle states.**
Affordances that don't apply to the current state render
disabled (yellow lock card pattern), not removed.

### P5 — Every session-scoped page has a parent

**Outside the pages associated with the Operator's Overview,
every page in the app is either a Setup Page, an Operations
Page, or a child of one of those.** The Per Session Home /
Control Panel is the single exception — it is the session's
identity page, not a child surface, and it does not host its
own children.

The four-line shape of P1–P4: two principles about *where the
operator can go* (P1 and P2), one about *what stays put* (P3),
one about *what stays reachable* (P4). P5 is the structural
guarantee that keeps the page set tidy as new pages are added
— every new page has to declare which parent it belongs to.

## Navigation model

The chrome that implements the principles above. The page-level
implementation lives in `spec/operator_map.md`; the conceptual
contract is here.

### Two-row chrome with double-height Home

Every session-scoped page renders the same chrome:

```
┌────────┬──────────────────────────────────────────────────────────┐
│        │  Setup row:   Reviewers · Reviewees · Assignments ·      │
│        │               Instruments · Email Template               │
│  HOME  ├──────────────────────────────────────────────────────────┤
│        │  Operations row:  Validate · Invitations ·               │
│        │                   Monitoring · Outbox                    │
└────────┴──────────────────────────────────────────────────────────┘
```

- **Home** anchors the left, spanning both rows (double-height).
  Implements P3: Home is reachable from every session-scoped
  page without competing for tab-row width on either row.
- **Setup row** (top right) carries the five Setup tabs.
- **Operations row** (bottom right) carries the four Operations
  tabs.
- **Both rows are always visible** on every session-scoped
  page. Implements P2 — phase switching is one click from
  anywhere, never via Home.

### Group identity and active marker

- **Tab tint = group identity.** Home tab carries one tint,
  Setup tabs another, Operations tabs another. The tint tells
  the operator at a glance which group a tab belongs to.
- **Active marker is a single colour everywhere.** The active
  tab gets a short understated underline (or equivalent) in one
  unified colour, regardless of group. The tint already carries
  the group; the active marker just says *"you are here"*.

The exact tints are an `operator_map.md` concern; see that file
for current values.

### Sub-pages and Preview Pages

- **Preview Pages** render the chrome with their **parent
  Setup tab active** (e.g. on `/preview`, the Instruments tab
  is highlighted). The Preview surface is "still inside"
  Instruments.
- **The Control Panel's inline Edit-Session form** stays inline
  on Home; clicking the form shows the editor without
  leaving the Home page. (Per P5, Home has no separate child
  pages — Edit lives on Home.)

### Lifecycle behaviour (P4 in chrome)

Tabs themselves stay clickable in every session lifecycle
state. Lifecycle disabling lives **inside the destination page**
— typically the yellow lock card explaining what state change
will unlock the page's actions, plus disabled buttons / forms.
The chrome is for *navigation*; lifecycle is for *what you can
do once you're there*.

This is a deliberate choice: greying out the tab itself would
hide the existence of the page until the lifecycle moved
forward, which contradicts P4's "disables, never hides" framing.

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
  Invitations + Monitoring into a single page (and Validate's
  inline-on-Home rendering stays sufficient), the Operations
  row could shrink to one or two tabs. At which point the
  two-row chrome could collapse to a **single row** (Setup tabs
  only, with the residual Operations tab(s) appended). This is
  a possible future, not a plan.
- **Cross-session System Admin** — when added, sits at
  Operator's Overview level (or above), not inside a session.
  Implies its own chrome (different from the per-session two-row
  nav). Not a per-session Operations Page.

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
