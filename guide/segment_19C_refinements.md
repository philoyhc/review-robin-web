# Segment 19C — Refinements

**Status: all six items ✅ shipped** — the segment stays **open** as a home for
further small refinements. **Item 1 ✅ 2026-08-20** (friendly tag labels via
roster CSV headers; sole round-trip carrier); **Item 2 ✅ 2026-08-21**
(light/dark Display mode — chrome toggle, W1–W8); **Item 3 ✅** (Danger Zone
hardening); **Item 4 ✅** (button treatment refinements); **Item 5 ✅ v1
2026-09-04** (theme customizer — developer designer; three-part
click-to-reflect/edit designer, PRs #2065–#2083; operator-facing **Stretch**
deferred to `guide/deferred_consolidated.md`); **Item 6 ✅ 2026-08-23**
(semantic colour tokens — two-tier reorg; the app is now fully two-tier, plan
archived at `guide/archive/semantic_tokens.md`).
A holding segment for **small,
self-contained operator-facing refinements** that don't warrant their own
segment — the sibling of 19A (docs hygiene) and 19B (code consistency), but
for behaviour / contract polish. Items land as independent slices; the
segment stays open as a home for further refinements as they're identified.
(Item 6 is the largest so far — a multi-PR migration; it may graduate to its
own segment if it grows.)

> Consequential-UI note: per `CLAUDE.md` → "Working approach", anything that
> adds a card / nav / affordance lands **scaffold-first**. Item 1 is a
> **CSV-contract** change (no new UI surface), so it lands as ordinary
> reviewable slices rather than scaffold-first — but each slice is a
> self-contained proof before the next widens it.

---

## Item 1 — Friendly tag labels via roster CSV headers (sole round-trip carrier)

**Status: ✅ shipped 2026-08-20 (single PR).** Landed as one cohesive
transport change (the PR ladder below collapsed to one PR — intermediate
slices would have left a dual-carrier state, which is exactly what this item
removes). New `app/services/field_label_csv.py` (`split_header` /
`normalize_headers` / `labeled_header`) + `field_labels.apply_import`; the
three roster parsers capture header suffixes, the three roster extracts emit
them, `save_reviewers` / `save_reviewees` / `save_relationships` reconcile
(via a `field_labels_captured` arg, threaded from both the interactive routes
and rehydrate); the Settings CSV `field_labels.*` carrier removed (serialize
+ apply + `_apply_field_label.py` deleted; stale keys silently ignored). Full
suite green (2,695 passed); `ruff` clean. **Decisions confirmed at build:**
bare header / absent tag column = **clear** (roster is wipe-and-replace);
stale settings keys silent-dropped; clean settings-contract cutover.

### The opportunity

Operator-definable friendly labels for the **reviewer / reviewee /
relationships** tag slots (the nine `(source_type, source_field)` slots:
`reviewer.tag_1..3`, `reviewee.tag_1..3`, `pair_context.1..3`) are today
keyed in via **two** paths only:

1. the per-page label editor on the Reviewers / Reviewees / Relationships
   Setup pages (three `.../field-labels` POST routes → `_save_field_labels`
   in `routes_operator/_shared.py:595`), and
2. the **Settings CSV** round-trip (`field_labels.*` rows —
   `session_config_io/_serialize.py:615` on export, `_apply_parse.py:107` +
   `_apply_field_label.py` on import).

The per-page UI ergonomics are fine and stay. But operators typically
**already know the friendly labels at the point of roster upload** (they come
from the same upstream source as the roster itself), and the roster CSV is
much easier to author than the Settings CSV. Letting the label ride in the
**roster CSV header** captures it at the moment it's known, with no second
file to assemble.

### The decision (converged design)

Make the **roster CSV header the sole round-trip carrier** for these nine
labels, and **remove them from the Settings CSV** — one carrier, full
export/import symmetry, no dual-carrier precedence rule. **Internal storage
is unchanged**: labels still live in `session_field_labels`, resolved by
`app/services/field_labels.py`; the per-page UI, audit events
(`session_field_label.set` / `.cleared`), and the `ready`-lock are all
untouched. This is a change of **transport only**, not of storage.

Header grammar — a column may carry its friendly label as a suffix after the
**first** period:

```
ReviewerTag1.Tutor        → slot reviewer.tag_1, label "Tutor"
RevieweeTag2.House         → slot reviewee.tag_2, label "House"
PairContextTag1.Mentor of  → slot pair_context.1, label "Mentor of"
ReviewerTag1               → slot reviewer.tag_1, label left as-is
```

- **Split on the first period only.** The prefix (a canonical slot name —
  always period-free) is the column key; everything after the first period is
  the label (may itself contain periods, e.g. `Dept. Head`). Unambiguous.
- Applies only to the nine renamable tag slots. Non-slot columns
  (`ReviewerName`, `ReviewerEmail`, `IncludeAssignment`, `Status`, …) keep
  their bare canonical names; a stray suffix on them is ignored.

### Import semantics

Each roster parser normalises its header line **before** `DictReader`:
capture any `<Slot>.<label>` suffix, feed the **bare** canonical name to
`DictReader` (so row access + the existing missing-column checks are
unchanged), and apply the captured label.

The rule follows the roster's **wipe-and-replace** semantics — a roster
upload already deletes and reloads the entire roster (`save_reviewers` is a
"bulk wipe-and-replace", `confirm_replace`-gated), so the uploaded file is the
**complete new truth**, labels included. The label for a slot mirrors how that
slot's tag *value* is treated: populated iff the file says so, cleared
otherwise.

- **Suffix present + non-empty → `field_labels.upsert`** for that slot (a
  fourth write path into the same table the UI already uses).
- **Bare header, or the tag column absent entirely → `field_labels.clear`**
  for that slot. Consistent with the tag *values*: an omitted / blank tag
  column re-imports as NULL, so its label is cleared too. Clearing a slot
  that had no override is an idempotent no-op (no audit event). A cleared
  slot resolves back to its built-in default (`Tag 1` …).
- **Consequence — clearing a label is now possible via CSV** (upload a bare
  header), in addition to the per-page blank-to-clear gesture. Symmetric with
  export: a slot on its default exports bare, and a bare header clears — so
  the roster file is a fully faithful, lossless carrier of label state.
- **Scope of a clear is per-file / per-slot.** Uploading `reviewers.csv`
  clears/sets only `reviewer.tag_*` labels; it never touches `reviewee.*` or
  `pair_context.*` (those live in their own files). Each roster file replaces
  only its own roster and owns only its own slots.
