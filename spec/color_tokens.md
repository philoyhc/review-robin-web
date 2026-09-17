# Colour tokens — Review Robin Web App

The app's colour system is **two-tier**, defined in `app/web/templates/base.html`'s
`:root` blocks. **Tier 1 primitives** hold the raw palette; **Tier 2 semantic**
tokens name every role and are the *only* thing components and templates consume.

**There is no flat colour-named token.** `--accent-blue`, `--bg-page` and their
kind are not part of the model and must not be reintroduced: a name that says
*blue* cannot be remapped for dark, or moved for contrast, without lying about
what it is — which is the whole reason the two tiers exist. Where a document
uses those names it is naming a design *role*, not a token
(`spec/visual_style_general.md`).

This document is the catalogue; the design rationale is in
`guide/archive/semantic_tokens.md`.

Read alongside `spec/visual_style_rrw.md` (accent assignments, light/dark),
`spec/visual_style_general.md` (design system), `spec/ui_elements.md` (elements).

**Maintenance.** Edit tokens in `base.html` (both `:root` blocks); keep the
`tools/` harness `LABELS` and this catalogue in sync. Rules of the model
(independent slots; marked `@coupled` for deliberate coupling; dark `:root`
remaps semantics onto the one primitive palette) are in `guide/archive/semantic_tokens.md`.

**80 primitives · 107 semantic tokens · 16 non-colour scale tokens.**

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
| `--text-on-accent` | `--white` | `--ink` | `#ffffff` | `#111827` |
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
contributes nothing and the border is the entire delineation. **It is held to
the 3:1 WCAG 1.4.11 asks of a UI-component boundary**, and a light grey cannot
meet that: a pair at `--gray-soft` / `--slate-deep` measures **1.47:1** light
and **1.95:1** dark against that surface, with light the worse of the two.
`--slate-dim` is the one primitive that clears 3:1 in both themes
near-symmetrically (**4.29:1** light, **4.31:1** dark), so a single primitive
serves both columns. The options weighed, including per-theme primitives at an
exact 3:1, are in `guide/archive/segment_19C_refinements.md`.

Two consequences worth knowing. `--decor-muted` also resolves to `--slate-dim`
in dark, so the border and the decorative dividers share a value there — they
are **independently mapped, not coupled**, and either can move alone. And
`--marker-neutral` has `--gray-soft` / `--slate-deep` to itself: repointing
`--border-default` rather than editing those primitives is what keeps the
neutral nav-tab markers where they are, and is the move to repeat next time.

### The AA floor on text

**Every token in the Text cluster clears WCAG AA normal (4.5:1)
against every `--surface-*` token, in both themes**, and
`tests/unit/test_contrast_audit.py` computes that from the shipped
values rather than pinning hexes. The worst case is checked rather
than the likely one: which surface a label lands on is a template's
choice, and the worst light surface is `--surface-tint-5` (`#fff1f2`),
not `--surface-muted`.

**There is one muted text tier, not two.** A second one
(`--text-dim`, `#9ca3af`) sits at **2.31:1** at worst, under the floor,
and two muted tiers whose difference nobody could state are not worth
keeping once one of them has to move. Muted text takes `--text-subtle`
by way of the `--slate` primitive (`#616874`, **4.53:1** at worst);
`--slate`'s only other consumer is `--btn-secondary-border`, a boundary
held to 3:1 and clearing it at 5.61.

**The worst case is not a surface**, which is why the check sweeps
pairs rather than tokens. `--nav-home-bg` (`--gray-mist`, `#e5e7eb`)
is darker than any `--surface-*` token and carries muted text on the
Session Home anchor, so it — not `--surface-tint-5` — is the binding
constraint on `--text-subtle`: **4.53:1** at the shipped value against
5.11:1 on the worst surface. A sweep of the Text cluster against the
Surfaces cluster never reads that pair at all. The worked case:
`--slate` at `#667080` scores 4.56 on the worst surface and passes,
while the Session Home anchor sits at **4.04** — only a pair sweep
catches that. `#667080` is named here because it is the only way to
check the 4.04; it maps to nothing.

