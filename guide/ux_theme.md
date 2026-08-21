# UX theming sweep — light / dark mode (Segment 19C Item 2)

**Purpose.** Working sweep + punch-list for wiring an operator-facing
**light / dark Display mode**. Records what is already themeable, what is
not, and the exact code that needs work before a dark palette can ship. Not
a spec — the shipped behaviour goes to `spec/visual_style_rrw.md` /
`spec/operator_ui_concept.md` when it lands.

## Decision (settled)

- **Purely browser-local.** The theme choice lives in `localStorage`
  (`rrw-theme` ∈ `{light, dark}`) and is applied via a `data-theme`
  attribute on `<html>`. **No backend** — no route, service, model,
  migration, or template-context change. Covers operators *and* participants
  uniformly, and (with a synchronous head script) is flash-free without any
  server involvement.
- **Two states only — Light (default) and Dark.** No `system` / OS-follow
  option (dropped 2026-08-20). **Light** is the bare `:root`; **Dark** stamps
  `data-theme="dark"`. There is **no `@media (prefers-color-scheme: dark)`
  block** — first load is always Light until the user picks Dark. This
  simplifies both the palette (one dark block, not two guarded ones) and the
  toggle (a 2-way control).
- **`color-scheme`** tracks the active theme (`light` on `:root`, `dark` on
  `:root[data-theme="dark"]`) so the browser paints its *native* surfaces —
  scrollbar gutter, canvas, overscroll, form controls — in the active theme.
  Without it the page background is dark but those surfaces stay light.
- **UX placement is deliberately open** (chrome vs. `/operator/settings`
  card) — see "Open — UX placement". The *code* work below is
  placement-agnostic except for the toggle control itself (W6).

## Mechanism (all client-side)

1. **Dark palette** — dark values for the `base.html` colour tokens under a
   single guarded block: `:root` keeps the light palette + `color-scheme:
   light`; `:root[data-theme="dark"]` redefines the tokens + `color-scheme:
   dark`. base.html's `body` also needs `background: var(--bg-page)` (its real
   rule sets none), or the page canvas stays white in dark.
2. **No-FOUC head script** — a *synchronous* inline `<script>` at the very
   top of `base.html`'s `<head>` (before the `<style>`) reads `localStorage`
   and sets `data-theme` before first paint. Eliminates the flash with no
   server round-trip.
3. **Toggle JS** — writes `localStorage`, flips `data-theme` on `<html>`,
   updates `aria-pressed`. Lives wherever the control lands.

## Sweep findings (taken at `main` 162ddaa)

### base.html — the canonical palette

- **28 colour tokens** defined in `:root` (the palette). `--bg-card` /
  `--text-on-accent` were added and the `#fff` split shipped in PR #2012.
- **118 raw-hex usages remain** (~48 distinct values) in the `<style>`
  block — not yet tokenised, so they would be **light islands** under a
  dark palette. Breakdown of the notable ones:
  - Map cleanly to existing tokens (value-identical): `#2563eb`(9)→
    `--accent-blue`, `#9ca3af`(6)→`--text-muted`, `#d97706`(5)→
    `--accent-amber`, `#d1d5db`(4)→`--border-default`, `#111827`(4)→
    `--text-primary`, `#fee2e2`(3)→`--accent-red-bg`, `#fafcff`(3)→
    `--accent-blue-bg-faint`, `#6b7280`(3)→`--text-secondary`,
    `#fef3c7`/`#92400e`/`#e5e7eb`/`#eff6ff`/`#dbeafe`/`#dc2626`/`#1d4ed8`
    → their obvious accent/border tokens.
  - **One-offs with no token** (need new tokens or consolidation):
    slates `#94a3b8`(7) `#475569`(3) `#1f2937`(3) `#cbd5e1`(2) `#4b5563`(2)
    `#374151`(2) `#64748b` `#e2e8f0` `#0f172a` `#f1f5f9`; plain grays
    `#ddd`(6) `#555`(3) `#222`(3) `#999`(2) `#444`(2) `#eee` `#bbb` `#777`;
    surfaces `#f3f4f6`(4) `#f4f4f4`(2); violets `#ede9fe`(2) `#5b21b6`(2);
    reds `#b91c1c`(5) `#991b1b`(3); ambers `#f59e0b`(2); blues `#1e40af`(2)
    `#075985`; greens `#16a34a` `#166534` `#dcfce7` `#f0fdf4` `#e0f2fe`
    `#f0f9ff` `#f8fafc`.

