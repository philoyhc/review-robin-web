# UI elements catalogue

> **Status (2026-05-03):** Pilot-validated. Initial audit-derived draft;
> then iterated through `/operator/sessions/{id}/reviewers1` (the
> first page on `body.ui-v2`) over PRs #333 → #341. Pilot-derived
> principles have been folded back into `spec/visual_style_general.md`. This
> doc is now the implementation catalogue: it tracks per-element
> current state, canonical naming, and the rollout status across the
> seven-PR migration plan in Part 3.
>
> **Reference implementation.** `app/web/templates/operator/session_reviewers1.html`
> + the `body.ui-v2`-scoped block in `app/web/templates/base.html`
> together show every primitive in this catalogue in working form.
> When porting a page to v2, mirror that template's class usage.

This document expands `unfinished_business.md` #21 from a buttons-only
restyle into a full operator-surface settling pass covering navigation
chrome, cards, tables, buttons, forms, banners, badges, and layout
primitives. It is split into:

- **Part 1 — Element catalogue.** One section per element family.
  Each entry lists the canonical name, the canonical visual treatment
  (per `spec/visual_style_general.md`), the current implementation in
  `base.html` and templates, and the migration delta.
- **Part 2 — Drift catalogue.** Cross-cutting list of one-off
  inline styles, unique classes, and inconsistent treatments the
  audit surfaced.
- **Part 3 — Restyle bundle PR split.** Suggested chunking of the
  expanded #21 work into ~6 PRs.

Cross-references:

- **`spec/visual_style_general.md`** — authoritative design system (palette,
  type scale, spacing, component shapes, app-specific accent
  assignments). This catalogue instantiates that spec against the
  current codebase.
- **`spec/assumptions.md`** — current "as-built" UI vocabulary
  (`.btn` family, layout primitives, banner conventions). Sections
  marked superseded there are pointers into this doc.
- **`spec/operator_ui_concept.md`** — page-level chrome and per-page
  layout contracts that consume these primitives.
- **`spec/reviewer-surface.md`** — reviewer-surface page contracts.

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
> `visual_style_general.md`.
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
> *Canonical:* match `visual_style_general.md` "Breadcrumb" pattern (no home
> icon, small text, consistent spacing).
> *Migration delta:* swap `#999` separator for `text-muted` token;
> verify type scale.
> *PR:* D (chrome).

### 2. Session-scoped chrome

> **`.session-nav-card`** — the two-row navigation card with the
> double-height Home anchor on the left and Setup / Operations tab
> rows on the right. Specified in detail in
> `spec/visual_style_rrw.md` "Operator session chrome > Navigation chrome (two-row layout)".
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
> *Canonical:* `visual_style_rrw.md` "Operator session chrome > Status strip" — middle-dot
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
> *Canonical:* `visual_style_general.md` "Type scale" — explicit `1.5rem`
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

> **`.card` (default)** — white surface, `border-default` 2px border,
> `border-radius: 8px`, 16px padding.
> *v1:* `border: 2px solid #bbb; border-radius: 12px; padding: 20px`.
> *v2 (pilot-validated):* `border: 2px solid var(--border-default);
> border-radius: var(--radius-card); padding: var(--space-4)`. The
> 1px border in the original spec was visually swallowed by table
> grid lines and form borders — bumped to 2px during the pilot.
> *Migration delta:* sweep page-by-page; the v2 rule already lives
> under `body.ui-v2` so any opted-in template picks it up.
> *PR:* C (cards & banners) — landed in pilot.

> **`.card.lock` (warning-framed, lifecycle-locked)** — same shape
> as `.card`, with `accent-amber-bg` background and
> `accent-amber-dark` border (the warning brown). Recovery action
> inside uses outline-amber button (see §6).
> *v1:* not a class — inline-styled `.card` with bespoke amber
> border + bg per page.
> *v2 (pilot-validated):* `.card.lock` rule under `body.ui-v2`.
> *Migration delta:* sweep templates to replace inline amber cards
> with `.card.lock`.
> *PR:* C (cards & banners) — class landed; per-template sweep
> still pending for the rest of the operator surface.

> **`.card.danger-zone` (warning-framed, destructive grouping)** —
> same shape as `.card`, white background, `accent-amber-dark`
> border (same warning brown as `.card.lock` — both warning
> surfaces share one visual language), H2 in `accent-amber-dark`.
> Destructive button inside stays outline-`accent-red` (the action
> that actually deletes data) — the brown frames the surface, the
> red marks the action.
> *v1:* not a class — inline-styled `.card` with bespoke red
> border (and inconsistent backgrounds) per page.
> *v2 (pilot-validated):* `.card.danger-zone` rule under
> `body.ui-v2`.
> *Migration delta:* sweep `session_detail.html`,
> `session_reviewees.html`, `session_assignments.html`,
> `instruments_index.html` to use the class; drop inline
> `style="color: #b91c1c"` H2 overrides.
> *PR:* C (cards & banners) — class landed; per-template sweep
> still pending.

