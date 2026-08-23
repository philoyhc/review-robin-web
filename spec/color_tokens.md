# Colour tokens — Review Robin Web App

The complete inventory of the app's colour palette. The **authoritative
source is `app/web/templates/base.html`'s `:root` block** — this document
is the human-readable catalogue of what lives there: every colour token,
its friendly name, its light and dark value, and where it is used.

The theming discipline (from `spec/visual_style_rrw.md`): *use tokens,
never raw hex.* Light is the bare `:root { … }`; Dark is
`:root[data-theme="dark"] { … }` (plus `color-scheme: dark`), toggled by
`data-theme` on `<html>`. Any surface built from tokens themes for free.

Read alongside:

- `spec/visual_style_general.md` — the portable design system: the semantic
  accent definitions (blue / green / amber / red) these tokens instantiate.
- `spec/visual_style_rrw.md` — the RRW accent assignments (blue = Setup,
  green = Operations, amber = locked/warning, red = destructive), lifecycle
  colours, and the light/dark mechanics.
- `spec/ui_elements.md` — the `.btn` roles and other element treatments that
  consume these tokens.

**Tooling.** `tools/theme_customizer.gen.py` (designer) and
`tools/theme_preview.gen.py` (read-only preview) both render this palette;
the friendly names in this document come from `LABELS` in
`tools/_harness_common.py`. See `guide/theme_customizer.md`.

**Maintenance.** When adding, renaming, or removing a colour token: update
`base.html` (both the `:root` and the `:root[data-theme="dark"]` blocks),
the `LABELS` map in `tools/_harness_common.py`, and this document together.

The palette is **47 colour tokens** plus **16 non-colour scale tokens**
(type / spacing / radius), all defined in the one `:root` block.

---

## Neutral surfaces & text (11)

| Token | Friendly name | Light | Dark | Used by |
|---|---|---|---|---|
| `--bg-page` | Page background | `#ffffff` | `#0f141b` | `html` / `body` / page canvas; card fill; outline-button fill (Secondary / Destructive / Amber); text input background |
| `--bg-card` | Card background | `#ffffff` | `#1a212e` | Card surfaces; active nav-tab; session-nav cards; row labels; status row |
| `--bg-muted` | Muted background | `#f5f5f7` | `#232c3b` | Tab-strip backgrounds, table header + row hover, code blocks, handle / tag-mode pills, Secondary-button hover, sort-button hover |
| `--border-subtle` | Subtle border | `#e5e7eb` | `#2b3547` | Hairlines — chrome bottom border, banners, session-nav cards, row dividers, status-row top |
| `--border-default` | Default border | `#d1d5db` | `#3a465c` | Standard borders — cards, inputs, signout button, section dividers |
| `--neutral-marker` | Neutral marker | `#d1d5db` | `#3a465c` | Inactive active-underline marker on the Setup / Page tab strips |
| `--text-primary` | Primary text | `#111827` | `#e6eaf2` | Body text, headings, Secondary-button label, active nav-tab, help-card |
| `--text-secondary` | Secondary text | `#6b7280` | `#a9b4c6` | Page subtitles, `.muted`/help text, chrome identity, Secondary-button border |
| `--text-muted` | Muted text | `#9ca3af` | `#6f7b8e` | De-emphasised — breadcrumb separator, disabled nav-tabs, canonical field labels |
| `--text-on-accent` | Text on accent | `#ffffff` | `#ffffff` | Label on filled accent — Primary / CTA / alert-solid buttons, selected tag-chip, skip-link, theme-toggle |
| `--text-on-amber` | Text on amber | `#ffffff` | `#111827` | Label on filled amber — Alert (`.btn.danger-solid`) button |

---

## Blue — Setup identity, links, primary (8)

| Token | Friendly name | Light | Dark | Used by |
|---|---|---|---|---|
| `--accent-blue` | Blue / link | `#2563eb` | `#4b8bf5` | Links; Primary / CTA button fill + border; input focus ring (border + outline); active states; card accents (next-action, editing, acknowledge, severity, selected data-shape); selected tag-chip; back-link |
| `--accent-blue-bg` | Blue background | `#dbeafe` | `#16324f` | Info pill + banner background, count pill, reviewer / validated pills, focus-ring halo |
| `--accent-blue-bg-soft` | Blue background (soft) | `#eff6ff` | `#12283f` | Resolved config value, session-home anchor, active severity-chip |
| `--accent-blue-bg-faint` | Blue background (faint) | `#fafcff` | `#0e1c2c` | Selected data-shape card, acknowledge card, session-home-anchor hover |
| `--accent-blue-light` | Blue (light) | `#3b82f6` | `#60a5fa` | Filled-button hover fill (Primary / CTA / alert-solid) |
| `--accent-blue-dark` | Blue (dark) | `#1d4ed8` | `#93c5fd` | Reviewer-role pill text, sort-button focus outline |
| `--accent-blue-marker` | Blue marker | `#93c5fd` | `#3b82f6` | Setup tab active-underline marker + session-home-anchor marker |
| `--accent-blue-strong` | Blue (strong) | `#1e40af` | `#93c5fd` | Active nav-tab text, info-pill text |

---

## Green — Operations identity, success (5)

| Token | Friendly name | Light | Dark | Used by |
|---|---|---|---|---|
| `--accent-green` | Green | `#059669` | `#34d399` | Success-banner border; ready / reviewee / success pills; complete status icon; green next-action signal |
| `--accent-green-bg` | Green background | `#d1fae5` | `#0f3d2e` | Success banner + success / ready / reviewee pill backgrounds |
| `--accent-green-bg-faint` | Green background (faint) | `#f0fdf4` | `#0c2419` | Operations tab-strip background |
| `--accent-green-marker` | Green marker | `#a7f3d0` | `#065f46` | Operations tab active-underline marker |
| `--accent-green-text` | Green text | `#166534` | `#6ee7b7` | Success pill text |