### Non-base templates — light islands outside base.html

Six templates carry raw hex; seven have their own `<style>` block (most of
those already consume tokens). Priorities:

- **`operator/instruments_index.html` (46 hexes — the big one).** Its inline
  `<style>` references a **shadow token vocabulary that base.html never
  defines**, so every one always falls back to its light hex:
  `--danger-bg` / `--danger-border` / `--danger-text`, `--surface-muted`,
  `--color-muted` / `--color-border` / `--color-text` / `--color-error` /
  `--color-link` / `--color-success` / `--color-warning`, `--border-muted` /
  `--border-strong`, `--rule-bar-color`, `--bg`. These are a parallel naming
  scheme that diverged from the canonical `--accent-*` / `--text-*` /
  `--bg-*` / `--border-*` tokens. **Reconcile them to canonical tokens**
  (either define the aliases in `:root` pointing at canonical tokens, or
  rewrite the usages) so the instrument card + Band-1 rule editor theme at
  all.
- **`error.html` (7 hexes) — STANDALONE.** It is its own `<!doctype html>`
  document; it does **not** extend `base.html`, so it inherits neither the
  palette, the head script, nor `data-theme`. Decide: give it its own tiny
  `prefers-color-scheme` block, or accept it staying light (it's a rare
  error page). Lowest priority.
- **Minor (1-2 hexes each):** `reviewer/results.html`,
  `operator/sys_admin_session_audit_log.html` (+ its own `<style>`),
  `operator/session_observers.html`, `operator/session_extract_data.html`.
  Tokenise their few colours.

## What code needs work (punch-list)

| # | Work | File(s) | Risk / notes |
|---|---|---|---|
| **W1** | Tokenise the remaining **118 raw-hex usages** → canonical tokens; add new tokens for the one-off slates / grays / violets (or consolidate imperceptible near-dupes). | `base.html` | Value-preserving (light unchanged). **Delicate:** must not corrupt the 28 token *definitions* → per-site pass, not a bare global replace. |
| **W2** | Reconcile the **shadow token vocab** to canonical tokens so the instruments page themes; tokenise its remaining raw hexes. | `operator/instruments_index.html` | Define aliases in `:root` **or** rewrite usages. Biggest single island. |
| **W3** | Tokenise the minor templates' few raw hexes. | `reviewer/results.html`, `sys_admin_session_audit_log.html`, `session_observers.html`, `session_extract_data.html` | Small. |
| **W4** | **Dark palette** — dark values for the full token set under `:root[data-theme="dark"]` (single block), plus `color-scheme` on both states and `body { background: var(--bg-page) }`. Tune in the preview harness first. | `base.html` | **Needs dev-slot visual QA** — colour correctness across cards / pills / banners / tables / forms / nav / danger zones can't be verified by the test suite. Any raw-hex site left after W1–W3 shows as a light island. |
| **W5** | **No-FOUC head script** — synchronous `<script>` at the top of `<head>`. | `base.html` | Small; `node --check` in tests. |
| **W6** | **Chrome toggle + JS + retire settings card** — a shared `_partials/theme_toggle.html` two-segment pill `[☀ Light \| 🌙 Dark]` in the `.chrome-user` of all three top-bar variants; wire `localStorage` + `data-theme` + `aria-pressed` (Light = remove `data-theme`; Dark = set it). Remove the `/operator/settings` Display-mode card + its test. | `_partials/theme_toggle.html`, `base.html`, `reviewer/_top_bar.html`, `review_surface.html`, `operator_settings.html` | Placement settled (chrome, see below). |
| **W7** | **error.html** dark handling (own `prefers-color-scheme` block) or leave light. | `error.html` | Standalone doc; lowest priority. |
| **W8** | Verify: `node --check` on the new inline JS; dev-slot visual QA on representative pages (a dark card, a pill row, a banner, a table, the Danger Zone, the instruments page). | tests + dev slot | The test suite can't see colour. |

