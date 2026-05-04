# Assumptions

> **Note (2026-05-03):** The visual sections (button styles, layout
> primitives, typography) overlap with `spec/visual_style_general.md`
> and `spec/visual_style_rrw.md`, which are now authoritative for the
> visual design system. Where this file disagrees with them, the
> visual_style docs win. A reconciliation pass is pending.

A living record of the load-bearing assumptions — both domain
shape and visual conventions — that the app is built around.
Update this file when you introduce a new structure or named
style; reference these names in code reviews and PR descriptions
instead of describing them from scratch.

## Domain

### Hierarchy of structures

#### Session

Contains the same universe of Reviewers, Reviewees, Assignments,
1-6 Instruments and their associated Response Forms, Email,
deadline.

At any one time, operating under one assignment mode (FullMatrix,
Manual, RuleBased; note that FullMatrix should be absorbed as a
particular rule set).

Status: Draft, Ready (when populated sufficiently, within
deadline), Expired (when deadline has passed), Archived (data
collected has been downloaded and deleted).

Session can be edited when instruments are closed/paused; if there
are ongoing reviews, reviewers need to be notified.

Note: While Session is the top level structure, there should be a
way to put arbitrarily assign them to Groups. Sessions can be
duplicated (without the response data).

#### Instrument

Associated with one set of response questions (ratings, comments,
etc.) and their instructions.

Status: Draft, Receiving responses, Closed/Paused.

Closed/Paused defaults to keeping existing responses invisible to
reviewers, but visibility can be turned on.

Instrument can be edited when closed/paused; if there are ongoing
reviews, reviewers need to be notified.

Instrument automatically closes upon session deadline.

## UI

### Button styles

> **Superseded (2026-05-03).** The six-style affordance×treatment
> matrix below describes the *current* CSS in `base.html`, which
> `spec/visual_style_general.md` retires. The general visual-style
> spec is now authoritative for button styling and replaces this
> hierarchy with a muted Primary / Secondary / Destructive
> vocabulary. The migration to those new styles is tracked as
> `unfinished_business.md` #21. Until that ships, the table below
> still describes what's in the templates today.

The app uses six canonical button styles. Each is described by
**affordance × treatment** (`primary`/`alert`/`danger` × `solid`/`outline`):

| Name | Fill | Text | Stroke | Use for |
|---|---|---|---|---|
| **Primary** | blue (`#2563eb`) | white | blue (`#2563eb`) | Default action: form submit, navigation, "do the thing". |
| **Primary Outline** | white | blue (`#2563eb`) | blue (`#2563eb`) | Secondary action that lives next to a Primary, or a non-destructive sibling action. |
| **Alert** | orange (`#d97706`) | white | orange (`#d97706`) | High-attention but non-destructive action that changes session lifecycle state in a meaningful way (e.g. "Revert to draft"). Sits between Primary and Danger. |
| **Alert Outline** | white | orange (`#d97706`) | orange (`#d97706`) | Cautionary entry point that opens an Alert action; or an inline acknowledgement / dismiss control with a warning tone. |
| **Danger** | red (`#b91c1c`) | white | red (`#b91c1c`) | Destructive confirm action — final step that actually deletes / wipes data. |
| **Danger Outline** | white | red (`#b91c1c`) | red (`#b91c1c`) | Destructive entry point that opens a confirmation step (e.g. a "Delete…" link that reveals the real Danger button). |

#### Where each style currently lives in CSS

The styles are realized through the `.btn` family in
`app/web/templates/base.html`:

- **Primary** — `.btn` (default, no modifier).
- **Primary Outline** — `.btn.secondary`.
- **Alert** — `.btn.alert-solid`.
- **Alert Outline** — `.btn.alert`.
- **Danger** — `.btn.danger-solid`. (The danger-zone confirm
  buttons in `session_detail.html` still use inline-style
  overrides on `.btn` for the same red fill — candidate to be
  migrated to `.btn.danger-solid` next time those forms are
  touched.)
- **Danger Outline** — `.btn.danger`.

#### CTA variant

`.btn-cta` is a layout-and-prominence variant of **Primary** used
for the four cards-page-level Run Session buttons and for the
Session Setup row buttons. It uses the same blue fill and white
text as Primary, but renders as a centered flex container so
multi-line labels stay vertically aligned in equal-height rows.
It is not a fifth style — it's "Primary, large and centered".

Buttons should not stack a `.btn-cta` modifier with `.danger`;
if a CTA is destructive, treat that as a new red-fill CTA variant
and add it explicitly to this taxonomy.

### Inline error / warning banners

Operator-page mutating routes (Save / Add / Delete) commonly
reject a payload with a redirect-back-with-banner pattern: the
route 303s to the GET page with a query-string flag, and the GET
template renders an inline banner card describing what went
wrong.

