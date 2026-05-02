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
