## Part 1 — General visual style spec (portable design system)

A guide for building calm, consistent operator-facing and admin-facing UIs. The goal is restraint: the UI should feel like a clean working surface where the *content* carries the visual weight, not the chrome and not the controls.

This document is app-agnostic. It defines the design system itself: principles, palette, typography, spacing, components, and cross-cutting patterns. App-specific decisions (lifecycle states, navigation structure, domain entities) live in a companion document that references this one.

---

### Design principles

**P1 — Neutral by default, color where it carries meaning.** Most of the UI should be black text on white with subtle grey separators. Color is reserved for things that have semantic meaning the operator needs to read — state indicators, group identity, validation outcomes, destructive actions. A button that's just "submit this form" doesn't need color; a button that's "destructively replace existing data" does.

**P2 — Low contrast for chrome, higher contrast for content.** Navigation, page structure, and supporting metadata sit at low visual contrast (greys, soft tints). Page content — the data the operator is looking at, the form they're filling in — sits at higher contrast (black text, clear borders). The eye should land on content, not on the frame around it.

**P3 — Consistent component shapes, varied only by role.** Buttons all share the same shape, padding, and corner radius. They differ by *role* (primary action vs. secondary vs. destructive) through subtle treatment, not through dramatically different appearances. Same for cards, tabs, badges, inputs — one shape per component type, role expressed through tonal variation.

**P4 — Information density over decoration.** Operators are working, not browsing. The UI should pack information cleanly into available space without ornamental padding, gradient backgrounds, or decorative imagery. Whitespace exists to separate logical groups, not to make the page look airy.

**P5 — The color test.** When tempted to introduce a colored element, apply this test: *if removing the color would make the UI ambiguous or harder to scan, the color is doing work; if removing it changes nothing functional, it's decoration*. Decoration loses.

**P6 — Hover by fill.** Filled controls (solid background, white text) *lighten* on hover; outline controls (white background, colored border + text) *darken* with a subtle background tint in their role's color. Same direction across the app, applied consistently from buttons to nav anchors, so "you can click this" reads the same way everywhere.

**P7 — Recovery actions adopt the card's color family.** When an action lives inside a card whose color carries the meaning (a lock card, a danger zone), the action picks up that family rather than reasserting its own. A Primary blue button inside an amber lock card clashes; an outline-amber button continues the card's framing. Same logic for outline-red destructive buttons inside the danger zone. The card already says "this region needs care" — the action shouldn't have to repeat the color story in a different language.

---

### Color palette

Anchor the entire UI on this palette. No off-palette colors should appear without a specific documented reason.

**Neutrals (the workhorse).**
- `bg-page` — pure white or near-white (`#FFFFFF` or `#FAFAFA`). Page background.
- `bg-muted` — very light grey (`#F5F5F7` or similar). Card backgrounds, inactive tab backgrounds, status strip background.
- `border-subtle` — light grey (`#E5E7EB` or similar). Borders on cards, separators, table grid lines.
- `border-default` — medium grey (`#D1D5DB`). Borders on inputs, more prominent dividers.
- `text-primary` — near-black (`#111827` or `#1F2937`). Body text, headings.
- `text-secondary` — medium grey (`#6B7280`). Supporting text, labels, captions.
- `text-muted` — lighter grey (`#9CA3AF`). De-emphasized text, placeholder.

**Semantic accents (used sparingly, with specific meaning).** Each accent comes as a small ladder of shades so hover, marker, and dark-text variants stay on-palette without ad-hoc hex picking. Tailwind step numbers shown in parentheses for orientation.

- `accent-blue` — default accent for active states, links, primary actions. *Use sparingly* — at most one solid-blue Primary per page region.
  - `accent-blue-bg-faint` (blue-50, `#FAFCFF`) — hover surface for already-tinted cells (e.g. Home anchor).
  - `accent-blue-bg-soft` (blue-50, `#EFF6FF`) — base for tinted cells like the chrome's Home anchor.
  - `accent-blue-bg` (blue-100, `#DBEAFE`) — pill-count background, banner-info background.
  - `accent-blue-marker` (blue-300, `#93C5FD`) — active-tab underline. Lighter than full accent so the marker signals position without competing.
  - `accent-blue-light` (blue-500, `#3B82F6`) — Primary button hover (lighten).
  - `accent-blue` (blue-600, `#2563EB`) — Primary button base, link color, active-tab text.
  - `accent-blue-dark` (blue-700, `#1D4ED8`) — kept for contexts that explicitly want a darker blue.

- `accent-green` — successful states, completion indicators.
  - `accent-green-bg` (green-100, `#D1FAE5`) — pill background.
  - `accent-green-marker` (green-300, `#6EE7B7`) — Operations-row active-tab underline.
  - `accent-green` (green-600, `#059669`) — emphasis text.

