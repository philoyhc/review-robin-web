# UI elements catalogue

> **Status (2026-05-03):** Initial draft. Derived from an audit of every
> operator and reviewer template against `app/web/templates/base.html`
> and `spec/visual_style.md`. Intended to be the canonical reference
> for every onscreen element in the app — what it's called, what it
> looks like today, what it should look like after the
> `unfinished_business.md` #21 restyle, and which PR in the restyle
> bundle owns the migration.

This document expands `unfinished_business.md` #21 from a buttons-only
restyle into a full operator-surface settling pass covering navigation
chrome, cards, tables, buttons, forms, banners, badges, and layout
primitives. It is split into:

- **Part 1 — Element catalogue.** One section per element family.
  Each entry lists the canonical name, the canonical visual treatment
  (per `spec/visual_style.md`), the current implementation in
  `base.html` and templates, and the migration delta.
- **Part 2 — Drift catalogue.** Cross-cutting list of one-off
  inline styles, unique classes, and inconsistent treatments the
  audit surfaced.
- **Part 3 — Restyle bundle PR split.** Suggested chunking of the
  expanded #21 work into ~6 PRs.

Cross-references:

- **`spec/visual_style.md`** — authoritative design system (palette,
  type scale, spacing, component shapes, app-specific accent
  assignments). This catalogue instantiates that spec against the
  current codebase.
- **`spec/assumptions.md`** — current "as-built" UI vocabulary
  (`.btn` family, layout primitives, banner conventions). Sections
  marked superseded there are pointers into this doc.
- **`spec/operator_map.md`** — page-level chrome and per-page
  layout contracts that consume these primitives.
- **`spec/reviewer_map.md`** — reviewer-surface page contracts.

When this doc disagrees with `assumptions.md`, this doc wins for
canonical naming; `assumptions.md` remains accurate for what's in
the templates today until the migration ships.

---

## Part 1 — Element catalogue

Each element entry follows the same shape:

