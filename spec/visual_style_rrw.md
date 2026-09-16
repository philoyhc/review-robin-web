# Visual style — Review Robin Web App

Instantiates the general visual style spec (`spec/visual_style_general.md`) for Review Robin specifically. Defines:

- The app-specific decisions the general spec leaves open: which accents map to which navigation groups, how lifecycle states render.
- The chrome that surrounds Review Robin pages — operator session chrome, non-session operator chrome, reviewer-facing chrome.

Read alongside:

- `spec/visual_style_general.md` — the design system this document instantiates. Components and visual vocabulary defined there (palette, typography, spacing, button shapes, card shapes, badge shapes, etc.) apply uniformly across all surfaces.
- `spec/ui_elements.md` — element catalogue the app-level UI vocabulary lives in: the five canonical `.btn` roles (Primary / Secondary / Destructive [outline red] / Alert [filled amber] / Outline-amber [lock-card recovery]) in §6, where `.alert-solid` resolves to Primary and `.danger` is a context class; the inline error / warning banner convention (mandatory `.btn.alert` Cancel, `banner-scroll-target` auto-scroll, `#source-row` Cancel-return fragment) in §5a; and the `.page-grid` / `.bottom-grid` layout primitives in §10. When this doc names a button or banner pattern, the mechanics live there.
- `spec/domain_assumptions.md` — load-bearing domain (Session + Instrument) assumptions only; the UI vocabulary lives in `spec/ui_elements.md`.
- `spec/audience_and_identity_model.md` — audience definitions, auth posture, and customization boundaries that this document's chrome decisions implement.

The visual vocabulary defined in `visual_style_general.md` applies uniformly across all surfaces. What differs by surface is the *chrome* — the framing and navigation patterns that surround page content.

---

## App-specific accent assignments

The general spec defines four semantic accents by role — blue, green, amber, red. Review Robin assigns them as follows. **The role names below are `visual_style_general.md`'s, not token identifiers**; the tokens each role resolves to are catalogued in `spec/color_tokens.md`.

- **Blue** — the **Setup** navigation group identity. Active states across the app. Links. Primary actions.
- **Green** — the **Operations** navigation group identity. Successful states. The `ready` lifecycle indicator.
- **Amber** — setup-incomplete indicators (`NONE`, `NOT SET UP`). The yellow lock card pattern. Lifecycle-locked surfaces.
- **Red** — destructive action confirmations (e.g., replacing existing setup data via Quick Setup). Validation errors. Used rarely.

Setup and Operations are two parallel series of pages (see `spec/operator_ui_concept.md` for the taxonomy). The blue/green pairing for these two groups is the app's most visible colour decision and should be preserved across the entire chrome.

---

## Light / dark mode

Review Robin themes **light or dark**, chosen per-viewer and stored browser-local. The whole palette lives as `:root` colour tokens in `base.html`; `:root[data-theme="dark"]` redefines them (plus `color-scheme: dark`), so any surface built from tokens themes for free — the discipline is *use tokens, never raw hex* (the `guide/archive/ux_theme.md` sweep tokenised the app to make this hold).

- **Two states, no OS-follow.** Light is the bare `:root`; Dark is an explicit `data-theme="dark"` on `<html>`. There is no `prefers-color-scheme` path — first paint is Light until the viewer picks Dark.
- **The control** is a two-segment pill `[☀ Light | 🌙 Dark]` (`_partials/theme_toggle.html`) in the top-left chrome, inline after the app identity, in **both** the operator chrome and the reviewer top bar — so operators and participants share one control.
- **Browser-local**, never synced to the server; the storage key + no-FOUC mechanism are specced in `spec/settings_inventory.md` §7 (`rrw-theme`).

---

## Lifecycle state colors

Sessions move through three live states (and two reserved future states; see `app/services/session_lifecycle.py` for the canonical enum). Each renders as a badge in the status strip and (where relevant) inline elsewhere:

Each state has its **own** token pair (`--lifecycle-<state>-bg` / `-fg`, catalogued in `spec/color_tokens.md`), so a state's colour can move without disturbing the status-pill vocabulary that happens to share its hue:

- **`draft`** — warning amber. The same treatment as `.pill-empty`, because the session is *not ready for action*: setup work remains, and the operator's eye should land on the badge as a "needs work" cue rather than a neutral "nothing happening here" grey.
- **`validated`** — muted blue. Setup is complete and validated; ready to activate.
- **`ready`** — muted green. The session is live. Renders as **"Activated"** in user-facing copy via the lifecycle display-label mapping (see `spec/session_home.md`).
- **`expired`** — red. Renders as **"Closed"**. It shares the reviewer dashboard's red in light and **not** in dark, where the lifecycle pair resolves to `--red-bright` and the dashboard's error pill to `--red-soft`; the hue is the shared signal, not the value, and the per-state pair is what lets this move without disturbing the status-pill vocabulary.
- **`archived`** — neutral grey.

Lifecycle state always appears first in the status strip, leftmost, before per-entity counts.

**Status-strip surface — an override of `visual_style_general.md`.** That
spec's Patterns entry gives the generic strip a `bg-muted` fill with
`border-subtle` top *and* bottom borders, sitting between the chrome and
the page body. Review Robin's `.status-row` sits **inside** the session
nav card and takes `--surface-card` with a **top border only**: the card
already supplies the surrounding frame, so a second fill and a second
bottom border would read as a box inside a box. Placement and fill move
together — the general spec's values apply to a strip that stands alone,
which this one does not.

