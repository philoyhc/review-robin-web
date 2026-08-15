# Segment 18P — Patching the round-trip (harmonize + rehydrate)

**Status:** Planning. Grounded in the completed coverage sweep
(`spec/roundtrip_coverage.md`) and the rehydrate design
(`docs/rehydrate.md`). Two coupled work groups; Group 1 lands first because
Group 2 sits on top of it.

> Depends on the round-trip coverage doc (`spec/roundtrip_coverage.md`) and
> the rehydrate spec (`docs/rehydrate.md`) already in the tree. This plan
> turns their findings + design into an ordered slice ladder.

---

## Why this segment

Two things surfaced from designing the rehydrate feature:

1. **The round-trip leaks.** Exporting a session's config and re-importing
   it (or cloning it) silently drops several hand-set settings — visibility
   policies, feature toggles, observer cohort rules, roster status, and a
   scattering of clone-vs-settings-CSV mismatches. The sweep catalogued
   every leak in `spec/roundtrip_coverage.md`. These are real bugs in
   plain export/import + backup/restore, independent of rehydrate.
2. **Rehydrate needs a clean round-trip under it.** "Rebuild a session
   from its extract" is only faithful if the config actually survives
   export→import. So the harmonization work is *also* the set of
   prerequisites for rehydration.

Hence one segment, two groups: **harmonize the round-trip** (Group 1,
which includes the rehydrate prerequisites), then **rehydrate a complete
extracted session** (Group 2).

---

## Group 1 — Harmonize the round-trip

