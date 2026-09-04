# Colour tokens — Review Robin Web App

The app's colour system is **two-tier**, defined in `app/web/templates/base.html`'s
`:root` blocks. **Tier 1 primitives** hold the raw palette; **Tier 2 semantic**
tokens name every role and are the *only* thing components and templates consume.
The former flat colour-named tokens (`--accent-blue`, `--bg-page`, …) are fully
retired. This document is the catalogue; the design + rationale live in
`guide/archive/semantic_tokens.md`.

Read alongside `spec/visual_style_rrw.md` (accent assignments, light/dark),
`spec/visual_style_general.md` (design system), `spec/ui_elements.md` (elements).

**Maintenance.** Edit tokens in `base.html` (both `:root` blocks); keep the
`tools/` harness `LABELS` and this catalogue in sync. Rules of the model
(independent slots; marked `@coupled` for deliberate coupling; dark `:root`
remaps semantics onto the one primitive palette) are in `guide/archive/semantic_tokens.md`.

**79 primitives · 103 semantic tokens · 16 non-colour scale tokens.**

---

## Tier 1 — primitives (descriptive, theme-agnostic)

| Primitive | Value |
|---|---|
| `--white` | `#ffffff` |
| `--paper` | `#e6eaf2` |
| `--ink-abyss` | `#0f141b` |
| `--ink` | `#111827` |
| `--ink-deep` | `#1a212e` |
| `--ink-muted` | `#232c3b` |
| `--slate-deeper` | `#2b3547` |
| `--slate-deep` | `#3a465c` |
| `--slate` | `#6b7280` |
| `--slate-dim` | `#6f7b8e` |
| `--slate-pale` | `#a9b4c6` |
| `--gray` | `#9ca3af` |
| `--gray-soft` | `#d1d5db` |
| `--gray-mist` | `#e5e7eb` |
| `--gray-wash` | `#f5f5f7` |
| `--blue-abyss-faint` | `#0e1c2c` |
| `--blue-abyss-soft` | `#12283f` |
| `--blue-abyss` | `#16324f` |
| `--blue-deep` | `#1d4ed8` |
| `--blue-deeper` | `#1e40af` |
| `--blue-strong` | `#2563eb` |
| `--blue-bright` | `#3b82f6` |
| `--blue-glow` | `#4b8bf5` |
| `--blue-glow-soft` | `#60a5fa` |
| `--blue-soft` | `#93c5fd` |
| `--blue-pale` | `#dbeafe` |
| `--blue-wash` | `#eff6ff` |
| `--blue-mist` | `#fafcff` |
| `--sky-deep` | `#075985` |
| `--sky-abyss` | `#0c2f42` |
| `--sky-soft` | `#7dd3fc` |
| `--sky-pale` | `#e0f2fe` |
| `--green-strong` | `#059669` |
| `--green-abyss` | `#065f46` |
| `--green-abyss-faint` | `#0c2419` |
| `--green-abyss-mid` | `#0f3d2e` |
| `--green-deep` | `#166534` |
| `--green-bright` | `#34d399` |
| `--green-glow` | `#6ee7b7` |
| `--green-soft` | `#a7f3d0` |
| `--green-pale` | `#d1fae5` |
| `--green-wash` | `#f0fdf4` |
| `--amber-abyss` | `#3a2c0a` |
| `--amber-abyss-mid` | `#4a3a10` |
| `--amber-deep` | `#92400e` |
| `--amber-deep-dk` | `#b45309` |
| `--amber-strong` | `#d97706` |
| `--amber` | `#f59e0b` |
| `--amber-bright` | `#fbbf24` |
| `--amber-glow` | `#fcd34d` |
| `--amber-soft` | `#fde68a` |
| `--amber-pale` | `#fef3c7` |
| `--red-abyss` | `#3d1a1a` |
| `--red-deep` | `#991b1b` |
| `--red-firm` | `#b91c1c` |
| `--red-strong` | `#dc2626` |
| `--red-bright` | `#f87171` |
| `--red-soft` | `#fca5a5` |
| `--red-pale` | `#fee2e2` |
| `--danger-abyss-border` | `#7f2a2a` |
| `--danger-deep` | `#8a1c14` |
| `--danger-soft` | `#f2b8b5` |
| `--danger-pale` | `#fdecea` |
| `--violet-abyss` | `#2e2250` |
| `--violet-strong` | `#5b21b6` |
| `--violet-soft` | `#c4b5fd` |
| `--violet-pale` | `#ede9fe` |
| `--tint-sky-dark` | `#0e1a24` |
| `--tint-mint-dark` | `#0e1f18` |
| `--tint-lavender-dark` | `#191527` |
| `--tint-cream-dark` | `#221d0e` |
| `--tint-rose-dark` | `#241318` |
| `--tint-peach-dark` | `#241a10` |
| `--tint-mint` | `#ecfdf5` |
| `--tint-sky` | `#f0f9ff` |
| `--tint-lavender` | `#f5f3ff` |
| `--tint-rose` | `#fff1f2` |
| `--tint-peach` | `#fff7ed` |
| `--tint-cream` | `#fffbeb` |