---

## Page composition — card kinds and layout

Review Robin pages **compose from cards**. The page body is rarely loose markup; instead, every distinct concern on a page lands in its own card. Cards are the unit of layout, the unit of mobile collapse, and the unit of "this region is about one thing".

The general visual spec (`spec/visual_style_general.md` Components > Cards) defines the card *shape* (white background, `border-default` 2px border, 8px corner radius, 16-24px padding, no shadow), plus the Lock-card and Danger-zone variants. This section adds the Review-Robin layout discipline and card-kind taxonomy.

### Width discipline

Cards are either **half-width** or **full-width**:

- **Half-width is the default.** Half-width cards keep line lengths reasonable — full-width body text and form labels sprawl across the screen and become harder to scan. Pair half-width cards in a `.bottom-grid` (a 2-column grid with `align-items: start` so each side keeps its natural height — never stretches to match the taller column). When two half-width cards naturally belong together side-by-side, write them as a pair; when several stack on one side, wrap them in a `.bottom-left` flex column inside the grid. Example arrangements on operator pages:
  - Reviewees / Relationships: the friendly-label editor (left) + Operator actions card (right) pair, with the Upload card (left) + Danger Zone (right) pair below it.
  - Reviewers: **neither pair, since 19P.1.** All four cards are in one **Unlock panel** inside the roster card — the label editor over the Danger Zone on the left, Upload on the right — and nothing renders below the preview table. Half-width is still the rule; the container changed, not the measure. The label editor keeps a `.card-columns` fallback home for the states the panel cannot render in (locked, or mid-edit), which is that container's only tenant on this page.
  - Session Home: the **Workflow card** on top full-width, the in-place `#session-config` card below it, then a `.bottom-grid` with **Quick Setup** on the left and **Danger Zone** on the right. There is no Extract Data card on Home; Extract Setup lives on the Extract data page. `spec/session_home.md` §3 is authoritative for this page.
  - **There is no Edit Session Details page.** `/operator/sessions/{id}/edit` is a 308 redirect to `…?editing=1#session-config`, which opens the config card in place — session details are edited where they are read, not on a separate page.
- **Full-width when content requires it.** Reach for full-width only when the card's content genuinely needs more horizontal space:
  - Wide tables (Reviewers / Reviewees / Relationships / Invitations / Responses data tables) where half-width would force horizontal scroll or column truncation.
  - Per-instrument cards on the Instruments page, each of which hosts nested half-width Display Fields + Response Fields children.
  - Top-of-page status / overview cards that span the chrome's status strip width — the "All Instrument Status" card is one such case.
  - Multi-column forms whose grouping exceeds a half-width column.
- **Nested half-within-full.** Inside a full-width card, two half-width sub-cards can sit side-by-side when the parent's affordance benefits from that arrangement. Example: each per-instrument card on the Instruments page is full-width, with Display Fields + Response Fields half-cards side-by-side inside (the `.field-builder` `.bottom-grid` pattern).

`.page-grid` (with `align-items: stretch` for L-shape equal-height layouts and explicit placement classes `.card-tl` / `.card-tr` / `.card-bl` / `.card-br`) is a legacy primitive; **`.bottom-grid` is preferred** for new pairings since natural heights almost always read better than stretched ones.

### Mobile ordering = DOM order

All grids collapse to a single column at narrow viewports (≤800px). On collapse:

- Cards stack in **DOM order**. Authors write cards in the order they want operators to read on mobile.
- Half-width pairs stack as left-column card → right-column card.
- For two-column layouts using two `.bottom-left` wrappers (the Session Home pattern), the left wrapper's full stack appears first, then the right wrapper's full stack.

The implication: when designing a page, **think about mobile order first**, then arrange the desktop grid so the DOM order matches. Don't reach for `order:` CSS to fix mobile after the fact.

### Card-kind taxonomy

A page is composed of cards drawn from a small named vocabulary. The kind sets the card's role and (for the warning kinds) its visual treatment.

**Status / info card** — read-mostly, no primary action. Renders pills, counts, summaries, identifying metadata. Default visual treatment (white background, neutral border). Examples:

- Session Details card on Session Home.
- Summary card on the Responses page (assigned / invited / opened / submitted / incomplete pills).
- "All Instrument Status" card at the top of Instruments.

**Action card** — primary content is a form or affordance. The card exists to host the action, with framing copy and any required confirmation around it. Default visual treatment (white background, neutral border). Examples:

- Upload card on Reviewers / Reviewees / Relationships.
- Quick Setup card on Session Home.
- Next Action card on Session Home (the state-conditional Validate / Activate / Pause card).
- The Rule Based Assignment card on the Operations Assignments page.

**Lock card (yellow warning)** — lifecycle-locked or otherwise non-interactive surface, with optional recovery action. `--card-warning-bg` background, `--card-warning-border` border (the warning brown). The recovery action inside follows P7 and uses the outline-amber button. See "Warning surfaces — shared brown framing" below for the per-page application matrix.

**Danger zone card** — groups destructive actions. `--card-warning-bg` tinted background, `--card-warning-border` border, H2 in `--card-warning-fg` — the same amber surface as the lock card (see "Warning surfaces — shared brown framing" below). Destructive buttons inside use the outline-red Destructive role.

Status / info and Action cards share the same default visual treatment; the kinds are about *role*, not visual differentiation. The two warning kinds (Lock card, Danger zone) carry their own visual treatment because the warning framing is doing semantic work.