- `accent-amber` — warnings that aren't errors, lock-card patterns, "needs setup" indicators. **Used as the framing color for any card surface that needs the operator's attention** — lock cards and danger zones both border in `accent-amber-dark` so warning surfaces share one visual language.
  - `accent-amber-bg` (amber-100, `#FEF3C7`) — pill background, lock-card surface.
  - `accent-amber-bg-mid` (amber-200, `#FDE68A`) — outline-amber button hover surface.
  - `accent-amber` (amber-600, `#D97706`) — emphasis text where a brighter amber is wanted.
  - `accent-amber-dark` (amber-800, `#92400E`) — pill text on `accent-amber-bg`, warning-card border, outline-amber button border + text. The "warning brown" that frames every warning surface.

- `accent-red` — destructive action confirmations, validation errors. Used **rarely** — most "negative" signals are amber, not red. Reserved for the one button that actually deletes data.
  - `accent-red-bg` (red-100, `#FEE2E2`) — destructive-button hover surface, banner-error background.
  - `accent-red-soft` (red-500, `#EF4444`) — softer red for surfaces that want to flag destructive context without alarming.
  - `accent-red` (red-600, `#DC2626`) — destructive-button border + text, banner-error border.

The accents are deliberately muted. Saturated, high-contrast colors should not appear. If a color feels saturated enough to draw the eye from across the room, dial it back.

App-specific uses of these accents (e.g., assigning `accent-blue` to a particular navigation group, mapping accents to lifecycle states) belong in the companion app-specific document.

---

### Typography

**Font stack.** System sans-serif: `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`. No custom web fonts; system fonts render fast and feel native.

**Type scale.** Tight, with few sizes:
- **H1 (page title)** — 1.5rem, semibold, `text-primary`.
- **H2 (section title)** — 1.125rem, semibold, `text-primary`.
- **Body** — 1rem, regular, `text-primary`. Default text size.
- **Small** — 0.875rem, regular, `text-secondary`. Labels, captions, dense table cells.
- **Tiny** — 0.75rem, medium weight, `text-secondary`. Badge labels, field hints.

**Weight discipline.** Use semibold (600) for headings and bold-ish emphasis. Avoid bold (700+) in body text — it shouts. Regular (400) is the default; medium (500) is for badges and small structural labels.

**Line height.** 1.5 for body text, 1.3 for headings. Don't tighten further; the UI is for reading.

---

### Spacing

A 4px base grid. Spacing values: 4, 8, 12, 16, 24, 32, 48, 64. Stick to these; off-grid spacing creates the subtle visual noise that makes a UI feel sloppy.

- **Tight (4–8px)** — between a label and its input, between a badge and surrounding text.
- **Normal (12–16px)** — internal padding of cards, gaps between adjacent controls in a row.
- **Loose (24–32px)** — between major sections of a page, between chrome and page content.
- **Page (48–64px)** — top of page to first content, between distinct page regions.

Card internal padding: 16px or 24px depending on density. Don't go lower; cramped cards feel anxious.

---

### Components

**Buttons.**

All buttons share: 8px vertical padding, 16px horizontal padding, 6px corner radius, medium font weight (500), single-line label.

- **Primary.** Solid `accent-blue` background, white text. Used for the page's *single* main affirmative action — *at most one* per page region. "Submit this form" is *not* enough to qualify; routine submits like "Upload" should be Secondary.
- **Secondary.** White background, `border-default` border, `text-primary` text. The default button. Used for everything that isn't the single primary action: "Cancel," "Edit," "View detail," routine submits.
- **Destructive.** White background, `accent-red` border, `accent-red` text. For the *confirmation step* of destructive actions, not for the trigger. The trigger is a normal secondary button; clicking it surfaces a confirmation where the destructive button appears.
- **Outline-amber (recovery action inside a colored card).** White background, `accent-amber-dark` border, `accent-amber-dark` text. Per **P7**, recovery actions inside a lock card or other warning-framed card adopt the card's color family. Used e.g. for "Revert to draft" inside a lock card.
- **Disabled.** Same shape as the role variant; reduced opacity (0.5), `cursor: not-allowed`, `pointer-events: none`. One rule covers `<button disabled>`, `<a class="btn disabled" aria-disabled="true">`, and any role variant.

**Hover** (per **P6**):
- *Filled buttons* (Primary, any future filled role): lighten — bg/border move one shade lighter (e.g. `accent-blue` → `accent-blue-light`).
- *Outline buttons* (Secondary, Destructive, Outline-amber): darken — background gains a subtle tint in the role's family (`bg-muted` for Secondary, `accent-red-bg` for Destructive, `accent-amber-bg-mid` for Outline-amber). Border + text stay put.