## Preview harness (in-repo mockup)

`guide/theme_preview.html` is a standalone dark-mode design harness —
**open it in a browser**, no server or seed data. It lifts the *real*
`<style>` block from `base.html` (so the component CSS is faithful, not a
hand-copy), applies a **draft dark palette**, and renders a component gallery
plus a **swatch grid of all 47 tokens** whose chips show the *active* theme. A
toolbar flips Light / Dark live (2-state, default Light).

**Gallery coverage** — the shared `base.html` vocabulary: the canonical `.btn`
set; text / links / breadcrumb; cards (plain / help / Danger Zone); pills;
warning / danger / soft-error banners; a table with config-value cells;
instrument tints; **form controls** (input / email / number / select /
textarea / disabled + focus ring); the **chrome top bar**; the **session
navigation** (tab strips + active states); and **tag-chips** + back-link /
page-header / help-preview. *Out of scope:* components whose CSS lives in an
individual template's own `<style>` (not `base.html`) — the Instruments
Band-1 rule-editor bars, sort buttons / badges, the reorder toast, Band-2
preview tables. Those are page-specific islands, not the shared palette this
harness (and a default-scheme rethink) turns on.

This is the W4 tuning loop: edit the `DARK = {…}` map in
`guide/theme_preview.gen.py`, re-run `python3 guide/theme_preview.gen.py`,
refresh the browser. The draft values are a first cut (tokens named
`*-dark` / `*-strong` / `*-text` invert to light-on-dark; `*-bg` tints become
dark solids). When the palette reads well across the gallery, **port the final
values into `base.html`'s `:root[data-theme="dark"]` block** — that is W4
proper. The harness is a design tool only; it is not wired into the app, and
it retires with this doc when dark mode ships.

## Sequencing (the Item 2 ladder)

1. **Tokenise** — W1 + W2 + W3 (value-preserving; light mode unchanged;
   independently reviewable and safe).
2. **Dark palette + no-FOUC** — W4 + W5 (dark works after this,
   before any toggle; **dev-slot QA**).
3. **Wire the toggle** — W6 (+ W7 mop-up).

## UX placement — settled (2026-08-21): chrome pill

**Decision: a chrome light/dark toggle, not the settings card.** The clincher
is reach — participants never see `/operator/settings`, so a settings-only
control can't serve them; the chrome is the only surface common to operators
*and* participants. So:

- **Control** — a shared `_partials/theme_toggle.html` include, dropped into the
  `.chrome-user` block of all three top-bar variants: base.html's operator
  chrome (`{% block top_bar %}`), `reviewer/_top_bar.html`, and
  `review_surface.html`'s custom bar. (Note: `.chrome-user` is gated on
  `{% if user %}`, so logged-out pages like `pre_open` won't show it — move it
  to `.chrome-left` if pre-auth toggling is wanted.)
- **Shape** — a **two-segment pill** `[ ☀ Light | 🌙 Dark ]`, active side
  highlighted via `aria-pressed`. Two states only (System was dropped
  2026-08-20). CSS in base.html.
- **The `/operator/settings` Display-mode card is retired** — the chrome pill is
  the single canonical control. This retargets Segment 19C Item 2 from "settings
  card" to "chrome toggle" (the scaffolded card + its test get removed in W6).

W6 (below) is this pill + the card removal. It stays the last step: it only
does something once the dark palette (W4) + no-FOUC script (W5) exist — a pill
wired before then is a dead switch (base.html has no `[data-theme="dark"]`
block yet; the palette lives only in the preview harness).

