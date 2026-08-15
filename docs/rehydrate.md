# Rehydrate an extracted session — functional spec

> **Status: proposed (not yet built).** This is a design spec for a new
> capability, written against the current code seams. `docs/` normally
> documents shipped behaviour; this file is the exception until the
> feature lands, at which point it should be trimmed to "how it works
> today." Companion to `spec/sessions_overview.md` (the lobby),
> `spec/setup_pages.md`, and `spec/assignments.md`.

## 1. What this is

**Rehydrate** turns a *complete set of extract CSV files* from a past
session back into a live, working session — same settings, same
populations, and with the collected response data repopulated. It is the
inverse of the Extract surfaces (`app/web/routes_operator/_extracts.py`).

The reconstructed session is always named **`<original name>_REHYD`**
(with a numeric suffix on collision — [§5](#5-naming-and-description)),
carries a provenance note appended to its Description, and is created on a
**dedicated `/operator/sessions/rehydrate` page** reached from a
**`Rehydrate`** button in the Sessions Lobby. Every run is **gated on a
mandatory pre-flight validation** ([§3](#3-entry-point-and-page)): the
operator uploads the extract set, runs **Validate**, sees a findings +
preview report, and only then can **Rehydrate**.

### Why it's not just "clone"

`session_clone.clone_session` already deep-copies a session's config +
roster into a fresh draft, and `session_config_io.apply_session_config`
already round-trips settings via CSV. Both operate on an **in-database
source** and neither copies **responses**. Rehydrate differs on two axes:

1. its source is **external CSV files** (an extract taken earlier, possibly
   from a session that has since been purged or archived), not a live row;
2. it **repopulates response data**, which nothing in the codebase can do
   today.

## 2. Capability boundary — what rehydrate can and cannot reconstruct

Grounded in what the extract actually captures and what importers exist:

| Session facet | Extract source | Import path today | Rehydrate approach |
|---|---|---|---|
| Session metadata, instruments (+ display/response fields), rule sets, field labels, email overrides, data shapes | `settings.csv` | ✅ `session_config_io.apply_session_config` | Apply as-is |
| Reviewers / Reviewees / Observers | `reviewers.csv` / `reviewees.csv` / `observers.csv` | ✅ `csv_imports.save_*` | Import as-is |
| Relationships (reviewer↔reviewee pairs + status + pair tags) | `relationships.csv` | ✅ `relationships.save_relationships` | Import as-is |
| **Assignments** | derived (rule-generated) | ⚠️ no importer — regenerated from rules | Regenerate from imported rule sets, then backfill any pair present in `responses.csv` |
| **Responses** (the data) | `responses.csv` (in the responses bundle) | ❌ **none — output-only** | **Net-new importer** ([§6.4](#64-load-responses)) |
| Instrument visibility policies (`instrument_view_policies`) | `settings.csv` (18P PR A2) | ✅ | Apply as-is |
| `relationships_enabled` / `observers_enabled` toggles | `settings.csv` (18P PR A1) | ✅ | Apply as-is |
| Invitations, email outbox, `results_acknowledged_at`, participant tokens | not reconstructable / regenerated | — | Not restored ([§9](#9-limitations-and-known-gaps)) |

Rows one to three, plus the two rows closed by the
[prerequisite](#prerequisite-extend-the-settings-round-trip), reuse
existing (or prerequisite-extended) settings/roster seams. The **responses**
row is the genuinely new work.

## Prerequisite: extend the settings round-trip

> **Status: shipped** — the two session feature toggles landed in **18P PR
> A1** and `instrument_view_policies` in **18P PR A2**. Both now round-trip
> through `settings.csv`, so rehydrate inherits them. Section kept as the
> design record.

**Separate work item, landed first — valuable on its own, and a hard
dependency of rehydrate.**

`instrument_view_policies` (the per-instrument 3×2 visibility grid) and the
session-level `relationships_enabled` / `observers_enabled` toggles are
currently serialized by neither `session_config_io` nor `session_clone`.
So they don't survive a plain `export settings.csv → import settings.csv`
today — a real gap in the **normal** settings round-trip, independent of
rehydrate. Close it there, not inside rehydrate:

- **Serialize** — extend `session_config_io._serialize` to emit
  `instruments[n].view_policies[audience].*` rows (the while-ongoing and
  after-release *granularity* + *identification* pairs and `observer_tag`,
  per `spec/visibility_policy.md`) and two `session.relationships_enabled`
  / `session.observers_enabled` rows.
- **Apply** — extend `session_config_io._apply` to parse and restore them
  within the existing instrument wipe-and-rebuild pass.
- **Test** — a round-trip test (`serialize → apply → assert view policies +
  toggles unchanged`), matching how the rest of the settings round-trip is
  covered.

Once this ships, `settings.csv` fully describes visibility policy and the
feature toggles, so **rehydrate inherits them for free** — no
rehydrate-specific view-policy code, and every session's export/import
(clone-by-config, backup/restore) also stops losing them. This is why it's
a prerequisite rather than a rehydrate sub-task.

## 3. Entry point and page

### 3.1 Getting there — the lobby "Rehydrate" button

Rehydrate has its **own page**, not a card on Add New Session. It's reached
from the **Sessions Lobby** (`/operator/sessions`): the search card's
button row — today `Cancel` · `Add new` · `Go to Archive`
(`app/web/templates/operator/sessions_list.html`) — gains a **`Rehydrate`**
button **between `Add new` and `Go to Archive`**, linking to
`GET /operator/sessions/rehydrate`. Same `.btn` styling as its siblings.

Giving it its own page removes the whole "ignore the other inputs" problem
the earlier Add-New-card design carried — there is no create form on this
page to bleed into.

### 3.2 The rehydrate page (`GET /operator/sessions/rehydrate`)

Same operator chrome and header nav as `/operator/sessions/new` (breadcrumb
back to the lobby; no session context yet — this page creates one). Layout:

```
┌─ Instructions (½, top-left) ──┐  ┌─ Upload + actions (½, top-right) ─┐
│ what a complete extract set   │  │ file upload (loose CSVs / ZIPs)   │
│ is; what's restored / not     │  │ [ Validate ]   [ Rehydrate ]      │
│ restored                      │  │        (Rehydrate disabled        │
│                               │  │         until validation passes)  │
└───────────────────────────────┘  └───────────────────────────────────┘
┌─ Details + validation output (full width) ────────────────────────────┐
│ empty until Validate runs; then the derived _REHYD name/code, preview  │
│ counts, and the findings list (blocking errors vs warnings)            │
└────────────────────────────────────────────────────────────────────────┘
```

- **Instructions card (½, top-left).** Brief: what a complete extract set
  is ([§4](#4-required-file-set)) and the restored / not-restored summary
  (mirrors the description note, [§5](#5-naming-and-description)). Alert
  tint. No "other inputs ignored" warning — there are none here.
- **Upload + actions card (½, top-right).** A `multiple` file input taking
  the loose CSVs and/or the two ZIP bundles (Setup + Responses, unpacked
  server-side — [§4](#4-required-file-set)), plus two buttons:
  - **Validate** — Primary Outline; always available. Runs the pre-flight
    ([§3.3](#33-pre-flight-validation-mandatory)).
  - **Rehydrate** — Primary; **disabled until the current upload has passed
    validation**. Commits the validated set.
- **Details + validation card (full width, below).** Empty on first load.
  After Validate it populates with the run's **basic details** (derived
  `_REHYD` name + unique code; preview counts — reviewers, reviewees,
  observers, relationships, instruments, assignments-to-generate,
  responses) and the **validation findings**, severity-chipped, reusing the
  Validate page's vocabulary (`spec/validate_page.md`).

### 3.3 Pre-flight validation (mandatory)

**Every rehydration passes through validation first — there is no blind
rehydrate.** The Rehydrate button is inert until a Validate run on the
current upload returns no blocking errors.

**One shared analyzer.** Both buttons route through a single pure function,
`analyze_rehydrate_set(files) -> RehydrateReport` ([§11](#11-new-machinery-to-build)),
so a green preview cannot diverge from what the commit actually does. The
report carries:

- **Completeness** — required files present, headers matching, and any
  extra/ignored files ([§4](#4-required-file-set)).
- **Cross-file integrity** — every reviewer/reviewee email in
  `responses.csv` resolves in the roster CSVs; every instrument short-label
  + field-key in `responses.csv` resolves in `settings.csv`;
  relationship/observer emails resolve; `relationships.csv` /
  `observers.csv` are present iff the settings imply them. These catch the
  most common real mistake — **files from two different sessions or a stale
  re-export**.
- **Preview** — the derived `_REHYD` name + code and the counts, so the
  operator can confirm it's the right session before committing.
- **Verdict** — blocking errors (block Rehydrate) vs warnings (allow, but
  surfaced).

**Straight-from-verdict-to-run flow (the stash design).**

1. **Validate** POSTs the upload to
   `POST /operator/sessions/rehydrate/validate`. The handler runs
   `analyze_rehydrate_set`, **stashes the uploaded set server-side** under a
   short-TTL, operator-scoped token, and re-renders the page with the
   full-width report + the token.
2. On a clean verdict the **Rehydrate** button activates, carrying the
   token. **The operator does not re-upload.**
3. **Rehydrate** POSTs the token to
   `POST /operator/sessions/rehydrate/commit`, which **re-runs
   `analyze_rehydrate_set` on the stashed set** (so an expired or altered
   stash fails safely), and — if still clean — runs the reconstruction
   pipeline ([§6](#6-reconstruction-pipeline)) and redirects to the new
   Session Home.

**Stash mechanism — no blob storage required.** The stash holds the
uploaded set between the Validate and Commit requests, keyed by an opaque,
operator-scoped, short-TTL token (cleaned up after commit or on expiry; a
foreign or expired token is rejected and the page asks for a re-upload).
Three no-blob options, in order of robustness:

1. **Postgres-backed stash (recommended).** Persist the uploaded bytes as a
   `bytea` row keyed by token, TTL-swept. Survives instance recycle **and**
   scale-out — which matters, because this app is sized to autoscale to 2–3
   App Service instances under load (`docs/architecture.md`,
   `azure_provision.md`), and a Validate on one instance / Commit on another
   must still find the stash. Uses infrastructure already provisioned (the
   database); no Storage Account.
2. **Local temp-file + App Service session affinity.** Simplest, and fine
   for the single-instance pilot, but the local file only exists on the
   instance that wrote it — it relies on session affinity routing the
   operator back there, and is lost on instance recycle. Fragile exactly
   when the app scales out.
3. **Re-upload on commit (no stash).** Zero state; the Commit POST carries
   the files again. Slightly worse UX; always available as the fallback.

None require blob storage. Prefer **(1)** so the straight-to-run flow stays
robust under scale-out; **(3)** is the safe minimum.

**Button styles.** Validate = Primary Outline; Rehydrate = Primary (per
`spec/domain_assumptions.md`). Rehydrate is additive — it creates a new
session and never mutates or deletes an existing one.

## 4. Required file set

Rehydrate needs the union of the **Setup bundle** and the **Responses
bundle**. The operator may upload the two ZIPs, the loose CSVs, or a mix;
the handler resolves files by name.

**Required always:**

| File | Header (must match) | Provides |
|---|---|---|
| `*_settings.csv` | `field,value,data_type` (`session_config_io._rows.HEADER`) | All config: session metadata, instruments + fields, rule sets, field labels, email overrides, data shapes |
| `*_reviewers.csv` | `ReviewerName,ReviewerEmail,ReviewerTag1..3,PhotoLink` | Reviewer population |
| `*_reviewees.csv` | `RevieweeName,RevieweeEmail,RevieweeTag1..3,PhotoLink` | Reviewee population |
| `*_responses.csv` | the 21-column responses header (`responses_extract.HEADER`) | The response data + `SavedAt`/`SubmittedAt`/`Version` |

**Required conditionally** (presence also *sets the feature toggle* — see
[§6.2](#62-apply-settings)):

| File | Needed when | Provides |
|---|---|---|
| `*_relationships.csv` | the session used relationships | `ReviewerEmail,RevieweeEmail,PairContextTag1..3,Status` pairs |
| `*_observers.csv` | the session used observers | `ObserverEmail,ObserverName,ObserverTag1,Status` |

**Completeness validation (the card's promise, enforced).** Before
creating anything, the handler verifies the four required files are
present and their headers match. On any miss it rejects the whole upload
with a specific, actionable error and creates **no** session — e.g.
*"Missing settings.csv — rehydrate needs the full extract set"* or
*"responses.csv header doesn't match the expected format; re-export via
Extract data → Extract all data."* Filenames are matched by suffix
(`*_settings.csv` etc.), tolerating the `{code}_` prefix the extracts
emit and any operator renaming that preserves the suffix.

**Ignored files.** `reviewer_stats.csv`, `reviewee_stats.csv`, the
per-instrument `*_instrument_{N}.csv`, saved data-shape CSVs, and
`participant_tokens.csv` may be present in the bundle but are **not read**
by rehydrate (stats/tokens are derived; per-instrument CSVs duplicate
`responses.csv`). They are silently ignored, not errors.

## 5. Naming and description

**Name.** Read the original name from the `session.name` row of
`settings.csv`. The rehydrated name is:

- `"<original name>_REHYD"` if no session with that exact name exists;
- otherwise `"<original name>_REHYD_1"`, `"_REHYD_2"`, … choosing the
  lowest free integer.

Collision is checked by exact-match against existing **session names the
operator owns** (`session_operators` for the caller). Names are **not**
unique in the schema (only `code` is — `review_session.py`), so this is a
service-level scan, mirroring how `session_clone` derives a unique *code*.
If appending the suffix would exceed the 255-char `name` limit, the base
is truncated to fit. Rehydrating an already-`_REHYD` session yields
`…_REHYD_REHYD` (literal rule; acceptable).

**Code.** The original `session.code` from `settings.csv` **cannot** be
reused — `sessions.code` has a unique index. Derive a fresh unique code
the way `session_clone._unique_code` does: `"<original code>-rehyd"`, then
`"-rehyd-2"`, … until free.

**Description.** Take the original `session.description` and append a
provenance paragraph that states, succinctly, what was and wasn't brought
across:

```
[Rehydrated {YYYY-MM-DD} from an extract of "{original name}"
({original code}).
Restored: settings, reviewers, reviewees, observers, relationships,
assignments (regenerated), and submitted responses.
Not restored: invitations, email send history, and participant
results-acknowledgements.]
```

(The date is stamped by the caller, not inside any pure/deterministic
layer. The restored/not-restored split is grounded in
`spec/roundtrip_coverage.md`.)

## 6. Reconstruction pipeline

Order matters — responses key onto assignments, which key onto instruments
+ rosters, which key onto the applied settings. The whole pipeline runs as
one logical unit; on any failure the partially-built session is hard-deleted
so no half-rehydrated session survives ([§7](#7-atomicity-and-audit)).

### 6.1 Create the shell session

Parse `settings.csv` first to learn the original name/code, then create a
new **draft** via `sessions.create_session` with:

- `name` = the computed `_REHYD[_n]` name,
- `code` = the derived unique code,
- `description` = original + provenance note,
- `relationships_enabled` / `observers_enabled` = presence of the
  respective CSV ([§6.2](#62-apply-settings)).

`create_session` adds the owner `SessionOperator`, seeds a default
instrument (immediately replaced by the settings apply), and writes
`session.created`.

### 6.2 Apply settings

Call `session_config_io.apply_session_config(db, new_session, rows)` with
the parsed `settings.csv` rows, **after rewriting two rows**: replace the
`session.name` value with the `_REHYD` name and the `session.code` value
with the derived code (otherwise apply would restore the original name and
collide on code). `apply` rebuilds instruments (+ display/response
fields), session rule sets, field labels, email overrides, and data
shapes, and restores per-instrument runtime flags including
`accepting_responses` and `responses_visible_when_closed`.

With the [prerequisite](#prerequisite-extend-the-settings-round-trip) in
place, `relationships_enabled` / `observers_enabled` **and** the instrument
visibility policies are carried in `settings.csv` and restored by `apply` —
no rehydrate-specific handling. (Defensive fallback for a legacy extract
taken before the prerequisite: infer the toggles from file presence and
leave view policies at defaults.)

### 6.3 Import populations and regenerate assignments

1. **Reviewers / Reviewees / Observers** via `csv_imports.save_reviewers`
   / `save_reviewees` / `save_observers` (observers only if enabled). Same
   dedup + email-lowercasing + cross-table-identity rules as normal
   import; `reviewees` keep their `email_or_identifier` (non-email handles
   allowed).
2. **Relationships** (if enabled) via `relationships.save_relationships`,
   resolving emails against the just-imported rosters.
3. **Assignments** — regenerate from the imported rule sets via the
   canonical `assignments.generate` path (deterministic given seed + rules
   + populations, so it reproduces the original assignment graph for
   rule-driven sessions). Then **backfill**: for every distinct
   `(reviewer, reviewee, instrument)` that appears in `responses.csv` but
   has no generated assignment, create one (`include=True`,
   `is_self_review` = reviewer-email == reviewee-email,
   `created_by_mode="manual"`). This guarantees every response has a home
   even where a manual per-pair toggle diverged from the rules
   ([§9](#9-limitations-and-known-gaps)).

### 6.4 Load responses

**New machinery** (no importer existed — responses were export-only).
Implemented in **18P PR F** (`app/services/extracts/responses_import.py`):
`parse_responses_csv` + `load_responses`. For each data row, resolve
identity to the newly-created PKs and insert a `Response`:

- **Reviewer** ← `ReviewerEmail` (lower-cased) → new `Reviewer.id`.
- **Instrument** ← `InstrumentShortLabel` (primary key for the match;
  unique per session), falling back to the positional `InstrumentName`
  = `instrument_{n}` → the instrument at `order = n`.
- **Response field** ← `(instrument, FieldKey)` →
  `InstrumentResponseField.id` (unique `(instrument_id, field_key)`).
- **Per-reviewee rows** (`InstrumentFlavour = per-reviewee`) — **Reviewee**
  ← `RevieweeEmail` (lower-cased / identifier); **Assignment** ←
  `(reviewer, reviewee, instrument)`, **find-or-create** (backfills a pair
  the rules didn't regenerate — [§6.3](#63-import-populations-and-regenerate-assignments)).
- **Insert** `Response(assignment_id, response_field_id, value=Value,
  saved_at=parse(SavedAt), submitted_at=parse(SubmittedAt),
  version=Version)`, respecting the unique `(assignment_id,
  response_field_id)` constraint. `Value` maps straight to the `Text`
  column (empty cell → `NULL`; no type coercion).

**Group-scoped instruments — fan-out.** The export **collapses** a
group-scoped instrument's per-member Response rows to *one row per group*:
`RevieweeEmail` is empty and the group identity is composed into
`RevieweeName` (e.g. `"Team A (Ana, Bo)"`), with
`InstrumentFlavour = group-scoped`. So a group row is **fanned back out**
to every member assignment of the matching group. The group is matched by
**reusing the exporter's own identity computation**
(`responses_extract._group_export_index`) on the reconstructed session —
so the import identity is byte-identical to what the export composed — then
the value is written to each member assignment's `Response`. (This is why
the responses round-trip needs the assignments regenerated first: the
member assignments are the fan-out targets.)

**Format.** `responses.csv` is a field-dictionary **preamble** (per
instrument: an `instrument_{n}` row then `(field_key, help_text)` rows), a
blank row, then the single 21-column header, then one data table. The
parser streams to the header, then reads data rows; the
`InstrumentShortLabel` column (positional `InstrumentName` fallback) is the
durable instrument key.

**Scale.** `responses.csv` for a large session (e.g. 1,500 reviewers) far
exceeds the roster importer's `MAX_ROWS = 5000` / `MAX_BYTES = 1 MiB`
caps (`csv_imports.py`). The responses parser therefore **must not** reuse
those limits — it streams rows and inserts in batches
(`Session.bulk_save_objects` or chunked `add_all` + periodic flush),
with its own, higher bound. This is called out because reusing
`csv_imports`' guard rails here would silently truncate real data.

### 6.5 Land the session

Leave the session in **`draft`** — assignments are generated
([§6.3](#63-import-populations-and-regenerate-assignments)) and all data is
loaded, but the session is **not activated** ([§8](#8-target-lifecycle-state)) —
and write the `session.rehydrated` audit event.

## 7. Atomicity and audit

- **All-or-nothing.** If any step fails (bad file, unresolvable identity,
  constraint violation), roll back and **hard-delete** the new session
  (`sessions.delete_session`) so the lobby never shows a half-built
  rehydrated session. Report the failing step to the operator.
- **Audit.** Emit one `session.rehydrated` event on success, with a
  `counts` payload (`reviewers`, `reviewees`, `observers`, `relationships`,
  `assignments`, `responses`) and a `context`/`refs` recording the original
  name + code from the extract. Register `session.rehydrated` in
  `EVENT_SCHEMAS` (the strict-mode test gate rejects unregistered emitters
  — see `CLAUDE.md` "Audit events").

## 8. Target lifecycle state

The rehydrated session lands in **`draft`**, with **all assignments
generated** ([§6.3](#63-import-populations-and-regenerate-assignments)) and
all response data loaded, but **not activated**. The operator reviews the
rebuilt session and runs Validate → Activate themselves when ready.

Rationale for not auto-activating: `activate_session` has real gates (a
clean `ReadinessReport`, acknowledged warnings) that a rehydrate shouldn't
silently bypass, and activation force-flips **every** instrument to
`accepting_responses=True` — which would *re-open* a previously-closed
session for new input and overwrite the per-instrument runtime flags that
[§6.2](#62-apply-settings) just restored. A rehydrated draft with fully
generated assignments and loaded data is completely viewable and operable;
activation stays a deliberate, separate operator gesture.

## 9. Limitations and known gaps

Stated plainly so the card copy and the PR description can be honest:

- **Visibility policies + feature toggles** (`instrument_view_policies`,
  `relationships_enabled`, `observers_enabled`) round-trip through
  `settings.csv` once the
  [prerequisite](#prerequisite-extend-the-settings-round-trip) lands —
  which is a hard dependency of rehydrate, so by ship time these are not
  gaps. (Only a legacy pre-prerequisite extract would fall back to default
  view policies + presence-inferred toggles.)
- **Manual per-pair assignment overrides don't round-trip** (confirmed —
  `spec/roundtrip_coverage.md`). A pair the operator hand-toggled via the
  Assignments page's bulk Activate / Inactivate (the `Assignment.include`
  flag) is captured by no export and is reset to `include=True` when
  assignments regenerate. Rehydrate backfills an assignment for any pair
  that *has* responses ([§6.3](#63-import-populations-and-regenerate-assignments)),
  so no response is lost, but an *empty-but-included* manual assignment
  won't reappear.
- **Observer cohort rules aren't restored** (confirmed). The observers CSV
  carries only Email/Name/Tag1/Status, so `Observer.cohort_rule` is lost —
  rehydrated observers come back without their cohort scoping. *Fix path:*
  carry `cohort_rule` in the observers CSV or serialize observers through
  `session_config_io` (`spec/roundtrip_coverage.md` recommendation 2).
- **Not restored** (confirmed): invitations, email-outbox send history,
  `Reviewee.results_acknowledged_at`, and participant anonymization tokens
  (regenerated fresh for the new session, so they won't match the original
  `participant_tokens.csv`). These match `session_clone`'s existing
  exclusions and are acceptable for a working copy — and are the basis of
  the [description note](#5-naming-and-description)'s "not restored" line.
- **Group-scoped instruments / self-reviews** reconstruct correctly as
  long as the rule sets + `group_kind` in `settings.csv` regenerate the
  same graph; the responses backfill covers any residual pairs.

## 10. Resolved decisions

1. **Target lifecycle** — land as **`draft`** with all assignments
   generated but **not activated** ([§8](#8-target-lifecycle-state)). The
   operator activates deliberately.
2. **Visibility-policy / config gap** — closed **outside** rehydrate, as a
   separate [prerequisite](#prerequisite-extend-the-settings-round-trip)
   that extends the normal settings round-trip to cover
   `instrument_view_policies` and the feature toggles.
3. **Name-collision scope** — match `_REHYD` names against the **operator's
   own** sessions ([§5](#5-naming-and-description)).

## 11. New machinery to build

Grounded in the existing seams so the diff stays small:

- **Page + lobby button.** A new `operator/session_rehydrate.html`
  template (the two half-width cards + full-width output,
  [§3.2](#32-the-rehydrate-page-get-operatorsessionsrehydrate)) served by
  `GET /operator/sessions/rehydrate`, plus the `Rehydrate` `.btn` in the
  lobby search-card row (`sessions_list.html`,
  [§3.1](#31-getting-there--the-lobby-rehydrate-button)).
- **Analyzer (shared, pure).** `app/services/session_rehydrate.py` (or a
  sibling) — `analyze_rehydrate_set(files) -> RehydrateReport`: the
  completeness + cross-file-integrity + preview checks
  ([§3.3](#33-pre-flight-validation-mandatory)). Called by **both** the
  validate route and (re-run) the commit route, so validate and commit
  can't drift. Pure and unit-testable against a produced extract set.
- **Two routes, not one.**
  - `POST /operator/sessions/rehydrate/validate` — unpack ZIPs, resolve
    files, run the analyzer, **stash** the set under a token, re-render the
    page with the report.
  - `POST /operator/sessions/rehydrate/commit` — take the token, load the
    stash, **re-run the analyzer**, and on a clean verdict call the
    orchestrator, then redirect to the new Session Home.
- **Stash.** A short-TTL, operator-scoped store keyed by token, cleaned up
  after commit or on expiry — **no blob storage**; a Postgres `bytea` row is
  the recommended backing (survives scale-out), with local temp-file or
  re-upload as fallbacks ([§3.3](#33-pre-flight-validation-mandatory)).
- **Orchestrator service.** `session_rehydrate.rehydrate_session(db, *,
  files, user, correlation_id) -> ReviewSession`, running the
  [§6](#6-reconstruction-pipeline) pipeline and owning the all-or-nothing
  rollback. Reuses `sessions.create_session`,
  `session_config_io.apply_session_config`, `csv_imports.save_*`,
  `relationships.save_relationships`, and `assignments.generate`. Assumes a
  validated set (the commit route re-checks first).
- **Responses importer.** `app/services/extracts/responses_import.py` (the
  net-new piece) — a streaming parser for the sectioned 21-column
  `responses.csv` and the identity→PK resolution + batched `Response`
  insert in [§6.4](#64-load-responses). Its own size limits, independent
  of `csv_imports`. Shared by the analyzer (dry-run: resolve + count, don't
  insert) and the orchestrator (insert).
- **Audit.** Register `session.rehydrated` in `EVENT_SCHEMAS`.

## 12. Testing expectations

- **Round-trip integration test.** Build a session with reviewers,
  reviewees, relationships, multiple instruments, and submitted responses;
  run the real Extract routes to produce the CSVs; feed them to
  `rehydrate_session`; assert the new session has the `_REHYD` name, the
  appended description note, matching populations, matching instruments +
  fields, regenerated assignments covering every response, and byte-equal
  response values / `SavedAt` / `SubmittedAt` / `Version`.
- **Collision test** — rehydrating the same extract twice yields `_REHYD`
  then `_REHYD_1`, with distinct unique codes.
- **Analyzer tests** — the shared `analyze_rehydrate_set` returns the right
  verdict for: a complete clean set; each missing required file; a
  malformed header; a `responses.csv` referencing an email absent from the
  rosters (cross-session mix); an instrument short-label/field-key absent
  from `settings.csv`; `observers.csv` present/absent vs the settings. Each
  blocking case blocks; warnings don't.
- **Mandatory-gate test** — `POST …/rehydrate/commit` with no prior
  validation (or a bad/expired token) is rejected and creates no session.
- **Stash round-trip test** — Validate stashes the set and returns a token;
  Commit with that token reconstructs from the stash without re-upload;
  another operator's token is rejected.
- **Rollback test** — a mid-pipeline failure leaves zero new rows.
- **Scale test** — a `responses.csv` well beyond 5000 rows validates and
  imports fully (guards the [§6.4](#64-load-responses) limit note).

## 13. References

- Extract surfaces: `app/web/routes_operator/_extracts.py`,
  `app/services/extracts/` (`responses_extract.py`, `reviewers_extract.py`,
  `reviewees_extract.py`, `relationships_extract.py`, `observers_extract.py`,
  `zip_bundle.py`).
- Config round-trip: `app/services/session_config_io/`
  (`_serialize.py`, `_apply.py`, `_rows.py`).
- Roster import: `app/services/csv_imports.py`,
  `app/services/relationships.py`.
- Create / clone / lifecycle: `app/services/sessions.py`,
  `app/services/session_clone.py`, `app/services/session_lifecycle.py`.
- Assignments: `app/services/assignments/` + `spec/assignments.md`.
- Round-trip coverage matrix: `spec/roundtrip_coverage.md` (what survives
  export→import today, and the gaps this spec depends on closing).
- Lobby / entry UI: `spec/sessions_overview.md`,
  `app/web/templates/operator/sessions_list.html` (the search-card button
  row that gains `Rehydrate`), `app/web/routes_operator/_session_home.py`
  (the `/operator/sessions/new` page whose chrome the rehydrate page
  mirrors).
- Validate-page vocabulary (findings / severity chips reused by the
  full-width output card): `spec/validate_page.md`.