The same direction is used for tinted nav cells (e.g. the chrome's Home anchor lightens from `accent-blue-bg-soft` to `accent-blue-bg-faint` on hover).

**Cards.**

White background, `border-default` 2px border, 8px corner radius, 16–24px padding. No drop shadows; the border is enough. Card titles in H2 sit at the top of the card with 16px of space below them before content.

(Border is 2px rather than 1px because at 1px the card edge gets visually swallowed by the table grid lines and form borders nearby.)

**Lock card variant.** Same card shape, but with `accent-amber-bg` light background and `accent-amber-dark` border (the warning brown). Used for surfaces that are intentionally non-interactive in the current state. Explanatory text and (if applicable) recovery action inside; the recovery action follows **P7** and uses the outline-amber button.

**Danger-zone card variant.** Same card shape, white background, `accent-amber-dark` border (same warning brown as the lock card — both warning-framed surfaces share one visual language), H2 in `accent-amber-dark`. The destructive button *inside* the card stays in its own role color (outline `accent-red`) — the brown frames the surface; the red marks the action that actually deletes data.

**Tabs.**

- Tab labels at small text size, semibold (600).
- Inactive tabs: `text-secondary` on the row's tinted background.
- Hovered tab: `text-primary` with a subtle white-tint background on the row strip (matches **P6** — outline-style hover lightens the surface).
- Active tab: `text-primary` with a short inset underline in the row's *marker* tone (`accent-blue-marker` / `accent-green-marker`), not the full accent. The marker is one shade lighter so it signals position without competing with the label.
- Row backgrounds (if multi-row navigation is used): very subtle tint of the row's accent color (5% opacity).
- Row labels (if used): tiny text size, bold (700), uppercase, `text-muted` when inactive, `text-primary` when the row is active *or* the cursor is over any tab in the row's strip (use a `:has()` selector so hovering a tab previews the row's emphasis without transferring active state).

**Badges (status pills).**

Small inline labels for state. 2px vertical padding, 8px horizontal padding, 9999px corner radius (fully pill-shaped), tiny text size, medium weight (500), `text-transform: uppercase`. Used inline in copy too — e.g. "Yes, delete the existing **3 reviewers** and **27 assignments**" wraps the count phrases as pills so the eye lands on the numbers without bolding the whole sentence.

- **Counts** (numeric values): `accent-blue-bg` background, `text-primary` text. The blue tint signals "this is information" without using a state color.
- **Empty / missing** indicators: `accent-amber-bg` background, `accent-amber-dark` text. Same brown the warning cards use for their borders, so chips and surfaces share one warning language.
- **Lifecycle / state indicators**: respective semantic accent — see app-specific document for the per-state mapping.
- **Success / completion**: `accent-green-bg` background, `accent-green` text.

**Forms.**

- Inputs: white background, `border-default` border, 6px radius, 8px vertical / 12px horizontal padding, body text size.
- Focus state: `accent-blue` border, no thick outline ring; just the border color change plus a subtle 1px box-shadow in `accent-blue` at low opacity if more emphasis is needed.
- Labels: above the input, small text size, `text-primary`, medium weight, 4px gap to the input.
- Helper text: below the input, small text size, `text-secondary`.
- Error state: `accent-red` border, error message in `accent-red` below the input at small size.

**Tables.**

- Header row: `bg-muted` background, small text, medium weight, `text-secondary`.
- Body rows: white background, `border-subtle` 1px bottom border per row.
- No alternating row colors (zebra striping); the row borders are enough.
- Cell padding: 12px vertical, 16px horizontal.
- Row hover: very subtle `bg-muted` background tint.

**Links.**

- Default: `accent-blue` text, no underline.
- Hover: `accent-blue` text, underline appears.
- Visited: same as default; no distinct visited state in operator UI.
- Within prose: same treatment.
- Breadcrumb links: `accent-blue`, no underline; current/last segment is `text-primary` non-link.

---

### Patterns

**Status strip.** A horizontal line of compact key-value pairs separated by middle-dot characters (`·`). Small text size, `text-secondary` for labels, badges for values. `bg-muted` background, `border-subtle` top and bottom borders. Sits between the chrome and the page body. The composition (which keys appear, in what order) is app-specific.

**Breadcrumb.** Top-of-page navigation showing path. `accent-blue` for clickable segments, `text-primary` for the current page. Separator: ` / ` with surrounding spaces, in `text-muted`. Small text size. No "home icon" or other ornamentation.

**Empty state.** When a page or card would render empty, show a brief explanatory message in `text-secondary` rather than a blank surface. If there's an action that resolves the empty state, link to it. No illustrations, no oversized icons, no marketing copy.

**Confirmations.** Destructive confirmations render *inline* where the action was triggered, not as modal dialogs. The triggering button transforms into a confirmation row: a short explanatory message, a destructive-styled "Confirm" button, and a secondary "Cancel" button.

**Loading states.** Brief operations (under 1 second): no loading indicator; let the action complete and the UI update. Longer operations: replace the triggering button with a disabled-state copy of itself with a small spinner inline, leaving the rest of the page interactive. Never use full-page loading overlays for individual actions.

---

### What to retire (when revamping an existing UI)

- **High-contrast solid-colored buttons** (saturated blue, orange, red fills). Replace with the muted button hierarchy above.
- **Multiple colors competing on one page** for non-semantic decoration. Reduce to neutrals plus accents that carry meaning.
- **Drop shadows and elevation effects.** Cards stand out via borders, not shadows.
- **Decorative icons.** Icons appear only where they carry meaning the text alone doesn't.
- **Heavy borders or thick rules.** Borders are 1px; horizontal rules are 1px in `border-subtle`.
- **Mixed corner radii.** All components use the radii defined above. Mixed radii on a single page reads as inconsistency.

---

### What this spec doesn't cover