## Status

- ✅ `#fff` split (`--bg-card` / `--text-on-accent`) — PR #2012.
- ✅ **W1 — base.html tokenised.** All 113 raw-hex usages in the `<style>`
  block resolved: value-identical hexes → existing tokens; near-dupe legacy
  grays / slates / surfaces consolidated onto the neutral ramp (imperceptible
  in light); genuinely-distinct accents given **10 new exact-value tokens**
  (`--accent-red-strong` / `-text`, `--accent-amber-border`,
  `--accent-green-text` / `-bg-faint`, `--accent-blue-strong`,
  `--accent-violet-bg` / `-text`, `--accent-sky-bg` / `-text`). Dead
  `var(--defined, #hex)` fallbacks dropped. Light mode unchanged; only the
  `:root` palette definitions carry raw hex now (that is the source of truth).
- ✅ **W2 — instruments_index.html reconciled.** The shadow-token vocabulary is
  retired: `--danger-bg` / `-border` / `-text` **promoted to real `:root`
  tokens** (exact values — a soft inline-error treatment distinct from the hard
  `.danger-banner`); `--surface-muted` / `--color-muted` / `--border-muted` /
  `--bg` / `--bg-muted`/`--text-*` fallbacks rewritten to canonical tokens; the
  Jinja cycling palette moved to **6 new `--instrument-tint-1..6` tokens** so
  the inline `style="background: …"` themes. Zero raw color-hex left.
- ✅ **W3 — minor templates.** `sys_admin_session_audit_log.html` (2 shadow
  fallbacks → `--accent-blue-dark` / `--text-secondary`) and
  `session_observers.html` (2 → `--text-muted`) reconciled.
  `reviewer/results.html` and `session_extract_data.html` were **already
  clean** — their apparent hexes in the sweep were HTML numeric entities
  (`&#…;`), not colours.
- **Tokenise phase complete.** Palette now = **47 `:root` tokens** (28 original
  + 19 new). The only remaining raw-hex light-island is **`error.html`**
  (7 hexes, standalone doc) — that is W7. Every base-extending template themes
  off tokens.
- ✅ **W4 — dark palette in base.html.** The harness-tuned dark values (sign-off
  2026-08-21) ported into `:root[data-theme="dark"]` (47 tokens), with
  `color-scheme: light` / `dark` on the two states and `background:
  var(--bg-page)` on `html` + `body`. `.session-nav-grid`'s local
  `--tab-marker-color` now derives from `--accent-blue-marker` so the nav marker
  themes (a component-scoped property the `:root` block couldn't reach). Light
  unchanged.
- ✅ **W5 — no-FOUC head script.** Synchronous `<script>` before `<style>` in
  `<head>`; reads `localStorage["rrw-theme"]`, stamps `data-theme="dark"` before
  first paint (try/catch for blocked storage). `node --check` passes.
- ✅ **W6 — chrome toggle + settings card retired.** A shared
  `_partials/theme_toggle.html` two-segment pill `[☀ Light | 🌙 Dark]` in the
  `.chrome-user` of base.html's operator chrome + `reviewer/_top_bar.html`
  (which also covers `review_surface.html` via its `super()` / include). Pill
  JS reflects the current `data-theme` on load and, on click, writes
  `localStorage["rrw-theme"]` + flips `data-theme` (Light = remove the attr).
  The `/operator/settings` Display-mode card was removed and Date & time
  returns to full-width. Verified on the real settings page in a browser: click
  → `data-theme="dark"`, canvas `#0f141b`, `aria-pressed` syncs. **Dark mode is
  now live end-to-end for operators and participants.**
- ☐ W7 (error.html) / W8 (dev-slot QA) — pending. W7 is the standalone
  `error.html` (own `prefers-color-scheme` block or leave light); W8 is a
  dev-slot colour pass across representative real pages.
