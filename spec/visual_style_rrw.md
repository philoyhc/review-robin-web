# Visual style — Review Robin Web App

Instantiates the general visual style spec (`spec/visual_style_general.md`) for Review Robin specifically. Defines:

- The app-specific decisions the general spec leaves open: which accents map to which navigation groups, how lifecycle states render.
- The chrome that surrounds Review Robin pages — operator session chrome, non-session operator chrome, reviewer-facing chrome.

Read alongside:

- `spec/visual_style_general.md` — the design system this document instantiates. Components and visual vocabulary defined there (palette, typography, spacing, button shapes, card shapes, badge shapes, etc.) apply uniformly across all surfaces.
- `spec/audience_and_identity_model.md` — audience definitions, auth posture, and customization boundaries that this document's chrome decisions implement.

The visual vocabulary defined in `visual_style_general.md` applies uniformly across all surfaces. What differs by surface is the *chrome* — the framing and navigation patterns that surround page content.

---

## App-specific accent assignments

The general spec defines four semantic accents (blue, green, amber, red). Review Robin assigns them as follows:

- **`accent-blue`** — the **Setup** navigation group identity. Active states across the app. Links. Primary actions.
- **`accent-green`** — the **Operations** navigation group identity. Successful states. The `ready` lifecycle indicator.
- **`accent-amber`** — setup-incomplete indicators (`NONE`, `NOT SET UP`). The yellow lock card pattern. Lifecycle-locked surfaces.
- **`accent-red`** — destructive action confirmations (e.g., replacing existing setup data via Quick Setup). Validation errors. Used rarely.

Setup and Operations are two parallel series of pages (see `spec/operator_ui_concept.md` for the taxonomy). The blue/green pairing for these two groups is the app's most visible color decision and should be preserved across the entire chrome.

---

## Lifecycle state colors

Sessions move through three live states (and two reserved future states; see `app/services/session_lifecycle.py` for the canonical enum). Each renders as a badge in the status strip and (where relevant) inline elsewhere:

- **`draft`** — warning amber (`accent-amber-dark` text on `accent-amber-bg` background). Same treatment as `.pill-empty`. The session is *not ready for action* — setup work remains, the operator's eye should land on the badge as a "needs work" cue rather than a neutral "nothing happening here" grey.
- **`validated`** — muted blue (`accent-blue` text on `accent-blue-bg` background). Setup is complete and validated; ready to activate.
- **`ready`** — muted green (`accent-green` text on `accent-green-bg` background). The session is live. Renders as **"Activated"** in user-facing copy via the lifecycle display-label mapping (see `spec/session_home.md`).

Lifecycle state always appears first in the status strip, leftmost, before per-entity counts.

---

## Operator session chrome

The chrome that surrounds session-scoped operator pages (Session Home and the Setup / Operations tab pages).

### Navigation chrome (two-row layout)

The session-scoped chrome consists of:

**Top region** (above the chrome): breadcrumb in the standard pattern.

**Chrome itself**: a double-height **Home** anchor on the left, two rows of phase tabs to its right.

```
┌────────┬─ SETUP ▶      [Reviewers][Reviewees][Assignments][Instruments][Email Template]
│  Home  │
└────────┴─ OPERATIONS ▶ [Validate][Previews][Invitations][Monitoring]
```

Specifics:
- **Home** is double-height to span both rows, signalling that it's one level up from the phase tabs rather than a peer of any of them.
- **Row labels** ("SETUP", "OPERATIONS") sit at the left edge of each row, in tiny text, medium weight. The `▶` glyph sits adjacent to indicate the row's tabs follow.
- **Row backgrounds** use the row's accent color at 5% opacity (`accent-blue` for Setup, `accent-green` for Operations).
- **Active tab** uses an underline in the row's marker tone (`accent-blue-marker` for Setup, `accent-green-marker` for Operations) — lighter than the full accent so the marker signals position without competing with the label.
- **Active row** (the one containing the active tab): row label renders at `text-primary` instead of `text-muted`; the `▶` glyph emphasizes correspondingly.
- **Hovering a tab** in a non-active row previews-emphasizes that row's label without transferring active state — gives the operator a sense of "this is the row you're about to enter."
- **Same tab shape** across both rows. Differences between rows are carried by row labels and row tints, not by tab shape.

