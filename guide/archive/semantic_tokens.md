# Semantic colour tokens — two-tier migration plan

**Status:** ✅ **SHIPPED 2026-08-23 — archived.** The migration is complete
(19C Item 6, 17 PRs #2047–#2062); `base.html` is fully two-tier and all flat
tokens are retired. This is the design + decision record, kept for reference;
the live catalogue is `spec/color_tokens.md`. The one deferred piece — the
app-agnostic customizer tooling (the portability kernel) — is tracked under
19C Item 5. Original plan status preserved below.

Supersedes the flat, colour-named token model. Scoped as **Segment 19C Items
4–5** (theme machinery: the customizer + this token system) with an explicit
**portability goal** — reusable by other apps of the same look and feel, with
a **clean extractable kernel as the unhurried end-state** (see "Reusability
across apps" + "Decisions").

## Why

Today's palette (`base.html` `:root`, catalogued in `spec/color_tokens.md`)
is **one flat list of colour-named tokens** — `--accent-blue`,
`--accent-amber-dark`, `--bg-page` … Two problems fall out of naming by
colour instead of by role:

1. **Unrelated elements are coupled.** `--accent-blue` is the link colour
   *and* the Primary-button fill *and* the input focus ring *and* several
   card accents. You cannot restyle the Primary button without moving links,
   because they are literally the same token. The value can't diverge from
   the intent.
2. **No single home per token.** The theme-customizer reorg kept hitting
   this: a token that serves five elements can't live in one "zone." That
   friction is the symptom, not the disease — the disease is a **missing
   semantic layer**.

The fix is the standard two-tier token system: keep the colour scale as
low-level *primitives*, and add a *semantic* layer named by role that every
component consumes. This is a **superset** of what exists — today's tokens
are a muddle of both tiers flattened into one list.

The audit this needs is already half-built: `spec/color_tokens.md` + the
consumer map produced alongside it is the "which element uses what"
inventory. What remains is the **taxonomy** (cluster elements into roles,
name them, fix the hierarchy) and the **migration** (rewire consumers),
landed incrementally.

---

## Target architecture — two tiers

```
Tier 1  PRIMITIVES   --blue-600, --amber-700, --gray-500, --white …
   │                 the raw colour scale. Named by hue + step. Theme-agnostic.
   ▼   (aliased by)
Tier 2  SEMANTIC     --btn-primary-bg, --text-body, --surface-card,
   │                 --status-warning-bg … named by ROLE. Redefined per theme.
   ▼   (consumed by)
        COMPONENTS   .btn, .pill, .banner, .card … consume ONLY Tier 2.
```

**Rules of the model:**

- **Components never reference a primitive.** A `.btn` rule uses
  `var(--btn-primary-bg)`, never `var(--blue-600)`.
- **Primitives are the only place raw hex lives.** Semantic tokens are all
  `var(--primitive)` references.
- **Every semantic slot is independent by default** *(core principle —
  author directive)*. Each identified slot is **its own token that maps to a
  primitive**. **Two slots that share a value today still get separate
  tokens**, so either can be re-pointed later without a rename and without
  disturbing the other. `--text-link` and `--btn-primary-bg` are distinct
  even though both resolve to `--blue-600` now; `--role-reviewer-bg` is
  distinct from `--status-info-bg`; the soft inline error keeps its own
  `--status-error-soft-*`. Never collapse two slots because they coincide —
  coincidence of value is not identity of role.
- **Deliberate coupling is allowed — but it must be a marked choice.** A slot
  *may* be defined in terms of another (`--x: var(--y)`) to intentionally
  make the two track together — when the design *wants* them locked, not
  merely equal today. This is the one sanctioned exception to
  semantic→primitive resolution, and it only counts when it is **flagged as
  intent**, so it reads as a decision rather than an accidental chain:
  annotate the definition with the `@coupled` marker and record it in the
  Deliberate-couplings registry (below). An **unmarked** semantic→semantic
  reference is disallowed — that's exactly the accidental coupling the
  default guards against. Default stays: map to a primitive.
- **Theming lives in Tier 2.** Light `:root` maps each semantic token to a
  light-appropriate primitive; `:root[data-theme="dark"]` remaps the same
  semantic tokens to dark-appropriate primitives (decision #5 — one palette,
  no parallel dark namespace). Primitives themselves do **not** change per
  theme (`--blue-strong` is always the same blue). This keeps "what dark mode
  does" readable as one block of role→primitive reassignments.

### Deliberate couplings — marker + registry

When a coupling is genuinely wanted (two slots that should *stay* locked, not
just happen to match), express it and flag it:

```css
/* @coupled → --status-info-bg : reviewer chip intentionally tracks Info */
--role-reviewer-bg: var(--status-info-bg);
```

- **Marker.** The `@coupled → <target> : <reason>` comment immediately above
  (or trailing) the declaration. Machine-readable, so an audit / the
  customizer can find every coupling and distinguish it from an accidental
  `var(--semantic)` reference (which is disallowed).
- **Registry.** Every coupling is also listed here, so the set is reviewable
  in one place:

  | Coupled slot | → tracks | Reason |
  |---|---|---|
  | *(none yet)* | | Decisions 1–3 kept the tempting pairs independent |

- **Tooling.** The customizer surfaces a coupled slot as *"→ tracks
  {target}"* — editing the target moves both; the coupling can be broken
  deliberately (repoint the slot to a primitive), which also removes its
  registry entry.

Default remains independence; a coupling is only ever an explicit entry in
this registry.

### Tier 1 — the primitive palette

**Descriptively named** (decision #4) — `--{hue}-{shade-word}`, not numeric
steps. One `{hue}` per colour family plus a neutral ramp; a small, consistent
shade-word ladder (e.g. `-mist / -wash / -pale / -soft / -bright / -strong /
-deep / -deeper`) covers the lightnesses. Examples (the exact shade vocabulary
is finalised in slice 1):

| Primitive | Value | (today's token at this value) |
|---|---|---|
| `--white` | `#ffffff` | `--bg-page`, `--bg-card`, `--text-on-accent` |
| `--ink` | `#111827` | `--text-primary` |
| `--slate` | `#6b7280` | `--text-secondary` |
| `--slate-soft` | `#9ca3af` | `--text-muted` |
| `--gray` | `#d1d5db` | `--border-default`, `--neutral-marker` |
| `--gray-soft` | `#e5e7eb` | `--border-subtle` |
| `--gray-wash` | `#f5f5f7` | `--bg-muted` |
| `--blue-strong` | `#2563eb` | `--accent-blue` |
| `--blue-bright` | `#3b82f6` | `--accent-blue-light` |
| `--blue-deep` | `#1d4ed8` | `--accent-blue-dark` |
| `--blue-deeper` | `#1e40af` | `--accent-blue-strong` |
| `--blue-soft` | `#93c5fd` | `--accent-blue-marker` |
| `--blue-pale` | `#dbeafe` | `--accent-blue-bg` |
| `--blue-wash` | `#eff6ff` | `--accent-blue-bg-soft` |
| … | | (amber / red / green / violet / sky + the dark shades likewise) |

**One palette, no parallel dark set** (decision #5). Primitives are
theme-agnostic; the dark shades (`#4b8bf5`, the dark inks `#0f141b / #1a212e
/ #232c3b`, …) are simply **more named primitives in the same set**
(`--blue-glow`, `--ink-abyss`, …). Dark mode is **not** a parallel `--blue-dk-*`
namespace — the dark `:root` just **reassigns each semantic token to whichever
existing primitive fits** (light `--btn-primary-bg: var(--blue-strong)`;
dark `--btn-primary-bg: var(--blue-glow)`). Slice 1 enumerates the full
descriptive palette from the 47 light + 47 dark values (many collapse —
several tokens already share a value).

### Tier 2 — semantic naming convention

`--{group}-{role}-{property}[-{state}]`, kebab-case, short:

- **group** — `surface` `text` `border` `btn` `status` `role` `lifecycle`
  `nav` `config` `card` `focus`.
- **property** — `bg` (background/fill) · `fg` (text/foreground) · `border`.
- **state** — `hover` (optional).

Examples: `--btn-primary-bg`, `--btn-primary-fg`, `--btn-primary-bg-hover`,
`--status-warning-bg`, `--text-link`, `--surface-card`.

---

## Reusability across apps (design goal)

**Build the machinery to be portable** — reusable by other apps that want
this look and feel, not welded to Review Robin. That reshapes the design in
three ways:

1. **Split Tier 2 into a portable core + an app-specific layer.**
   - **Portable core semantics** — every app of this family has these:
     `surface-*`, `text-*`, `border-*` / `focus`, `btn-*` (the five roles),
     `status-*` (info / success / warning / error). Clusters **1–5, 11, and
     the borders/focus half of 3** below.
   - **App-specific semantics** — Review-Robin domain: participant-role
     pills, lifecycle badges, session-nav markers, config-value chips,
     instrument tints. Clusters **6–10**. By default each is an
     **independent slot that maps to a primitive** rather than introducing
     new colours, so a new app either drops them or re-points them without
     touching the core. Where an app-specific slot is *meant* to track a core
     role (e.g. a chip that should always equal Info), that is expressed as a
     **marked deliberate coupling** to the core semantic — an explicit choice,
     per the coupling rule, not an implicit dependency.
   Naming keeps the split legible (portable tokens carry no domain word;
   app-specific ones do — `--lifecycle-*`, `--role-*`, `--config-value-*`).

2. **Keep the token layer extractable.** The primitives + portable core
   should live as a **self-contained block** (a clearly delimited region of
   `base.html` now; a candidate for its own `tokens.css` partial later) that
   another app can lift wholesale, then **swap primitive values to rebrand**
   and define only its own app-specific layer. The portable→app dependency
   runs one way, so the core never imports app specifics.

3. **Make the tooling app-agnostic.** The customizer / preview
   (`tools/`, `guide/theme_customizer.md`) must be **parameterised by the
   target token file**, not hard-wired to RRW: the friendly-name `LABELS`,
   the seed families, and the zone/cluster definitions become **data** the
   generator reads (ideally derived from the token file itself), not baked
   constants. The JSON export/import is already the portable interchange
   format — a coding agent ports it into any app's token block. Result: point
   the customizer at another app's `tokens.css`, design, export, apply.

The reusable deliverable is therefore: **{primitives + portable-core
semantic layer} + {the app-agnostic customizer}** — a small design-system
kernel; each app supplies its own primitive values and app-specific
semantics on top.

---

## Element → role taxonomy (the clustering)

Eleven clusters, derived from the consumer audit. Each row is a proposed
Tier-2 token and the **current** token it takes its value from (which fixes
its Tier-1 primitive). This *is* the reorg deliverable; slice 1 turns it into
the actual `:root` blocks. **[P]** = portable core · **[A]** = app-specific
(see "Reusability" above).

### 1. Surfaces — [P] (tints `--surface-tint-*` are [A])

| Semantic | ← current | Notes |
|---|---|---|
| `--surface-page` | `--bg-page` | body/html, card fill, outline-button fill, input bg |
| `--surface-card` | `--bg-card` | raised card |
| `--surface-muted` | `--bg-muted` | tab strips, table header/hover, code blocks |
| `--surface-tint-1…6` | `--instrument-tint-1…6` | per-instrument card tints |

### 2. Text & links — [P]

| Semantic | ← current | Notes |
|---|---|---|
| `--text-body` | `--text-primary` | body, headings |
| `--text-subtle` | `--text-secondary` | subtitles, help, chrome identity |
| `--text-muted` | `--text-muted` | de-emphasised |
| `--text-on-accent` | `--text-on-accent` | label on filled accent |
| `--text-on-amber` | `--text-on-amber` | label on filled amber |
| `--text-link` | `--accent-blue` | **decoupled from `--btn-primary-bg`** — same value today, own token now |

### 3. Borders & focus — [P]

| Semantic | ← current |
|---|---|
| `--border-subtle` | `--border-subtle` |
| `--border-default` | `--border-default` |
| `--focus-ring` | `--accent-blue` (border + outline; halo = `--accent-blue-bg`) |
| `--marker-neutral` | `--neutral-marker` |

### 4. Buttons (5 roles × fill / label / border / hover) — [P]

| Role | `-bg` | `-fg` | `-border` | `-bg-hover` |
|---|---|---|---|---|
| `--btn-primary-*` | `--accent-blue` | `--text-on-accent` | `--accent-blue` | `--accent-blue-light` |
| `--btn-secondary-*` | `--bg-page` | `--text-primary` | `--text-secondary` | `--bg-muted` |
| `--btn-destructive-*` | `--bg-page` | `--accent-red` | `--accent-red` | `--accent-red-bg` |
| `--btn-alert-*` | `--accent-amber-dark` | `--text-on-amber` | `--accent-amber-dark` | `--accent-amber` |
| `--btn-amber-*` | `--bg-page` | `--accent-amber-dark` | `--accent-amber-dark` | `--accent-amber-bg-mid` |

(This is exactly the label/fill/border grid the customizer's Buttons zone
already shows — the zone was an early sketch of this cluster.)

### 5. Status / feedback (info · success · warning · error) — [P]

Consumed by pills, banners, and inline messages.

| Status | `-bg` | `-fg` | `-border` |
|---|---|---|---|
| `--status-info-*` | `--accent-blue-bg` | `--accent-blue-strong` | `--accent-blue` |
| `--status-success-*` | `--accent-green-bg` | `--accent-green-text` | `--accent-green` |
| `--status-warning-*` | `--accent-amber-bg` | `--accent-amber-dark` | `--accent-amber` |
| `--status-error-*` | `--accent-red-bg` | `--accent-red-text` | `--accent-red` |

Per the independent-slot rule (former decisions 1–2, now resolved): **success
keeps two independent fg slots** — `--status-success-fg` (`--accent-green-text`,
pill text) and `--status-success-accent` (`--accent-green`, icon / border) —
and the **soft inline save-error keeps its own** `--status-error-soft-{bg,
border,fg}` (← `--danger-{bg,border,text}`), distinct from `--status-error-*`.
Live banners are the ui-v2 `.banner.banner-*`, whose borders resolve to the
`--status-*-border` slots above; the standalone `.warning-banner` /
`.danger-banner` are dead (see "Completeness pass").

### 6. Participant-role pills — [A]

| Semantic | ← current |
|---|---|
| `--role-reviewer-bg / -fg` | `--accent-blue-bg` / `--accent-blue-dark` |
| `--role-reviewee-bg / -fg` | `--accent-green-bg` / `--accent-green` |
| `--role-observer-bg / -fg` | `--accent-amber-bg` / `--accent-amber-dark` |

### 7. Lifecycle badges — [A]

| Semantic | maps to |
|---|---|
| `--lifecycle-draft` | warning (amber) |
| `--lifecycle-validated` | info (blue: `--accent-blue-bg` / `--accent-blue`) |
| `--lifecycle-ready` | success (green) |
| `--lifecycle-expired` | error (red) |
| `--lifecycle-archived` | muted (`--bg-muted`) |

### 8. Navigation — [A]

| Semantic | ← current |
|---|---|
| `--nav-marker-setup` | `--accent-blue-marker` |
| `--nav-marker-ops` | `--accent-green-marker` |
| `--nav-tab-active-fg` | `--accent-blue-strong` |
| `--nav-tab-active-bg` | `--bg-card` |
| `--nav-strip-ops-bg` | `--accent-green-bg-faint` |
| `--nav-home-bg / -bg-hover / -marker` | `--accent-blue-bg-soft` / `--accent-blue-bg-faint` / `--accent-blue-marker` |

### 9. Config values — [A]

| Semantic | ← current |
|---|---|
| `--config-value-bg / -fg` | `--accent-sky-bg` / `--accent-sky-text` |
| `--config-value-resolved-bg` | `--accent-blue-bg-soft` |

### 10. Card accents — [A]

| Semantic | ← current |
|---|---|
| `--card-active-border / -bg` | `--accent-blue` / `--accent-blue-bg-faint` (editing / acknowledge / selected / severity) |
| `--card-warning-bg / -border` | `--accent-amber-bg` / `--accent-amber-dark` (danger-zone, lock) |
| next-action signals | reuse `--status-{success,warning,error,info}-fg` |

### 11. Super pill (violet) — [P] (extended status accent)

| Semantic | ← current |
|---|---|
| `--status-super-bg / -fg` | `--accent-violet-bg` / `--accent-violet-text` |

### 12. Selection, toggles & markers — [P] / [A]

The long tail surfaced by the completeness pass — live consumers that no
earlier cluster named.

| Semantic | ← current | [P]/[A] | Consumers |
|---|---|---|---|
| `--selected-bg` | `--accent-blue` | [P] | `.tag-chip.is-selected`, `.theme-toggle-opt[aria-pressed]`, `.skip-link` |
| `--selected-fg` | `--text-on-accent` | [P] | (label on the above) |
| `--icon-btn-action-fg` | `--accent-blue` | [P] | `.btn-icon.action` |
| `--icon-btn-danger-fg` | `--accent-red` | [P] | `.btn-icon.danger` |
| `--focus-ring-strong` | `--accent-blue-dark` | [P] | `.rrw-sort-btn:focus-visible` (a second, darker focus tone) |
| `--row-pending-marker` | `--accent-amber-border` | [A] | `[data-row-pending]` warning box-shadow (the sole live consumer of `--accent-amber-border`) |

**Relationships / hierarchy.** Clusters 6–7 (roles, lifecycle) and much of
10 reuse the *same colours* as the cluster-5 status palette — but, per the
independent-slot rule, each **maps to the primitive directly** (not to the
status semantic), so "observer" can diverge from generic "warning" without a
rename. A slot that *should* track a status role expresses it as a marked
`@coupled` reference. Dependency runs one way: components → semantic →
primitive (with the occasional marked semantic→semantic coupling).

### Completeness pass (2026-08-23)

All **47** current colour tokens are dispositioned:

- **Mapped** into clusters 1–12: **44**.
- **Kept, newly slotted** in cluster 12: `--accent-amber-border` (→
  `--row-pending-marker`, one live consumer).
- **Drop (dead — no live consumer):** `--accent-red-soft` (never referenced)
  and `--accent-red-strong` (only the dead standalone `.danger-banner` +
  legacy pre-`ui-v2` `.btn.danger*`). Remove the dead `.warning-banner` /
  `.danger-banner` rules with them.

Finding: **two banner implementations coexist** in `base.html` — the live
ui-v2 `.banner.banner-*` (14 template uses; borders = `--status-*-border`)
and the **dead** standalone `.warning-banner` / `.danger-banner` (0 uses).
The migration drops the dead pair; no live element is uncovered.

---

## Migration strategy — slices

Value-preserving throughout: every slice must reproduce the current pixels
(assert each primitive equals the current hex; each repointing is a no-op
visually). Verified on the Azure dev slot, since the suite can't see CSS.

- **Slice 0 — this plan.** Review + agree the taxonomy and naming.
- **Slice 1 — introduce both tiers, zero consumers changed.** Add the Tier-1
  primitives and the full Tier-2 semantic layer to `:root` +
  `:root[data-theme="dark"]`, as aliases reproducing today's values exactly.
  Nothing consumes them yet; the old flat tokens stay. Pure addition,
  visually inert. (Scaffold-first, per `CLAUDE.md`.)
- **Slices 2…N — migrate consumers, one cluster per PR.** Repoint the CSS
  rules (and the two template inline-style blocks) from old tokens to
  semantic tokens, cluster by cluster. Suggested order — most self-contained
  first:
  1. Buttons (already audited; one `.btn` block)
  2. Status core → pills → banners → inline messages
  3. Roles + lifecycle badges (thin aliases over status)
  4. Cards + navigation
  5. Config values, focus ring, forms
  6. Surfaces + text + borders (touch the most rules; do last)
- **Slice N+1 — retire the old flat tokens.** Once no rule references
  `--accent-*` / `--bg-*` / `--text-*` directly, delete them. Colour-named
  survivors, if any, fold into Tier-1 primitives.
- **Tooling slice — rework the customizer + preview + docs, app-agnostic.**
  The customizer becomes two-tier: edit the **primitive palette** (and see
  every semantic role repaint) and/or edit **semantic assignments**. The
  zones we built map 1:1 onto the semantic clusters. Per the reusability
  goal, **parameterise it by the target token file** (labels / clusters /
  seeds read as data, not baked to RRW) so it drives any app's `tokens.css`;
  JSON export/import stays the portable interchange. Rewrite
  `spec/color_tokens.md` as a two-tier catalogue; retarget
  `_harness_common.LABELS` into data.

---

## Impact & risks

### Blast radius (measured)

**Presentation-layer only — zero Python, zero tests, zero DB/behavior.**
Tokens live only in CSS + template inline styles, so the migration never
reaches the three-layer core.

| Area | Scope |
|---|---|
| `base.html` | **94** token definitions (47 light + 47 dark → primitives + semantic layer) + **505** `var(--…)` call-sites to repoint |
| Other templates (17 files) | **~90** inline `var(--…)` call-sites — dominated by `operator/instruments_index.html` (**47**: the `--danger-*` save-error banner + the `--instrument-tint` palette + more); the rest are 1–7 each across operator / reviewer / error surfaces |
| `tools/` | customizer, preview, `_harness_common` — reworked in the tooling slice |
| Docs | `spec/color_tokens.md` (rewrite to two-tier), `spec/visual_style_rrw.md` (touch-ups), `spec/README.md` |

**Not touched:** `app/**/*.py` (routes / services / models) — **0**
references; `tests/` — **0**; migrations / config / behavior — none.

Totals: ~**595** `var()` call-sites + **94** definitions, across
`base.html` + 17 templates + tooling + 4 docs. ~85% of the churn is one file
(`base.html`), all mechanical value-preserving swaps.

### Risks

- **base.html churn is large but mechanical.** Splitting by cluster keeps
  every PR reviewable; each swap is value-preserving.
- **Template inline-style consumers migrate with their clusters** — the
  CSS-only grep misses them. Chief among them:
  `operator/instruments_index.html` (`--danger-*` with the status/error
  cluster; `--instrument-tint-*` with surfaces).
- **No automated visual coverage.** The pytest suite touches **0** tokens, so
  correctness = "pixels unchanged" — each slice needs a dev-slot look, stated
  in the PR description.
- **The customizer is temporarily ahead of the app.** Until the tooling
  slice, the customizer still edits flat tokens; that's fine — it's dev-only
  and not wired in.
- **Dead tokens dropped, not slotted** (per the Completeness pass):
  `--accent-red-soft` (never referenced) and `--accent-red-strong` (only the
  dead standalone `.danger-banner` + legacy `.btn.danger*`). Remove the dead
  `.warning-banner` / `.danger-banner` CSS rules alongside them.

---

## Decisions — all resolved (Slice 1 unblocked)

**1–3** settled by the independent-slot rule; **4–6** decided by the author
2026-08-23. Kept for the record.

1. ~~**Two error treatments.**~~ **Keep separate.** Soft inline save-error
   keeps `--status-error-soft-*` (the `--danger-*` values), distinct from
   `--status-error-*`.
2. ~~**Success two-tone.**~~ **Keep both slots.** `--status-success-fg` (pill
   text) and `--status-success-accent` (icon / border).
3. ~~**Roles / lifecycle collapse vs. distinct.**~~ **Distinct, independent.**
   `--role-*` and `--lifecycle-*` are their own slots, each mapping to a
   primitive.
4. ~~**Primitive naming.**~~ **Descriptive** (`--blue-strong`), not numeric
   steps. Shade-word ladder finalised in slice 1.
5. ~~**Dark primitives.**~~ **One palette; the dark `:root` reassigns the
   same semantic tokens to whichever primitive fits.** No parallel `--blue-dk-*`
   set — dark shades are just more named primitives.
6. ~~**Portability factoring.**~~ **Namespace now, extract cleanly at the
   end — no rush.** No second app is in flight, so Slice 1 keeps one `:root`
   block with [P]/[A] namespacing; a late slice lifts the primitives +
   portable core into a **clean, self-contained kernel** (delimited block →
   `tokens.css` partial) as the final outcome. The customizer is
   data-driven in the tooling slice, once the app migration has settled —
   not front-loaded. **Clean kernel is the target end-state, reached without
   haste.**