### When a card isn't the answer

Not every page region needs to be a card. Loose markup is fine when:

- The content is a single piece of body copy or a heading + paragraph (e.g., a placeholder page).
- The content is naturally tabular and would be the only thing inside its own card (a wrapping card adds chrome without adding meaning).

If you're tempted to put loose form controls or pills outside any card, that's a sign you need a card around them — usually a Status / info or Action card.

---

## Operator session chrome

The chrome that surrounds session-scoped operator pages (Session Home and the Setup / Operations tab pages).

### Navigation chrome (two-row layout)

The session-scoped chrome consists of:

**Top region** (above the chrome): breadcrumb in the standard pattern.

**Chrome itself**: a double-height **Home** anchor on the left, two rows of phase tabs to its right.

```
┌────────┬─ SETUP ▶      [Reviewers][Reviewees][Relationships][Observers][Instruments][Email Template]
│  Home  │
└────────┴─ OPERATIONS ▶ [Assignments][Validate][Previews][Invitations][Responses][Extract data]
```

Specifics:
- **Home** is double-height to span both rows, signalling that it's one level up from the phase tabs rather than a peer of any of them.
- **Row labels** ("SETUP", "OPERATIONS") sit at the left edge of each row, in tiny text, medium weight. The `▶` glyph sits adjacent to indicate the row's tabs follow.
- **Row backgrounds** use a very subtle tint of the row's own accent — `--nav-strip-setup-bg` for Setup, `--nav-strip-ops-bg` for Operations.
- **Active tab** uses an underline in the row's marker tone (`--nav-marker-setup` for Setup, `--nav-marker-ops` for Operations) — lighter than the full accent so the marker signals position without competing with the label.
- **Active row** (the one containing the active tab): the row label renders at `--text-body` instead of `--text-subtle`, and the triangle after it emphasizes correspondingly.
- **Hovering a tab** in a non-active row previews-emphasizes that row's label without transferring active state — gives the operator a sense of "this is the row you're about to enter."
- **Same tab shape** across both rows. Differences between rows are carried by row labels and row tints, not by tab shape.
- **Relationships and Observers are optional Setup tabs**, each rendered only when its per-session toggle is enabled (User interface settings on Edit Session Details). When disabled, the tab is omitted and the Setup row is correspondingly shorter.

**On Home itself**: chrome renders in the same shape, with no tab active. Both rows remain visible and clickable.

**On sub-pages of Home** (Edit Session, etc.): chrome renders normally. The sub-page identifies itself in the page body via H1, not in the chrome.

**On Preview pages** that are children of a Setup tab: chrome renders normally with the parent Setup tab active.

### Status strip

The status strip sits below the chrome and above the page body on all session-scoped pages. Composition, left to right:

```
Session: [LIFECYCLE_BADGE]  ·  Reviewers: [count]  ·  Reviewees: [count]  ·  Relationships: [count]  ·  Observers: [count]  ·  Instruments: [configured / total]  ·  Email Template: [count or NOT SET UP]  ·  Invitations: [state]  ·  Responses: [state]
```

Lifecycle badge first, then the Setup entities in canonical order (Reviewers, Reviewees, Relationships, Observers, Instruments, Email Template — Relationships and Observers report only when their optional Setup tab is enabled), then the two operations indicators (Invitations, Responses) at the right. Counts use the standard count-badge styling; missing/empty states use the amber empty-indicator badge.

The strip is a setup + ops at-a-glance summary, not a running-session dashboard. Detailed operations state (per-reviewer invitation status, per-instrument response counts) lives on the Operations pages themselves.

**Instruments state values.** The Instruments pill reports **two** numbers, not one, computed by `app.web.views.session_status_pills` from `instruments.configured_counts`. One number cannot distinguish an instrument a reviewer would meet as an empty page from a finished one, so a count alone lets the strip read *done* for a session that cannot be answered:

| Pill text | Pill class | Condition |
|---|---|---|
| `none` | `pill-warning` | The session has no instruments. |
| `<configured> / <total>` | `pill-info` | Every instrument is configured (`configured == total`). |
| `<configured> / <total>` | `pill-warning` | At least one instrument is not configured. |

**Configured** is `instruments.is_configured`: at least one `visible=True` response field, **and** all three Band 1 links touched (`band1_touched_links`). Both that predicate and the batched `configured_counts` apply the same rule, and `has_unconfigured` reads its answer from the latter, so there is one definition rather than three.

The colour is what makes this scannable: the numbers say what is left, the tint says whether anything is.

Order is **done over total**, matching the Responses pill in the same row (`3 drafts / 5`). `5 / 3` reads backwards as a fraction — not a proportion anyone can complete — so the direction is part of the contract and the test asserts the direction, not merely that both numbers appear.

Zero reads `none` rather than `0 / 0`, matching Reviewers and Reviewees; instruments are likewise required to validate, so the same warning tint applies rather than a third treatment.

**Invitations state values.** The Invitations pill reads one of four labels, computed by `app.web.views.session_status_pills` from the `Invitation` and `EmailOutbox` rows for the session:

| Label | Pill class | Condition |
|---|---|---|
| `Not created` | `pill-empty` | No `Invitation` rows exist for the session yet. |
| `Not sent` | `pill-warning` | `Invitation` rows exist, but no reviewer has a `sent` outbox row for their invitation. |
| `Partially sent` | `pill-warning` | At least one reviewer has a `sent` outbox row, but not every reviewer with an invitation does. |
| `All sent` | `pill-info` | Every reviewer with an invitation has a `sent` outbox row. |

