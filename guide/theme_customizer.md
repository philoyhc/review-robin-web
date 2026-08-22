# Theme customizer — plan (ergonomic, seed-and-derive)

**Status: idea / not scheduled.** No commitment to build; this records the
design so it's ready to pick up. Phase 1 (below) is migration-free and
touches nothing in `app/`. Phase 2 (app consumption) needs a migration and is
deliberately out of scope here.

## The idea

Grow the theme-preview harness (`tools/theme_preview.gen.py` →
`tools/theme_preview.html`) into a **theme customizer**: pick colours / hues
for the major elements, watch the whole component gallery repaint live, and
**export the palette as JSON**. The *ergonomic* version isn't 47 colour
pickers — it's a handful of **seed** hues that **derive** the rest, with
per-token override for the stubborn cases.

## Why the harness is the right host

The app is already fully token-driven (`:root` custom properties in
`base.html`; see `spec/visual_style_rrw.md` "Light / dark mode"), so **live
editing is almost free**: setting `root.style.setProperty('--accent-blue', v)`
repaints every surface instantly. The harness already renders the whole
gallery + the 47-token swatch grid + a Light/Dark toggle — it just needs
*inputs* and an *export*.

## Scope boundary (important)

- **Phase 1 — customizer + JSON export (this plan).** Lives entirely in the
  harness. **No backend, no migration, no `app/` change.** Output is a JSON
  palette you hand-port into `base.html` (exactly the dark-mode flow). Safe to
  build any time.
- **Phase 2 — the app *consuming* a custom theme (future).** Persist named
  themes, inject them at render, governance + defaults. **This** is where the
  migration lives. Sketched at the end; not planned.

The two are cleanly separable because both produce/consume the same artifact:
a token set. Phase 1 authors it; Phase 2 (later) stores + applies it.

## The model — seed-and-derive

### Seeds (the "major elements")

~8 controls the user actually touches. Each is one colour; its family derives.

| Seed | Drives |
|---|---|
| **Neutral base** | `--bg-page`, `--bg-card`, `--bg-muted`, `--border-subtle/-default`, `--neutral-marker`, `--text-primary/-secondary/-muted` (the whole grey ramp) |
| **Blue** (primary accent) | `--accent-blue` + `-bg` / `-bg-soft` / `-bg-faint` / `-light` / `-dark` / `-marker` / `-strong` |
| **Green** (success) | `--accent-green` + `-bg` / `-marker` / `-text` / `-bg-faint` |
| **Amber** (caution / Alert) | `--accent-amber` + `-bg` / `-bg-mid` / `-dark` / `-border` |
| **Red** (destructive) | `--accent-red` + `-bg` / `-soft` / `-strong` / `-text`, and the soft-error `--danger-bg` / `-border` / `-text` |
| **Violet** | `--accent-violet-bg` / `-text` |
| **Sky** | `--accent-sky-bg` / `-text` |
| **Instrument tints** | `--instrument-tint-1..6` — either 6 hue stops rotated off a single "tint chroma/lightness" control, or left as-is |

### Fixed / structural (not seed-driven)

- `--text-on-accent` — text on filled accents; effectively white, both themes.
- `--text-on-amber` — the known exception (dark label on the light-amber Alert
  fill in dark mode). Per-token override, not derived.

### Derivation rules (per family, per mode)

Work in **OKLCH**, not HSL — perceptually even lightness/chroma steps and
predictable contrast (HSL "lighten" skews hue + contrast). From a seed at
`oklch(L C H)`:

- **base accent** = the seed.
- **-bg** (tint surface): **light** → high L, low C, same H; **dark** → low L,
  low-moderate C, same H (a dark solid, not a wash).
- **-bg-soft / -bg-faint**: successively closer to the page background.
- **-light**: +ΔL. **-dark / -strong / -text** (text on the tint): −ΔL in
  light; in **dark** these *invert* to +ΔL (light text on dark surface).
- **-marker**: a light, low-chroma tint for underlines / left-borders.

The neutral ramp derives from the neutral seed as a lightness scale (page →
card → muted → borders → muted-text → secondary → primary), with a small,
tunable chroma so greys can lean warm or cool.

Each family is one function `derive(seed, mode) -> {token: value}`; the app's
current light + dark values are the reference output to match at the defaults.

### Per-token override

Any derived token can be pinned to a manual value (the swatch grid stays fully
editable — "advanced mode"). Overrides win over derivation and are recorded
separately so re-deriving from a changed seed keeps them.

## Two themes at once

Light and Dark are **separate palettes**; `derive()` takes a `mode`. The editor
edits one mode at a time (the Light/Dark toggle switches which mode you edit
*and* preview). Model: `{ light: {...}, dark: {...} }` for both seeds and the
derived tokens.