- **App-specific decisions** (lifecycle states, navigation structure, domain entities, status strip composition, page header conventions). Those live in a companion app-specific document.
- **Specific copy** (button labels, error messages). Those belong in functional specs for individual pages.
- **Responsive behavior.** Default assumption is desktop-first; mobile / narrow-viewport support is a separate spec.
- **Accessibility specifics beyond color contrast.** The palette is chosen to meet WCAG AA contrast for body text, but full accessibility review (keyboard navigation, screen reader labeling, focus management) is its own work.
- **Animation and motion.** Default is no motion beyond instant state changes.

The intent throughout: when in doubt, pick the calmer, more neutral, more consistent option.

---
---

## Part 2 — Review Robin Web App: visual style application

This document instantiates the general visual style spec for Review Robin specifically. It defines the app-specific decisions that the general spec leaves open: which accents map to which navigation groups, how lifecycle states render, what the status strip contains, and so on.

Read this document alongside the general visual style spec. Where this document is silent, the general spec applies.

---

### App-specific accent assignments

The general spec defines four semantic accents (blue, green, amber, red). Review Robin assigns them as follows:

- **`accent-blue`** — the **Setup** navigation group identity. Active states across the app. Links. Primary actions.
- **`accent-green`** — the **Operations** navigation group identity. Successful states. The `ready` lifecycle indicator.
- **`accent-amber`** — setup-incomplete indicators (`NONE`, `NOT SET UP`). The yellow lock card pattern. Lifecycle-locked surfaces.
- **`accent-red`** — destructive action confirmations (e.g., replacing existing setup data via Quick Setup). Validation errors. Used rarely.

Setup and Operations are two parallel series of pages (see UI concept doc for the taxonomy). The blue/green pairing for these two groups is the app's most visible color decision and should be preserved across the entire chrome.

---

### Lifecycle state colors

Sessions move through four lifecycle states. Each renders as a badge in the status strip and (where relevant) inline elsewhere:

- **`draft`** — warning amber (`accent-amber-dark` text on `accent-amber-bg` background). Same treatment as `.pill-empty`. The session is *not ready for action* — setup work remains, the operator's eye should land on the badge as a "needs work" cue rather than a neutral "nothing happening here" grey.
- **`validated`** — muted blue (`accent-blue` text on `accent-blue-bg` background). Setup is complete and validated; ready to activate.
- **`ready`** — muted green (`accent-green` text on `accent-green-bg` background). The session is live.
- **`closed`** — neutral grey (`text-secondary` on `bg-muted`). Indicates finality; the work is done and the surface is no longer actionable.

Lifecycle state always appears first in the status strip, leftmost, before per-entity counts.

---

### Navigation chrome (two-row layout)

The session-scoped chrome consists of:

**Top region** (above the chrome): breadcrumb in the standard pattern.

**Chrome itself**: a double-height **Home** anchor on the left, two rows of phase tabs to its right.

```
┌────────┬─ SETUP ▶      [Reviewers][Reviewees][Assignments][Instruments][Email Template]
│  Home  │
└────────┴─ OPERATIONS ▶ [Preview][Invitations][Monitoring][Outbox]
```

Specifics:
- **Home** is double-height to span both rows, signalling that it's one level up from the phase tabs rather than a peer of any of them.
- **Row labels** ("SETUP", "OPERATIONS") sit at the left edge of each row, in tiny text, medium weight. The `▶` glyph sits adjacent to indicate the row's tabs follow.
- **Row backgrounds** use the row's accent color at 5% opacity (`accent-blue` for Setup, `accent-green` for Operations).
- **Active tab** uses a 2px underline in the row's accent color.
- **Active row** (the one containing the active tab): row label renders at `text-primary` instead of `text-secondary`; the `▶` glyph emphasizes correspondingly.
- **Hovering a tab** in a non-active row previews-emphasizes that row's label without transferring active state — gives the operator a sense of "this is the row you're about to enter."
- **Same tab shape** across both rows. Differences between rows are carried by row labels and row tints, not by tab shape.

**On Home itself**: chrome renders in the same shape, with no tab active. Both rows remain visible and clickable.

**On sub-pages of Home** (Edit Session, Validate detail): chrome renders normally. The sub-page identifies itself in the page body via H1, not in the chrome.

**On Preview pages** that are children of a Setup tab: chrome renders normally with the parent Setup tab active.

---

### Status strip

The status strip sits below the chrome and above the page body on all session-scoped pages. Composition, left to right:

```
Session: [LIFECYCLE_BADGE]  ·  Reviewers: [count]  ·  Reviewees: [count]  ·  Assignments: [count or NONE]  ·  Instruments: [count]  ·  Email Template: [count or NOT SET UP]
```

Lifecycle badge first, then the five Setup entities in canonical order (Reviewers, Reviewees, Assignments, Instruments, Email Template). Counts use the standard count-badge styling; missing/empty states use the amber empty-indicator badge.

Operations-side state (sent invitations, responses received, etc.) does **not** appear in the status strip. The strip is a setup-readiness summary, not a running-session dashboard. Operations state lives on the Operations pages themselves.

---

### Page header conventions