The `Not created` vs `Not sent` split matters because the operator's next action differs: generate the invitation rows first vs. press Send. Collapsing both into a single "not sent" pill would hide that.

**Responses state values.** The Responses pill is **reviewee-centric** and **data-driven**, computed by `app.web.views.session_status_pills` (composed in `SessionStatusPills.responses_label`) — *not* gated on lifecycle state:

| Pill text | Pill class | Condition |
|---|---|---|
| `Awaiting` | `pill-empty` | No response activity yet — zero `include` assignments carry any saved response. |
| `<n> drafts / <reviewees>` | `pill-info` | Some reviews are in progress but none submitted (drafts only; the submitted term is omitted). |
| `<m> submitted / <reviewees>` | `pill-info` | Some reviews submitted but no bare drafts (the drafts term is omitted). |
| `<n> drafts / <m> submitted / <reviewees>` | `pill-info` | Both in-progress and submitted reviews exist. |

Definitions (both counted as **distinct `include` assignments = "reviews"**, mutually exclusive per assignment):

- **Drafts** (`responses_drafts`) — assignments with at least one saved response but **no** submitted one (all `submitted_at` still null).
- **Submitted** (`responses_submitted`) — assignments with at least one response bearing a `submitted_at`.
- The trailing **`<reviewees>`** is the reviewee count (the reviewee-centric denominator, matching the Responses operations page).

The gate is deliberately data-driven, not lifecycle-driven: the numbers appear as soon as any response is saved and **persist even if the session is reverted to draft** after responses came in, rather than snapping back to `Awaiting`. Whichever of drafts / submitted is zero is dropped from the label so the pill stays terse. Detailed per-reviewee / per-instrument coverage lives on the Responses operations page, not the strip.

**Lifecycle pill — enum vs. label.** The lifecycle badge renders through the `lifecycle_label` Jinja filter (`app.services.lifecycle_display`). All values pass through capitalised except `ready → "Activated"` and `expired → "Closed"`. CSS class names continue to use the raw enum (`pill-lifecycle-ready`, not `pill-lifecycle-activated`). See `spec/session_home.md` §"Lifecycle state vocabulary" for the rationale.

### Page header conventions

Page-level identity is established by the breadcrumb and the active chrome tab in combination. Most pages do not need a redundant H1 echoing the active tab name.

Exceptions:
- **Home (Session Home / Control Panel)** — H1 is the session name, since the session is what Home represents. Lifecycle state appears as a badge in the status strip; no need to repeat in the page body.
- **Sub-pages of Home** (Edit Session) — H1 is the sub-page name ("Edit Session"), since the chrome doesn't distinguish sub-pages from Home.
- **Operator's Overview** (sessions list) — H1 is "Sessions" or similar, since this page sits outside session-scoped chrome.
- **Preview pages** that are children of a Setup tab — H1 is the preview's name ("Reviewer surface preview"), not the parent tab's name.

For all other session-scoped pages (the five Setup pages, the Operations pages), no H1 is needed. The chrome tab and breadcrumb together establish identity.

### Warning surfaces — shared brown framing

Two card variants in the app's vocabulary frame "this region needs care": the **lock card** (intentionally non-interactive due to lifecycle) and the **danger-zone card** (groups destructive actions). Both share the same amber surface — `--card-warning-border` (the warning brown) over a `--card-warning-bg` tinted infill — so the operator's eye recognises the same visual category whether reading "you can't change this right now" or "here's where you delete data". The framing *and* the fill are one; the action inside differentiates them (the lock card's outline-amber recovery vs. the danger zone's outline-red Destructive).

Per **P7**, recovery / primary actions inside these cards adopt the card's color family:

- **Inside a lock card**: outline-amber button (e.g. "Revert to draft"). A solid Primary blue inside an amber card clashes; the outline-amber action continues the framing.
- **Inside a danger zone**: outline-red Destructive button. Same principle applied to the destructive role — the brown frames the surface; the red marks the action that actually deletes data.

#### Lock card uses

Used when a page or section is reachable but its actions are disabled because the session lifecycle locks them.

- **On Setup pages** when session is `ready`: lock card explains that setup is locked and offers a "Revert to draft" action where appropriate.
- **On Operations pages** when session is `draft` or `validated`: lock card explains that operations are unavailable until the session is activated, and links to Home where the Activate action lives.
- **On the send-test affordance** within the Reviewer Experience Preview when session is no longer accepting responses: same pattern.

The lock card pattern is consistent across all of these. Its prominence and explanatory copy adapt to the specific case, but its visual treatment does not.

**Exception — Session Home.** Per `spec/session_home.md`, Home does *not* render lock cards; the Next Action card carries any explanatory messaging the operator needs about lifecycle. Disabled treatment on Home is plain greying-out. Lock cards remain in use everywhere else.

#### Danger-zone card uses