- **Locking:** roster imports are already `409`'d on a live (`ready`)
  session, so the label writes ride the same lock — no new gate. (The label
  mutators also reject on `is_ready` in `field_labels`; the parser path
  inherits the roster-import gate.)

### Extract (export) semantics

Each roster extract emits the suffix on the header cell **when an override
exists for that slot**, bare otherwise — restoring full symmetry:

- `reviewers_extract.py:36` (`HEADER`) — `ReviewerTag{N}` → `ReviewerTag{N}.<label>`
- `reviewees_extract.py:30` — `RevieweeTag{N}` → `RevieweeTag{N}.<label>`
- `relationships_extract.py:25` — `PairContextTag{N}` → `PairContextTag{N}.<label>`

The header is computed once per file from `field_labels.resolve` (only when
`resolve_pair(...).has_override`), so a slot on its built-in default (`Tag 1`)
stays bare — the export never fabricates a "Tag 1" suffix. Header emission is
already **unconditional** (`relationships_extract.py:45` yields `HEADER`
before any data row), so a zero-pair `relationships.csv` still carries its
labels.

### Why no label is ever stranded

The nine slots map exactly onto the three roster files, and each file that
could carry a label is always present when that label can exist:

- `reviewers.csv` / `reviewees.csv` are always in the bundle.
- `relationships.csv` is required whenever `relationships_enabled`
  (rehydrate errors if it's missing — `session_rehydrate.py`), and
  `pair_context.*` labels can only exist when relationships are enabled.

So there is no state where a label has no carrier. (Observer tags are **out
of scope** — the observer roster carries a single `tag_1` with no
friendly-label affordance by design; `spec/participant_model.md` §obs. No
change here.)

### Settings-carrier removal + stale-file handling

- **Remove** `_field_label_rows` from Settings serialize
  (`session_config_io/_serialize.py:84` call + `:615` def) so exports no
  longer emit `field_labels.*`.
- **Remove** the `field_labels.` branch from Settings apply
  (`_apply_parse.py:107`) and retire `_apply_field_label.py`'s parse/apply
  helpers (or keep them dead-but-unwired if a cheaper diff — decide at
  build).
- **Stale bundles degrade gracefully.** With the branch gone, any
  `field_labels.*` row in an old / hand-authored `settings.csv` falls through
  to the existing **silent-ignore** for unknown keys (`_apply_parse.py`
  tail) — the same pattern the retired `rtds[` keys already rely on. No
  error; labels from old settings files are simply dropped (re-export to
  recover them in the new location).
- **This is a breaking change to the `settings.csv` contract** (rows
  removed). The app's pre-deployment / no-real-traffic posture (the basis
  that justified the `/reviewer`→`/me` hard rename) makes a clean cutover
  acceptable; call it out in the PR + spec so it's a deliberate decision, not
  a surprise.

### Rehydrate

Rehydrate already parses the three roster CSVs for tag **values**. Route them
through the **same** roster parser so the label capture comes along for free
— do **not** fork a second parser or add a rehydrate-specific label path. The
Settings-side label application simply disappears; no new rehydrate wiring
beyond ensuring the shared parser is the one rehydrate calls.

### Judgment calls — decided

1. **Bare header = clear**, consistent with the roster's wipe-and-replace
   semantics (the uploaded file is the complete new truth; a bare header is
   the label analogue of a NULL tag value). Clearing is therefore possible via
   CSV as well as the UI. *(Decided 2026-08-20 — overrides the initial
   "leave-as-is" lean once it was confirmed roster import is a full replace.)*
2. **Stale `settings.csv` `field_labels.*` = silent-drop** (matches the
   `rtds[` precedent), optionally a debug log.
3. **Clean cutover** of the settings contract (no dual-carrier transition
   window); documented as deliberate; fails gracefully (stale keys ignored,
   never an error).

Do **not** leave labels in Settings "just in case" — that reintroduces the
dual carrier this item exists to remove. The roster header is the sole
carrier.

### Scope / blast radius

- **Header-suffix helper (new, shared).** One small `split_field_label_header`
  helper (canonical prefix + optional label) used by all three parsers +
  all three extracts. Natural home: `csv_imports.py` (or a tiny sibling), so
  `relationships.py`'s parser can import it too.
- **3 roster parsers:** `csv_imports.parse_reviewer_csv` (`:204`),
  `csv_imports.parse_reviewee_csv` (`:308`),
  `relationships.parse_relationship_csv` (`relationships.py:52`) — normalise
  header + capture + `field_labels.upsert`.
- **3 roster extracts:** compute the per-slot header suffix from
  `field_labels.resolve_pair`.
- **Settings I/O:** remove serialize + apply of `field_labels.*`.
- **Rehydrate:** confirm it consumes the shared parser (no new label path).
- **Tests:** header round-trip per entity (set → export → re-import → same
  label); **bare header clears** (and absent tag column clears); first-period
  split with a period-bearing label; a slot on its default exports bare;
  settings.csv no longer emits `field_labels.*`; stale `field_labels.*`
  silently ignored; rehydrate carries labels from roster files; observer
  roster unaffected.

### PR ladder (each slice independently shippable)

1. **Shared helper + Reviewers proof slice.** Add
   `split_field_label_header`; wire it into `parse_reviewer_csv` (import
   capture → upsert) **and** `reviewers_extract` (emit suffix). Full
   set→export→re-import round-trip on reviewers only; Settings CSV still
   carries all nine labels (unchanged) so nothing regresses. Lands the
   grammar + the round-trip pattern on one entity.
2. **Reviewees + Relationships.** Same treatment for
   `parse_reviewee_csv` / `reviewees_extract` and
   `parse_relationship_csv` / `relationships_extract`. All nine slots now
   round-trip via roster headers **and** (still) via Settings.
3. **Retire the Settings carrier.** Remove `field_labels.*` from Settings
   serialize + apply; confirm stale-key silent-ignore; confirm rehydrate now
   sources labels from the roster parsers. Roster header becomes the **sole**
   carrier. (Land last so 1–2 de-risk the new carrier before the old one is
   removed.)
4. **Docs.** `spec/csv_contracts.md` (header grammar + bare-header-clears rule),
   `spec/roundtrip_coverage.md` (carrier moved Settings→roster header,
   symmetry restored), `spec/settings_inventory.md` (drop `field_labels.*`
   from the Settings-CSV inventory). Fold into PR 3 or land alongside.

### Definition of done

- A reviewer / reviewee / relationships CSV with `<Slot>.<label>` headers
  imports the tag values **and** sets the friendly labels; a bare header (or
  absent tag column) **clears** that slot's label — consistent with the
  roster's wipe-and-replace semantics.
