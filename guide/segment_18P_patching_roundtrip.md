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

Reviewer / reviewee CSVs carry no `Status` column, so re-import
reactivates everyone; the observers CSV *emits* `Status` but the importer
ignores it. Decide the policy first (it's a real product call):

- **Preserve** — add `Status` to the reviewer / reviewee extract headers +
  importers, and have `parse_observer_csv` read the `Status` it already
  exports; or
- **Reset (documented)** — accept that re-import reactivates everyone and
  say so in `spec/csv_contracts.md`.

Recommend **Preserve** (rehydrate should bring back inactive members as
inactive). Flip gap 4. *Small `AskUserQuestion`-worthy policy point at
implementation time.*

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