**Decoration is outside the floor, and has its own token so that it
stays outside.** WCAG 1.4.3 governs text; a 3px divider and the two
gradient stops in a resize grip are not text and are not held to a
ratio. They take `--decor-muted`, which is free to carry the faint value
the text floor rules out. **The point of the separate token is that the
faint value cannot drift back onto a label**: a `color:` declaration
naming `--decor-muted` fails the test.

**Three pairs fall short of AA normal, all accepted; none is open.**
The three are light button labels dipping **only under the pointer** —
3.19/3.68/3.95 on hover against 7.09/5.17/4.83 at rest — and that
acceptance is **conditional on the resting pair**, which the suite
asserts rather than assumes. They are listed in
`docs/known_limitations.md` and pinned in `ACCEPTED_BELOW_AA`. **A new
sub-AA pair fails the suite rather than joining a list**: the accepted
set is closed, and reopening it is a decision, not a fix.

**A label on a bright dark accent fill inverts rather than staying
white.** `--text-on-amber` and `--btn-alert-fg` take `--white` in light
and `--ink` in dark, because the dark alert fill is bright;
`--btn-primary-fg`, `--selected-fg` and `--text-on-accent` follow the
same rule for the same reason. White on `--blue-glow` reaches only
**2.54** on the hover pair, which would be the worst in the palette;
`--ink` gives **5.33** at rest and **6.98** on hover.

*Do not darken the fill instead.* White on
`--blue-strong` reaches 5.17 and is the only step that works —
`--blue-deep` gives 6.70 for the label but drops the fill to **2.76**
against `--surface-page`, under the **3:1** WCAG 1.4.11 asks of a
control boundary, trading a text failure for a boundary one. That route
has one usable value and moves `--blue-glow`, which nine dark tokens
resolve to; the inversion moves three mappings and no primitive.
`--btn-primary-border` stays on `--blue-glow`, being a boundary at 3:1,
by the line that keeps `--decor-muted` outside the text floor.

*`--ink` rather than `--ink-deep`*: at 5.33 against 4.85 the two are
near-indistinguishable on the control itself, so the one with headroom
wins on the only axis that separates them.

### Collapsing a tier

**Where a hue carries two text tiers on one surface and the lighter
one fails AA, collapse it into the darker rather than inventing a
value.** The tell is that the darker tier **already exists and already
passes**, which means the palette has answered the question once and
not applied the answer. Four text tokens are held there for that
reason:

| Token | Primitive (light) | Ratio |
|---|---|---|
| `--lifecycle-ready-fg` | `--green-deep` | **6.29** |
| `--role-reviewee-fg` | `--green-deep` | **6.29** |
| `--status-success-accent` | `--green-deep` | **6.29** |
| `--lifecycle-expired-fg` | `--red-deep` | **6.80** |

The lighter tier of each hue — `--green-strong` at 3.32,
`--red-strong` at 3.95 — is **not a text colour**. Putting one back
would leave a single tint carrying two text colours of the same hue,
one passing and one failing, for no reason a reader could state:
`--status-success-fg` and `--status-error-fg` sit on the same tints at
`--green-deep` and `--red-deep`.

Two limits, both following the rules above rather than taste:

- **Only text collapses.** `--status-success-border` keeps
  `--green-strong`: it is a boundary, held to 1.4.11's 3:1, which it
  clears at 3.32. The same line that keeps `--decor-muted` outside the
  text floor.
- **Light only, here.** The dark mappings of all four differ
  (`--green-bright`, `--red-bright`) and already clear AA, so
  collapsing them would change appearance to fix nothing.