> **Canonical name** — one-line role.
> *Current* (what's in the codebase today): CSS class(es) + the
> file(s) that own the rules.
> *Canonical* (what it should be after #21): treatment per
> `visual_style.md`.
> *Migration delta* (what changes): brief.
> *PR* (which slice of the bundle owns it): see Part 3.

### 1. Page chrome (top of every page)

> **App identity bar** — small "Review Robin Web App (version …)"
> link in the top-left, sign-in info + Sign-out button on the right.
> *Current:* `.chrome` flex row + `.chrome-left` / `.chrome-user` /
> `.chrome-app-identity` / `.signout` in `base.html`. Bottom border
> at `#eee`.
> *Canonical:* unchanged shape. Tighten to the visual_style palette
> (`border-subtle` for the bottom border, `text-secondary` for the
> identity link). The Sign-out button becomes a Secondary button
> (see §6).
> *Migration delta:* swap raw greys for palette tokens; adopt
> Secondary button shape for Sign-out.
> *PR:* D (chrome).

> **Breadcrumb** — `_partials/breadcrumb.html`, rendered inside
> `.chrome-left`. Links in `accent-blue`, current segment in
> `text-primary` semibold, separator " / " in `text-muted`.
> *Current:* `.breadcrumb`, `.breadcrumb-sep`, `[aria-current="page"]`
> rules in `base.html`. Already close to spec.
> *Canonical:* match `visual_style.md` "Breadcrumb" pattern (no home
> icon, small text, consistent spacing).
> *Migration delta:* swap `#999` separator for `text-muted` token;
> verify type scale.
> *PR:* D (chrome).

### 2. Session-scoped chrome

> **`.session-nav-card`** — the two-row navigation card with the
> double-height Home anchor on the left and Setup / Operations tab
> rows on the right. Specified in detail in
> `spec/visual_style.md` Part 2 ("Navigation chrome (two-row layout)").
> *Current:* `.session-nav-card`, `.session-nav-grid`,
> `.session-home-anchor`, `.row-label`, `.tab-strip-setup`,
> `.tab-strip-ops`, `.nav-tab`, `.status-row` rules in `base.html`;
> rendered by `operator/partials/session_top_nav.html` and included
> by every session-scoped operator template.
> *Canonical:* already implements the two-row spec. Delta is small:
> recheck row tints (`accent-blue` / `accent-green` at 5% opacity,
> not the current `#f3f4f6` / `#f0fdf4`), active-tab marker uses the
> row's accent rather than a global `--tab-marker-color: #93c5fd`,
> row labels darken to `text-primary` when their row is active.
> *Migration delta:* recolor row tints and the active-tab underline
> to match per-row accent assignment; tighten label / arrow colors
> to palette tokens.
> *PR:* D (chrome).

> **Status strip (`.status-row`)** — horizontal compact strip of
> "Lifecycle · Reviewers · Reviewees · Assignments · Instruments ·
> Email Template" sitting inside the nav card.
> *Current:* `.status-row` rules in `base.html`; rendered by
> `operator/partials/session_setup_status_row.html`. Today emits
> `<p>` tags rather than the canonical "key: badge · key: badge"
> middle-dot row.
> *Canonical:* `visual_style.md` Part 2 "Status strip" — middle-dot
> separators, lifecycle badge first, count / empty badges per slot,
> `bg-muted` background.
> *Migration delta:* template rewrite of
> `session_setup_status_row.html` to the canonical strip; lift
> lifecycle badge into the strip (currently lives on Session
> Details card on session_detail.html).
> *PR:* D (chrome).

> **Setup nav (`.setup-nav`)** — equal-width 140px button row at the
> top of session-scoped pages.
> *Current:* `.setup-nav` rules in `base.html`. Documented in
> `assumptions.md`. Audit found no template currently using
> `.setup-nav` — it appears to have been superseded by the
> `.session-nav-card` two-row chrome.
> *Canonical:* obsolete; remove the class once we confirm no
> template references it.
> *Migration delta:* delete `.setup-nav` rule from `base.html`.
> *PR:* D (chrome).

### 3. Page headings

> **H1 (page title)** — `1.5rem semibold text-primary`, with a
> `.page-subtitle` line allowed below.
> *Current:* `h1` global rule in `base.html` (margin only, no size
> override). `.page-subtitle` defined as `0.95em #555`.
> *Canonical:* `visual_style.md` "Type scale" — explicit `1.5rem`
> semibold, `page-subtitle` becomes `text-secondary` small.
> *Migration delta:* size + weight on H1; color token on subtitle.
> *PR:* A (tokens & primitives).

> **H2 (card / section title)** — `1.125rem semibold text-primary`,
> sits at top of card with 16px space below.
> *Current:* `.card h2` rule sets `font-size: 1.15rem`; bare `h2`
> outside cards inherits browser default.
> *Canonical:* uniform 1.125rem semibold across cards and sections.
> *Migration delta:* normalize to one rule.
> *PR:* A (tokens & primitives).

### 4. Cards

> **`.card` (default)** — white surface with subtle border,
> 16–24px padding, `border-radius: 8px`, no shadow.
> *Current:* `.card` rule in `base.html` uses
> `border: 2px solid #bbb; border-radius: 12px; padding: 20px`.
> Heavier border, larger radius, and saturated grey vs. spec.
> *Canonical:* `border: 1px solid border-subtle; border-radius: 8px;
> padding: 16-24px`.
> *Migration delta:* re-tune to spec.
> *PR:* C (cards & banners).

> **Lock card (yellow)** — same shape as `.card`, with
> `accent-amber` light background and `accent-amber` border. Used
> when a surface is reachable but locked by lifecycle.
> *Current:* not a class. Templates simulate it with
> inline-styled `.card` (e.g. `style="border-color: #d97706;
> background: #fef3c7;"` on the "session is ready" warning card on
> several Setup pages).
> *Canonical:* `.card.lock` (or `.card-lock`) — single class,
> consistent across every locked surface listed in
> `visual_style.md` Part 2 "Yellow lock card pattern".
> *Migration delta:* introduce class; sweep templates to replace
> inline-styled amber cards.
> *PR:* C (cards & banners).

> **Danger Zone card** — bordered card grouping destructive
> actions (Delete data, Delete session, Delete instrument).
> *Current:* not a class. Each occurrence uses inline
> `style="border-color: #b91c1c;"` (and sometimes
> `background: #fff;`) on a `.card`. Locations:
> `session_detail.html` (`#danger-zone`), `session_reviewers.html`,
> `session_reviewees.html`, `session_assignments.html`,
> `instruments_index.html`. Inconsistent: some set background,
> some don't.
> *Canonical:* `.card.danger-zone` — `accent-red` border,
> white background, optional H2 in `accent-red`. Destructive
> buttons inside use Destructive variant (see §6).
> *Migration delta:* introduce class; sweep templates; remove
> inline `style="color: #b91c1c"` H2 overrides.
> *PR:* C (cards & banners).

> **Reviewer help cards (`.rs-help-card` family)** — bg-muted
> tinted blocks listing per-instrument response-field help text.
> Two-up grid (`.rs-help-grid`) when ≥2 items; single full-width
> (`.rs-help-card-solo`) when exactly one.
> *Current:* `.rs-help-grid`, `.rs-help-card`, `.rs-help-card-solo`
> in `base.html`. Already palette-aligned (`#f5f5f7`, `#444`,
> strong `#111827`).
> *Canonical:* keep as-is; tokenize colors during PR A.
> *Migration delta:* none beyond token swap.
> *PR:* A (tokens) for color tokens; otherwise no change.

### 5. Banners

> **Inline error / warning banner** — appears at the top of a page
> after a redirect-back-with-banner from a mutating route. Carries
> `.banner-scroll-target` so the page-wide auto-scroll script jumps
> to it on load.
> *Current:* mix of patterns:
> - `.warning-banner` and `.danger-banner` classes defined in
>   `base.html` — used in some places (notably
>   `review_surface.html`'s preview banner, recolored to blue
>   inline).
> - Most operator usages render an inline-styled `.card` with a
>   bespoke border + background per case (rf-save-error,
>   rtd-error, rtd-would-empty, rtd-delete-blocked in
>   `instruments_index.html`; missing-confirm, upload-blocked in
>   `session_assignments.html`; the cross-template "session is
>   ready" amber warning).
> - All carry `banner-scroll-target` and a stable id used by the
>   Cancel-return anchor.
> *Canonical:* four banner variants matched to the four semantic
> accents:
> - `.banner.banner-info` (`accent-blue` light bg, `accent-blue`
>   border, `text-primary` body) — preview-mode notice on
>   reviewer surface.
> - `.banner.banner-success` (`accent-green`) — submission
>   confirmation on reviewer surface.
> - `.banner.banner-warning` (`accent-amber`) — lifecycle-locked
>   notices, missing-required acknowledgements, cascade
>   confirmations.
> - `.banner.banner-error` (`accent-red`) — Could-not-save /
>   Could-not-delete inline errors.
> All four reuse a single `.banner` base (padding, radius,
> border-width, scroll-target hooks). Cancel button (per
> `assumptions.md` "Inline error / warning banners") stays.
> *Migration delta:* introduce four-variant `.banner` family;
> retire `.warning-banner` / `.danger-banner` standalones; sweep
> every inline-styled banner-card across operator and reviewer
> surfaces.
> *PR:* C (cards & banners).

### 6. Buttons

The original #21 brief. Six canonical affordance × treatment styles
listed in `assumptions.md` map onto `visual_style.md`'s
Primary / Secondary / Destructive trio as follows.

| Today (`.btn` modifier) | Canonical name (visual_style.md) | Notes |
|---|---|---|
| `.btn` (no modifier) | **Primary** | Solid `accent-blue`, white text. Lower saturation than today. |
| `.btn.secondary` | **Secondary** | White bg, `border-default`, `text-primary`. *Today this renders blue text on white — visual_style retires the colored secondary in favor of neutral text.* |
| `.btn.alert` | **Secondary (warning context)** or retire | visual_style.md does not define a free-standing "alert outline" button. Resolve case-by-case — most usages (banner Cancel) become Secondary; lifecycle-state changers become Primary. |
| `.btn.alert-solid` | **Primary** for lifecycle-changing actions ("Revert to draft", "Activate session") | visual_style.md collapses the orange solid into Primary. The action's gravity is communicated by the surrounding context (lock card, confirm-step), not the button color. |
| `.btn.danger-solid` | **Destructive** | White bg, `accent-red` border + text. *Today renders red fill — visual_style flips it to outline.* Used as the **confirmation step** of destructive actions. |
| `.btn.danger` | **Destructive** (entry point) or **Secondary** | Where `.danger` is the entry into a confirmation, prefer Secondary; the destructive treatment lands on the confirm step. |
| `.btn-cta` | **Primary (large / centered variant)** | Layout variant only. Keep, but normalize fill to Primary. |
| `.btn-cta.disabled` | **Primary (disabled)** | Opacity 0.5, no fill change beyond opacity. |
| `.btn-icon` | **Icon button** | Borderless inline action (move-up / move-down / delete-row). Keep; add canonical disabled treatment. |

> **Disabled anchor-as-button** — anchors used as buttons that
> render disabled (Edit Reviewers / Edit Reviewees on the manage
> pages, Extract Data CTA on Session Home).
> *Current:* inconsistent — `.btn.alert-solid.disabled` with
> `aria-disabled="true"` and ad-hoc inline
> `style="opacity: 0.5; pointer-events: none;"` in some places;
> `.btn.secondary.disabled` in others.
> *Canonical:* one `.btn.disabled` rule that handles both
> `<button disabled>` and `<a class="btn disabled" aria-disabled>`,
> matching visual_style.md's "Disabled — same shape as the role
> variant; reduced opacity (0.5) and `cursor: not-allowed`".
> *Migration delta:* unify; remove inline overrides.
> *PR:* B (buttons).

> **Inline-style buttons** — ad-hoc buttons that bypass the `.btn`
> family entirely.
> *Current:* found in `instruments_index.html` (rf-delete /
> rf-add row buttons using inline `style="background: none;
> border: none; color: #dc2626/#2563eb"`); `session_detail.html`
> (Delete Data / Delete session with inline
> `style="background: #b91c1c; border-color: #b91c1c;"`);
> `review_surface.html` ("Clear all" with the same inline red).
> *Canonical:* all migrate to a canonical class — Destructive for
> the danger-zone forms, `.btn-icon` (or a new `.btn-icon.danger`
> variant) for the row-level rf-delete.
> *Migration delta:* sweep; delete inline styles.
> *PR:* B (buttons).

### 7. Tables

> **Default table** — header row in `bg-muted` with small
> medium-weight `text-secondary` labels; body rows white with
> `border-subtle` 1px bottom border per row; no zebra; subtle
> hover tint.
> *Current:* global `table` rule in `base.html` uses
> `border-collapse: collapse; width: 100%`; `th, td { border: 1px
> solid #ddd; padding: 4px 8px; }` (full grid, every cell
> bordered); `th { background: #f4f4f4; }`. Two divergences from
> visual_style.md: full grid lines (spec calls for row-only) and
> tight `4px 8px` cell padding (spec calls for `12px 16px`).
> *Canonical:* row-only borders, generous cell padding, hover tint.
> *Migration delta:* rewrite global `th, td` rules; some dense
> tables (Display Fields, Response Fields, RTD on instruments
> page) may need a `.table-dense` opt-in if 12/16 padding makes
> them too tall.
> *PR:* E (tables).

> **`.table-scroll`** — wrapper that adds `overflow-x: auto` for
> wide tables.
> *Current:* one rule in `base.html`. Used widely on
> `instruments_index.html` and around `review_surface.html`'s
> response table.
> *Canonical:* keep as-is.
> *Migration delta:* none.

> **`.col-shrink`** — width-1% no-wrap idiom for action columns
> that should hug the right edge.
> *Current:* one rule in `base.html`. Used on
> `sessions_list.html` Actions column.
> *Canonical:* keep; rename in docs to "shrink-to-fit column" for
> clarity.
> *Migration delta:* none.

> **Reviewer-table column-width hints (`.rs-narrow`,
> `.rs-reviewee`, `.rs-textlong`)** — column-shape hints for the
> response-input table on the reviewer surface.
> *Current:* defined in `base.html`, applied dynamically in
> `review_surface.html` based on RTD `data_type`.
> *Canonical:* keep. These are reviewer-surface specific and
> don't conflict with the general table treatment.
> *Migration delta:* none beyond palette token swap during PR A.

### 8. Forms / inputs

> **Text input / textarea / datetime-local** — white bg,
> `border-default`, `border-radius: 6px`, body text size,
> `8px / 12px` padding.
> *Current:* global `input[type="text"], textarea,
> input[type="datetime-local"]` rule in `base.html` uses
> `border: 1px solid #ddd; border-radius: 6px; padding: 8px;
> font-size: 1em; width: 100%`. Close to spec; padding is even
> 8px instead of 8/12; border color is `#ddd` rather than
> `border-default` (`#D1D5DB`).
> *Canonical:* asymmetric padding `8px 12px`; tokenize border.
> *Migration delta:* small.
> *PR:* F (forms).

> **`<select>` / `<input type="file">` / `<input type="number">`
> / `<input type="checkbox">` / `<input type="radio">`** —
> currently un-styled (browser defaults). visual_style.md does
> not yet specify treatment.
> *Current:* browser defaults.
> *Canonical:* spec to be written. For #21 we adopt the minimum:
> match `input[type="text"]` border-color and radius on `select`;
> leave checkbox / radio as native; leave `file` as native.
> *Migration delta:* minor — `select` only.
> *PR:* F (forms).

> **Label** — above the input, small text size, `text-primary`
> medium weight, 4px gap.
> *Current:* global `label` rule in `base.html`:
> `display: block; margin-top: 12px; font-weight: 600`. Bold
> rather than medium; 12px stack rather than 4px.
> *Canonical:* `font-weight: 500`, `margin-bottom: 4px` to the
> input that follows; the 12px section-stack belongs on the
> wrapping form group, not the label.
> *Migration delta:* tune.
> *PR:* F (forms).

> **Helper text / error text** — currently inconsistent (mix of
> `<p class="muted">` and inline `<small>`).
> *Canonical:* small text size, `text-secondary` for help,
> `accent-red` for error, sit below the input.
> *Migration delta:* introduce `.form-help` and `.form-error`
> classes; sweep usages.
> *PR:* F (forms).

> **Inline-edit pattern (`.display-edit`, `.instrument-edit`,
> field-builder details/summary)** — `<details>` shells for inline
> label edits with tick/cross affordances. Used on the
> Instruments page.
> *Current:* defined in `base.html` and `assumptions.md`. Works.
> *Canonical:* keep; verify the toggled-in inputs pick up the
> standard input treatment after PR F.
> *Migration delta:* none structurally.

### 9. Badges / pills

| Today (`.pill` modifier) | Canonical name | Notes |
|---|---|---|
| `.pill` (base) | base pill — pill shape, tiny medium-weight text | shape stays, palette tokenized |
| `.pill-info` (blue) | overloaded today — used for counts AND for "ready"/"opened"/etc. lifecycle-ish state | split into **`.pill-count`** (`bg-muted` / `text-primary`, neutral) and **`.pill-state-ready`** (`accent-green`) — see lifecycle table below |
| `.pill-warning` (amber) | **`.pill-empty`** for missing/empty counts; **`.pill-state-draft`** for draft lifecycle (visual_style.md Part 2 makes draft neutral grey, so revisit) | |
| `.pill-success` (green) | **`.pill-state-ready`** | |
| `.pill-error` (red) | **`.pill-error-count`** — used in validation summary for error counts. Keep `accent-red` light. | |
| `.pill-handle` (grey monospace) | **`.pill-handle`** — keep, tokenize | |

> **Lifecycle badges (specific to status strip)** — per
> `visual_style.md` Part 2:
> - `draft` → neutral grey (`text-secondary` on `bg-muted`)
> - `validated` → muted blue (`accent-blue`)
> - `ready` → muted green (`accent-green`)
> - `closed` → neutral grey, slightly darker than draft
> *Current:* rendered as `.pill.pill-info` / `.pill.pill-warning`
> indiscriminately across `session_detail.html`,
> `session_setup_status_row.html`, `sessions_list.html`,
> `session_invitations.html`, `session_monitoring.html`.
> *Canonical:* one `.pill-lifecycle-{draft|validated|ready|closed}`
> set. Lifecycle badge always renders through this set, never
> through generic `pill-info`.
> *Migration delta:* introduce classes; sweep templates.
> *PR:* G (badges).

> **Status-symbol indicators (✓ / ⚠ in reviewer response table)**
> *Current:* inline-styled Unicode glyphs with per-symbol
> `style="color: #16a34a/#d97706; font-weight: bold;
> font-size: 1.2em;"` in `review_surface.html`.
> *Canonical:* `.status-icon.status-icon-complete` /
> `.status-icon-incomplete` classes; tokenize colors.
> *Migration delta:* small extraction.
> *PR:* G (badges).

### 10. Layout primitives

Most of these are already canonical. The audit confirmed they're
used consistently; the migration just tokenizes their colors and
spacing.

| Class | Status | PR |
|---|---|---|
| `.page-grid` + placement classes (`.card-tl/r/bl/l/tr/br`) | keep, gap → spacing token | A |
| `.bottom-grid` + `.bottom-left` | keep, gap → token | A |
| `.btn-row` (equal-flex) | keep | — |
| `.btn-pair` (inline pair) | keep | — |
| `.setup-grid` (4-col grid for Session Setup card) | keep | — |
| `.fill-col` (flex column where last child grows) | keep | — |
| `.card-half` (`max-width: calc(50% - 10px)`) | keep | — |
| `.session-meta-row`, `.session-status-row` | keep | — |
| `.field-builder` + `.field-builder.locked` | keep | — |

`.setup-nav` is a candidate for deletion (see §2).

### 11. Misc one-offs

> **`.btn-icon`** — borderless inline action (move-up, move-down,
> rf-delete, rf-add). Keep; add `.btn-icon.danger` modifier so the
> red rf-delete inline `style` can be retired.
> *PR:* B.

> **`<pre>` blocks (outbox preview)** — currently inline-styled in
> `session_outbox.html` (`background: #f3f4f6; padding: 12px;
> border-radius: 4px; white-space: pre-wrap`). Promote to
> `.code-block`.
> *PR:* C (cards & banners) — same family as content surfaces.

> **`form style="display: contents;"`** — layout hack on RTD edit
> form in `instruments_index.html`. Out of scope for #21; flag for
> a separate cleanup.

> **Inline JS event handlers** — heavy use of `onclick="…"` and
> `onsubmit="return confirm(…)"` in `instruments_index.html`. Out
> of scope for #21; flag for a separate cleanup.

---

## Part 2 — Drift catalogue

Cross-cutting list of inline styles, unique classes, and inconsistent
treatments the audit surfaced. Each entry names the offender and the
target canonical element from Part 1.

**Banner cards rendered with inline `style` attributes** rather than
a banner class:
- `instruments_index.html` — rf-save-error, rtd-error,
  rtd-would-empty, rtd-delete-blocked banners.
- `session_assignments.html` — missing-confirm, upload-blocked.
- Cross-template "session is ready" amber warning card on every
  Setup page when the session is locked.
- `review_surface.html` — success (green), submitted (blue),
  warning (amber), session-closed (amber), preview-mode (blue
  via recolored `.warning-banner`).
- `invite_mismatch.html` — danger card.
→ all become **`.banner.banner-{info|success|warning|error}`** (§5).

**Danger Zone cards** rendered with inline `style="border-color:
#b91c1c"` (and inconsistent `background`):
- `session_detail.html`, `session_reviewers.html`,
  `session_reviewees.html`, `session_assignments.html`,
  `instruments_index.html`.
→ all become **`.card.danger-zone`** (§4).

**Inline-styled buttons** that bypass the `.btn` family:
- `instruments_index.html` rf-delete / rf-add row buttons.
- `session_detail.html` Delete Data / Delete session.
- `review_surface.html` "Clear all".
→ rf-delete / rf-add → `.btn-icon` + `.btn-icon.danger`; the rest
  → Destructive (§6).

**Disabled anchor-as-button** styling:
- `.btn.alert-solid.disabled` + inline opacity + pointer-events
  (`instruments_index.html`).
- `.btn.secondary.disabled` (`session_reviewees.html`,
  `session_reviewers.html`).
- `.btn.alert-solid.disabled` (`session_detail.html` Extract Data).
→ unify under one `.btn.disabled` rule (§6).

**Inline `style="color: #b91c1c;"` on Danger Zone H2** —
`session_detail.html`, others.
→ subsumed by `.card.danger-zone` H2 rule (§4).

**Lifecycle pills using generic `.pill-info` / `.pill-warning`** —
every page that shows session lifecycle.
→ use `.pill-lifecycle-{draft|validated|ready|closed}` (§9).

**Reviewer-surface status icons (✓ / ⚠) inline-styled** —
`review_surface.html`.
→ `.status-icon-complete` / `.status-icon-incomplete` (§9).

**Reviewer-surface `<h2 style="margin-top: 24px;">`** for
instrument group headings, and `<h2 style="color: #b91c1c;">` for
the Clear-all section — both inline overrides on H2.
→ section-spacing belongs on the wrapping section, not the H2; the
  red H2 is subsumed by `.card.danger-zone` (§4) and (§3).

**Per-instrument card cycling backgrounds** —
`style="background: {{ instrument_palette[…] }}"` on instrument
cards in `instruments_index.html`. Out of scope for the restyle
(it's a domain feature, not chrome). Flag only.

---

## Part 3 — Restyle bundle PR split

Expanded scope of `unfinished_business.md` #21. Suggested order is
**A → B → C → D → E → F → G**. Each PR is independently shippable
once A lands.

**PR A — Tokens & primitives (foundation).**
Introduce CSS custom properties for the visual_style palette,
type scale, and spacing scale at the top of `base.html`'s
`<style>` block. Rewrite the global rules that consume them
(`body`, `h1`, `h2`, `a`, `label`, `.muted`, `.page-subtitle`,
the `.page-grid` / `.bottom-grid` gap values). No visible
template change beyond a small overall recoloring; sets the
groundwork every later PR depends on.

**PR B — Buttons.**
Migrate the `.btn` family to the visual_style Primary / Secondary
/ Destructive vocabulary per the table in §6. Adopt one
`.btn.disabled` rule for both `<button>` and anchor-as-button
disabled states. Sweep every inline-styled button (the three
locations called out in the drift catalogue) onto canonical
classes. Touches every operator and reviewer template that
renders a button — the largest mechanical sweep in the bundle.

**PR C — Cards & banners.**
Re-tune `.card` to spec (1px border, 8px radius, palette token);
introduce `.card.lock`, `.card.danger-zone`, and the four-variant
`.banner` family; sweep templates to retire every inline-styled
card / banner. Promote the outbox `<pre>` to `.code-block`.

**PR D — Navigation chrome.**
Repaint `.session-nav-card` row tints to per-row accent (5% of
`accent-blue` and `accent-green`); recolor the active-tab
underline; tighten `.row-label` typography; rewrite
`session_setup_status_row.html` to the canonical middle-dot
status strip; lift the lifecycle badge into the strip; recolor
the breadcrumb separator and chrome border to palette tokens;
restyle the chrome Sign-out as a Secondary button. Delete
unused `.setup-nav` rule once verified.

**PR E — Tables.**
Switch the global `th, td` rule from full-grid to row-only
borders, bump cell padding to `12px / 16px`, recolor the header
background to `bg-muted`, add the subtle hover tint. Add a
`.table-dense` opt-in for the three Instruments-page tables if
the new padding makes them too tall.

**PR F — Forms.**
Tune input padding to `8px / 12px`, tokenize border colors,
align focus state with spec, restyle `label` to medium weight
with 4px gap, introduce `.form-help` and `.form-error` classes
and sweep usages. Lightly normalize `<select>` to match.

**PR G — Badges.**
Split `.pill-info` into `.pill-count` (neutral) and lifecycle
classes; introduce `.pill-lifecycle-{draft|validated|ready|closed}`
and the reviewer-surface `.status-icon-{complete|incomplete}`;
sweep every lifecycle-pill site to use the new classes.

After G ships, the prerequisites for #22 (Home body rebuild +
Option F sub-card relocation) and #30 (Quick Setup card on Home)
are met: every primitive #22/#30 want to compose with is in place
and named.

---

## Open questions

- **Session-scoped chrome on the reviewer surface?** Audit
  confirmed the reviewer surface has no `.session-nav-card` and
  uses a flat heading layout. visual_style.md is silent on this.
  Likely correct as-is (reviewers are not navigating the session;
  they're filling in one form), but worth confirming before PR D.
- **`.alert` outline button retire path.** visual_style.md
  doesn't define an "alert outline" tier. Most current `.alert`
  usages (banner Cancel buttons) become Secondary; but the
  Inactivate / lifecycle-edge buttons may want a distinct
  treatment. Decide during PR B.
- **Tab-row tints — `accent-blue`/`accent-green` at 5% or stay
  neutral grey?** visual_style.md Part 2 specifies the per-row
  accent tint, but the current neutral-grey + light-green pairing
  (`#f3f4f6` / `#f0fdf4`) reads calmer in practice. Trial both
  during PR D and pick.