Groups the destructive actions for a given Setup entity (Delete all reviewers / reviewees / relationships / instruments) and the session-level destructive actions (Delete data, Delete session). H2 is "Danger Zone" in `--card-warning-fg`. Lives at the bottom-right of the page (or in the bottom row of a `.bottom-grid`) so it stays visually grouped with the entity it operates on but isn't the first thing the eye lands on. **On Reviewers since 19P.1 it is inside the roster card's Unlock panel instead** — grouped with the entity as before, and de-prioritised by being behind a disclosure rather than by sitting low on the page. The amber framing is unchanged and deliberately so: the card keeps `.card.danger-zone` inside the panel, because that class is the only reach for the warning treatment and three sibling pages still carry it outside one. If the framing is ever dropped there, this section and `spec/ui_elements.md` §`.card.danger-zone` both become false of Reviewers as a matter of pixels rather than placement.

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

- **Left:** "Review Robin Web App (version …)" — small, in `--text-subtle`. App identity and version, modest.
- **Right:** A small **user menu** containing:
  - "Signed in as [Operator Name]" (informational, not a link).
  - About — opens About page, with return-to-origin behavior (see below).
  - Settings — opens Settings page, with return-to-origin behavior.
  - Sign out — ends the operator's session.

The user menu can render as inline links (when the menu has three or four items) or as a dropdown triggered by clicking the operator name. Inline is preferred while the menu is small; promote to dropdown when it would otherwise crowd the top bar.

#### Return-to-origin behavior

About and Settings are detour destinations: the operator opens them to consult or adjust something, then wants to return to whatever they were doing. The pattern:

- When the operator opens About or Settings, the URL captures the origin via a query parameter (e.g., `?return_to=/sessions/abc123`) or session state.
- The About/Settings page renders a clear "Back" affordance — a `.back-link` in `--text-link` near the top of the page body, labeled with context where possible: "← Back to Sessions" or "← Back to Student Associate Selection 2026 Peer Review".
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
- **Body:** A table inside a single `.card`. Columns:
  - **Session Name** — linked to that session's Home. The name is the row's primary affordance; there's no separate Access button.
  - **Session Code** — rendered in `<code>`.
  - **Deadline** — `.pill.pill-info` carrying the ISO date when set; plain muted "No deadline" when unset.
  - **Created by** — display name of the operator who created the session (falls back to email).
  - **Created** — `YYYY-MM-DD`.
  - **Last Modified** — `YYYY-MM-DD`.
  - **Action** — unlabelled trailing column carrying a select-row checkbox. The column carries **no per-row Delete**: deletion from the lobby is a bulk action over the checkbox selection, so a per-row affordance here would be a second route to the same thing.
- **Create Session affordance:** a single Primary button labeled "Add new session", in the Search card, present in every lobby state. **It is the page's only route to `/operator/sessions/new`** — the empty state's first-run card names this button rather than carrying a second one, because two buttons to one route is two affordances for one action (`spec/sessions_overview.md`).

**A table, not a grid of session cards.** At the operator's lobby dense scannable rows matter more than per-card framing, and every column above has a natural width budget. The table takes the row-only borders and muted header treatment from the app's default table (`spec/ui_elements.md` §7) and adds no framing of its own.

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

- **Left:** "Review Robin" — small, `--text-subtle`. App identity as a trust anchor. No version info (operators care about that; reviewers don't).
- **Right:** A small **user menu** containing:
  - "Signed in as [Reviewer Name]" — informational. Lets the reviewer confirm correct identity (important on shared computers, useful in institutions where SSO might silently log the wrong person in).
  - "My Reviews" — link back to the reviewer's review list (only rendered when the reviewer has more than one review pending or completed; suppressed when there's just one).
  - "Guide" — opens the Guide (`/guide?return_to=<path>`, skipped on `/guide` itself), rendered only for a viewer who resolves at least one Guide audience. Gated on the same `request.state.guide_hidden` **hide** flag the operator chrome reads, and **fails open**: an unset flag renders the link, because `/guide` itself bounces a viewer who resolves nothing to `/about`, so a stray link is cosmetic while a missing one hides a page someone is entitled to.
  - "About" — opens the About / access-help page (`/about?return_to=<path>`, skipped on `/about` itself), same as the operator chrome's About link.
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
- Empty state when the reviewer has no pending reviews: "You have no pending reviews." in `--text-subtle`. Not an error; just informational.

**Deep-linking behavior:** when a reviewer signs in via a session-specific invitation link and has only one pending review, the sign-in flow can deep-link them past the review list to the response surface directly. The list exists for the cases where it's useful (multiple reviews, returning to find a specific one); it's not a forced waypoint for every visit.

#### Response surface (the response form)

The main task surface, where the reviewer completes their evaluations.

**Chrome:**

- Standard reviewer top bar (Review Robin identity + user menu).
- **Page header** with session context:
  - Session name — rendered at H1 size.
  - Deadline — small reminder in `--text-subtle`, near the session name.
  - Optional: institution or operator name (small, `--text-subtle`) — useful for reviewers participating across institutions or with multiple operators in mind.
  - Optional: operator-configured welcome message / instructions, shown above the form on first visit. Plain text or limited markdown.
- **Page navigation** (only when the session has more than one instrument; see "Multi-instrument navigation" below).
- **Form body.**

##### Multi-instrument navigation

A session may have multiple instruments for a reviewer to complete across their assigned reviewees. This requires more than one page facing the reviewer, and some navigation chrome.

(Underlying rationale: see "Response form layout and instrument pacing" below — one page per instrument is the canonical principle.)

**Pattern: one action row, with page navigation at its right.** The surface's main action row carries `Save` / `Cancel` / `Submit`, and — only when the session runs to more than one page — a vertical divider followed by the navigation cluster: `< Previous page`, a `Page {N} of {M}` counter, and `Next page >`. The row is repeated at the top and bottom of the form so the reviewer can act without scrolling.

