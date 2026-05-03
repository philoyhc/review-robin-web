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

**Semantic accents (used sparingly, with specific meaning).**
- `accent-blue` — muted blue (`#2563EB` for emphasis, `#DBEAFE` for backgrounds). Default accent for active states, links, primary actions.
- `accent-green` — muted green (`#059669` for emphasis, `#D1FAE5` for backgrounds). Successful states, completion indicators.
- `accent-amber` — muted amber (`#D97706` for emphasis, `#FEF3C7` for backgrounds). Setup-incomplete indicators, warnings that aren't errors, lock-card patterns.
- `accent-red` — muted red (`#DC2626` for emphasis, `#FEE2E2` for backgrounds). Destructive action confirmations, validation errors. Used **rarely** — most "negative" signals are amber, not red.

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

All buttons share: 8px vertical padding, 16px horizontal padding, 6px corner radius, medium font weight, single-line label.

- **Primary.** Solid `accent-blue` background, white text. Used for the page's main affirmative action — at most one per page region.
- **Secondary.** White background, `border-default` border, `text-primary` text. The default button. Used for everything that isn't the single primary action: "Cancel," "Edit," "View detail."
- **Destructive.** White background, `accent-red` border, `accent-red` text. For the *confirmation step* of destructive actions, not for the trigger. The trigger is a normal secondary button; clicking it surfaces a confirmation where the destructive button appears.
- **Disabled.** Same shape as the role variant; reduced opacity (0.5) and `cursor: not-allowed`. No fill change beyond opacity.

**Cards.**

White background, `border-subtle` 1px border, 8px corner radius, 16–24px padding. No drop shadows; the border is enough. Card titles in H2 sit at the top of the card with 16px of space below them before content.

**Lock card variant.** Same card shape, but with `accent-amber` light background and `accent-amber` border. Used for surfaces that are intentionally non-interactive in the current state. Lock card icon on the left; explanatory text and (if applicable) recovery action on the right.

**Tabs.**

- Tab labels at small text size, medium weight.
- Inactive tabs: `text-secondary` on `bg-muted` row background.
- Active tab: `text-primary` with a 2px underline in the relevant accent color.
- Row backgrounds (if multi-row navigation is used): very subtle tint of the row's accent color (5% opacity).
- Row labels (if used): tiny text size, medium weight, `text-secondary` when inactive, `text-primary` when the row is active or hovered.

**Badges (status pills).**

Small inline labels for state. 2px vertical padding, 8px horizontal padding, 9999px corner radius (fully pill-shaped), tiny text size, medium weight.

- **Counts** (numeric values): `bg-muted` background, `text-primary` text.
- **Empty/missing** indicators: `accent-amber` light background, `accent-amber` text.
- **State indicators**: respective semantic accent color.
- **Success / completion**: `accent-green` light background, `accent-green` text.

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

- **`draft`** — neutral grey (`text-secondary` on `bg-muted`). The default working state.
- **`validated`** — muted blue (`accent-blue` text on `accent-blue` light background). Setup is complete and validated; ready to activate.
- **`ready`** — muted green (`accent-green` text on `accent-green` light background). The session is live.
- **`closed`** — neutral grey, slightly darker than draft to indicate finality.

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

### Yellow lock card pattern

Used when a page or section is reachable but its actions are disabled because the session lifecycle locks them. Standard application of the general spec's lock card variant, with Review Robin specifics:

- **On Setup pages** when session is `ready` or `closed`: lock card explains that setup is locked and offers a "Revert to draft" action where appropriate.
- **On Operations pages** when session is `draft` or `validated`: lock card explains that operations are unavailable until the session is activated, and links to Home where the Activate action lives.
- **On the Quick Setup card on Home** when session is `ready` or `closed`: same as Setup pages.
- **On the send-test affordance** within the Reviewer Experience Preview when session is `closed`: same pattern.

The lock card pattern is consistent across all of these. Its prominence and explanatory copy adapt to the specific case, but its visual treatment does not.

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