**On Home itself**: chrome renders in the same shape, with no tab active. Both rows remain visible and clickable.

**On sub-pages of Home** (Edit Session, etc.): chrome renders normally. The sub-page identifies itself in the page body via H1, not in the chrome.

**On Preview pages** that are children of a Setup tab: chrome renders normally with the parent Setup tab active.

### Status strip

The status strip sits below the chrome and above the page body on all session-scoped pages. Composition, left to right:

```
Session: [LIFECYCLE_BADGE]  ·  Reviewers: [count]  ·  Reviewees: [count]  ·  Assignments: [count or NONE]  ·  Instruments: [count]  ·  Email Template: [count or NOT SET UP]  ·  Invitations: [state]  ·  Responses: [state]
```

Lifecycle badge first, then the five Setup entities in canonical order (Reviewers, Reviewees, Assignments, Instruments, Email Template), then the two operations indicators (Invitations, Responses) at the right. Counts use the standard count-badge styling; missing/empty states use the amber empty-indicator badge.

The strip is a setup + ops at-a-glance summary, not a running-session dashboard. Detailed operations state (per-reviewer invitation status, per-instrument response counts) lives on the Operations pages themselves.

### Page header conventions

Page-level identity is established by the breadcrumb and the active chrome tab in combination. Most pages do not need a redundant H1 echoing the active tab name.

Exceptions:
- **Home (Session Home / Control Panel)** — H1 is the session name, since the session is what Home represents. Lifecycle state appears as a badge in the status strip; no need to repeat in the page body.
- **Sub-pages of Home** (Edit Session) — H1 is the sub-page name ("Edit Session"), since the chrome doesn't distinguish sub-pages from Home.
- **Operator's Overview** (sessions list) — H1 is "Sessions" or similar, since this page sits outside session-scoped chrome.
- **Preview pages** that are children of a Setup tab — H1 is the preview's name ("Reviewer surface preview"), not the parent tab's name.

For all other session-scoped pages (the five Setup pages, the Operations pages), no H1 is needed. The chrome tab and breadcrumb together establish identity.

### Warning surfaces — shared brown framing

Two card variants in the app's vocabulary frame "this region needs care": the **lock card** (intentionally non-interactive due to lifecycle) and the **danger-zone card** (groups destructive actions). Both border in `accent-amber-dark` (the warning brown), so the operator's eye recognises the same visual category whether reading "you can't change this right now" or "here's where you delete data". The interior treatments differ — the lock card has the `accent-amber-bg` tinted surface; the danger zone has white — but the framing is one.

Per **P7**, recovery / primary actions inside these cards adopt the card's color family:

- **Inside a lock card**: outline-amber button (e.g. "Revert to draft"). A solid Primary blue inside an amber card clashes; the outline-amber action continues the framing.
- **Inside a danger zone**: outline-red Destructive button. Same principle applied to the destructive role — the brown frames the surface; the red marks the action that actually deletes data.

#### Lock card uses

Used when a page or section is reachable but its actions are disabled because the session lifecycle locks them.

- **On Setup pages** when session is `ready`: lock card explains that setup is locked and offers a "Revert to draft" action where appropriate.
- **On Operations pages** when session is `draft` or `validated`: lock card explains that operations are unavailable until the session is activated, and links to Home where the Activate action lives.
- **On the send-test affordance** within the Reviewer Experience Preview when session is no longer accepting responses: same pattern.

The lock card pattern is consistent across all of these. Its prominence and explanatory copy adapt to the specific case, but its visual treatment does not.

**Exception — Session Home.** Per `spec/session_home.md`, Home does *not* render lock cards; the contextual primary action card carries any explanatory messaging the operator needs about lifecycle. Disabled treatment on Home is plain greying-out. Lock cards remain in use everywhere else.

#### Danger-zone card uses

Groups the destructive actions for a given Setup entity (Delete all reviewers / reviewees / assignments / instruments) and the session-level destructive actions (Delete data, Delete session). H2 is "Danger Zone" in `accent-amber-dark`. Lives at the bottom-right of the page (or in the bottom row of a `.bottom-grid`) so it stays visually grouped with the entity it operates on but isn't the first thing the eye lands on.

