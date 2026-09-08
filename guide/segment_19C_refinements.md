# Segment 19C — Refinements

**Status: all eight items ✅ shipped** — the segment stays **open** as a home for
further small refinements. **Item 1 ✅ 2026-08-20** (friendly tag labels via
roster CSV headers; sole round-trip carrier); **Item 2 ✅ 2026-08-21**
(light/dark Display mode — chrome toggle, W1–W8); **Item 3 ✅** (Danger Zone
hardening); **Item 4 ✅** (button treatment refinements); **Item 5 ✅ v1
2026-09-04** (theme customizer — developer designer; three-part
click-to-reflect/edit designer, PRs #2065–#2083; operator-facing **Stretch**
deferred to `guide/deferred_consolidated.md`); **Item 6 ✅ 2026-08-23**
(semantic colour tokens — two-tier reorg; the app is now fully two-tier, plan
archived at `guide/archive/semantic_tokens.md`); **Item 7 ✅ 2026-09-05** (the
first drift sweep's eight findings); **Item 8 ✅ 2026-09-06** (input boundaries
— `--border-default` to `--slate-dim` for 3:1, and `.rs-help-card` off the
border token onto `--surface-muted`).
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
light→dark; editing a primitive's own value from the picker; **add / delete
primitives** (below); the operator-facing Stretch (see deferred_consolidated).
Original slice notes below.

**Add / delete primitives — deferred 2026-09-06, wanted for portability.**
v1 edits a primitive's *value* freely: each swatch in Part B carries a colour
input and a hex field, both wired to `setPrim` (live `setProperty` repaint), and
a chromatic family can be shifted wholesale from its seed. What it cannot do is
change the palette's *membership* — the primitive grid is emitted at build time
from `parse_primitives(base_css)`, and `applyActive()` walks `D.primOrder`, the
build-time name list, rather than `Object.keys(model.prims)`. So a primitive the
generator did not see is stored in the model and never reaches the DOM, and a
semantic pointed at it resolves to an undefined `var()`.