---

## Tier 2 — semantic tokens, by cluster

Each row: the token, the primitive it maps to in **light** / **dark**, and the
resolved hex. `[P]` portable core · `[A]` app-specific.

### Surfaces [P] (tints [A])

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--surface-page` | `--white` | `--ink-abyss` | `#ffffff` | `#0f141b` |
| `--surface-card` | `--white` | `--ink-deep` | `#ffffff` | `#1a212e` |
| `--surface-muted` | `--gray-wash` | `--ink-muted` | `#f5f5f7` | `#232c3b` |
| `--surface-tint-1` | `--tint-sky` | `--tint-sky-dark` | `#f0f9ff` | `#0e1a24` |
| `--surface-tint-2` | `--tint-mint` | `--tint-mint-dark` | `#ecfdf5` | `#0e1f18` |
| `--surface-tint-3` | `--tint-lavender` | `--tint-lavender-dark` | `#f5f3ff` | `#191527` |
| `--surface-tint-4` | `--tint-peach` | `--tint-peach-dark` | `#fff7ed` | `#241a10` |
| `--surface-tint-5` | `--tint-rose` | `--tint-rose-dark` | `#fff1f2` | `#241318` |
| `--surface-tint-6` | `--tint-cream` | `--tint-cream-dark` | `#fffbeb` | `#221d0e` |

### Text & links [P]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--text-body` | `--ink` | `--paper` | `#111827` | `#e6eaf2` |
| `--text-subtle` | `--slate` | `--slate-pale` | `#6b7280` | `#a9b4c6` |
| `--text-dim` | `--gray` | `--slate-dim` | `#9ca3af` | `#6f7b8e` |
| `--text-on-accent` | `--white` | `--white` | `#ffffff` | `#ffffff` |
| `--text-on-amber` | `--white` | `--ink` | `#ffffff` | `#111827` |
| `--text-link` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--text-link-strong` | `--blue-deep` | `--blue-soft` | `#1d4ed8` | `#93c5fd` |

### Borders & focus [P]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--border-subtle` | `--gray-mist` | `--slate-deeper` | `#e5e7eb` | `#2b3547` |
| `--border-default` | `--gray-soft` | `--slate-deep` | `#d1d5db` | `#3a465c` |
| `--focus-ring` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--focus-ring-halo` | `--blue-pale` | `--blue-abyss` | `#dbeafe` | `#16324f` |
| `--marker-neutral` | `--gray-soft` | `--slate-deep` | `#d1d5db` | `#3a465c` |

### Buttons [P]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--btn-primary-bg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--btn-primary-fg` | `--white` | `--white` | `#ffffff` | `#ffffff` |
| `--btn-primary-border` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--btn-primary-bg-hover` | `--blue-bright` | `--blue-glow-soft` | `#3b82f6` | `#60a5fa` |
| `--btn-secondary-bg` | `--white` | `--ink-abyss` | `#ffffff` | `#0f141b` |
| `--btn-secondary-fg` | `--ink` | `--paper` | `#111827` | `#e6eaf2` |
| `--btn-secondary-border` | `--slate` | `--slate-pale` | `#6b7280` | `#a9b4c6` |
| `--btn-secondary-bg-hover` | `--gray-wash` | `--ink-muted` | `#f5f5f7` | `#232c3b` |
| `--btn-destructive-bg` | `--white` | `--ink-abyss` | `#ffffff` | `#0f141b` |
| `--btn-destructive-fg` | `--red-strong` | `--red-bright` | `#dc2626` | `#f87171` |
| `--btn-destructive-border` | `--red-strong` | `--red-bright` | `#dc2626` | `#f87171` |
| `--btn-destructive-bg-hover` | `--red-pale` | `--red-abyss` | `#fee2e2` | `#3d1a1a` |
| `--btn-alert-bg` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |
| `--btn-alert-fg` | `--white` | `--ink` | `#ffffff` | `#111827` |
| `--btn-alert-border` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |
| `--btn-alert-bg-hover` | `--amber-strong` | `--amber-bright` | `#d97706` | `#fbbf24` |
| `--btn-amber-bg` | `--white` | `--ink-abyss` | `#ffffff` | `#0f141b` |
| `--btn-amber-fg` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |
| `--btn-amber-border` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |
| `--btn-amber-bg-hover` | `--amber-soft` | `--amber-abyss-mid` | `#fde68a` | `#4a3a10` |