Page-level identity is established by the breadcrumb and the active chrome tab in combination. Most pages do not need a redundant H1 echoing the active tab name.

Exceptions:
- **Home (Session Home / Control Panel)** — H1 is the session name, since the session is what Home represents. Lifecycle state appears as a badge adjacent to or below the H1.
- **Sub-pages of Home** (Edit Session, Validate detail) — H1 is the sub-page name ("Edit Session," "Validate Setup"), since the chrome doesn't distinguish sub-pages from Home.
- **Operator's Overview** (sessions list) — H1 is "Sessions" or similar, since this page sits outside session-scoped chrome.
- **Preview pages** that are children of a Setup tab — H1 is the preview's name ("Reviewer surface preview"), not the parent tab's name.

For all other session-scoped pages (the five Setup pages, the Operations pages), no H1 is needed. The chrome tab and breadcrumb together establish identity.

---

### Warning surfaces — shared brown framing

Two card variants in the app's vocabulary frame "this region needs care": the **lock card** (intentionally non-interactive due to lifecycle) and the **danger-zone card** (groups destructive actions). Both border in `accent-amber-dark` (the warning brown), so the operator's eye recognises the same visual category whether reading "you can't change this right now" or "here's where you delete data". The interior treatments differ — the lock card has the `accent-amber-bg` tinted surface; the danger zone has white — but the framing is one.

Per **P7**, recovery / primary actions inside these cards adopt the card's color family:

- **Inside a lock card**: outline-amber button (e.g. "Revert to draft"). A solid Primary blue inside an amber card clashes; the outline-amber action continues the framing.
- **Inside a danger zone**: outline-red Destructive button. Same principle applied to the destructive role — the brown frames the surface; the red marks the action that actually deletes data.

#### Lock card uses

Used when a page or section is reachable but its actions are disabled because the session lifecycle locks them.

- **On Setup pages** when session is `ready` or `closed`: lock card explains that setup is locked and offers a "Revert to draft" action where appropriate.
- **On Operations pages** when session is `draft` or `validated`: lock card explains that operations are unavailable until the session is activated, and links to Home where the Activate action lives.
- **On the Quick Setup card on Home** when session is `ready` or `closed`: same as Setup pages.
- **On the send-test affordance** within the Reviewer Experience Preview when session is `closed`: same pattern.

The lock card pattern is consistent across all of these. Its prominence and explanatory copy adapt to the specific case, but its visual treatment does not.

#### Danger-zone card uses

Groups the destructive actions for a given Setup entity (Delete all reviewers / reviewees / assignments / instruments) and the session-level destructive actions (Delete data, Delete session). H2 is "Danger Zone" in `accent-amber-dark`. Lives at the bottom-right of the page (or in the bottom row of a `.bottom-grid`) so it stays visually grouped with the entity it operates on but isn't the first thing the eye lands on.

---

### Migration approach

The current Review Robin UI uses high-contrast solid-colored buttons (saturated blue, orange, red) and other patterns this spec retires. The migration sequence:

1. **Establish the palette and component primitives** in a shared stylesheet. Define colors, spacing, type scale, and core component classes (`button-primary`, `button-secondary`, `card`, `badge`, `tab`, etc.) in one place.
2. **Migrate the chrome first** — the two-row navigation, breadcrumbs, status strip, page header. The chrome appears on every session-scoped page, so migrating it once visually unifies the entire app.
3. **Migrate page-by-page**, starting with the highest-traffic pages: Home / Control Panel, then the five Setup pages. Operations pages and sub-pages follow.
4. **Retire the old styles last.** Once every page uses the new components, the old CSS classes can be removed.

A useful checkpoint: after the chrome migration but before page-body migration, screenshot every page in the app and compare. The chrome unification alone should already make the app feel substantially calmer. If it doesn't, the chrome work isn't done.

---

### Doc cross-references

- **General visual style spec** — the design system this document instantiates.
- **`spec/ui_concept.md`** — the page taxonomy and navigation principles. The two-row chrome described here implements the navigation model described there.
- **`spec/operator_map.md`** — page-level chrome and per-page layout contracts. Style decisions here inform layout decisions there.

---

The intent: this document captures only the Review Robin-specific decisions. When starting a new app, copy the general spec unchanged and write a new app-specific document of comparable size to this one. Common decisions stay common; app-specific decisions are local.

---
---

## Part 3 — Non-session and reviewer surface chrome

This document extends the visual style spec to cover surfaces outside
the per-session operator chrome:

- **Non-session operator pages** — Operator's Overview (sessions
  list), About, Settings, Create Session.
- **Reviewer-facing pages** — the surfaces a reviewer sees when
  signing into Review Robin and responding to a session.

Read alongside Part 1 (general visual style), Part 2 (Review Robin
operator session chrome), and the **audience and identity model
doc** (`spec/audience_and_identity_model.md`), which establishes the
audience definitions, auth posture, and customization boundaries
that this document's chrome decisions implement.

The visual vocabulary defined in Part 1 (palette, typography,
spacing, components) applies uniformly across all surfaces. What
differs by surface is the *chrome* — the framing and navigation
patterns that surround page content.

### Audience surface map

