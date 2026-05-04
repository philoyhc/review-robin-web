# Visual style — general design system (portable)

A guide for building calm, consistent operator-facing and admin-facing UIs. The goal is restraint: the UI should feel like a clean working surface where the *content* carries the visual weight, not the chrome and not the controls.

This document is app-agnostic. It defines the design system itself: principles, palette, typography, spacing, components, and cross-cutting patterns. App-specific decisions (lifecycle states, navigation structure, domain entities) live in `spec/visual_style_rrw.md` for Review Robin specifically.

---

## Design principles

**P1 — Neutral by default, color where it carries meaning.** Most of the UI should be black text on white with subtle grey separators. Color is reserved for things that have semantic meaning the operator needs to read — state indicators, group identity, validation outcomes, destructive actions. A button that's just "submit this form" doesn't need color; a button that's "destructively replace existing data" does.

**P2 — Low contrast for chrome, higher contrast for content.** Navigation, page structure, and supporting metadata sit at low visual contrast (greys, soft tints). Page content — the data the operator is looking at, the form they're filling in — sits at higher contrast (black text, clear borders). The eye should land on content, not on the frame around it.

**P3 — Consistent component shapes, varied only by role.** Buttons all share the same shape, padding, and corner radius. They differ by *role* (primary action vs. secondary vs. destructive) through subtle treatment, not through dramatically different appearances. Same for cards, tabs, badges, inputs — one shape per component type, role expressed through tonal variation.

**P4 — Information density over decoration.** Operators are working, not browsing. The UI should pack information cleanly into available space without ornamental padding, gradient backgrounds, or decorative imagery. Whitespace exists to separate logical groups, not to make the page look airy.

**P5 — The color test.** When tempted to introduce a colored element, apply this test: *if removing the color would make the UI ambiguous or harder to scan, the color is doing work; if removing it changes nothing functional, it's decoration*. Decoration loses.

**P6 — Hover by fill.** Filled controls (solid background, white text) *lighten* on hover; outline controls (white background, colored border + text) *darken* with a subtle background tint in their role's color. Same direction across the app, applied consistently from buttons to nav anchors, so "you can click this" reads the same way everywhere.

**P7 — Recovery actions adopt the card's color family.** When an action lives inside a card whose color carries the meaning (a lock card, a danger zone), the action picks up that family rather than reasserting its own. A Primary blue button inside an amber lock card clashes; an outline-amber button continues the card's framing. Same logic for outline-red destructive buttons inside the danger zone. The card already says "this region needs care" — the action shouldn't have to repeat the color story in a different language.

---

## Color palette

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

## Typography

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

## Spacing

A 4px base grid. Spacing values: 4, 8, 12, 16, 24, 32, 48, 64. Stick to these; off-grid spacing creates the subtle visual noise that makes a UI feel sloppy.

- **Tight (4–8px)** — between a label and its input, between a badge and surrounding text.
- **Normal (12–16px)** — internal padding of cards, gaps between adjacent controls in a row.
- **Loose (24–32px)** — between major sections of a page, between chrome and page content.
- **Page (48–64px)** — top of page to first content, between distinct page regions.

Card internal padding: 16px or 24px depending on density. Don't go lower; cramped cards feel anxious.

---

## Components

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

## Patterns

**Status strip.** A horizontal line of compact key-value pairs separated by middle-dot characters (`·`). Small text size, `text-secondary` for labels, badges for values. `bg-muted` background, `border-subtle` top and bottom borders. Sits between the chrome and the page body. The composition (which keys appear, in what order) is app-specific.

**Breadcrumb.** Top-of-page navigation showing path. `accent-blue` for clickable segments, `text-primary` for the current page. Separator: ` / ` with surrounding spaces, in `text-muted`. Small text size. No "home icon" or other ornamentation.

**Empty state.** When a page or card would render empty, show a brief explanatory message in `text-secondary` rather than a blank surface. If there's an action that resolves the empty state, link to it. No illustrations, no oversized icons, no marketing copy.

**Confirmations.** Destructive confirmations render *inline* where the action was triggered, not as modal dialogs. The triggering button transforms into a confirmation row: a short explanatory message, a destructive-styled "Confirm" button, and a secondary "Cancel" button.

**Loading states.** Brief operations (under 1 second): no loading indicator; let the action complete and the UI update. Longer operations: replace the triggering button with a disabled-state copy of itself with a small spinner inline, leaving the rest of the page interactive. Never use full-page loading overlays for individual actions.

---

## What to retire (when revamping an existing UI)

- **High-contrast solid-colored buttons** (saturated blue, orange, red fills). Replace with the muted button hierarchy above.
- **Multiple colors competing on one page** for non-semantic decoration. Reduce to neutrals plus accents that carry meaning.
- **Drop shadows and elevation effects.** Cards stand out via borders, not shadows.
- **Decorative icons.** Icons appear only where they carry meaning the text alone doesn't.
- **Heavy borders or thick rules.** Borders are 1px; horizontal rules are 1px in `border-subtle`.
- **Mixed corner radii.** All components use the radii defined above. Mixed radii on a single page reads as inconsistency.

---

## What this spec doesn't cover

- **App-specific decisions** (lifecycle states, navigation structure, domain entities, status strip composition, page header conventions). Those live in `spec/visual_style_rrw.md`.
- **Specific copy** (button labels, error messages). Those belong in functional specs for individual pages.
- **Responsive behavior.** Default assumption is desktop-first; mobile / narrow-viewport support is a separate spec.
- **Accessibility specifics beyond color contrast.** The palette is chosen to meet WCAG AA contrast for body text, but full accessibility review (keyboard navigation, screen reader labeling, focus management) is its own work.
- **Animation and motion.** Default is no motion beyond instant state changes.

The intent throughout: when in doubt, pick the calmer, more neutral, more consistent option.
