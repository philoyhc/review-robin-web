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

**80 primitives · 106 semantic tokens · 16 non-colour scale tokens.**

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
| `--slate` | `#616874` |
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
| `--blue-cyan-deep` | `#075985` |
| `--blue-cyan-abyss` | `#0c2f42` |
| `--blue-cyan-soft` | `#7dd3fc` |
| `--blue-cyan-pale` | `#e0f2fe` |
| `--green-strong` | `#059669` |
| `--green-abyss` | `#065f46` |
| `--green-abyss-faint` | `#0c2419` |
| `--green-abyss-mid` | `#0f3d2e` |
| `--green-deep` | `#166534` |
| `--green-bright` | `#34d399` |
| `--green-glow` | `#6ee7b7` |
| `--green-soft` | `#a7f3d0` |
| `--green-pale` | `#d1fae5` |
| `--green-wash` | `#ddf4e3` |
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
| `--red-warm-border` | `#7f2a2a` |
| `--red-warm-deep` | `#8a1c14` |
| `--red-warm-soft` | `#f2b8b5` |
| `--red-warm-pale` | `#fdecea` |
| `--violet-abyss` | `#2e2250` |
| `--violet-strong` | `#5b21b6` |
| `--violet-bright` | `#8b5cf6` |
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

**`--violet-bright` is declared but unmapped.** Every other primitive is
reached by at least one semantic token in at least one theme; this one is
reached by none, deliberately. It fills the `bright` slot the other four
chromatic families carry (`--blue-bright`, `--green-bright`,
`--amber-bright`, `--red-bright`) in the smallest family in the palette, and
it is the customizer's live case for the **unused-primitive** marker
(`tools/README.md`), which paints such a chip red — a marker that
highlights nothing cannot be seen to work. Mapping a semantic to it later is expected and needs no note here;
what would need one is the marker going quiet with no such mapping added.

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
| `--text-subtle` | `--slate` | `--slate-pale` | `#616874` | `#a9b4c6` |
| `--text-on-accent` | `--white` | `--white` | `#ffffff` | `#ffffff` |
| `--text-on-amber` | `--white` | `--ink` | `#ffffff` | `#111827` |
| `--text-link` | `--blue-strong` | `--blue-glow-soft` | `#2563eb` | `#60a5fa` |
| `--text-link-strong` | `--blue-deep` | `--blue-soft` | `#1d4ed8` | `#93c5fd` |

### Borders & focus [P]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--border-subtle` | `--gray-mist` | `--slate-deeper` | `#e5e7eb` | `#2b3547` |
| `--border-default` | `--slate-dim` | `--slate-dim` | `#6f7b8e` | `#6f7b8e` |
| `--focus-ring` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--focus-ring-halo` | `--blue-pale` | `--blue-abyss` | `#dbeafe` | `#16324f` |
| `--marker-neutral` | `--gray-soft` | `--slate-deep` | `#d1d5db` | `#3a465c` |
| `--decor-muted` | `--gray` | `--slate-dim` | `#9ca3af` | `#6f7b8e` |