**A collapse is available only where the palette has already produced a
passing tier to collapse into**, which is not every case: white on
`--blue-glow` in dark is a single value with no second tier. **And a
collapse is not the only alternative to moving a value** — inverting the
*foreground* is a third move, and it is what closes that case (above). A
rule that names only the options it can see makes the unseen one look
impossible.

**To look at the audit rather than read it**, open
`tools/theme_customizer.html`: its Contrast panel lists every pair,
outlines in red any that fall under AA in the active theme, and
recomputes as you remap, so the cost of a palette change is visible
before it is made. The panel and the test derive their pairs from the
same function.

**Border colours do not paint fills.** A surface takes a token from the
Surfaces cluster. `.rs-help-card` fills with `--card-help-bg` — its own
token, not a borrowed one, so the next change to a border token cannot reach
it (`--gray-mist` light / `--ink-muted` dark, carrying body text at 14.3:1 and
11.7:1). Filled with `--border-default` instead it would read acceptably only
while that token stayed very light, and at 3:1-plus the body text on it falls
to 3.96:1 light / 3.41:1 dark, both under AA. See "Card accents" below and
`spec/ui_elements.md` §"Reviewer help cards".

### Buttons [P]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--btn-primary-bg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--btn-primary-fg` | `--white` | `--ink` | `#ffffff` | `#111827` |
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
| `--status-success-accent` | `--green-deep` | `--green-bright` | `#166534` | `#34d399` |
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
| `--role-reviewee-fg` | `--green-deep` | `--green-bright` | `#166534` | `#34d399` |
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
| `--lifecycle-ready-fg` | `--green-deep` | `--green-bright` | `#166534` | `#34d399` |
| `--lifecycle-expired-bg` | `--red-pale` | `--red-abyss` | `#fee2e2` | `#3d1a1a` |
| `--lifecycle-expired-fg` | `--red-deep` | `--red-bright` | `#991b1b` | `#f87171` |
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