---

## Non-session and reviewer chrome

Per `spec/audience_and_identity_model.md`, the app comprises three distinct surface types, each with its own chrome conventions:

```
                    App
                     │
       ┌─────────────┼─────────────┐
       │                           │
   Operator                    Reviewer
    surface                     surface
       │                           │
   ┌───┴───┐                       │
   │       │                       │
Session-  Non-session         Sign-in +
scoped    operator pages      review list +
operator  (this section)      response form
pages                         (this section)
(above)
```

Within each surface, components from `visual_style_general.md` are used identically; chrome and structural patterns differ.

### Non-session operator pages

Pages the operator visits when *not* working inside a specific session: the Sessions list (Operator's Overview), the Create Session form, About, Settings, and any future app-level pages.

#### Chrome philosophy

**Minimal and quiet.** Non-session operator pages are visited rarely and usually as detours from the operator's main work (which happens inside sessions). The chrome should not invest visual weight in navigating between them, since operators rarely navigate between non-session pages directly.

The two-row session chrome (Setup row, Operations row) **does not appear** on these pages. The status strip does not appear. Lifecycle badges do not appear. These are session-scoped affordances and have no meaning outside a session.

#### Top bar

The existing top bar pattern continues:

- **Left:** "Review Robin Web App (version dev)" — small, in `text-secondary`. App identity and version, modest.
- **Right:** A small **user menu** containing:
  - "Signed in as [Operator Name]" (informational, not a link).
  - About — opens About page, with return-to-origin behavior (see below).
  - Settings — opens Settings page, with return-to-origin behavior.
  - Sign out — ends the operator's session.

The user menu can render as inline links (when the menu has three or four items) or as a dropdown triggered by clicking the operator name. Inline is preferred while the menu is small; promote to dropdown when it would otherwise crowd the top bar.

#### Return-to-origin behavior

About and Settings are detour destinations: the operator opens them to consult or adjust something, then wants to return to whatever they were doing. The pattern:

- When the operator opens About or Settings, the URL captures the origin via a query parameter (e.g., `?return_to=/sessions/abc123`) or session state.
- The About/Settings page renders a clear "Back" affordance — a link in `accent-blue` near the top of the page body, labeled with context where possible: "← Back to Sessions" or "← Back to Student Associate Selection 2026 Peer Review".
- Clicking the affordance returns the operator to the origin URL.
- If no origin is recorded (e.g., the operator deep-linked to Settings), the affordance defaults to "← Back to Sessions" — the app's natural lobby.

This is a small piece of plumbing but it changes the affordance from "trip down a rabbit hole" to "quick consultation." Operators learn to use About and Settings without losing their place.

#### Page structure

Non-session operator pages share a simple structure:

1. **Top bar** (as above).
2. **Page body**:
   - Optional return-to-origin affordance (top-left of body).
   - **H1 page title.**
   - Page content.

No breadcrumb is needed; the page hierarchy is too shallow. The H1 and the user menu together orient the operator sufficiently.

#### Operator's Overview (Sessions list)

This page is the operator's "lobby" and is the natural landing page when signing in or returning from a session. It deserves slightly more care than other non-session pages, but uses the same chrome.

- **H1:** "Sessions" or "My Sessions".
- **Body:** A list or grid of session cards. Each card shows:
  - Session name (linked to that session's Home).
  - Lifecycle state badge (using the display labels: Draft, Validated, Activated, etc.).
  - Deadline.
  - Brief setup readiness summary (count badges or a single status summary).
- **Create Session affordance:** primary button in the top-right of the list area, labeled "New Session" or "Create Session". When the list is empty, this becomes the page's prominent affordance, rendered larger and with explanatory text.

The session cards reuse the Card component from the general spec; the lifecycle badges reuse the badge component with the lifecycle color treatments above.

#### About / Settings / Create Session

Each is a single page with the standard non-session chrome. Body content is whatever the page does:

- **About:** version info, links to documentation, changelog. Read-only.
- **Settings:** operator preferences, app-level configuration. Form with standard form components.
- **Create Session:** a form for creating a new session. Submitting takes the operator to the new session's Home.

If any of these grow into multi-page sets later (e.g., Settings with multiple categories), they may need their own internal navigation — but this is a future concern, not a current one. The first such page-set to land will define the pattern.

### Reviewer-facing pages

The surfaces a reviewer sees when signing into Review Robin and responding to a session. Per the audience and identity model, reviewers are authenticated users of the app — not anonymous form respondents — but they spend most of their time in task-focused surfaces rather than in app-level navigation. The chrome reflects this: app identity is persistent and visible enough to function as a trust anchor, but unobtrusive enough that the reviewer's attention stays on their work.

#### Chrome philosophy

**Light but recognizable.** The reviewer's experience is minimal in structure but consistent in identity. Across sessions, the reviewer-facing chrome looks the same; per-session variation is limited to content (session name, instructions, instrument names) within stable chrome.

What this means in practice:

- Review Robin identity is **persistent and visible** but small — enough for the reviewer to recognize the app, not enough to dominate the page.
- Per-session operator customization is **content-only** — session name, optional welcome message, optional institution name. No visual customization (colors, layout, branding imagery). See `spec/audience_and_identity_model.md` for the rationale.
- Operator chrome (two-row session navigation, status strips, lifecycle badges) does **not** appear on reviewer pages. Reviewers don't navigate the operator's structure; they have their own.

#### Top bar

Reviewer-facing pages have a top bar, but lighter than the operator's:

- **Left:** "Review Robin" — small, `text-secondary`. App identity as a trust anchor. No version info (operators care about that; reviewers don't).
- **Right:** A small **user menu** containing:
  - "Signed in as [Reviewer Name]" — informational. Lets the reviewer confirm correct identity (important on shared computers, useful in institutions where SSO might silently log the wrong person in).
  - "My Reviews" — link back to the reviewer's review list (only rendered when the reviewer has more than one review pending or completed; suppressed when there's just one).
  - "Sign out" — ends the reviewer's session.

The top bar is consistent across all reviewer pages. Its presence is what makes the reviewer surface recognizable as Review Robin across sessions.

#### Sign-in surface

The first page a reviewer sees, reached by clicking a sign-in link in their invitation email or by direct URL. This page has elevated trust significance: the reviewer is about to authenticate, and they need to verify they're on the right system before doing so.

**Chrome:**

- Standard top bar with Review Robin identity (no user menu yet, since the reviewer isn't signed in).
- Page body centered on the sign-in flow:
  - **H1:** "Sign in to Review Robin" or similar.
  - Brief explanation of the auth flow ("You'll be redirected to your institution's sign-in page.").
  - Primary action: "Sign in with [Institution]" (SSO trigger, branded with the institution name when known from the invitation context).
  - Secondary affordance: magic-link option, for reviewers without SSO access. Less prominent than the SSO action.

After authentication, the reviewer is delivered to either:

- The specific response surface they were invited to (if the sign-in link was for a specific session), or
- Their reviewer review list (if no specific destination is associated with the sign-in).

#### Reviewer's review list

The reviewer's "home" after sign-in. A simple list of pending and recent reviews.

**Chrome:** standard reviewer top bar + page body.

**Body:**

- **H1:** "My Reviews" or "Your Reviews".
- A list of review cards, each showing:
  - Session name (linked to that session's response surface for this reviewer).
  - Deadline.
  - Completion status (e.g., "Not started," "In progress: 2 of 5 reviewees," "Completed").
  - Optional: institution name if relevant for cross-institution reviewers.
- Empty state when the reviewer has no pending reviews: "You have no pending reviews." in `text-secondary`. Not an error; just informational.

**Deep-linking behavior:** when a reviewer signs in via a session-specific invitation link and has only one pending review, the sign-in flow can deep-link them past the review list to the response surface directly. The list exists for the cases where it's useful (multiple reviews, returning to find a specific one); it's not a forced waypoint for every visit.

#### Response surface (the response form)

The main task surface, where the reviewer completes their evaluations.

**Chrome:**

- Standard reviewer top bar (Review Robin identity + user menu).
- **Page header** with session context:
  - Session name — rendered at H1 size.
  - Deadline — small reminder in `text-secondary`, near the session name.
  - Optional: institution or operator name (small, `text-secondary`) — useful for reviewers participating across institutions or with multiple operators in mind.
  - Optional: operator-configured welcome message / instructions, shown above the form on first visit. Plain text or limited markdown.
- **Instrument tab strip** (only when the session has more than one instrument; see below).
- **Form body.**

##### Multi-instrument navigation

A session may have multiple instruments for a reviewer to complete across their assigned reviewees. This requires more than one page facing the reviewer, and therefore some navigation chrome.

**Pattern: a single horizontal tab strip.**

Below the page header, one row of tabs — one tab per instrument the reviewer needs to complete:

```
Session: Student Associate Selection 2026 Peer Review · Deadline: 2026-07-01
─────────────────────────────────────────────────────────────────
[Skills Assessment] [Cultural Fit] [Final Recommendation]
─────────────────────────────────────────────────────────────────
```

Specifics:

- **Tab labels** are the instrument names, kept short.
- **Active tab** uses the same underline-and-color-emphasis pattern as the operator session chrome above, but in a single row. Reuses the tab component from the general spec.
- **Per-tab completion indicator.** A small badge or dot adjacent to the tab label shows whether that instrument is incomplete, in progress, or complete:
  - No badge: not started.
  - In progress (some responses entered, not all): muted dot indicator.
  - Complete: small check icon or `accent-green` badge.

  This lets the reviewer track progress at a glance without a separate dashboard.
- **Tab order** matches whatever order the operator configured in the Instruments Setup page. The reviewer is not free to reorder; the tabs are determined by the session's setup.
- **Free movement between tabs.** The reviewer can switch tabs at any time. Responses are saved per-tab as they go (auto-save or on-tab-change save — implementation detail, but the reviewer should never lose work by switching tabs).
- **No tab is "locked" by another tab's completion.** The reviewer can complete instruments in any order.

**When there is only one instrument**, the tab strip does not render. A single-instrument session shows just the page header and the form directly; introducing a one-tab strip would be visual noise.

##### Per-reviewee navigation within an instrument

A separate concern: within a single instrument, the reviewer may need to evaluate multiple reviewees. This is *content-level* navigation, not chrome-level. It belongs inside the instrument's form, not in the page chrome.

Pattern options for in-form per-reviewee navigation:

- **One reviewee per page**, with "Next reviewee" / "Previous reviewee" affordances at the bottom of the form, plus a small indicator ("Reviewee 2 of 7") near the top.
- **All reviewees on one page**, in a long scrolling form with each reviewee as a section.
- **Sidebar of reviewees** within the form, letting the reviewer jump between them.

The choice depends on instrument complexity and reviewee count and is properly the concern of the response-form component, not the chrome. Flagging here so it's clear the chrome stops at the instrument-level tab strip; what happens *inside* the form is the form's design.

#### Submission confirmation

Shown after the reviewer submits all required responses for the session.

**Chrome:** standard reviewer top bar + page body.

**Body:**

- Brief acknowledgement: "Thank you. Your responses have been received."
- Optional: summary ("You completed 3 instruments across 7 reviewees.").
- Optional: link back to the reviewer's review list, if other reviews remain.
- No tab strip; the task is complete.

Tone: calm and brief. The reviewer is finished; the page should confirm and let them go.

#### Error / expired states

Shown when a sign-in link is invalid, the session is not in Activated state, or the deadline has passed.

**Chrome:** standard reviewer top bar (with whatever auth state applies — signed in or not) + page body.

**Body:**

- Brief explanation in plain language. Examples:
  - "This review is no longer accepting responses. The deadline passed on [date]."
  - "This sign-in link is no longer valid. Request a new one from the session organizer."
  - "This review is not currently available. Try again later or contact the session organizer."
- Avoid technical detail (no "Session is in Draft state" — that's operator vocabulary). The reviewer doesn't need or want the internal model.
- Where appropriate, surface the operator-configured contact information ("Questions? Contact [operator email]").

#### What reviewers must not see

Worth being explicit, since the temptation when sharing components with the operator surface is to leak operator-context affordances:

- **No lifecycle state mention.** The reviewer doesn't care whether the session is "Activated"; they just need the form. If the session is not Activated, the page renders a generic "This review is not currently available" state, not "Session is in Draft."
- **No setup-state badges, readiness summaries, or operator-side status.**
- **No links to operator pages**, even if the reviewer happens to also be an operator on another session in the same app. The two surfaces remain distinct; an operator-reviewer who needs to switch contexts does so by navigating the URL or signing out and back in via a different entry point.
- **No mention of other reviewers, assignment structure, or cross-reviewer state.**
- **No operator-uploaded visual content** (banners, logos, custom imagery). Per the audience and identity model, visual customization is not permitted; operator presence is expressed through content (session name, instructions, institution name) within stable chrome.

### Cross-surface consistency

Some patterns from `visual_style_general.md` and the operator session chrome above carry over uniformly to all three surfaces:

- **Component library.** Buttons, cards, badges, form inputs, tables, and links all use the general spec's definitions on every surface. A submit button on a reviewer form looks identical to a submit button on an operator setup page.
- **Color palette.** Same neutrals, same accents. Lifecycle accent colors are operator-only (reviewers don't see lifecycle); other accents (blue for action, green for completion, amber for warnings) apply across all surfaces.
- **Typography.** Same type scale and font stack on all surfaces.
- **Spacing.** Same 4px grid throughout.
- **Top bar pattern.** Both operator and reviewer surfaces have a top bar with app identity (left) and user menu (right). Operator's says "Review Robin Web App (version dev)" because operators care about the version; reviewer's says "Review Robin" because they don't. Operator's user menu hosts About / Settings / Sign out; reviewer's user menu hosts My Reviews / Sign out. Same shape, different contents.

The discipline: components and visual language are uniform; chrome and navigation patterns are audience-specific. An operator and a reviewer should recognize the same app from the visual style; a quick glance at the chrome should tell each which surface they're on.

---

## Migration approach

The pre-v2 Review Robin UI used high-contrast solid-colored buttons (saturated blue, orange, red) and other patterns this spec retired. The migration sequence (now substantially complete via the v2 sweep tracked in `guide/ui_checklist.md`):

1. **Establish the palette and component primitives** in a shared stylesheet. Define colors, spacing, type scale, and core component classes (`button-primary`, `button-secondary`, `card`, `badge`, `tab`, etc.) in one place.
2. **Migrate the chrome first** — the two-row navigation, breadcrumbs, status strip, page header. The chrome appears on every session-scoped page, so migrating it once visually unifies the entire app.
3. **Migrate page-by-page**, starting with the highest-traffic pages: Home / Control Panel, then the five Setup pages. Operations pages and sub-pages follow.
4. **Retire the old styles last.** Once every page uses the new components, the old CSS classes can be removed.

A useful checkpoint: after the chrome migration but before page-body migration, screenshot every page in the app and compare. The chrome unification alone should already make the app feel substantially calmer. If it doesn't, the chrome work isn't done.

---

## Doc cross-references

- **`spec/visual_style_general.md`** — the design system this document instantiates.
- **`spec/audience_and_identity_model.md`** — audience definitions, auth posture, customization boundaries that the chrome decisions in this doc implement.
- **`spec/operator_ui_concept.md`** — page taxonomy, navigation principles, and per-page contracts for the operator surface. The two-row chrome described here implements the navigation model described there.
- **`spec/session_home.md`** — functional spec for Session Home (the per-session Control Panel), including the lifecycle display-label mapping (`ready` → "Activated") referenced above.
- **`spec/ui_elements.md`** — implementation catalogue mapping the canonical primitives in this doc to the CSS classes and templates that realise them.

---

## What this spec doesn't cover

- **Per-page detail layouts** for non-session operator pages (Settings forms, About content). These belong in functional specs for individual pages.
- **Response form internals** (reviewee navigation, instrument question types, submission validation). These belong in the Instruments Setup spec and the response-form component spec.
- **Email templates** that lead reviewers to these pages. Email artifacts have their own design considerations and are not part of the in-page UI spec.
- **Auth flow specifics** (SSO integration, magic-link generation and validation, session lifetime, MFA). These are handled at the auth layer, not the chrome layer; the chrome simply assumes authentication has happened where appropriate.
- **Future audience surfaces** (reviewees, if the app becomes symmetric; cross-session admin). These will add their own sections to this document when they ship; `spec/audience_and_identity_model.md` records them as forward-looking.