**`--border-default` is the only row that maps to the same primitive in both
themes**, and that is deliberate. It carries the whole boundary of every
bordered surface — inputs and cards fill with `--surface-page`, so the fill
contributes nothing and the border is the entire delineation. At its previous
values it measured **1.47:1** light and **1.95:1** dark against that surface,
under the **3:1** WCAG 1.4.11 asks of a UI-component boundary, and light was
the worse of the two. `--slate-dim` is the one existing primitive that clears
3:1 in both themes near-symmetrically (**4.29:1** light, **4.31:1** dark), so a
single primitive serves both columns. Changed in Segment 19C Item 8; the
options weighed, including per-theme primitives at an exact 3:1, are in
`guide/archive/segment_19C_refinements.md`. *(That plan, and this line
until 19K.7, gave the dark figure as 1.70. It does not reproduce:
`--slate-deep` `#3a465c` on `--ink-abyss` `#0f141b` is **1.95:1**, which
is what this document already computed for the same pair under "Card
accents" below. The light figure, 1.47, reproduces exactly.)*

Two consequences worth knowing. `--decor-muted` also resolves to `--slate-dim`
in dark, so the border and the decorative dividers share a value there — they
are independently mapped, not coupled, and either can move alone. (It was
`--text-dim` that shared it until 19K.7 retired that token; see **The AA floor
on text** below.) And `--marker-neutral` keeps
`--gray-soft` / `--slate-deep`, which it now has to itself: repointing
`--border-default` rather than editing those primitives is what left the
neutral nav-tab markers where they were.

### The AA floor on text

**Every token in the Text cluster clears WCAG AA normal (4.5:1)
against every `--surface-*` token, in both themes**, and
`tests/unit/test_contrast_audit.py` computes that from the shipped
values rather than pinning hexes. The worst case is checked rather
than the likely one: which surface a label lands on is a template's
choice, and the worst light surface is `--surface-tint-5` (`#fff1f2`),
not `--surface-muted`.

Set at 19K.7, which collapsed the two muted tiers into one.
`--text-dim` (`#9ca3af`, **2.31:1** at worst) is **retired**: its text
uses took `--text-subtle`, which moved from `#6b7280` to `#616874` to
clear the floor itself — **3.90:1** at worst before, **4.53:1** after
— by way of the `--slate` primitive, whose only other consumer is
`--btn-secondary-border` (a boundary, held to 3:1, and improved from
4.83 to 5.61 by the same edit).

**The worst case is not a surface**, which is why the check sweeps
pairs rather than tokens. `--nav-home-bg` (`--gray-mist`, `#e5e7eb`)
is darker than any `--surface-*` token and carries muted text on the
Session Home anchor, so it — not `--surface-tint-5` — is the binding
constraint on `--text-subtle`: **4.53:1** at the shipped value against
5.11:1 on the worst surface. A sweep of the Text cluster against the
Surfaces cluster never reads that pair at all. 19K.7 first moved
`--slate` to `#667080`, which a surfaces-only sweep scores 4.56 and
passes while the Session Home anchor sits at **4.04**; the pair sweep
is what caught it, and the value moved again to `#616874`. `#667080`
is recorded here because it is the only way to check that 4.04, and
it ships nowhere.

**Decoration is outside the floor, and has its own token so that it
stays outside.** WCAG 1.4.3 governs text; a 3px divider and the two
gradient stops in a resize grip are not text and are not held to a
ratio. Those five uses took `--decor-muted`, which carries exactly the
primitives `--text-dim` carried, so nothing decorative changed value.
The point of the separate token is that the failing value cannot drift
back onto a label: a `color:` declaration naming `--decor-muted` fails
the test.

**Eleven pairs still fall short and are recorded rather than fixed.**
None is body text; they are accent fills and pill tints, in two
families. White on a mid-tone accent (**2.54–3.68**) covers the dark
primary button and its hover, the light primary and alert hovers, and
the dark selected state — the dark fill is `--blue-glow`, the reserved
shade, so moving it moves nine other dark tokens with it. Saturated
text on its own pale tint (**3.32–3.95**) covers the green `#059669`
on `#d1fae5` shared by the ready lifecycle pill, the reviewee role
chip and the success pill, and the red `#dc2626` on `#fee2e2` shared
by the expired pill and the destructive button's hover. Each is listed
with its measured ratio in `docs/known_limitations.md` and pinned in
`KNOWN_SHORTFALLS`, so none can worsen, and a fix has to delete its
entry rather than leave a stale number behind.

**To look at the audit rather than read it**, open
`tools/theme_customizer.html`: its Contrast panel lists all 73 pairs,
outlines in red any that fall under AA in the active theme, and
recomputes as you remap, so the cost of a palette change is visible
before it is made. The panel and the test derive their pairs from the
same function.

**Border colours do not paint fills.** A surface takes a token from the
Surfaces cluster. `.rs-help-card` used to fill with `--border-default`, which
read acceptably only while that token was very light; at 3:1-plus the body text
on it would have fallen to 3.96:1 light / 3.41:1 dark, both under AA. It now
fills with `--card-help-bg` — its own token, not a borrowed one, so the next
change to a border token cannot reach it (`--gray-mist` light /
`--ink-muted` dark, carrying body text at 14.3:1 and 11.7:1). See "Card accents" above and
`spec/ui_elements.md` §"Reviewer help cards".

### Buttons [P]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--btn-primary-bg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--btn-primary-fg` | `--white` | `--white` | `#ffffff` | `#ffffff` |
| `--btn-primary-border` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--btn-primary-bg-hover` | `--blue-bright` | `--blue-glow-soft` | `#3b82f6` | `#60a5fa` |
| `--btn-secondary-bg` | `--white` | `--ink-abyss` | `#ffffff` | `#0f141b` |
| `--btn-secondary-fg` | `--ink` | `--paper` | `#111827` | `#e6eaf2` |
| `--btn-secondary-border` | `--slate` | `--slate-pale` | `#616874` | `#a9b4c6` |
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
| `--status-error-soft-bg` | `--red-warm-pale` | `--red-abyss` | `#fdecea` | `#3d1a1a` |
| `--status-error-soft-border` | `--red-warm-soft` | `--red-warm-border` | `#f2b8b5` | `#7f2a2a` |
| `--status-error-soft-fg` | `--red-warm-deep` | `--red-soft` | `#8a1c14` | `#fca5a5` |
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
| `--lifecycle-validated-fg` | `--blue-deeper` | `--blue-soft` | `#1e40af` | `#93c5fd` |
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
| `--nav-strip-setup-bg` | `--blue-pale` | `--blue-abyss-soft` | `#dbeafe` | `#12283f` |
| `--nav-strip-ops-bg` | `--green-wash` | `--green-abyss-faint` | `#ddf4e3` | `#0c2419` |
| `--nav-home-bg` | `--gray-mist` | `--ink-muted` | `#e5e7eb` | `#232c3b` |
| `--nav-home-marker` | `--blue-soft` | `--blue-bright` | `#93c5fd` | `#3b82f6` |

### Config values [A]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--config-value-bg` | `--blue-cyan-pale` | `--blue-cyan-abyss` | `#e0f2fe` | `#0c2f42` |
| `--config-value-fg` | `--blue-cyan-deep` | `--blue-cyan-soft` | `#075985` | `#7dd3fc` |
| `--config-value-resolved-bg` | `--blue-wash` | `--blue-abyss-soft` | `#eff6ff` | `#12283f` |

### Card accents [A]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--card-active-border` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--card-active-bg` | `--blue-mist` | `--blue-abyss-faint` | `#fafcff` | `#0e1c2c` |
| `--card-warning-bg` | `--amber-pale` | `--amber-abyss` | `#fef3c7` | `#3a2c0a` |
| `--card-warning-border` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |
| `--card-warning-fg` | `--amber-deep` | `--amber-glow` | `#92400e` | `#fcd34d` |
| `--card-help-bg` | `--gray-mist` | `--ink-muted` | `#e5e7eb` | `#232c3b` |
| `--card-help-border` | `--gray` | `--slate-deep` | `#9ca3af` | `#3a465c` |
| `--card-help-fg` | `--ink` | `--paper` | `#111827` | `#e6eaf2` |


**Two callers, one token set.** `--card-help-*` paints both
`.rs-help-card` (the Instruments page's help slabs) and
`.page-guidance` (the `What this page is for` disclosure on every Setup
page, Segment 19E rung 6). The theme customizer's facet is therefore
named **`Help card`**, not `Instrument help card` — a facet named after
one caller would misdescribe what editing it changes.

**`--card-help-border` is darker than `--card-help-bg`** — `--gray` over
`--gray-mist` in light, `--slate-deep` over `--ink-muted` in dark. It
sits **between a soft edge and an outline**: **2.54:1** against the page
in light and **1.95:1** in dark (2.05:1 and 1.48:1 against its own
fill). Short of the 3:1 WCAG 1.4.11 asks of a UI-component boundary, so
it is not load-bearing as a control edge — but firm enough that a card
standing alone in a column reads as bounded.

*Deepened 2026-09-06* from `--gray-soft` / `--slate-deeper` (1.47:1 and
1.50:1 against the page), authored in the customizer. The two themes no
longer read alike by the numbers — light is the firmer edge — which is
the consequence of both themes having only one shared step available at
each end of that ramp.

*This reverses 19C Item 8*, which pointed the border at the fill's own
primitive so the edge vanished entirely. That was right while the help
card was a tinted slab sitting **inside** another card — an edge there
would have been `.card`'s 2px `--border-default` cutting across a nested
block. It stopped being right at 19E rung 6b, when `.page-guidance` made
the help card a card **of its own** in a column, where an edgeless card
reads as unanchored against the page. The token did not change meaning;
the thing it paints did.

They remain **two independent mappings, not a coupling**:
`--card-help-border` points at a primitive, never at
`var(--card-help-bg)`, so either can be repointed alone without dragging
the other — which is exactly what let this change happen as one edit.
The same reason the help card has its own `-fg` rather than inheriting
`--text-body`.

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

**`--blue-strong` / `--blue-glow` are reserved.** The pair
`--selected-bg` resolves to — `#2563eb` light, `#4b8bf5` dark — means
*you can act on this*: click it, or in Instruments Band 2, click and
drag it. `--text-link` is the same rule rather than an exception, since
a link is actionable.

**The coupling holds in light and is one step off in dark**, since
19K.7. Dark `--text-link` measured **4.22:1** on `--surface-muted` at
`--blue-glow` — under AA normal — and moved to `--blue-glow-soft`
(`#60a5fa`, **5.53:1**). It is the adjacent step on the same ramp, so
the *you can act on this* reading survives; what does not survive is
the literal shared value, and a reader comparing the two columns
should expect the dark one to differ. Moving `--blue-glow` itself was
rejected: it is the reserved shade, and nine other dark tokens
(`--selected-bg`, `--focus-ring`, `--btn-primary-bg`,
`--chip-active-fg` among them) resolve to it.

**The scope is the ambiguity, not the element type** (author,
2026-09-11, closing `guide/archive/segment_19J_assessment_moves.md` Item 10).
The reservation exists because a pill and a chip have a **dual
nature**: one rounded shape states a fact in one place and offers a
click in another, and before Segment 19J.7 the only thing separating
them was `cursor: pointer` — invisible until the pointer is on it,
absent on touch, absent from every screenshot. The shade is what makes
that difference visible.

It follows that the rule reaches **any element class carrying the same
dual nature**, and does *not* reach a class that has no interactive
twin to be confused with. Two consequences, and both were measured
before being written here:

- `--status-info-border` resolves to the pair on a static
  `.banner-info`, and that is **not** an inconsistency. There is no
  such thing as a clickable info banner that looks like a static one,
  so the border misleads nobody. (Item 7 recorded it as a possible
  violation and scoped it out; Item 10 measured it and settled that it
  never was one.)
- `.btn-icon` **acquired** the dual nature at 19J.9, when the row
  pager's inactive steps began rendering as `<span class="btn-icon …">`
  beside live ones that are anchors. It is in scope from that day, and
  it holds: the inert form takes `--text-subtle` at 0.4 opacity and
  never the accent.

`--focus-ring`, `--btn-primary-bg` and `--card-active-border` sit on
actionable or focus surfaces and are unambiguous either way. Every
other blue stays freely available to static elements —
`--status-info-bg` `#dbeafe`, `--status-info-fg` `#1e40af`,
`--role-reviewer-fg` `#1d4ed8` — because the reservation is on the
shade, not the hue.

`tests/unit/test_reserved_shade.py` resolves every token in both themes
and fails if anything but a confirmed control lands on the pair. Its
selector filter is a **consequence** of the rule rather than the rule
itself, and grows when a new element class acquires the dual nature —
which is exactly what happened to `.btn-icon`.
`--lifecycle-validated-fg` used to land on the pair, which is why it
now reads `--blue-deeper` / `--blue-soft` above.

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
  standalone `.warning-banner` / `.danger-banner` rules. `--nav-home-bg-hover`
  joined them on 2026-09-11, when session-nav hover was standardised to wear
  the selected tab's colours and its one consumer went with it.
- **Dark neutrals invert, accents stay hued:** e.g. `--text-on-accent` is white
  in both themes (label on the still-blue Primary), while `--text-on-amber` flips
  to near-black in dark.