**Cancel button.** Every such banner — both red error banners
("Could not save…", "Could not delete…") and amber confirmation
banners ("Cascade preview…") — must carry a **Cancel button**
(`.btn.alert`) right-aligned at the bottom of the card. The
Cancel button links back to the page **without** the
query-string flag, so the operator has a one-click way to
dismiss the banner and return to the table state. For
confirmation-style banners (e.g. cascade-preview before a
destructive action), Cancel sits next to the confirm button
(usually `.btn.danger-solid`). For pure error banners (no
confirm path — the operator must fix the underlying issue),
Cancel is the only button.

**Auto-scroll on display.** Every banner card carries the
`banner-scroll-target` class plus a unique anchor id (e.g.
`id="rf-save-error-banner"`). A small page-wide script in
`base.html` scrolls the first `.banner-scroll-target` on the
page smoothly into view on `DOMContentLoaded`, overriding any
natural URL fragment-jump that would otherwise scroll past the
banner. Without this the operator can land on a long page with
the banner offscreen — common when the redirect URL fragment
preserves the source row's anchor for the Cancel-return path.

**Cancel-return anchor.** The Cancel button's `href` includes a
fragment pointing back at the **source row** (the table row or
card the operator was working on when the banner fired), e.g.
`#instrument-{iid}` or `#rtd-row-{id}`. When the operator clicks
Cancel, the browser navigates to a clean URL (no banner flag)
and the natural fragment-jump returns them to where they were
before the banner pulled them up. The auto-scroll script doesn't
fire on the dismissed page because no `banner-scroll-target`
exists there.

### Typography

- Root font size is set on `html` as a percentage so all
  `em` / `rem` measurements scale from one knob (currently `100%`,
  i.e. browser default ~16px). Tune via that single rule rather
  than hardcoding pixel values on individual elements.

### Layout

All layout primitives live as classes in
`app/web/templates/base.html`. Pages whose body splits into two
parallel groupings use the `.page-grid` two-column pattern
(documented in detail in `spec/operator_map.md` "Page layout —
two-column option"). Pages whose body is a single linear flow
keep the default single-column layout — no wrapper grid needed.

#### Primitives reference

| Class | Purpose |
|---|---|
| `.page-grid` | Two-column desktop grid with `align-items: stretch` for equal-height cards. Collapses to one column ≤800px. |
| `.bottom-grid` | Two-column grid with `align-items: start` for natural-height pairs (bottom row of cards, or any side-by-side that shouldn't stretch). |
| `.card-tl` / `.card-r` / `.card-bl` / `.card-l` / `.card-tr` / `.card-br` | Placement classes inside `.page-grid` for L-shape layouts (e.g. session detail's Session Details / Session Setup / Run Session). |
| `.bottom-left` | Vertical flex stack inside the left column of a `.bottom-grid`. |
| `.setup-nav` | Equal-width 140px nav buttons row, right-aligned, wraps on narrow viewports. The 6-button setup nav at the top of every session-scoped operator page. |
| `.setup-grid` | 4-column grid for setup-row Manage CTAs + content, used in the Session Setup card. |
| `.btn-row` | Equal-flex row of buttons (each child gets `flex: 1`). Used for the 4-up Run Session card and similar. |
| `.btn-pair` | Inline button pair (e.g. Cancel + Save). |
| `.btn-cta` / `.btn-cta.disabled` | Layout-and-prominence variant of Primary (centered flex container, multi-line labels). Used on Session Setup / Run Session cards. See "CTA variant" above. |
| `.fill-col` | Flex column where the last child grows (e.g. textarea fills card height). |
| `.col-shrink` | `width: 1%; white-space: nowrap` — makes table action cells hug the right edge. |
| `.card-half` | `max-width: calc(50% - 10px)` for cards that should never exceed half their container. |
| `.session-meta-row` / `.session-status-row` | Inline meta rows on Session Details (deadline / created-by; status pill + Edit). |
| `.field-builder` (+ `.field-builder.locked`) | Wrapper for the Display + Response Fields side-by-side cards on a per-instrument card. `.locked` disables all inputs and hides edit/add/delete affordances. |
| `.display-edit` | `<details>` shell for inline label edit forms (tick/cross pattern). CSS hides the closed-state summary when open. |
| `.table-scroll` | Wrapper that adds `overflow-x: auto` so wide tables scroll horizontally instead of breaking layout. |
| `.page-subtitle` | Small muted subtitle rendered just below an H1 (e.g. session code under session name on session detail). |

Mobile (≤800px) collapses every grid to a single column and
stacks cards in DOM order; `.card-half`'s max-width is dropped
in the same breakpoint.
