# Theme customizer — plan

**Status:** **First — ✅ v1 shipped 2026-09-04** as **Segment 19C Item 5**
(`guide/segment_19C_refinements.md`, PRs #2065–#2083): a three-part,
data-driven `tools/theme_customizer.html` designer — Part A previews the real
gallery, Part B edits tokens (seeds / primitives / contrast / semantic remaps),
Part C click-to-reflect + primitive-picker editing, with Save/Undo/Revert and
Export/Import JSON. **Stretch** (operator in-app tweaker) is deferred pending
pilot feedback (`guide/deferred_consolidated.md` Part A → "Operator theming").
This doc is the full design for both. **Two plans that share one editor core**,
sequenced so the second builds cleanly on the first. Both are **migration-free**
(no database); a DB-backed "persistent / shared themes" version is a further
future neither plan does.

> **Portability goal (author directive, logged against 19C Items 4–5).** The
> customizer should be built **app-agnostic** — reusable by other apps of the
> same look and feel: parameterised by the target token file, with friendly
> labels / seed families / zone-clusters read as **data** (ideally from the
> token file) rather than baked to Review Robin, and JSON as the portable
> interchange. This dovetails with the two-tier semantic-token migration
> (`guide/archive/semantic_tokens.md` §"Reusability across apps"): the reusable
> kernel is {primitives + portable-core semantics} + {this app-agnostic
> customizer}. Realised in that plan's tooling slice.

## The two plans at a glance

- **First — developer theme *designer*** (in the `tools/` harness). Design the
  light + dark palettes visually; **export JSON**; a coding agent ports that
  JSON into `base.html`'s token blocks. For someone with repo/file access.
  Migration-free; touches nothing in `app/`.
- **Stretch — operator theme *tweaker*** (in the app). An operator tweaks the
  light + dark themes for **their own view** and **saves browser-local**
  (localStorage), applied at runtime. **No database, no migration** — per
  browser, exactly like the existing light/dark choice; participants
  unaffected.

**They compose on purpose.** Both use the same **editor core** — the token
model, the live-preview controls, the seed-and-derive logic, and the JSON
contract. *First* wraps that core in the static harness; *Stretch* drops the
**same** core into an app page and adds localStorage persistence + a
runtime-apply script. Build the core once; Stretch is core + a thin app shell.

## Why it's cheap either way

The app is fully token-driven (`:root` custom properties in `base.html`; see
`spec/visual_style_rrw.md` "Light / dark mode"), so **live editing is almost
free**: `root.style.setProperty('--accent-blue', v)` repaints every surface
instantly. The harness already renders the whole gallery + the 47-token swatch
grid + a Light/Dark toggle — the editor is mostly *inputs* + *serialization* on
top of what exists.

---

## The shared editor core (build once, both reuse)

Keep it **framework-free vanilla JS + markup + one JSON schema**, so it embeds
unchanged in a generated static file (First) *or* a Jinja template (Stretch).
No build step, no runtime deps. The core is four things:

1. **Token model** — `{ light: {token→value}, dark: {token→value} }` over the
   47 `:root` tokens. First seeds it from `base.html` (baked at generate time
   or a file-picker, below); Stretch opens on the current applied values (its
   last-saved, if any) and reads `base.html`'s declared `:root` via the CSSOM
   for *defaults* (see State & retrieval). Same shape either way.
2. **Controls + live preview** — per-token colour inputs and/or seed sliders;
   on change → apply (`setProperty` for the harness; an injected `<style>` for
   the app) → the gallery / page repaints.
3. **Seed-and-derive + contrast** — the ergonomic layer (below).
4. **JSON serialize / parse** — the identical contract (below). First *exports*
   it for a coding agent; Stretch *stores* it in localStorage.

### The model — seed-and-derive

The *ergonomic* version isn't 47 pickers — a handful of **seed** hues drive the
families, with per-token override for the stubborn cases.

**Seeds (the "major elements")** — ~8 controls; each is one colour, its family
derives:

| Seed | Drives |
|---|---|
| **Neutral base** | `--bg-page`, `--bg-card`, `--bg-muted`, `--border-subtle/-default`, `--neutral-marker`, `--text-primary/-secondary/-muted` (the grey ramp) |
| **Blue** (primary) | `--accent-blue` + `-bg` / `-bg-soft` / `-bg-faint` / `-light` / `-dark` / `-marker` / `-strong` |
| **Green** (success) | `--accent-green` + `-bg` / `-marker` / `-text` / `-bg-faint` |
| **Amber** (caution / Alert) | `--accent-amber` + `-bg` / `-bg-mid` / `-dark` / `-border` |
| **Red** (destructive) | `--accent-red` + `-bg` / `-soft` / `-strong` / `-text`, and the soft-error `--danger-bg` / `-border` / `-text` |
| **Violet** | `--accent-violet-bg` / `-text` |
| **Sky** | `--accent-sky-bg` / `-text` |
| **Instrument tints** | `--instrument-tint-1..6` — six independent hue controls |

**Fixed / structural (not seed-driven):** `--text-on-accent` (≈white, both
themes) and `--text-on-amber` (the dark-label-on-light-amber exception) — manual
override, not derived.

**Derivation (per family, per mode)** — work in **OKLCH**, not HSL
(perceptually even lightness/chroma; HSL "lighten" skews hue + contrast). From a
seed `oklch(L C H)`: **base** = seed; **-bg** = high-L/low-C (light) or
low-L/low-C dark solid (dark); **-bg-soft/-faint** step toward the page bg;
**-light** = +ΔL; **-dark/-strong/-text** = −ΔL in light, *inverted* to +ΔL in
dark (light text on dark surface); **-marker** = light low-chroma tint. The
neutral ramp is a lightness scale off the neutral seed; greys stay neutral (no
warmth control). Each family is one
`derive(seed, mode) -> {token: value}`; the app's current values are the
reference the defaults must reproduce (fixture: `derive(defaults) == base.html`).

**Per-token override** — any derived token can be pinned manually (the full grid
stays editable — "advanced"); overrides win over derivation and survive
re-deriving from a changed seed.

### Two themes at once

Light and Dark are **separate palettes**; `derive()` takes a `mode`. Edit one at
a time — the Light/Dark toggle switches which mode you edit *and* preview.

### Contrast safety

Many tokens are **bg/text pairs** (pill bg + text, `--danger-bg`+`-text`,
`--text-primary` on `--bg-page`, `--text-on-accent` on each filled accent).
Compute WCAG contrast live and show an **AA badge** per pair, so a theme can't
render itself unreadable. The single most valuable guardrail — build it early,
and make it a **hard gate** in Stretch (an operator isn't a designer).

### JSON contract (identical for both plans)

```json
{
  "version": 1,
  "seeds":  { "light": { "blue": "oklch(...)", "neutral": "...", ... },
              "dark":  { ... } },
  "tokens": { "light": { "--accent-blue": "#2563eb", "--bg-page": "#ffffff", ... },
              "dark":  { "--accent-blue": "#4b8bf5", ... } }
}
```

- **`tokens`** is the portable artifact — a flat map that lands **1:1 onto
  `base.html`'s `:root` / `:root[data-theme="dark"]` blocks** (First → base.html)
  *and* onto a runtime override `<style>` (Stretch → localStorage). Keep it dumb.
- **`seeds`** lets the editor round-trip (re-load + keep tuning). Import reads
  `seeds` if present (re-derive), else applies `tokens` directly.

### State & retrieval — defaults / saved / working

Three retrievable states. **Both plans must always be able to get back to the
baked-in defaults**, plus a plan-specific "saved" slot:

- **Defaults (the app's actual palette).** Both plans expose a **"Load defaults
  / Reset to actual"** control — the always-available escape hatch, so you never
  lose the real palette.
  - *First* reads them from `base.html` (baked at generate time, or re-read live
    via the file-picker).
  - *Stretch* reads them from **`base.html`'s own `:root` rule via the CSSOM**
    (`document.styleSheets`), **not** `getComputedStyle` — because when a custom
    theme is applied the computed value *is* the custom one, but the declared
    base rule is still the true default.
- **Saved.**
  - *First* keeps a **library of named saves** in the harness's own
    `localStorage` (e.g. `rrw-theme-designs`): **Save as…** (name it); a picker
    **lists past saves to load**; delete / rename. (Plus Export / Import JSON for
    the coding-agent handoff and moving between machines.)
  - *Stretch* keeps a **single last-saved** in `localStorage["rrw-theme-custom"]`
    (the applied theme). Save overwrites it; **"Revert to last saved"** discards
    the in-progress edits and reloads it — the abandon-an-edit path.
- **Working (the in-progress edit)** — in memory; Save promotes it to the
  saved slot(s); Reset/Revert discards it.

Control set: **both** get *Load defaults*; **First** adds *Save as… / Load save
/ Delete* (library) + Export/Import; **Stretch** adds *Save* + *Revert to last
saved* (+ optional Export/Import).

---

## Plan A — First: developer theme designer

**Goal:** design light + dark visually; hand the result off as JSON that a
coding agent turns into template code.

- **Host:** a new `tools/theme_customizer.gen.py` → `tools/theme_customizer.html`
  (keeps the read-only `theme_preview` simple); factor the shared `base.html`
  lift + gallery into `tools/_harness_common.py` that both generators import.
  Developer, file access.
- **The three controls (Slice-1 surface):**
  1. **Load from app / "Refresh to actual".** The generator bakes `base.html`'s
     real light *and* dark token values as the baseline. In-page, a
     **file-picker** ("Re-read from base.html…", via the File API) lets the dev
     load the *current* on-disk `base.html` live — no server — so the baseline
     never goes silently stale. (Regenerating the script is the other way to
     re-read; a static page can't read the file on its own.)
  2. **Edit light and dark separately** — the toggle switches which theme you
     edit/preview; the two palettes are independent.
  3. **Save (both themes).** Two flavours: **Save as…** to the harness's
     named-save library (localStorage — retrieve past saves from the picker),
     and **Export JSON** to a single downloaded file (both themes; the handoff
     artifact). Plus **Load defaults** (above) always available.
- **The handoff loop:** export `tokens` → hand a coding agent *"apply this theme
  JSON to `base.html`"* → the agent rewrites the `:root` / `:root[data-theme=
  "dark"]` blocks (token names map 1:1 — mechanical, exactly the dark-mode
  port). This formalises the loop we already ran by hand for dark.
- **Build slices:** (1) editable grid + the three controls + JSON;
  (2) contrast badges; (3) seeds + OKLCH derivation; (4) polish (presets,
  save-library UX).

---

## Plan B — Stretch: operator theme tweaker (browser-local)

**Goal:** let an operator tweak the light + dark themes for **their own view**
and keep the tweak in their browser. "Tweak," not "publish."

- **Reuses** the shared editor core — **seeds only** (a few hues) for a
  light-touch "tweak" UX; the full per-token grid / Advanced is First-only
  (developer).
- **Adds (a thin app shell over the core):**
  1. **A Display-mode section on `/operator/settings`** hosting the editor
     (settled — not a dedicated route). Server-rendered; the editor JS is the
     shared core, unchanged.
  2. **Browser-local persistence** — Save writes the JSON to
     `localStorage["rrw-theme-custom"]` (sibling of the existing `rrw-theme`
     light/dark key).
  3. **Runtime-apply** — a small synchronous script in `base.html`, placed
     **after `base.html`'s own `<style>` block** (but still in `<head>`, before
     `</head>` — so it runs before first paint *and* its override wins the
     cascade). It reads `rrw-theme-custom` and, if present, injects
     `<style id="rrw-custom-theme">:root{ …light overrides… }
     :root[data-theme="dark"]{ …dark overrides… }</style>`. The override only
     wins because it comes **after** the base `:root` blocks (equal specificity
     → later wins) — placing it beside the no-FOUC script, which sits *before*
     the `<style>`, would let base.html overwrite it. It overrides only the
     tweaked tokens; the light/dark toggle keeps working because the overrides
     live in both guarded blocks.
  4. **Revert to last saved** — discard in-progress edits and reload
     `rrw-theme-custom` (abandon an edit). **Reset to defaults** is separate —
     it clears the key and returns to `base.html`'s palette.
  5. **Optional export / import** — the same JSON, to carry a tweak between
     browsers (there's no server copy).
- **Deliberately NOT:** no database, no migration, no cross-user / session / org
  scope, no governance. It's **per-browser**, precisely like the light/dark
  `rrw-theme` choice — a personal display preference. Other people's browsers
  (including participants') are untouched.
- **Contrast is a hard gate here** — Save is blocked (or warns hard) on any AA
  failure, since the editor is in non-designer hands.
- **Build slices** (scaffold-first per `AGENTS.md` → "Consequential UI lands
  scaffold-first"): (1) **scaffold** the Display-mode section on
  `/operator/settings` — real layout + copy, seed controls present but **inert**
  (no reading, no preview, no save); (2) wire the editor — extract the First
  core into a reusable module, host it in that section, read live tokens + live
  preview; (3) localStorage Save + the runtime-apply script + Reset; (4) the AA
  save-gate; (5) export/import + Revert-to-last-saved + seed polish.

### How Stretch rides on First (the reuse contract)

- **Same core module** — framework-free vanilla JS + markup; First emits it into
  the generated harness, Stretch `{% include %}`s the same file in a template.
  Keep it DOM-portable, no build step.
- **Same token model** — First reads `base.html` (bake / file-picker); Stretch
  reads live `getComputedStyle(:root)`. Both produce `{light, dark}`.
- **Same JSON** — First's export is a design handoff; Stretch's is a localStorage
  payload (+ optional export). One schema.
- So **Stretch = First's core + { app page, localStorage save, runtime-apply,
  reset, AA gate }** — no rework of the editor itself.

---

## Decisions (settled 2026-08-22)

- **Editor host in the app (Stretch)** — a **Display-mode section on
  `/operator/settings`** (not a dedicated route).
- **Tweak depth (Stretch)** — **seeds only.** The full per-token grid /
  Advanced mode stays First-only (developer). Simplest + safest in operator
  hands.
- **Instrument tints** — **six independent hue controls** (not one rotated
  knob).
- **Neutral warmth** — **greys stay neutral;** no warmth/chroma control on the
  grey ramp.
- **Derivation fidelity** — **re-tune the app's current token values to be
  formula-clean:** adjust `base.html` so `derive(default_seed)` reproduces every
  token exactly, with no leftover per-token overrides in the *defaults*. Note
  this is a **deliberate, small visual change to today's shipped light/dark
  palette** — author it in the harness and dev-slot-QA it like any palette
  change. Cleanest as a **self-contained pre-step**: land the formula-clean
  defaults first, then build the customizer on a clean base.
- **Flash-free apply (Stretch)** — **confirmed:** the runtime `<style>`
  injection is a synchronous script in `<head>` **placed after `base.html`'s
  `<style>`** (so it both runs before first paint *and* wins the cascade — see
  Plan B, Runtime-apply) — a custom theme never flashes the
  default.

## Further future (neither plan) — persistent / shared themes

Out of scope for both plans, recorded for continuity. Both plans keep themes
**local** (First → source code via the agent; Stretch → the operator's browser).
The moment you want a theme **shared across users, persisted server-side, or
pushed onto participants**, you need the database:

- **Storage** — a `themes` table (or JSON column): `{name, tokens_light,
  tokens_dark, scope/owner, is_default}`. The migration lives here.
- **Scope** — per-operator / per-org / per-session (the pivotal decision;
  per-session reaches participant surfaces).
- **Apply** — inject the stored token map at render (a `data-theme="<slug>"`
  variant or an inline override block), gated like `rrw-theme`.
- **Governance** — who authors, a default, per-session override, and the
  enforced AA gate on save.

That's a segment-sized feature (the migration is the easy part; scope + render
path + governance are the work) — explicitly beyond First and Stretch.
