# Segment 19C — Refinements

**Status:** In progress — **Item 1 ✅ shipped 2026-08-20** (friendly labels
via roster CSV headers; sole round-trip carrier). A holding segment for **small,
self-contained operator-facing refinements** that don't warrant their own
segment — the sibling of 19A (docs hygiene) and 19B (code consistency), but
for behaviour / contract polish. Items land as independent slices; the
segment stays open as a home for further refinements as they're identified.

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

## Future items (add as they come up)

Landing place for further small operator-facing refinements. Log new ones
here as `Item N` with the same problem / decision / scope / done-when shape,
and keep each a self-contained slice. The user will populate this list as
refinements are identified.

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