- Each roster extract re-emits the operator's labels in its header; a
  download → edit → re-import preserves them.
- `settings.csv` no longer contains `field_labels.*`; an old bundle carrying
  them imports without error (labels silently dropped) and rehydrate sources
  labels from the roster files.
- The per-page label editor, `session_field_labels` storage, the resolver,
  audit events, and the `ready`-lock are all unchanged.
- `spec/csv_contracts.md` / `roundtrip_coverage.md` / `settings_inventory.md`
  updated; full suite + `ruff` green.

### Open questions

- **PR 3 `_apply_field_label.py`** — delete outright vs leave dead-but-unwired
  for one release. Lean: delete (pre-deployment; no value in dead code).
- **Header suffix on *non-override* slots in the UI-facing preview** — the
  Setup-page preview tables resolve labels from the DB, not the CSV, so they
  are unaffected; no change needed. (Noted to pre-empt the question.)

---

## Item 2 — Light / dark Display mode (chrome toggle)

**Status: ✅ complete 2026-08-21 (W1–W8; dev-slot QA signed off).** The
control landed as a *chrome toggle* (not the `/operator/settings` card, which
was retired). Full detail + the W1–W8 ladder live in the retired working doc
`guide/archive/ux_theme.md`; the shipped behaviour is specced in
`spec/settings_inventory.md` §7 (`rrw-theme`) + `spec/visual_style_rrw.md`
("Light / dark mode"). Two decisions shaped it:

- **Chrome, not settings** — participants never see `/operator/settings`, so a
  settings-only control can't reach them. The toggle becomes a shared
  `_partials/theme_toggle.html` **two-segment pill `[☀ Light | 🌙 Dark]`** in the
  `.chrome-user` of all three top bars (operator chrome, `reviewer/_top_bar.html`,
  `review_surface.html`). The scaffolded settings Display-mode card + its test
  are removed as part of the wiring slice.
- **Two states, not three** — the `System` / OS-follow option was dropped
  (2026-08-20); default is Light, Dark is an explicit `data-theme="dark"`, no
  `prefers-color-scheme` block.

Everything else (browser-local mechanism, the W1–W8 ladder) stands. The full,
full record lives in **`guide/archive/ux_theme.md`** ("UX placement — settled" + the
punch-list). The scaffold history below is kept for reference but the settings
card is no longer the deliverable.

**Original status (historical): scaffold slice landing first (this plan + the
placeholder card).**

### The opportunity

`/operator/settings` today stacks full-width cards: Email send (SMTP),
**Date & time** (per-operator default display timezone), and a Clear-all
Danger Zone. The app is **light-only** — `base.html` defines a `:root`
token palette (~28 colour tokens, ~389 `var()` uses) but has no dark theme
and no user control. Add an operator-facing **Display mode** control
(light / dark / follow-system) and, while there, tighten the settings-page
layout so the two "personal preference" cards sit side by side.

### The layout change (scaffold)

- **Date & time** card → **half-width, flush left**, moved into a
  `.bottom-grid` (the canonical `1fr 1fr` half-width pair from `base.html`).
- **Display mode** card → **half-width, flush right**, the right cell of the
  same grid.
- The Email send (SMTP) card (above) and the Clear-all Danger Zone (below)
  stay **full-width**; only the two preference cards pair up.
- **Scaffold-first** (`CLAUDE.md` → "Consequential UI lands scaffold-first"):
  the Display mode card lands as a **static placeholder** — real heading +
  copy + the three inert options (System / Light / Dark) — before any
  behaviour. This slice ships the layout + placeholder only.

### The wiring (follow-up slices)

> **Sweep + punch-list: `guide/archive/ux_theme.md`.** That doc records the full
> theming sweep (base.html's 28 tokens + 118 remaining raw-hex usages, the
> non-base light-islands, and the undefined shadow-token vocab on the
> instruments page) and the W1–W8 code punch-list. **Purely browser-local
> confirmed — no backend work** (no route/service/model/migration).

The card offers **System (default) / Light / Dark**:

- **System** follows the OS via `@media (prefers-color-scheme: dark)`.
- **Light / Dark** stamp `data-theme="light"` / `"dark"` on `<html>`, which
  wins over the media query.