---

## Amber — warning, lock, Alert (5)

| Token | Friendly name | Light | Dark | Used by |
|---|---|---|---|---|
| `--accent-amber` | Amber | `#d97706` | `#fbbf24` | Warning-banner border; Amber-outline & alert-solid button; danger-solid hover; missing-card border; amber signal icon |
| `--accent-amber-bg` | Amber background | `#fef3c7` | `#3a2c0a` | Warning surfaces — danger-zone & lock cards, warning banner / pill, draft / observer / empty pills, missing card |
| `--accent-amber-bg-mid` | Amber background (mid) | `#fde68a` | `#4a3a10` | Amber-outline button hover fill |
| `--accent-amber-dark` | Amber (dark) | `#92400e` | `#fcd34d` | The framing "brown" — Alert (`.danger-solid`) fill; Amber-outline text + border; danger-zone & lock border + h2; warning / draft / observer pill text; incomplete status icon |
| `--accent-amber-border` | Amber border | `#f59e0b` | `#b45309` | Legacy `.warning-banner` border; pending new-model row shadow |

---

## Red — destructive, errors (5) + Danger inline-error (3)

| Token | Friendly name | Light | Dark | Used by |
|---|---|---|---|---|
| `--accent-red` | Red | `#dc2626` | `#f87171` | Error-banner border; Destructive button text + border; form-error text; expired pill; danger icon-button; error signal icon |
| `--accent-red-bg` | Red background | `#fee2e2` | `#3d1a1a` | Error banner + Destructive hover fill; error / expired pills; danger-banner background |
| `--accent-red-soft` | Red (soft) | `#ef4444` | `#ef4444` | **Defined, no current consumer** — reserved (see Notes) |
| `--accent-red-strong` | Red (strong) | `#b91c1c` | `#f87171` | Legacy `.btn.danger-solid` fill / border; danger-banner border |
| `--accent-red-text` | Red text | `#991b1b` | `#fca5a5` | Error pill text; danger-banner text |
| `--danger-bg` | Danger background | `#fdecea` | `#3d1a1a` | Instruments save-error banner background † |
| `--danger-border` | Danger border | `#f2b8b5` | `#7f2a2a` | Instruments save-error banner border † |
| `--danger-text` | Danger text | `#8a1c14` | `#fca5a5` | Instruments save-error banner text † |

† The `--danger-*` trio is consumed by an inline `<style>` block in
`app/web/templates/operator/instruments_index.html` (the soft inline
save-error banner), not by `base.html`'s stylesheet.

---

## Violet — super pill (2)

| Token | Friendly name | Light | Dark | Used by |
|---|---|---|---|---|
| `--accent-violet-bg` | Violet background | `#ede9fe` | `#2e2250` | Super pill background |
| `--accent-violet-text` | Violet text | `#5b21b6` | `#c4b5fd` | Super pill text |

---

## Sky — config values (2)

| Token | Friendly name | Light | Dark | Used by |
|---|---|---|---|---|
| `--accent-sky-bg` | Sky background | `#e0f2fe` | `#0c2f42` | `.config-value` chip background |
| `--accent-sky-text` | Sky text | `#075985` | `#7dd3fc` | `.config-value` chip text |

---

## Instrument card tints (6)

Per-instrument card background tints, cycled across instruments via the
`instrument_palette` list in
`app/web/templates/operator/instruments_index.html` (not referenced by
`base.html`'s stylesheet).

| Token | Friendly name | Light | Dark |
|---|---|---|---|
| `--instrument-tint-1` | Instrument tint 1 | `#f0f9ff` | `#0e1a24` |
| `--instrument-tint-2` | Instrument tint 2 | `#ecfdf5` | `#0e1f18` |
| `--instrument-tint-3` | Instrument tint 3 | `#f5f3ff` | `#191527` |
| `--instrument-tint-4` | Instrument tint 4 | `#fff7ed` | `#241a10` |
| `--instrument-tint-5` | Instrument tint 5 | `#fff1f2` | `#241318` |
| `--instrument-tint-6` | Instrument tint 6 | `#fffbeb` | `#221d0e` |

---

## Non-colour scale tokens (16)

Defined in the same `:root` block; **not** redefined per theme (they are
dimensions, not colours).

**Type scale** — `--fs-tiny` `0.75rem` · `--fs-small` `0.875rem` ·
`--fs-body` `1rem` · `--fs-h2` `1.125rem` · `--fs-h1` `1.5rem`.

**Spacing scale** — `--space-1` `4px` · `--space-2` `8px` · `--space-3`
`12px` · `--space-4` `16px` · `--space-6` `24px` · `--space-8` `32px` ·
`--space-12` `48px` · `--space-16` `64px`.

**Radius** — `--radius-button` `6px` · `--radius-card` `8px` ·
`--radius-pill` `9999px`.

---

## Notes

- **`--accent-red-soft` has no consumer.** It is defined in both `:root`
  blocks and documented in `spec/visual_style_general.md` ("softer red for
  surfaces that want to flag destructive context without alarming"), but no
  rule in `base.html` or any template references it. Treat it as reserved.
- **Consumed outside `base.html`.** The `--danger-*` trio and the six
  `--instrument-tint-*` tokens are used only via inline template styles
  (both in `operator/instruments_index.html`), so they don't appear in the
  main stylesheet's rules.
- **Dark-mode neutrals invert while accents stay hued.** In dark,
  `--text-on-accent` remains `#ffffff` (labels on the still-blue Primary
  fill) but `--text-on-amber` flips to near-black (`#111827`) for legibility
  on the lighter dark-mode amber.
