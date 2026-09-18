# UI elements catalogue

The operator surface's element catalogue: the visual primitives the app is
built from, the class each one carries, and the constraints a future
change has to respect. Values live as tokens in
`app/web/templates/base.html`'s inline stylesheet; this document is the
contract they implement.

Every page template sets its `body_class` block to `ui-v2` (reviewer
templates to `ui-v2 reviewer`), so the `body.ui-v2`-scoped rules are the
treatment; the unprefixed rules earlier in the sheet apply only where that
block does not override them.

> **Reference implementation.** `app/web/templates/operator/session_reviewers.html`
> + the `body.ui-v2`-scoped block in `app/web/templates/base.html`
> together show every primitive in this catalogue in working form.
> When porting a page, mirror that template's class usage.

Cross-references:

- **`spec/visual_style_general.md`** — authoritative design system (palette,
  type scale, spacing, component shapes). It names colour **roles**
  (`accent-blue`, `text-primary` and the rest) rather than the app's
  own token identifiers, deliberately, because it is portable; this
  catalogue names this app's tokens, which `spec/color_tokens.md`
  catalogues.
- **`spec/color_tokens.md`** — the two-tier token catalogue. Every token
  named below resolves there.
- **`spec/domain_assumptions.md`** — load-bearing domain assumptions. The
  banner-behaviour contract lives here instead, at §5a.
- **`spec/operator_ui_concept.md`** — page-level chrome and per-page
  layout contracts that consume these primitives.
- **`spec/reviewer-surface.md`** — reviewer-surface page contracts.

When this doc and `visual_style_general.md` disagree on a
visual treatment, `visual_style_general.md` wins; this doc is
the implementation catalogue mapping those treatments to CSS
classes.

---

## Part 1 — Element catalogue

### 1. Page chrome (top of every page)

> **App identity bar** — a `.chrome` flex row: `.chrome-left` carries the
> "Review Robin Web App (version …)" identity plus the theme toggle in a
> `.chrome-identity-row`, with the breadcrumb below; `.chrome-user` on the
> right carries the signed-in line, the `.chrome-link` detours (Settings /
> Admin / Guide / About) and Sign out. Bottom border `--border-subtle`,
> identity text and the signed-in line `--text-subtle`.
> **Sign out is a bespoke chrome control, not a `.btn` role.** It ships
> its own rule — `--border-default` (not `--btn-secondary-border`),
> `--text-body`, `--surface-muted` on hover — so it reads as
> Secondary-ish at chrome scale without joining the button vocabulary.
> §6's roles govern page-scale buttons; this one is deliberately outside
> them. Chrome scale, not page
> scale — the
> chrome's one control must not read as loudly as the page's default
> button.

> **Breadcrumb** — `_partials/breadcrumb.html`, rendered inside
> `.chrome-left`. `.breadcrumb` links in `--text-link`, the current
> segment a `span[aria-current="page"]` in `--text-body` semibold, and a
> `.breadcrumb-sep` " / " in `--text-subtle`. No home icon and no other
> ornamentation, per `visual_style_general.md` "Breadcrumb".
> Operator pages build the trail through `app/web/breadcrumbs.py`
> (`operator_root`, `operator_session_child`) rather than hand-rolling the
> markup, so the segment vocabulary stays in one place.

> **Navigation busy indicator** — a 3px indeterminate bar fixed to the
> top of the viewport, plus a visually-hidden `role="status"` region.
> Arms ~200 ms after a same-origin link click or form submit and clears
> when the next page paints, so a fast navigation never flashes it and
> a slow one stops looking like a hang. Indeterminate by construction:
> a page is one blocking response, so there is no progress to report.
> Carried by `.rrw-busy` / `.rrw-busy-fill` / `body.rrw-navigating` /
> `.rrw-navigating [aria-busy="true"]` in `base.html`, driven by a
> delegated listener in the same file. Inherited by every template
> that extends `base.html`; there is no per-page markup and no
> opt-in.
> *Excluded from arming:* modified and middle clicks, `target`
> anything but `_self`, bare `#` fragments (and same-page links whose
> href differs from the current URL only in its fragment),
> `javascript:` hrefs, links marked `aria-disabled`, cross-origin
> links, and links carrying `download` — an attachment never replaces
> the page, so no load event would arrive to clear the bar. Every
> anchor in the app whose response is an attachment carries
> `download`; a unit test scans the templates and fails on one that
> does not.
> *Busy control:* the clicked link or submit button gets
> `aria-busy="true"`, never `disabled` — a disabled control is not
> serialized, so its `name`/`value` would vanish from the payload.
> *Reduced motion:* `prefers-reduced-motion` renders a static bar
> rather than a travelling one.
> *JS off:* nothing renders and nothing breaks.

### 2. Session-scoped chrome

> **`.session-nav-card`** — the two-row navigation card with the
> double-height Home anchor on the left and Setup / Operations tab
> rows on the right. Specified in detail in
> `spec/visual_style_rrw.md` "Operator session chrome > Navigation chrome (two-row layout)".
> Carried by `.session-nav-card`, `.session-nav-grid`,
> `.session-home-anchor`, `.row-label`, `.tab-strip-setup`,
> `.tab-strip-ops`, `.nav-tab`, `.status-row` rules in `base.html`;
> rendered by `operator/partials/session_top_nav.html` and included
> by every session-scoped operator template.
> **Each row wears its group's own tint and its own marker**, so the
> Setup / Operations split is legible before any label is read: the
> strips fill with `--nav-strip-setup-bg` / `--nav-strip-ops-bg`, and the
> active tab's `::after` underline takes `--tab-marker-color`, which the
> grid defaults to `--nav-marker-setup` and the Operations row overrides
> to `--nav-marker-ops`. The Home anchor fills with `--nav-home-bg` and
> marks itself with `--nav-home-marker`. Row labels and the right-pointing
> triangle after them — drawn in CSS from borders rather than set as a
> glyph, so its height matches the surrounding cap-height — sit at
> `--text-subtle` and darken to `--text-body` when their
> row is active **or** when the cursor is over any tab in that row's strip
> (a `:has()` selector, so hovering previews the row's emphasis without
> transferring active state).

> **Hover = selected.** Hovering any session-nav target — a Setup or
> Operations tab, or the Home anchor — paints it in that target's own
> **selected** colours: `--nav-tab-active-bg` / `--nav-tab-active-fg` for
> a tab, and the anchor's selected background for Home.
> **A hover value must be a token, never a literal.** A literal
> near-white (the shape this replaced) cannot follow the theme: it reads
> as a tint over the light strips and a pale block over the dark ones.
> **The active underline is not part of it.** The `::after` marker
> stays on `.active` alone — painted under the cursor it would leave
> the operator unable to tell which page they are on while hovering.
> **Disabled tabs never hover, and the guard has to be in the selector.**
> The rules carry `:not(.disabled):not([aria-disabled="true"])` rather
> than relying on a later override: `body.ui-v2 .nav-tab:hover` is
> specificity (0,3,1) against `.nav-tab.disabled:hover`'s (0,3,0), so an
> override loses on specificity wherever it sits.
> Pinned by `tests/unit/test_session_nav_hover.py`.

> **Status strip (`.status-row`)** — horizontal compact strip of
> "Lifecycle · Reviewers · Reviewees · Assignments · Instruments ·
> Email Template" sitting inside the nav card.
> `.status-row`, rendered by
> `operator/partials/session_setup_status_row.html` as one `<p>` of
> "key: badge · key: badge" pairs separated by middle dots — lifecycle
> badge first, then a count pill or an empty pill per slot, per
> `visual_style_rrw.md` "Operator session chrome > Status strip", which
> owns the slot order. **It sits inside the nav card**, not between the
> chrome and the page body, so a `--border-subtle` top border is what
> separates it from the tab rows above.

### 3. Page headings

> **H1 (page title)** — `--fs-h1` (1.5rem) at weight 600, line-height
> 1.3, with `--space-4` below. An optional `.page-subtitle` line sits
> under it at `--fs-small` in `--text-subtle`, pulled up 8px so it reads
> as part of the title block rather than as the first paragraph.