> **Status: shipped 2026-06-05** — all seven PRs landed (A1 #1864, A2
> #1865, B #1866, C #1867, D1 #1868, D2 #1869, E #1870), each
> migration-free and flipping its gap in `spec/roundtrip_coverage.md`. The
> rehydrate prerequisite (A1 + A2) is satisfied; Group 2 is unblocked.

Close the gaps in `spec/roundtrip_coverage.md`. Each Part flips one class
of gap from ❌/⚠️ to ✅ in that matrix and lands a round-trip test. Ordered
so the rehydrate-blocking items come first.

### What needs to be harmonized (from the sweep)

| # | Gap | Today | Target | Part | Rehydrate prereq? |
|---|---|---|---|---|:--:|
| 1 | `instrument_view_policies` | in neither settings-CSV nor clone | serialize + apply in `session_config_io` | **A** | **Yes** |
| 2 | `relationships_enabled` / `observers_enabled` toggles | in neither | serialize + apply in `session_config_io` | **A** | **Yes** |
| 3 | Observer `cohort_rule` | dropped by observers CSV | carry it (CSV column or via `session_config_io`) | **B** | Yes (observer-collation fidelity) |
| 4 | Reviewer / reviewee / observer `status` | roster CSVs don't preserve it (all → active) | add `Status` round-trip; decide preserve-vs-reset policy | **C** | Yes (roster fidelity) |
| 5 | Clone drops scheduling/retention anchors | settings-CSV ✅, clone ❌ | clone copies them | **D** | No |
| 6 | Clone drops data shapes | settings-CSV ✅, clone ❌ | clone copies them | **D** | No |
| 7 | settings-CSV drops session tags | clone ✅, settings-CSV ❌ | serialize + apply tags | **D** | No |
| 8 | settings-CSV drops `band1_touched_links` | clone ✅, settings-CSV ❌ | serialize + apply it | **D** | No |
| 9 | Instrument `order` ignored on apply | position wins; `order` cell decorative | make position authoritative *by design* + document, or honour the cell | **E** | No |
| 10 | Field labels outside the tag allowlist | export-without-import (import rejects) | stop exporting what can't be imported (align export to allowlist) | **E** | No |
| 11 | `display_fields.label` dead column | never restored | leave (already unserialized) or drop the column | **E** | No |
| — | Session-operator role grants | carried by no path | **out of scope** (permissions, not config) | — | No |
| — | Manual per-pair assignment overrides | not exported, reset on regenerate | **out of scope** unless pilot shows need (documented as regenerate-from-rules) | — | No |

### Part A — Settings round-trip: visibility policies + feature toggles

**The rehydrate prerequisite** already named in
`docs/rehydrate.md#prerequisite-extend-the-settings-round-trip`. Ships on
its own; fixes plain export/import + backup/restore too.

- **Serialize** (`session_config_io/_serialize.py`): emit
  `instruments[n].view_policies[audience].*` rows (the while-ongoing /
  after-release *granularity* + *identification* pairs and `observer_tag`,
  per `spec/visibility_policy.md`) and two `session.relationships_enabled`
  / `session.observers_enabled` rows.
- **Apply** (`session_config_io/_apply_instrument.py` for view policies
  within the instrument rebuild; `_apply_session.py` for the toggles): parse
  + restore. Guard the toggles' lock-on-data semantics.
- **Test:** `serialize → apply → assert view policies + toggles unchanged`.
- **Coverage doc:** flip gaps 1–2 to ✅; drop the "via prerequisite"
  wording once real.

*Risk note — land A first as a self-contained settings-round-trip fix.*
Nothing else in the segment blocks on it, and it's the single item Group 2
hard-depends on.

### Part B — Observer cohort rules round-trip

`Observer.cohort_rule` (JSON) is dropped by the observers CSV
(`observers_extract.py` header is only Email/Name/Tag1/Status;
`parse_observer_csv` ignores extras). Pick one:

- **B-CSV:** add a `CohortRule` column to the observers extract + importer
  (JSON-in-a-cell), or
- **B-config:** serialize observers through `session_config_io` so the
  cohort rule rides the settings CSV.

Prefer **B-CSV** (keeps observers on the roster-CSV path with reviewers /
reviewees; smaller blast radius). Update `spec/csv_contracts.md`. Flip gap
3.

### Part C — Roster status round-trip

**Decision: preserve status for all three participant rosters —
reviewers, reviewees, and observers.** Rehydrate (and plain
export→import) should bring back inactive members as inactive.

- Add a `Status` column to the reviewer / reviewee extract headers +
  importers.
- Have `parse_observer_csv` **read** the `Status` the observers extract
  already emits (today it's exported but ignored on import).

**Why observers are in, and operator roles are out.** Observers are a
*participant roster* — on par with reviewers and reviewees, and
disanalogous to true account-roles. Their status is per-session
participant config, so it belongs in the round-trip. That's the line that
keeps **session-operator role grants out of scope** (a real permission /
account concern, not roster config — see "Deliberately out of scope").

Flip gap 4.

### Part D — Clone ↔ settings-CSV convergence

The two config paths drop *different* things, which reads as "why did my
Duplicate lose X?". Converge them:

- **D1 (clone gaps):** `session_clone.clone_session` copies the scheduling
  / retention anchors (`scheduled_activate_at`, `responses_release_at`,
  `responses_release_until`, `invite_offsets`, `reminder_offsets`,
  `archive_offset`, `retention_exception`, `retention_overrides`) and
  `data_shapes`. Flip gaps 5–6.
- **D2 (settings-CSV gaps):** `session_config_io` serializes + applies
  session tags and `band1_touched_links`. Flip gaps 7–8.

Land D1 and D2 as separate PRs (different files, different review
surfaces).

### Part E — Asymmetry & footgun cleanups

Lower priority; correctness/clarity, not data loss:

- **Instrument `order`** — decide: keep position-authoritative (and stop
  serializing the decorative `order` cell / document it) *or* honour the
  cell on apply. One or the other; today it's ambiguous.
- **Non-allowlist field labels** — align the exporter to the import
  allowlist so `settings.csv` never emits a row the importer will reject.
- **`display_fields.label`** — dead column; either drop it (Alembic
  migration) or leave and note it. Cheapest to leave + document.

Flip gaps 9–11 / mark as deliberately documented.

---

## Group 1 — implementation (PR ladder)

Seven small PRs, one (or two) per Part. Each is independent unless noted,
each **flips its gap(s) in `spec/roundtrip_coverage.md` in the same PR**
(the coverage matrix is the scoreboard), and each lands a round-trip test.
No Alembic migrations are required in Group 1 — every column already
exists; this is serialize/apply and extract/import wiring only. Land **A1 →
A2** first (the rehydrate prerequisite); B, C, D1, D2, E are mutually
independent.

### PR A1 — settings CSV: feature toggles  *(gap 2; prereq)*

- **Serialize** (`session_config_io/_serialize.py::_session_rows`): emit two
  boolean rows, `session.relationships_enabled` and
  `session.observers_enabled`.
- **Apply** (`_apply_session.py`): parse + apply the two bools. Respect the
  existing lock-on-data semantics (the toggles can't flip once
  relationship/observer rows exist) — settings import is already
  lifecycle-gated to draft/validated, so on the fresh rehydrate target
  they apply cleanly; on an existing populated session, skip-with-warning
  rather than fight the lock.
- **Route** the two keys through `_apply_parse.py` (session-level, already a
  routed prefix).
- **Test:** round-trip both toggles at `true`/`false`.
- Tiny (~2 serialize rows + apply). Ships on its own.

### PR A2 — settings CSV: `instrument_view_policies`  *(gap 1; prereq)*

The substantive prerequisite. Per `spec/visibility_policy.md` /
`instrument_view_policy.py`.

- **Serialize** (`_serialize.py`): new `_view_policy_rows(instrument, n)`
  called from `_instrument_blocks`, emitting per present
  `InstrumentViewPolicy` (per audience) the keys
  `instruments[n].view_policies[<audience>].while_ongoing_granularity`,
  `.while_ongoing_identification`, `.after_release_granularity`,
  `.after_release_identification`, `.observer_tag`. Cells are the enum
  strings + `observer_tag` string.
- **Apply** (`_apply_instrument.py`): view policies are children of the
  instrument, so recreate them inside the existing instrument
  wipe-and-rebuild pass — collect the view-policy cells per `(instrument
  index, audience)` in the parser, validate the enums against the model,
  and insert `InstrumentViewPolicy` rows. Add the parse routing in
  `_apply_parse.py` / a helper in `_apply_shared.py`.
- **Test:** round-trip a session carrying per-audience policies (all three
  audiences, both windows); assert unchanged.
- **Doc follow:** once merged, drop the "via prerequisite" wording in
  `docs/rehydrate.md` (§2 table, §6.2, §9) — view policies now round-trip.
- Medium. Depends on nothing but is the gate for Group 2 fidelity.

### PR B — observers CSV: `cohort_rule`  *(gap 3)*

- **Export** (`extracts/observers_extract.py`): append a `CohortRule`
  column to `HEADER`; serialize `json.dumps(observer.cohort_rule)` (empty
  when null). Append at the end for round-trip stability.
- **Import** (`csv_imports.py::parse_observer_csv`): read the optional
  `CohortRule` column, `json.loads` with shape validation (dict/None),
  thread it onto `ObserverImportRow` → `save_observers`.
- **Doc:** `spec/csv_contracts.md` observers contract.
- **Test:** observer round-trip incl. cohort rule; malformed JSON rejected.

### PR C — roster CSVs: `status`  *(gap 4)*

Decision recorded in Part C — preserve for all three participant rosters.

- **Export** (`reviewers_extract.py`, `reviewees_extract.py`): append a
  `Status` column; serialize `.status`. (Observers already export `Status`.)
- **Import** (`csv_imports.py`): `parse_reviewer_csv` / `parse_reviewee_csv`
  read the optional `Status` (default `"active"`, validated); make
  `parse_observer_csv` **read** the `Status` it currently ignores. Thread
  through the `*ImportRow` + `save_*`.
- **Back-compat:** appended optional column — CSVs without `Status` still
  import (→ active).
- **Doc:** `spec/csv_contracts.md`.
- **Test:** status round-trip for all three rosters; inactive preserved;
  missing column → active.

### PR D1 — clone: data shapes + retention  *(gap 6; gap 5 documented)*

- **`session_clone.py`:** add `DataShape` to the copy set — copy each
  `data_shapes` row, remapping `instrument_id` / `response_field_id`
  through the id maps clone already builds during the instrument copy.
  Copy `retention_exception` / `retention_overrides` in the `ReviewSession`
  constructor.
- **Scheduling anchors — deliberate split, not a copy.** Clone already
  resets `deadline`; a duplicate is meant to be re-scheduled, so leave
  `scheduled_activate_at` / `responses_release_at` / `_until` / the offset
  lists **reset by design** and *document* that in `session_clone`'s
  docstring + the coverage doc (rehydrate restores scheduling via the
  settings-CSV path, not clone, so this doesn't affect rehydrate). Flip
  gap 6 to ✅; annotate gap 5 as "intentional reset."
- **Test:** clone preserves data shapes + retention; asserts scheduling
  resets.

### PR D2 — settings CSV: session tags + `band1_touched_links`  *(gaps 7–8)*

- **Serialize** (`_serialize.py`): emit `session_tags[i]` rows (tag value)
  and an `instruments[n].band1_touched_links` row (JSON).
- **Apply:** upsert `SessionTag` rows (new `_apply_session_tag.py` or fold
  into `_apply_session.py`); set `instrument.band1_touched_links` in the
  instrument rebuild (`_apply_instrument.py`).
- **Test:** round-trip tags + `band1_touched_links`.

### PR E — asymmetry cleanups  *(gaps 9–11)*

- **Field-label export allowlist** (real code): filter
  `_serialize.py::_field_label_rows` to the same allowlist the importer
  enforces (`reviewer/reviewee.tag_1..3`, `pair_context.1..3`) so
  `settings.csv` never emits a row import would reject.
- **Instrument `order`** (doc): position is authoritative on apply; document
  that in `spec/csv_contracts.md` and leave the `order` cell as
  informational. No behaviour change.
- **`display_fields.label`** (doc): leave the dead column, note it; drop-via-
  migration deferred.
- **Test:** a `settings.csv` with only allowlisted labels round-trips; a
  non-allowlist label is no longer emitted.

---

## Group 2 — Rehydrate a complete extracted session

Implements `docs/rehydrate.md`. Depends on **Part A** (and, for full
fidelity, **B** + **C**). The reconstruction pipeline, naming, atomicity,
and target-lifecycle (`draft`, assignments generated, not activated) are
all specified there — this is the build ladder.

### Part F — Responses importer (the net-new machinery)

`app/services/extracts/responses_import.py` — a streaming parser for the
sectioned 21-column `responses.csv` (`docs/rehydrate.md` §6.4): identity →
new-PK resolution (reviewer/reviewee by lowered email, instrument by
`InstrumentShortLabel` with positional fallback, response field by
`(instrument, field_key)`), assignment lookup, and batched `Response`
insert with its **own** size limits (not `csv_imports`' 5000-row / 1 MiB
caps). Pure, unit-testable against a `responses.csv` produced by the real
extract — **lands independently of the rest**, so build it first.

### Part G — Pre-flight analyzer + validate page (mandatory gate)

The entry point is a **dedicated `/operator/sessions/rehydrate` page**
reached from a new **`Rehydrate`** button in the lobby search-card row
(between `Add new` and `Go to Archive`), **not** a card on Add New Session
(`docs/rehydrate.md` §3). Validation is a **mandatory gate** — no blind
rehydrate.

- **G1 — the analyzer.** `analyze_rehydrate_set(files) -> RehydrateReport`
  (in `session_rehydrate.py` or a sibling): completeness (files + headers),
  cross-file integrity (responses ↔ rosters ↔ settings references resolve —
  catches cross-session mixes), and a preview (derived `_REHYD` name/code +
  entity counts). Pure, unit-testable; reuses the Part F resolver in a
  count-only mode (no inserts). **Shared** by validate and commit so a
  green preview can't diverge from the run.
- **G2 — page + validate route + stash.** New
  `operator/session_rehydrate.html` (instructions card ½ top-left; upload +
  Validate/Rehydrate buttons ½ top-right; full-width details+findings card
  below) served by `GET /operator/sessions/rehydrate`; the lobby button in
  `sessions_list.html`; and `POST …/rehydrate/validate` (analyze → **stash**
  the set under a short-TTL operator-scoped token → render findings). The
  Rehydrate button stays disabled until a clean verdict; the findings card
  reuses the Validate-page severity vocabulary (`spec/validate_page.md`).
  **Stash needs no blob storage** — back it with a Postgres `bytea` row
  (recommended; survives the autoscale-to-2–3-instances story), or local
  temp-file / re-upload fallbacks (`docs/rehydrate.md` §3.3).

### Part H — Commit route + orchestrator

- **H1 — orchestrator service.** `session_rehydrate.rehydrate_session(db,
  *, files, user, correlation_id) -> ReviewSession` running the full
  pipeline (create draft → apply settings → import rosters + relationships →
  generate assignments + backfill from responses → load responses via Part
  F → land as draft, not activated), with all-or-nothing rollback, the
  `_REHYD[_n]` naming + unique-code + restored/not-restored description
  note. Register `session.rehydrated` in `EVENT_SCHEMAS`. Fully testable
  headless.
- **H2 — commit route.** `POST …/rehydrate/commit` — take the stash token,
  load the set, **re-run the analyzer** (expired/altered stash fails safely),
  and on a clean verdict call H1 and redirect to the new Session Home.

*Risk note — land F before G/H.* The responses importer is the only novel
algorithm; getting it right (and tested) in isolation de-risks the whole
feature. The analyzer (G1) reuses it; the page (G2) is testable against the
analyzer; the orchestrator (H1) before the commit route (H2).

---

## Group 2 — implementation (PR ladder)

Five PRs. Unlike Group 1, **PR G2 carries the segment's one Alembic
migration** (the stash table); everything else is service / route / template
wiring. Land **F first** (independent, de-risks the novel algorithm), then
the analyzer, then stash, then the page, then commit. Each PR that closes a
`docs/rehydrate.md` item updates that spec in the same PR.

### PR F — responses importer  *(net-new; independent)*

`app/services/extracts/responses_import.py` — the only genuinely new
algorithm (`docs/rehydrate.md` §6.4).

- **`parse_responses_csv(content) -> list[_ParsedResponseRow]`** — a
  streaming parser for the *sectioned* 21-column `responses.csv`
  (per-instrument preamble → blank → header → data). Pure; **its own size
  bound**, not `csv_imports`' 5000-row / 1 MiB caps (a 1,500-reviewer file
  is far larger). Each row yields `(reviewer_email, reviewee_email,
  instrument_short_label, field_key, value, saved_at, submitted_at,
  version)` with the positional `instrument_{n}` as the short-label
  fallback.
- **`load_responses(db, *, review_session, rows) -> ResponseLoadResult`** —
  resolve identity to the session's new PKs (reviewer/reviewee by lowered
  email, instrument by short-label, field by `(instrument, field_key)`);
  **find-or-create the assignment** for each `(reviewer, reviewee,
  instrument)` (`include=True`, `created_by_mode="manual"`, `is_self_review`
  = emails equal) so no response is orphaned; batched `Response` insert
  (`saved_at` / `submitted_at` / `version` preserved). Returns counts +
  unresolved-row warnings.
- **Tests:** parse a real extract `responses.csv` (multi-instrument,
  sectioned); load into a seeded session and assert byte-equal
  value/timestamps/version + backfilled assignments; a scale test well
  beyond 5000 rows.

### PR G1 — the pre-flight analyzer  *(pure; needs F's parser)*

`analyze_rehydrate_set(files) -> RehydrateReport` in
`app/services/session_rehydrate.py` (`docs/rehydrate.md` §3.3). Completeness
(required files + header match), **cross-file integrity** (responses emails
resolve in the rosters; instrument short-labels + field-keys resolve in
`settings.csv`; relationships/observers present iff the settings imply
them — catches cross-session mixes), and a **preview** (derived `_REHYD`
name/code + entity counts). Reuses F's parser in count-only mode + the
settings/roster parsers. Pure and unit-testable; no route yet.

- **Tests:** each verdict — clean, each missing file, malformed header,
  responses referencing an absent email, an absent instrument/field, the
  observers-vs-settings mismatch.

### PR G2 — the stash  *(the segment's only migration)*

`rehydrate_stashes` table (Alembic migration): `id`, `token` (unique),
`operator_user_id` FK, `payload` (`LargeBinary` — the zipped/serialized
file set; portable BLOB / bytea, **no `sqlalchemy.dialects.postgresql`
import** per the model convention), `created_at`. A thin
`rehydrate_stash` service: `put(files, user) -> token`, `get(token, user)`
(TTL-checked, operator-scoped), and a sweep of expired rows. Postgres-backed
so the Validate → Commit hand-off survives App Service scale-out
(`docs/rehydrate.md` §3.3). Round-trips both dialects (SQLite tests +
`ci-postgres`).

- **Tests:** put→get round-trip; expired token rejected; another operator's
  token rejected.

### PR G3 — the rehydrate page + validate route + lobby button

`GET /operator/sessions/rehydrate` → new `operator/session_rehydrate.html`
(instructions ½ top-left; upload + Validate/Rehydrate ½ top-right; full-width
details+findings below — `docs/rehydrate.md` §3.2); the `Rehydrate` `.btn`
in the lobby search-card row (`sessions_list.html`, between `Add new` and
`Go to Archive`); and `POST …/rehydrate/validate` (unpack ZIPs → G1 analyze
→ G2 stash → render findings, Rehydrate button gated on a clean verdict,
findings reusing the Validate-page severity vocabulary).

- **Tests:** page renders with the button disabled; validate on a clean set
  stashes + enables Rehydrate + shows the preview; validate on an
  incomplete set blocks with specific messages and no session created.

### PR H — commit route + orchestrator

- **Orchestrator** `session_rehydrate.rehydrate_session(db, *, files, user,
  correlation_id) -> ReviewSession` — the full pipeline (`docs/rehydrate.md`
  §6): create draft → apply settings (with the `_REHYD` name + unique-code
  rewrite) → import rosters + relationships + observers → generate
  assignments → load responses via F → land **draft, not activated**; the
  restored/not-restored description note; all-or-nothing rollback. Register
  `session.rehydrated` in `EVENT_SCHEMAS`.
- **Commit route** `POST …/rehydrate/commit` — load the stash by token,
  **re-run the analyzer** (stale/expired stash fails safe), and on a clean
  verdict call the orchestrator + redirect to the new Session Home.
- **Tests:** the full round-trip integration (`docs/rehydrate.md` §12 —
  build → extract → rehydrate → assert populations / instruments /
  assignments / byte-equal responses / `_REHYD` name + note); collision
  naming (`_REHYD` → `_REHYD_1`); mandatory-gate (commit with no / bad token
  rejected, no session); rollback leaves zero rows.

**Landing order:** F → G1 → (G2 ∥ G3-scaffold) → G3 → H. F and G2 are
mutually independent; G3 needs G1 + G2; H needs F + G1 + G3.

---

## Suggested landing order

1. **A** (settings round-trip: view policies + toggles) — prerequisite,
   self-contained.
2. **F** (responses importer) — independent, de-risks Group 2 early. Can
   run in parallel with A.
3. **B**, **C** (observer cohort + roster status) — rehydrate fidelity.
4. **G** (analyzer + validate page + stash) → **H** (commit + orchestrator)
   — needs A (+ B/C for fidelity) and F. G is the mandatory pre-flight gate;
   H can't ship without it.
5. **D1**, **D2**, **E** (clone convergence + cleanups) — independent
   hygiene; can land any time, not blocking.

Rehydrate can technically ship after A + F + G + H with B/C/D/E following,
but its description note + `docs/rehydrate.md` limitations must honestly
state whatever isn't harmonized yet.

---

## Done when

- `spec/roundtrip_coverage.md`'s config matrix has **no ❌ gaps** except the
  two explicitly out-of-scope rows (operator role grants, manual
  assignment overrides), each documented as such.
- A session exported (setup bundle + responses bundle) and rehydrated
  produces a `_REHYD` **draft** with matching settings, populations,
  regenerated assignments, and byte-equal responses — asserted by a
  round-trip integration test (`docs/rehydrate.md` §12).
- Export→import and clone no longer silently lose the Part A–D settings.

---

## Doc impact

- Update `spec/roundtrip_coverage.md` as each Part flips a gap (it is the
  living scoreboard for this segment).
- Update `spec/csv_contracts.md` for any new CSV columns (cohort rule,
  roster status).
- Update `spec/settings_inventory.md` §10 coverage table (currently omits
  view policies, cohort rule, `band1_touched_links`, reviewer
  `profile_link`).
- Update `spec/sessions_overview.md` for the new lobby search-card
  `Rehydrate` button (Part G) and describe the
  `/operator/sessions/rehydrate` page.
- On Group 2 ship, trim `docs/rehydrate.md` from "proposed" to
  "how it works today" and update `docs/status.md`.
- Register `session.rehydrated` in `EVENT_SCHEMAS`.

---

## Deliberately out of scope

- **Session-operator role-grant porting** — permissions, not config.
- **Manual per-pair assignment override round-trip** — assignments always
  regenerate from rules; only build an override importer if pilot feedback
  shows operators rely on hand-toggling pairs.
- **Not-restored-by-design items** (per `docs/rehydrate.md` §9):
  invitations, email-outbox send history, `results_acknowledged_at`,
  participant anonymization tokens.