That is a real limit on the portability kernel (decision #6): a `tokens.css` of
the same shape but a *different* palette can only be explored by editing the
79 names this build happens to have. It also bit the 19C input-boundary work —
`tools/theme_variants.gen.py` *(retired 2026-09-06 with the `beyond-*` set;
see Item 8's judgment calls)* had to preview off-palette border values by
overriding `--gray-soft` / `--slate-deep` instead of adding primitives, which
dragged `--marker-neutral` along with them.

Scope when it is taken: `model.prims` becomes the authority in `applyActive`
(iterate its keys, not `D.primOrder`); Part B's grid renders from the model
rather than a build-time list; add/delete affordances with a delete guarded on
"no semantic still points here"; and the export/import contract gains nothing
new, since `{version: 2, primitives, semantic}` already carries an arbitrary
primitive map. Not gated on anything — it is deferred by priority, not by a
dependency.

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

**2026-09-08 — closed. Intended versus done, across ten items.** 19C was
planned as a holding segment for small operator-facing refinements and it
did that: every item it took on shipped, none was struck, and the two it
never started are rehomed rather than dropped. What it also did — and
this is the reason it is closing rather than continuing — is **grow past
the shape that made it useful**.

**The holding shape has three costs, and 19C paid all of them.**

1. **A plan nobody reads end to end.** Ten items over nineteen days is
   long enough that a reader looking for one decision scrolls past nine
   others. The items are self-contained, which is what made adding
   "just one more" cheap each time.
2. **A `close_check` window that means almost nothing.** The window runs
   from the manifest's first commit to the close, so 19C's spanned the
   whole of 19A, 19E and 19F. Both of its advisory notes pointed at other
   segments' work — the check cannot distinguish "touched during this
   segment" from "touched by this segment" when a segment lasts long
   enough to contain others.
3. **Pointers that rot.** `docs/status.md` promised the technical-support
   contact as *"Segment 19C Item 8"*. Item 8 is the input-boundaries
   work; the contact sat unnumbered in Future items, unbuilt. The
   reference was wrong the day it was written and nothing checks a
   cross-file pointer against a plan's numbering. A segment that keeps
   gaining items keeps inviting that error.

**Both notes were adjudicated, not actioned.** `_results.py` was touched
by 19F PR 4, which declared `spec/participant_model.md` in its own
manifest. `_preview_surface.py` was touched by 19C Item 7 PR 1 — and
there the change was a **docstring corrected to match**
`spec/preview_hub.md`, which was already right. A note firing on a
code→spec correction is the check doing its job and owing nothing: the
direction of the fix is what the note cannot see.

**Two items leave alive.** The theme-customizer element pass (author
intent, logged at Item 8's close) and the global technical-support
contact (moved out of Segment 20 on 2026-09-05) moved to
`guide/todo_master.md` under Upcoming → Stubs. The ledger
(`deferred_consolidated.md`) would have been the wrong home for both:
that file is explicitly work *not* intended to ship, and these are
intended — just not scheduled, and no longer parked anywhere that was
about to be archived.

**What the segment produced, in one line each:** the roster-CSV header as
the sole friendly-label carrier (1); light / dark mode (2); Danger Zone
gating and button treatments (3, 4); the theme customizer and the
two-tier token reorg it reports on (5, 6); the first drift sweep's
follow-through (7); input boundaries at 3:1 (8); and, from 19F's close
audit, the import guard and the retrospective audit card (9, 10).

**2026-09-08 — Item 10 rung 2 shipped: the card is wired, and the audit
found nothing, which is the expected result and not a verification.**
`app/web/views/_visibility_audit.py` reads every
`instrument_view_policies` row, decodes each window's pair, and reports
any cell whose mode `valid_modes_for_cell` does not allow — the same
table the editor and Item 9's import guard read, so a change to a cell's
rules cannot leave the audit checking an old copy.

**A bug the template would have hidden.** The reviewer audience is
stored as `peer_reviewer`, and `base.html` styles `.pill-role-reviewer`;
`pill-role-{{ row.audience }}` would have rendered a class that does not
exist and a pill with no styling — invisible in a review of the markup
and visible only on the page. The slug is mapped in the view, where the
fourth-seam rule puts it. Found by writing the template against the real
column values rather than against the audience names in prose.

**Three mutations, three different tests.** Making the cell check always
pass fails the three findings tests; dropping the live-first sort fails
only the ordering test; collapsing the half-set branch fails only its
own. Each mutation is caught by exactly the test that should catch it,
which is the property that says the suite is measuring three things and
not one thing three times. The ordering test picks session codes so that
alphabetical order would put the *closed* session first — otherwise it
would pass on the code alone and say nothing about liveness.

**Rendered with seeded findings rather than read.** Two findings on a
`ready` session sort above a `draft` and an `archived` one, each row
naming session, instrument, audience, cell, stored value and reason, and
the live rows carrying **Reachable now**. The empty case says "No
findings" in a sentence, because an empty table reads as *not
implemented*.

**What this item cannot claim.** It ran against a test database. The
deferral's premise still holds — the pilot has not deployed — so a green
card today means "no rows here", and there are almost no rows here. What
shipped is a check that is ready and proven against fixtures. The first
real run is the one at deploy, before any reviewee-facing window opens.

**2026-09-08 — Item 10 opened, and the deferral it lifts was wrong about
where the check should live.** The author lifted the audit ahead of its
trigger, hours after deferring it. The ledger entry is **removed**, not
copied, per the ledger's own rule for a lifted item.

**The wire-up in that entry said `tools/`. Building it showed why that
was wrong.** Every script in `tools/` is stdlib + `git` and operates on
the repo; none opens a database. More decisively, `CLAUDE.md` says the
author runs no Python, alembic or database locally, and an agent sandbox
cannot reach Azure Postgres — so a `tools/` script would have been a
deliverable **nobody could run against the data it audits**. The check
moved to a card on Sys Admin → Sessions Diagnostics: the deployed app is
the only thing holding a connection to that database, and Sys Admin is
the only surface whose audience may read across every session. **A
deferral records a decision at the moment its cost is lowest and its
information is thinnest** — the wire-up line was written before anyone
tried to write the code, and it did not survive contact.

**Rung 1 is the scaffold**, per `CLAUDE.md`'s rule for a new card: real
copy and layout, sample rows, wired to nothing. Its placeholder banner is
**pinned by a test that will fail when rung 2 lands** — the banner and
that assertion come out in the same diff that makes the rows real, so the
scaffold cannot be left in place by forgetting.

**One thing the scaffold is careful about.** Sample rows that look like
findings, on a page a sys-admin visits to check on a workspace, are a
false alarm waiting to happen. The card carries an explicit
placeholder banner, and a third test asserts the card renders
*identically* whether or not the database holds an offending policy row —
which is what proves rung 1 queries nothing, rather than trusting that it
doesn't.

**2026-09-08 — Item 9's open question closed: the audit is deferred,
not dropped.** The author's call — leave it until there is a database
worth auditing. Moved to `guide/deferred_consolidated.md` with a lift
trigger rather than left in a plan that will eventually archive, because
a deferral nobody can find at the moment it matters is indistinguishable
from having forgotten. The trigger is the first deployment carrying
imported sessions, and the entry says to run it *before* any
reviewee-facing window opens: a hit would be a live disclosure, and
finding one after release answers the question too late to act on it.

**2026-09-08 — Item 9 shipped in one PR, as planned, plus a spec
correction the plan did not anticipate.** The guard went where the plan
said — `_cross_row_errors`, before `_apply_plan` — and the ladder's one
rung carried it, its ten tests and the four doc-impact specs.

**The plan under-counted the failure modes.** It named the illegal-cell
case and, in Semantics, the half-set pair. Writing the check turned up a
third: `decode_pair_to_mode` also swallows the reserved-incoherent
`aggregated` + `identified` pair as `None`, so a bundle carrying it would
have imported as "off" rather than being named. Three distinct messages
now, deliberately not collapsed — an operator whose file is wrong needs
to know *how* it is wrong.

**A stale section in a file the manifest already named.**
`spec/visibility_policy.md` §3 documented the `visible_when` column as
current; it was retired in the S14 contract step, and §4 of the same file
says so. Worse, §3.1's per-audience table read *"Reviewee — all three are
valid"*, which is the exact opposite of the rule this item enforces: the
constant has allowed `reviewee` `while_ongoing` only `None` since it was
written. So the file that documents the rule stated it backwards, one
section away from stating it correctly. §3.1 was rewritten from
`_PER_CELL_VALID_MODES` and §3's framing corrected; the rest of §3's
window definitions are still right and were left. **A spec can hold both
answers at once and pass every check** — nothing greps prose against a
constant, which is the same shape of gap 19F kept finding.

**Verified by re-running 19F's reproduction, not by reading.** The
import that persisted a mid-flight reviewee grant now returns the named
error, writes **zero** rows, leaves `reviewee_has_current_grant` False,
and `/results` 404s. Both halves of the guard were mutation-checked:
removing it fails seven of the ten tests, and the three that survive are
the positive controls — the round-trip, the legal `after_release` cell,
and the legal `observer` `summarized` cell.

`ruff check .` clean; 2,915 passed / 16 skipped (2,905 before).

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

**2026-09-06 — Item 8's two warnings, adjudicated; Item 4's has cleared.**
`close_check.py 19C` now warns on Item 8's own bullets and no longer on Item
4's. Both movements are the check behaving as documented, not drift:

- `spec/color_tokens.md` and `spec/ui_elements.md` (the two `(Item 8)` bullets)
  were edited in the **same commit that added the `## Item 8` heading**. The
  window is half-open — `(start, end]`, the start commit excluded — so a slice
  that lands its manifest and its spec edit together reads as unhonoured. The
  module docstring names this case exactly. Honoured; the edits are in the
  commit that opened the window.
- The `(done — Item 4)` warning below has **cleared on its own**:
  `spec/ui_elements.md` was edited again for Item 8, well after Item 4's
  heading existed, so the bullet now honours without help. Left recorded
  because the reasoning is what makes the next one cheap to read.

- `spec/ui_elements.md` (the `(done — Item 4)` bullet) was edited on
  2026-08-20 by `4a72813c` "style: soften Secondary button outline to
  `text-secondary`" — exactly what the bullet promises — while the Item 4
  heading was logged the next day, 2026-08-21, by `49a8177f` "docs: log
  19C refinements — Item 3 (Danger Zone) + Item 4 (buttons)". Honoured;
  the item was written up after its work landed. This is the retroactive
  case the check warns about rather than failing on, and it is why it
  warns: nothing in the timestamps distinguishes it from another item's
  edit.

## Item 8 — Input boundaries: `--border-default` to 3:1, help card off it

**Status: ✅ complete, closed 2026-09-06 (PRs #2126 → #2128).** Filed
2026-08-21 from Item 2 QA as a dark-mode input-background defect; re-measured
2026-09-05 as a both-themes contrast item; decided 2026-09-06 as a border tweak
only; shipped the same day, then twice more as the customizer surfaced
consequences nobody had predicted. `docs/status.md` carries the row.

**Opportunity.** `body.ui-v2 input / select / textarea` fill with
`var(--surface-page)`, and `body.ui-v2 .card` fills with `var(--surface-page)`
too — a plain card is raised by its border, not by a distinct surface. So an
input in any ordinary operator form had a fill **identical** to its container,
1.00:1, in both themes. The entire boundary was the 1px border, at **1.47:1**
light and **1.70:1** dark, both under the **3:1** WCAG 1.4.11 asks of a
UI-component boundary — and light was the worse of the two, which the original
dark-only framing had missed.

**Decision.** Repoint `--border-default` to the existing primitive
`--slate-dim` in *both* themes: **4.286:1** light, **4.312:1** dark. No new
primitive, no new spec row, no change to the customizer's facet pick-list.
`--gray-soft` / `--slate-deep` keep their values and now serve
`--marker-neutral` alone, so the neutral nav-tab markers did not move.

*Rejected:* a dedicated `--surface-input` fill (the original proposal). Built
and looked at as `theme_variant_beyond-input-fill.json` — it reaches only
1.238:1 light / 1.145:1 dark, because the palette has no off-white with real
separation. *Rejected:* per-theme primitives at an exact 3:1 (`#8b96a5` /
`#516280`). Two new Tier 1 rows for less headroom, and 2.998:1 in light fails a
strict `>= 3.0` check.

**The consequence the customizer caught.** `.rs-help-card` filled with
`var(--border-default)` — a border colour used as a surface. That read
acceptably only while the border was very light. At the new value the slab
turns mid-grey and **body text on it drops to 3.96:1 light / 3.41:1 dark, both
under AA**. The border change alone would have shipped failing text on the
reviewer surface. Found by loading the variant in
`tools/theme_customizer.html`, not by the test suite, which has no way to see
it.

The fix restores stated intent rather than inventing one:
`spec/ui_elements.md` §"Reviewer help cards" has always described these as
"bg-muted tinted blocks" and recorded `#f5f5f7` as their value. The
tokenization pass it called for pointed them at `--border-default` instead. They
now fill with `--surface-muted` — `#f5f5f7` light, exactly the recorded value —
and text lands at **16.29:1 / 11.65:1**. The visible change is that the slab is
a lighter tint than it has been, which is what "bg-muted tinted block"
describes.

**Judgment calls — decided.**

- *`--slate-dim` over an exact target* (2026-09-06). Both themes share one
  primitive, so a single value cannot hit a per-theme target. Solving for the
  floor instead, the best any shared value reaches on that hue is **4.291:1**
  — `--slate-dim` is at 4.286:1, within 0.005 of the ceiling. Beating it needs
  two per-theme primitives, which buys little for two new Tier 1 rows.
- *Border and dim text share a value in dark* (`--text-dim` is also
  `--slate-dim`). Accepted: they are independently mapped, not coupled, so
  either can move alone later.
- *The border-`*` theme variants are retired, not updated* (`constitution.md`
  Article VI). They existed to choose a border value; the choice is made and
  the ceiling above says there is no better shared value to find. The
  `beyond-*` files stay — they are the record of why the fill route lost.
  **Reversed 2026-09-06 by the author, and the whole variants harness went
  with them.** Keeping the artefacts assumed a reader would take them as
  evidence; in practice a second 2.6 MB customizer — differing from the stock
  one by a 582-byte `<style>` shim declaring two tokens `base.html`
  deliberately does not have — reads as a *facility*, and invites exactly the
  question it was meant to answer ("shouldn't we add these to `base.html` and
  retire one of these?"). It did, within the day. Retiring it costs nothing
  the record needs: the numbers that decided the question are in the
  **Decision** paragraph above, in prose, which is where Article V says
  reasoning travels. `theme_variants.gen.py`, its three `beyond-*.json`
  outputs and `theme_customizer_beyond.html` are deleted; `git log --` has the
  machinery, including `max_shared_floor()`, if a future palette reopens the
  question. Note the scope: the five border-`*` variants had already gone, so
  `VARIANTS` held only the three `beyond-*` entries — retiring them left the
  377-line generator producing nothing, and a generator that generates nothing
  is the Article VI case exactly.

**Blast radius (measured).** `app/web/templates/base.html` — 2 token rows + 1
rule; `spec/color_tokens.md` — 1 row + 2 notes; `spec/ui_elements.md` — 1 entry;
`tools/theme_preview.html`, `tools/theme_customizer.html`,
`tools/theme_customizer_beyond.html` regenerated; `tools/theme_variants.gen.py`
+ `tools/README.md` updated; 5 retired JSONs deleted. No app code, no schema, no
route.

**Follow-on, 2026-09-06 — the help card gets its own tokens.** Shipping the
above left two loose ends, both caught by looking rather than by a check.

1. **The border.** `.rs-help-card` never overrode `.card`'s 2px
   `var(--border-default)`. Before, fill *and* border were the same token, so
   the outline was invisible and the block read as the slab its comment
   describes. Moving the fill to `--surface-muted` while the border darkened to
   `--slate-dim` gave it a **3.94:1** edge in light, 3.28:1 in dark — precisely
   the "regular card with contrasting border + interior" the comment says it
   must not be.
2. **The customizer's facet pick-list went stale.** `theme_customizer.gen.py`
   still declared the help card's background facet as `--border-default`, so
   Part C reported the wrong token for it. Nothing caught this: the pick-list
   comment claims a browser-side self-check against computed colour, but
   `getComputedStyle` appears nowhere in the tool — Item 5's "0 mismatches" was
   a one-time build-time verification, not running code.

Both are fixed by giving the block its own `--card-help-bg` / `-border` / `-fg`
family in the **Card accents** cluster, the shape `.danger-zone` already uses,
and adding the border facet to the pick-list. `--card-help-border` resolves to
the **same primitive** as the fill, so the edge disappears; the two map
independently rather than one pointing at the other, so either can be
repointed alone.

*Considered and rejected: reclassifying it as a banner.* It is not transient
page-level feedback — it is persistent, half-width inside a two-up grid, and on
the operator Instruments page an unlocked help card **hosts a `<textarea>`**
for editing the help text (`instruments_index.html`). A container with
interactive content is a card. The `rs-` prefix is still inaccurate (the block
renders on an operator page too) but renaming it buys nothing now that the
category is right, so the class names stand.

*A defect this incidentally fixed.* That Instruments-page textarea sits inside
the help card and takes `--border-default` for its own border. While the slab
was also `--border-default`, the edit box had a **1.00:1** edge against its
container — no visible boundary at all. It is now delineated at 3.94:1 light /
3.28:1 dark.

**`spec-writer` at close, 2026-09-06 — two flags, both upheld.** Run against
the two doc-impact specs. Each was re-verified against the tree before acting;
neither was taken on the agent's word.

1. **My own stale line.** `spec/color_tokens.md`'s "Border colours do not paint
   fills" note ended "It now fills with `--surface-muted`". True when I wrote it
   in the first Item 8 commit; false a commit later, when the follow-on gave the
   card `--card-help-bg`. The rule reads `background: var(--card-help-bg)`.
   Corrected — and the sentence now says *why* it is its own token, which is the
   part that stops the next border change reaching it.
2. **A retired class described as live, in two specs.** Both
   `spec/ui_elements.md` and `spec/reviewer-surface.md` documented a two-variant
   help block: a grid for several items, `.rs-help-card-solo` full-width for
   one. Verified: zero CSS rules for that class in `base.html`, no template
   renders it, `review_surface.html` always emits `.rs-help-grid` with no count
   branch, and `test_reviewer_response_flow.py` asserts the modifier **does not**
   render. It was retired 2026-05-05 in `62a85fee` when the per-instrument intro
   became a half-width card grid. Both specs now say so, with the date and the
   commit, rather than deleting the sentence and losing why.

`spec/reviewer-surface.md` was **not** in the manifest — undeclared spec impact,
so it gains a bullet above and this note, per the skill. Fixing it was in scope
because the false claim sat in the same entry Item 8 rewrote twice; leaving a
neighbouring sentence wrong while correcting the one beside it is how the drift
survives. That the flag came from a second reader is the point of the step:
finding 1 was mine, and I had already read that line three times.

**Not verifiable here.** This is a pure visual change to a template's CSS. The
test suite cannot see it; `pytest` and `ruff` passing say only that nothing
else broke. Confirmed by eye in the customizer before shipping, and due a look
on the Azure dev slot after deploy.

### Superseded framing

The future-item entry this item grew out of, kept for the record of how the
diagnosis moved from "dark-mode input background" to a both-themes boundary
problem:

- **Input boundaries carry no fill contrast, in either theme** *(filed
  2026-08-21 from Item 2 QA as "dark-mode input background"; **re-measured and
  re-scoped 2026-09-06** — see below).* `body.ui-v2 input / select / textarea`
  fill with `var(--surface-page)` (`base.html:2205`), and `body.ui-v2 .card`
  **also** fills with `var(--surface-page)` (`base.html:1291` — a plain card is
  raised by its border, not by a distinct surface). Every ordinary operator form
  therefore renders an input whose fill is identical to its container:

  | | input fill | container | ratio |
  |---|---|---|---|
  | Dark, input in a card | `#0f141b` | `#0f141b` | **1.00:1** |
  | Light, input in a card | `#ffffff` | `#ffffff` | **1.00:1** |

  The whole boundary is the 1px `--border-default`, and that is thin in both
  themes: **1.70:1** dark (`#3a465c` on `#0f141b`) and **1.47:1** light
  (`#d1d5db` on `#ffffff`). Neither reaches the **3:1** WCAG 1.4.11 asks of a
  UI-component boundary, and light is the *worse* of the two.

  **What the re-measure changed.** The original note read this as a dark-mode
  defect ("light unaffected") and proposed lifting the dark fill toward
  `--bg-card`. That would fix one theme and leave the weaker one alone. Only
  three narrow elements actually use `--surface-card` — `.session-nav-card`,
  `.status-row`, `.data-shape-card` — and none of them is a form container, so
  the "input matches its card" reading was never dark-specific. Treat this as a
  **both-themes contrast item**, not a dark-mode polish item.

  The note's token names are also pre-Item 6: `--bg-page` / `--bg-card` were
  retired by the two-tier reorg on 2026-08-23 (`spec/color_tokens.md`).

  **Constraints for whoever builds it.**
  - `--surface-card` **cannot** be reused as the input surface. It is a step
    lighter than `--surface-page` in dark (`#1a212e` vs `#0f141b`) but both
    resolve to `#ffffff` in light, so repointing to it fixes dark and changes
    nothing in light — the same half-fix in different clothing. A new Tier 2
    token is needed, with a real value in *both* columns.
  - A new semantic token means a row in `spec/color_tokens.md` §"Surfaces",
    which is specced as a closed set.
  - `tools/theme_customizer.gen.py` names `--surface-page` as the background
    facet for `input[type=text]` / `textarea` / `select` at lines 176-181. That
    pick-list is hand-written and is the authority for Part C's readout; a
    browser-side self-check compares each facet against the element's computed
    colour in both themes. Change the token without changing those three
    entries and the self-check reports mismatches (it is at 0 today).
  - Raising `--border-default` to 3:1 instead of adding a fill is the obvious
    alternative and is **not** obviously worse — it needs no new token and no
    spec row. It does change every bordered surface, not just inputs, which is
    the trade to weigh.

  **Decided 2026-09-06 (user).** Border tweak only — no new input-surface
  token, no new spec row, no change to the customizer pick-list. The current UI
  reads acceptably in use; this is a contrast-headroom item, not a defect
  report, and the fill route is out of proportion to it. To be tried in
  `tools/theme_customizer.html` before anything is committed to `base.html`.

  **Candidate, if the tweak is taken.** `--border-default` repoints to the
  **existing** primitive `--slate-dim` (`#6f7b8e`) in *both* themes. Measured
  against `--surface-page`:

  | Primitive | Light (`#ffffff`) | Dark (`#0f141b`) |
  |---|---|---|
  | `--gray-soft` / `--slate-deep` (today) | 1.47:1 | 1.70:1 |
  | `--gray` `#9ca3af` | 2.54:1 | 7.28:1 |
  | **`--slate-dim` `#6f7b8e`** | **4.29:1** | **4.31:1** |
  | `--slate` `#6b7280` | 4.83:1 | 3.82:1 |

  `--slate-dim` is the only one that lands near-symmetrically in both themes,
  and one primitive serving both columns collapses the change to a single
  Tier 2 row. Two things to look at in the customizer rather than reason about:
  4.3:1 is roughly triple today's contrast, which on a **2px** `.card` border
  may read heavier than intended; and the repoint moves every bordered
  surface — cards, nav, tables — not just inputs. `--gray` is the fallback if
  `--slate-dim` looks too strong, at the cost of leaving light at 2.54:1,
  still short of 3:1.

  Scope, after the decision: one line in `base.html`, one row in
  `spec/color_tokens.md`. The token stays `--border-default`, so the
  customizer pick-list and its self-check are untouched.

---

## Item 9 — The Settings-CSV import writes visibility cells the editor forbids — ✅ shipped 2026-09-08

### Opportunity

Two writers create `instrument_view_policies` rows and only one of them
validates. `visibility_policies.upsert_policy` runs
`_validate_per_window` and refuses a `(audience, window)` cell outside
`_PER_CELL_VALID_MODES`; `session_config_io/_apply_instrument.py:403`
builds the row straight from the parsed spec and checks nothing. The
parser validates the **vocabulary** — granularity in `{row, aggregated}`,
identification in `{identified, deidentified}` — never the cell those
values land in.

The cell that matters is `("reviewee", "while_ongoing")`, whose only
legal mode is `None`: a reviewee may never see responses while the review
is running. Driven end to end during Segment 19F's close, on a session
whose only oddity is an imported Settings CSV:

```
apply_session_config errors : []
persisted row: while_ongoing=(row,identified) after_release=(None,None)
editor validation: REJECTS -> VisibilityPolicyError: audience 'reviewee'
  while_ongoing cell only accepts modes in ['None']; got 'raw'.
session status: ready -> has_current_grant: True | GET /results: 200
```

A reviewee reading responses **mid-flight** — the state 19F decision 3
exists to prevent, reachable through a door that never asked. The leak
is older than 19F: the unvalidated writer arrived with **18P PR A2**
(2026-06-05), when the Settings CSV gained the Band 3 grid, and before
19F `/results` would have rendered those values to any active reviewee
anyway. 19F neither caused it nor widened it — its predicate honours the
row like any other — but its audit is what found it.

**Correction to 19F's record.** Its `## Status` and PR #2187 both said
"the same door serves clone and rehydrate". Rehydrate yes —
`session_rehydrate.py:515` calls `apply_session_config`. **Clone no**:
`clone_session` copies no view-policy rows at all, which
`spec/roundtrip_coverage.md` line 86 already records ("Clone still
doesn't copy it — a clone reverts to default visibility"). The archived
plan was **amended 2026-09-08** to carry the correction; the merged PR
body cannot be, so this is the only other place the wrong claim is
answered.

### Decision

**Reject the import with a named error** (author, 2026-09-08). An
offending row fails the whole apply in the parse phase, before anything
is written, with an `ApplyError` naming the field and the legal modes —
the same shape and the same wording the editor already refuses with.

The check belongs in **`_cross_row_errors`**, not in the row router: a
cell is a *pair* of rows (`…_granularity` + `…_identification`) and is
only complete once both are parsed. That hook already exists, already
emits `ApplyError(row_number=0, …)` for exactly this class of
cross-row invariant, and runs before `_apply_plan`, so rejection is free
of a partial write.

**Rejected: coerce the offending cell to `None` and import the rest.**
It is the friendlier failure and the wrong one. A visibility grid is a
permission document; silently downgrading one cell of it hands the
operator a session that does *not* say what their file said, with
nothing in the UI to show which cell moved. The same bundle would import
differently depending on a rule the file never mentions. An import that
stops and names the row leaves the operator with a file to fix and a
session unchanged — and the editor already treats this shape as an
error, so rejecting keeps one answer to "is this legal?" instead of two.

### Semantics

- **A valid round-trip must stay valid.** `_serialize.py:485` emits all
  four cells for every audience, so a legitimately authored session
  exports `reviewee.while_ongoing_granularity` as an **empty string**.
  Empty parses to `None`, `None` is the legal mode for that cell, so
  export → import of any session the editor produced is unaffected. This
  is the property to assert first; without it the item breaks backup and
  restore for everyone to close a hole almost nobody has.
- **A half-authored cell.** Granularity set, identification empty (or
  the reverse) is not a mode at all. `decode_pair_to_mode` is what turns
  a pair into a mode; a pair it cannot decode is its own error, distinct
  from a legal-mode-in-the-wrong-cell, and is reported as such rather
  than being coerced to `None` and passing.
- **Every offending cell is reported, not just the first.** The parse
  phase's contract is "collect every error before reporting; one bad row
  doesn't mask the next", and this check follows it.
- **Other audiences, same rule.** `peer_reviewer.while_ongoing` accepts
  only `raw` and `observer.while_ongoing` only `{None, summarized}`; the
  check reads `_PER_CELL_VALID_MODES` rather than special-casing the
  reviewee, so all six cells are covered by construction. The reviewee
  cell is the one with a disclosure behind it, not the only one wrong.
- **Rows already in the database are not touched.** This closes the
  door; it does not sweep the room. See Open questions.
- **The error is the editor's sentence.** `_validate_per_window` already
  produces "audience 'reviewee' while_ongoing cell only accepts modes in
  ['None']; got 'raw'." Reusing it — rather than writing a second
  wording — is what keeps the two writers answerable to one rule.

### Judgment calls — decided

- **Reuse `_PER_CELL_VALID_MODES` by import, don't restate it**
  (2026-09-08). A second copy of the table in the parser is a second
  thing to forget when a cell's rules change.
- **Report at `row_number=0`** (2026-09-08), like every other cross-row
  error, with `field` naming the offending path
  (`instruments[1].view_policies[reviewee].while_ongoing_granularity`).
  The operator needs the field far more than the line, and a cell spans
  two lines anyway.
- **No new error class.** `ApplyError` carries `field` + `message`,
  which is what the import surface renders; a code adds nothing a
  caller reads today.

### Blast radius (measured)

Commands run at `bc3a30bf`, 2026-09-08:

- `grep -rn "InstrumentViewPolicy(" app/ --include=*.py | wc -l` → **3**:
  the model class, the validating writer
  (`visibility_policies.py:419`), and the unvalidated one
  (`_apply_instrument.py:403`).
- `grep -rn "apply_session_config(" app/ --include=*.py` → **3 real
  call sites** plus the definition: `_quick_setup.py:930`,
  `session_rehydrate.py:515`, and the Session-Home config card via
  `_session_home.py:432` → `_apply_session_config_form`. Those are every
  door onto the unvalidated writer. **Clone is not one** — `grep -n
  "view_policies\|ViewPolicy" app/services/session_clone.py` is empty.
- `grep -c "ApplyError(" app/services/session_config_io/_apply_parse.py`
  → **10** existing emitters to match in shape.
- `grep -rln "view_policies" tests/ --include=*.py | wc -l` → **4**:
  `tests/unit/test_apply_session_config.py`,
  `tests/unit/test_instrument_view_policy_model.py`,
  `tests/integration/test_instrument_view_policy_routes.py`,
  `tests/integration/conftest.py`.
- `grep -rln "view_policies" spec/ docs/ | wc -l` → **7**, of which the
  ones this changes are named under Doc impact.

One PR. No migration, no route shape, no template.

### PR ladder

1. **The guard, its tests, and the specs.** `_cross_row_errors` gains
   the per-cell check reading `_PER_CELL_VALID_MODES`; tests assert (a)
   a `reviewee` + `while_ongoing` bundle is rejected with the field
   named and **nothing written**, (b) a real export → import round-trip
   of an editor-authored session still applies clean, (c) an
   undecodable pair reports its own error, and (d) the other two
   audiences' illegal cells are caught by the same code path. **Must not
   touch** `upsert_policy`, the resolver, or any existing row.

Small enough to be one slice; the round-trip assertion is what makes it
safe to land in one.

### Definition of done

- A Settings CSV carrying `instruments[n].view_policies[reviewee]
  .while_ongoing_*` fails `apply_session_config` with an `ApplyError`
  naming that field, and `counts` is empty — asserted.
- The same CSV writes **no** `instrument_view_policies` row — asserted
  by querying after the failed apply, not inferred from `errors`.
- `serialize_session_config` → `apply_session_config` on an
  editor-authored session with a reviewee `after_release` grant still
  applies with `errors == []` — asserted, and it is the regression that
  matters most.
- The illegal `peer_reviewer` and `observer` `while_ongoing` cells are
  rejected by the same path — asserted.
- A granularity without its identification reports a distinct error —
  asserted.
- `python3 tools/close_check.py 19C` exits 0.
- `ruff check .` and the full suite pass.

### Open questions

- ~~**Rows already persisted through the old door.**~~ **Resolved
  2026-09-08 — deferred, by the author: leave the audit until there is a
  database worth auditing.** The guard is prospective, and the
  population at risk is only *sessions whose config was imported from a
  hand-edited bundle before 2026-09-08*; the pilot has not deployed, so
  that population is very likely empty. An audit run against a database
  with no such rows proves nothing and has to be re-run later anyway.
  Recorded in `guide/deferred_consolidated.md` (Part A, "Data integrity
  & template maintainability") with its lift trigger — **the first real
  deployment carrying imported sessions**, run before any
  reviewee-facing window opens, since a hit is a disclosure. Kept here
  rather than deleted because the question is what makes the deferral a
  decision rather than an oversight: nobody has checked, because there
  is not yet anything to check.

### Out of scope

- **The editor path.** `upsert_policy` already validates; nothing to do.
- **Clone.** It copies no view-policy rows at all, by design recorded in
  `spec/roundtrip_coverage.md` — a separate gap with its own decision,
  untouched here.
- **The resolver.** `resolve_mode` honouring whatever row it finds is
  correct behaviour for a resolver; the fix belongs at the write, not
  the read. Making the resolver second-guess its own table would put the
  rule in two places and hide bad data rather than refuse it.
- **19F's shipped behaviour.** Unchanged. This closes the door 19F's
  audit found open; it revisits none of its decisions.

---

## Item 10 — Audit visibility rows that predate the import guard — ✅ shipped 2026-09-08

### Opportunity

Item 9 closed the door: since PR #2188 the Settings-CSV import refuses a
`(audience, window)` cell outside `_PER_CELL_VALID_MODES`, the same table
the Band 3 editor enforces. That guard is **prospective**. Any row
written before it — through Quick Setup, the Session-Home config card or
rehydrate, the three doors onto the old unvalidated writer — is still
sitting in `instrument_view_policies`, and `resolve_mode` honours it.

The row that matters is a `reviewee` grant on `while_ongoing`, whose only
legal mode is `None`. One of those is a reviewee reading responses while
the review is still running.

**The deferral is lifted, not reversed.** Item 9's open question was
answered on 2026-09-08 with "leave it until there is a database worth
auditing", and the entry went to `guide/deferred_consolidated.md` with a
lift trigger. The author lifted it on 2026-09-08 ahead of that trigger.
Per the ledger's own rule — *"When one fires, lift the section into a
fresh segment plan (or fold it into a related in-flight segment) and
delete its entry here"* — the entry is removed there rather than
duplicated here.

**What that means for the definition of done.** The premise of the
deferral has not changed: the pilot has not deployed, so this cannot be
verified by finding anything. What ships is a check that is **ready and
proven against fixtures**, not an audit result. A green run today says
"no rows in this database", and this database has almost no rows.

### Decision

**A read-only card on Sys Admin → Sessions Diagnostics**, not a script.
The plan Item 9 carried said `tools/` — that was wrong, and building it
is what showed why:

- every script in `tools/` is stdlib + `git` and operates **on the
  repo**; none opens a database;
- `CLAUDE.md` is explicit that the author runs no Python, alembic or
  database locally — there is no laptop dev loop;
- an agent sandbox cannot reach Azure Postgres.

So a `tools/` script would have been a deliverable **nobody could run
against the data it audits**. The deployed app is the only thing holding
a connection to that database, and Sys Admin is the only surface whose
audience is entitled to a workspace-wide read: the query spans every
session, which no per-session operator may see.

**Rejected: a Validate-page finding per session.** It puts the answer in
front of the operator who owns the session, which is the right person to
act — but it only fires for sessions somebody re-validates, and a session
already past validation is exactly the one nobody will touch again. The
question here is retrospective and workspace-wide; the surface should be
too. Worth revisiting as a *second* home if a hit is ever found.

**Rejected: run it on deploy and log.** Findings in a log nobody reads
are findings nobody has. Failing the deploy over pre-existing data would
be worse — it would block a release to report a condition the release did
not cause.

### Semantics

- **Read-only, always.** The card reports; it never clears a cell.
  Deciding what an offending grant should become is a judgment about a
  live review — whether the operator meant `after_release`, or meant
  nothing — and belongs to the operator who owns that session, not to a
  sweep run by an admin who does not know the review.
- **Empty is the expected state, and must read as reassurance.** The card
  says so in words rather than rendering a bare empty table, which reads
  as "not implemented yet".
- **All six cells, not just the reviewee's.** The check asks
  `_PER_CELL_VALID_MODES` for every `(audience, window)` pair, exactly as
  the import guard does. The reviewee's `while_ongoing` is the one with a
  disclosure behind it, not the only one that can be wrong.
- **The three not-a-mode shapes count as findings too**, matching the
  guard: a half-set pair, the reserved-incoherent `aggregated` +
  `identified`, and a legal mode in the wrong cell. A half-set pair is
  reported because `decode_pair_to_mode` reads it as "off" — it is
  currently harmless and still not what anybody authored.
- **Ordering is by exposure, not by id.** A hit on a `ready` or
  `expired` session is live; one on a `draft` or `archived` session is
  not. The live ones sort first, because the card's reader is deciding
  what to do this morning.
- **Cost is bounded by instrument count, not session count.** One query
  over `instrument_view_policies` joined to instruments and sessions;
  the decode is in Python against a six-entry table.

### Judgment calls — decided

- **On Sessions Diagnostics, not a third nav page** (2026-09-08). The
  Sys Admin nav has two entries and this is a diagnostic about sessions.
  A third page for one card would make the nav the feature.
- **No count in the nav or a badge** (2026-09-08). A badge implies
  something to clear on every visit; the expected steady state is zero,
  and a permanent "0" is noise.
- **Reuse `valid_modes_for_cell` and `decode_mode`, do not restate the
  table** (2026-09-08) — the same rule Item 9's guard follows, so a
  change to a cell's rules cannot leave the audit reading an old copy.

### Blast radius (measured)

Commands run at `6d6840c0`, 2026-09-08:

- `grep -n "sys-admin" app/web/routes_operator/_sys_admin.py | wc -l` →
  the module owns every `/operator/sys-admin/*` route; the card hangs off
  the existing `sys_admin_sessions` handler, so **no new route**.
- `grep -n "_sys_admin" app/web/spec_registry.py` → **1** —
  `spec/permissions.md` governs the module, so that is the spec the
  coverage test will look at.
- `grep -c "href" app/web/templates/operator/partials/sys_admin_top_nav.html`
  → **2** nav entries, unchanged by this item.
- Templates touched: **1** (`sys_admin_sessions.html`). New view module:
  **1** (`app/web/views/`, per the fourth-seam rule — a status label
  computed from instrument state is view shape, not business logic).

Two PRs. No migration, no new route, no model change.

### PR ladder

1. **Scaffold.** The card on `sys_admin_sessions.html` with its real copy
   and layout, rendering a **static placeholder** row set and the
   empty-state text, wired to nothing. Per `CLAUDE.md`'s scaffold-first
   rule for a new card. **Must not** query
   `instrument_view_policies` or touch `visibility_policies`.
2. **The wiring.** The view builder that runs the real check, the
   handler passing it, and the tests — including a seeded offending row
   per shape, and the empty-database case. **Must not** change the card's
   shape agreed in rung 1.

### Definition of done

- The card renders on `/operator/sys-admin/sessions` for a sys-admin and
  is unreachable for everyone else — asserted through the existing
  `require_sys_admin` gate, not by reading it.
- With no offending rows, the card says so in words — asserted.
- A seeded `reviewee` + `while_ongoing` grant appears, naming session,
  instrument, audience, cell and decoded mode — asserted.
- A seeded illegal `peer_reviewer` cell and a seeded illegal `observer`
  cell appear by the same code path — asserted.
- A half-set pair and the reserved-incoherent pair each appear with their
  own reason — asserted.
- A legal grid produces no findings — asserted, so the check cannot pass
  by finding everything.
- Rows on `ready` / `expired` sessions sort above `draft` / `archived` —
  asserted.
- Nothing writes: the card issues no POST and the view calls no mutating
  service — asserted by the absence of an audit event after a render.
- `python3 tools/close_check.py 19C` exits 0.
- `ruff check .` and the full suite pass.

### Open questions

- None. The one that mattered — whether to audit at all — was Item 9's,
  and the author answered it twice: defer (2026-09-08), then lift
  (2026-09-08).

### Out of scope

- **Clearing an offending cell.** Read-only by decision above. If a hit
  is ever found, the fix is the operator's, on the Band 3 editor, which
  already refuses to author the bad value.
- **The Validate page.** Rejected above as the primary home; revisit only
  if a hit is found.
- **Item 9's guard.** Unchanged. This item is the retrospective half of
  the same finding, not a second look at the prospective half.
- **Any other integrity check.** The card is named for this one question.
  A general "workspace integrity" surface is a different item with a
  different scope, and inventing it here would mean designing for checks
  nobody has asked for.

---

## Future items — retired at close

This section was the segment's landing place for further refinements, and
it is why 19C stayed open for nineteen days. **It is closed with the
segment** (author, 2026-09-08): new refinements get their own segments
rather than accreting here.

Two items were parked here and unbuilt when the segment closed. Neither
is dropped — both moved to `guide/todo_master.md` (Upcoming → Stubs) on
2026-09-08, because that file is the committed sequence and this one is
about to be archived:

- **Theme customizer — a full pass over every element** (author intent,
  logged 2026-09-06 at Item 8's close).
- **Technical-support contact (global)**, moved out of Segment 20 on
  2026-09-05 because the mechanism needs no deployed host.

`docs/status.md`'s "not yet there" row for the support contact pointed at
*"Segment 19C Item 8"*, which was never true — Item 8 is the
input-boundaries work, and the contact sat here, unnumbered. Corrected at
close to name its actual home.

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
- `spec/color_tokens.md` — `--border-default` repoints to `--slate-dim` in both
  themes, with the 3:1 rationale, the shared-primitive consequence, and the rule
  that border colours do not paint fills (Item 8).
- `spec/ui_elements.md` — the Reviewer help cards entry records the
  `--card-help-*` family, why the tokenization pass had it wrong, and that the
  border resolves to the fill's primitive on purpose (Item 8).
- `spec/reviewer-surface.md` — the Help block's two-variant description drops
  the `.rs-help-card-solo` case, retired 2026-05-05 (Item 8; **added at close**,
  not planned — see Status).
- `spec/quick_setup_card_spec.md` — `app/services/session_config_io/`
  package rename (Item 7).
- `spec/settings_inventory.md` — `app/services/scheduled_events/` package
  rename (Item 7).
- `docs/security_posture.md` — drop the pointer to the retired
  authentication doc, whose content this file absorbed (Item 7).
  <!-- doc-impact-waived: finding 2.7 declined at PR 1 — the reference is a dated provenance note ("formerly ..., retired 2026-08-19"), not a live pointer; see Status -->
- `spec/permissions.md` — the Sys Admin Sessions Diagnostics page gains the
  read-only visibility-audit card; it is workspace-wide by construction, which
  is why it sits behind `require_sys_admin` rather than on any per-session
  operator surface (Item 10).
- `spec/visibility_policy.md` — the per-cell validity table is a rule the
  **import** honours too, not only the Band 3 editor; an illegal cell in a
  Settings CSV rejects the apply (Item 9).
- `spec/settings_inventory.md` — the `instruments[n].view_policies[<audience>].*`
  entries gain the per-cell constraint, so the inventory says which values a
  cell may carry and not merely which words parse (Item 9).
- `spec/roundtrip_coverage.md` — the instrument-visibility row records that a
  round-trip of an editor-authored session is unaffected (empty cells serialize
  to empty and parse to `None`), and that the import now refuses what the editor
  refuses (Item 9).
- `spec/rehydrate.md` — a settings bundle carrying an illegal cell fails
  rehydrate at the settings step, with the named error surfaced (Item 9).
- `spec/visual_style_rrw.md` — repoint the two references to specs
  consolidated into the instruments spec in 2026-05 (Item 7).
- `spec/lifecycle.md` — §1 state diagram to show all five states, plus the
  package rename (Item 7).
- `spec/operator_ui_concept.md` — document the `(super admin)` /
  `(sys admin)` suffix on the user card (Item 7).
- `spec/domain_assumptions.md` — drop or qualify "1-6 Instruments"; there
  is no cap in code (Item 7).
- `spec/visual_style_general.md` — the finding 2.4 decision (Item 7).