### Status / feedback [P]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--status-info-bg` | `--blue-pale` | `--blue-abyss` | `#dbeafe` | `#16324f` |
| `--status-info-fg` | `--blue-deeper` | `--blue-soft` | `#1e40af` | `#93c5fd` |
| `--status-info-border` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--status-success-bg` | `--green-pale` | `--green-abyss-mid` | `#d1fae5` | `#0f3d2e` |
| `--status-success-fg` | `--green-deep` | `--green-glow` | `#166534` | `#6ee7b7` |
| `--status-success-accent` | `--green-strong` | `--green-bright` | `#059669` | `#34d399` |
| `--status-success-border` | `--green-strong` | `--green-bright` | `#059669` | `#34d399` |
| `--status-warning-bg` | `--amber-pale` | `--amber-abyss` | `#fef3c7` | `#3a2c0a` |
| `--status-warning-fg` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |
| `--status-warning-border` | `--amber-strong` | `--amber-bright` | `#d97706` | `#fbbf24` |
| `--status-warning-accent` | `--amber-strong` | `--amber-bright` | `#d97706` | `#fbbf24` |
| `--status-error-bg` | `--red-pale` | `--red-abyss` | `#fee2e2` | `#3d1a1a` |
| `--status-error-fg` | `--red-deep` | `--red-soft` | `#991b1b` | `#fca5a5` |
| `--status-error-border` | `--red-strong` | `--red-bright` | `#dc2626` | `#f87171` |
| `--status-error-accent` | `--red-strong` | `--red-bright` | `#dc2626` | `#f87171` |
| `--toast-error-bg` | `--red-firm` | `--red-bright` | `#b91c1c` | `#f87171` |
| `--status-error-soft-bg` | `--danger-pale` | `--red-abyss` | `#fdecea` | `#3d1a1a` |
| `--status-error-soft-border` | `--danger-soft` | `--danger-abyss-border` | `#f2b8b5` | `#7f2a2a` |
| `--status-error-soft-fg` | `--danger-deep` | `--red-soft` | `#8a1c14` | `#fca5a5` |
| `--status-super-bg` | `--violet-pale` | `--violet-abyss` | `#ede9fe` | `#2e2250` |
| `--status-super-fg` | `--violet-strong` | `--violet-soft` | `#5b21b6` | `#c4b5fd` |

### Participant roles [A]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--role-reviewer-bg` | `--blue-pale` | `--blue-abyss` | `#dbeafe` | `#16324f` |
| `--role-reviewer-fg` | `--blue-deep` | `--blue-soft` | `#1d4ed8` | `#93c5fd` |
| `--role-reviewee-bg` | `--green-pale` | `--green-abyss-mid` | `#d1fae5` | `#0f3d2e` |
| `--role-reviewee-fg` | `--green-strong` | `--green-bright` | `#059669` | `#34d399` |
| `--role-observer-bg` | `--amber-pale` | `--amber-abyss` | `#fef3c7` | `#3a2c0a` |
| `--role-observer-fg` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |

### Lifecycle badges [A]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--lifecycle-draft-bg` | `--amber-pale` | `--amber-abyss` | `#fef3c7` | `#3a2c0a` |
| `--lifecycle-draft-fg` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |
| `--lifecycle-validated-bg` | `--blue-pale` | `--blue-abyss` | `#dbeafe` | `#16324f` |
| `--lifecycle-validated-fg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--lifecycle-ready-bg` | `--green-pale` | `--green-abyss-mid` | `#d1fae5` | `#0f3d2e` |
| `--lifecycle-ready-fg` | `--green-strong` | `--green-bright` | `#059669` | `#34d399` |
| `--lifecycle-expired-bg` | `--red-pale` | `--red-abyss` | `#fee2e2` | `#3d1a1a` |
| `--lifecycle-expired-fg` | `--red-strong` | `--red-bright` | `#dc2626` | `#f87171` |
| `--lifecycle-archived-bg` | `--gray-wash` | `--ink-muted` | `#f5f5f7` | `#232c3b` |

