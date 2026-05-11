# UI elements catalogue — Parts 2 + 3 (historical)

**Archived from `spec/ui_elements.md` 2026-05-11.** Originally
landed as the post-pilot audit (Part 2) + restyle bundle PR
ladder (Part 3) of the seven-PR `body.ui-v2` migration. By
2026-05-11 the migration had run its course; the per-element
canonical treatments live in Part 1 of `spec/ui_elements.md`
and the design tokens live in `spec/visual_style_general.md`.

Preserved here for archaeological reference: the Drift
catalogue documents what the audit found, and the PR-ladder
table records what landed per PR. Anyone tracing a v2-era
template back to its driving spec entry can read this file
to understand the migration shape.

---

## Part 2 — Drift catalogue

Cross-cutting list of inline styles, unique classes, and inconsistent
treatments the audit surfaced. Each entry names the offender and the
target canonical element from Part 1.

**Banner cards rendered with inline `style` attributes** rather than
a banner class:
- `instruments_index.html` — rf-save-error, rtd-error,
  rtd-would-empty, rtd-delete-blocked banners.
- `session_assignments.html` — missing-confirm, upload-blocked.
- Cross-template "session is ready" amber warning card on every
  Setup page when the session is locked.
- `review_surface.html` — success (green), submitted (blue),
  warning (amber), session-closed (amber), preview-mode (blue
  via recolored `.warning-banner`).
- `invite_mismatch.html` — danger card.
→ all become **`.banner.banner-{info|success|warning|error}`** (§5).

**Danger Zone cards** rendered with inline `style="border-color:
#b91c1c"` (and inconsistent `background`):
- `session_detail.html`, `session_reviewers.html`,
  `session_reviewees.html`, `session_assignments.html`,
  `instruments_index.html`.
→ all become **`.card.danger-zone`** (§4).

**Inline-styled buttons** that bypass the `.btn` family:
- `instruments_index.html` rf-delete / rf-add row buttons.
- `session_detail.html` Delete Data / Delete session.
- `review_surface.html` "Clear all".
→ rf-delete / rf-add → `.btn-icon` + `.btn-icon.danger`; the rest
  → Destructive (§6).

**Disabled anchor-as-button** styling:
- `.btn.alert-solid.disabled` + inline opacity + pointer-events
  (`instruments_index.html`).
- `.btn.secondary.disabled` (`session_reviewees.html`,
  `session_reviewers.html`).
- `.btn.alert-solid.disabled` (`session_detail.html` Extract Data).
→ unify under one `.btn.disabled` rule (§6).

**Inline `style="color: #b91c1c;"` on Danger Zone H2** —
`session_detail.html`, others.
→ subsumed by `.card.danger-zone` H2 rule (§4).

**Lifecycle pills using generic `.pill-info` / `.pill-warning`** —
every page that shows session lifecycle.
→ use `.pill-lifecycle-{draft|validated|ready}` (§9).

**Reviewer-surface status icons (✓ / ⚠) inline-styled** —
`review_surface.html`.
→ `.status-icon-complete` / `.status-icon-incomplete` (§9).

**Reviewer-surface `<h2 style="margin-top: 24px;">`** for
instrument group headings, and `<h2 style="color: #b91c1c;">` for
the Clear-all section — both inline overrides on H2.
→ section-spacing belongs on the wrapping section, not the H2; the
  red H2 is subsumed by `.card.danger-zone` (§4) and (§3).

**Per-instrument card cycling backgrounds** —
`style="background: {{ instrument_palette[…] }}"` on instrument
cards in `instruments_index.html`. Out of scope for the restyle
(it's a domain feature, not chrome). Flag only.

---

## Part 3 — Restyle bundle PR split

Expanded scope of `guide/archive/unfinished_business.md` #21. The seven PRs land
in order **A → B → C → D → E → F → G**. The pilot drove all seven
through `/operator/sessions/{id}/reviewers1` — the foundation +
canonical primitives are in place under `body.ui-v2`. The remaining
work is a per-template **sweep**: replicate the `/reviewers1` recipe
on every other operator (and reviewer) page, then promote the
`body.ui-v2` rules to default and retire the wrapper.

| PR | Scope | Status |
|---|---|---|
| **A** | Tokens & primitives (palette / type / spacing custom properties; global rule rewrites) | **Foundation landed in pilot.** Token shade ladders extended through the iteration (PRs #334, #336, #337, #338, #341). |
| **B** | Buttons — Primary / Secondary / Destructive / Outline-amber vocabulary; unified `.btn.disabled`; inline-style sweep | **Classes landed**, applied on `/reviewers1`. Per-template sweep across the rest of the operator surface still pending. |
| **C** | Cards & banners — `.card`, `.card.lock`, `.card.danger-zone`, four-variant `.banner` family | **`.card` / `.card.lock` / `.card.danger-zone` landed**, applied on `/reviewers1`. Banner family defined but not yet used on a page (next pilot target: a page with a real banner, e.g. `instruments_index.html`). |
| **D** | Navigation chrome — `.session-nav-card` recolor, lighter Home anchor, bold tab text, lighter active-tab markers, restored row-label emphasis, status-row white background | **Landed in pilot** (PRs #336, #338, #341). The `session_setup_status_row.html` middle-dot rewrite + lifecycle-badge lift was deferred — strip is already close to spec on structure; revisit if visual feedback warrants. |
| **E** | Tables — row-only borders, `12 / 16` padding, `bg-muted` header, subtle hover tint | **Landed in pilot.** Table on `/reviewers1` uses the v2 treatment. `.table-dense` opt-in for the Instruments-page tables not yet needed. |
| **F** | Forms — input padding `8 / 12`, tokenized borders, `.form-help` / `.form-error`, label medium weight | **Landed in pilot.** `/reviewers1` uses `.form-help` for the CSV instructions; file input + checkboxes carry the v2 treatment. |
| **G** | Badges — `.pill-count` (neutral) and lifecycle classes (`.pill-lifecycle-{draft\|validated\|ready}`), reviewer-surface `.status-icon-*` | **`.pill-count` and `.pill-empty` landed** with the refined blue-tint / brown-on-yellow treatments. Lifecycle classes still pending — `session_setup_status_row.html` still emits generic `.pill-info` for the lifecycle badge; the v2 treatment of `.pill-info` is "count" which is acceptable as a placeholder. Reviewer status icons not yet introduced. |

Once the sweep across the rest of the operator surface lands (the
mechanical work to replicate `/reviewers1` page-by-page), the
prerequisites for #22 (Home body rebuild) and #30 (Quick Setup
card on Home) are met: every primitive #22/#30 want to compose
with is in place and named.

---