**Decision — browser-local, not a DB column.** The choice persists in
`localStorage` and applies via `data-theme` on `<html>`; the card is pure
progressive-enhancement JS (no POST form, no Save button — it applies
instantly), matching how the app already stores UI state (column-visibility
chips, sort prefs). *Rationale:* no migration, applies before auth resolves,
no round-trip. *Tradeoff:* the preference is per-browser, not per-account
(doesn't follow the operator across devices) — acceptable for a display
preference; revisit only if operators ask for it to sync.

**No-FOUC.** A tiny synchronous inline script at the top of `base.html`'s
`<head>` reads `localStorage` and sets `data-theme` **before first paint**,
so there's no light flash on a dark-mode load.

**Dark palette is the real work — and why we scaffold first.** For the
control to actually do anything, a dark theme must exist. `base.html` is
*mostly* tokenised but still carries **~167 hardcoded hex colours** that
would become light-coloured islands under a dark palette. So the wiring
splits into:

1. **Tokenise sweep** — replace the ~167 stray hexes in `base.html` with the
   existing `:root` tokens. Mechanical, no visual change in light mode; pure
   prep, independently reviewable.
2. **Dark palette** — define dark values for the ~28 colour tokens under the
   three guarded blocks (`:root` stays the light palette; redefine under
   `@media (prefers-color-scheme: dark)` guarded as
   `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`
   so an explicit toggle wins both ways). System-follow works once this lands,
   even before the toggle.
3. **Wire the card** — the System/Light/Dark control writes `localStorage` +
   sets `data-theme`; the no-FOUC head script; the card reflects the active
   choice (and a "System" option reads `prefers-color-scheme` for its live
   preview).

### Scope / blast radius

- `app/web/templates/operator/operator_settings.html` — wrap Date & time +
  the new Display mode card in a `.bottom-grid`; add the placeholder card
  (scaffold), then the control + inline JS (wiring).
- `app/web/templates/base.html` — the no-FOUC head script (wiring), the
  tokenise sweep, and the dark token blocks.
- No route / service / model change for the browser-local design (the
  existing `GET /operator/settings` render is untouched; no new POST).
- **Tests:** the settings page still renders with the new card + grid
  (extend the existing settings render test); `node --check` on the inline
  JS (per the repo's inline-JS test convention); a dark-token presence check
  on `base.html` if useful. No Python behaviour to unit-test for the
  browser-local path.

### PR ladder

1. **Scaffold + the `#fff` split** *(this slice)* — layout (Date & time →
   half-width left) + Display mode **placeholder** card (half-width right;
   System/Light/Dark options rendered but inert); plus the dark-critical
   tokenise step: split every raw `#fff` in `base.html` into `--bg-card`
   (`background:` — card surfaces, darken in dark mode) vs `--text-on-accent`
   (`color:` — white text on accent controls, stays light). Value-preserving
   (light mode byte-identical); no behaviour.
2. **Tokenise sweep (remainder)** — the accent / border / one-off hex colours
   → tokens (value-preserving; some slate / violet one-offs get new tokens).
   Light mode unchanged. **Delicate:** must not corrupt the ~24 token
   *definitions*, so it's a per-site pass, not a bare global replace.
3. **Dark palette** — dark values for the token set under the guarded blocks
   + the no-FOUC head script; System-follow live. **Needs dev-slot visual
   QA** (colour correctness across cards / pills / banners / tables can't be
   verified in the test suite); any raw-hex sites left after step 2 show as
   light islands and get mopped up here.
4. **Wire the card** — the toggle writes `localStorage` + `data-theme`;
   card reflects the choice (System reads `prefers-color-scheme`).

### Definition of done

- Settings page shows Date & time (half-width left) + Display mode
  (half-width right) as a `.bottom-grid` pair; SMTP + Danger Zone stay full
  width.
- Choosing Light / Dark / System re-themes the whole app instantly and
  persists across reloads (browser-local); no light flash on a dark load.
- No route/model/migration; full suite + `ruff` green.

### Open question (for the wiring slices)

- **Browser-local vs per-operator DB column** — this plan commits to
  browser-local (above). Flag if you'd rather it sync per-account (that adds
  a `users` column + migration + a POST, and makes the card a normal
  Save-form).
- **A chrome quick-toggle** (top-right user menu) in addition to the card —
  out of scope for Item 2 unless requested; the card is the deliverable.

---

## Item 3 — Danger Zone hardening (visual + gating + coupling) — ✅ shipped

Three refinements to the Session Home Danger Zone card, found while reviewing
its behaviour.

**The problems.**
- **Delete Data was ungated.** Unlike Delete session, Delete Data had no
  lifecycle gate on either the confirm checkbox or the `/delete-data` route, so
  wiping every live reviewer response on an Activated session was one tick +
  click away (frontend and backend agreed — it was intentional but unsafe).
- **The card's surface didn't read as "needs care."** The danger-zone card
  bordered amber but had a white interior, diverging from the lock card (which
  is the sibling "needs care" surface).
- **The two confirms were independent.** Deleting the whole session inherently
  deletes its data, but ticking Delete session didn't reflect that.

**The decisions (shipped).**
- **Gate Delete Data like Delete session** — confirm checkbox `disabled` while
  `is_ready` + a lock note + `_require_editable()` on `/delete-data`. Responses
  only exist once Activated, so deletion is a pause-first workflow (revert
  preserves the `Response` rows). (PR #2026.)
- **Unify the card surface** — the danger-zone card adopts the lock-card
  treatment: `accent-amber-dark` border + `accent-amber-bg` infill + amber H2.
  Both "needs care" cards now share one surface; the outline-red Destructive
  button inside still marks the action. (PR #2025.)
- **Couple the confirms, one-directional** — ticking Delete session marks
  Delete data selected + inactive (checkbox checked + disabled, button
  disabled); unticking restores it. Ticking Delete data leaves Delete session
  available. Progressive-enhancement JS; degrades safely. (PR #2027.)

**Done.** Specs updated (`session_home.md`, `operator_button_audit.md`,
`visual_style_rrw.md`/`visual_style_general.md` for the card surface); full
suite green. JS toggle needs a dev-slot click post-deploy.

## Item 4 — Button treatment refinements — ✅ shipped

Two button-treatment fixes surfaced by the dark-mode preview harness (Item 2).

- **Secondary outline → `text-secondary`.** The default button's outline was the
  very light `border-default`, which read weak. Now a medium grey — one shade
  lighter than the `text-primary` label — stronger without going near-black.
  (PR #2023, walking back the too-dark `text-primary` outline from #2022.)
- **Alert label readable in dark.** The filled-amber Alert button
  (`.btn.danger-solid`) used `text-on-accent` (white), unreadable on the
  light-amber fill the amber tokens take in dark mode. New `--text-on-amber`
  token — white in light (unchanged), dark in dark. (PR #2024.)

**Done.** `base.html` + `spec/ui_elements.md` §6 updated; full suite green.
Colour correctness needs a dev-slot eyeball.

---

## Item 5 — Theme customizer (developer designer) — ✅ v1 shipped 2026-09-04

The developer-facing half of the theme-customizer design — **full plan in
`guide/theme_customizer.md` ("Plan A — First")**. Data-driven / app-agnostic
(parses primitives, semantic maps, and clusters from `base.html` itself, so it
drives any tokens.css of the same shape — the portability kernel, decision #6).
Lives in the `tools/` harness and is not wired into the app. (The operator-facing
**Stretch** half is deferred — `guide/deferred_consolidated.md` Part A "Operator
theming"; it reuses this item's editor core.)

**v1 (shipped, PRs #2065–#2083).** `tools/theme_customizer.gen.py` →
`tools/theme_customizer.html`, a three-part visual designer:
- **Part A — Preview.** The real component gallery (chrome, nav, cards, forms,
  buttons, pills, banners, table…) in top-down page order, in a left column
  pinned to five primitive-cards wide; the actual screen elements, so tokens are
  designed against them.
- **Part B — Tokens.** Seeds (five chromatic families, OKLCH delta-shift),
  Primitives (grouped by family; edit any swatch, live repaint), Contrast (AA)
  badges, and Semantic remaps (repoint a role to a primitive or, deliberately,
  another semantic — the `@coupled` chain — per theme).
- **Part C — Selection.** Click any coloured element in Part A → it reflects
  (a) the element + colour facet, (b) the semantic token painting it,
  (c) the primitive that token resolves to in the active theme (with the
  coupling chain), and (d) what else the token covers. Click a facet's swatch
  → a primitive picker repoints that token live. A build-time registry maps
  every element+facet to its token and is **self-verified against the element's
  computed colour in both themes** (0 mismatches).
- **Toolbar.** Light/Dark, Undo (per-gesture history), Save + Revert (a local
  `localStorage` checkpoint that auto-restores on reload — intermediate saves
  without exporting), Load defaults, Export / Import JSON
  (`{version, primitives, semantic:{light,dark}}`, ported 1:1 into `base.html`).

Along the way the tool surfaced and fixed real `base.html` gaps (nav tab-strip
backgrounds tokenized; nav chrome + active tab take `--surface-page`; primitive
families rationalized — sky→`--blue-cyan-*`, danger→`--red-warm-*`, neutrals as
one family) — all value-preserving except the intentional nav-chrome shift.

**Deferred / optional follow-ons:** Ctrl/Cmd-Z + Redo; sort the Neutral group
light→dark; editing a primitive's own value from the picker; the operator-facing
Stretch (see deferred_consolidated). Original slice notes below.

**What.** Grow the theme-preview harness into a visual **designer** for the
light + dark palettes: seed-and-derive (OKLCH) editing with live repaint,
contrast (AA) badges, load-from-app / a named-save library, and **export JSON**.
The JSON's flat `tokens` map lands 1:1 on `base.html`'s `:root` /
`:root[data-theme="dark"]` blocks, so a coding agent ports a finished design
into the template mechanically — the dark-mode port, formalised.

**Pre-step (derivation-fidelity decision).** Re-tune `base.html`'s current token
values to be **formula-clean** — adjust the shipped light/dark palette so
`derive(default_seed)` reproduces every token with no per-token overrides in the
defaults. A deliberate, small visual change; author it in the harness and
dev-slot-QA it. Land this first, then build seed-derive on a clean base.

**Slices** (per `theme_customizer.md` Plan A):
- **✅ Slice 1 (shipped) — manual editor.** `tools/theme_customizer.gen.py`
  (+ shared `tools/_harness_common.py`, which `theme_preview.gen.py` now also
  uses) → `tools/theme_customizer.html`: every colour token editable with live
  repaint, edit light + dark separately, load-defaults / Re-read-`base.html`
  (file-picker) / named-save library / Export + Import JSON.
- **✅ Slice 2 (shipped) — contrast (AA) badges.** A live WCAG-ratio + AA
  pass/fail badge per bg/text pair (16 pairs) for the active theme, updating as
  tokens change. (Surfaces e.g. muted-on-card at 2.54:1 — intentionally-low
  decorative text.)
- **✅ Slice 3 (shipped) — seeds + OKLCH derivation.** Six per-hue seed
  controls (blue / green / amber / red / violet / sky) above the gallery. Moving
  a seed re-hues its whole family by the OKLCH delta between the anchor's old and
  new value, applied to each member and **tapered by `room = 1 − |2·L − 1|`** so
  extreme-lightness members (pale bg tints, near-black darks) don't clip the sRGB
  gamut; the anchor lands exactly (WYSIWYG). Because the shift is *relative* to
  the current hand-tuned values, `base.html` stays untouched — the risky
  "formula-clean re-tune" pre-step is **not needed** (delta-shift supersedes it).
  Each editor chip also dropped its redundant static swatch (the `<input
  type="color">` is the sample).
- **✅ Slices 4+ (shipped) — the designer proper.** Part A/B/C restructure;
  click-to-reflect + primitive-picker editing in Part C; Save/Undo/Revert with
  localStorage; app-agnostic data-driven parsing; primitive-family
  rationalization. See the v1 summary above.

---

## Item 6 — Semantic colour tokens (two-tier reorg) — ✅ shipped 2026-08-23

**Status: ✅ complete (2026-08-23).** `base.html` is now fully two-tier —
**79 descriptive primitives + 103 role-named semantic tokens** (16 non-colour
scale tokens unchanged); every component and template inline style consumes
only semantic tokens, and all flat colour-named tokens are retired. Every
slice was value-preserving (verified by hex re-resolution) with the suite
green throughout (2,697 passing). Catalogue: `spec/color_tokens.md`; design +
decisions archived at `guide/archive/semantic_tokens.md`.

Shipped across **17 PRs**: the plan + decisions (#2047 plan · #2048 blast-radius
log · #2049 portability goal · #2050 independent-slot + coupling + completeness
· #2051 decisions 4–6), then the migration (#2052 Slice 1 two-tier tokens
introduced · #2053 Buttons · #2054 Status · #2055 roles+lifecycle · #2056 cards
· #2057 navigation · #2058 links/focus/config/selection/icons · #2059
surfaces+text · #2060 misc chips/signals · #2061 template inline styles · #2062
cleanup — dead-code removal + flat-def retirement + spec rewrite).

Decisions (all in `guide/archive/semantic_tokens.md`): 1–3 keep-separate
(independent-slot rule); 4 descriptive primitive names (`--blue-strong`); 5 one
palette, dark `:root` remaps semantics (no parallel dark set); 6 namespace with
`[P]`/`[A]`, kernel extraction deferred — no rush.

**Tooling slice — ✅ done under Item 5 (v1 shipped 2026-09-04):** the `tools/`
customizer / preview were reworked two-tier, app-agnostic + data-driven (parsing
primitives / semantics / clusters from `base.html` — the portability kernel).

Historical detail below (kept for the record).

### The problem

The palette is one flat list of **colour-named** tokens (`--accent-blue`,
`--bg-page`, …; catalogued in `spec/color_tokens.md`). Naming by colour
instead of role couples unrelated elements — `--accent-blue` is the link
colour *and* the Primary-button fill *and* the focus ring, so they can't
diverge. The theme-customizer "one token, many zones" friction (Item 5) is
the symptom of this missing semantic layer.

### The decision

Move to a **two-tier** system (confirmed with the author; plan-first):

- **Tier 1 — primitives** (`--blue-600`, `--gray-500`, …): the raw colour
  scale, named by hue + step, theme-agnostic.
- **Tier 2 — semantic** (`--btn-primary-bg`, `--surface-card`,
  `--status-warning-bg`, `--text-link`, …): named by role; redefined per
  theme; **the only thing components consume.**

Full taxonomy (eleven element→role clusters), naming convention, the
token-by-token mapping, and the migration order live in
`guide/archive/semantic_tokens.md` — the authoritative plan for this item.

**Portability goal (author directive).** Build the theme machinery — this
token system *and* the customizer (Item 5) — **reusable by other apps of the
same look and feel**. Concretely: split Tier 2 into a **portable core**
(surfaces / text / borders / buttons / status — `[P]`) and an **app-specific
layer** (participant roles, lifecycle, nav, config, tints — `[A]`) that
aliases the core; keep the primitives + portable core **extractable** (a
delimited block now, a `tokens.css` partial candidate later) so a new app
lifts them and swaps primitive values to rebrand; and make the customizer
**app-agnostic** (labels / clusters / seeds data-driven from the token file,
JSON as the interchange). Reusable kernel = {primitives + portable-core
semantics} + {the app-agnostic customizer}. See `guide/archive/semantic_tokens.md`
§"Reusability across apps".

**Independent-slot principle (author directive).** Every identified semantic
slot is its own token, mapping to a primitive by default; two slots that
share a value today still get separate tokens so either can diverge later
without a rename. **Deliberate coupling is allowed but must be marked** — a
slot may be defined in terms of another (`--x: var(--y)`) only as a flagged
choice (`@coupled` marker + registry entry), never as an unmarked chain. This
settles former open decisions 1–3 (soft-error, success two-tone,
roles/lifecycle) toward **keep separate**; only primitive naming, dark
primitives, and portability-factoring remain open. See
`guide/archive/semantic_tokens.md` "Rules of the model" + "Deliberate couplings".

### Scope / blast radius (measured)

Presentation-layer only — **0** references in `app/**/*.py`, **0** in
`tests/`, no DB/behavior. `base.html`: **94** token definitions (47 light +
47 dark) + **505** `var(--…)` call-sites. **~90** more inline `var()`
call-sites across **17** templates (dominated by
`operator/instruments_index.html`). Plus `tools/` (customizer / preview) and
the palette docs. ~**595** call-sites total, ~85% in `base.html`, all
mechanical value-preserving swaps. No automated visual coverage → each slice
needs dev-slot QA.

### PR ladder

Per `guide/archive/semantic_tokens.md` "Migration strategy":

1. **Slice 1 — both tiers as inert aliases.** Add the primitives + full
   semantic layer to `:root` + `:root[data-theme="dark"]`, reproducing
   today's values exactly; nothing consumes them yet. Additive, visually
   inert (scaffold-first).
2. **Slices 2…N — migrate consumers, one cluster per PR** (buttons → status
   / pills / banners → roles + lifecycle → cards + nav → config + focus →
   surfaces + text last). Template inline styles migrate with their cluster.
3. **Retire the flat tokens** once nothing references them.
4. **Tooling + docs slice** — two-tier customizer; rewrite
   `spec/color_tokens.md`; retarget `_harness_common.LABELS`.

### Decisions — all resolved (2026-08-23); Slice 1 unblocked

Full text in `guide/archive/semantic_tokens.md` "Decisions". (1) soft-error, (2)
success two-tone, (3) roles/lifecycle → **keep separate** (independent-slot
rule). (4) primitive naming → **descriptive** (`--blue-strong`). (5) dark
primitives → **one palette; dark `:root` remaps semantics** (no parallel dark
set). (6) portability → **namespace now, extract a clean kernel at the end,
no rush** (no second app yet); customizer data-driven in the tooling slice.

### Definition of done

`base.html` and all templates reference **only** semantic (Tier-2) tokens;
primitives are the only place raw hex lives; the customizer, preview, and
`spec/color_tokens.md` are two-tier; every slice value-preserving and
dev-slot-verified.

---

## Item 7 — Sweep follow-through (the 2026-09-05 drift findings)

**Opened:** 2026-09-05 · **Source:** `guide/sweep_2026-09-05_spec-docs.md` §2

### Opportunity

The first sweep under `guide/sweep_template.md` filed **eight
update-in-place findings** across ten live `spec/` + `docs/` files. By that
sweep's own scope rule the fixes are ordinary follow-on work rather than
part of the item that produced them, and this segment's `## Future items`
section is the landing place for exactly that kind of small refinement.

Six of the eight are **carried from `spec_sweep_18Aug.md`**, where they
were filed as "minor / cosmetic (non-actionable)" and then never re-read
for eighteen days. Two of those six were mis-filed: one had the drift on
the wrong side entirely (the code comment was wrong, not the spec), and
one was recorded as smaller than it is. A finding that survives two sweeps
unactioned is not minor, it is unattended.

None is catchable by a constant — `test_doc_conventions.py` and
`test_spec_coverage.py` both pass on all ten files today.

### Decision

Fix all eight, in three slices grouped **by the kind of judgement each
needs** rather than by file: mechanical reference corrections, then spec
content that understates or contradicts the code, then the one finding
that needs a decision before any edit is right.

**Rejected.** *One PR per file* — ten PRs for ten small edits, no reviewer
benefit; the grouping lets a reviewer check a whole class at once.
*Folding the fixes into the sweep's own PR* — the sweep recommends and a
person decides; collapsing the two makes the sweep an agent that edits,
which `constitution.md` Article IV rules out. *Leaving them as sweep
findings only* — the exact failure the carry-forward section exists to
catch; reproducing it in the first cycle after building the mechanism
would be perverse.

### Semantics

- **A stale module path is prose, not a link.** The five references to
  `app/services/assignments.py` and friends still resolve through the
  package `__init__`; the fix names the package, restructures nothing.
- **Finding 2.1 changes code, not a spec.** The docstring in
  `app/web/routes_operator/_preview_surface.py` misattributes its segment
  (it says 18Q; the file was created 2026-05-28 and 18Q is Blob storage).
  The spec it was blamed against is correct. No behaviour, no tests.
- **Finding 2.4 is not a rename.** `spec/visual_style_general.md` is the
  *portable* design system, so its 17 `accent-*` names may be
  illustrative by intent. Either outcome — repoint them to the post-19C
  vocabulary, or state in the doc that `spec/color_tokens.md` is
  authoritative and these are examples — is a legitimate close. Picking
  silently is not.
- **Nothing here is a contract change.** Every edit makes a document match
  code that already shipped. If one turns out to need a code change
  instead, that is a `## Status` entry, not a quiet widening.

### Judgment calls — decided

- **2026-09-05 — grouped by judgement kind, not by file or folder.**
  "Are these references dead?" and "does this paragraph match the code?"
  are different reading jobs; mixing them makes both harder.
- **2026-09-05 — finding 2.4 lands last, on its own.** It is the only one
  that cannot be settled against the repository alone, so it must not
  block the seven that can.
- **2026-09-05 — a path merely *mentioned* in a `Doc impact` bullet is not
  backticked.** `close_check.py` treats every backticked `spec/`/`docs/`
  path under the heading as a commitment; naming a retired or neighbouring
  file in passing would commit this segment to editing it. C2 caught
  exactly that in this item's first draft. Backticks there mean "I will
  change this file".
- **2026-09-05 — `spec/blob_storage.md` is deliberately not a finding.**
  It references a module never written, but it is a labelled stub for
  deferred infrastructure. Recorded in the sweep's *Retire* section so the
  next sweep does not re-propose it.

### Blast radius (measured)

| What | Count | Command |
|---|---|---|
| Findings to action | 8 | `guide/sweep_2026-09-05_spec-docs.md` §2 |
| Live `spec/` + `docs/` files touched | 10 | the findings' targets, deduplicated |
| Code files touched | 1 (docstring only) | finding 2.1 |
| Stale `app/services/*.py` references | 5 across 5 files | `grep -rln '<mod>.py' spec/ docs/ --exclude-dir=archive` |
| `accent-*` names in `visual_style_general.md` | 17 | `grep -oE "accent-[a-z-]+" spec/visual_style_general.md \| sort -u \| wc -l` |
| Carried from the 2026-08-18 sweep | 6 of 8 | that sweep's §C, reconciled in the new sweep's §0 |

### PR ladder

1. **PR 1 — dead and wrong references.** Findings 2.1, 2.3, 2.7, 2.8: the
   `_preview_surface.py` segment misattribution; five stale
   `app/services/*.py` paths renamed to their packages; the security doc's
   pointer at the authentication doc it absorbed; and
   ~~`spec/visual_style_rrw.md`'s two references to specs consolidated away
   in 2026-05~~ — **moved to PR 2 at build; see Status.** All verifiable
   against the repository. Must not touch spec *content*.
2. **PR 2 — spec content that understates or contradicts the code.**
   Findings 2.2, 2.5, 2.6: `lifecycle.md` §1 showing three of five states;
   `operator_ui_concept.md`'s user card omitting the `(super admin)` /
   `(sys admin)` suffix `base.html` renders; `domain_assumptions.md`'s
   "1-6 Instruments" implying a cap that is not in code. Must not touch
   `visual_style_general.md`.
3. **PR 3 — `spec/visual_style_general.md` (finding 2.4).** Lands whichever
   outcome the author picks, and records the choice in `## Status`.

### Definition of done

- All eight findings closed in `guide/sweep_2026-09-05_spec-docs.md`'s
  ledger — actioned, or declined with a reason recorded there so the next
  sweep carries the decision rather than the finding.
- No `app/services/*.py` path in live `spec/` or `docs/` names a module
  that is now a package.
- `spec/lifecycle.md` §1 shows all five states.
- The `visual_style_general.md` decision is recorded in `## Status`, not
  only in the diff.
- `python3 tools/close_check.py 19C` exits 0 with the Item 7 bullets
  honoured.

### Open questions

- Finding 2.4: repoint the 17 names, or declare them illustrative and
  point at `spec/color_tokens.md`? **Decided by the author**, before PR 3.
- Should the sweep document gain a findings ledger later sweeps read, or
  should closure be tracked only in this item? Leaning on the sweep
  document, since that is where the next sweep will look — but it makes a
  dated snapshot into a living file. Decide at PR 1.

### Out of scope

- Re-sweeping the 51 files the 2026-09-05 sweep did not read — the next
  sweep's job, on its own trigger.
- The orphan-spec test and a `CROSS_CUTTING` allowlist — still the
  archived 19A Item 3's deferred question, needing several sweeps'
  evidence.
- Any code change beyond the one docstring in finding 2.1.

---

## Status

**2026-09-05 — Item 7 PR 1.** Two of the sweep's own findings did not
survive re-verification at build. Both were filed by the mechanical
dead-reference pass, which can see that a path does not exist but not
*why* the document names it — the sweep's rule is that a finding is
verified before it is filed, and these two were not verified closely
enough.

- **Finding 2.7 declined.** `docs/security_posture.md` reads "Absorbs the
  identity-subsystem write-up (formerly `docs/authentication.md`, retired
  2026-08-19)". That is a correct, dated provenance note, not a pointer a
  reader could follow and be let down by. Its manifest bullet carries a
  reasoned waiver rather than being deleted, so the next sweep inherits
  the decision instead of re-filing the finding.
- **Finding 2.8 re-diagnosed and moved to PR 2.** The two specs
  `visual_style_rrw.md` names are marked "(forthcoming)" and have **never
  existed** — zero commits, ever. They are unwritten aspirations from an
  old plan, not specs "consolidated away in 2026-05" as the sweep claimed.
  Repointing them to the live specs that own those surfaces today is a
  content judgement about what those documents actually cover, so it
  belongs in PR 2, not in a slice whose rule is "must not touch spec
  content".

**Shipped in PR 1:** finding 2.1 (the `_preview_surface.py` docstring now
attributes the 2026-05-28 follow-on to Segment 11F, PRs #1530 / #1531 —
verified against the commit that created the file) and finding 2.3 (five
`app/services/*.py` paths across five specs renamed to their packages).
The same module names in `docs/status.md` were left alone: it is a dated
timeline, and what a module was called in 2026-05 is history.

**Decided here (the item's second open question):** closure is tracked in
the sweep document's own ledger, since that is where the next sweep will
look. It makes a dated snapshot into a living file, which is the cost.

**2026-09-05 — Item 7 PR 2, landed in the same pull request as PR 1.**
The ladder planned two PRs; both slices ship as two clearly separated
commits on one branch instead, because they were requested together and a
merge round-trip between them would buy nothing — the reviewer benefit
the split exists for (checking one class of judgement at a time) is
preserved by the commit boundary.

Shipped: finding 2.2 (`lifecycle.md` §1 now draws all five states,
including the archive edge from any non-archived state, which the state
table already documented); 2.5 (the user card's `(super admin)` /
`(sys admin)` suffix, super winning when both apply); 2.6 (the 1-6
instrument range restated as typical usage — nothing in code bounds it);
and 2.8 as re-diagnosed above, repointed to `spec/instruments.md` and
`spec/reviewer-surface.md`. Those two content lists are kept as **open
design notes**, not moved: neither spec covers large-table ergonomics or
the pacing guidance today, and repointing a promise to a document that
does not keep it would trade one wrong reference for another.

Item 7 now waits only on finding 2.4 (PR 3) and the author's decision on
`spec/visual_style_general.md`.

**`close_check.py 19C` exits 0 anyway, and should not be read as "Item 7
is done".** Finding 2.4 is outstanding, but its manifest bullet's path,
`spec/visual_style_general.md`, passes C3 on commit `bf2d5ad8` — Item
**3**'s danger-zone work from 2026-08-20, inside the same segment window.

This is the segment-level analogue of the item-window false pass fixed in
the archived 19A Item 2 PR 2, and unlike that one it is **inherent to the
documented semantics** rather than a bug: C3 asks whether a path was
touched inside the segment's window, and a segment-level manifest spanning
seven items over three weeks gives an older item's edit every chance to
satisfy a newer item's bullet. The item-level fix worked because an item
has its own heading to date from; a `(Item n)`-tagged bullet has no such
anchor today.

Not fixed here — it is a change to `close_check.py`, not to this segment,
and it needs design thought (dating a bullet from the heading of the item
its tag names is the obvious candidate). Recorded so the next reader does
not take a green 19C as evidence that its newest item has landed.

**2026-09-05 — Item 7 PR 3, closing the item.** Finding 2.4 decided in
favour of **declaring the names illustrative**, against repointing them.
The deciding argument was the customizer, not tidiness:
`tools/theme_customizer.gen.py` reads `app/web/templates/base.html`
directly and exports JSON ported back into it, so the refinement loop is
`base.html` ⇄ customizer with `spec/color_tokens.md` as the hand-synced
catalogue. Every *other* document that names tokens is therefore a copy of
an authority it does not hold — and this one drifted three days after the
19C Item 6 reorg, which is the failure Article V names. Repointing would
have created a fourth copy and guaranteed the next drift; it would also
have put RRW-specific identifiers into a document whose first line calls
itself portable and app-agnostic.

The palette keeps its roles and example hexes — those are portable design
decisions, and stripping them would leave a designer with nothing to act
on. What changed is one blockquote under `## Color palette` stating that
these are the system's *role* names, that `spec/color_tokens.md` is
authoritative for the shipped identifiers (it already retires the flat
`accent-*` vocabulary by name), and that values change in `base.html` or
live in the customizer. `color_tokens.md` already pointed back here, so
the pair is now consistent in both directions.

With 2.4 closed, `spec/visual_style_general.md` is genuinely edited inside
the window rather than passing C3 on Item 3's 2026-08-20 commit — the
blind spot noted above no longer masks anything for this item. It remains
true of the check in general.

**Item 7 is complete**: all eight sweep findings closed, seven actioned
and one declined with a reason. `docs/status.md` gains no row — the item
changed no behaviour, and its record lives in the sweep's findings ledger
and here.

**2026-09-05 — the blind spot is now checked, and this plan carries the
first adjudicated warning.** `tools/close_check.py` dates each
`(Item n)`-tagged bullet in a segment-level manifest from that item's own
heading, so a newer item's commitment can no longer be satisfied by an
older item's edit. Running it here now reports one warning, which this
entry adjudicates:

- `spec/ui_elements.md` (the `(done — Item 4)` bullet) was edited on
  2026-08-20 by `4a72813c` "style: soften Secondary button outline to
  `text-secondary`" — exactly what the bullet promises — while the Item 4
  heading was logged the next day, 2026-08-21, by `49a8177f` "docs: log
  19C refinements — Item 3 (Danger Zone) + Item 4 (buttons)". Honoured;
  the item was written up after its work landed. This is the retroactive
  case the check warns about rather than failing on, and it is why it
  warns: nothing in the timestamps distinguishes it from another item's
  edit.

## Future items (add as they come up)

Landing place for further small operator-facing refinements. Log new ones
here as `Item N` with the same problem / decision / scope / done-when shape,
and keep each a self-contained slice. The user will populate this list as
refinements are identified.

- **Dark-mode input background (from Item 2 QA).** In dark mode form controls
  use `var(--bg-page)`, so `<input>` / `<select>` / `<textarea>` sit at the same
  near-black as the page canvas and are delineated only by their border. A
  dedicated input-background token (a step lighter than `--bg-page`, e.g. near
  `--bg-card`) applied to `body.ui-v2 input/select/textarea` would lift them.
  Light unaffected (input bg would resolve to white as today). Small, isolated.

---

## Doc impact

- `spec/csv_contracts.md` — add the `<Slot>.<label>` header grammar for the
  three roster files; document the first-period split + the bare-header-clears
  rule (label follows the roster's wipe-and-replace semantics) (Item 1).
- `spec/roundtrip_coverage.md` — record the friendly-label carrier move
  (Settings CSV → roster CSV headers) and that export/import is now
  symmetric on the roster file (Item 1).
- `spec/settings_inventory.md` — remove `field_labels.*` from the Settings
  CSV inventory; note the carrier is now the roster headers (Item 1).
- `docs/status.md` — note the ship when Item 1 lands.
- `spec/operator_ui_concept.md` / `spec/visual_style_rrw.md` — the
  settings-page layout (Date & time + Display mode half-width pair) and the
  Display mode card + `data-theme` theming primitive (Item 2, on wiring).
- `spec/settings_inventory.md` — the browser-local `data-theme` UI-state
  primitive (Item 2, on wiring).
- `spec/session_home.md` — Delete Data locked-while-Activated (pause-first) +
  the Delete-session⊇Delete-data confirm coupling; `spec/operator_button_audit.md`
  — the Delete Data lifecycle gate; `spec/visual_style_rrw.md` /
  `spec/visual_style_general.md` — the danger-zone card adopts the lock-card
  amber surface (done — Item 3).
- `spec/ui_elements.md` §6 — Secondary outline (`text-secondary`) + the Alert
  button's `--text-on-amber` label token (done — Item 4).
- `spec/assignments.md`, `spec/setup_pages.md` — name the
  `app/services/assignments/` package, not the retired module path (Item 7).
- `spec/quick_setup_card_spec.md` — `app/services/session_config_io/`
  package rename (Item 7).
- `spec/settings_inventory.md` — `app/services/scheduled_events/` package
  rename (Item 7).
- `docs/security_posture.md` — drop the pointer to the retired
  authentication doc, whose content this file absorbed (Item 7).
  <!-- doc-impact-waived: finding 2.7 declined at PR 1 — the reference is a dated provenance note ("formerly ..., retired 2026-08-19"), not a live pointer; see Status -->
- `spec/visual_style_rrw.md` — repoint the two references to specs
  consolidated into the instruments spec in 2026-05 (Item 7).
- `spec/lifecycle.md` — §1 state diagram to show all five states, plus the
  package rename (Item 7).
- `spec/operator_ui_concept.md` — document the `(super admin)` /
  `(sys admin)` suffix on the user card (Item 7).
- `spec/domain_assumptions.md` — drop or qualify "1-6 Instruments"; there
  is no cap in code (Item 7).
- `spec/visual_style_general.md` — the finding 2.4 decision (Item 7).