### Navigation [A]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--nav-marker-setup` | `--blue-soft` | `--blue-bright` | `#93c5fd` | `#3b82f6` |
| `--nav-marker-ops` | `--green-soft` | `--green-abyss` | `#a7f3d0` | `#065f46` |
| `--nav-tab-active-fg` | `--blue-deeper` | `--blue-soft` | `#1e40af` | `#93c5fd` |
| `--nav-tab-active-bg` | `--white` | `--ink-abyss` | `#ffffff` | `#0f141b` |
| `--nav-strip-setup-bg` | `--blue-wash` | `--tint-sky-dark` | `#eff6ff` | `#0e1a24` |
| `--nav-strip-ops-bg` | `--green-wash` | `--green-abyss-faint` | `#f0fdf4` | `#0c2419` |
| `--nav-home-bg` | `--blue-wash` | `--blue-abyss-soft` | `#eff6ff` | `#12283f` |
| `--nav-home-bg-hover` | `--blue-mist` | `--blue-abyss-faint` | `#fafcff` | `#0e1c2c` |
| `--nav-home-marker` | `--blue-soft` | `--blue-bright` | `#93c5fd` | `#3b82f6` |

### Config values [A]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--config-value-bg` | `--sky-pale` | `--sky-abyss` | `#e0f2fe` | `#0c2f42` |
| `--config-value-fg` | `--sky-deep` | `--sky-soft` | `#075985` | `#7dd3fc` |
| `--config-value-resolved-bg` | `--blue-wash` | `--blue-abyss-soft` | `#eff6ff` | `#12283f` |

### Card accents [A]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--card-active-border` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--card-active-bg` | `--blue-mist` | `--blue-abyss-faint` | `#fafcff` | `#0e1c2c` |
| `--card-warning-bg` | `--amber-pale` | `--amber-abyss` | `#fef3c7` | `#3a2c0a` |
| `--card-warning-border` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |
| `--card-warning-fg` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |

### Selection, toggles & markers [P]/[A]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--selected-bg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--selected-fg` | `--white` | `--white` | `#ffffff` | `#ffffff` |
| `--icon-btn-action-fg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--icon-btn-danger-fg` | `--red-strong` | `--red-bright` | `#dc2626` | `#f87171` |
| `--focus-ring-strong` | `--blue-deep` | `--blue-soft` | `#1d4ed8` | `#93c5fd` |
| `--row-pending-marker` | `--amber` | `--amber-deep-dk` | `#f59e0b` | `#b45309` |
| `--chip-active-border` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--chip-active-fg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--chip-active-bg` | `--blue-wash` | `--blue-abyss-soft` | `#eff6ff` | `#12283f` |
| `--chip-selected-bg` | `--blue-pale` | `--blue-abyss` | `#dbeafe` | `#16324f` |

---

## Deliberate couplings

Registry of intentional semantic→semantic couplings (`@coupled` marker in
`base.html`). Per the independent-slot rule, none exist yet — every slot maps
to a primitive.

| Coupled slot | → tracks | Reason |
|---|---|---|
| *(none)* | | |

---

## Non-colour scale tokens (16)

Theme-agnostic; not redefined per theme.

**Type** — `--fs-tiny` 0.75rem · `--fs-small` 0.875rem · `--fs-body` 1rem · `--fs-h2` 1.125rem · `--fs-h1` 1.5rem.

**Spacing** — `--space-1` 4px · `--space-2` 8px · `--space-3` 12px · `--space-4` 16px · `--space-6` 24px · `--space-8` 32px · `--space-12` 48px · `--space-16` 64px.

**Radius** — `--radius-button` 6px · `--radius-card` 8px · `--radius-pill` 9999px.

---

## Notes

- **Migrated from flat tokens** over Segment 19C Item 6 (`guide/archive/semantic_tokens.md`);
  `base.html` is now fully two-tier — no flat colour-named token remains.
- **Dropped as unused:** `--accent-red-soft` (never referenced) and the dead
  standalone `.warning-banner` / `.danger-banner` rules.
- **Dark neutrals invert, accents stay hued:** e.g. `--text-on-accent` is white
  in both themes (label on the still-blue Primary), while `--text-on-amber` flips
  to near-black in dark.