Navigation is **plain HTTP**: Prev and Next are `<a href>` links to `/me/sessions/{id}/{page_n}`, and the unavailable one at either end renders as a disabled `<button>`. There is no per-instrument button and no client-side visibility toggle — a page change is a server round-trip, which is why unsaved edits do not survive one and `Save` exists. Pages are operator-defined and may carry several instruments each; within a page, instruments stack vertically.

Detailed layout contract — control order within the row, the navigation cluster and its divider, status-pill placement, save semantics — lives in `spec/reviewer-surface.md`. This document covers the chrome philosophy; the surface spec is the implementation contract.

Three persistent guarantees the chrome makes regardless of layout details:

- **Tab order** matches whatever order the operator configured in the Instruments Setup page. Reviewers can't reorder; the order is the session's.
- **Free movement between pages.** The reviewer can switch pages at any time, in any order. **Unsaved typing does not survive the move** — a page change is a server round-trip, there is no dirty-tracking and no `beforeunload` guard, so `Save` before navigating is the reviewer's responsibility (`spec/reviewer-surface.md`, Prev / Next row and "Dirty-state"). Restoring typed-but-unsaved values across a page change is a real improvement and is not built.
- **No page is "locked" by another page's completion.** The reviewer can fill instruments in any order.

**When the session runs to a single page**, the navigation cluster doesn't render — the action row carries only Save / Cancel / Submit. The per-page status pill in the right-half status panel is then the only signal that pages exist as a concept. (The pill's label is `#{N} {short_label}`, or bare `#{N}` — note it uses a space where the per-instrument H2 uses `#{N}: {short_label}`.)

##### Per-reviewee navigation within an instrument

A separate concern: within a single instrument, the reviewer evaluates multiple reviewees. **This is rendered as a table — every reviewee on one page, one row per reviewee.** No per-reviewee paging, no sidebar drill-down. See "Response form layout and instrument pacing" below for the canonical principle and rationale; pacing across cohorts is handled by splitting the work across pages, not by paging within an instrument.

The chrome stops at the action row; what happens *inside* the form (table layout, sticky headers, keyboard navigation, auto-save) is the response-form component's concern — see "Large-table ergonomics" below.

#### Submission confirmation

Shown after the reviewer submits all required responses for the session.

**Chrome:** standard reviewer top bar + page body.

**Body:**

- Brief acknowledgement: "Thank you. Your responses have been received."
- Optional: summary ("You completed 3 instruments across 7 reviewees.").
- Optional: link back to the reviewer's review list, if other reviews remain.
- No page navigation; the task is complete.

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
- **Top bar pattern.** Both operator and reviewer surfaces have a top bar with app identity (left) and user menu (right). Operator's says "Review Robin Web App (version dev)" because operators care about the version; reviewer's says "Review Robin" because they don't. Operator's user menu hosts Guide / About / Settings / Sign out; reviewer's user menu hosts My Reviews / Guide / About / Sign out, with Guide suppressed for a viewer who resolves no Guide audience. Same shape, different contents.

The discipline: components and visual language are uniform; chrome and navigation patterns are audience-specific. An operator and a reviewer should recognize the same app from the visual style; a quick glance at the chrome should tell each which surface they're on.

---

## Response form layout and instrument pacing

### Core principle

**One page per instrument.** Each instrument the reviewer is
assigned renders as one page, with the instrument's tabular form
as the page's main content and reviewees as rows.

This pattern is canonical and uniform: it applies to sessions of 5
reviewees and sessions of 100 reviewees, to numeric scoring
instruments and qualitative comment instruments, to one-instrument
sessions and many-instrument sessions. There is no alternative
"narrative mode," no per-reviewee paging variant, no layout toggle.
One pattern.

**Pacing is operator-controlled at instrument-design time.** If a
reviewer should encounter the work in smaller chunks — because the
cohort is large, because different reviewees should be evaluated in
different contexts, or because the operator wants to break a long
task into parts — the operator designs that pacing into the
instruments themselves. Smaller instruments give smaller pages;
more instruments give more tabs. The reviewer-side layout does not
vary by scale; the operator-side instrument design carries the
burden of pacing.

### Why this principle

#### Tabular instruments are the app's defining feature

Review Robin supports tabular review artifacts at scale as a
deliberate product positioning. Generic form tools (MS Forms,
Google Forms, Qualtrics) handle per-reviewee paged forms perfectly
well; the differentiator is the tabular workflow — cross-reviewee
calibration, efficient bulk scoring, spreadsheet-mode entry. Honoring
the operator's choice of a tabular instrument means rendering it
*as a table*, not transposing it into something else on the
reviewer side.

#### The operator already has the right knowledge to decide pacing

The operator knows the cohort size, the question complexity, the
reviewer's likely time commitment, and the cognitive structure they
want the reviewer to enter. The reviewer-side renderer does not
have any of this information and is in a poor position to make
pacing decisions on the operator's behalf. Pushing the decision to
instrument-design time puts it where it can actually be reasoned
about.

#### One reviewer pattern simplifies the system

A single canonical response form layout means:

- Reviewers learn the pattern once and recognize it across all
  sessions and review types.
- The Setup-side and reviewer-side share one model; what the
  operator builds is what the reviewer sees.
- The chrome (action row, page navigation, persistent
  affordances) is stable and well-defined; no mode-dependent
  variants.