> **H2 (card / section title)** — `--fs-h2` (1.125rem) at weight 600,
> **one rule for cards and sections alike**, so a heading does not change
> size by moving into or out of a card. `--space-3` below, zeroed on the
> top when it is a card's first child. `h3` takes `--fs-body` at the same
> weight; on `/guide` it also takes a `--space-6` top margin (see §10).

### 4. Cards

> **`.card` (default)** — `border: 2px solid var(--border-default)`,
> `border-radius: var(--radius-card)` (8px), `padding: var(--space-4)`,
> filled with `--surface-page`.
> **2px, not 1px**: at 1px the card edge is visually swallowed by the
> table grid lines and form borders sitting next to it.
> **Inside `.page-grid` and `.bottom-grid`, no `margin-bottom`**: those
> wrappers zero it and the card's vertical spacing comes from their flex
> or grid `gap`, because a margin on the card compounded with
> `.bottom-grid`'s own margin and the `align-items: start` offset and
> doubled the gap on the Setup pages. **A bare `.card` outside such a
> wrapper still carries the base `margin-bottom`** and spaces itself —
> which is what stacks consecutive top-level cards on the sys-admin
> pages.

> **`.card.lock` (warning-framed, lifecycle-locked)** — `.card`'s shape
> with `--card-warning-bg` fill and `--card-warning-border` border (the
> warning brown). The recovery action inside uses the outline-amber
> `.btn.alert` role (§6), per `visual_style_general.md` P7. Never build an
> amber card from inline styles: the framing is shared with
> `.card.danger-zone` and has to move in one place.

> **`.card.danger-zone` (warning-framed, destructive grouping)** —
> `.card`'s shape over the **same amber surface as `.card.lock`**:
> `--card-warning-bg` fill and `--card-warning-border` border, plus an H2
> in `--card-warning-fg`. Both warning surfaces share one visual language,
> fill included, so the operator's eye recognises the category whether the
> card says "you can't change this right now" or "here's where you delete
> data". The Destructive button inside keeps its own outline red — the
> amber frames the surface, the red marks the action that deletes data.
>
> **Delete-confirm standard.** Every destructive
> submit is **disabled-until-checked**: the button ships
> `disabled aria-disabled="true"` and a paired confirmation checkbox
> enables it. The checkbox is also `required` — belt-and-suspenders
> against a JS-off submit — **wherever the gate owns its form**: the
> `Danger Zone`'s `delete-all` and the Upload card's `replace-roster`,
> on all four roster pages.
>
> **It is not `required` where the gate shares a form with
> non-destructive submits**, and that is forced rather than an
> oversight. The row expander's bulk-delete confirm is attached by
> `form="<noun>-bulk-form"`, and so are `Inactivate` and `Activate` —
> so `required` would refuse those two submits until an operator ticked
> a delete confirmation, which is worse than the thing it guards
> against. The disabled-until-checked pairing still holds, and the
> route re-checks `confirm == "true"` server-side, which is the gate
> that actually binds. *(Adjudicated at 19P.3 rung 5b; the rule read
> as unconditional and was false of four pages.)* The app-wide `data-delete-confirm="{key}"`
> ↔ `data-delete-btn="{key}"` pairing (base.html) drives single-form
> pages; a **list** of destructive rows (the sessions-lobby /
> archived expanders) uses its own per-node script for the same
> disabled-until-checked behaviour, because the app-wide `querySelector`
> can't address N buttons. The confirm-checkbox label uses the
> affirmative **"Yes, delete …"** voice everywhere (full sentence in a
> danger-zone card; compact "Yes, delete" in the expander toolbar) —
> never a permissive "Allow delete".
>
> **`.confirm-label` is `display: flex`, so the sentence must live in
> ONE child element.** A bare text run inside a flex container becomes
> its own anonymous flex item and takes the container's `gap` with it,
> so a confirm that interleaves pills with prose — *"Yes, replace the
> existing `12 reviewers`."* — renders its closing text detached from
> the pill before it. Measured in Chromium at 19P.1: **12px** off the
> pill unwrapped, **4px** once the sentence was wrapped in a single
> `<span>`, that 4px being the pill primitive's own margin and what
> every pill-in-a-sentence in the app shows. The `gap` is for the
> checkbox, not for the words. Four pages reach this class and nothing
> stated the constraint, so the defect arrived by moving a label onto
> it — correctly, a class over an inline style — and was invisible in
> the markup. **The better fix is the class's, not each caller's**: drop
> `gap` in favour of a margin on the checkbox, and the wrappers stop
> being load-bearing. Recorded rather than done, because it changes a
> primitive four pages render and 19P.1 was not the segment to do it in.

> **`.card.placeholder` (canonical placeholder treatment)** — `.card`'s
> shape with a `--surface-muted` fill, `--text-subtle` H2 and body, and
> `not-allowed` cursor on the card and everything in it. For cards whose
> underlying feature is not yet implemented.
> **Every instance reads identically.** Per-card state distinctions belong
> in body copy, never in an opacity flip: two placeholders on one page
> that differ visually invite the reader to look for a difference in
> meaning that is not there.
> There is **no macro**: one existed, went uncalled, and was retired.
> A placeholder card writes the canonical heading + body + disabled
> action button directly, and the class above is what keeps every
> instance identical.