> **`.card.placeholder` (canonical placeholder treatment)** — same
> shape as `.card`, with `bg-muted` background, `text-muted` H2,
> `text-secondary` body, `not-allowed` cursor on the whole card.
> Used for cards whose underlying feature is not yet implemented;
> every instance reads as visually identical so siblings on the
> same page render with the same typography and contrast
> regardless of which is in its "active" lifecycle state.
> *v1:* not a class — placeholder cards mixed with active cards
> rendered identically (default `.card`), distinguished only by
> a "(under construction)" body line.
> *v2 (Segment 11B):* `.card.placeholder` rule under
> `body.ui-v2`; a Jinja macro `placeholder_card(id, title,
> description, button_label, button_tooltip)` in
> `app/web/templates/operator/partials/_placeholder_card.html`
> packages the canonical heading + body + disabled action
> button. Used on Session Home (Quick Setup, Extract Data) and
> the Assignments page (Rule Based Assignment). New placeholder
> cards on any page should reuse the macro without further
> design work.
> *Migration delta:* none — canonical from the start.
> *PR:* Segment 11B (PRs C / D / 386 / 387 / 388).

> **`.card.next-action` (Session Home's Next Action card)** —
> same shape as `.card`, with `accent-blue` border (matching the
> Primary button inside) and `display: flex; flex-direction: column`.
> No fixed `min-height` — the card grows to fit its content. Three
> vertically-stacked children:
> `.next-action-body` (flex-grows), optional `.next-action-confirm`
> (sits just above the buttons), and `.next-action-buttons`
> (Primary + Secondary buttons in one row at the bottom). The
> H2 is the literal constant string "Next Action"; per-state
> action verbs live in the primary button label, not the H2.
> The blue border signals this is the page's single most
> important card. POST forms (Activate / Revert to draft /
> Pause) declare an id in the body and the button declares
> `form="next-action-{name}-form"` so the form definition stays
> near its checkbox while the submit button lives in the bottom
> row.
> *v1:* not a class — Home rendered four equal-weight CTAs in a
> "Run Session" card.
> *v2 (Segment 11B):* `.card.next-action` rule under
> `body.ui-v2`; spec at `spec/session_home.md`.
> *Migration delta:* none — net-new in 11B.
> *PR:* Segment 11B (PRs B / 390 / 391 / 392 / 393).

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

The original #21 brief. Pilot-validated. Six v1 affordance × treatment
styles map onto a refined Primary / Secondary / Destructive / Outline-amber
vocabulary as follows.

| v1 (`.btn` modifier) | v2 canonical | Notes |
|---|---|---|
| `.btn` (no modifier) | **Primary** | Solid `accent-blue`, white text. Reserved for the page's *single* main affirmative action — at most one per page region. "Submit this form" doesn't qualify; routine submits use Secondary. |
| `.btn.secondary` | **Secondary** | White bg, `border-default`, `text-primary`. The default button. Used for routine submits (Upload, Save), Cancel, View detail, etc. |
| `.btn.alert` | **Outline-amber (recovery in lock card)** | White bg, `accent-amber-dark` border + text. Per `visual_style_general.md` P7, recovery actions inside a lock card adopt the card's color family. Used e.g. for "Revert to draft" inside a `.card.lock`. |
| `.btn.alert-solid` | **Primary** | The orange solid collapses to Primary. The action's gravity is communicated by the surrounding context (lock card, confirm-step), not the button color. |
| `.btn.danger-solid` | **Destructive** | White bg, `accent-red` border + text. Used as the **confirmation step** of destructive actions. Lives inside `.card.danger-zone` — the brown frames the surface, the red marks the action. |
| `.btn.danger` | **Destructive** (entry point) or **Secondary** | Where `.danger` is the entry into a confirmation, prefer Secondary; the destructive treatment lands on the confirm step. |
| `.btn-cta` | **Primary (large / centered variant)** | Layout variant only. Keep, but normalize fill to Primary. |
| `.btn-cta.disabled` | **Primary (disabled)** | Opacity 0.5, `pointer-events: none`. Same disabled rule as the regular Primary. |
| `.btn-icon` | **Icon button** | Borderless inline action (move-up / move-down / delete-row). Keep; add canonical disabled treatment. |
| `.btn-reset` | **Inline text-button** (revert-this-field) | Single-line link-styled button used to revert a single text field inside an editor without cancelling and exiting the whole editor. Reference example: per-field `Reset {{ field }} to default` on the Email Template page (`session_setupinvite.html`). Reads as a small inline link (`color: accent-blue`, underline-on-hover); posts a form. The pattern can apply to any editor with per-field overrides — adopt this class instead of inline-styled buttons. |
| `.nav-tab` (chrome class, reused for page-internal) | **Nav button** (page-internal view switcher) | Page-internal tab-like navigation between sibling views inside a single operator page — *not* the chrome. Reference examples: Email Template's `Invitation` / `Reminder` / `Responses received` row (`session_setupinvite.html`); Previews-page email-tab strip (`partials/_email_preview_region.html`). Reuses the chrome's `.nav-tab` styling so the visual vocabulary stays consistent: active view renders `<span class="nav-tab active" aria-current="page">` (non-anchor, current location), sibling views render `<a class="nav-tab">` anchors, "coming soon" reserved tabs render `<span class="nav-tab disabled" aria-disabled="true">`. Wrap in a `.tab-strip` flex container. No new CSS classes — sweep is template-only. |

**Hover** (per `visual_style_general.md` P6 — pilot-validated):
- *Filled buttons* (Primary, `.alert-solid`): bg/border move from `accent-blue` to `accent-blue-light` (lighten).
- *Outline buttons* (Secondary, Destructive, Outline-amber): subtle background tint in the role's family (`bg-muted`, `accent-red-bg`, `accent-amber-bg-mid`).
- Disabled buttons skip via `pointer-events: none`.

> **Disabled anchor-as-button** — anchors used as buttons that
> render disabled (Edit Reviewers / Edit Reviewees on the manage
> pages, Extract Data CTA on Session Home).
> *Current:* inconsistent — `.btn.alert-solid.disabled` with
> `aria-disabled="true"` and ad-hoc inline
> `style="opacity: 0.5; pointer-events: none;"` in some places;
> `.btn.secondary.disabled` in others.
> *Canonical:* one `.btn.disabled` rule that handles both
> `<button disabled>` and `<a class="btn disabled" aria-disabled>`,
> matching visual_style_general.md's "Disabled — same shape as the role
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
> visual_style_general.md: full grid lines (spec calls for row-only) and
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
> currently un-styled (browser defaults). visual_style_general.md does
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

Pilot-validated. Pill shape (`9999px` radius, tiny uppercase text,
medium weight 500). Used both standalone (status indicators) and
inline in copy — e.g. confirm labels wrap count phrases as pills so
the eye lands on the numbers without bolding the whole sentence.

| v1 (`.pill` modifier) | v2 canonical | Notes |
|---|---|---|
| `.pill` (base) | base pill — uppercase tiny text, weight 500 | text-transform: uppercase kept from v1 |
| `.pill-info` (blue) | aliased to **`.pill-count`** under v2 — `accent-blue-bg` background, `text-primary` text | the blue tint signals "this is information" without implying state. Existing `.pill-info` markup picks up the new treatment. |
| `.pill-warning` (amber) | aliased to **`.pill-empty`** under v2 — `accent-amber-bg` background, `accent-amber-dark` text | warning brown, matches the `.card.lock` / `.card.danger-zone` border color so chips and surfaces share one warning language. Existing `.pill-warning` markup picks up the new treatment. |
| `.pill-success` (green) | **`.pill-state-ready`** (or `.pill-success`) — `accent-green-bg`, `accent-green` text | unchanged from v1 in spirit |
| `.pill-error` (red) | **`.pill-error-count`** — `accent-red-bg`, `accent-red` text | for validation-summary error counts |
| `.pill-handle` (grey monospace) | **`.pill-handle`** — keep | tokenize colors |

> **Lifecycle badges (specific to status strip)** — per
> `spec/visual_style_rrw.md` "Lifecycle state colors":
> - `draft` → warning amber (`accent-amber-dark` on `accent-amber-bg`)
> - `validated` → muted blue (`accent-blue`)
> - `ready` → muted green (`accent-green`); rendered as "Activated"
>   in user copy via the lifecycle display-label mapping
>   (`spec/session_home.md`)
> *Current:* rendered as `.pill.pill-info` / `.pill.pill-warning`
> indiscriminately across `session_detail.html`,
> `session_setup_status_row.html`, `sessions_list.html`,
> `session_invitations.html`, `session_monitoring.html`.
> *Canonical:* one `.pill-lifecycle-{draft|validated|ready}` set
> covering the three live states. Reserved future states
> (`expired`, `archived`, per `spec/session_home.md`) get classes
> when those states ship. Lifecycle badge always renders through
> this set, never through generic `pill-info`.
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
→ use `.pill-lifecycle-{draft|validated|ready}` (§9).

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

Expanded scope of `unfinished_business.md` #21. The seven PRs land
in order **A → B → C → D → E → F → G**. The pilot drove all seven
through `/operator/sessions/{id}/reviewers1` — the foundation +
canonical primitives are in place under `body.ui-v2`. The remaining
work is a per-template **sweep**: replicate the `/reviewers1` recipe
on every other operator (and reviewer) page, then promote the
`body.ui-v2` rules to default and retire the wrapper.

| PR | Scope | Status |
|---|---|---|
| **A** | Tokens & primitives (palette / type / spacing custom properties; global rule rewrites) | **Foundation landed in pilot.** Token shade ladders extended through the iteration (PRs #334, #336, #337, #338, #341). |
| **B** | Buttons — Primary / Secondary / Destructive / Outline-amber vocabulary; unified `.btn.disabled`; inline-style sweep | **Classes landed**, applied on `/reviewers1`. Per-template sweep across the rest of the operator surface still pending. |
| **C** | Cards & banners — `.card`, `.card.lock`, `.card.danger-zone`, four-variant `.banner` family | **`.card` / `.card.lock` / `.card.danger-zone` landed**, applied on `/reviewers1`. Banner family defined but not yet used on a page (next pilot target: a page with a real banner, e.g. `instruments_index.html`). |
| **D** | Navigation chrome — `.session-nav-card` recolor, lighter Home anchor, bold tab text, lighter active-tab markers, restored row-label emphasis, status-row white background | **Landed in pilot** (PRs #336, #338, #341). The `session_setup_status_row.html` middle-dot rewrite + lifecycle-badge lift was deferred — strip is already close to spec on structure; revisit if visual feedback warrants. |
| **E** | Tables — row-only borders, `12 / 16` padding, `bg-muted` header, subtle hover tint | **Landed in pilot.** Table on `/reviewers1` uses the v2 treatment. `.table-dense` opt-in for the Instruments-page tables not yet needed. |
| **F** | Forms — input padding `8 / 12`, tokenized borders, `.form-help` / `.form-error`, label medium weight | **Landed in pilot.** `/reviewers1` uses `.form-help` for the CSV instructions; file input + checkboxes carry the v2 treatment. |
| **G** | Badges — `.pill-count` (neutral) and lifecycle classes (`.pill-lifecycle-{draft\|validated\|ready}`), reviewer-surface `.status-icon-*` | **`.pill-count` and `.pill-empty` landed** with the refined blue-tint / brown-on-yellow treatments. Lifecycle classes still pending — `session_setup_status_row.html` still emits generic `.pill-info` for the lifecycle badge; the v2 treatment of `.pill-info` is "count" which is acceptable as a placeholder. Reviewer status icons not yet introduced. |

Once the sweep across the rest of the operator surface lands (the
mechanical work to replicate `/reviewers1` page-by-page), the
prerequisites for #22 (Home body rebuild) and #30 (Quick Setup
card on Home) are met: every primitive #22/#30 want to compose
with is in place and named.

---

## Pilot decisions worth remembering

The pilot resolved the original Open questions and surfaced a few
new patterns:

- **Hover by fill** (now `visual_style_general.md` P6). Filled controls
  lighten on hover; outline controls darken with a subtle bg
  tint in their role's color. One direction across buttons,
  nav anchors, tinted cells.
- **Recovery actions in colored cards** (now `visual_style_general.md`
  P7). Action picks up the card's color family rather than
  reasserting Primary blue. Two concrete cases: outline-amber
  Revert-to-draft inside `.card.lock`; outline-red Destructive
  inside `.card.danger-zone`.
- **Warning surfaces share one brown.** Lock card and danger
  zone both border in `accent-amber-dark`. The interior
  treatments differ but the framing is one.
- **Primary used sparingly.** "Submit this form" doesn't qualify
  as Primary; routine submits like Upload are Secondary.
  Reserve Primary for the page's single main affirmative
  action.
- **Pills inline in copy.** Confirm labels wrap count phrases as
  `.pill-empty` chips so the eye lands on the numbers without
  bolding the whole sentence.
- **`.bottom-grid` for natural-height pairs.** When two cards in
  a 2-column layout don't carry the same weight, prefer
  `.bottom-grid` over `.page-grid`. `.page-grid`'s
  equal-height stretch is for the L-shape patterns that
  actually need it (`session_detail.html`).
- **Reviewer-surface chrome is intentionally minimal.** No
  `.session-nav-card` — reviewers fill one form, they don't
  navigate the session. Confirmed during the audit; left
  alone in the pilot.