- Future variations (different review types, embedded scenarios,
  audience extensions) sit alongside this pattern as separate
  features rather than as toggles within it.

### How operators use instruments as a pacing tool

Some illustrative cases:

**Wide-and-shallow** — 30 reviewers each rating 80 reviewees on
familiarity, rating, and a comment. One large instrument with three
columns and 80 rows. One reviewer page with one big table.
Reviewers use spreadsheet-mode entry to work through it efficiently,
calibrating across rows.

**Multiple contexts, same reviewer pool** — reviewers evaluate one
group of people on technical criteria and a slightly different
group on collaborative criteria. Two instruments, two pages, two
tables. Page navigation carries the context switch; each table is
appropriately sized to its scope.

**Large global cohort, small per-reviewer scopes** — 1,000 people
to be reviewed in groups of 5–8 by their groupmates. Each reviewer
sees only their group as rows; structurally this is per-reviewer
assignment scoping rather than instrument design, but the principle
holds: the reviewer's tabular experience is bounded by what the
operator configured for them.

**Narrative-heavy review with few reviewees** — 8 people each
needing a written holistic evaluation. Operator can design 8
instruments (one per reviewee) so each tab becomes a per-reviewee
narrative page. This is a workable use of the principle, and the
slight clunkiness is a useful signal that this review type is at
the edge of what tabular framing handles well — not its center. If
it became a frequent need, it would warrant a separate review type
with its own design, not a layout toggle on the existing pattern.

The thread through these cases: the operator's instrument design
*is* the reviewer's pacing. Smaller instruments mean smaller pages
mean more breakpoints. Operators who want reviewers to feel chunked
progress design for it; operators who want one continuous tabular
sweep design for that.

### Implications for instrument design

Operators should consider, when designing instruments:

- **How wide can a row reasonably be?** A row with three or four
  short columns reads cleanly; a row with twelve columns and a
  long comment field reads cluttered. If a single instrument has
  too many response dimensions, splitting it into multiple
  instruments may improve the reviewer's experience.
- **Are different evaluation criteria genuinely separate, or just
  long?** A single instrument with related criteria (all
  technical-skills questions) is appropriate. An instrument
  conflating unrelated dimensions (technical skills + cultural
  fit + recommendation) might benefit from being three
  instruments — both for the reviewer's mental clarity and for
  the operator's downstream analysis.
- **Will reviewers benefit from a context reset between groups?**
  If yes, separate instruments for separate groups (as in the
  multiple-contexts case above) make the context boundary
  explicit.
- **Is the cohort small enough to feel manageable as one table?**
  At small reviewee counts (say, under 20), one instrument
  with all relevant columns is usually fine. At larger counts,
  the operator should think harder about pacing.

These are guidance for the Instruments Setup experience, not hard
rules. Operators retain full control; the app does not enforce
splits. Surfacing the considerations is a job for Setup-side
documentation and possibly inline guidance on the Instruments Setup
page.

### Implications for the reviewer surface

Most of these are already covered above in "Multi-instrument
navigation"; restating in this principle's context:

- **Page buttons are the reviewer's pacing UI.** Each button is
  one instrument, one page. Operators choose page order; reviewers
  move freely between pages.
