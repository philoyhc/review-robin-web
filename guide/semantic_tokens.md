# Semantic colour tokens — two-tier migration plan

**Status:** proposed (plan only — no code yet). Supersedes the flat,
colour-named token model documented in `spec/color_tokens.md`.

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
- **Theming lives in Tier 2.** Light `:root` maps each semantic token to a
  light-appropriate primitive; `:root[data-theme="dark"]` remaps the same
  semantic tokens to dark-appropriate primitives. Primitives themselves do
  **not** change per theme (a `--blue-600` is always the same blue). This
  keeps "what dark mode does" readable as one block of role→primitive
  reassignments.

### Tier 1 — the primitive palette

The current values are already a Tailwind-shaped scale, so primitives fall
out mechanically. Examples (exact assignment is slice-1 work):

| Primitive | Value | (today's token at this value) |
|---|---|---|
| `--white` | `#ffffff` | `--bg-page`, `--bg-card`, `--text-on-accent` |
| `--gray-900` | `#111827` | `--text-primary` |
| `--gray-500` | `#6b7280` | `--text-secondary` |
| `--gray-400` | `#9ca3af` | `--text-muted` |
| `--gray-300` | `#d1d5db` | `--border-default`, `--neutral-marker` |
| `--gray-200` | `#e5e7eb` | `--border-subtle` |
| `--gray-100` | `#f5f5f7` | `--bg-muted` |
| `--blue-600` | `#2563eb` | `--accent-blue` |
| `--blue-500` | `#3b82f6` | `--accent-blue-light` |
| `--blue-700` | `#1d4ed8` | `--accent-blue-dark` |
| `--blue-800` | `#1e40af` | `--accent-blue-strong` |
| `--blue-300` | `#93c5fd` | `--accent-blue-marker` |
| `--blue-100` | `#dbeafe` | `--accent-blue-bg` |
| `--blue-50`  | `#eff6ff` | `--accent-blue-bg-soft` |
| … | | (amber / red / green / violet / sky / dark-mode steps likewise) |

Dark mode contributes its own steps (e.g. `--blue-dk-600 #4b8bf5`) — the
dark palette is a *parallel* set of primitives the dark `:root` block maps
semantic tokens onto. Slice 1 enumerates the full primitive set from the 47
current light values + their 47 dark counterparts (many collapse — several
current tokens already share a value).

### Tier 2 — semantic naming convention

`--{group}-{role}-{property}[-{state}]`, kebab-case, short:

- **group** — `surface` `text` `border` `btn` `status` `role` `lifecycle`
  `nav` `config` `card` `focus`.
- **property** — `bg` (background/fill) · `fg` (text/foreground) · `border`.
- **state** — `hover` (optional).

Examples: `--btn-primary-bg`, `--btn-primary-fg`, `--btn-primary-bg-hover`,
`--status-warning-bg`, `--text-link`, `--surface-card`.

---

## Element → role taxonomy (the clustering)

Eleven clusters, derived from the consumer audit. Each row is a proposed
Tier-2 token and the **current** token it takes its value from (which fixes
its Tier-1 primitive). This *is* the reorg deliverable; slice 1 turns it into
the actual `:root` blocks.

### 1. Surfaces

| Semantic | ← current | Notes |
|---|---|---|
| `--surface-page` | `--bg-page` | body/html, card fill, outline-button fill, input bg |
| `--surface-card` | `--bg-card` | raised card |
| `--surface-muted` | `--bg-muted` | tab strips, table header/hover, code blocks |
| `--surface-tint-1…6` | `--instrument-tint-1…6` | per-instrument card tints |

### 2. Text & links

| Semantic | ← current | Notes |
|---|---|---|
| `--text-body` | `--text-primary` | body, headings |
| `--text-subtle` | `--text-secondary` | subtitles, help, chrome identity |
| `--text-muted` | `--text-muted` | de-emphasised |
| `--text-on-accent` | `--text-on-accent` | label on filled accent |
| `--text-on-amber` | `--text-on-amber` | label on filled amber |
| `--text-link` | `--accent-blue` | **decoupled from `--btn-primary-bg`** — same value today, own token now |

### 3. Borders & focus

| Semantic | ← current |
|---|---|
| `--border-subtle` | `--border-subtle` |
| `--border-default` | `--border-default` |
| `--focus-ring` | `--accent-blue` (border + outline; halo = `--accent-blue-bg`) |
| `--marker-neutral` | `--neutral-marker` |

### 4. Buttons (5 roles × fill / label / border / hover)

| Role | `-bg` | `-fg` | `-border` | `-bg-hover` |
|---|---|---|---|---|
| `--btn-primary-*` | `--accent-blue` | `--text-on-accent` | `--accent-blue` | `--accent-blue-light` |
| `--btn-secondary-*` | `--bg-page` | `--text-primary` | `--text-secondary` | `--bg-muted` |
| `--btn-destructive-*` | `--bg-page` | `--accent-red` | `--accent-red` | `--accent-red-bg` |
| `--btn-alert-*` | `--accent-amber-dark` | `--text-on-amber` | `--accent-amber-dark` | `--accent-amber` |
| `--btn-amber-*` | `--bg-page` | `--accent-amber-dark` | `--accent-amber-dark` | `--accent-amber-bg-mid` |

(This is exactly the label/fill/border grid the customizer's Buttons zone
already shows — the zone was an early sketch of this cluster.)

### 5. Status / feedback (info · success · warning · error)

Consumed by pills, banners, and inline messages.

| Status | `-bg` | `-fg` | `-border` |
|---|---|---|---|
| `--status-info-*` | `--accent-blue-bg` | `--accent-blue-strong` | `--accent-blue` |
| `--status-success-*` | `--accent-green-bg` | `--accent-green-text` | `--accent-green` |
| `--status-warning-*` | `--accent-amber-bg` | `--accent-amber-dark` | `--accent-amber` |
| `--status-error-*` | `--accent-red-bg` | `--accent-red-text` | `--accent-red` |

Open sub-decisions (see below): success has two fg tones today
(`--accent-green` icon vs `--accent-green-text` pill text); and the **soft
inline save-error** (`--danger-bg/border/text`) is a *second* error
treatment distinct from `--status-error-*`. Consolidate or keep as
`--status-error-soft-*`.

### 6. Participant-role pills

| Semantic | ← current |
|---|---|
| `--role-reviewer-bg / -fg` | `--accent-blue-bg` / `--accent-blue-dark` |
| `--role-reviewee-bg / -fg` | `--accent-green-bg` / `--accent-green` |
| `--role-observer-bg / -fg` | `--accent-amber-bg` / `--accent-amber-dark` |

### 7. Lifecycle badges

| Semantic | maps to |
|---|---|
| `--lifecycle-draft` | warning (amber) |
| `--lifecycle-validated` | info (blue: `--accent-blue-bg` / `--accent-blue`) |
| `--lifecycle-ready` | success (green) |
| `--lifecycle-expired` | error (red) |
| `--lifecycle-archived` | muted (`--bg-muted`) |

### 8. Navigation

| Semantic | ← current |
|---|---|
| `--nav-marker-setup` | `--accent-blue-marker` |
| `--nav-marker-ops` | `--accent-green-marker` |
| `--nav-tab-active-fg` | `--accent-blue-strong` |
| `--nav-tab-active-bg` | `--bg-card` |
| `--nav-strip-ops-bg` | `--accent-green-bg-faint` |
| `--nav-home-bg / -bg-hover / -marker` | `--accent-blue-bg-soft` / `--accent-blue-bg-faint` / `--accent-blue-marker` |

### 9. Config values

| Semantic | ← current |
|---|---|
| `--config-value-bg / -fg` | `--accent-sky-bg` / `--accent-sky-text` |
| `--config-value-resolved-bg` | `--accent-blue-bg-soft` |

### 10. Card accents

| Semantic | ← current |
|---|---|
| `--card-active-border / -bg` | `--accent-blue` / `--accent-blue-bg-faint` (editing / acknowledge / selected / severity) |
| `--card-warning-bg / -border` | `--accent-amber-bg` / `--accent-amber-dark` (danger-zone, lock) |
| next-action signals | reuse `--status-{success,warning,error,info}-fg` |

### 11. Super pill (violet)

| Semantic | ← current |
|---|---|
| `--status-super-bg / -fg` | `--accent-violet-bg` / `--accent-violet-text` |

**Relationships / hierarchy.** Clusters 6–7 (roles, lifecycle) and much of
10 are *not new colours* — they alias the cluster-5 status palette. Naming
them separately is deliberate: it lets, say, the "observer" pill diverge
from the generic "warning" amber later without a rename. The dependency runs
one way only: components → semantic → (status/foundation) → primitive.

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
- **Tooling slice — rework the customizer + preview + docs.** The
  customizer becomes two-tier: edit the **primitive palette** (and see every
  semantic role repaint) and/or edit **semantic assignments**. The zones we
  built map 1:1 onto the semantic clusters. Rewrite `spec/color_tokens.md`
  as a two-tier catalogue; retarget `_harness_common.LABELS`.

---

## Impact & risks

- **base.html churn is large but mechanical.** ~200 `var(--…)` call-sites
  move; each is a value-preserving swap. Splitting by cluster keeps every PR
  reviewable.
- **Two template inline-style consumers** (`operator/instruments_index.html`:
  `--danger-*` and the `--instrument-tint-*` palette) migrate with their
  clusters — don't forget them; the CSS-only grep misses them.
- **No automated visual coverage.** Correctness = "pixels unchanged," which
  the pytest suite can't assert. Each slice needs a dev-slot look; PR
  descriptions must say so.
- **The customizer is temporarily ahead of the app.** Until the tooling
  slice, the customizer still edits flat tokens; that's fine — it's dev-only
  and not wired in.
- **`--accent-red-soft` is unused** (per `spec/color_tokens.md`) — drop it
  in this migration rather than inventing a semantic home.

---

## Open decisions (resolve during Slice 0 review)

1. **Two error treatments.** Consolidate `--danger-*` (soft inline
   save-error) into `--status-error-*`, or keep a distinct
   `--status-error-soft-*`? (They're different values today.)
2. **Success two-tone.** One `--status-success-fg`, or split
   `-fg` (pill text, darker) from `-accent` (icon/border)?
3. **Roles / lifecycle as aliases vs. distinct primitives.** Plan assumes
   distinct semantic *names* aliasing the shared status primitives (cheap
   future divergence). Confirm.
4. **Primitive naming.** Numeric Tailwind-style steps (`--blue-600`) vs.
   descriptive (`--blue-strong`). Plan assumes numeric.
5. **Dark primitives naming.** Parallel set (`--blue-dk-600`) vs. letting
   the dark `:root` reassign the same semantic tokens to whatever primitive
   fits (preferred — fewer names).