> **`.card.next-action` (Session Home's Workflow card)** —
> `.card`'s shape with a `--card-active-border` border and
> `display: flex; flex-direction: column`. The border signals this is the
> page's single most important card and ties it to the Primary button it
> carries. **No fixed `min-height`** — the card grows to fit its content,
> so a short early state is not padded out to match a tall one.
> **The H2 is the constant string "Workflow"**; the per-state action verb
> belongs in the primary button's label, never in the heading.
> The card's parts are `.next-action-body` (flex-grows),
> `.next-action-buttons`, and `.next-action-signals` /
> `.next-action-signal` (the tone-coded inline captions). Which of them
> each lifecycle state renders is `spec/session_home.md`'s contract, not
> this catalogue's.
> **A POST form declares its id in the body and its submit button
> declares `form="next-action-{name}-form"`**, so the form definition
> stays next to the checkbox it gates while the submit sits in the bottom
> row.

> **Reviewer help cards (`.rs-help-card` family)** — tinted slabs
> listing per-instrument response-field help text, in `base.html`.
> **Always a `.rs-help-grid` row of half-width `.rs-help-card` items,
> whatever the count.** There is no full-width variant and adding one
> strands the lone card: the per-instrument intro is a half-width card
> grid, so a sole card that expanded would land in column 2 beside the
> heading card. `test_reviewer_response_flow.py` asserts that no
> `rs-help-card-solo` renders.
>
> **Its own token family, not borrowed ones** — `--card-help-bg` /
> `-border` / `-fg` (`#e5e7eb` / `#9ca3af` / `#111827` light,
> `#232c3b` / `#3a465c` / `#e6eaf2` dark). The fill must never point at a
> border token: pointed at `--border-default` it reads acceptably only
> while that token is very light, and `--border-default` carries every
> bordered surface's boundary and so has to be free to darken. Own tokens
> are what stop the next border change reaching this card, and are the
> same reason the family has its own `-fg` rather than inheriting
> `--text-body`.
>
> **A slab with a defined edge**: `--card-help-border` is darker than the
> fill — **2.54:1** against the page in light, **1.95:1** in dark. Enough
> for a card standing alone in a column to read as bounded; still short of
> the 3:1 WCAG 1.4.11 asks of a UI-component boundary, so it is decoration
> rather than a control edge, and does not have to reach 3:1. The two
> themes deliberately do not match by the numbers — each ramp has one
> shared step available at that end.
>
> **One token set, two callers**: `.rs-help-card` and `.page-guidance`
> (the Setup pages' guidance disclosure). That is why the theme
> customizer's facet is named `Help card` rather than `Instrument help
> card` — a facet named after one caller would misdescribe what editing it
> changes. See `spec/color_tokens.md` "Card accents".

### 5. Banners

> **Inline error / warning banner** — appears at the top of a page
> after a redirect-back-with-banner from a mutating route. Carries
> `.banner-scroll-target` so the page-wide auto-scroll script jumps
> to it on load.
> Four variants, matched to the four semantic accents:
> - `.banner.banner-info` (`--status-info-bg` / `--status-info-border`)
>   — preview-mode notice on reviewer surface.
> - `.banner.banner-success` (`--status-success-*`) — submission
>   confirmation on reviewer surface.
> - `.banner.banner-warning` (`--status-warning-*`) — lifecycle-locked
>   notices, missing-required acknowledgements, cascade
>   confirmations.
> - `.banner.banner-error` (`--status-error-*`) — Could-not-save /
>   Could-not-delete inline errors.
> Each variant sets **only** `background` and `border-color`; padding,
> radius, border-width and margin come from the single `.banner` base,
> and body text is the page's `--text-body`. Cancel button per the
> "Banner behaviour conventions" sub-section below.
> Two sub-elements sit inside the family: **`.banner-headline`**, the
> bolded first line, and **`.banner-actions`**, the right-aligned
> control row that carries the Cancel button §5a requires.
>
> **The family is not universal, and `.banner-scroll-target` is not a
> claim of membership.** Other surfaces announce themselves with a plain
> `.card` plus `role="alert"`, or with a paragraph styled by its own
> parent card's rule — carrying the scroll hook and the ARIA role but no
> error accent. Those are outside this family and outside this catalogue,
> so a page audit should expect them alongside the four variants rather
> than reading a missing accent as a defect.

#### 5a. Banner behaviour conventions

Operator-page mutating routes (Save / Add / Delete) commonly
reject a payload with a redirect-back-with-banner pattern: the
route 303s to the GET page with a query-string flag, and the
GET template renders an inline banner card describing what
went wrong. Three conventions govern every banner the surface
renders.

**Cancel button.** Every such banner — both red error banners
("Could not save…", "Could not delete…") and amber confirmation
banners ("Cascade preview…") — must carry a **Cancel button**
(`.btn.alert`) right-aligned at the bottom of the card. The
Cancel button links back to the page **without** the
query-string flag, so the operator has a one-click way to
dismiss the banner and return to the table state. For
confirmation-style banners (e.g. cascade-preview before a
destructive action), Cancel sits next to the confirm button —
`.btn.danger-solid` (filled amber) for a recoverable proceed
(archive / regenerate-&-prepare / acknowledge-&-activate),
`.btn.destructive` (outline red) for an irreversible delete. For
pure error banners (no
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

**Cancel-return anchor.** The Cancel button's `href` includes
a fragment pointing back at the **source row** (the table row
or card the operator was working on when the banner fired),
e.g. `#instrument-{id}`. When the operator
clicks Cancel, the browser navigates to a clean URL (no banner
flag) and the natural fragment-jump returns them to where they
were before the banner pulled them up. The auto-scroll script
doesn't fire on the dismissed page because no
`banner-scroll-target` exists there.

### 6. Buttons

Five canonical roles — **Primary**, **Secondary**, **Destructive**
(outline red), **Alert** (filled amber) and **Outline-amber** (lock-card
recovery). Every `.btn` shares one shape: `var(--space-2) var(--space-4)`
padding, `var(--radius-button)` radius, `--fs-small` at weight 500, a 1px
border, single-line label. **Roles differ by token, not by shape**, so a
role change is a colour change and nothing else. If a button does not fit
one of the five, ask before inventing a sixth.

| Class | Role | Notes |
|---|---|---|
| `.btn` (no modifier) | **Primary** | `--btn-primary-bg` fill, `--btn-primary-fg` label, `--btn-primary-border` border. Reserved for the page's *single* main affirmative action — at most one per page region. "Submit this form" doesn't qualify; routine submits use Secondary. |
| `.btn.secondary` | **Secondary** | `--btn-secondary-bg` (white) with a `--btn-secondary-fg` label and a `--btn-secondary-border` outline — a medium grey, a shade lighter than the label. The default button. Used for routine submits (Upload, Save), Cancel, View detail, etc. |
| `.btn.alert` | **Outline-amber (recovery in lock card)** | `--btn-amber-bg` (white) with `--btn-amber-border` + `--btn-amber-fg` — the same warning brown that frames the lock card. Per `visual_style_general.md` P7, recovery actions inside a lock card adopt the card's color family. Used e.g. for "Revert to draft" inside a `.card.lock`. |
| `.btn.alert-solid` | **Primary** | Resolves to the Primary tokens; there is no separate orange solid. The action's gravity is communicated by the surrounding context (lock card, confirm-step), not the button color. |
| `.btn.destructive` | **Destructive (outline red)** | `--btn-destructive-bg` (white) with `--btn-destructive-border` + `--btn-destructive-fg`. Irreversible row / collection **deletes** — Delete session, delete-all rosters, bulk-delete, and the delete confirm step inside `.card.danger-zone`. The role also appears **outside** a danger zone: every roster Setup page carries a `Delete` for the checkbox-selected rows in its **row expander** — Reviewers since 19P.1, Observers 19P.2, Reviewees and Relationships 19P.3. Nothing sits between `Add new` and `Search` in the toolbar; the one-row constraint that once shortened `Add` went with `Delete`. The expander is not red and does not become so — the button's own role carries the weight, and the destructive act is gated by the confirmation checkbox beside it (`spec/setup_pages.md` § *Roster controls and their route contracts*). |
| `.btn.danger-solid` | **Alert (filled amber)** | Filled `--btn-alert-bg` with a `--btn-alert-fg` label; lightens to `--btn-alert-bg-hover`. Serious-but-**recoverable** actions — purge-and-archive, Archive session, and the Acknowledge-and-activate confirm. Amber = caution, and the role exists to stay distinct from `.btn.destructive` (red, deletes data) and `.btn.alert` (outline amber, recovery inside a lock card): three amber-or-red treatments that mean three different things, so none may borrow another's fill. |
| `.btn.danger` | **Destructive** (entry point) or **Secondary** | Where `.danger` is the entry into a confirmation, prefer Secondary; the destructive treatment lands on the confirm step. |
| `.btn-cta` | **Primary (large / centered variant)** | Layout variant only — flex centering and multi-line labels; the fill is Primary's. Reach for it only where a page genuinely has one affordance and nothing else competing with it; **never beside an existing Primary pointing at the same route**, which is two buttons for one action (`spec/sessions_overview.md`). |
| `.btn-cta.disabled` | **Primary (disabled)** | Opacity 0.5, `pointer-events: none`. Same disabled rule as the regular Primary. |
| `.btn-icon` | **Icon button** | Borderless inline action (move-up / move-down / delete-row), `--text-subtle` by default with `.danger` / `.action` modifiers taking `--icon-btn-danger-fg` / `--icon-btn-action-fg`. **As an anchor** (the row pager's steps): the live cell is `<a class="btn-icon …">` and the unavailable one a `<span class="btn-icon … is-inactive" aria-disabled="true">` — a `<span>` rather than an href-less `<a>`, following `.nav-tab disabled`, because an anchor without an href is focusable-but-inert in some browsers and not others. Inactive is `opacity: 0.4` + `cursor: not-allowed` and takes **no** accent fill, the reserved shade being for things that act. An anchor `.btn-icon` also needs `text-decoration: none` on its own rule — the page's `a` rule underlines it otherwise, and an underlined `»` reads as a typo. **A specialising rule must name `.btn-icon` in its own selector.** `body.ui-v2 .btn-icon` is (0,2,1) and sits late in `base.html`, so `body.ui-v2 .table-pager-step` ties it and loses on source order — silently, if its declarations happen to match what `.btn-icon` already sets. Write `body.ui-v2 .btn-icon.table-pager-step`, which is (0,3,1) and wins. `tests/integration/test_cascade_ties.py` resolves the cascade in Python — rendered class sets against parsed rules — and fails when a canonical class's declaration is dead because an equal-specificity rule sets the same property later. A variant that comes *later* and wins (`.table-pager-cluster-bottom` over `.table-pager-cluster`) is the idiom and is not reported; a specialisation that comes *earlier* and loses is. The check covers simple class selectors on one element only: combinator rules, `@media` blocks, inline `style=` and shorthand-versus-longhand are outside it, each able to make it silent but none able to make it report a tie that is not there. |
| `.btn-reset` | **Inline text-button** (revert-this-field) | Single-line link-styled button used to revert a single text field inside an editor without cancelling and exiting the whole editor. Reference example: per-field `Reset {{ field }} to default` on the Email Template page (`session_setupinvite.html`). Reads as a small inline link (`--text-link`, underline on hover); posts a form. The pattern can apply to any editor with per-field overrides — adopt this class instead of inline-styled buttons. |
| `.back-link` | **Return-to-where-you-came-from** | Top-of-body inline link rendered as `<a class="back-link" href="{{ return_to_url }}">← Back to {{ return_to_label }}</a>`. The canonical "navigate back" affordance for chrome-detour pages and session-level child pages. Used by Operator Settings (`/operator/settings`), About (`/about`), and any page that should return the operator to wherever they came from regardless of the page's working state. Pages that need a "Cancel uncommitted edits" affordance render an inline Cancel button alongside the working-state Save (the back-link still navigates regardless). The `?return_to=<path>` query-param round-trip surfaces as `return_to_url` / `return_to_label` view-shape variables. |
| `.nav-tab` (chrome class, reused for page-internal) | **Nav button** (page-internal view switcher) | Page-internal tab-like navigation between sibling views inside a single operator page — *not* the chrome. Reference examples: Email Template's `Invitation` / `Reminder` / `Responses received` row (`session_setupinvite.html`); the email-tab strip on the Manage Invitations per-reviewer drill-in (`partials/_email_preview_region.html`). Reuses the chrome's `.nav-tab` styling so the visual vocabulary stays consistent: active view renders `<span class="nav-tab active" aria-current="page">` (non-anchor, current location), sibling views render `<a class="nav-tab">` anchors, "coming soon" reserved tabs render `<span class="nav-tab disabled" aria-disabled="true">`. Wrap in `<div class="tab-strip tab-strip-page">` — the `.tab-strip-page` modifier gives the row the chrome's grey tint, a thin border, and rounded corners so the active-tab white background reads against the row tint just like the chrome's Setup row. |

**Hover** (per `visual_style_general.md` P6): filled controls lighten,
outline controls gain a subtle tint in their own family. One direction
everywhere, so "you can click this" reads the same way on every control.

- *Filled* — Primary and `.alert-solid` move to `--btn-primary-bg-hover`;
  `.btn.danger-solid` to `--btn-alert-bg-hover`.
- *Outline* — Secondary to `--btn-secondary-bg-hover`, `.btn.destructive`
  to `--btn-destructive-bg-hover`, `.btn.alert` to
  `--btn-amber-bg-hover`. Border and label stay put.
- Disabled buttons never hover: `pointer-events: none`.

> **Disabled anchor-as-button** — an anchor doing button duty that has to
> render inert, such as the table toolbar's `Add new` while a row is
> being edited. **One rule covers all four forms** —
> `body.ui-v2 .btn:disabled`, `button.btn:disabled`, `a.btn.disabled` and
> `.btn[aria-disabled="true"]` — at `opacity: 0.5`, `cursor: not-allowed`,
> `pointer-events: none`. Markup carries the class **and**
> `aria-disabled="true"` (an anchor cannot take the `disabled` attribute),
> and never an inline `style` override: a role's disabled look has to move
> in one place.

> **No inline-styled buttons.** Every button takes a role from the table
> above; an inline `style` on a button is a defect, because a role that
> lives in one template's markup cannot be restyled from `base.html`. The
> role assignments that recur: a danger-zone form's submit is
> `.btn.destructive`, and a row-level delete / add inside a field builder
> is `.btn-icon.danger` / `.btn-icon.action`.

### 7. Tables

> **Row pager** — a table longer than one page carries the cluster described in §10 (`.table-pager-cluster`), above it and again below it. See there for the shape; `spec/setup_pages.md`, `spec/assignments.md` and `spec/operations_pages.md` carry the per-page behaviour.

> **Default table** — `border-collapse: collapse; width: 100%`, and
> **row-only borders**: `th, td` set `border: 0` then one
> `border-bottom: 1px solid var(--border-default)`, so a row reads as a
> row rather than as a grid of cells. Padding is
> `var(--space-3) var(--space-4)` (12px / 16px). Header cells fill with
> `--surface-muted` and carry `--fs-small` labels at weight 500 in
> `--text-subtle`; body rows take the card's fill and a
> `--surface-muted` hover tint. **No zebra striping** — the row borders
> already separate the rows, and a second separator is decoration.
> Colours come from tokens, never literals: `--border-default` carries
> every bordered surface in the app and has to be free to move for
> contrast without a hex here going stale (`spec/color_tokens.md`).

> **`.table-scroll`** — a wrapper adding `overflow-x: auto`, so a wide
> table's overflow stays inside its card instead of scrolling the page.
> Used on `instruments_index.html` and around `review_surface.html`'s
> response table. See §10 for which tables need it and which measure
> inside their card and go without.

> **`.col-shrink`** — the shrink-to-fit column idiom: `width: 1%` plus
> `white-space: nowrap`, for an action column that should hug the right
> edge. Used on `sessions_list.html`'s Actions column.

> **Reviewer-table column-width hints (`.rs-narrow`,
> `.rs-reviewee`, `.rs-textlong`)** — column-shape hints for the
> response-input table on the reviewer surface, applied from each response
> field's `data_type`. Reviewer-surface specific; they shape widths only and do
> not conflict with the general table treatment.

### 8. Forms / inputs

> **Text inputs** — one rule covers `input[type="text"]`,
> `datetime-local`, `number`, `email`, `file`, `textarea` **and**
> `select`, so a form does not change shape by changing field type:
> `width: 100%`, `padding: var(--space-2) var(--space-3)` (8px / 12px),
> `--fs-body`, `border: 1px solid var(--border-default)`,
> `border-radius: var(--radius-button)`, filled `--surface-page` with
> `--text-body`. Tokens, not literals — `--border-default` moves for
> contrast and a hex written here would go stale
> (`spec/color_tokens.md`).
> **Focus is two-layered.** `:focus` recolours the border to
> `--focus-ring` and adds a 1px `--focus-ring-halo` shadow; `:focus-visible`
> adds a 2px `--focus-ring` outline on top, so the strong ring is
> keyboard-only and a mouse click does not draw it.
> **`textarea` resizes vertically only** — a long entry grows downward; a
> horizontal drag would pull it wider than its column and break the page
> grid.
> **`input[type="number"]` hides its native spinners** — the reviewer
> surface uses numeric inputs for HTML5 `min` / `max` enforcement, not for
> spinner-driven entry.

> **`<input type="checkbox">` / `<input type="radio">`** — left native.
> No treatment is specified, deliberately: a restyled checkbox has to
> reimplement the indeterminate, focus and forced-colors states the
> platform already ships.

> **Label** — `display: block`, `--fs-small` at weight 500 in
> `--text-body`, with `margin: var(--space-3) 0 var(--space-1) 0`: 12px
> above to separate one field from the last, 4px below to bind the label
> to its own input. A nested label that sits inside a flex row with its
> own gap **must reset that top margin** or the two stack; three rules in
> `base.html` do so and say why.

> **Helper text / error text** — `.form-help` (`--fs-small` in
> `--text-subtle`) and `.form-error` (`--fs-small` in
> `--status-error-accent`), both below the input. Use these rather than a
> `<p class="muted">` or a bare `<small>`, so supporting text is one
> treatment app-wide.

> **Inline-edit pattern (`.display-edit`, `.instrument-edit`,
> field-builder `<details>` / `<summary>`)** — `<details>` shells for
> inline label edits with tick / cross affordances, defined in
> `base.html` and used on the Instruments page. `.field-builder.locked`
> suppresses the summary's pointer and hides the edit / delete / add-row
> affordances, so a locked builder reads as inert rather than as broken.

### 9. Badges / pills

The base `.pill`: `padding: 2px var(--space-2)`,
`border-radius: var(--radius-pill)` (9999px), `--fs-tiny` at weight 500,
`text-transform: uppercase`, and `border: 1px solid transparent`.
**Every pill reserves the edge's space** even when it has no edge, so
adding one to the interactive chips does not grow them by 2px and reflow
every table where a status label sits beside a toggle (see "Label or
control" below). Pills are used standalone as status indicators and
inline in copy — confirm labels wrap count phrases as pills so the eye
lands on the numbers without bolding the whole sentence.

| Class | Fill / text | Notes |
|---|---|---|
| `.pill-count`, `.pill-info` | `--status-info-bg` / `--text-body` | **One rule for both names.** The blue tint says "this is information" without implying a state. |
| `.pill-empty`, `.pill-warning` | `--status-warning-bg` / `--status-warning-fg` | **One rule for both names.** The warning brown matches the `.card.lock` / `.card.danger-zone` framing, so chips and surfaces share one warning language. |
| `.pill-success` | `--status-success-bg` / `--status-success-fg` | The `-fg` slot, like every other pill: a pill's label is text, and `-accent` is the marker slot. |
| `.pill-error` | `--status-error-bg` / `--status-error-fg` | Validation-summary error counts. |
| `.pill-super` | `--status-super-bg` / `--status-super-fg` | The super-admin tier badge — violet, so the protected top tier is not read as an ordinary blue info pill. |
| `.pill-handle` | `--surface-muted` / `--text-body` | Monospace, and the one pill that is **not** uppercased — a handle is a literal string and case is part of it. |

### Label or control

A pill states a fact; a chip offers a click. **That difference has to be
visible without a pointer.** `cursor: pointer` is the whole distinction
only while the cursor is already on the element; it says nothing on touch
and nothing in a screencap.

**Every interactive chip carries a 1px edge in the reserved accent
shade** (`--blue-strong` / `--blue-glow` — see
`spec/color_tokens.md` "Deliberate couplings"). That covers
`.tag-chip` — which is every lobby tag filter, every column toggle and
every Instruments Band 2 pill — plus the lobby's Clear and AND/OR chips.
Static pills carry no edge.

Three rules make that work:

- **The fill is untouched.** The edge is additive over whatever a
  modifier gives the chip, because a Band 1 link chip in the "not set"
  state is `pill-empty tag-chip` and that amber is a *status*. Amber says
  not set, the edge says you can fix it, and both are true at once. A
  blanket `background: transparent` reads as the tidier rule and trades
  one signal away for the other.
- **Every `.pill` reserves the space.** The base rule carries
  `border: 1px solid transparent` and the edge comes from an inset
  shadow rather than a wider `border-width`, so a chip is exactly as tall
  as the status label beside it and adding an edge reflows nothing.
- **`.tag-chip.is-disabled` cancels the edge.** It sets
  `cursor: default` and is the one inert chip in the vocabulary; a chip
  that says it cannot be clicked must not also say it can.

`.severity-chip` on Validate is the shape this generalises: an outlined
pill, with `.active` taking the shade on its border and text.

`.is-selected` is unchanged — a solid `--selected-bg` fill, which is how
a chip says its filter is on, and it appears only on controls.
`tests/integration/test_chip_edge.py` pins the treatment;
`tests/unit/test_reserved_shade.py` keeps the shade off anything static.

> **Lifecycle badges** — one `.pill-lifecycle-*` set covers all five
> states, each on its own token pair so a state's colour can move without
> touching the status vocabulary:
> - `draft` → `--lifecycle-draft-bg` / `-fg` (warning amber — the same
>   "needs work" treatment as `.pill-empty`, because a draft session is
>   not ready for action)
> - `validated` → `--lifecycle-validated-bg` / `-fg` (blue)
> - `ready` → `--lifecycle-ready-bg` / `-fg` (green)
> - `expired` → `--lifecycle-expired-bg` / `-fg` (red — the same
>   treatment as the reviewer dashboard's "closed" pill, so the
>   post-window state reads consistently across surfaces)
> - `archived` → `--lifecycle-archived-bg` with `--text-body`
> **The lifecycle badge always renders through this set**, never through a
> generic `pill-info`. Operator-facing labels come from the display-label
> mapping in `app/services/lifecycle_display.py` (`ready` → "Activated",
> `expired` → "Closed"), never from the raw enum; see
> `spec/session_home.md` and `spec/lifecycle.md`.

> **Status-symbol indicators (✓ / ⚠ in the reviewer response table)** —
> `.status-icon-complete` and `.status-icon-incomplete`, on tokens.
> **The two are siblings, not a base and its modifiers**: markup carries
> one class alone (`class="status-icon-complete"`), never a compound, and
> there is no bare `.status-icon` base rule for a compound to inherit
> from. A change to both has to be made on both.

### 10. Layout primitives

One row per primitive. Colours and spacing come from tokens throughout.

| Class | Notes |
|---|---|
| `.page-grid` + placement classes (`.card-tl` / `-tr` / `-bl` / `-br`) | Equal-height two-column grid with explicit placement, for the L-shape layouts that need the stretch. `.bottom-grid` is preferred for a new pairing (see below). |
| `.bottom-grid` + `.bottom-left` | Two-column grid at `align-items: start`, so each side keeps its natural height instead of stretching to match the taller column. `.bottom-left` is the flex column for stacking several cards on one side. |
| `.btn-row` (equal-flex) | A row of buttons sharing the width equally. |
| `.card-action-row` | A right-flushed row for a card's own action, `--space-3` above it, as the card's **last child**. Ships in `base.html` and had one caller from 11F until 19P.6 gave it a second; named here at that point, because a primitive with two callers is a primitive. |
| `.btn-pair` (inline pair) | Two buttons side by side at their natural widths. |
| `.setup-grid` (4-col grid for the Session Setup card) | |
| `.fill-col` (flex column whose last child grows) | |
| `.card-half` (`max-width: calc(50% - 10px)`) | |
| `.session-meta-row`, `.session-status-row` | |
| `.field-builder` + `.field-builder.locked` | The Display Fields / Response Fields builder, and its inert form (§8). |
| `.subcard-row` (+ `.stepped`, `.subcard-arrow`) | Equal-width tile row inside a card. Detailed below. |
| `.guide-figure` (+ `.guide-figure-narrow`) | The `/guide` screencap figure. Detailed below. |
| `.table-scroll` (`overflow-x: auto`) | A wide table's overflow stays inside its card instead of scrolling the page. For a table that is wider than its card by construction — the Operations preview tables, whose hidden columns still occupy width; a roster that measures inside its card goes without |
| `.col-divider` (`border-top: 1px solid var(--border-default)`) | A horizontal rule **inside** a column, marking that what follows shares the column for space rather than belonging to what precedes it. Takes the same `--border-default` as the vertical rules between columns, so the two read as one system — that match is the point, and a divider drawn from another token would say the wrong thing. Today: the self-review exclusion checkbox under Link 3 of the Instrument assignment rule card, which is not a unit-of-review setting and must not read as a third Link 3 state (`spec/instruments.md` § *Self-review exclusion*). **Use it only where a reader would otherwise misattribute the control to the block above**; a rule between two things that do belong together is noise |
| `.chip-group` | One labelled group of chips inside a `.col-chip-row`, so a row carrying several groups wraps **between** them rather than stranding a label from its chips |
| `.col-chip-row.is-grouped` | The modifier a chip row takes **when its chips are in `.chip-group` boxes**: it swaps the parent's `gap` for a wider `column-gap` between the groups. A `gap` applies on both axes, so a wrapped second line arrived indented against the line above it; a column-gap is between-items-on-a-line by definition and cannot. A **modifier and not a change to `.col-chip-row`**, because the four roster rows put their label and chips directly in the row — widening the gap there would space a label from its own chips. Assignments is the only caller (19P.5 rung 1 moved its three groups into the half-width left pane, where they stopped fitting on one line) |
| `.col-chip-row` (+ `[data-col-toggles-for]`, `[data-col-toggle]`, `[data-rrw-col-toggles]`) | The column-visibility chips above a table. A chip is `role="button" tabindex="0"` and toggles `col-hidden-{slot}` on the table it names; each page maps its own slots to its own column classes, so the slot vocabulary is not fixed here. The storage key lives on the **table** (`[data-rrw-col-toggles]`) and a page may carry several chip rows against one table, grouping its slots. **Both behaviours are delegated on `document`**: a chip rendered after load works with no registration, because the handler resolves its row, table and storage key from the event target with `closest`. **A re-rendered table card must call two hooks** — `window._rrwHydrateColToggles()` to restore the operator's saved columns, and `_rrwHydrateFromCookies()` to repaint the sort badges — because delegation keeps a chip *clickable* while the server re-renders it all-visible, and neither state is in the markup |
| `.session-row-selected` | A selected row on the sessions lobby and on its archived child page. **A rail at each end, and no fill**: `--selected-bg` as a `box-shadow: inset 6px 0 0` on `td:first-child` and `inset -6px 0 0` on `td:last-child`. Inset shadows rather than borders, so selection does not change the row's height and reflow the table under the pointer; no top or bottom cap, for the same reason. **No fill.** A row fill resolves to the same primitives that back `.pill-count` and `.pill-info` from one rule, so it erases every pill the row carries; the six pale pill fills sit between relative luminance 0.810 and 0.914 against a 1.000 card, leaving no clearance above the band, and the only clearance below it is dark enough to stop reading as a highlight. **A sort drops it and re-anchors it** (19O Item 4): `_rrwApplySort` removes every `.session-expander` child of `tbody.rrw-rows` **before** it collects rows or stamps `rrwOriginalIndex`, then dispatches `rrw:sorted` once the rows have landed. **All six injecting pages that sort listen for it**, since 19O Item 6 completed the migration: `sessions_list`, `sessions_archived`, `session_reviewers`, `session_reviewees`, `session_relationships` and `session_assignments`, each rebuilding through the funnel named below. 19P.1's per-page capture-phase handler, which removed the panel before the inline sort handler ran and restored it after, is gone from all three pages that carried it — **one mechanism, not two**. `session_observers` injects a panel without a sortable table, so it needs neither half. **The removal in `_rrwApplySort` is unconditional** — it is the index half and runs on every sortable table; only the re-anchor half is per page. Removal rather than hiding, because a hidden row still occupies an index — and the index is the quieter half of the defect: a panel counted at stamping time shifts every row after it by one, so clearing the sort stops restoring the server's order. Rebuild rather than move, because the panel's content follows the selection, not the row order. A page that injects nothing has no listener and is unaffected. **The panel closes the bracket**: the injected expander row carries `.session-expander-bracketed`, whose single `colspan` cell is first and last child at once and so takes both rails in one declaration, over `--selection-panel-bg`. **Opt-in by class**, because seven templates inject panels with the same `session-expander` class names from their own scripts, which have diverged deliberately: `sessions_list.html`, `sessions_archived.html`, all four roster pages (`session_reviewers.html`, `session_observers.html`, `session_reviewees.html`, `session_relationships.html`) and `session_assignments.html` — the seventh since 19P.5 rung 2, and the first that is not a roster or lobby page. An unscoped rule would style every one of them whether or not each marks its rows. The `.session-expander*` family is therefore **no longer lobby-only** — each roster page renders both the expander and the bracketed variant, for its selection actions and for the edit row's Save / Cancel bar. **Observers' expander is two-column** (`.row-expander-body.is-split`): the cohort rule builder in the left pane, the count / confirm / actions in the right, top-aligned rather than sharing a bottom edge because the builder is the taller of the two and bottom-aligning would anchor `Save` to a button row it has no relationship with. That variant is this page's alone so far; a third caller is what would make it a primitive. **The panel is a pill-free zone**: its fill resolves to `--status-info-bg`'s primitive, so a `.pill-count` rendered inside it reopens the collision one storey down. **Two meanings since 19P.1, and the second is not selection.** On the lobby it marks a row the operator checked. On every roster Setup page it also marks the row being **edited** — a server-rendered `?edit_id=` / `?add=1` row, which is not selected at all — because the edit row wants exactly the same treatment: rails at both ends, no fill, and an expander beneath it closing the bracket. The class is the visual grammar for *"this row, and the panel under it, are one unit"*; selection was its first use, not its definition. A third meaning should be named here too rather than assumed. **Transferred page, and now transferred sense**: the lobby-only scoping below was about *pages*, and 19P.1 settled both questions in one direction — the mechanism travels, so the class is applied by any page that marks its own rows. **Still not a general primitive**: named here so it is findable, deliberately not promoted. The lobby and its archived child are one surface family, which is not evidence of generality; a speculative third, a Rosters index, is recorded in `guide/new_ux_ideas.md` with the transfer question stated rather than assumed — this was designed for one wide row in a tall table of *like* things, and a roster preview table is exactly that. **Not scanned by `tests/unit/test_reserved_shade.py`, and not exempted from it**: that guard's filter is pill / chip / `btn-icon` classes, because its subject is elements with a dual nature — a `<tr>` has none. Applied in the page's single selection funnel, which clears all rows each pass before marking the selected set. **Three names for it across the seven**, which is the diverged-deliberately point above showing through: `refreshExpander()` on the two lobby pages, `render()` on Reviewers, Reviewees, Relationships and Assignments, `renderPanel()` on Observers. The contract is the funnel, not its name — one function every selection path meets, clearing all rows each pass. **Assignments' funnel counts only visible rows**, because it is the one page with a *client-side* filter: its per-instrument `Show` checkboxes hide rows with `display: none`, and an expander anchored after a hidden row, or a `colSpan` counted before a chip toggle, both follow from treating a selectable row as a visible one |
| `.table-pager-cluster` (+ `.table-pager-cluster-bottom`, `.table-pager-step`, `.table-pager-menu`, `.table-pager-menu-panel`, `.table-pager-menu-item`, `.table-pager-anchored`) | The row pager on a roster-bearing table, rendered above the table and again below it. **Five cells**: `«` first, `‹` back, a range menu, `›` forward, `»` last — so any page is one move away whatever the roster size. Ranges (`201–400`), not page numbers. Suppressed whenever a search or status filter is active. The four steps are the `.btn-icon` role and carry no link underline; at the ends they render **in place and inactive** (`<span aria-disabled>`, never absent, or the other cells shift sideways as the operator pages) and take no accent fill — the shade `--blue-strong` / `--blue-glow` stays reserved for things that act, and an inactive step does not. The menu is a `<details>` holding every range as an anchor, **not** a `<select>`: a select navigating on `change` fires on every arrow key, so a keyboard user reaching the fifth option would navigate five times. Its summary names the current range, so one element says where you are and is the way to leave; the current entry is a `<span aria-current="page">` marked by weight and a muted fill. Every cell is an anchor — the pager needs no script to navigate; one delegated `document` listener closes the menu on an outside click or Escape. Each href carries a `#<noun>-table-card` fragment so a page turn arrives at the **table's card**: its top edge, then the column chips, then the cluster, then the new rows. The id sits on the card with a `scroll-margin-top` so the top border reads as a boundary rather than a crop; the route supplies the id, the pager never derives it. **This is one of three landing targets since 19P.1, and the only one that is a card** — see the landing-target entry below; the filter strip's controls now take this same anchor, so the contract is no longer the pager's alone. The cluster shares the chip line where it fits and wraps to its own line where it does not — the chip row's width is operator data, and a roster with no tags renders no chip row at all, so the row belongs to the cluster and the chips join it |
| **Landing targets** — `#<noun>-table-card`, `tr.row-action-target`, `#<noun>-row-editor` / `#<noun>-row-<id>` | **Three targets since 19P.1, and only the first is a card.** A page turn, and a filter or a Search / Clear, lands on the **table card** (`scroll-margin-top: var(--space-4)` — enough to keep the top border off the viewport edge so it reads as a boundary rather than a crop). A **row action** lands on the row it acted on, via `tr.row-action-target` at **`scroll-margin-top: 88px`** — deliberately larger than the cards' 16px, because a row flush against the viewport edge reads as the table's first row rather than as one row among others, and because the row's own expander renders *below* it: 88px clears one 68px row plus 16px, putting the acted-on row second from the top with a neighbour visible for context. Nothing on these pages is `position: sticky`, so there is no fixed chrome to land underneath. **Entering edit mode takes the third**: `#<noun>-row-editor` is an **add-mode-only id on the `<tr>` itself**, and `Edit` builds `#<noun>-row-<id>` from the id it already has — there is no editor card in the contract, the row is the editor. A fourth anchor, `.roster-card`, exists for the same reason as the first: a control inside the Unlock panel returns to `#roster-card` so the panel stays open, and without a `scroll-margin-top` it arrived cropped. On the three pages with a tag-label editor that is the labels save, the delete-all and a successful import; on Observers, which has none, the latter two. **A fragment that does not resolve is ignored by the browser and lands at the top of the document**, so any surface using a row fragment must also ship the fallback that catches a missing target — at most **two** cases reach it — a row the active filter excludes, and a row moved by a cookie-held sort. A delete is **not** one of them: it is handled a step earlier by the route, which has no row to land on and so sends the table card itself, and the script never fires. Two is the ceiling, not the count on every page — a page whose table is not sortable reaches only the first, as Observers does; Reviewers, Reviewees and Relationships are all sortable and reach both. `spec/setup_pages.md` § *Per-row Edit / Add / bulk actions* states the same rule for the page that implements it |
| `.filter-row` (+ `.filter-row > label`, `.filter-actions`) | **The search + status filter strip, as one unscoped base with narrowings** (19P.1 rung 2a′). It was three private per-card copies; declaring the shape once means a move carries it, which is what let Reviewers lift the strip into its table toolbar without restyling it. The base sets the row (`flex`, `--space-4` gap; status a third of the width, search two thirds, so the typeahead's `Name (email)` labels stay readable while the dropdown collapses to its short options) and the action row (`flex`, `flex-end`, wrapping). Each named scope narrows **only what genuinely differs**, and says why. One `body.ui-v2` prefix on the generic label rule is **load-bearing specificity, not scoping**: the global `body.ui-v2 label` is (0,1,2) and would otherwise beat a bare `.filter-row > label` at (0,1,1), re-blockifying the label, un-stacking it from its input, and blockifying the select with it — which is only `display: block` by virtue of being a flex item |
| `.table-card-toolbar` (+ `.is-split`, `.toolbar-pane`, `.toolbar-left`, `.toolbar-right`) | **Two bare panes at the head of a table card**, on **all seven table pages** — the four rosters (Reviewers 19P.1, Observers 19P.2, Reviewees and Relationships 19P.3) and the three Operations tables (Assignments 19P.5 rung 1, Invitations and Responses rung 3). Card geometry — the same half-and-half split and gutter `.card-columns` gives — with **no border, fill or padding of its own**, because these are regions of one card rather than two cards. That is the distinction §10 already draws against `.card-columns`, now with a name. Left pane: what the table is showing (column chips, pager cluster, count line) — **and it renders empty where a page has none of those**, as Observers does on an unpaged roster: it has one fixed tag slot so no chips exist to toggle, and the pager appears only past one page. The pane stays so the split holds; an asymmetric toolbar is the intended shape, not a gap to fill. Right pane: the filter strip that decides it. The strip moved here from a card a grid away, so the controls sit with the rows they act on. **`is-split` stays a modifier now that every carrier opts in**, which looks redundant and is not: the shared class stays `display: flex`, so the next page to open a table card with a toolbar is not silently re-laid-out by a grid it never asked for. A pager-only toolbar is the sharp case — as a grid item the cluster would right-align into the second column. **The two panes are gated differently by page family, and deliberately**: the rosters include the pager and count line unconditionally and let those partials self-guard, while the three Operations pages wrap the whole left pane in a has-rows conditional — `{% if rows %}` on Invitations and Responses, `{% if pair_sample %}` on Assignments, whose rows are generated rather than rostered. An empty pane and an absent pane render the same, so nothing turns on it visually; recorded so the next reader does not take one for a bug |

**`.bottom-grid > .grid-right` is retired** (19P.5 rung 2). It held a
lone card to the right-hand column at half width, and Assignments'
operator-actions card was its only caller; when that card went, so did
the rule and the `bottom-grid` around it. The question it answered
recurs, so it is recorded rather than dropped: a single child of a
`1fr 1fr` grid lands in column 1 and reads as a card that failed to
fill the row. **The answer is a decision, not a default**: half width
flush right for a *control*, full width for a *readout* — the
author's 2026-09-10 call, restated in this item's § *Semantics*. Where
the answer is full width, the grid goes with the rule, because a grid
with one child is not a grid and a plain card is page width with no
rule at all. That is what 19P.5 rung 3 did on Invitations and
Responses, whose survivor was a counters card: eight pills in half a
page wrap badly (`spec/operations_pages.md` § *Shared page shape*).
`base.html`'s surviving comment at the rule's old site says the same.

**Do not bring back the range strip.** `.table-pager`,
`.table-pager-bottom`, `.table-pager-link`, `.table-pager-gap` and
`.table-pager-jump` must not return: a five-wide
window of ranges with First / Last hung off the ends and `…` for each
elided gap bounds the strip's width, and so bounds its reach at two pages
per click whatever the roster size — five clicks to row 2,400 of 5,861,
fifty to the middle of 40,000. The cluster's five fixed cells reach any
page in one move instead. A rule for markup nothing renders leaves the
next reader working out whether it is dead or whether they have missed
the page that uses it, which is why none may come back.
`tests/integration/test_pager_link_style.py` pins **four** of the five —
`.table-pager-link`, `.table-pager-link.is-current`, `.table-pager-gap`
and `.table-pager-bottom`. **Bare `.table-pager` and
`.table-pager-jump` are held by this paragraph alone**, so a rule for
either would pass the suite; that is what the prohibition is for.
The names are listed here because they appear in older plans and commit
messages, and someone grepping one should find out that it is gone rather
than that the spec is silent.

**A page turn reloads the page, and that is settled rather than
pending.** Swapping the table in place — a fragment endpoint per page,
the table markup extracted to a partial, history handling — was measured
against the reload and **rejected outright, not deferred**.

The cost is not the deciding argument, and the measurements behind it are
in `guide/archive/inplace_pagination_assessment.md` — re-take them rather
than trusting them, as that document itself says. What decides it is
intent. The one case a reload is
mildly jarring is a click on the **bottom** pager strip, which sends the
viewport back up; an operator who turns a page and then stays on it is
almost always intending to read the new range from its start, so the
jump and the intent point the same way. That is a firmer reason to stop
than the cost tables are: cost argues *not yet* and invites the question
back every few segments, whereas this argues **not at all**.

Build the swap only if something else comes to need it — live-updating
rows, or a page turn that must not lose an in-progress edit — never to
fix the scroll. If it is ever built, the partial extraction lands first
on its own with no behaviour change, so the swap rung is a swap and not
a rewrite.

**`.subcard-row`.** A row of equal-width tiles laid across the inside
of an outer `.card`. Distinct from `.card-columns`, whose children are
*columns* that stack their own cards and are deliberately allowed to
differ in height: `.subcard-row`'s children are one row, and they
**stretch to match**, because parallel items at different heights read
as different weights. Count comes from `--n` (default 4); tracks are
`minmax(0, 1fr)` so a long word cannot widen its tile. Collapses to
two columns under 900px and one under 560px.

**The row styles layout only.** Its children are ordinary `.card`s and
bring their own look; the row zeroes their margins so the grid gap is
the only spacing, and clears the last child's bottom margin so the
tile's padding is the only space under it. In practice the children
are **`.card.rs-help-card`** (§4): a row of tiles inside a card is
explaining something, which is what the help-card semantics already
say. Tile headings are plain `<h3>` and need no class.

**`.stepped` + `.subcard-arrow`.** The modifier for a row whose tiles
are a **sequence** rather than parallel options: it puts a `→` between
them. Mechanically it interleaves an `auto` track after each tile to
hold the arrow, so the class and the `<span class="subcard-arrow">`
children travel together — one without the other is a bug. The last
such track is left empty (*n* tiles, *n−1* arrows) and an `auto` track
with no content is zero-width, so nothing trails off the right end.
`column-gap` drops to 0 under `.stepped` because the arrows' own side
padding *is* the gap; leaving both would double the space either side
of every arrow. Tiles keep `minmax(0, 1fr)`, so arrows narrow them
rather than widening the row.

The glyph is `→` (U+2192), which is the app's established arrow — this
introduces no new vocabulary, and a second arrow character would.
Arrows render at `--text-subtle`: the tiles are the content and the
arrow is punctuation.

**Arrows are `aria-hidden="true"` and hide below 900px.** Order is
already carried by reading order, which is where a screen reader takes
it from, and "right arrow" announced between every pair of headings is
noise. Below 900px the row wraps to two columns and a horizontal arrow
between stacked tiles points at nothing, so the arrows go and the plain
column gap comes back.

**The row introduces no tile class of its own, and must not acquire one.**
`.data-shape-card` already answers "bordered thing inside a bordered
thing", and a second answer earns a reader nothing. Reach for
`.rs-help-card` inside a `.subcard-row`; if a row ever wants tiles that
are genuinely not help cards, give them an existing card variant rather
than a new tile look.

Reference user: the sessions-lobby first-run card
(`spec/sessions_overview.md`).

**`.guide-figure` / `.guide-figure-narrow`.** The `/guide` screencaps.

These are pictures **of** this app rendered **inside** it, so a bordered
image alone reads as more page rather than as an illustration of one —
the capture's own white ground runs straight into the card's. The figure
is therefore a **mat**: a padded `--surface-muted` panel with a
`--border-subtle` edge, on which the capture sits the way a photograph is
mounted. The tint separates the two even where the capture's own edge is
white, and the inset says *this is a picture of something* before the
reader has parsed what. The capture keeps a 1px `--border-default` edge,
whose job is only to define it against the mat — thickening it fights
the mat rather than helping.

**Not a drop shadow**, the other common answer: shadows in this app are
solid offset markers and focus rings, never blurred elevation, so a soft
shadow here would read as a different design language.

**Each capture ships twice**: `x.png` and `x-dark.png`, both rendered
inside the one `<figure>`, with the theme choosing which is shown —
`img[data-theme-variant="dark"]` is hidden by default and the pair swaps
under `:root[data-theme="dark"]`.
The selector reads the **`data-theme` attribute the toggle writes**, not
`prefers-color-scheme`: this app is two-state with no OS-follow
(`spec/settings_inventory.md`), so a media query would serve a light
capture to a reader sitting in Dark. Because the no-FOUC script stamps
the attribute in `<head>` before the `<img>`s are parsed, the right
capture is up from the first frame; because it is CSS, the live toggle
flips every figure on the page with no reload and no JavaScript of its
own. Light is the copy with no hiding rule, so a page with JavaScript off
or storage blocked shows the light set — the same default the rest of the
theme system takes. Both copies carry the **same** `alt`: they are
pictures of one UI, and only one is in the accessibility tree at a time.

`fit-content` makes the mat hug its picture rather than run to the column
edge past a 600px capture, and `box-sizing: border-box` keeps the padding
inside `max-width` so a narrow column cannot overflow.

The captures arrive at **two scales** — 1× shots at ~830px and 2× shots
at ~1680px. Left to fill the prose column they would read at two
different apparent scales, so each family gets a **fixed display width**:
the base rule pins the wide family at **1200px**, `.guide-figure-narrow`
pins the narrow one at **600px**. Both are author's numbers, set from
looking at the rendered page rather than derived from the pixel
dimensions; treat them as presentation, not as a rule with a formula
behind it.

They set `width`, not `max-width` — only `width` pins an image below its
natural size — and the base `max-width: 100%` still takes over on a
narrower column, so neither number can cause a horizontal scroll. The
modifier rule must stay **after** the base one: equal specificity means
source order is what makes it win.

Which family a capture belongs to is asserted from its **actual pixel
width** in `tests/integration/test_guide_screencaps.py`, not from a
hand-kept list, so a capture retaken at the other scale fails rather
than quietly rendering wrong. The same file checks the two halves of a
pair against **each other** — same family, same `alt`, same `<figure>` —
which is the part the markup cannot state.

In-card headings on `/guide` take a `--space-6` top margin
(`body.ui-v2 .card[id^="guide-"] h3`): its cards run long enough that
their `<h3>`s are section breaks rather than labels on the paragraph
below, which is what ui-v2's global `h3` rule assumes. Scoped by the
`guide-` id prefix the cards already carry, so no other page moves.

### 11. Misc one-offs

> **`.btn-icon`** — borderless inline action (move-up, move-down,
> row-delete, row-add), `--text-subtle` by default. Two semantic
> modifiers: `.btn-icon.danger` takes `--icon-btn-danger-fg` and
> `.btn-icon.action` takes `--icon-btn-action-fg`. See the §6 row for the
> anchor form and the specificity rule a specialising variant must obey.

> **`<pre>` blocks (outbox preview)** — render as `.code-block`, the
> same content-surface family as cards. A raw `<pre>` is not a
> content surface and must not be used as one.

> **Inline `onclick` attributes** — the Instruments page's row controls
> bind their handlers inline, and those attributes are load-bearing rather
> than incidental. **The Lock and Unlock anchors pair differently, and a
> delegation sweep must preserve the asymmetry**: Lock carries
> `onclick="return newModelLockClick(event, <id>)"` over a plain
> `…/instruments#instrument-<id>` href, while Unlock carries
> `newModelUnlockClick` over a `…/instruments?editing=<id>#…` href — only
> Unlock has a no-JS fallback, because only *entering* edit mode needs a
> server round trip to fall back to. Inline attributes in a template are a
> different thing from the element-bound listeners in `base.html`'s script
> blocks; a rule about one does not govern the other.

---

## Cross-cutting rules worth restating

The rules a reader is most likely to need without having read the entry
that owns them. Each is stated in full above; none is decided here.

- **A page turn reloads.** The in-place table swap was measured and
  rejected outright rather than deferred — build it only if something
  else comes to need it, never to fix the scroll. Stated in full in §10
  beside `.table-pager-cluster`, because it governs the pager every
  roster-bearing page shares rather than any one page's spec.
- **Hover by fill** (`visual_style_general.md` P6). Filled controls
  lighten; outline controls gain a subtle tint in their role's family.
  One direction across buttons, nav anchors and tinted cells.
- **Recovery actions in coloured cards** (`visual_style_general.md` P7).
  The action picks up the card's colour family rather than reasserting
  Primary blue. Two cases: outline-amber Revert-to-draft inside
  `.card.lock`; outline-red Destructive inside `.card.danger-zone`.
- **Warning surfaces share one framing.** `.card.lock` and
  `.card.danger-zone` both take `--card-warning-bg` and
  `--card-warning-border`; the action inside differentiates them, the
  framing does not.
- **Primary used sparingly.** "Submit this form" does not qualify;
  routine submits like Upload are Secondary. Primary is the page's single
  main affirmative action.
- **Pills inline in copy.** Confirm labels wrap count phrases as
  `.pill-empty` chips so the eye lands on the numbers without bolding the
  whole sentence.
- **`.bottom-grid` for natural-height pairs.** When two cards in a
  two-column layout do not carry the same weight, prefer `.bottom-grid`
  over `.page-grid`; `.page-grid`'s equal-height stretch is for the
  L-shape patterns that need it (`session_detail.html`).
- **Reviewer-surface chrome is deliberately minimal.** No
  `.session-nav-card` — reviewers fill one form, they do not navigate the
  session.
