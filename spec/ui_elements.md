# UI elements catalogue

The operator surface's element catalogue: the visual primitives the app is
built from, the class each one carries, and the constraints a future
change has to respect. Values live as tokens in
`app/web/templates/base.html`'s inline stylesheet; this document is the
contract they implement.

Every page template sets its `body_class` block to `ui-v2` (reviewer
templates to `ui-v2 reviewer`), so the `body.ui-v2`-scoped rules are the
treatment; the unprefixed rules earlier in the sheet apply only where that
block does not override them. **The one exception is `error.html`**: it
does not extend `base.html`, because it must render when the request
context that `base.html` needs is broken (`app/web/error_handlers.py`),
so it carries its own small light / dark palette in raw hex and sits
outside this catalogue and the contrast audit. Its card still takes the
card shape (`spec/visual_style_general.md`): a 2px edge in
`--border-default`'s value, an 8px radius, no shadow.

> **Reference implementation.** `app/web/templates/operator/session_reviewers.html`
> + the `body.ui-v2`-scoped block in `app/web/templates/base.html`
> together show every primitive in this catalogue in working form.
> When porting a page, mirror that template's class usage.

Cross-references:

- **`spec/visual_style_general.md`** — the portable design system (palette,
  type scale, spacing, component shapes). It names colour **roles**
  (`accent-blue`, `text-primary` and the rest) rather than the app's
  own token identifiers, deliberately, because it is portable; this
  catalogue names this app's tokens, which `spec/color_tokens.md`
  catalogues.
- **`spec/color_tokens.md`** — the two-tier token catalogue. Every token
  named below resolves there.
- **`spec/operator_ui_concept.md`** — page-level chrome and per-page
  layout contracts that consume these primitives.
- **`spec/reviewer-surface.md`** — reviewer-surface page contracts.

When `visual_style_general.md` and Review Robin disagree on a
visual treatment, **the app wins**: `spec/visual_style_rrw.md`
"Other overrides of `visual_style_general.md`" records each
override, and the general spec stays the portable default. This doc
is the implementation catalogue mapping the Review Robin treatments
to CSS classes.

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
> Nor does it arm, for a link or a submit, while the page says it will
> ask before being left (`window.rrwLeaveWillPrompt()` returns `true`).
> Three pages set it, each to the predicate its `beforeunload` guard
> reads: Session Home's details card over unsaved edits, the Instruments
> page over a dirty card, and the Observers expander over an unsaved
> cohort rule. Without the hook the bar would
> sit behind the prompt, and an operator who stays gets no load to clear
> it. A leave the operator confirms loads without a bar.
> *Busy control:* the clicked link or submit button gets
> `aria-busy="true"`, never `disabled` — a disabled control is not
> serialized, so its `name`/`value` would vanish from the payload.
> *Reduced motion:* `prefers-reduced-motion` renders a static bar
> rather than a travelling one.
> *JS off:* nothing renders and nothing breaks.

> **Skip link and main landmark** — the first element in `base.html`'s
> `<body>` is `<a class="skip-link" href="#main-content">Skip to main
> content</a>`, so it is the first focusable element on every page that
> extends it. `.skip-link` sits off-screen (`top: -48px`) until it takes
> keyboard focus, then moves to `top: 8px`, filled `--selected-bg` with a
> `--selected-fg` label. Page content renders inside
> `<main id="main-content" tabindex="-1">`; the `tabindex` is what lets the
> link move focus into the landmark, since a bare `<main>` is not
> focusable.

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
> strips fill with `--nav-strip-setup-bg` / `--nav-strip-ops-bg`, and each
> strip sets its active tab's `::after` underline directly —
> `--nav-marker-setup` on Setup, `--nav-marker-ops` on Operations. The
> Home anchor fills with `--nav-home-bg` and marks itself with
> `--nav-home-marker`. Row labels sit at `--text-subtle`, and the
> right-pointing triangle after them — drawn in CSS from borders rather
> than set as a glyph, so its height matches the surrounding cap-height —
> at `--border-default`. Both darken to `--text-body` when their
> row is active **or** when the cursor is over any tab in that row's strip
> (a `:has()` selector, so hovering previews the row's emphasis without
> transferring active state).

