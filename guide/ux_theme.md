# UX theming sweep — light / dark mode (Segment 19C Item 2)

**Purpose.** Working sweep + punch-list for wiring an operator-facing
**light / dark Display mode**. Records what is already themeable, what is
not, and the exact code that needs work before a dark palette can ship. Not
a spec — the shipped behaviour goes to `spec/visual_style_rrw.md` /
`spec/operator_ui_concept.md` when it lands.

## Decision (settled)

- **Purely browser-local.** The theme choice lives in `localStorage`
  (`rrw-theme` ∈ `{system, light, dark}`) and is applied via a `data-theme`
  attribute on `<html>`. **No backend** — no route, service, model,
  migration, or template-context change. Covers operators *and* participants
  uniformly, and (with a synchronous head script) is flash-free without any
  server involvement.
- **`system`** = no `data-theme`; `@media (prefers-color-scheme: dark)`
  decides. **`light` / `dark`** = stamp `data-theme` explicitly, which wins
  over the media query.
- **UX placement is deliberately open** (chrome vs. `/operator/settings`
  card) — see "Open — UX placement". The *code* work below is
  placement-agnostic except for the toggle control itself (W7).

## Mechanism (all client-side)

1. **Dark palette** — dark values for the `base.html` colour tokens under
   three guarded blocks: `:root` keeps the light palette; redefine under
   `@media (prefers-color-scheme: dark)` guarded as
   `:root:not([data-theme="light"])`, and again under
   `:root[data-theme="dark"]` so an explicit toggle wins both directions.
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
| **W4** | **Dark palette** — dark values for the full token set under the three guarded blocks. | `base.html` | **Needs dev-slot visual QA** — colour correctness across cards / pills / banners / tables / danger zones can't be verified by the test suite. Any raw-hex site left after W1–W3 shows as a light island. |
| **W5** | **No-FOUC head script** — synchronous `<script>` at the top of `<head>`. | `base.html` | Small; `node --check` in tests. |
| **W6** | **Toggle control + JS** — enable the placeholder buttons (or the chrome control), wire `localStorage` + `data-theme` + `aria-pressed`; `system` reads `prefers-color-scheme` for its live state. | placement TBD (see below) + inline JS | Small; the only placement-dependent piece. |
| **W7** | **error.html** dark handling (own `prefers-color-scheme` block) or leave light. | `error.html` | Standalone doc; lowest priority. |
| **W8** | Verify: `node --check` on the new inline JS; dev-slot visual QA on representative pages (a dark card, a pill row, a banner, a table, the Danger Zone, the instruments page). | tests + dev slot | The test suite can't see colour. |

## Sequencing (the Item 2 ladder)

1. **Tokenise** — W1 + W2 + W3 (value-preserving; light mode unchanged;
   independently reviewable and safe).
2. **Dark palette + no-FOUC** — W4 + W5 (System-follow works after this,
   before any toggle; **dev-slot QA**).
3. **Wire the toggle** — W6 (+ W7 mop-up).

## Open — UX placement (set aside for now)

Chrome (top-right, on every page — reaches operators *and* participants) vs.
the `/operator/settings` Display mode card (operator-only, already
scaffolded). The code work above is identical either way except W6's host
element. To settle later.

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
- ☐ W4 (dark palette) / W5 (no-FOUC script) / W6 (toggle) / W7 (error.html) /
  W8 (verify) — not started.