The app comprises three distinct surface types, each with its own
chrome conventions:

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
operator  (this doc)          response form
pages                         (this doc)
(Part 2)
```

Within each surface, components from Part 1 are used identically;
chrome and structural patterns differ.

---

### Non-session operator pages

Pages the operator visits when *not* working inside a specific
session: the Sessions list (Operator's Overview), the Create Session
form, About, Settings, and any future app-level pages.

#### Chrome philosophy

**Minimal and quiet.** Non-session operator pages are visited
rarely and usually as detours from the operator's main work (which
happens inside sessions). The chrome should not invest visual
weight in navigating between them, since operators rarely navigate
between non-session pages directly.

The two-row session chrome (Setup row, Operations row) **does not
appear** on these pages. The status strip does not appear.
Lifecycle badges do not appear. These are session-scoped affordances
and have no meaning outside a session.

#### Top bar

The existing top bar pattern continues:

- **Left:** "Review Robin Web App (version dev)" — small, in
  `text-secondary`. App identity and version, modest.
- **Right:** A small **user menu** containing:
  - "Signed in as [Operator Name]" (informational, not a link).
  - About — opens About page, with return-to-origin behavior (see
    below).
  - Settings — opens Settings page, with return-to-origin behavior.
  - Sign out — ends the operator's session.

The user menu can render as inline links (when the menu has three
or four items) or as a dropdown triggered by clicking the operator
name. Inline is preferred while the menu is small; promote to
dropdown when it would otherwise crowd the top bar.

#### Return-to-origin behavior

About and Settings are detour destinations: the operator opens them
to consult or adjust something, then wants to return to whatever
they were doing. The pattern:

- When the operator opens About or Settings, the URL captures the
  origin via a query parameter (e.g., `?return_to=/sessions/abc123`)
  or session state.
- The About/Settings page renders a clear "Back" affordance — a
  link in `accent-blue` near the top of the page body, labeled
  with context where possible: "← Back to Sessions" or "← Back
  to Student Associate Selection 2026 Peer Review".
- Clicking the affordance returns the operator to the origin URL.
- If no origin is recorded (e.g., the operator deep-linked to
  Settings), the affordance defaults to "← Back to Sessions" —
  the app's natural lobby.

This is a small piece of plumbing but it changes the affordance
from "trip down a rabbit hole" to "quick consultation." Operators
learn to use About and Settings without losing their place.

#### Page structure

Non-session operator pages share a simple structure:

1. **Top bar** (as above).
2. **Page body**:
   - Optional return-to-origin affordance (top-left of body).
   - **H1 page title.**
   - Page content.

No breadcrumb is needed; the page hierarchy is too shallow. The H1
and the user menu together orient the operator sufficiently.

#### Operator's Overview (Sessions list)

This page is the operator's "lobby" and is the natural landing page
when signing in or returning from a session. It deserves slightly
more care than other non-session pages, but uses the same chrome.

- **H1:** "Sessions" or "My Sessions".
- **Body:** A list or grid of session cards. Each card shows:
  - Session name (linked to that session's Home).
  - Lifecycle state badge (using the display labels: Draft,
    Validated, Activated, etc.).
  - Deadline.
  - Brief setup readiness summary (count badges or a single status
    summary).
- **Create Session affordance:** primary button in the top-right of
  the list area, labeled "New Session" or "Create Session". When
  the list is empty, this becomes the page's prominent affordance,
  rendered larger and with explanatory text.

The session cards reuse the Card component from Part 1; the
lifecycle badges reuse the badge component with the lifecycle color
treatments from Part 2.

#### About / Settings / Create Session

Each is a single page with the standard non-session chrome. Body
content is whatever the page does:

- **About:** version info, links to documentation, changelog.
  Read-only.
- **Settings:** operator preferences, app-level configuration. Form
  with standard form components.
- **Create Session:** a form for creating a new session. Submitting
  takes the operator to the new session's Home.

If any of these grow into multi-page sets later (e.g., Settings
with multiple categories), they may need their own internal
navigation — but this is a future concern, not a current one. The
first such page-set to land will define the pattern.

---

### Reviewer-facing pages

The surfaces a reviewer sees when signing into Review Robin and
responding to a session. Per the **audience and identity model**,
reviewers are authenticated users of the app — not anonymous form
respondents — but they spend most of their time in task-focused
surfaces rather than in app-level navigation. The chrome reflects
this: app identity is persistent and visible enough to function as
a trust anchor, but unobtrusive enough that the reviewer's
attention stays on their work.

#### Chrome philosophy

**Light but recognizable.** The reviewer's experience is minimal in
structure but consistent in identity. Across sessions, the
reviewer-facing chrome looks the same; per-session variation is
limited to content (session name, instructions, instrument names)
within stable chrome.

What this means in practice:

- Review Robin identity is **persistent and visible** but small —
  enough for the reviewer to recognize the app, not enough to
  dominate the page.
- Per-session operator customization is **content-only** — session
  name, optional welcome message, optional institution name. No
  visual customization (colors, layout, branding imagery). See the
  audience and identity model doc for the rationale.
- Operator chrome (two-row session navigation, status strips,
  lifecycle badges) does **not** appear on reviewer pages.
  Reviewers don't navigate the operator's structure; they have
  their own.

#### Top bar

Reviewer-facing pages have a top bar, but lighter than the
operator's:

- **Left:** "Review Robin" — small, `text-secondary`. App identity
  as a trust anchor. No version info (operators care about that;
  reviewers don't).
- **Right:** A small **user menu** containing:
  - "Signed in as [Reviewer Name]" — informational. Lets the
    reviewer confirm correct identity (important on shared
    computers, useful in institutions where SSO might silently
    log the wrong person in).
  - "My Reviews" — link back to the reviewer's review list (only
    rendered when the reviewer has more than one review pending or
    completed; suppressed when there's just one).
  - "Sign out" — ends the reviewer's session.

The top bar is consistent across all reviewer pages. Its presence
is what makes the reviewer surface recognizable as Review Robin
across sessions.

#### Sign-in surface

The first page a reviewer sees, reached by clicking a sign-in link
in their invitation email or by direct URL. This page has elevated
trust significance: the reviewer is about to authenticate, and they
need to verify they're on the right system before doing so.

**Chrome:**

- Standard top bar with Review Robin identity (no user menu yet,
  since the reviewer isn't signed in).
- Page body centered on the sign-in flow:
  - **H1:** "Sign in to Review Robin" or similar.
  - Brief explanation of the auth flow ("You'll be redirected to
    your institution's sign-in page.").
  - Primary action: "Sign in with [Institution]" (SSO trigger,
    branded with the institution name when known from the
    invitation context).
  - Secondary affordance: magic-link option, for reviewers without
    SSO access. Less prominent than the SSO action.

After authentication, the reviewer is delivered to either:

- The specific response surface they were invited to (if the
  sign-in link was for a specific session), or
- Their reviewer review list (if no specific destination is
  associated with the sign-in).

#### Reviewer's review list

The reviewer's "home" after sign-in. A simple list of pending and
recent reviews.

**Chrome:** standard reviewer top bar + page body.

**Body:**

- **H1:** "My Reviews" or "Your Reviews".
- A list of review cards, each showing:
  - Session name (linked to that session's response surface for
    this reviewer).
  - Deadline.
  - Completion status (e.g., "Not started," "In progress: 2 of 5
    reviewees," "Completed").
  - Optional: institution name if relevant for cross-institution
    reviewers.
- Empty state when the reviewer has no pending reviews: "You have
  no pending reviews." in `text-secondary`. Not an error; just
  informational.

**Deep-linking behavior:** when a reviewer signs in via a
session-specific invitation link and has only one pending review,
the sign-in flow can deep-link them past the review list to the
response surface directly. The list exists for the cases where
it's useful (multiple reviews, returning to find a specific one);
it's not a forced waypoint for every visit.

#### Response surface (the response form)

The main task surface, where the reviewer completes their
evaluations.

**Chrome:**

- Standard reviewer top bar (Review Robin identity + user menu).
- **Page header** with session context:
  - Session name — rendered at H1 size.
  - Deadline — small reminder in `text-secondary`, near the
    session name.
  - Optional: institution or operator name (small,
    `text-secondary`) — useful for reviewers participating across
    institutions or with multiple operators in mind.
  - Optional: operator-configured welcome message / instructions,
    shown above the form on first visit. Plain text or limited
    markdown.
- **Instrument tab strip** (only when the session has more than
  one instrument; see below).
- **Form body.**

##### Multi-instrument navigation

A session may have multiple instruments for a reviewer to complete
across their assigned reviewees. This requires more than one page
facing the reviewer, and therefore some navigation chrome.

**Pattern: a single horizontal tab strip.**

Below the page header, one row of tabs — one tab per instrument
the reviewer needs to complete:

```
Session: Student Associate Selection 2026 Peer Review · Deadline: 2026-07-01
─────────────────────────────────────────────────────────────────
[Skills Assessment] [Cultural Fit] [Final Recommendation]
─────────────────────────────────────────────────────────────────
```

Specifics:

- **Tab labels** are the instrument names, kept short.
- **Active tab** uses the same underline-and-color-emphasis pattern
  as the operator session chrome (Part 2), but in a single row.
  Reuses the tab component from Part 1.
- **Per-tab completion indicator.** A small badge or dot adjacent
  to the tab label shows whether that instrument is incomplete, in
  progress, or complete:
  - No badge: not started.
  - In progress (some responses entered, not all): muted dot
    indicator.
  - Complete: small check icon or `accent-green` badge.

  This lets the reviewer track progress at a glance without a
  separate dashboard.
- **Tab order** matches whatever order the operator configured in
  the Instruments Setup page. The reviewer is not free to reorder;
  the tabs are determined by the session's setup.
- **Free movement between tabs.** The reviewer can switch tabs at
  any time. Responses are saved per-tab as they go (auto-save or
  on-tab-change save — implementation detail, but the reviewer
  should never lose work by switching tabs).
- **No tab is "locked" by another tab's completion.** The reviewer
  can complete instruments in any order.

**When there is only one instrument**, the tab strip does not
render. A single-instrument session shows just the page header and
the form directly; introducing a one-tab strip would be visual
noise.

##### Per-reviewee navigation within an instrument

A separate concern: within a single instrument, the reviewer may
need to evaluate multiple reviewees. This is *content-level*
navigation, not chrome-level. It belongs inside the instrument's
form, not in the page chrome.

Pattern options for in-form per-reviewee navigation:

- **One reviewee per page**, with "Next reviewee" / "Previous
  reviewee" affordances at the bottom of the form, plus a small
  indicator ("Reviewee 2 of 7") near the top.
- **All reviewees on one page**, in a long scrolling form with
  each reviewee as a section.
- **Sidebar of reviewees** within the form, letting the reviewer
  jump between them.

The choice depends on instrument complexity and reviewee count and
is properly the concern of the response-form component, not the
chrome. Flagging here so it's clear the chrome stops at the
instrument-level tab strip; what happens *inside* the form is the
form's design.

#### Submission confirmation

Shown after the reviewer submits all required responses for the
session.

**Chrome:** standard reviewer top bar + page body.

**Body:**

- Brief acknowledgement: "Thank you. Your responses have been
  received."
- Optional: summary ("You completed 3 instruments across 7
  reviewees.").
- Optional: link back to the reviewer's review list, if other
  reviews remain.
- No tab strip; the task is complete.

Tone: calm and brief. The reviewer is finished; the page should
confirm and let them go.

#### Error / expired states

Shown when a sign-in link is invalid, the session is not in
Activated state, or the deadline has passed.

**Chrome:** standard reviewer top bar (with whatever auth state
applies — signed in or not) + page body.

**Body:**

- Brief explanation in plain language. Examples:
  - "This review is no longer accepting responses. The deadline
    passed on [date]."
  - "This sign-in link is no longer valid. Request a new one from
    the session organizer."
  - "This review is not currently available. Try again later or
    contact the session organizer."
- Avoid technical detail (no "Session is in Draft state" — that's
  operator vocabulary). The reviewer doesn't need or want the
  internal model.
- Where appropriate, surface the operator-configured contact
  information ("Questions? Contact [operator email]").

#### What reviewers must not see

Worth being explicit, since the temptation when sharing components
with the operator surface is to leak operator-context affordances:

- **No lifecycle state mention.** The reviewer doesn't care whether
  the session is "Activated"; they just need the form. If the
  session is not Activated, the page renders a generic "This
  review is not currently available" state, not "Session is in
  Draft."
- **No setup-state badges, readiness summaries, or operator-side
  status.**
- **No links to operator pages**, even if the reviewer happens to
  also be an operator on another session in the same app. The two
  surfaces remain distinct; an operator-reviewer who needs to
  switch contexts does so by navigating the URL or signing out and
  back in via a different entry point.
- **No mention of other reviewers, assignment structure, or
  cross-reviewer state.**
- **No operator-uploaded visual content** (banners, logos, custom
  imagery). Per the audience and identity model, visual
  customization is not permitted; operator presence is expressed
  through content (session name, instructions, institution name)
  within stable chrome.

---

### Cross-surface consistency

Some patterns from Part 1 and Part 2 carry over uniformly to all
three surfaces:

- **Component library.** Buttons, cards, badges, form inputs,
  tables, and links all use the Part 1 definitions on every
  surface. A submit button on a reviewer form looks identical to a
  submit button on an operator setup page.
- **Color palette.** Same neutrals, same accents. Lifecycle accent
  colors are operator-only (reviewers don't see lifecycle); other
  accents (blue for action, green for completion, amber for
  warnings) apply across all surfaces.
- **Typography.** Same type scale and font stack on all surfaces.
- **Spacing.** Same 4px grid throughout.
- **Top bar pattern.** Both operator and reviewer surfaces have a
  top bar with app identity (left) and user menu (right).
  Operator's says "Review Robin Web App (version dev)" because
  operators care about the version; reviewer's says "Review Robin"
  because they don't. Operator's user menu hosts About / Settings
  / Sign out; reviewer's user menu hosts My Reviews / Sign out.
  Same shape, different contents.

The discipline: components and visual language are uniform; chrome
and navigation patterns are audience-specific. An operator and a
reviewer should recognize the same app from the visual style; a
quick glance at the chrome should tell each which surface they're
on.

---

### What this part doesn't cover

- **Per-page detail layouts** for non-session operator pages
  (Settings forms, About content). These belong in functional
  specs for individual pages.
- **Response form internals** (reviewee navigation, instrument
  question types, submission validation). These belong in the
  Instruments Setup spec and the response-form component spec.
- **Email templates** that lead reviewers to these pages. Email
  artifacts have their own design considerations and are not part
  of the in-page UI spec.
- **Auth flow specifics** (SSO integration, magic-link generation
  and validation, session lifetime, MFA). These are handled at the
  auth layer, not the chrome layer; the chrome simply assumes
  authentication has happened where appropriate.
- **Future audience surfaces** (reviewees, if the app becomes
  symmetric; cross-session admin). These will add their own
  sections to this document when they ship; the audience and
  identity model doc records them as forward-looking.