> **Hover = selected.** Hovering any session-nav target — a Setup or
> Operations tab, or the Home anchor — paints it in that target's own
> **selected** colors: `--nav-tab-active-bg` as the background and
> `--text-body` as the foreground for a tab — the selected tab's
> foreground is `--text-body` too — and the anchor's selected background,
> `--surface-page`, for Home.
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
> setup and operations pills sitting inside the nav card.
> `.status-row`, rendered by
> `operator/partials/session_setup_status_row.html` as one `<p>` of
> "key: badge · key: badge" pairs separated by middle dots — lifecycle
> badge first, then a count, state or empty pill per slot, per
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
> size by moving into or out of a card. `--space-3` below and no top
> margin anywhere. `h3` takes `--fs-body` at the same
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
> **All of that exists to deliver `visual_style_general.md` P8: two
> visible card borders never touch.** The mechanism differs by context —
> the wrapper's `gap` inside `.page-grid` / `.bottom-grid`, the card's
> own `margin-bottom` outside one — and the value is 20px in both.
> **The step below a `.page-grid` / `.bottom-grid` wrapper is the one
> exception**: under `body.ui-v2` (every page) the wrapper's own
> `margin-bottom` is `--space-4` (16px), so whatever follows a grid sits
> 16px below it, not 20px. Borders still never touch.
> **Two cards stacked in one cell of a `.bottom-grid` need
> `.bottom-left`** (§10), the flex column whose `gap` spaces them. In a
> plain `<div>` cell the zeroed margin leaves them flush. Check a new
> card by measuring its gap to the card above in a browser, not by
> reading the CSS — `docs/unenforced_conventions.md` §1.12 says why no
> test does it.
> **Tiles grouped inside one card stay tighter, deliberately.**
> `.subcard-row` spaces its tile cards 12px apart
> (`--space-3`; the lobby's first-run card), and `.data-shape-card` tiles
> on Extract Data carry an 8px `margin-top`. A tile row reads as one group
> inside its card, not as separate cards, so it does not take the 20px
> step — but its borders still never touch, which is all P8 requires.

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
> that actually binds. The app-wide `data-delete-confirm="{key}"`
> ↔ `data-delete-btn="{key}"` pairing (base.html) drives single-form
> pages; a **list** of destructive rows (the sessions-lobby /
> archived expanders) uses its own per-node script for the same
> disabled-until-checked behaviour, because the app-wide `querySelector`
> can't address N buttons under one key. **A list whose rows each carry
> a unique key does use the app-wide pairing**: the Instruments page's
> per-instrument delete keys on the instrument id, and the Extract data
> page's Data shaper keys each shape card's Delete `shape-{id}` (saved),
> `shape-new-0` (initial blank) or `shape-new-N` (spawned in JS), per
> `spec/extract_data.md`. That Delete is a `fetch`, not a form submit,
> so its confirm has no form to be `required` in. The confirm-checkbox
> label uses the affirmative **"Yes, delete …"** voice everywhere (full sentence in a
> danger-zone card; compact "Yes, delete" in the expander toolbar) —
> never a permissive "Allow delete".
>
> **`.confirm-label` is `display: flex`, so the sentence must live in
> ONE child element.** A bare text run inside a flex container becomes
> its own anonymous flex item and takes the container's `gap` with it,
> so a confirm that interleaves pills with prose — *"Yes, replace the
> existing `12 reviewers`."* — renders its closing text detached from
> the pill before it. Wrapped in a single `<span>`, the only space beside
> the pill is the pill primitive's own margin, as on every
> pill-in-a-sentence in the app. The `gap` is for the checkbox, not for
> the words. Moving that space onto the checkbox as a margin, in place
> of `gap`, would make the wrappers unnecessary, at the cost of changing
> a shared primitive.

> **`.card.placeholder` (canonical placeholder treatment)** — `.card`'s
> shape with a `--surface-muted` fill, `--text-subtle` H2 and body, and
> `not-allowed` cursor on the card and everything in it. For cards whose
> underlying feature is not yet implemented.
> **Every instance reads identically.** Per-card state distinctions belong
> in body copy, never in an opacity flip: two placeholders on one page
> that differ visually invite the reader to look for a difference in
> meaning that is not there.
> There is **no macro**: a placeholder card writes the canonical heading + body + disabled
> action button directly, and the class above is what keeps every
> instance identical.
> **No markup uses it between scaffolds, and that is expected**: it
> exists for the scaffold-first slices `CLAUDE.md` requires, which land a
> new page with every card a static placeholder before any card is
> wired.

> **`.card.next-action` (Session Home's Workflow card)** —
> `.card`'s shape with a `--card-active-border` border and
> `display: flex; flex-direction: column`. The border signals this is the
> page's single most important card and ties it to the Primary button it
> carries. **The card has no `min-height` of its own, but
> `.next-action-body` carries `min-height: 7.5em`**, so the button row
> lands at the same height in every state and content past that grows the
> card (`spec/workflow_card.md` "Stable card height").
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
> **Always stacked in the per-instrument intro's right column, as wide
> as it** (`.rs-intro-columns`: two `.rs-intro-col`, the heading card
> over the visibility card on the left, one `.rs-help-stack` on the
> right), whatever the count (`spec/reviewer-surface.md`, "Intro and
> help cards"). There is no full-width variant:
> `test_reviewer_response_flow.py` asserts that no `rs-help-card-solo`
> renders.
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
> **A slab with a defined edge**: `--card-help-border` is two palette
> steps off the fill (darker in light, lighter in dark) — **2.54:1** against the page in light, **1.95:1** in dark. Enough
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
> - `.banner.banner-success` (`--status-success-*`) — the Rehydrate
>   page's "Validation passed — ready to rehydrate."
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

Six canonical roles — **Primary**, **Secondary**, **Destructive**
(outline red), **Alert** (filled amber), **Outline-amber** (lock-card
recovery) and **Toggle** (a two-state per-row flag). Every `.btn` shares one shape: `var(--space-2) var(--space-4)`
padding, `var(--radius-button)` radius, `--fs-small` at weight 500, a 1px
border, single-line label. **Roles differ by token, not by shape**, so a
role change is a colour change and nothing else. If a button does not fit
one of the six, ask before inventing a seventh.

**A `.btn` never extends past its container.** The mechanism is `box-sizing: border-box` on the base `.btn`
rule, and it is stated here because the default is a trap rather than a
neutral choice: `<button>` inherits `border-box` from the UA stylesheet
and `<a>` does not, and this sheet has no global reset. Without it the
two forms of one role size differently once either is given a width — a
`width: 100%` `a.btn` in a grid track overflows it by its padding and
border. Only an *explicit* width
does this: flex and grid account for padding and border themselves.
`tests/unit/test_btn_box_model.py` pins both halves — the base rule
carries `border-box`, and nothing anywhere takes it away.

A `.btn` can still overflow the one way the box model cannot reach: a
grid item never shrinks below its longest unbreakable word, whatever
`min-width` says. On the Workflow card's four-slot row that happens only
below the narrowest breakpoint this sheet has, and narrow-viewport
support is a separate spec (`visual_style_general.md`).

| Class | Role | Notes |
|---|---|---|
| `.btn` (no modifier) | **Primary** | `--btn-primary-bg` fill, `--btn-primary-fg` label, `--btn-primary-border` border. Reserved for the page's *single* main affirmative action — at most one per page region. "Submit this form" doesn't qualify; routine submits use Secondary. |
| `.btn.secondary` | **Secondary** | `--btn-secondary-bg` (white) with a `--btn-secondary-fg` label and a `--btn-secondary-border` outline — a medium grey, a shade lighter than the label. The default button. Used for routine submits (Upload, Save), Cancel, View detail, etc. |
| `.btn.alert` | **Outline-amber (recovery in lock card)** | `--btn-amber-bg` (white) with `--btn-amber-border` + `--btn-amber-fg` — the same warning brown that frames the lock card. Per `visual_style_general.md` P7, recovery actions inside a lock card adopt the card's color family. Used e.g. for "Revert to draft" inside a `.card.lock`. |
| `.btn.destructive` | **Destructive (outline red)** | `--btn-destructive-bg` (white) with `--btn-destructive-border` + `--btn-destructive-fg`. Irreversible row / collection **deletes** — Delete session, delete-all rosters, bulk-delete, and the delete confirm step inside `.card.danger-zone`. The role also appears **outside** a danger zone: every roster Setup page carries a `Delete` for the checkbox-selected rows in its **row expander**, not in the table toolbar. The expander is not red and does not become so — the button's own role carries the weight, and the destructive act is gated by the confirmation checkbox beside it (`spec/setup_pages.md` § *Roster controls and their route contracts*). |
| `.btn.danger-solid` | **Alert (filled amber)** | Filled `--btn-alert-bg` with a `--btn-alert-fg` label; lightens to `--btn-alert-bg-hover`. Serious-but-**recoverable** actions — purge-and-archive, Archive session, and the Acknowledge-and-activate confirm. Amber = caution, and the role exists to stay distinct from `.btn.destructive` (red, deletes data) and `.btn.alert` (outline amber, recovery inside a lock card): three amber-or-red treatments that mean three different things, so none may borrow another's fill. |
| `.btn` ⇄ `.btn.secondary` + `aria-pressed` | **Toggle** | A two-state on/off button for one flag on one row. On takes the Primary tokens (`.btn`), off takes Secondary (`.btn.secondary`), and `aria-pressed` carries the state; whatever changes the flag — the click handler for R and ≡, the row's state sync for ⑂ — sets the class and the attribute together. It reuses the two roles' tokens rather than adding its own, so it is a role by behavior, not a new colour. Used on the Instruments page's response-field rows only: **R** (required), **≡** (help-text card) and **⑂** (branch — on once the field has a branch, and disabled then). It is not a chip: the column chips (`.tag-chip` in a `.col-chip-row`) and the Light / Dark switch (`.theme-toggle`) toggle too, but each is its own primitive. |
| `.btn.danger` | *(no rule)* | `.danger` is a context class, not a button role: `base.html` gives `.btn.danger` no rule, and nothing renders it. A `.btn` that enters a confirmation takes Secondary; the destructive treatment lands on the confirm step (`.btn.destructive`). |
| `.btn-icon` | **Icon button** | Borderless single-glyph affordance in `--text-subtle`; the row pager's steps are its one caller. **Neither of Band 3's tables uses this role for their ▲ ▼** — both are outlined `btn secondary`, short (`btn-short`, §10) on the display-field table and full-size on the response-field table. **As an anchor** (the row pager's steps): the live cell is `<a class="btn-icon …">` and the unavailable one a `<span class="btn-icon … is-inactive" aria-disabled="true">` — a `<span>` rather than an href-less `<a>`, following `.nav-tab disabled`, because an anchor without an href is focusable-but-inert in some browsers and not others. Inactive is `opacity: 0.4` + `cursor: not-allowed` and takes **no** accent fill, the reserved shade being for things that act. An anchor `.btn-icon` also needs `text-decoration: none` on its own rule — the page's `a` rule underlines it otherwise, and an underlined `»` reads as a typo. **A specialising rule must name `.btn-icon` in its own selector.** `body.ui-v2 .btn-icon` is (0,2,1) and sits late in `base.html`, so `body.ui-v2 .table-pager-step` ties it and loses on source order — silently, if its declarations happen to match what `.btn-icon` already sets. Write `body.ui-v2 .btn-icon.table-pager-step`, which is (0,3,1) and wins. `tests/integration/test_cascade_ties.py` resolves the cascade in Python — rendered class sets against parsed rules — and fails when a canonical class's declaration is dead because an equal-specificity rule sets the same property later. A variant that comes *later* and wins (`.table-pager-cluster-bottom` over `.table-pager-cluster`) is the idiom and is not reported; a specialisation that comes *earlier* and loses is. The check covers simple class selectors on one element only: combinator rules, `@media` blocks, inline `style=` and shorthand-versus-longhand are outside it, each able to make it silent but none able to make it report a tie that is not there. |
| `.btn-reset` | **Inline text-button** (revert-this-field) | Single-line link-styled button used to revert a single text field inside an editor without cancelling and exiting the whole editor. Reference example: per-field `Reset {{ field }} to default` on the Email Template page (`session_setupinvite.html`). Reads as a small inline link (`--text-link`, underline on hover); posts a form. The pattern can apply to any editor with per-field overrides — adopt this class instead of inline-styled buttons. |
| `.back-link` | **Return-to-where-you-came-from** | Top-of-body inline link rendered as `<a class="back-link" href="{{ return_to_url }}">← Back to {{ return_to_label }}</a>`. The canonical "navigate back" affordance for chrome-detour pages and session-level child pages. Used by Operator Settings (`/operator/settings`), About (`/about`), and any page that should return the operator to wherever they came from regardless of the page's working state. Pages that need a "Cancel uncommitted edits" affordance render an inline Cancel button alongside the working-state Save (the back-link still navigates regardless). The `?return_to=<path>` query-param round-trip surfaces as `return_to_url` / `return_to_label` view-shape variables. |
| `.nav-tab` (chrome class, reused for page-internal) | **Nav button** (page-internal view switcher) | Page-internal tab-like navigation between sibling views inside a single operator page — *not* the chrome. Reference examples: Email Template's `Invitation` / `Reminder` / `Responses received` row (`session_setupinvite.html`); the email-tab strip on the Manage Invitations per-reviewer drill-in (`partials/_email_preview_region.html`). Reuses the chrome's `.nav-tab` styling so the visual vocabulary stays consistent: active view renders `<span class="nav-tab active" aria-current="page">` (non-anchor, current location), sibling views render `<a class="nav-tab">` anchors, "coming soon" reserved tabs render `<span class="nav-tab disabled" aria-disabled="true">`. Wrap in `<div class="tab-strip tab-strip-page">` — the `.tab-strip-page` modifier gives the row a gray `--surface-muted` tint (not the chrome Setup row's pale-blue `--nav-strip-setup-bg`), a thin border, and rounded corners so the active tab's `--nav-tab-active-bg` reads against the row tint. |

**Hover** (per `visual_style_general.md` P6): filled controls lighten,
outline controls gain a subtle tint in their own family. One direction
everywhere, so "you can click this" reads the same way on every control.

- *Filled* — Primary moves to `--btn-primary-bg-hover`;
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
> in one place. **One exception:** inside a container that already fades
> as a whole — the roster toolbar's locked filter strip,
> `.operator-actions-filter.is-locked` — a `.btn` takes `opacity: 1`, so
> the 0.5 comes from the strip once rather than compounding to 0.25 and
> leaving a disabled button fainter than the inputs beside it.

> **No inline-styled buttons.** Every button takes a role from the table
> above; an inline `style` on a button is a defect, because a role that
> lives in one template's markup cannot be restyled from `base.html`. The
> role assignments that recur: a danger-zone form's submit is
> `.btn.destructive`, and a row-level delete / add inside a field
> builder is `.btn.destructive` / `.btn.secondary` — the Instruments
> page's Band 1 rule/unit X and Band 3's response-field X and "+"
> (Band 3 matches Band 1).

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
> **Every table in the app but one sits in one**, which §10 states as a rule and
> a test holds; the wrapper costs a table that never overflows nothing,
> and the judgment about which tables need it is the thing that could not
> be written down.

> **`.col-shrink`** — the shrink-to-fit column idiom: `width: 1%` plus
> `white-space: nowrap`, for a column that should hug its content. On
> the lobby and its archived page (`sessions_list.html`,
> `sessions_archived.html`) it is the Timezone and select-all columns;
> elsewhere it is action columns (the Owners tables, Invitations, the
> Sys Admin Sessions and Users tables) and the response-field table's
> control columns.

> **Reviewer-table column-width hints (`.rs-narrow`, `.rs-status`,
> `.rs-reviewee`, `.rs-textlong`)** — column-shape hints for the
> response-input table on the reviewer surface, applied from each response
> field's `data_type` (`.rs-narrow` also on a profile-link column,
> `.rs-status` on the trailing status column). Reviewer-surface specific; they shape widths only and do
> not conflict with the general table treatment.

### 8. Forms / inputs

> **Text inputs** — one rule covers `input[type="text"]`, `date`,
> `datetime-local`, `number`, `email`, `password`, `file`, `textarea`
> **and** `select`, so a form does not change shape by changing field type
> (`tests/unit/test_input_type_styling.py` fails when a template uses an
> input type the rule does not name):
> `width: 100%`, `padding: var(--space-2) var(--space-3)` (8px / 12px),
> `--fs-body`, `border: 1px solid var(--border-default)`,
> `border-radius: var(--radius-button)`, filled `--surface-page` with
> `--text-body`. Tokens, not literals — `--border-default` moves for
> contrast and a hex written here would go stale
> (`spec/color_tokens.md`).
> **Focus is two-layered.** `:focus` recolours the border to
> `--focus-ring` and adds a 1px `--focus-ring-halo` shadow; `:focus-visible`
> adds a 2px `--focus-ring` outline on top. The browser decides when
> `:focus-visible` matches: always on keyboard focus, and on a click into
> a text-entry field or a `select` too, so a clicked file input is the
> only one left with the halo alone. Both focus rules name every input
> type the text-input rule does.
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
> own gap **must reset that top margin** or the two stack.

> **Helper text** — `.form-help` (`--fs-small` in `--text-subtle`), below
> the input. Use it rather than a `<p class="muted">` or a bare
> `<small>`, so supporting text is one treatment app-wide.
>
> **A card subtitle is not helper text, and takes `<p class="muted">`.**
> The rule above governs text bound to a *field* — it sits below that
> field's input and is read with it. A line directly under a card's own
> `<h2>` / `<h3>`, describing what the card is for, is a different
> element: it precedes every control in the card and belongs to none of
> them.
>
> **The ambiguous case is a card holding exactly one field**, where the
> subtitle and the field's helper text describe the same thing — the
> Tags card on the Create page, whose `<h3>` doubles as the field's
> accessible label. **That takes the subtitle**, so a column of such
> cards reads uniformly rather than alternating. Session Home's Tags is
> not this case: it is a field of the Session details card, so its
> helper is a `.form-help` below the box, `data-edit-only` because it
> describes the box and a locked card has none — only the pills.
> (Create's Owners card takes one too, but is not this case: it holds a table and
> a picker, and the picker has its own `<label for>`.)
> `validation_results.html`'s *"No issues match the current severity
> filter."* sits in the subtitle position but is neither: it is an
> empty-state line under an `<h2>`.

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
| `.pill-role-reviewer`, `.pill-role-reviewee`, `.pill-role-observer` | `--role-<role>-bg` / `--role-<role>-fg` | A participant role, on its own token pair per role. Rendered by the `/me` dashboard's role column, the role-navigator chips on the `/me` surfaces (`app/web/templates/reviewer/_role_chips.html`) and the audience column of Sessions Diagnostics' Visibility grid audit card, which maps the stored `peer_reviewer` audience to the `reviewer` suffix (`app/web/views/_visibility_audit.py`). |

### Label or control

A pill states a fact; a chip offers a click. **That difference has to be
visible without a pointer.** `cursor: pointer` is the whole distinction
only while the cursor is already on the element; it says nothing on touch
and nothing in a screencap.

**Every interactive chip carries a 2px edge in the reserved accent
shade** (`--blue-strong` / `--blue-glow` — see
`spec/color_tokens.md` "Deliberate couplings"), drawn as the 1px
border plus a 1px inset shadow. That covers
`.tag-chip` — which is every lobby tag filter, every column toggle and
every *clickable* Instruments Band 2 pill — plus the lobby's Select all /
Clear all (`.pill-tag-clear`, also on the Archived page) and AND/OR
(`.tag-mode-chip`) chips, and a
role pill when it is a link (`a.pill.pill-role-*`: the `/me`
dashboard's role column and the role navigator's other-role links,
whose `<span>` forms stay plain). Static pills carry no edge: the
Visibility card's locked preview table (`spec/instruments.md` "Visibility
card") is the static, no-click-handler pattern. A fixed switch carries
no edge either (`.tag-chip.is-fixed`, below), and that includes the
display-field table's locked Name / Email chips (`spec/instruments.md`
"Display-field table").

Three rules make that work:

- **The fill is untouched.** The edge is additive over whatever a
  modifier gives the chip, because a Band 1 link chip in the "not set"
  state is `pill-empty tag-chip` and that amber is a *status*. Amber says
  not set, the edge says you can fix it, and both are true at once. A
  blanket `background: transparent` reads as the tidier rule and trades
  one signal away for the other.
- **Every `.pill` reserves the space.** The base rule carries
  `border: 1px solid transparent`; an interactive chip colors that
  border and adds a 1px inset shadow inside it rather than a wider
  `border-width`, so a chip is exactly as tall
  as the status label beside it and adding an edge reflows nothing.
- **`.tag-chip.is-disabled` cancels the edge.** It sets
  `cursor: default` and is an inert chip, as `.is-locked` and
  `.is-fixed` (below) are; a
  chip that says it cannot be clicked must not also say it can.

**A chip can be a form control.** Session Home's optional-tab chips
(`spec/session_home.md`) and the Instruments display-field and
response-field name chips (`spec/instruments.md` "Display-field table",
"Response fields"), and the Assignments status table's instrument-name
and self-review chips (`spec/assignments.md` "Per-instrument status
table"), are each a `<label
class="pill pill-count tag-chip">` around a visually hidden checkbox, so
a click ticks the box and the form or row script reads it. `.tag-chip:has(> input:checked)` is the
`.is-selected` fill, read off the box itself, so a form reset repaints
the chip with no script; the hidden box's keyboard focus shows as a
`--focus-ring` outline on the chip. **`.tag-chip.is-locked`** is the
chip of a locked card: it drops the edge
and the pointer like `is-disabled`, but is not struck through, because
it still says on or off. On takes the card's display-value colors
(`--config-value-bg` / `--config-value-fg`) rather than the reserved
shade; off is faded. **A locked Instruments card's Band 3 chips read as
plain `pill-count` pills** (the author, 2026-10-10): no edge, pointer or
lock glyph, an unticked field faded, read off the card's
`data-instrument-locked` so an in-page lock or unlock repaints them.

`.severity-chip` on Validate is the shape this generalises: an outlined
pill, with `.active` taking the shade on its border and text.

`.is-selected` is unchanged — a solid `--selected-bg` fill, which is how
a chip says its filter is on, and it reaches the reserved shade only on
controls (a fixed switch, `.tag-chip.is-fixed`, is the one inert
exception): a locked chip may carry it to say "on", and
`.tag-chip.is-locked.is-selected` repaints it in the display-value
colors.

**Five chip types, one look each.** What a chip's states mean decides
its fill; a fixed switch keeps the fill of the state it is held at:

| Type | States | Fill | Standard |
|---|---|---|---|
| **On/off** | selected, not selected; the label doesn't change | dark (`--selected-bg`) when on, light when off | the Setup pages' column chips |
| **On/off with a partial state** | all, none, or some of a set; the label counts how many are on | dark when all, light when none, amber (`pill-empty`) when some; a click on light or amber turns all on | the Assignments page's "Include N self reviews" |
| **Cycle** | every state a positive choice, a deliberate "off" included; the label names the state | always dark | Extract's Data shaper "All rows ↔ Rows with data"; the Instruments card's "Include ↔ Exclude self reviews" |
| **Cycle with an unset state** | one "not configured yet" state, the rest positive | amber (`pill-empty`) when unset, dark otherwise | the Instruments page's Band 1 link chips |
| **Fixed** | one switch held at its value while the chips beside it stay live | its siblings' fill for the held state (dark when on), with no edge or pointer and a lock glyph before the label (`.tag-chip.is-fixed`) | Session Home's optional tab once it holds data |

A fixed switch keeps its siblings' dark fill so it reads as a switch
that is on rather than a display; the glyph (a CSS mask in
`currentColor`) says why it doesn't move. A `<label>` chip takes the
fill only while its box is ticked, so a switch fixed off stays the off
chip, with the glyph. A `<label>` chip whose box is disabled is fixed
too, read off the box (`label.tag-chip:has(> input:disabled)`), so a
script that disables or re-enables the box needs no class in step: the
display-field table's Name and Email chips, on a group-scoped
instrument the fields a group row can't show (`spec/instruments.md`
"Display-field table"), and a response field whose branch parent is
hidden ("Response fields"). It is per item: a card's locked view stays
`is-locked`, or on a locked Instruments card the plain pill (above). Its other use is the Instruments
Visibility card's two cells whose mode isn't the operator's to choose
(`spec/instruments.md` "Visibility card"), and the Assignments page's
self-review chip on a session that isn't editable, which keeps its
amber when mixed.

The lobby's AND/OR and Select all / Clear all chips, and the Archived
page's Select all / Clear all, are cycle chips (`.tag-mode-chip`,
`.pill-tag-clear` take `--selected-bg` / `--selected-fg` outright).
Select all / Clear all is the edge case whose label names the next click
rather than a state. The Instruments Visibility cells that can change
are cycle chips too, "—" being a deliberate off. So are Extract's three empty-row chips
("All reviewers ↔ Reviewers with responses" and its two siblings), which
keep `is-selected` on in both labels (`spec/extract_data.md`).
`tests/browser/test_cycle_chips.py` pins the lobby, Archived and Extract
fills;
`tests/integration/test_chip_edge.py` pins the edge treatment;
`tests/unit/test_reserved_shade.py` keeps the shade off anything static
except `.tag-chip.is-fixed`.

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
| `.page-grid` | Equal-height two-column grid (`1fr 1fr`, `align-items: stretch`, 20px gap), collapsing to one column at 800px or narrower. Its callers pair fields more often than cards: field pairs inside Session Home's details card, on the Create page and in Operator Settings' SMTP form, the audit log's two-column filter strip, and the Rehydrate page's cards. It has no placement classes: children fill the grid in source order. `.bottom-grid` is preferred for a new pairing of cards (see below). |
| `.card-columns` | Two independent column stacks: a `1fr 1fr` grid at `align-items: start` with a 20px gap, whose children are *columns* that each stack their own cards, so a card growing in one column moves only what sits below it there. Children take `min-width: 0`, so a wide table or a long unbroken string cannot push a column past its half. It does not collapse at narrow widths. Callers: the Instruments page's guidance and Session status pair, Email Template, and the tag-label editor's fallback home on Reviewers, Reviewees and Relationships. |
| `.bottom-grid` + `.bottom-left` | Two-column grid at `align-items: start`, so each side keeps its natural height instead of stretching to match the taller column. `.bottom-left` is the flex column for stacking several cards on one side. At 800px or narrower it collapses to one column with a 20px `row-gap`, since `.bottom-grid .card` zeroes the cards' own margins. |
| `.card-action-row` | A right-flushed row for a card's own action, `--space-3` above it, as the card's **last child**. Used by the Owners card on the Create page and on Session Home, and the Invitations reviewer drill-in's Review Progress card. |
| `.roster-card` (+ `.roster-readouts`, `.roster-readout*`, `.roster-card-actions`) | The roster pages' roster card: a flex column at a 16px gap. `.roster-readouts` is one wrapping row of label + values readouts, not a one-row table; each readout wraps as a unit so a label never parts from its values. `.roster-card-actions` sits flush right. `spec/setup_pages.md` "The roster card and the Unlock panel" owns the contract. |
| `.unlock-panel` (+ `.unlock-stack`, `.unlock-right`, `.unlock-col-actions`) | Two equal `minmax(0, 1fr)` columns at a 20px gap, top-aligned, one column at 800px or narrower. `.unlock-stack` stacks a column's cards at the same 20px, and cards inside take no margin of their own. **`.unlock-panel[hidden]` restates `display: none`**, because the grid's `display` beats the attribute's UA rule. |
| `.row-expander-body` (+ `.row-expander-actions`, `.row-expander-pane*`, `.row-expander-label`, `.row-expander-count`) | The interior of the injected row-action panel: a wrapping flex row whose `.row-expander-actions` take `margin-left: auto`, so the buttons sit flush right. The `.is-split` modifier makes it a two-column top-aligned grid (Observers; see the expander rules below). |
| `.session-expander-*` + `.exp-*` | The lobby expander's field and button rows. `.exp-field-name` / `-code` / `-deadline` / `-tags` share the row 3 / 2 / 2 / 3, and the bulk expander's `.exp-field-bulk-tags` takes half of it flush right. `.exp-allow-delete` is the confirm, `.exp-purge-opts` (+ `.exp-purge-title`) the purge checkboxes, grayed to 0.5 opacity by `.is-disabled`, and `.exp-sep` the divider between them. `spec/sessions_overview.md` owns the contract. |
| `.quick-setup-*` | The Quick Setup card's layout: `.quick-setup-top-grid` is two columns, one at 800px or narrower; `.quick-setup-slot`s are separated by a top rule; `.quick-setup-body.locked` grays the body to 0.55 opacity with a `not-allowed` cursor; `.quick-setup-card-footer` holds Submit outside that body, flush right. `spec/quick_setup_card_spec.md` owns the contract. |
| `.card.setup-coverage` (+ `.setup-coverage-*`) | Validate's setup-coverage card: the H2 and its subtitle on one line, over a grid of four columns, two at 900px or narrower and one at 500px. |
| `.card.severity-filter-card` + `.severity-filter-row` | Validate's severity filter: a tighter-padded card holding one wrapping row of `.severity-chip`s (§9). |
| `.btn-pair` (inline pair) | Two buttons side by side at their natural widths. |
| `.fill-col` (flex column whose last child grows) | |
| `.subcard-row` (+ `.stepped`, `.subcard-arrow`) | Equal-width tile row inside a card. Detailed below. |
| `.guide-figure` (+ `.guide-figure-narrow`) | The `/guide` screencap figure. Detailed below. |
| `.table-scroll` (`overflow-x: auto`) | A wide table's overflow stays inside its card instead of scrolling the page. **Every table but one sits in one** — see below |
| `.col-divider` (`border-top: 1px solid var(--border-default)`) | A horizontal rule **inside** a column, marking that what follows shares the column for space rather than belonging to what precedes it. Takes the same `--border-default` as the vertical rules between columns, so the two read as one system — that match is the point, and a divider drawn from another token would say the wrong thing. Today: the self-review chip under Link 3 of the Instrument assignment rule card, which is not a unit-of-review setting and must not read as a third Link 3 state (`spec/instruments.md` § *Self-review exclusion*). **Use it only where a reader would otherwise misattribute the control to the block above**; a rule between two things that do belong together is noise |
| `row-group-start` (`tr.row-group-start > td { border-top: 2px solid var(--border-default); }`) | A heavier rule above a **table row** that starts a new group, where the table already separates every row with 1px. First user: the Observers row of an instrument's visibility editor (`spec/instruments.md` § *Visibility card*) |
| `table-compact` (`body.ui-v2 table.table-compact th, td { padding: var(--space-1) var(--space-2); }`) | A table whose rows sit closer together than the default cell padding gives. First user: Band 3's display-field table (`spec/instruments.md` § *Display-field table*) |
| `rf-table` | Band 3's response-field table (`spec/instruments.md` § *Response fields*). One `<tbody>` per field, ruled underneath (`border-bottom: 1px solid var(--border-default)` on the `<tbody>`) and not inside it (`border-bottom: 0` on each `<td>`), so a branch's parent, condition row and governed fields share one `<tbody>` as one ruled group (`td.rf-branch-bar` draws the branch's bar, 4px at 0.35 opacity, from a parent's + column (`td.rf-branch-bar-start`), and `--rf-glyph-width` (2rem, R and X's own width) gives every row button — +, ⑂, ↰ / ↳, R, ≡, ▲, ▼, X — one width; `td.rf-active-cell` is every row's first column, holding the field's name chip (`label.rf-name-chip`: an on/off chip around the Active checkbox, flush left, `max-width: 8em` border box, a longer name ending in "…"), `td.rf-slot` is an empty column of the glyph width, two after ↰ / ↳, into which a branch's rows shift one column per level (a level-1 row fills both, its ↰ in the first and its ↳ in the second), `tr.rf-inner-top` / `tr.rf-inner-end` rule a branch inside a branch above its parent and below its last field from the parent's + column (`td:nth-child(n+3)`) rightward, and the condition row's `td.rf-condition-lead` / `td.rf-condition-op` (on a List parent `tr.rf-condition-list`, the operator shrunk and its box beside it) put "If the above" right-aligned before the name column and the operator in it). The table keeps `min-width: 66rem` and scrolls in its `.table-scroll` on a narrow card, locked or not: a locked card makes the table inert, never its `.table-scroll`. The name column takes a fixed share (20%) and the type column `8.5rem`, about an "Agreement" select; the bounds column takes the rest, its boxes no narrower than `3.5rem` (room for "2000"). An empty name box (`td.rf-name input`) shows its default label muted, as its placeholder (`color: var(--text-subtle)`, `opacity: 1`, so the color alone mutes it whatever opacity a browser gives placeholders by default) |
| `.btn-short` | A shorter `.btn` for a compact table row — same role and outline, 19px tall inside a 32px row. Used by the display-field table's ▲ ▼ (`spec/instruments.md` § *Display-field table*); the response-field table's ▲ ▼ stay full-size |
| `.chip-group` | One labelled group of chips inside a `.col-chip-row`, so a row carrying several groups wraps **between** them rather than stranding a label from its chips |
| `.col-chip-row.is-grouped` | The modifier a chip row takes **when its chips are in `.chip-group` boxes**: it swaps the parent's `gap` for a wider `column-gap` between the groups. A `gap` applies on both axes, so a wrapped second line arrived indented against the line above it; a column-gap is between-items-on-a-line by definition and cannot. A **modifier and not a change to `.col-chip-row`**, because the four roster rows put their label and chips directly in the row — widening the gap there would space a label from its own chips. Assignments is the only caller (its three groups sit in the half-width left pane, where they do not fit on one line) |
| `.col-chip-row` (+ `[data-col-toggles-for]`, `[data-col-toggle]`, `[data-rrw-col-toggles]`) | The column-visibility chips above a table. A chip is `role="button" tabindex="0"` and toggles `col-hidden-{slot}` on the table it names; each page maps its own slots to its own column classes, so the slot vocabulary is not fixed here. The storage key lives on the **table** (`[data-rrw-col-toggles]`) and a page may carry several chip rows against one table, grouping its slots. **Both behaviours are delegated on `document`**: a chip rendered after load works with no registration, because the handler resolves its row, table and storage key from the event target with `closest`. **A re-rendered table card must call two hooks** — `window._rrwHydrateColToggles()` to restore the operator's saved columns, and `_rrwHydrateFromCookies()` to repaint the sort badges (and to re-sort the rows when the stored spec holds a `response:N` key, which the server cannot apply) — because delegation keeps a chip *clickable* while the server re-renders it all-visible, and neither state is in the markup |
| `.session-row-selected` | A selected or edited row on the sessions lobby, its archived page, the four roster pages and Assignments. **A rail at each end, and no fill**: `--selected-bg` as a `box-shadow: inset 6px 0 0` on `td:first-child` and `inset -6px 0 0` on `td:last-child`. Detailed below |
| `.table-pager-cluster` (+ `.table-pager-cluster-bottom`, `.table-pager-step`, `.table-pager-menu`, `.table-pager-menu-panel`, `.table-pager-menu-item`, `.table-pager-anchored`) | The row pager on a roster-bearing table, rendered above the table and again below it. **Five cells**: `«` first, `‹` back, a range menu, `›` forward, `»` last — so any page is one move away whatever the roster size. Ranges (`201–400`), not page numbers. Suppressed whenever a search or status filter is active. The four steps are the `.btn-icon` role and carry no link underline; at the ends they render **in place and inactive** (`<span aria-disabled>`, never absent, or the other cells shift sideways as the operator pages) and take no accent fill — the shade `--blue-strong` / `--blue-glow` stays reserved for things that act, and an inactive step does not. The menu is a `<details>` holding every range as an anchor, **not** a `<select>`: a select navigating on `change` fires on every arrow key, so a keyboard user reaching the fifth option would navigate five times. Its summary names the current range, so one element says where you are and is the way to leave; the current entry is a `<span aria-current="page">` marked by weight and a muted fill. Every cell is an anchor — the pager needs no script to navigate; one delegated `document` listener closes the menu on an outside click or Escape. Each href carries a `#<noun>-table-card` fragment so a page turn arrives at the **table's card**: its top edge, then the column chips, then the cluster, then the new rows. The id sits on the card with a `scroll-margin-top` so the top border reads as a boundary rather than a crop; the route supplies the id, the pager never derives it. **This is one of three landing targets, and the only one that is a card** — see the landing-target entry below; the filter strip's controls now take this same anchor, so the contract is no longer the pager's alone. The cluster shares the chip line where it fits and wraps to its own line where it does not — the chip row's width is operator data, and a roster with no tags renders no chip row at all, so the row belongs to the cluster and the chips join it |
| **Landing targets** — `#<noun>-table-card`, `tr.row-action-target`, `#<noun>-row-editor` / `#<noun>-row-<id>` | **Three targets, and only the first is a card.** A page turn, and a filter or a Search / Clear, lands on the **table card** (`scroll-margin-top: var(--space-4)` — enough to keep the top border off the viewport edge so it reads as a boundary rather than a crop). A **row action** lands on the row it acted on, via `tr.row-action-target` at **`scroll-margin-top: 88px`** — deliberately larger than the cards' 16px, because a row flush against the viewport edge reads as the table's first row rather than as one row among others, and because the row's own expander renders *below* it: 88px clears one 68px row plus 16px, putting the acted-on row second from the top with a neighbour visible for context. Nothing on these pages is `position: sticky`, so there is no fixed chrome to land underneath. **Entering edit mode takes the third**: `#<noun>-row-editor` is an **add-mode-only id on the `<tr>` itself**, and `Edit` builds `#<noun>-row-<id>` from the id it already has — there is no editor card in the contract, the row is the editor. A fourth anchor, `.roster-card`, exists for the same reason as the first: a control inside the Unlock panel returns to `#roster-card` so the panel stays open, and without a `scroll-margin-top` it arrived cropped. On the three pages with a tag-label editor that is the labels save, the delete-all and a successful import; on Observers, which has none, the latter two. **A fragment that does not resolve is ignored by the browser and lands at the top of the document**, so any surface using a row fragment must also ship the fallback that catches a missing target — at most **two** cases reach it — a row the active filter excludes, and a row moved by a cookie-held sort. A delete is **not** one of them: it is handled a step earlier by the route, which has no row to land on and so sends the table card itself, and the script never fires. Two is the ceiling, not the count on every page — a page whose table is not sortable reaches only the first, as Observers does; Reviewers, Reviewees and Relationships are all sortable and reach both. `spec/setup_pages.md` § *Per-row Edit / Add / bulk actions* states the same rule for the page that implements it |
| `.filter-row` (+ `.filter-row > label`, `.filter-actions`) | **The search + status filter strip, as one unscoped base with narrowings.** It was three private per-card copies; declaring the shape once means a move carries it, which is what let Reviewers lift the strip into its table toolbar without restyling it. The base sets the row (`flex`, `--space-4` gap; status a third of the width, search two thirds, so the typeahead's `Name (email)` labels stay readable while the dropdown collapses to its short options) and the action row (`flex`, `flex-end`, wrapping). Each named scope narrows **only what genuinely differs**, and says why. One `body.ui-v2` prefix on the generic label rule is **load-bearing specificity, not scoping**: the global `body.ui-v2 label` is (0,1,2) and would otherwise beat a bare `.filter-row > label` at (0,1,1), re-blockifying the label, un-stacking it from its input, and blockifying the select with it — which is only `display: block` by virtue of being a flex item |
| `.table-card-toolbar` (+ `.is-split`, `.toolbar-pane`, `.toolbar-left`, `.toolbar-right`) | **Two bare panes at the head of a table card**, on **all seven table pages** — the four rosters and the three Operations tables (Assignments, Invitations and Responses). Card geometry — the same half-and-half split and gutter `.card-columns` gives — with **no border, fill or padding of its own**, because these are regions of one card rather than two cards. That is the distinction §10 already draws against `.card-columns`, now with a name. Left pane: what the table is showing (column chips, pager cluster, count line) — **and it renders empty where a page has none of those**, as Observers does on an unpaged roster: it has one fixed tag slot so no chips exist to toggle, and the pager appears only past one page. The pane stays so the split holds; an asymmetric toolbar is the intended shape, not a gap to fill. Right pane: the filter strip that decides it. The strip moved here from a card a grid away, so the controls sit with the rows they act on. **`is-split` stays a modifier now that every carrier opts in**, which looks redundant and is not: the shared class stays `display: flex`, so the next page to open a table card with a toolbar is not silently re-laid-out by a grid it never asked for. A pager-only toolbar is the sharp case — as a grid item the cluster would right-align into the second column. **The two panes are gated differently by page family, and deliberately**: the rosters include the pager and count line unconditionally and let those partials self-guard, while the three Operations pages wrap the whole left pane in a has-rows conditional — `{% if rows %}` on Invitations and Responses, `{% if pair_sample %}` on Assignments, whose rows are generated rather than rostered. An empty pane and an absent pane render the same, so nothing turns on it visually; recorded so the next reader does not take one for a bug |

**A lone card in a two-column grid is a decision, not a default.** A
single child of a `1fr 1fr` grid lands in column 1 and reads as a card
that failed to fill the row. Half width flush right suits a *control*,
full width a *readout* — the author's call each time. Where the answer
is full width, the grid goes: a grid with one child is not a grid, and a
plain card is page width with no rule at all. Invitations and Responses
take that answer for their counters card, because eight pills in half a
page wrap badly (`spec/operations_pages.md` § *Shared page shape*).

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

**The selected row (`.session-row-selected`).**

- **Rails, not borders.** Inset shadows, so marking a row does not
  change its height and reflow the table under the pointer; no top or
  bottom cap, for the same reason.
- **No fill.** A row fill resolves to the same primitives that back
  `.pill-count` and `.pill-info`, so it erases every pill the row
  carries, and no pale fill clears the pills while still reading as a
  highlight.
- **Two meanings.** On every page that carries it, it marks a row the
  operator checked. On every roster Setup page it also marks the row
  being **edited** — a server-rendered `?edit_id=` / `?add=1` row, which
  is not selected at all — because the edit row wants the same
  treatment: rails at both ends, no fill, and an expander beneath it
  closing the bracket. The class means *"this row, and the panel under
  it, are one unit"*; a third meaning should be named here rather than
  assumed.
- **The panel closes the bracket.** The injected expander row carries
  `.session-expander-bracketed`, whose single `colspan` cell is first and
  last child at once and so takes both rails in one declaration, over
  `--selection-panel-bg`. **The panel is a pill-free zone**: its fill
  resolves to `--status-info-bg`'s primitive, so a `.pill-count` inside
  it reopens the collision one storey down.
- **Opt-in by class.** These templates inject panels with the same
  `session-expander` class names from their own scripts, which differ
  deliberately: `sessions_list.html`, `sessions_archived.html`, the four
  roster pages (`session_reviewers.html`, `session_observers.html`,
  `session_reviewees.html`, `session_relationships.html`) and
  `session_assignments.html`. An unscoped rule would style every one of
  them whether or not each marks its rows. Each roster page renders both
  the expander and the bracketed variant, for its selection actions and
  for the edit row's Save / Cancel bar.
- **Observers' expander is two-column** (`.row-expander-body.is-split`):
  the cohort rule builder in the left pane, the count / confirm / actions
  in the right, top-aligned, because the builder is the taller and
  bottom-aligning would anchor `Save` to a button row it has no
  relationship with. That variant is this page's alone.
- **One selection funnel per page.** The class is applied in the page's
  single selection funnel, which clears all rows each pass before
  marking the selected set: `refreshExpander()` on the two lobby pages,
  `render()` on Reviewers, Reviewees, Relationships and Assignments,
  `renderPanel()` on Observers. The contract is the funnel, not its
  name. **Assignments' funnel counts only visible rows**, because it is
  the one page with a client-side filter: its instrument-name chips
  hide rows with `display: none`, and an expander anchored
  after a hidden row, or a `colSpan` counted before a chip toggle, both
  follow from treating a selectable row as a visible one.
- **A sort drops the panel and re-anchors it.** `_rrwApplySort` removes
  every `.session-expander` child of `tbody.rrw-rows` **before** it
  collects rows or stamps `rrwOriginalIndex`, on every sortable table,
  then dispatches `rrw:sorted` once the rows have landed. Removal rather
  than hiding, because a hidden row still occupies an index: a panel
  counted at stamping time shifts every row after it by one, so clearing
  the sort stops restoring the server's order. The six injecting pages
  that sort — `sessions_list`, `sessions_archived`, `session_reviewers`,
  `session_reviewees`, `session_relationships` and `session_assignments`
  — listen for `rrw:sorted` and rebuild through their funnel, with no
  per-page capture-phase removal handler beside it. Rebuild rather than
  move, because the panel's content follows the selection, not the row
  order. `session_observers` injects a panel without a sortable table,
  so it needs neither half.
- **Not a general primitive.** Named here so it is findable, and
  deliberately not promoted: it was designed for one wide row in a tall
  table of *like* things. A speculative further use, a Rosters index, is
  recorded in `guide/archive/new_ux_ideas.md`.
- **Outside `tests/unit/test_reserved_shade.py`**, neither scanned nor
  exempted: that guard's filter is pill / chip / `btn-icon` classes,
  elements with a dual nature, and a `<tr>` has none.

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

**`.table-scroll`.** Every table in the app sits in one, with a single
exception, and `tests/unit/test_table_scroll_wrappers.py` holds the rule.
There is no width threshold, because **nothing in a template knows a
rendered width**: which tables overflow depends on the viewport, and an
exceptions list is a judgment nobody re-measures. A wrapper on a table
that never overflows costs nothing.

Three things the rule has to say out loud, because a template-level check
cannot see them:

- **A table built in JavaScript needs the wrapper on or directly around its host.** The
  Instrument card's Band 2 preview is assembled in `rebuildPreview` and
  written into `[data-new-model-band2-preview]`; there is no
  server-rendered `<table>` to wrap, so the wrapper sits directly around
  the container (not on it: the container is a lock region).
- **It can hold a non-table.** The Instrument card's Band 1 wraps its
  rule columns (`.band1-grid`, a `76rem` floor) in one, the first form
  layout rather than table to use it. **A locked region
  goes inside the wrapper, never on it**: an inert `.table-scroll`
  doesn't scroll.
- **`.shaper-preview-table` goes without**, and is the one exception.
  It is flattened to `display: block; width: 100%` with its cells as
  wrapping flex children, and its own `.shaper-preview-scroll` sets
  `overflow-x: visible` deliberately — the row *wraps to a second line*
  rather than scrolling. It is a table in name only and cannot exceed
  its container; a scroller there would re-add what that rule removed.
  The exception is anchored to that CSS decision, not to a width.

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

The captures arrive at **two scales** — a narrow 1× family at ~830px and
a wide 2× family around ~1680px. Left to fill the prose column they would read at two
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

**What none of it checks is that the two halves show the same app
state.** A pair is meant to be one screen photographed twice; nothing
stops it being two different screens, and the failure is invisible to
every gate above — the files exist, both halves land in the same scale
family, the one `alt` agrees with itself. It is a reader-facing defect: the instrument appears
to rename itself, or a counter to change, when the theme toggle is
pressed. Comparing pixel heights catches only the cases where the difference
moves the layout. **So a replaced capture is read against its twin, not
just against the page**, and the alt text is written to be true of
both.

In-card headings on `/guide` take a `--space-6` top margin
(`body.ui-v2 .card[id^="guide-"] h3`): its cards run long enough that
their `<h3>`s are section breaks rather than labels on the paragraph
below, which is what ui-v2's global `h3` rule assumes. Scoped by the
`guide-` id prefix the cards already carry, so no other page moves.

### 11. Misc one-offs

> **`.btn-icon`** — a borderless single-glyph affordance in
> `--text-subtle`; the row pager's steps are its one caller. See the §6
> row for the anchor form and the specificity rule a specialising
> variant must obey.

> **Sort headers** — `th.rrw-sortable` (kept on one line) holds the
> label and a small `.rrw-sort-btn`, the click target, so the label
> reads as a label rather than a control. The button is borderless in
> `--text-subtle` until hover, which adds a `--border-default` edge on
> `--surface-muted`; `:focus-visible` takes a 2px `--focus-ring-strong`
> outline. `.rrw-sort-badge` inside it reads `↕` on an unsorted column
> and the column's rank and direction (`1↑`) once sorted, when it also
> takes `.rrw-sort-badge-active` (`--text-body`, weight 600). The Band 2 preview renders the button as
> an inert `span.rrw-sort-btn`, the same box with no control's look.
> The table-side contract and the click semantics are in
> `spec/setup_pages.md` and `spec/sort_by_reviewee.md`; the Instruments
> page's `.sort-btn` below copies the button's dimensions.

> **`<pre>` blocks (outbox preview)** — render as `.code-block`, the
> same content-surface family as cards. A raw `<pre>` is not a
> content surface and must not be used as one.

> **Email preview (Invitations drill-in)** — `.email-preview-card`
> stacks `.email-preview-tabs` (a `.tab-strip-page`), the envelope
> lines (`.email-preview-header`), an `<hr class="email-preview-divider">`
> and `<pre class="email-preview-body">`. That `<pre>` is not a
> `.code-block`: it is monospace and `pre-wrap` with no fill of its own,
> because the card is already its surface.

> **Instruments page primitives** — in `base.html` with the rest of
> the app's CSS, each scoped to markup only that page renders:
> - `data-instrument-locked` rules hide `[data-unlock-only]` /
>   `[data-lock-only]` controls by card state, dim a locked card's
>   `[data-lock-region]` and its visibility preview card, and hide an
>   empty intro name (`.rs-intro-name[data-intro-empty]`);
> - `.save-error-banner`, the card's server-error list above Save;
> - disabled `[data-new-model-rf-data-type]` / `[data-new-model-rf-bound]`,
>   a response field's frozen shape (it has responses);
> - `.sort-btn` / `.sort-badge` (and `.sort-badge-empty`), the
>   display-field sort control and its rank number;
> - the Band 2 preview's cell padding and top alignment, matched to the
>   reviewer surface's rows;
> - `.instrument-card-collapsible` / `-summary` / `-toggle-icon` /
>   `-drag-handle` / `-dragging`, the collapsible, draggable card (a
>   summary pill sits 1px higher to align with the title), and
>   `.card-title-fallback`, the `Instrument_{N}` title of an unlabeled
>   card;
> - `.page-break-card` / `-label` / `-delete`, the reviewer page-break
>   marker between cards;
> - `.instrument-reorder-toast`, the reorder-failure toast — fixed, on
>   `--toast-error-bg`, and with **no drop shadow** (the toast's own
>   fill separates it from the page).

> **Admin audit-log primitives** — in `base.html`, scoped to markup only
> `operator/sys_admin_session_audit_log.html` renders:
> - `.audit-log-table`, `table-layout: fixed` with a `.col-*` width per
>   column, so the detail cell wraps instead of widening the table;
> - `.audit-detail` / `-section` / `-raw`, the per-row expander: a link-
>   colored `summary`, a `<dl>` grid per envelope section, and the raw
>   JSON in a nested `<details>`.

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
that owns them, each with a pointer to its owner. None is decided here.

- **A page turn reloads** — §10, "A page turn reloads the page".
- **Hover by fill** (`visual_style_general.md` P6) — §6, "Hover".
- **Recovery actions in colored cards** (`visual_style_general.md` P7)
  — §4, `.card.lock`, and §6, the `.btn.alert` row.
- **Warning surfaces share one framing** — §4, `.card.danger-zone`.
- **Primary used sparingly** — §6, the `.btn` row.
- **Pills inline in copy** — §9.
- **Cards never touch** (`visual_style_general.md` P8) — §4, `.card`.
- **`.bottom-grid` for natural-height pairs** — §10.
- **Reviewer-surface chrome is deliberately minimal** —
  `spec/visual_style_rrw.md` "Reviewer-facing pages".