- **Two operator-authored strings per instrument.** The schema
  exposes:
  - **`Instrument.short_label`** (`String(32) | None`) — the
    operator's reviewer-facing framing. Lands on Page button
    labels and as the per-instrument H2 title above each table.
    Capped at 32 characters at the schema layer.
  - **`Instrument.description`** (`String(2000) | None`) — the
    longer per-instrument blurb. Lands as the subtitle next to the
    H2 title. Optional per-instrument context the reviewer reads
    on instrument entry ("This instrument asks you to rate the
    candidates on technical skills, considering their submitted
    work samples.").
  The system handle `Instrument.name` is **not** reviewer-facing
  — it carries audit-event copy and is otherwise invisible.
- **The per-instrument heading carries the operator's framing.**
  `short_label` reaches the reviewer in two places, neither of
  them a control: the H2 above each table, and the per-page status
  pill's label. The navigation cluster shows only `Page {N} of
  {M}`, which grounds position without naming content. The H2 reads `#{N}: {short_label}` on a multi-instrument
  session and bare `{short_label}` on a single-instrument one
  (no `#1:` prefix needed when there is only one). Note the
  composed form is `#{N}:`, not `Page #{N}:`. "#1: Round 1" /
  "#2: Round 2" is a different reviewer experience from
  "#1: Skills" / "#2: Cultural Fit" / "#3: Recommendation", so
  operators should choose `short_label` values with
  reviewer-comprehension in mind.
- **Description renders beside it.** The longer description is the
  subtitle on the same row as the H2, baseline-aligned, so "what is
  this page, and what's it for" reads in one glance. With both
  fields empty in a single-instrument session, no H2 row renders at
  all; with only a description set on such a session, the
  description takes the H2 itself (a deliberate deviation recorded
  on `views.InstrumentHeading`, so operators who have not adopted
  `short_label` do not silently lose their per-instrument context).
  The full composition table lives on that dataclass.
- **`short_label` length constraint.** **`Instrument.short_label`
  is capped at 32 characters** — `String(32)` on the column, with
  the check in `update_short_label`
  (`instruments/_instrument_crud.py`). The cap is a Setup-side
  responsibility and the reviewer surface trusts the value it's
  given (`spec/instruments.md`). **No rationale for 32 is recorded
  anywhere**, and nothing downstream depends on it: the cap is the
  whole of the defence — `base.html` carries no `text-overflow`
  declaration and no single-line constraint on the H2, here or
  anywhere — so a longer label would wrap rather than break.
- **Per-page status pills** (per "Multi-instrument navigation")
  live in the right-half status panel above the action rows, not
  in the navigation cluster. The panel always renders (one
  pill per instrument) so the reviewer sees the shape of their
  remaining work at a glance, regardless of which page is visible.
  Within an instrument, completeness is a property of the table
  itself (filled vs. empty rows), so per-row indicators may also
  be useful — see "Large-table ergonomics" below.

### Large-table ergonomics

Since the canonical layout is "one page = one tabular instrument,"
and instruments may legitimately have 80+ rows, the response-form
component must handle large tables as a first-class concern. These
are first-class because the app's positioning depends on them, not
nice-to-haves.

The full design for large tables belongs in the response-form
component spec (separate from this document), but the requirements
this principle imposes are:

- **Auto-save** at appropriate granularity (cell change, row blur,
  or short interval) so that reviewers working on long tables do
  not lose work to browser crashes, accidental navigations, or
  session timeouts.
- **Return-to-place behavior** when a reviewer comes back to an
  in-progress table — landing at the first incomplete row, the
  last edited row, or top with a "resume" affordance.
- **Visible progress.** A small "47 of 80 complete" indicator at
  the top of the table, plus per-row completion icons in a sticky
  leftmost column.
- **Sticky column headers.** When the reviewer is on row 60, the
  column headers (question text) should still be visible at the
  top of the viewport. **Ruled out, not deferred:** the reviewer
  table sits in a `.table-scroll` wrapper whose `overflow-x`
  forces an `overflow-y` scroll context, so a `position: sticky`
  header stays visible only if the table becomes its own internal
  scroll viewport (a `max-height` box). The surface keeps
  whole-page scroll and a non-sticky header — a header that stays
  put does not buy that scroll-model change.
- **Filter to incomplete.** A "show only unscored" toggle is
  invaluable for reviewers working across multiple sessions or
  returning to a table they partially filled.
- **Keyboard navigation.** Tab moves to the next cell within a
  row; Enter (or Tab from the last cell) moves to the next row.
  Reviewers who learn this can work through large tables several
  times faster than mouse-only.
- **Submission semantics.** Submitting a review is a
  review-session-level action (one Submit covers every instrument
  the reviewer has been assigned), not per-row. Submission should
  be enabled only when the review is complete, or should warn
  explicitly about partial submission.
- **Column type ergonomics.** Numeric scoring columns can be
  narrow; comment columns need to expand. Long-form comments
  may need a click-to-expand or popover pattern within the cell —
  inline editing of long text inside a tight cell is poor
  ergonomics.

The last point bleeds back into instrument design: if operators
add comment fields to a tabular instrument, the reviewer's
ergonomics depend on how the comment field renders within the
table. The Instruments Setup page may want to surface a soft
warning about column types and reviewer ergonomics — for example,
flagging when an instrument has multiple long-form text columns
that may not work well in tabular form.

### What this principle is not

- **Not a one-row-per-page experience.** Even small instruments
  (5 reviewees) render as tables, not as paged forms. The unit of
  iteration is the instrument, not the reviewee.
- **Not configurable per session.** The reviewer-side layout is
  fixed; what varies is the operator's instrument design.
- **Not a commitment to handle every conceivable review type.**
  Reviews that genuinely want per-reviewee narrative paging are
  served imperfectly by this pattern. The principle accepts this
  trade-off in service of consistency and the tabular-at-scale
  positioning.
- **Not a barrier to future review types.** If a fundamentally
  different review type emerges (a longitudinal review where
  reviewers track a single subject over time, an ethnographic
  observation form, etc.), it can be added as its own type with
  its own reviewer pattern — alongside this one, not replacing or
  toggling it.

### Doc impact

`spec/operator_ui_concept.md`:

- The reviewer-facing pages section gains a brief reference to this
  principle.

This document (further down):

- The "Multi-instrument navigation" subsection above already
  aligns with this principle. A one-line cross-reference here
  clarifies the underlying rationale (added in the same change as
  this section).

`spec/instruments.md` owns the operator-side instrument surface. Not
yet specced there, and still open design notes:

- Explicit guidance to operators that instrument boundaries are
  pacing tools, not just data-grouping tools.
- The optional per-instrument description affordance recommended
  above.
- Soft-warning logic for column-type ergonomics.

`spec/reviewer-surface.md` owns the response form. Not yet specced
there, and still open design notes:

- The full large-table ergonomics design.
- Specific handling of auto-save, return-to-place, sticky headers,
  keyboard navigation, and submission semantics.

### Cross-references for this principle

- `spec/audience_and_identity_model.md` — the audience and surface
  philosophy the principle here serves.
- "Multi-instrument navigation" (above in this document) — the
  chrome around the response form, including the action row and
  its page-navigation cluster.
- `spec/reviewer-surface.md` — the multi-instrument-aware response
  surface spec; the URL pattern, page anatomy, form scope, and
  per-page status pills implementing this principle on the live
  surface.
- `spec/instruments.md` — operator-side instrument design, where
  pacing decisions are made.
- `spec/reviewer-surface.md` — the response form itself; the
  large-table handling above is not yet written there.

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