## Contrast safety

Many tokens are **bg/text pairs** — pill bg + text, `--danger-bg` + `-text`,
`--text-primary` on `--bg-page`, `--text-on-accent` on each filled accent.
Compute WCAG contrast live and show an **AA badge** (pass/fail) next to each
pair, so a custom theme can't render itself unreadable. This is the single
most valuable guardrail and worth building even in the MVP.

## Live application

On any change: recompute the affected family → `setProperty` each token on the
right scope (`:root` for light, a `[data-theme="dark"]` style block or a
second `setProperty` target for dark) → the gallery repaints. No rebuild.

## JSON export / import

Two payloads in one file:

```json
{
  "version": 1,
  "seeds":  { "light": { "blue": "oklch(...)", "neutral": "...", ... },
              "dark":  { ... } },
  "tokens": { "light": { "--accent-blue": "#2563eb", "--bg-page": "#ffffff", ... },
              "dark":  { "--accent-blue": "#4b8bf5", ... } }
}
```

- **`tokens`** is the portable artifact — a flat token map that maps **1:1 onto
  `base.html`'s `:root` / `:root[data-theme="dark"]` blocks**, so porting a
  theme into the app stays the mechanical copy we did for dark. Keep it dumb.
- **`seeds`** lets the editor round-trip (re-load and keep tuning). Import reads
  `seeds` if present (re-derive), else falls back to applying `tokens` directly.
- Export via a copyable `<textarea>` and a `download` link (works for a
  local file; the harness isn't sandboxed).

## Harness UI

- **Seed row** at the top of the toolbar: the ~8 seed swatches (colour input +
  OKLCH sliders: L / C / H), + the Light/Dark toggle (already there).
- **Advanced: the existing 47-token swatch grid** becomes editable — each chip
  gains a colour input + a "pin" (override) + an AA badge where it's half of a
  pair. Collapsible so the default view stays the seed row.
- **Export / Import** buttons + the JSON textarea.
- **Reset to app defaults** (re-lift base.html's current values).

## Implementation notes

- The harness HTML is *generated* by `tools/theme_preview.gen.py`, which already
  parses base.html's `:root` tokens (name → light value) and lifts the real
  dark block. The customizer is **new inline JS + controls emitted by the
  generator** — no app code, no new runtime deps.
- **OKLCH ↔ sRGB** conversion: inline a tiny hand-rolled converter (or emit
  `oklch()` directly and read back computed sRGB) — no external libraries in the
  harness.
- The default seeds are chosen so `derive()` reproduces the app's current
  light + dark values (a fixture test: derived defaults == base.html tokens).

## Build slices (if it ever gets scheduled)

1. **Editable grid + JSON (manual, no derivation).** Every token → colour input
   + live `setProperty`; flat `tokens` export/import; Reset. This alone is a
   useful palette authoring tool and de-risks the plumbing.
2. **Contrast badges** on the pairs (AA pass/fail). Cheap, high value.
3. **Seeds + OKLCH derivation** — the ergonomic layer: seed row → `derive()` →
   families; per-token override; `seeds` in the JSON. The real work.
4. **Polish** — presets, instrument-tint rotation control, download UX.

Slices 1–2 are the pragmatic MVP; slice 3 is the "ergonomic" ask.

## Open questions

- **Instrument tints** — 6 independent pale hues, or one chroma/lightness knob
  rotated across 6 stops? Rotation is more ergonomic but less exact.
- **Neutral warmth** — expose a chroma/hue control on the grey ramp, or keep
  greys neutral?
- **How many seeds** — is 8 right, or fold violet/sky into "extra accents"
  behind Advanced?
- **Derivation fidelity** — the current palette wasn't built by a formula, so
  `derive(default_seed)` won't hit every token exactly; decide the tolerance
  (treat mismatches as overrides, or re-tune the app values to be formula-clean).

## Phase 2 — app consumption (future, needs a migration)

Out of scope, recorded for continuity. To let *end-users* (not just us) choose
palettes:

- **Storage** — a `themes` table (or JSON column): `{name, tokens_light,
  tokens_dark, owner/org, is_default}`. The migration lives here.
- **Apply** — inject the stored token map as an inline `:root{…}` /
  `:root[data-theme="dark"]{…}` block at render (or a `data-theme="<slug>"`
  variant), gated like `rrw-theme` today.
- **Governance** — who authors (operator / sys-admin / org-level), a default,
  per-session override, and an **enforced AA gate** on save so a shared theme
  can't be unreadable.

Until then, the Phase 1 JSON is authored in the harness and hand-ported into
`base.html`, exactly as the dark palette was.