**One token set, more than one caller.** `--card-help-*` paints both
`.rs-help-card` (the Instruments page's help slabs) and
`.page-guidance` (the `What this page is for` disclosure on every Setup
page). The theme customizer's facet is therefore named **`Help card`**,
not `Instrument help card` — a facet named after one caller would
misdescribe what editing it changes.

**`--card-help-border` is darker than `--card-help-bg`** — `--gray` over
`--gray-mist` in light, `--slate-deep` over `--ink-muted` in dark. It
sits **between a soft edge and an outline**: **2.54:1** against the page
in light and **1.95:1** in dark (2.05:1 and 1.48:1 against its own
fill). Short of the 3:1 WCAG 1.4.11 asks of a UI-component boundary, so
it is not load-bearing as a control edge — but firm enough that a card
standing alone in a column reads as bounded.

A fainter pair does not do the job: `--gray-soft` / `--slate-deeper`
measures 1.47:1 and 1.50:1 against the page, which reads as no edge at
all. **The two themes deliberately do not match by the numbers** — light
is the firmer edge — because each end of that ramp offers only one shared
step.

**The border must not point at the fill's own primitive.** That erases
the edge, which is tolerable only for a tinted slab nested *inside*
another card, where an edge would be `.card`'s 2px `--border-default`
cutting across a nested block. A help card standing **alone in a column**
reads as unanchored without one, and `.page-guidance` is exactly that
case — including on the four roster pages, where 19P moved the card out
of `.card-columns` to full width above everything else. The argument is
about a card with nothing beside it to anchor against, which a
full-width card at the top of a page is even more plainly; the token
set and the reasoning are both unchanged by the move, and the
placement the sentence assumes is stated here rather than left to be
inferred from a container the page no longer uses.

`--card-help-border` and `--card-help-bg` are **two independent mappings,
not a coupling**: the border points at a primitive, never at
`var(--card-help-bg)`, so either can be repointed alone without dragging
the other. The same reason the help card has its own `-fg` rather than
inheriting `--text-body`.

### Selection, toggles & markers [P]/[A]

| Semantic token | Light → primitive | Dark → primitive | Light | Dark |
|---|---|---|---|---|
| `--selected-bg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--selected-fg` | `--white` | `--ink` | `#ffffff` | `#111827` |
| `--icon-btn-action-fg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--icon-btn-danger-fg` | `--red-strong` | `--red-bright` | `#dc2626` | `#f87171` |
| `--focus-ring-strong` | `--blue-deep` | `--blue-soft` | `#1d4ed8` | `#93c5fd` |
| `--row-pending-marker` | `--amber` | `--amber-deep-dk` | `#f59e0b` | `#b45309` |
| `--chip-active-border` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--chip-active-fg` | `--blue-strong` | `--blue-glow` | `#2563eb` | `#4b8bf5` |
| `--chip-active-bg` | `--blue-wash` | `--blue-abyss-soft` | `#eff6ff` | `#12283f` |
| `--chip-selected-bg` | `--blue-pale` | `--blue-abyss` | `#dbeafe` | `#16324f` |
| `--selection-panel-bg` | `--blue-pale` | `--blue-abyss` | `#dbeafe` | `#16324f` |

---

## Deliberate couplings

**`--blue-strong` / `--blue-glow` are reserved.** The pair
`--selected-bg` resolves to — `#2563eb` light, `#4b8bf5` dark — means
*you can act on this*: click it, or in Instruments Band 2, click and
drag it. `--text-link` is the same rule rather than an exception, since
a link is actionable.

**The coupling holds in light and is one step off in dark.** At
`--blue-glow`, dark `--text-link` measures **4.22:1** on
`--surface-muted`, under AA normal, so it takes `--blue-glow-soft`
instead (`#60a5fa`, **5.53:1**). It is the adjacent step on the same
ramp, so the *you can act on this* reading survives; what does not
survive is the literal shared value, and a reader comparing the two
columns should expect the dark one to differ. **Do not move
`--blue-glow` itself** to close that gap: it is the reserved shade, and
many other dark tokens (`--selected-bg`, `--focus-ring`,
`--btn-primary-bg`, `--chip-active-fg` among them) resolve to it.

**The scope is the ambiguity, not the element type.** The reservation
exists because a pill and a chip have a **dual nature**: one rounded
shape states a fact in one place and offers a click in another. Left to
`cursor: pointer` that difference is invisible until the pointer is on
the element, absent on touch, and absent from every screenshot. The
shade is what makes it visible.

It follows that the rule reaches **any element class carrying the same
dual nature**, and does *not* reach a class that has no interactive
twin to be confused with. Two consequences:

- `--status-info-border` resolves to the pair on a static
  `.banner-info`, and that is **not** an inconsistency. There is no
  such thing as a clickable info banner that looks like a static one,
  so the border misleads nobody.
- `.btn-icon` carries the dual nature too: the row pager's inactive
  steps render as `<span class="btn-icon …">` beside live ones that are
  anchors. It is in scope, and it holds — the inert form takes
  `--text-subtle` at 0.4 opacity and never the accent.

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
which is why `.btn-icon` is in it.
`--lifecycle-validated-fg` must stay **off** the pair — a lifecycle
badge states a fact — which is why it reads `--blue-deeper` /
`--blue-soft` above.

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

- **Dark neutrals invert; accent fills stay hued, and their labels flip.** The
  accent fills remain blue and amber in dark rather than greying out; the
  labels on them — `--text-on-accent`, `--text-on-amber`, `--btn-alert-fg`,
  `--btn-primary-fg`, `--selected-fg` — take `--ink` rather than `--white`,
  because the dark fills are bright. See **The AA floor on text** above.
- **A token with no consumer is not kept.** When a rule's last consumer goes,
  its token goes with it in the same change; an orphan token reads as a slot
  someone forgot to fill.
